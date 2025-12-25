"""Normalizer Lambda - Data Refinement and Storage

This Lambda function implements the "Closer" pattern:
1. Receives raw Textract output from parallel extractions
2. Uses Claude 3.5 Haiku to normalize and validate the data
3. Stores clean JSON to DynamoDB (for app) and S3 (for audit)
4. Ensures data conforms to expected schema

Cost optimization: Claude 3.5 Haiku provides excellent normalization
quality at ~70% lower cost than Sonnet 4 ($0.03 vs $0.09 per document).
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock_client = boto3.client('bedrock-runtime')

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME')
TABLE_NAME = os.environ.get('TABLE_NAME')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-5-haiku-20241022-v1:0')


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types for DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def convert_floats_to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(i) for i in obj]
    return obj


def build_credit_agreement_prompt(raw_text_sections: Dict[str, str]) -> str:
    """Build a specialized prompt for Credit Agreement raw text extraction.

    Uses the field-by-field extraction approach with specific keywords and value mappings.

    Args:
        raw_text_sections: Dict mapping section names to raw text content

    Returns:
        Specialized extraction prompt
    """
    sections_text = ""
    for section_name, text in raw_text_sections.items():
        sections_text += f"\n\n=== {section_name.upper()} SECTION ===\n{text}"

    return f"""Extract financial data from the Credit Agreement text below and return ONLY a JSON object (no other text).

RAW TEXT FROM DOCUMENT:
{sections_text}

EXTRACTION INSTRUCTIONS:

For each field below, search for the specified keywords and extract the value. Apply the
format rules and validate against allowed values where specified.

=== AGREEMENT INFORMATION ===

1. **Document Type**
   - Keywords: "Credit Agreement", "Amendment", "Restatement", "Loan Agreement"
   - Format: String describing the document type
   - Example: "Third Amended and Restated Credit Agreement"

2. **Agreement Date / Effective Date**
   - Keywords: "dated as of", "effective as of", "Closing Date"
   - Format: YYYY-MM-DD
   - Note: Look for dates near the beginning of the document

3. **Maturity Date**
   - Keywords: "Maturity Date", "Termination Date", "expires on"
   - Format: YYYY-MM-DD
   - Note: Usually defined in definitions section or facility terms

4. **Amendment Number**
   - Keywords: "Amendment No.", "First Amendment", "Second Amendment"
   - Format: String or null

=== PARTIES ===

5. **Borrower**
   - Keywords: "Borrower", "the Company", "as borrower"
   - Extract: Full legal name and jurisdiction (state of incorporation)
   - Format: {{"name": string, "jurisdiction": string}}

6. **Administrative Agent**
   - Keywords: "Administrative Agent", "as Agent", "Agent"
   - Extract: Bank name (e.g., "Wells Fargo Bank, National Association")

7. **Lead Arrangers**
   - Keywords: "Lead Arranger", "Joint Lead Arranger", "Bookrunner"
   - Extract: List of bank names

8. **Guarantors**
   - Keywords: "Guarantors", "Subsidiary Guarantors", "jointly and severally"
   - Extract: List of guarantor names or description

=== FACILITY TERMS ===

9. **Aggregate Maximum Revolving Credit Amount**
   - Keywords: "Aggregate Maximum Revolving Credit Amount", "Maximum Amount"
   - Format: Number (e.g., 900000000 for $900,000,000)

10. **Aggregate Elected Revolving Credit Commitment**
    - Keywords: "Aggregate Elected Revolving Credit Commitment", "Revolving Credit Commitment"
    - Format: Number

11. **LC Commitment / Sublimit**
    - Keywords: "LC Commitment", "Letter of Credit Sublimit", "L/C Sublimit"
    - Format: Number or percentage string (e.g., "10.0% of aggregate Revolving Credit Commitments")

12. **Swingline Sublimit**
    - Keywords: "Swingline Sublimit", "Swing Line"
    - Format: Number

13. **Term Loan Commitments**
    - Keywords: "Term Loan A Commitment", "Term Loan B", "Term Commitment"
    - Format: Number for each term loan type

=== APPLICABLE RATES (PRICING) ===

14. **Reference Rate**
    - Keywords: "Term SOFR", "SOFR", "Term Benchmark", "ABR", "Base Rate", "Prime"
    - Format: String identifying the rate type

15. **Floor Rate**
    - Keywords: "Floor", "floor rate", "0%", "0.00%"
    - Format: Decimal (e.g., 0.0 for 0%)

16. **Pricing Tiers** (CRITICAL - extract from "Applicable Rate" or "Applicable Margin" tables)
    - Look for tables with columns like: Level, Threshold, Term SOFR Spread, ABR Spread, Commitment Fee
    - Keywords: "Applicable Rate", "Applicable Margin", "Pricing Level", "Pricing Grid"
    - Extract each tier with:
      - level: "I", "II", "III", "IV", "V" or "Level 1", "Level 2", etc.
      - threshold: Availability or financial metric condition (e.g., "≥ $300,000,000", "< $150,000,000")
      - termSOFRSpread: Decimal (e.g., 0.015 for 1.50%)
      - abrSpread: Decimal (e.g., 0.005 for 0.50%)
      - unusedCommitmentFeeRate: Decimal (e.g., 0.002 for 0.20%)
      - lcFeeRate: Decimal if specified

=== FEES ===

17. **Commitment Fee Rate**
    - Keywords: "Commitment Fee", "Unused Fee", "Unused Commitment Fee"
    - Format: Decimal (e.g., 0.002 for 0.20%)
    - Note: May vary by pricing tier

18. **LC Fee Rate**
    - Keywords: "Letter of Credit Fee", "L/C Fee", "LC Participation Fee"
    - Format: Decimal

19. **Fronting Fee**
    - Keywords: "Fronting Fee", "L/C Fronting Fee"
    - Format: Decimal (e.g., 0.00125 for 0.125%)

20. **Agency Fee**
    - Keywords: "Agency Fee", "Administrative Agent Fee"
    - Format: Number (annual fee amount)

=== COVENANTS ===

21. **Fixed Charge Coverage Ratio**
    - Keywords: "Fixed Charge Coverage Ratio", "FCCR", "Fixed Charges"
    - Extract: Minimum ratio requirement (e.g., 1.15 or "1.15:1.00")
    - Format: {{"minimum": decimal, "testPeriod": string}}

22. **Other Financial Covenants**
    - Keywords: "Leverage Ratio", "Interest Coverage", "Debt to EBITDA"
    - Extract: List of covenant descriptions

=== LENDER COMMITMENTS (from Schedule 2.01 or Lender table) ===

23. **Lender Commitments**
    - Keywords: "Schedule 2.01", "Lender", "Commitment", "Applicable Percentage"
    - For each lender extract:
      - lenderName: Full legal name
      - applicablePercentage: Decimal (e.g., 0.216 for 21.60%)
      - revolvingCreditCommitment: Number
      - termCommitment: Number (if applicable)
    - Note: Percentages should sum to 100% (1.0)

=== OUTPUT FORMAT ===

Return ONLY valid JSON matching this structure:
{{
  "loanData": {{
    "creditAgreement": {{
      "agreementInfo": {{
        "documentType": <string or null>,
        "agreementDate": <YYYY-MM-DD or null>,
        "effectiveDate": <YYYY-MM-DD or null>,
        "maturityDate": <YYYY-MM-DD or null>,
        "amendmentNumber": <string or null>
      }},
      "parties": {{
        "borrower": {{"name": <string>, "jurisdiction": <string>}},
        "coBorrowers": [],
        "administrativeAgent": <string or null>,
        "leadArrangers": [<string>],
        "swinglineLender": <string or null>,
        "lcIssuer": <string or null>,
        "guarantors": [<string>]
      }},
      "facilities": [],
      "facilityTerms": {{
        "aggregateMaxRevolvingCreditAmount": <number or null>,
        "aggregateElectedRevolvingCreditCommitment": <number or null>,
        "lcCommitment": <number or null>,
        "lcSublimit": <string or number or null>,
        "swinglineSublimit": <number or null>,
        "termLoanACommitment": <number or null>,
        "termCommitment": <number or null>
      }},
      "applicableRates": {{
        "referenceRate": <string or null>,
        "floor": <decimal or null>,
        "pricingBasis": <string or null>,
        "tiers": [
          {{
            "level": <string>,
            "threshold": <string>,
            "termSOFRSpread": <decimal or null>,
            "abrSpread": <decimal or null>,
            "unusedCommitmentFeeRate": <decimal or null>,
            "lcFeeRate": <decimal or null>
          }}
        ]
      }},
      "fees": {{
        "commitmentFeeRate": <decimal or null>,
        "lcFeeRate": <decimal or null>,
        "frontingFeeRate": <decimal or null>,
        "agencyFee": <number or null>
      }},
      "paymentTerms": {{
        "interestPaymentDates": [<string>],
        "interestPeriodOptions": [<string>],
        "paymentDay": <string or null>
      }},
      "covenants": {{
        "fixedChargeCoverageRatio": {{
          "minimum": <decimal or null>,
          "testPeriod": <string or null>
        }},
        "otherCovenants": [<string>]
      }},
      "lenderCommitments": [
        {{
          "lenderName": <string>,
          "applicablePercentage": <decimal>,
          "revolvingCreditCommitment": <number or null>,
          "termCommitment": <number or null>
        }}
      ]
    }}
  }},
  "validation": {{
    "isValid": <boolean>,
    "confidence": "high" | "medium" | "low",
    "crossReferenceChecks": [],
    "validationNotes": [<string>],
    "missingRequiredFields": [<string>]
  }},
  "audit": {{
    "extractionSources": [
      {{
        "field": <string>,
        "sourceSection": <string>,
        "rawValue": <string>,
        "normalizedValue": <any>
      }}
    ]
  }}
}}

CRITICAL INSTRUCTIONS:
- Your response must be ONLY the JSON object - no explanations, no preamble, no markdown code blocks
- Start your response with {{ and end with }}
- Convert ALL percentages to decimals (e.g., "1.50%" → 0.015, "21.60%" → 0.216)
- Convert ALL currency amounts to numbers without symbols (e.g., "$900,000,000" → 900000000)
- Dates must be in YYYY-MM-DD format
- If a value cannot be confidently extracted, use null
- NEVER guess or hallucinate values
- Include validation notes for any uncertain extractions
- Track which section each value was extracted from in the audit trail

Output the JSON now:"""


def clean_extraction_for_normalization(extraction: Dict[str, Any], max_raw_text_chars: int = 5000) -> Dict[str, Any]:
    """Clean and truncate extraction data to reduce payload size for Bedrock.

    Args:
        extraction: Raw extraction dict from Textract/PyPDF
        max_raw_text_chars: Maximum characters to keep from raw text

    Returns:
        Cleaned extraction dict with essential data only
    """
    if not isinstance(extraction, dict):
        return extraction

    cleaned = {}

    # Copy essential metadata
    for key in ['creditAgreementSection', 'status', 'pageNumbers', 'pageCount',
                'pagesProcessed', 'textractFailed', 'fallbackUsed', 'usedImageRendering',
                'documentId', 'key', 'extractionType', 'pageNumber']:
        if key in extraction:
            cleaned[key] = extraction[key]

    # Clean results
    results = extraction.get('results', {})
    if isinstance(results, dict):
        cleaned_results = {}

        # Keep queries but remove geometry (not needed for normalization)
        if 'queries' in results:
            cleaned_queries = {}
            for query_text, answer_data in results['queries'].items():
                if isinstance(answer_data, dict):
                    # Keep only answer and confidence, remove geometry
                    cleaned_queries[query_text] = {
                        'answer': answer_data.get('answer'),
                        'confidence': answer_data.get('confidence'),
                        'sourcePage': answer_data.get('sourcePage')
                    }
                else:
                    cleaned_queries[query_text] = answer_data
            cleaned_results['queries'] = cleaned_queries

        # Keep tables but simplify structure
        if 'tables' in results:
            tables_data = results['tables']
            if isinstance(tables_data, dict):
                cleaned_tables = []
                for table in tables_data.get('tables', []):
                    # Keep only rows data, remove individual cell confidence
                    cleaned_tables.append({
                        'rows': table.get('rows', []),
                        'sourcePage': table.get('sourcePage')
                    })
                cleaned_results['tables'] = {
                    'tables': cleaned_tables,
                    'tableCount': tables_data.get('tableCount', len(cleaned_tables))
                }

        # Truncate raw text if too long
        if 'rawText' in results:
            raw_text = results['rawText']
            if len(raw_text) > max_raw_text_chars:
                cleaned_results['rawText'] = raw_text[:max_raw_text_chars] + f"\n\n... [truncated, {len(raw_text) - max_raw_text_chars} chars omitted]"
            else:
                cleaned_results['rawText'] = raw_text

        cleaned['results'] = cleaned_results

    return cleaned


def normalize_with_bedrock(raw_extractions: List[Dict[str, Any]], document_id: str) -> Dict[str, Any]:
    """Use Claude 3.5 Haiku to normalize and validate extracted data.

    Args:
        raw_extractions: List of extraction results from parallel Textract operations
        document_id: Unique document identifier

    Returns:
        Normalized and validated data dictionary
    """
    # Check if this is a Credit Agreement and whether we have Textract data or only raw text
    is_credit_agreement = False
    has_textract_data = False
    raw_text_only_sections = {}

    for ext in raw_extractions:
        if isinstance(ext, dict):
            section = ext.get('creditAgreementSection')
            if section:
                is_credit_agreement = True
                results = ext.get('results', {})
                if isinstance(results, dict):
                    # Check if we have Textract query results or tables
                    has_queries = bool(results.get('queries'))
                    has_tables = bool(results.get('tables', {}).get('tables'))
                    if has_queries or has_tables:
                        has_textract_data = True
                    # Also collect raw text for sections that ONLY have raw text (Textract failed)
                    raw_text = results.get('rawText')
                    if raw_text and not has_queries and not has_tables:
                        if len(raw_text) > 5000:
                            raw_text = raw_text[:5000] + f"\n\n... [truncated]"
                        raw_text_only_sections[section] = raw_text

    # Determine which prompt path to use:
    # - If ANY section has Textract data (queries/tables), use the general normalization path
    # - Only use raw text prompt if ALL Credit Agreement sections only have raw text (complete Textract failure)
    use_raw_text_prompt = is_credit_agreement and raw_text_only_sections and not has_textract_data

    if use_raw_text_prompt:
        print(f"Using specialized Credit Agreement raw text extraction prompt for {len(raw_text_only_sections)} sections (Textract failed)")
        prompt = build_credit_agreement_prompt(raw_text_only_sections)
    else:
        # Clean and truncate extractions before sending to Claude
        cleaned_extractions = [clean_extraction_for_normalization(ext) for ext in raw_extractions]
        extractions_json = json.dumps(cleaned_extractions, indent=2, cls=DecimalEncoder)
        if is_credit_agreement:
            print(f"Using general normalization with Textract data for Credit Agreement ({len(cleaned_extractions)} sections)")
        print(f"Cleaned extractions JSON size: {len(extractions_json)} chars")

        prompt = f"""You are a financial data normalizer for mortgage loan documents. 

You have received raw OCR extraction results from different parts of a loan document package.
Your job is to normalize, validate, and structure this data into a clean, consistent format.

RAW EXTRACTION DATA:
{extractions_json}

NORMALIZATION RULES:

1. **Interest Rates**:
   - Convert to decimal format (e.g., "5.5%" or "5.500%" -> 0.055)
   - Handle text formats ("Five and a half percent" -> 0.055)

2. **Currency/Dollar Amounts**:
   - Convert to numeric format without symbols (e.g., "$250,000.00" -> 250000.00)
   - Handle text formats ("Two hundred fifty thousand" -> 250000.00)

3. **Names**:
   - Convert to Title Case ("SMITH, JOHN A" -> "John A Smith")
   - Handle various formats consistently

4. **Dates**:
   - Convert to ISO 8601 format (YYYY-MM-DD)
   - Handle various input formats ("01/15/2024", "January 15, 2024", etc.)

5. **Percentages (non-rates)**:
   - Convert to decimal (e.g., "80%" -> 0.80)
   - For applicable percentages (lender shares), keep as decimal (e.g., "21.60%" -> 0.216)

6. **Credit Agreement Specific**:
   - Interest rate spreads/margins: Convert percentages to decimal (e.g., "4.25%" -> 0.0425, "2.50%" -> 0.025)
   - Floor rates: Convert to decimal (e.g., "0%" -> 0.0)
   - Facility usage tiers: Preserve as strings (e.g., "≥ 90%", "< 90%", "≤ 75%")
   - Availability-based tiers: Preserve thresholds as strings (e.g., "≥ $20,000,000", "< $10,000,000")
   - Commitment amounts: Convert to numeric without currency symbols
   - Sublimits: If percentage-based, preserve as string (e.g., "10.0% of aggregate Revolving Credit Commitments")
   - Lender names: Preserve full legal names as-is
   - Reference rates: Identify type (e.g., "Term SOFR", "Term Benchmark", "ABR", "Prime")
   - Interest payment dates: List as month names (e.g., ["March", "June", "September", "December"])
   - Interest period options: List as strings (e.g., ["1 month", "3 months", "6 months"])
   - Covenants: Extract ratio requirements (e.g., Fixed Charge Coverage Ratio minimum 1.15:1.00)
   - Fee rates: Convert to decimal (e.g., "0.20%" -> 0.002, "0.125%" -> 0.00125)
   - Facility types: Identify all facilities (Revolving Credit, Term Loan A, Term Loan Bond Redemption, Swingline, LC)

7. **Missing/Unclear Data**:
   - If data cannot be confidently extracted, use null
   - NEVER hallucinate or guess missing values
   - Add a note in the validation_notes field

OUTPUT SCHEMA:
{{
  "loanData": {{
    "promissoryNote": {{
      "interestRate": <decimal or null>,
      "principalAmount": <number or null>,
      "borrowerName": <string or null>,
      "coBorrowerName": <string or null>,
      "maturityDate": <ISO date string or null>,
      "monthlyPayment": <number or null>,
      "firstPaymentDate": <ISO date string or null>
    }},
    "closingDisclosure": {{
      "loanAmount": <number or null>,
      "interestRate": <decimal or null>,
      "monthlyPrincipalAndInterest": <number or null>,
      "estimatedTotalMonthlyPayment": <number or null>,
      "closingCosts": <number or null>,
      "cashToClose": <number or null>,
      "fees": [
        {{
          "name": <string>,
          "amount": <number>
        }}
      ]
    }},
    "form1003": {{
      "borrowerInfo": {{
        "name": <string or null>,
        "ssn": <string or null>,
        "dateOfBirth": <ISO date string or null>,
        "phone": <string or null>,
        "email": <string or null>
      }},
      "propertyAddress": {{
        "street": <string or null>,
        "city": <string or null>,
        "state": <string or null>,
        "zipCode": <string or null>
      }},
      "employmentInfo": {{
        "employerName": <string or null>,
        "position": <string or null>,
        "yearsEmployed": <number or null>,
        "monthlyIncome": <number or null>
      }}
    }},
    "creditAgreement": {{
      "agreementInfo": {{
        "documentType": <string or null>,
        "agreementDate": <ISO date string or null>,
        "effectiveDate": <ISO date string or null>,
        "maturityDate": <ISO date string or null>,
        "amendmentNumber": <string or null>
      }},
      "parties": {{
        "borrower": {{
          "name": <string or null>,
          "jurisdiction": <string or null>
        }},
        "coBorrowers": [
          {{
            "name": <string or null>,
            "jurisdiction": <string or null>
          }}
        ],
        "ultimateHoldings": {{
          "name": <string or null>,
          "jurisdiction": <string or null>
        }},
        "intermediateHoldings": {{
          "name": <string or null>,
          "jurisdiction": <string or null>
        }},
        "administrativeAgent": <string or null>,
        "leadArrangers": [<string>],
        "swinglineLender": <string or null>,
        "lcIssuer": <string or null>,
        "guarantors": [<string>]
      }},
      "facilities": [
        {{
          "facilityType": <string>,
          "facilityName": <string or null>,
          "commitmentAmount": <number or null>,
          "maturityDate": <ISO date string or null>
        }}
      ],
      "facilityTerms": {{
        "aggregateMaxRevolvingCreditAmount": <number or null>,
        "aggregateElectedRevolvingCreditCommitment": <number or null>,
        "lcCommitment": <number or null>,
        "lcSublimit": <number or null>,
        "swinglineSublimit": <string or null>,
        "termLoanACommitment": <number or null>,
        "termCommitment": <number or null>
      }},
      "applicableRates": {{
        "referenceRate": <string or null>,
        "floor": <decimal or null>,
        "pricingBasis": <string or null>,
        "tiers": [
          {{
            "level": <string or null>,
            "threshold": <string>,
            "termBenchmarkRFRSpread": <decimal or null>,
            "termSOFRSpread": <decimal or null>,
            "applicableMargin": <decimal or null>,
            "abrSpread": <decimal or null>,
            "unusedCommitmentFeeRate": <decimal or null>,
            "lcFeeRate": <decimal or null>
          }}
        ]
      }},
      "fees": {{
        "commitmentFeeRate": <decimal or null>,
        "lcFeeRate": <decimal or null>,
        "frontingFeeRate": <decimal or null>,
        "agencyFee": <number or null>
      }},
      "paymentTerms": {{
        "interestPaymentDates": [<string>],
        "interestPeriodOptions": [<string>],
        "paymentDay": <string or null>
      }},
      "covenants": {{
        "fixedChargeCoverageRatio": {{
          "minimum": <decimal or null>,
          "testPeriod": <string or null>
        }},
        "otherCovenants": [<string>]
      }},
      "lenderCommitments": [
        {{
          "lenderName": <string>,
          "applicablePercentage": <decimal or null>,
          "termCommitment": <number or null>,
          "termLoanACommitment": <number or null>,
          "revolvingCreditCommitment": <number or null>,
          "electedRevolvingCreditCommitment": <number or null>,
          "maxRevolvingCreditAmount": <number or null>
        }}
      ]
    }}
  }},
  "validation": {{
    "isValid": <boolean>,
    "confidence": "high" | "medium" | "low",
    "crossReferenceChecks": [
      {{
        "field1": <string>,
        "field2": <string>,
        "match": <boolean>,
        "note": <string or null>
      }}
    ],
    "validationNotes": [<string>],
    "missingRequiredFields": [<string>]
  }},
  "audit": {{
    "extractionSources": [
      {{
        "field": <string>,
        "sourceDocument": <string>,
        "sourcePage": <number>,
        "rawValue": <string>,
        "normalizedValue": <any>
      }}
    ]
  }}
}}

IMPORTANT:
- Cross-reference interest rates and loan amounts between Promissory Note and Closing Disclosure
- Flag any discrepancies in the validation section
- Include audit trail showing original values and normalized values
- Be conservative - better to return null than incorrect data

Respond with ONLY valid JSON matching the schema above."""

    # Log prompt size for debugging
    print(f"Normalization prompt size: {len(prompt)} chars")

    # Call Bedrock with increased max_tokens for complex Credit Agreement extractions
    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 8192,  # Increased for complex Credit Agreement extractions
                'temperature': 0,  # Deterministic for consistency
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    },
                    {
                        'role': 'assistant',
                        'content': '{'
                    }
                ]
            })
        )
    except Exception as bedrock_error:
        print(f"Bedrock invoke_model failed: {str(bedrock_error)}")
        raise ValueError(f"Bedrock API call failed: {str(bedrock_error)}")

    # Parse response with error handling
    try:
        response_body_raw = response['body'].read()
        print(f"Bedrock response size: {len(response_body_raw)} bytes")

        if not response_body_raw:
            raise ValueError("Bedrock returned empty response body")

        response_body = json.loads(response_body_raw)
    except json.JSONDecodeError as e:
        print(f"Failed to parse Bedrock response body: {response_body_raw[:500] if response_body_raw else 'empty'}")
        raise ValueError(f"Failed to parse Bedrock response JSON: {str(e)}")

    # Check for Bedrock errors
    if 'error' in response_body:
        error_msg = response_body.get('error', {}).get('message', str(response_body.get('error')))
        print(f"Bedrock returned error: {error_msg}")
        raise ValueError(f"Bedrock error: {error_msg}")

    # Extract content
    if 'content' not in response_body or not response_body['content']:
        print(f"Bedrock response missing content: {json.dumps(response_body)[:500]}")
        raise ValueError("Bedrock response missing 'content' field")

    content = response_body['content'][0].get('text', '')

    # Extract token usage for cost calculation
    usage = response_body.get('usage', {})
    input_tokens = usage.get('input_tokens', 0)
    output_tokens = usage.get('output_tokens', 0)

    # Extract JSON from response
    try:
        # Prepend the '{' we used as assistant prefill
        content = '{' + content

        # Handle potential markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]

        normalized_data = json.loads(content.strip())

        # Return both normalized data and token usage
        return {
            'data': normalized_data,
            'tokenUsage': {
                'inputTokens': input_tokens,
                'outputTokens': output_tokens,
            }
        }
    except json.JSONDecodeError as e:
        print(f"Error parsing normalization response: {content}")
        raise ValueError(f"Failed to parse Bedrock response: {str(e)}")


def calculate_processing_cost(
    normalizer_tokens: Dict[str, int],
    textract_pages: int,
    router_tokens: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Calculate the total processing cost for a document.

    Pricing (per 1K tokens):
    - Claude 3 Haiku (Router): $0.00025 input, $0.00125 output
    - Claude 3.5 Haiku (Normalizer): $0.001 input, $0.005 output
    - Textract (Tables + Queries): $0.02 per page

    Args:
        normalizer_tokens: Dict with inputTokens and outputTokens from normalizer
        textract_pages: Number of pages processed by Textract
        router_tokens: Optional dict with inputTokens and outputTokens from router

    Returns:
        Dict with cost breakdown and total
    """
    # Pricing constants (per 1K tokens)
    CLAUDE_3_HAIKU_INPUT = 0.00025
    CLAUDE_3_HAIKU_OUTPUT = 0.00125
    CLAUDE_35_HAIKU_INPUT = 0.001
    CLAUDE_35_HAIKU_OUTPUT = 0.005
    TEXTRACT_PER_PAGE = 0.02  # Tables + Queries combined

    # Router cost (Claude 3 Haiku)
    router_cost = 0.0
    router_input = 0
    router_output = 0
    if router_tokens:
        router_input = router_tokens.get('inputTokens', 0)
        router_output = router_tokens.get('outputTokens', 0)
        router_cost = (
            (router_input / 1000) * CLAUDE_3_HAIKU_INPUT +
            (router_output / 1000) * CLAUDE_3_HAIKU_OUTPUT
        )
    else:
        # Estimate router cost if not provided (~20K input, 500 output typical)
        router_input = 20000
        router_output = 500
        router_cost = (
            (router_input / 1000) * CLAUDE_3_HAIKU_INPUT +
            (router_output / 1000) * CLAUDE_3_HAIKU_OUTPUT
        )

    # Normalizer cost (Claude 3.5 Haiku)
    normalizer_input = normalizer_tokens.get('inputTokens', 0)
    normalizer_output = normalizer_tokens.get('outputTokens', 0)
    normalizer_cost = (
        (normalizer_input / 1000) * CLAUDE_35_HAIKU_INPUT +
        (normalizer_output / 1000) * CLAUDE_35_HAIKU_OUTPUT
    )

    # Textract cost
    textract_cost = textract_pages * TEXTRACT_PER_PAGE

    # Total cost
    total_cost = router_cost + textract_cost + normalizer_cost

    return {
        'totalCost': round(total_cost, 4),
        'breakdown': {
            'router': {
                'model': 'claude-3-haiku',
                'inputTokens': router_input,
                'outputTokens': router_output,
                'cost': round(router_cost, 6),
            },
            'textract': {
                'pages': textract_pages,
                'costPerPage': TEXTRACT_PER_PAGE,
                'cost': round(textract_cost, 4),
            },
            'normalizer': {
                'model': 'claude-3.5-haiku',
                'inputTokens': normalizer_input,
                'outputTokens': normalizer_output,
                'cost': round(normalizer_cost, 6),
            },
        },
        'currency': 'USD',
    }


def calculate_processing_time(
    uploaded_at: Optional[str],
    textract_pages: int,
) -> Dict[str, Any]:
    """Calculate the total processing time for a document.

    Args:
        uploaded_at: ISO timestamp when document was uploaded (from trigger)
        textract_pages: Number of pages processed by Textract

    Returns:
        Dict with processing time breakdown
    """
    completed_at = datetime.utcnow()

    # Calculate total duration
    total_seconds = 0.0
    started_at_str = None

    if uploaded_at:
        try:
            # Parse ISO timestamp (handles 'Z' suffix)
            if uploaded_at.endswith('Z'):
                uploaded_at = uploaded_at[:-1] + '+00:00'
            started_at = datetime.fromisoformat(uploaded_at.replace('+00:00', ''))
            total_seconds = (completed_at - started_at).total_seconds()
            started_at_str = uploaded_at
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not parse uploadedAt timestamp: {uploaded_at} - {e}")

    # Estimate phase breakdown (approximate based on typical processing patterns)
    # Router: ~10% of time, Textract: ~60% of time, Normalizer: ~30% of time
    router_seconds = total_seconds * 0.10
    textract_seconds = total_seconds * 0.60
    normalizer_seconds = total_seconds * 0.30

    return {
        'totalSeconds': round(total_seconds, 2),
        'startedAt': started_at_str,
        'completedAt': completed_at.isoformat() + 'Z',
        'breakdown': {
            'router': {
                'estimatedSeconds': round(router_seconds, 2),
                'description': 'Document classification with Claude Haiku',
            },
            'textract': {
                'estimatedSeconds': round(textract_seconds, 2),
                'pages': textract_pages,
                'description': 'Parallel page extraction with Textract',
            },
            'normalizer': {
                'estimatedSeconds': round(normalizer_seconds, 2),
                'description': 'Data normalization with Claude 3.5 Haiku',
            },
        },
    }


def store_to_dynamodb(
    document_id: str,
    normalized_data: Dict[str, Any],
    content_hash: Optional[str] = None,
    original_key: Optional[str] = None,
    file_size: Optional[int] = None,
    document_type: str = 'LOAN_PACKAGE',
    processing_cost: Optional[Dict[str, Any]] = None,
    processing_time: Optional[Dict[str, Any]] = None,
) -> None:
    """Store normalized data to DynamoDB with review status, processing cost, and time.

    Args:
        document_id: Unique document identifier
        normalized_data: Normalized loan data
        content_hash: SHA-256 hash for deduplication lookup
        original_key: Original S3 key of the document
        file_size: File size in bytes
        document_type: Type of document (LOAN_PACKAGE, CREDIT_AGREEMENT)
        processing_cost: Cost breakdown for processing this document
        processing_time: Time breakdown for processing this document
    """
    table = dynamodb.Table(TABLE_NAME)

    timestamp = datetime.utcnow().isoformat() + "Z"

    # First, check for and delete any existing PROCESSING record
    # (This handles the transition from PENDING/CLASSIFIED -> PROCESSED)
    try:
        from boto3.dynamodb.conditions import Key as DynamoKey
        query_result = table.query(
            KeyConditionExpression=DynamoKey("documentId").eq(document_id),
            Limit=1,
        )

        if query_result.get("Items"):
            existing_record = query_result["Items"][0]
            existing_doc_type = existing_record.get("documentType")

            # Delete the old record if it has a different documentType (e.g., PROCESSING)
            if existing_doc_type and existing_doc_type != document_type:
                table.delete_item(
                    Key={"documentId": document_id, "documentType": existing_doc_type}
                )
                print(f"Deleted old {existing_doc_type} record for document: {document_id}")
    except Exception as cleanup_err:
        print(f"Warning: Error cleaning up old record: {str(cleanup_err)}")
        # Continue anyway - the put_item will create the new record

    # Store main loan data record
    item = {
        'documentId': document_id,
        'documentType': document_type,
        'extractedData': convert_floats_to_decimal(normalized_data.get('loanData', {})),
        'validation': convert_floats_to_decimal(normalized_data.get('validation', {})),
        'audit': convert_floats_to_decimal(normalized_data.get('audit', {})),
        'status': 'PROCESSED',
        'reviewStatus': 'PENDING_REVIEW',  # Initial review status for approval workflow
        'reviewedBy': None,
        'reviewedAt': None,
        'reviewNotes': None,
        'corrections': None,
        'version': 1,  # For optimistic locking
        'createdAt': timestamp,
        'updatedAt': timestamp,
        'ttl': int(datetime.utcnow().timestamp()) + (365 * 24 * 60 * 60)  # 1 year TTL
    }

    # Add content hash for deduplication (enables ContentHashIndex GSI lookup)
    if content_hash:
        item['contentHash'] = content_hash

    # Add file metadata
    if original_key:
        item['originalS3Key'] = original_key
    if file_size:
        item['fileSize'] = file_size

    # Add processing cost
    if processing_cost:
        item['processingCost'] = convert_floats_to_decimal(processing_cost)

    # Add processing time
    if processing_time:
        item['processingTime'] = convert_floats_to_decimal(processing_time)

    table.put_item(Item=item)
    print(f"Stored normalized data to DynamoDB: {document_id} (hash: {content_hash[:16] if content_hash else 'N/A'}...)")
    print(f"Review status: PENDING_REVIEW")
    if processing_cost:
        print(f"Processing cost: ${processing_cost.get('totalCost', 0):.4f}")
    if processing_time:
        print(f"Processing time: {processing_time.get('totalSeconds', 0):.1f}s")


def store_audit_to_s3(bucket: str, document_id: str, raw_extractions: List[Dict], normalized_data: Dict) -> str:
    """Store complete audit trail to S3.
    
    Args:
        bucket: S3 bucket name
        document_id: Unique document identifier
        raw_extractions: Original extraction results
        normalized_data: Normalized data
        
    Returns:
        S3 key of the audit file
    """
    timestamp = datetime.utcnow().isoformat()
    
    audit_record = {
        'documentId': document_id,
        'processedAt': timestamp,
        'rawExtractions': raw_extractions,
        'normalizedData': normalized_data,
        'processingMetadata': {
            'normalizerModel': BEDROCK_MODEL_ID,
            'version': '1.0.0'
        }
    }
    
    key = f"audit/{document_id}/{timestamp.replace(':', '-')}.json"
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(audit_record, indent=2, cls=DecimalEncoder),
        ContentType='application/json'
    )
    
    print(f"Stored audit trail to s3://{bucket}/{key}")
    return key


def lambda_handler(event, context):
    """Main Lambda handler for data normalization and storage.

    Args:
        event: Input event containing documentId, contentHash, and extraction results
        context: Lambda context

    Returns:
        Dict with processing results and storage locations
    """
    print(f"Normalizer Lambda received event: {json.dumps(event, cls=DecimalEncoder)}")

    # Extract document metadata from the event
    # Fields are passed through from trigger -> router -> parallel -> normalizer
    document_id = None
    content_hash = None
    original_key = None
    file_size = None
    uploaded_at = None
    bucket = BUCKET_NAME

    # Handle different event structures
    if 'documentId' in event:
        document_id = event['documentId']
        content_hash = event.get('contentHash')
        original_key = event.get('key')
        file_size = event.get('size')
        uploaded_at = event.get('uploadedAt')
    elif isinstance(event, list) and len(event) > 0:
        # Coming from parallel state - extractions are in array
        for item in event:
            if isinstance(item, dict) and 'documentId' in item:
                document_id = item['documentId']
                content_hash = item.get('contentHash')
                original_key = item.get('key')
                file_size = item.get('size')
                uploaded_at = item.get('uploadedAt')
                break

    # Also check extractions array for metadata (passed through parallel state)
    extractions = event.get('extractions', event if isinstance(event, list) else [event])
    if isinstance(extractions, list):
        for ext in extractions:
            if isinstance(ext, dict):
                if not document_id and 'documentId' in ext:
                    document_id = ext['documentId']
                if not content_hash and 'contentHash' in ext:
                    content_hash = ext['contentHash']
                if not original_key and 'key' in ext:
                    original_key = ext['key']
                if not file_size and 'size' in ext:
                    file_size = ext['size']
                if not uploaded_at and 'uploadedAt' in ext:
                    uploaded_at = ext['uploadedAt']

    if not document_id:
        raise ValueError("Could not find documentId in event")

    print(f"Processing {len(extractions)} extractions for document: {document_id}")
    print(f"Content hash: {content_hash[:16] if content_hash else 'N/A'}...")

    # Detect document type from extractions
    # Credit Agreement extractions have 'creditAgreementSection' field
    is_credit_agreement = any(
        isinstance(ext, dict) and ext.get('creditAgreementSection')
        for ext in extractions
    )
    document_type = 'CREDIT_AGREEMENT' if is_credit_agreement else 'LOAN_PACKAGE'
    print(f"Detected document type: {document_type}")

    try:
        # 1. Normalize data with Bedrock (Claude 3.5 Haiku for cost optimization)
        print(f"Normalizing data with {BEDROCK_MODEL_ID}...")
        normalization_result = normalize_with_bedrock(extractions, document_id)
        normalized_data = normalization_result['data']
        normalizer_tokens = normalization_result['tokenUsage']
        print(f"Normalization complete. Validation: {normalized_data.get('validation', {})}")
        print(f"Normalizer tokens - Input: {normalizer_tokens['inputTokens']}, Output: {normalizer_tokens['outputTokens']}")

        # 2. Calculate Textract pages from extractions
        textract_pages = 0
        for ext in extractions:
            if isinstance(ext, dict):
                # Credit Agreement sections have pageCount
                if ext.get('pageCount'):
                    textract_pages += ext['pageCount']
                # Mortgage docs have single pageNumber
                elif ext.get('pageNumber') and ext.get('status') == 'EXTRACTED':
                    textract_pages += 1

        print(f"Textract pages processed: {textract_pages}")

        # 3. Calculate processing cost
        processing_cost = calculate_processing_cost(
            normalizer_tokens=normalizer_tokens,
            textract_pages=textract_pages,
            router_tokens=None,  # Router tokens not passed through, using estimate
        )
        print(f"Processing cost: ${processing_cost['totalCost']:.4f}")

        # 4. Calculate processing time
        processing_time = calculate_processing_time(
            uploaded_at=uploaded_at,
            textract_pages=textract_pages,
        )
        print(f"Processing time: {processing_time['totalSeconds']:.1f}s")

        # 5. Store to DynamoDB (with contentHash, reviewStatus, cost, and time)
        print("Storing to DynamoDB...")
        store_to_dynamodb(
            document_id=document_id,
            normalized_data=normalized_data,
            content_hash=content_hash,
            original_key=original_key,
            file_size=file_size,
            document_type=document_type,
            processing_cost=processing_cost,
            processing_time=processing_time,
        )

        # 6. Store audit trail to S3
        print("Storing audit trail to S3...")
        audit_key = store_audit_to_s3(bucket, document_id, extractions, normalized_data)

        # 7. Build summary based on document type
        summary = {}
        loan_data = normalized_data.get('loanData', {})

        if is_credit_agreement:
            # Credit Agreement summary - handle null/empty data gracefully
            credit_agreement = loan_data.get('creditAgreement') or {}
            parties = credit_agreement.get('parties') or {}
            borrower = parties.get('borrower') or {}
            facility_terms = credit_agreement.get('facilityTerms') or {}
            agreement_info = credit_agreement.get('agreementInfo') or {}
            validation = normalized_data.get('validation') or {}

            summary = {
                'documentType': 'CREDIT_AGREEMENT',
                'borrowerName': borrower.get('name'),
                'aggregateRevolvingCredit': facility_terms.get('aggregateMaxRevolvingCreditAmount'),
                'maturityDate': agreement_info.get('maturityDate'),
                'administrativeAgent': parties.get('administrativeAgent'),
                'isValid': validation.get('isValid', False),
                'confidence': validation.get('confidence', 'low'),
            }
        else:
            # Mortgage/Loan Package summary - handle null/empty data gracefully
            promissory_note = loan_data.get('promissoryNote') or {}
            validation = normalized_data.get('validation') or {}

            summary = {
                'documentType': 'LOAN_PACKAGE',
                'loanAmount': promissory_note.get('principalAmount'),
                'interestRate': promissory_note.get('interestRate'),
                'borrowerName': promissory_note.get('borrowerName'),
                'isValid': validation.get('isValid', False),
                'confidence': validation.get('confidence', 'low'),
            }

        # 8. Return results with processing cost and time
        return {
            'documentId': document_id,
            'contentHash': content_hash,
            'documentType': document_type,
            'status': 'COMPLETED',
            'reviewStatus': 'PENDING_REVIEW',
            'validation': normalized_data.get('validation', {}),
            'processingCost': processing_cost,
            'processingTime': processing_time,
            'storage': {
                'dynamodbTable': TABLE_NAME,
                'auditS3Key': audit_key
            },
            'summary': summary
        }

    except Exception as e:
        print(f"Error in Normalizer Lambda: {str(e)}")
        raise
