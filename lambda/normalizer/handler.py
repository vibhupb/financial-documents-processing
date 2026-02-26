"""Normalizer Lambda - Data Refinement and Storage

This Lambda function implements the "Closer" pattern:
1. Receives raw Textract output from parallel extractions
2. Uses Claude Haiku 4.5 to normalize and validate the data
3. Stores clean JSON to DynamoDB (for app) and S3 (for audit)
4. Ensures data conforms to expected schema

Cost: Claude Haiku 4.5 — $1.00/MTok input, $5.00/MTok output (~$0.013/doc).
"""

import datetime
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
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-haiku-4-5-20251001-v1:0')


def append_processing_event(document_id: str, document_type: str, stage: str, message: str):
    """Append a timestamped event to the document's processingEvents list."""
    try:
        table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "financial-documents"))
        table.update_item(
            Key={"documentId": document_id, "documentType": document_type},
            UpdateExpression="SET processingEvents = list_append(if_not_exists(processingEvents, :empty), :event)",
            ExpressionAttributeValues={
                ":event": [{
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "stage": stage,
                    "message": message,
                }],
                ":empty": [],
            },
        )
    except Exception:
        pass  # Non-critical — don't fail processing if event logging fails


# ==========================================
# Plugin-Driven Normalization Functions
# ==========================================


def build_normalization_prompt(
    plugin: Dict[str, Any],
    raw_extraction_data: Dict[str, Any],
) -> str:
    """Assemble normalization prompt from plugin config and template files.

    4-layer architecture: preamble -> schema fields -> plugin template -> footer
    """
    from pathlib import Path

    normalization_config = plugin.get("normalization", {})
    template_name = normalization_config.get("prompt_template", plugin["plugin_id"])

    prompts_dir = Path("/opt/python/document_plugins/prompts")
    if not prompts_dir.exists():
        # Local development fallback
        prompts_dir = Path(__file__).resolve().parent.parent / "layers" / "plugins" / "python" / "document_plugins" / "prompts"

    preamble = (prompts_dir / "common_preamble.txt").read_text()
    footer = (prompts_dir / "common_footer.txt").read_text()

    plugin_template = ""
    template_path = prompts_dir / f"{template_name}.txt"
    if template_path.exists():
        plugin_template = template_path.read_text()

    # Inject extraction data into preamble placeholder
    extraction_json = json.dumps(raw_extraction_data, indent=2, cls=DecimalEncoder)
    MAX_EXTRACTION_CHARS = 200000
    if len(extraction_json) > MAX_EXTRACTION_CHARS:
        extraction_json = extraction_json[:MAX_EXTRACTION_CHARS] + "\n... [TRUNCATED]"

    prompt = preamble.replace("{extraction_data}", extraction_json)
    if plugin_template:
        prompt += "\n\n" + plugin_template
    prompt += "\n\n" + footer

    print(f"Built normalization prompt: {len(prompt)} chars")
    return prompt


def invoke_bedrock_normalize(
    prompt: str,
    plugin: Dict[str, Any],
) -> tuple:
    """Invoke Bedrock and return (parsed_data, token_usage)."""
    normalization_config = plugin.get("normalization", {})
    model_id = normalization_config.get("llm_model", BEDROCK_MODEL_ID)
    max_tokens = normalization_config.get("max_tokens", 8192)
    temperature = normalization_config.get("temperature", 0.0)

    response = bedrock_client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "{"},
            ],
        }),
    )

    response_body = json.loads(response["body"].read())
    content = response_body["content"][0].get("text", "")
    usage = response_body.get("usage", {})
    token_usage = {
        "inputTokens": usage.get("input_tokens", 0),
        "outputTokens": usage.get("output_tokens", 0),
    }

    content = "{" + content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    try:
        normalized_data = json.loads(content.strip())
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}, raw={content[:500]}")
        normalized_data = {
            "loanData": {},
            "validation": {
                "isValid": False, "confidence": "low",
                "validationNotes": [f"LLM response parse failure: {e}"],
                "missingRequiredFields": ["all"],
            },
            "audit": {"extractionSources": []},
        }

    return normalized_data, token_usage


def apply_field_overrides(result: Dict[str, Any], plugin: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default values for null coded fields from plugin config."""
    overrides = plugin.get("normalization", {}).get("field_overrides", {})
    if not overrides:
        return result

    changes = []
    for dot_path, default_value in overrides.items():
        parts = dot_path.split(".")
        parent = result
        for part in parts[:-1]:
            if not isinstance(parent, dict):
                break
            if part not in parent:
                parent[part] = {}
            parent = parent[part]
        else:
            leaf = parts[-1]
            if isinstance(parent, dict):
                current = parent.get(leaf)
                if current is None or current == "":
                    parent[leaf] = default_value
                    changes.append(f"{dot_path} -> {default_value}")

    if changes:
        validation = result.setdefault("validation", {"isValid": True, "confidence": "medium", "validationNotes": []})
        validation.setdefault("validationNotes", []).append(
            f"Applied {len(changes)} field override(s): {', '.join(changes)}"
        )
    return result


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
   - Keywords: "Amendment No.", "First Amendment", "Second Amendment", "Third Amendment"
   - Format: String or null
   - CRITICAL: If documentType is "Amended and Restated Credit Agreement", the amendmentNumber should be null
     unless explicitly titled as "Amendment No. X to Amended and Restated Credit Agreement"
   - Do NOT use random document reference numbers (like "112" from footer/header) as amendment numbers
   - Only use amendment numbers if clearly stated in the document TITLE

=== PARTIES ===

5. **Borrower(s)** - IMPORTANT: Many agreements have JOINT BORROWERS
   - Keywords: "Borrower", "the Company", "as borrower", "together with", "individually and collectively"
   - CRITICAL: If multiple companies are listed as "Borrower" (e.g., "Company A and Company B, as Borrower"),
     extract ALL of them. Put the first company in "borrower" field, and additional companies in "coBorrowers" array.
   - Example: "AVIVA METALS, INC. and W.P. PROPERTY, INC., as Borrower" means BOTH are borrowers
   - Format for borrower: {{"name": string, "jurisdiction": string}}
   - Format for coBorrowers: [{{"name": string, "jurisdiction": string}}]

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
    - Keywords: "Term Loan A Commitment", "Term Loan B", "Term Commitment", "Term Loan Bond Redemption"
    - Format: Number for each term loan type
    - Note: Some agreements have Term Loan Bond Redemption facilities with different maturity dates

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
    - IMPORTANT: Extract ALL rows from the pricing table - do NOT summarize or truncate!
    - Typical tables have 5 tiers (e.g., ≥90%, <90%, ≤75%, ≤50%, ≤25%) - extract EVERY one
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
        "termLoanBCommitment": <number or null>,
        "termLoanBondRedemption": <number or null>,
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
- CRITICAL: For pricing tiers/arrays, include EVERY row from the source table - do NOT truncate, summarize, or limit to 3 items!
- If a table has 5 rows of pricing tiers, output all 5 tiers in the JSON array

Output the JSON now:"""


def build_loan_agreement_prompt(raw_text: str, textract_query_results: Optional[Dict[str, Any]] = None) -> str:
    """Build a specialized prompt for Loan Agreement raw text extraction.

    Uses detailed field definitions with extraction logic, formats, and valid values
    based on loan_prompts_map specifications. This is the HYBRID approach:
    - Textract OCR handles visual text extraction from scanned documents
    - Textract Queries provide high-confidence targeted extractions for key fields
    - Claude LLM handles intelligent data extraction with domain knowledge

    Args:
        raw_text: Raw OCR text from Textract DetectDocumentText or PyPDF extraction
        textract_query_results: Optional dict of Textract query results with pre-extracted values

    Returns:
        Specialized extraction prompt for Loan Agreements
    """
    # Build Textract query results section if available
    textract_section = ""
    if textract_query_results:
        textract_section = """
=== PRE-EXTRACTED VALUES FROM TEXTRACT (HIGH CONFIDENCE) ===
The following values were extracted by Amazon Textract with high confidence.
USE THESE VALUES when they have confidence >= 70%. These should take precedence over raw text parsing.

"""
        for query, result in textract_query_results.items():
            if isinstance(result, dict):
                answer = result.get('answer', 'N/A')
                confidence = result.get('confidence', 0)
                # Only include high-confidence results
                if confidence >= 50:  # Lower threshold to capture more useful data
                    textract_section += f"- {query}: {answer} (confidence: {confidence}%)\n"

        textract_section += """
IMPORTANT: If Textract extracted a value above (like Maturity Date, Interest Rate, etc.),
USE THAT VALUE in your output rather than trying to re-extract from raw text.

"""

    return f"""Extract financial data from the Loan Agreement text below and return ONLY a JSON object (no other text).
{textract_section}

RAW TEXT FROM DOCUMENT:
{raw_text}

EXTRACTION INSTRUCTIONS:

You are extracting data from a business/commercial Loan Agreement. For each field below,
search for the specified keywords, apply the extraction logic, and validate against allowed values.

=== LOAN MASTER FIELDS ===

1. **Instrument Type** (instrument_type)
   - Definition: The classification of the loan product (e.g., TERM LOAN, LINE OF CREDIT)
   - Keywords: "Loan Type", "Credit Type", "Facility Type", "Term Loan", "Line of Credit", "Revolving"
   - Extraction Logic: Look for loan classification in the document header or definitions
   - Valid Values:
     * "TERM:TERM LOAN" - if "term loan" found
     * "LINE:LINE OF CREDIT" - if "line of credit" or "revolving" found
     * "ABL:ASSET BASED LENDING" - if "asset based" found
     * "RLOC:REVOLVING LINE OF CREDIT" - if "revolving line" found
   - Default: "TERM:TERM LOAN" if not specified

2. **Loan Effective Date** (loan_effective_date)
   - Definition: The date on which the loan terms become effective
   - Keywords: "Effective Date", "Dated as of", "Agreement Date", "Closing Date"
   - Format: YYYY-MM-DD
   - Extraction Logic: Look for dates near "dated as of" or "effective" in first few paragraphs

3. **Maturity Date** (maturity_date)
   - Definition: The date when the loan becomes due and payable in full
   - Keywords: "Maturity Date", "Due Date", "Termination Date", "Final Payment"
   - Format: YYYY-MM-DD
   - Extraction Logic: Often stated as "Maturity Date means [date]" or in loan terms section

4. **Currency** (currency)
   - Definition: The currency denomination of the loan
   - Keywords: "USD", "Dollars", "$", "United States Dollars"
   - Valid Values: "USD:US DOLLAR" (default), "CAD:CANADIAN DOLLAR", "GBP:BRITISH POUND"
   - Default: "USD:US DOLLAR"

5. **Pricing Option** (pricing_option)
   - Definition: The interest rate structure selected for the loan
   - Keywords: "Pricing Option", "Rate Option", "Interest Option", "Prime", "SOFR", "Fixed"
   - Valid Values:
     * "FIXED:FIXED RATE" - for fixed rate loans
     * "FLOATING:FLOATING RATE" - for variable/floating rate
     * "LIBOR:LIBOR RATE" - if LIBOR referenced
     * "SOFR:SOFR RATE" - if SOFR referenced
     * "PRIME:PRIME RATE" - if Prime Rate referenced

=== INTEREST RATE FIELDS ===

6. **Interest Rate Type** (interest_rate_type)
   - Definition: Classification of how interest is calculated
   - Keywords: "Fixed Rate", "Variable Rate", "Floating Rate", "Prime", "SOFR", "Index"
   - Valid Values:
     * "FIX:FIXED RATE LOAN" - interest rate does not change
     * "PRM:PRIME RATE LOAN" - based on Prime Rate
     * "SOF:SOFR" - based on SOFR
     * "LIB:LIBOR RATE LOAN" - based on LIBOR (legacy)
     * "INT:INDEXED LOAN" - based on an index
   - Extraction Logic: Look for "fixed", "variable", "floating", or index references
   - IMPORTANT: If "Prime Rate" or "Prime" is mentioned, this is PRM:PRIME RATE LOAN

7. **Rate Setting** (rate_setting)
   - Definition: How and when interest rate changes are applied
   - Keywords: "Rate Setting", "Rate Adjustment", "Rate Reset", "Pricing Date"
   - Valid Values:
     * "INITIAL:INITIAL" - rate set once at origination
     * "DAILY:DAILY" - rate adjusts daily
     * "MONTHLY:MONTHLY" - rate adjusts monthly
     * "QUARTERLY:QUARTERLY" - rate adjusts quarterly
   - Default: "INITIAL:INITIAL" for fixed rates

8. **Base Rate / Interest Rate** (base_rate / interestRate)
   - Definition: The starting interest rate or the TOTAL interest rate for the loan
   - Keywords: "Base Rate", "Index Rate", "Prime Rate", "Reference Rate", "Interest Rate", "Rate", "per annum", "annual rate"
   - Format: Decimal (e.g., 0.085 for 8.5%)
   - Extraction Logic:
     * For FIXED loans: Look for "X% per annum" or "X% annually" or "interest rate of X%"
     * For VARIABLE loans: Calculate total rate = Index + Margin (e.g., "Prime + 2.0%" = current Prime + 0.02)
   - CRITICAL: If you find "Prime Rate plus X%" or "SOFR plus X bps", the interestRate should include the margin
   - For Prime-based: If Prime = 8.5% and margin = 0.5%, interestRate = 0.09 (9.0%)
   - If only margin is given without base rate, just record the margin in interestDetails.margin

9. **Spread Rate / Margin** (spread_rate)
   - Definition: The additional percentage added to the index rate
   - Keywords: "Spread", "Margin", "Plus", "+", "above Prime", "above SOFR", "floor", "minimum rate"
   - Format: Decimal (e.g., 0.02 for 2.0%, or 0.005 for 50 basis points)
   - Extraction Logic: Look for "Prime + X%" or "SOFR plus X%" or "X basis points above"
   - Note: If interest is "Prime + 2.0%", margin = 0.02
   - Common patterns: "Prime Rate plus one-half of one percent" = 0.005, "Prime + 50 bps" = 0.005

10. **Rate Index** (rate_index)
    - Definition: The reference rate used for variable rate loans
    - Keywords: "Prime Rate", "SOFR", "Wall Street Journal Prime", "Federal Funds"
    - Valid Values:
      * "WALLST:WALL STREET JOURNAL PRIME" - WSJ Prime Rate
      * "SOFR:SOFR RATE" - Secured Overnight Financing Rate
      * "WFPRIM:WELLS FARGO BANK PRIME" - Wells Fargo Prime
      * "FHLB:FHLB RATE" - Federal Home Loan Bank Rate
      * "FED:FEDERAL FUNDS RATE" - Fed Funds Rate
    - Extraction Logic: Look for "Prime Rate means" or "as published in" clauses

11. **Rate Calculation Method** (rate_calculation_method)
    - Definition: The year basis used for interest calculation
    - Keywords: "360-day", "365-day", "actual/360", "actual/365", "year basis"
    - Valid Values:
      * "360ACTUAL:ACTUAL DAYS / 360 DAY YEAR"
      * "365ACTUAL:ACTUAL DAYS / 365 DAY YEAR"
      * "360360:360 DAYS / 360 DAY YEAR"
    - Default: "360ACTUAL:ACTUAL DAYS / 360 DAY YEAR"

=== PAYMENT & REPAYMENT FIELDS ===

12. **Billing Type** (billing_type)
    - Definition: How payments are structured
    - Keywords: "Payment Type", "Interest Only", "Principal and Interest", "Payment Amount", "P&I", "Amortizing"
    - Valid Values:
      * "A:INTEREST ONLY" - payments cover only interest, principal due at maturity
      * "D:PRINCIPAL AMOUNT PLUS INTEREST" - specified principal + accrued interest each period
      * "F:PAYMENT AMOUNT INCLUDING INTEREST" - fixed total payment (amortizing loan)
      * "G:PRINCIPAL PLUS INTEREST REMAINDER" - principal payments + remaining interest
    - Extraction Logic:
      * Look for "interest only" or "interest-only" → "A:INTEREST ONLY"
      * Look for "principal and interest" or "P&I" or "amortizing" → "F:PAYMENT AMOUNT INCLUDING INTEREST"
      * Look for "principal payments" with "accrued interest" → "D:PRINCIPAL AMOUNT PLUS INTEREST"
      * For Lines of Credit with "interest due" on outstanding balance → "A:INTEREST ONLY"
      * Default for revolving credit/LOC: "A:INTEREST ONLY"
      * Default for term loans with fixed payments: "F:PAYMENT AMOUNT INCLUDING INTEREST"
    - IMPORTANT: Must provide a value - use context to determine the billing type

13. **Billing Frequency / Payment Frequency** (billing_frequency / paymentFrequency)
    - Definition: How often payments are due
    - Keywords: "Monthly", "Quarterly", "Semi-Annual", "Annual", "Payment Frequency", "Payable", "Due", "Each month", "Per month"
    - Valid Values:
      * "A:WEEKLY" - weekly payments
      * "C:MONTHLY" - monthly payments (most common)
      * "E:QUARTERLY" - quarterly payments
      * "G:SEMI-ANNUAL" - semi-annual payments
      * "I:ANNUAL" - annual payments
      * "X:ON DEMAND" - on demand (for demand notes)
    - Extraction Logic:
      * Look for "monthly" or "each month" or "per month" → "C:MONTHLY"
      * Look for "quarterly" or "each quarter" → "E:QUARTERLY"
      * Look for "annually" or "yearly" or "each year" → "I:ANNUAL"
      * Look for "on demand" or "upon demand" → "X:ON DEMAND"
      * If payment schedule mentions specific months (March, June, Sept, Dec) → "E:QUARTERLY"
      * Default: "C:MONTHLY" (most loans are monthly)
    - IMPORTANT: Must provide a value - default to "C:MONTHLY" if not explicitly stated

14. **Payment Amount** (payment_amount)
    - Definition: The dollar amount of each scheduled payment
    - Keywords: "Payment Amount", "Monthly Payment", "Installment", "Minimum Payment"
    - Format: Number without currency symbols (e.g., 5000.00)
    - Extraction Logic: Look for payment amount near "monthly payment" or "installment"
    - Note: For interest-only loans, this may be calculated from principal × rate / 12

15. **Next Due Date / First Payment Date** (next_due_date)
    - Definition: The date of the first or next scheduled payment
    - Keywords: "First Payment", "Next Payment", "Payment Due", "Beginning", "Commencing"
    - Format: YYYY-MM-DD

=== PREPAYMENT & FEES ===

16. **Prepayment Indicator** (prepayment_indicator)
    - Definition: Whether early repayment is allowed and under what conditions
    - Keywords: "Prepayment", "Early Payment", "Prepay", "Penalty"
    - Valid Values:
      * "Y:YES" - prepayment allowed with no penalty
      * "N:NO" - prepayment not allowed
      * "P:PENALTY" - prepayment allowed with penalty
    - Extraction Logic: Look for prepayment terms section

17. **Origination Fee** (origination_fee)
    - Keywords: "Origination Fee", "Loan Fee", "Commitment Fee"
    - Format: Number (dollar amount)

18. **Late Payment Fee** (late_payment_fee)
    - Keywords: "Late Fee", "Late Charge", "Late Payment"
    - Format: Number or percentage description

19. **Grace Period** (grace_period_days)
    - Keywords: "Grace Period", "Late after", "days after due"
    - Format: Number of days

=== PARTIES ===

20. **Borrower Name** (borrower_name)
    - Keywords: "Borrower", "Company", "the undersigned"
    - Extraction Logic: Look for party named as "Borrower" in first paragraphs
    - Extract full legal name including entity type (LLC, Inc., Corp.)

21. **Borrower Address** (borrower_address)
    - Keywords: "Address", "Principal Place of Business", "located at"
    - Extract full address if available

22. **Lender Name** (lender_name)
    - Keywords: "Lender", "Bank", "Financial Institution"
    - Extraction Logic: Look for party named as "Lender"

23. **Guarantor Name** (guarantor_name)
    - Keywords: "Guarantor", "Personal Guarantee", "jointly and severally"
    - Extraction Logic: Look for guarantor section

=== LOAN AMOUNTS ===

24. **Loan Amount / Principal** (loan_amount)
    - Keywords: "Principal Amount", "Loan Amount", "Credit Limit", "Commitment"
    - Format: Number without currency symbols
    - Extraction Logic: Look for dollar amount near "principal" or "loan amount"

25. **Credit Limit** (credit_limit)
    - Keywords: "Credit Limit", "Maximum Amount", "Commitment Amount"
    - Format: Number without currency symbols
    - Note: For lines of credit, this is the maximum available

=== COLLATERAL ===

26. **Is Secured** (is_secured)
    - Keywords: "Secured", "Collateral", "Security Interest", "UCC"
    - Format: Boolean (true/false)
    - Extraction Logic: If collateral or security interest mentioned, set true

27. **Collateral Description** (collateral_description)
    - Keywords: "Collateral", "Security", "Pledge", "Assets"
    - Extraction Logic: Describe the collateral pledged

=== OUTPUT FORMAT ===

Return ONLY valid JSON matching this structure:
{{
  "loanData": {{
    "loanAgreement": {{
      "documentInfo": {{
        "documentType": <string - use instrument_type extracted>,
        "loanNumber": <string or null>,
        "agreementDate": <YYYY-MM-DD or null>,
        "effectiveDate": <YYYY-MM-DD or null>,
        "closingDate": <YYYY-MM-DD or null>
      }},
      "loanTerms": {{
        "loanAmount": <number or null>,
        "creditLimit": <number or null>,
        "interestRate": <decimal or null - total rate including spread>,
        "annualPercentageRate": <decimal or null>,
        "isFixedRate": <boolean or null>,
        "maturityDate": <YYYY-MM-DD or null>,
        "loanTermMonths": <number or null>
      }},
      "interestDetails": {{
        "rateType": <string - use interest_rate_type code>,
        "indexRate": <string - use rate_index code>,
        "margin": <decimal - the spread_rate>,
        "floor": <decimal or null>,
        "ceiling": <decimal or null>,
        "defaultRate": <decimal or null>,
        "dayCountBasis": <string - use rate_calculation_method>
      }},
      "paymentInfo": {{
        "monthlyPayment": <number or null>,
        "firstPaymentDate": <YYYY-MM-DD or null>,
        "paymentDueDay": <number or null - day of month>,
        "paymentFrequency": <string - use billing_frequency code>,
        "numberOfPayments": <number or null>,
        "balloonPayment": <number or null>
      }},
      "parties": {{
        "borrower": {{
          "name": <string or null>,
          "address": <string or null>
        }},
        "guarantor": {{
          "name": <string or null>,
          "address": <string or null>
        }},
        "lender": {{
          "name": <string or null>,
          "address": <string or null>
        }}
      }},
      "security": {{
        "isSecured": <boolean or null>,
        "collateralDescription": <string or null>,
        "propertyAddress": <string or null>
      }},
      "fees": {{
        "originationFee": <number or null>,
        "latePaymentFee": <number or null>,
        "gracePeriodDays": <number or null>,
        "closingCosts": <number or null>,
        "annualFee": <number or null>
      }},
      "prepayment": {{
        "hasPenalty": <boolean or null>,
        "penaltyTerms": <string or null>
      }},
      "covenants": {{
        "financialCovenants": [<string>],
        "debtServiceCoverageRatio": <decimal or null>,
        "currentRatio": <decimal or null>
      }},
      "repayment": {{
        "schedule": <string or null>,
        "principalReductions": <string or null>,
        "interestOnlyPeriod": <string or null>
      }},
      "default": {{
        "eventsOfDefault": [<string>],
        "remedies": [<string>]
      }},
      "_extractedCodes": {{
        "instrumentType": <string - raw code like "TERM:TERM LOAN">,
        "interestRateType": <string - raw code like "PRM:PRIME RATE LOAN">,
        "rateIndex": <string - raw code like "WALLST:WALL STREET JOURNAL PRIME">,
        "rateCalculationMethod": <string - raw code like "360ACTUAL:ACTUAL DAYS / 360 DAY YEAR">,
        "billingType": <string - raw code like "F:PAYMENT AMOUNT INCLUDING INTEREST">,
        "billingFrequency": <string - raw code like "C:MONTHLY">,
        "prepaymentIndicator": <string - raw code like "Y:YES">
      }}
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
        "rawValue": <string>,
        "normalizedValue": <any>
      }}
    ]
  }}
}}

CRITICAL INSTRUCTIONS:
- Your response must be ONLY the JSON object - no explanations, no preamble, no markdown code blocks
- Start your response with {{ and end with }}
- Convert ALL percentages to decimals (e.g., "8.5%" → 0.085, "Prime + 2.0%" → spread of 0.02)
- Convert ALL currency amounts to numbers without symbols (e.g., "$500,000.00" → 500000.00)
- Dates must be in YYYY-MM-DD format
- Include the "_extractedCodes" section with the raw code values for system compatibility
- Track extraction sources in the audit trail

DEFAULT VALUE RULES (IMPORTANT - must apply these):
- For fields marked with "Default:" above, you MUST use the default if no explicit value is found
- billingFrequency/paymentFrequency: ALWAYS provide a value. Use "C:MONTHLY" if not stated.
- billingType: ALWAYS provide a value based on loan type:
  * For LINE OF CREDIT or REVOLVING: Use "A:INTEREST ONLY"
  * For TERM LOAN with payments: Use "F:PAYMENT AMOUNT INCLUDING INTEREST"
- currency: Default to "USD:US DOLLAR"
- rateCalculationMethod/dayCountBasis: Default to "360ACTUAL:ACTUAL DAYS / 360 DAY YEAR"
- interestRateType: If "Prime" is mentioned, use "PRM:PRIME RATE LOAN"
- rateIndex: If Prime Rate is mentioned, use "WALLST:WALL STREET JOURNAL PRIME"

WHEN TO USE NULL:
- For specific values like interestRate (number), maturityDate (date) where no data exists
- For party names/addresses when not specified
- For amounts when not explicitly stated
- NEVER use null for coded fields (billingType, billingFrequency) - use defaults instead

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
            queries_data = results['queries']
            cleaned_queries = {}
            # Handle dict format (query_text -> result_dict)
            if isinstance(queries_data, dict):
                for query_text, answer_data in queries_data.items():
                    # Skip metadata keys
                    if query_text.startswith('_'):
                        continue
                    if isinstance(answer_data, dict):
                        # Keep only answer and confidence, remove geometry
                        cleaned_queries[query_text] = {
                            'answer': answer_data.get('answer'),
                            'confidence': answer_data.get('confidence'),
                            'sourcePage': answer_data.get('sourcePage')
                        }
                    else:
                        cleaned_queries[query_text] = answer_data
            # Handle list format (legacy or alternative format)
            elif isinstance(queries_data, list):
                for item in queries_data:
                    if isinstance(item, dict):
                        query_text = item.get('query', item.get('text', ''))
                        if query_text:
                            cleaned_queries[query_text] = {
                                'answer': item.get('answer'),
                                'confidence': item.get('confidence'),
                                'sourcePage': item.get('sourcePage')
                            }
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
    """Use Claude Haiku 4.5 to normalize and validate extracted data.

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

    # Check if this is a Loan Agreement with raw text (HYBRID extraction approach)
    is_loan_agreement = False
    loan_agreement_raw_text = None
    loan_agreement_textract_queries = None  # Store Textract query results for Loan Agreements

    for ext in raw_extractions:
        if isinstance(ext, dict):
            # Check for Credit Agreement sections
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

            # Check for Loan Agreement with raw text (HYBRID approach)
            # This handles scanned documents where Textract QUERIES fail
            if ext.get('isLoanAgreement') is True:
                is_loan_agreement = True
                results = ext.get('results', {})
                if isinstance(results, dict):
                    raw_text = results.get('rawText')
                    if raw_text:
                        # Loan Agreement raw text - may be OCR from scanned or native PDF
                        # IMPORTANT: Use high limit to capture maturity date from later pages
                        # Claude Haiku 4.5 can handle ~100K tokens (~400K chars) context
                        # Using 50K chars to balance cost vs extraction quality
                        MAX_LOAN_AGREEMENT_RAW_TEXT = 50000
                        if len(raw_text) > MAX_LOAN_AGREEMENT_RAW_TEXT:
                            loan_agreement_raw_text = raw_text[:MAX_LOAN_AGREEMENT_RAW_TEXT] + f"\n\n... [truncated, {len(raw_text) - MAX_LOAN_AGREEMENT_RAW_TEXT} chars omitted]"
                        else:
                            loan_agreement_raw_text = raw_text
                        print(f"Loan Agreement raw text available: {len(raw_text)} chars (extraction method: {results.get('extractionMethod', 'unknown')})")

                    # CRITICAL: Also capture Textract query results for high-confidence extractions
                    # These contain valuable data like maturity date that may not be in raw text
                    queries = results.get('queries', {})
                    if queries and isinstance(queries, dict):
                        loan_agreement_textract_queries = queries
                        # Count high-confidence queries for logging
                        high_conf_count = sum(1 for q, r in queries.items()
                                              if isinstance(r, dict) and r.get('confidence', 0) >= 70)
                        print(f"Loan Agreement Textract queries available: {len(queries)} queries ({high_conf_count} high-confidence)")

    # Determine which prompt path to use:
    # 1. Loan Agreement with raw text -> use specialized Loan Agreement prompt (HYBRID approach)
    # 2. Credit Agreement with raw text only -> use specialized Credit Agreement prompt
    # 3. Otherwise -> use general normalization path
    use_loan_agreement_prompt = is_loan_agreement and loan_agreement_raw_text
    use_credit_agreement_raw_text_prompt = is_credit_agreement and raw_text_only_sections and not has_textract_data

    if use_loan_agreement_prompt:
        print(f"Using specialized Loan Agreement raw text extraction prompt (HYBRID: Textract OCR + Claude LLM)")
        # Pass both raw text AND Textract query results for better extraction
        prompt = build_loan_agreement_prompt(loan_agreement_raw_text, loan_agreement_textract_queries)
    elif use_credit_agreement_raw_text_prompt:
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

7. **Loan Agreement Specific**:
   - Loan amounts and credit limits: Convert to numeric without currency symbols
   - Interest rates: Convert percentages to decimal (e.g., "8.5%" -> 0.085)
   - Fixed vs Variable: Identify "Fixed Rate", "Variable Rate", "Floating Rate", "Adjustable Rate"
   - Index rates: Identify type (e.g., "Prime Rate", "SOFR", "Wall Street Journal Prime")
   - Margin/Spread: Convert to decimal (e.g., "Prime + 2.0%" means margin = 0.02)
   - Day count basis: Preserve as string (e.g., "360-day year", "365-day year", "Actual/360")
   - Payment frequency: Normalize to standard terms ("Monthly", "Quarterly", "Semi-Annual", "Annual")
   - Grace periods: Extract as number of days
   - Financial covenants: List all covenant requirements found
   - Collateral: Describe the security interest or collateral pledged

8. **Missing/Unclear Data**:
   - If data cannot be confidently extracted, use null
   - NEVER hallucinate or guess missing values
   - Add a note in the validation_notes field

OUTPUT SCHEMA:
{{
  "loanData": {{
    "promissoryNote": {{
      "loanNumber": <string or null>,
      "noteDate": <ISO date string or null>,
      "effectiveDate": <ISO date string or null>,
      "interestRate": <decimal or null>,
      "annualPercentageRate": <decimal or null>,
      "principalAmount": <number or null>,
      "totalLoanAmount": <number or null>,
      "borrowerName": <string or null>,
      "borrowerAddress": <string or null>,
      "coBorrowerName": <string or null>,
      "lenderName": <string or null>,
      "lenderAddress": <string or null>,
      "maturityDate": <ISO date string or null>,
      "monthlyPayment": <number or null>,
      "firstPaymentDate": <ISO date string or null>,
      "paymentDueDay": <number or null>,
      "totalPayments": <number or null>,
      "isFixedRate": <boolean or null>,
      "indexRate": <string or null>,
      "margin": <decimal or null>,
      "rateFloor": <decimal or null>,
      "rateCeiling": <decimal or null>,
      "defaultRate": <decimal or null>,
      "balloonPayment": <number or null>,
      "latePaymentFee": <number or null>,
      "gracePeriodDays": <number or null>,
      "isSecured": <boolean or null>,
      "collateral": <string or null>,
      "propertyAddress": <string or null>,
      "hasPrepaymentPenalty": <boolean or null>,
      "prepaymentTerms": <string or null>
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
    "loanAgreement": {{
      "documentInfo": {{
        "documentType": <string or null>,
        "loanNumber": <string or null>,
        "agreementDate": <ISO date string or null>,
        "effectiveDate": <ISO date string or null>,
        "closingDate": <ISO date string or null>
      }},
      "loanTerms": {{
        "loanAmount": <number or null>,
        "creditLimit": <number or null>,
        "interestRate": <decimal or null>,
        "annualPercentageRate": <decimal or null>,
        "isFixedRate": <boolean or null>,
        "maturityDate": <ISO date string or null>,
        "loanTermMonths": <number or null>
      }},
      "interestDetails": {{
        "rateType": <string or null>,
        "indexRate": <string or null>,
        "margin": <decimal or null>,
        "floor": <decimal or null>,
        "ceiling": <decimal or null>,
        "defaultRate": <decimal or null>,
        "dayCountBasis": <string or null>
      }},
      "paymentInfo": {{
        "monthlyPayment": <number or null>,
        "firstPaymentDate": <ISO date string or null>,
        "paymentDueDay": <number or null>,
        "paymentFrequency": <string or null>,
        "numberOfPayments": <number or null>,
        "balloonPayment": <number or null>
      }},
      "parties": {{
        "borrower": {{
          "name": <string or null>,
          "address": <string or null>
        }},
        "guarantor": {{
          "name": <string or null>,
          "address": <string or null>
        }},
        "lender": {{
          "name": <string or null>,
          "address": <string or null>
        }}
      }},
      "security": {{
        "isSecured": <boolean or null>,
        "collateralDescription": <string or null>,
        "propertyAddress": <string or null>
      }},
      "fees": {{
        "originationFee": <number or null>,
        "latePaymentFee": <number or null>,
        "gracePeriodDays": <number or null>,
        "closingCosts": <number or null>,
        "annualFee": <number or null>
      }},
      "prepayment": {{
        "hasPenalty": <boolean or null>,
        "penaltyTerms": <string or null>
      }},
      "covenants": {{
        "financialCovenants": [<string>],
        "debtServiceCoverageRatio": <decimal or null>,
        "currentRatio": <decimal or null>
      }},
      "repayment": {{
        "schedule": <string or null>,
        "principalReductions": <string or null>,
        "interestOnlyPeriod": <string or null>
      }},
      "default": {{
        "eventsOfDefault": [<string>],
        "remedies": [<string>]
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


def parse_percentage_to_decimal(value: str) -> Optional[float]:
    """Convert percentage string to decimal (e.g., '4.25%' -> 0.0425)."""
    if not value:
        return None
    try:
        value = str(value).strip().replace('%', '')
        return float(value) / 100
    except (ValueError, TypeError):
        return None


def parse_currency_to_number(value: str) -> Optional[float]:
    """Convert currency string to number (e.g., '$27,000,000.00' -> 27000000.0)."""
    if not value:
        return None
    try:
        value = str(value).strip().replace('$', '').replace(',', '')
        return float(value)
    except (ValueError, TypeError):
        return None


def find_table_for_section(
    raw_extractions: List[Dict[str, Any]],
    section_name: str
) -> Optional[Dict[str, Any]]:
    """Find and return the first table from a specific extraction section.

    Args:
        raw_extractions: List of raw extraction results
        section_name: The creditAgreementSection name to look for

    Returns:
        Table dict with 'rows' key, or None if not found
    """
    for ext in raw_extractions:
        if not isinstance(ext, dict):
            continue
        if ext.get('creditAgreementSection') == section_name:
            results = ext.get('results', {})
            if results is None:
                continue
            tables_data = results.get('tables', {})
            if tables_data is None:
                continue
            tables = tables_data.get('tables', [])
            if tables:
                return tables[0]
    return None


def ensure_all_table_data(
    normalized_data: Dict[str, Any],
    raw_extractions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Post-process to ensure all table data from Textract is preserved.

    Claude Haiku 4.5 sometimes truncates arrays. This function extracts data
    directly from Textract tables to ensure all rows are included.

    Handles multiple table types:
    - applicableRates.tiers (pricing grid)
    - lenderCommitments (lender allocation table)

    Args:
        normalized_data: The LLM-normalized data
        raw_extractions: Raw extraction results containing Textract tables

    Returns:
        Updated normalized_data with all table rows preserved
    """
    # Ensure nested structure exists
    if 'loanData' not in normalized_data:
        normalized_data['loanData'] = {}
    if 'creditAgreement' not in normalized_data['loanData']:
        normalized_data['loanData']['creditAgreement'] = {}

    credit_agreement = normalized_data['loanData']['creditAgreement']

    # Initialize validation notes list
    if 'validation' not in normalized_data:
        normalized_data['validation'] = {}
    if 'validationNotes' not in normalized_data['validation']:
        normalized_data['validation']['validationNotes'] = []

    # ============================================================
    # 1. Preserve applicableRates.tiers (pricing grid table)
    # ============================================================
    try:
        applicable_rates_table = find_table_for_section(raw_extractions, 'applicableRates')

        if applicable_rates_table:
            table_rows = applicable_rates_table.get('rows', [])
            if len(table_rows) >= 2:  # Need header + at least 1 data row
                header = table_rows[0]
                header_lower = [str(h).lower() for h in header]

                # Find column indices for pricing tier table
                level_idx = None
                sofr_idx = None
                abr_idx = None
                fee_idx = None

                for i, h in enumerate(header_lower):
                    if 'usage' in h or 'level' in h or 'threshold' in h:
                        level_idx = i
                    elif 'term' in h or 'sofr' in h or 'benchmark' in h or 'rfr' in h:
                        sofr_idx = i
                    elif 'abr' in h or 'base rate' in h:
                        abr_idx = i
                    elif 'unused' in h or 'commitment fee' in h or 'fee rate' in h:
                        fee_idx = i

                print(f"[applicableRates] Column mapping: level={level_idx}, sofr={sofr_idx}, abr={abr_idx}, fee={fee_idx}")

                data_rows = table_rows[1:]
                num_table_tiers = len(data_rows)
                print(f"[applicableRates] Found {num_table_tiers} pricing tiers in Textract table")

                # Check current normalized tiers count
                if 'applicableRates' not in credit_agreement:
                    credit_agreement['applicableRates'] = {}
                current_tiers = credit_agreement.get('applicableRates', {}).get('tiers', [])
                print(f"[applicableRates] Current normalized tiers count: {len(current_tiers)}")

                # If normalized has fewer tiers, rebuild from table
                if len(current_tiers) < num_table_tiers:
                    print(f"[applicableRates] Rebuilding tiers from Textract table ({num_table_tiers} rows)")
                    new_tiers = []

                    for row in data_rows:
                        tier = {}

                        if level_idx is not None and level_idx < len(row):
                            level_val = str(row[level_idx]).strip()
                            tier['level'] = level_val
                            tier['threshold'] = level_val

                        if sofr_idx is not None and sofr_idx < len(row):
                            sofr_val = parse_percentage_to_decimal(row[sofr_idx])
                            if sofr_val is not None:
                                tier['termBenchmarkRFRSpread'] = sofr_val

                        if abr_idx is not None and abr_idx < len(row):
                            abr_val = parse_percentage_to_decimal(row[abr_idx])
                            if abr_val is not None:
                                tier['abrSpread'] = abr_val

                        if fee_idx is not None and fee_idx < len(row):
                            fee_val = parse_percentage_to_decimal(row[fee_idx])
                            if fee_val is not None:
                                tier['unusedCommitmentFeeRate'] = fee_val

                        if tier:
                            new_tiers.append(tier)

                    if new_tiers:
                        credit_agreement['applicableRates']['tiers'] = new_tiers
                        print(f"[applicableRates] Updated with {len(new_tiers)} tiers from Textract table")
                        normalized_data['validation']['validationNotes'].append(
                            f"Pricing tiers rebuilt from Textract table ({len(new_tiers)} tiers, LLM returned only {len(current_tiers)})"
                        )
                else:
                    print("[applicableRates] All tiers preserved, no post-processing needed")

    except Exception as e:
        print(f"Error processing applicableRates table: {str(e)}")

    # ============================================================
    # 2. Preserve lenderCommitments (lender allocation table)
    # ============================================================
    try:
        lender_table = find_table_for_section(raw_extractions, 'lenderCommitments')

        if lender_table:
            table_rows = lender_table.get('rows', [])
            if len(table_rows) >= 2:
                header = table_rows[0]
                header_lower = [str(h).lower() for h in header]

                # Find column indices for lender commitments table
                name_idx = None
                pct_idx = None
                term_idx = None
                revolving_idx = None
                max_revolving_idx = None

                for i, h in enumerate(header_lower):
                    if 'name' in h or 'lender' in h:
                        name_idx = i
                    elif 'applicable' in h and 'percentage' in h:
                        pct_idx = i
                    elif 'term' in h and 'commitment' in h:
                        term_idx = i
                    elif 'elected' in h and 'revolving' in h:
                        revolving_idx = i
                    elif 'maximum' in h or 'max' in h:
                        max_revolving_idx = i

                print(f"[lenderCommitments] Column mapping: name={name_idx}, pct={pct_idx}, term={term_idx}, revolving={revolving_idx}, max={max_revolving_idx}")

                # Filter out TOTAL/summary rows
                data_rows = [row for row in table_rows[1:] if not str(row[0]).strip().upper() == 'TOTAL']
                num_table_lenders = len(data_rows)
                print(f"[lenderCommitments] Found {num_table_lenders} lenders in Textract table (excluding TOTAL row)")

                # Check current normalized lender commitments count
                current_lenders = credit_agreement.get('lenderCommitments', [])
                print(f"[lenderCommitments] Current normalized lenders count: {len(current_lenders)}")

                # If normalized has fewer lenders, rebuild from table
                if len(current_lenders) < num_table_lenders:
                    print(f"[lenderCommitments] Rebuilding lenders from Textract table ({num_table_lenders} rows)")
                    new_lenders = []

                    for row in data_rows:
                        lender = {}

                        if name_idx is not None and name_idx < len(row):
                            name_val = str(row[name_idx]).strip()
                            if name_val and name_val.upper() != 'TOTAL':
                                lender['lenderName'] = name_val

                        if pct_idx is not None and pct_idx < len(row):
                            pct_val = parse_percentage_to_decimal(row[pct_idx])
                            if pct_val is not None:
                                lender['applicablePercentage'] = pct_val

                        if term_idx is not None and term_idx < len(row):
                            term_val = parse_currency_to_number(row[term_idx])
                            if term_val is not None:
                                lender['termCommitment'] = term_val

                        if revolving_idx is not None and revolving_idx < len(row):
                            revolving_val = parse_currency_to_number(row[revolving_idx])
                            if revolving_val is not None:
                                lender['electedRevolvingCreditCommitment'] = revolving_val
                                lender['revolvingCreditCommitment'] = revolving_val

                        if max_revolving_idx is not None and max_revolving_idx < len(row):
                            max_val = parse_currency_to_number(row[max_revolving_idx])
                            if max_val is not None:
                                lender['maxRevolvingCreditAmount'] = max_val

                        if lender.get('lenderName'):
                            new_lenders.append(lender)

                    if new_lenders:
                        credit_agreement['lenderCommitments'] = new_lenders
                        print(f"[lenderCommitments] Updated with {len(new_lenders)} lenders from Textract table")
                        normalized_data['validation']['validationNotes'].append(
                            f"Lender commitments rebuilt from Textract table ({len(new_lenders)} lenders, LLM returned only {len(current_lenders)})"
                        )
                else:
                    print("[lenderCommitments] All lenders preserved, no post-processing needed")

    except Exception as e:
        print(f"Error processing lenderCommitments table: {str(e)}")

    return normalized_data


def apply_loan_agreement_defaults(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default values for Loan Agreement coded fields.

    Claude sometimes returns null for coded fields that should have defaults.
    This function applies defaults based on document type and context.

    Args:
        normalized_data: The normalized data from Bedrock

    Returns:
        Updated normalized_data with defaults applied
    """
    loan_data = normalized_data.get('loanData', {})
    loan_agreement = loan_data.get('loanAgreement', {})

    if not loan_agreement:
        return normalized_data

    # Get document info to determine loan type
    document_info = loan_agreement.get('documentInfo', {})
    doc_type = document_info.get('documentType', '') or ''

    # Get interest details
    interest_details = loan_agreement.get('interestDetails', {})

    # Get payment info
    payment_info = loan_agreement.get('paymentInfo', {})

    # Get extracted codes
    extracted_codes = loan_agreement.get('_extractedCodes', {})

    # Determine if this is a line of credit
    is_line_of_credit = any(x in doc_type.upper() for x in ['LINE', 'LOC', 'REVOLV', 'CREDIT'])

    changes_made = []

    # Apply paymentFrequency/billingFrequency default
    if not payment_info.get('paymentFrequency') and not extracted_codes.get('billingFrequency'):
        # Default to monthly
        if 'paymentInfo' not in loan_agreement:
            loan_agreement['paymentInfo'] = {}
        loan_agreement['paymentInfo']['paymentFrequency'] = 'C:MONTHLY'
        if '_extractedCodes' not in loan_agreement:
            loan_agreement['_extractedCodes'] = {}
        loan_agreement['_extractedCodes']['billingFrequency'] = 'C:MONTHLY'
        changes_made.append("paymentFrequency -> C:MONTHLY (default)")

    # Apply billingType default based on loan type
    if not extracted_codes.get('billingType'):
        if '_extractedCodes' not in loan_agreement:
            loan_agreement['_extractedCodes'] = {}
        if is_line_of_credit:
            # Lines of credit are typically interest-only until maturity
            loan_agreement['_extractedCodes']['billingType'] = 'A:INTEREST ONLY'
            changes_made.append("billingType -> A:INTEREST ONLY (LOC default)")
        else:
            # Term loans with payments are typically amortizing
            loan_agreement['_extractedCodes']['billingType'] = 'F:PAYMENT AMOUNT INCLUDING INTEREST'
            changes_made.append("billingType -> F:PAYMENT AMOUNT INCLUDING INTEREST (term loan default)")

    # Apply currency default
    if 'currency' not in extracted_codes or not extracted_codes.get('currency'):
        if '_extractedCodes' not in loan_agreement:
            loan_agreement['_extractedCodes'] = {}
        loan_agreement['_extractedCodes']['currency'] = 'USD:US DOLLAR'
        changes_made.append("currency -> USD:US DOLLAR (default)")

    # Apply rateCalculationMethod/dayCountBasis default
    if not interest_details.get('dayCountBasis') and not extracted_codes.get('rateCalculationMethod'):
        if 'interestDetails' not in loan_agreement:
            loan_agreement['interestDetails'] = {}
        loan_agreement['interestDetails']['dayCountBasis'] = '360ACTUAL:ACTUAL DAYS / 360 DAY YEAR'
        if '_extractedCodes' not in loan_agreement:
            loan_agreement['_extractedCodes'] = {}
        loan_agreement['_extractedCodes']['rateCalculationMethod'] = '360ACTUAL:ACTUAL DAYS / 360 DAY YEAR'
        changes_made.append("dayCountBasis -> 360ACTUAL:ACTUAL DAYS / 360 DAY YEAR (default)")

    # Apply interestRateType default if Prime is referenced
    raw_rate_type = interest_details.get('rateType', '') or ''
    if not extracted_codes.get('interestRateType') and raw_rate_type:
        if '_extractedCodes' not in loan_agreement:
            loan_agreement['_extractedCodes'] = {}
        if 'prime' in raw_rate_type.lower():
            loan_agreement['_extractedCodes']['interestRateType'] = 'PRM:PRIME RATE LOAN'
            changes_made.append("interestRateType -> PRM:PRIME RATE LOAN (detected Prime)")
        elif 'fixed' in raw_rate_type.lower():
            loan_agreement['_extractedCodes']['interestRateType'] = 'FIX:FIXED RATE LOAN'
            changes_made.append("interestRateType -> FIX:FIXED RATE LOAN (detected Fixed)")
        elif 'sofr' in raw_rate_type.lower():
            loan_agreement['_extractedCodes']['interestRateType'] = 'SOF:SOFR'
            changes_made.append("interestRateType -> SOF:SOFR (detected SOFR)")

    # Apply rateIndex default if Prime Rate is mentioned
    index_rate = interest_details.get('indexRate', '') or ''
    if not extracted_codes.get('rateIndex') and index_rate:
        if '_extractedCodes' not in loan_agreement:
            loan_agreement['_extractedCodes'] = {}
        if 'prime' in index_rate.lower() or 'wall street' in index_rate.lower():
            loan_agreement['_extractedCodes']['rateIndex'] = 'WALLST:WALL STREET JOURNAL PRIME'
            changes_made.append("rateIndex -> WALLST:WALL STREET JOURNAL PRIME (detected Prime)")
        elif 'sofr' in index_rate.lower():
            loan_agreement['_extractedCodes']['rateIndex'] = 'SOFR:SOFR RATE'
            changes_made.append("rateIndex -> SOFR:SOFR RATE (detected SOFR)")

    # Update the normalized data
    if changes_made:
        normalized_data['loanData']['loanAgreement'] = loan_agreement
        print(f"Post-processing: Applied Loan Agreement defaults: {', '.join(changes_made)}")

        # Add note to validation
        if 'validation' not in normalized_data:
            normalized_data['validation'] = {'isValid': True, 'confidence': 'medium', 'validationNotes': []}
        if 'validationNotes' not in normalized_data['validation']:
            normalized_data['validation']['validationNotes'] = []
        normalized_data['validation']['validationNotes'].append(
            f"Applied {len(changes_made)} default value(s) for coded fields"
        )

    return normalized_data


# Keep the old function name as an alias for backward compatibility
def ensure_all_pricing_tiers(
    normalized_data: Dict[str, Any],
    raw_extractions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Deprecated: Use ensure_all_table_data instead."""
    return ensure_all_table_data(normalized_data, raw_extractions)


def extract_signature_validation(extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract signature validation data from all extraction results.

    Aggregates signature detection results from all document sections/pages
    to provide a comprehensive signature validation status.

    Args:
        extractions: List of extraction results from parallel processing

    Returns:
        Dict with signature validation summary:
        - hasSignatures: bool indicating if any signatures were detected
        - signatureCount: total number of signatures found
        - highConfidenceCount: signatures meeting confidence threshold
        - signatures: list of signature details with page references
        - validationStatus: 'SIGNED', 'UNSIGNED', or 'PARTIAL'
    """
    all_signatures = []
    total_count = 0
    high_confidence_count = 0
    pages_with_signatures = set()

    for ext in extractions:
        if not isinstance(ext, dict):
            continue

        # Get results dict which contains signatures
        results = ext.get('results', {})
        if not isinstance(results, dict):
            continue

        # Extract signature data
        sig_data = results.get('signatures', {})
        if not sig_data:
            continue

        # Handle both dict format (from single extraction) and list format
        if isinstance(sig_data, dict):
            signatures = sig_data.get('signatures', [])
            for sig in signatures:
                if isinstance(sig, dict):
                    sig_entry = {
                        'confidence': sig.get('confidence', 0),
                        'meetsThreshold': sig.get('meetsThreshold', False),
                        'boundingBox': sig.get('boundingBox', {}),
                    }

                    # Track source page from extraction context
                    source_page = sig.get('sourcePage') or ext.get('pageNumber')
                    if source_page:
                        sig_entry['sourcePage'] = source_page
                        pages_with_signatures.add(source_page)

                    # Track section for Credit Agreements
                    section = ext.get('creditAgreementSection')
                    if section:
                        sig_entry['sourceSection'] = section

                    all_signatures.append(sig_entry)
                    total_count += 1
                    if sig.get('meetsThreshold', False):
                        high_confidence_count += 1

    # Determine validation status
    if total_count == 0:
        validation_status = 'UNSIGNED'
    elif high_confidence_count > 0:
        validation_status = 'SIGNED'
    else:
        # Signatures detected but all low confidence
        validation_status = 'PARTIAL'

    return {
        'hasSignatures': total_count > 0,
        'signatureCount': total_count,
        'highConfidenceCount': high_confidence_count,
        'lowConfidenceCount': total_count - high_confidence_count,
        'pagesWithSignatures': sorted(list(pages_with_signatures)),
        'validationStatus': validation_status,
        'signatures': all_signatures,
    }


def calculate_processing_cost(
    normalizer_tokens: Dict[str, int],
    textract_pages: int,
    router_tokens: Optional[Dict[str, int]] = None,
    is_credit_agreement: bool = False,
    lambda_memory_mb: int = 1024,
    estimated_duration_ms: int = 30000,
) -> Dict[str, Any]:
    """Calculate the total processing cost for a document including ALL AWS services.

    Pricing:
    - Claude Haiku 4.5 (Router): $0.001/1K input, $0.005/1K output
    - Claude Haiku 4.5 (Normalizer): $0.001/1K input, $0.005/1K output
    - Textract (Tables + Queries): $0.02 per page
    - Step Functions (Standard): $0.000025 per state transition
    - Lambda: $0.0000002 per invocation + $0.0000166667 per GB-second

    Args:
        normalizer_tokens: Dict with inputTokens and outputTokens from normalizer
        textract_pages: Number of pages processed by Textract
        router_tokens: Optional dict with inputTokens and outputTokens from router
        is_credit_agreement: Whether this is a Credit Agreement (affects state count)
        lambda_memory_mb: Lambda memory allocation in MB
        estimated_duration_ms: Estimated total Lambda execution time in ms

    Returns:
        Dict with cost breakdown and total
    """
    # Pricing constants (per 1K tokens)
    # Claude Haiku 4.5: $1.00/MTok input = $0.001/1K, $5.00/MTok output = $0.005/1K
    HAIKU_45_INPUT = 0.001
    HAIKU_45_OUTPUT = 0.005
    TEXTRACT_PER_PAGE = 0.02  # Tables + Queries combined

    # Step Functions pricing (Standard Workflow)
    STEP_FUNCTIONS_PER_TRANSITION = 0.000025  # $25 per million

    # Lambda pricing
    LAMBDA_PER_INVOCATION = 0.0000002  # $0.20 per million
    LAMBDA_PER_GB_SECOND = 0.0000166667

    # Router cost (Claude Haiku 4.5)
    router_cost = 0.0
    router_input = 0
    router_output = 0
    router_tokens_are_real = bool(router_tokens)  # Track if we have real data
    if router_tokens:
        router_input = router_tokens.get('inputTokens', 0)
        router_output = router_tokens.get('outputTokens', 0)
        router_cost = (
            (router_input / 1000) * HAIKU_45_INPUT +
            (router_output / 1000) * HAIKU_45_OUTPUT
        )
    else:
        # Estimate router cost if not provided (~20K input, 500 output typical)
        # This should NOT happen with the updated pipeline - log a warning
        print("WARNING: Using estimated router tokens - pipeline may not be passing real values")
        router_input = 20000
        router_output = 500
        router_cost = (
            (router_input / 1000) * HAIKU_45_INPUT +
            (router_output / 1000) * HAIKU_45_OUTPUT
        )

    # Normalizer cost (Claude Haiku 4.5)
    normalizer_input = normalizer_tokens.get('inputTokens', 0)
    normalizer_output = normalizer_tokens.get('outputTokens', 0)
    normalizer_cost = (
        (normalizer_input / 1000) * HAIKU_45_INPUT +
        (normalizer_output / 1000) * HAIKU_45_OUTPUT
    )

    # Textract cost
    textract_cost = textract_pages * TEXTRACT_PER_PAGE

    # Step Functions cost
    # Credit Agreement: classify -> choice -> 7 parallel branches -> normalize -> complete = 11 transitions
    # Mortgage: classify -> choice -> 3 parallel branches -> normalize -> complete = 7 transitions
    state_transitions = 11 if is_credit_agreement else 7
    step_functions_cost = state_transitions * STEP_FUNCTIONS_PER_TRANSITION

    # Lambda cost
    # 4 Lambda invocations per document: trigger, router, extractor, normalizer
    lambda_invocations = 4
    lambda_invocation_cost = lambda_invocations * LAMBDA_PER_INVOCATION

    # Lambda compute cost (GB-seconds)
    # Convert memory from MB to GB, duration from ms to seconds
    lambda_gb_seconds = (lambda_memory_mb / 1024) * (estimated_duration_ms / 1000)
    lambda_compute_cost = lambda_gb_seconds * LAMBDA_PER_GB_SECOND

    total_lambda_cost = lambda_invocation_cost + lambda_compute_cost

    # Total cost
    total_cost = router_cost + textract_cost + normalizer_cost + step_functions_cost + total_lambda_cost

    return {
        'totalCost': round(total_cost, 4),
        'breakdown': {
            'router': {
                'model': 'claude-haiku-4.5',
                'inputTokens': router_input,
                'outputTokens': router_output,
                'cost': round(router_cost, 6),
                'isReal': router_tokens_are_real,  # True = from Bedrock API, False = estimated
            },
            'textract': {
                'pages': textract_pages,
                'costPerPage': TEXTRACT_PER_PAGE,
                'cost': round(textract_cost, 4),
                'isReal': True,  # Always real - counted from extractions
            },
            'normalizer': {
                'model': 'claude-haiku-4.5',
                'inputTokens': normalizer_input,
                'outputTokens': normalizer_output,
                'cost': round(normalizer_cost, 6),
                'isReal': True,  # Always real - from Bedrock API in this Lambda
            },
            'stepFunctions': {
                'stateTransitions': state_transitions,
                'costPerTransition': STEP_FUNCTIONS_PER_TRANSITION,
                'cost': round(step_functions_cost, 6),
                'isReal': True,  # Deterministic based on workflow path
            },
            'lambda': {
                'invocations': lambda_invocations,
                'gbSeconds': round(lambda_gb_seconds, 2),
                'memoryMb': lambda_memory_mb,
                'estimatedDurationMs': estimated_duration_ms,
                'invocationCost': round(lambda_invocation_cost, 8),
                'computeCost': round(lambda_compute_cost, 6),
                'cost': round(total_lambda_cost, 6),
                'isReal': False,  # Duration is estimated - actual Lambda metrics not available here
            },
        },
        'currency': 'USD',
        # Summary flag: True only if ALL cost components are real/measured
        'allCostsReal': router_tokens_are_real,  # Lambda duration is always estimated
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

    # Estimate phase breakdown (approximate based on actual parallel processing patterns)
    # With 30-worker parallel Textract extraction:
    # - Router: ~45% of time (PyPDF text extraction + Claude Haiku classification)
    # - Textract: ~20% of time (parallel extraction across all sections)
    # - Normalizer: ~35% of time (Claude Haiku 4.5 data normalization)
    # NOTE: These are approximations - individual Lambda durations are not tracked
    router_seconds = total_seconds * 0.45
    textract_seconds = total_seconds * 0.20
    normalizer_seconds = total_seconds * 0.35

    return {
        'totalSeconds': round(total_seconds, 2),
        'totalSecondsIsReal': bool(uploaded_at and total_seconds > 0),  # True if measured from uploadedAt
        'startedAt': started_at_str,
        'completedAt': completed_at.isoformat() + 'Z',
        'breakdown': {
            'router': {
                'estimatedSeconds': round(router_seconds, 2),
                'description': 'Document classification with Claude Haiku',
                'isEstimated': True,  # Phase breakdown is approximated
            },
            'textract': {
                'estimatedSeconds': round(textract_seconds, 2),
                'pages': textract_pages,
                'description': 'Parallel page extraction with Textract',
                'isEstimated': True,  # Phase breakdown is approximated
            },
            'normalizer': {
                'estimatedSeconds': round(normalizer_seconds, 2),
                'description': 'Data normalization with Claude Haiku 4.5',
                'isEstimated': True,  # Phase breakdown is approximated
            },
        },
        'note': 'totalSeconds is real (measured); breakdown is estimated based on typical patterns',
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
    signature_validation: Optional[Dict[str, Any]] = None,
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
        signature_validation: Signature validation results
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

    # Add signature validation
    if signature_validation:
        item['signatureValidation'] = convert_floats_to_decimal(signature_validation)

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

    # ============================================================
    # Plugin-driven normalization path
    # ============================================================
    plugin_id = event.get("pluginId")
    if plugin_id:
        print(f"[PLUGIN] Using plugin path for plugin_id='{plugin_id}'")
        try:
            from document_plugins.registry import get_plugin
            plugin = get_plugin(plugin_id)
        except (ImportError, KeyError) as e:
            print(f"[PLUGIN] Plugin load failed: {e}, falling back to legacy path")
            plugin_id = None  # Fall through to legacy

    # Resolve existing DynamoDB documentType for event logging
    _doc_type_for_events = "PROCESSING"
    try:
        _q = dynamodb.Table(TABLE_NAME).query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
            Limit=1,
        )
        if _q.get("Items"):
            _doc_type_for_events = _q["Items"][0].get("documentType", "PROCESSING")
    except Exception:
        pass

    if plugin_id:
        append_processing_event(document_id, _doc_type_for_events, "normalizer", "Normalizing extracted data...")
        try:
            # Build prompt from plugin templates
            raw_data = {"sections": {}}
            extractions_list = event.get("extractions", [event])
            if isinstance(extractions_list, list):
                for ext in extractions_list:
                    if isinstance(ext, dict):
                        section = ext.get("section") or ext.get("creditAgreementSection")
                        if section:
                            raw_data["sections"][section] = ext.get("results", ext)
                        else:
                            raw_data = ext.get("results", ext)

            # Skip legacy clean_extraction_for_normalization for plugin path --
            # it drops forms/keyValues data needed for BSA Profile.
            # build_normalization_prompt handles payload truncation internally.
            prompt = build_normalization_prompt(plugin, raw_data)
            normalized_data, normalizer_tokens = invoke_bedrock_normalize(prompt, plugin)
            normalized_data = apply_field_overrides(normalized_data, plugin)

            # Apply document-type-specific post-processing that was in the legacy path.
            # These fix LLM truncation and apply coded defaults that the prompt alone
            # cannot guarantee.
            if plugin_id == "credit_agreement":
                try:
                    ensure_all_table_data(
                        normalized_data,
                        extractions_list if isinstance(extractions_list, list) else [extractions_list],
                    )
                except Exception as e:
                    print(f"[PLUGIN] ensure_all_table_data failed (non-fatal): {e}")

                # Amendment number cleanup: "Amended and Restated" docs sometimes
                # get spurious amendment numbers from Textract
                try:
                    loan_data = normalized_data.get("loanData", {})
                    ca_data = loan_data.get("creditAgreement", loan_data)
                    doc_info = ca_data.get("documentInfo", ca_data.get("agreementInfo", {}))
                    doc_title = (doc_info.get("documentType", "") or "").lower()
                    if "amended and restated" in doc_title:
                        amend_num = doc_info.get("amendmentNumber")
                        if amend_num and not str(amend_num).lower().startswith("amendment no"):
                            doc_info["amendmentNumber"] = None
                except Exception:
                    pass

            elif plugin_id == "loan_agreement":
                try:
                    apply_loan_agreement_defaults(normalized_data)
                except Exception as e:
                    print(f"[PLUGIN] apply_loan_agreement_defaults failed (non-fatal): {e}")

            print(f"[PLUGIN] Normalization complete. Tokens: in={normalizer_tokens['inputTokens']}, out={normalizer_tokens['outputTokens']}")

            # Count normalized fields for event message
            def _count_fields(obj, depth=0):
                if depth > 5 or obj is None:
                    return 0
                if isinstance(obj, dict):
                    return sum(_count_fields(v, depth + 1) for v in obj.values())
                if isinstance(obj, list):
                    return sum(_count_fields(i, depth + 1) for i in obj)
                return 1
            field_count = _count_fields(normalized_data.get("loanData", normalized_data))
            confidence = normalized_data.get("validation", {}).get("confidence", "unknown")
            append_processing_event(
                document_id, _doc_type_for_events, "normalizer",
                f"Normalization complete — {field_count} fields extracted (confidence: {confidence})",
            )

            # Signature validation (shared)
            signature_validation = extract_signature_validation(
                extractions_list if isinstance(extractions_list, list) else [extractions_list]
            )
            normalized_data["signatureValidation"] = signature_validation

            # Cost calculation
            textract_pages = 0
            for ext in (extractions_list if isinstance(extractions_list, list) else [extractions_list]):
                if isinstance(ext, dict):
                    textract_pages += ext.get("pageCount", 0) or (1 if ext.get("status") == "EXTRACTED" else 0)

            router_tokens = event.get("routerTokenUsage")
            processing_cost = calculate_processing_cost(
                normalizer_tokens=normalizer_tokens,
                textract_pages=textract_pages,
                router_tokens=router_tokens,
                is_credit_agreement=(plugin_id == "credit_agreement"),
                lambda_memory_mb=2048,
                estimated_duration_ms=30000 + (textract_pages * 1000),
            )
            processing_time = calculate_processing_time(
                uploaded_at=uploaded_at, textract_pages=textract_pages,
            )

            # Store results
            document_type = plugin_id.upper()
            store_to_dynamodb(
                document_id=document_id,
                normalized_data=normalized_data,
                content_hash=content_hash,
                original_key=original_key,
                file_size=file_size,
                document_type=document_type,
                processing_cost=processing_cost,
                processing_time=processing_time,
                signature_validation=signature_validation,
            )
            audit_key = store_audit_to_s3(
                bucket, document_id,
                extractions_list if isinstance(extractions_list, list) else [extractions_list],
                normalized_data,
            )

            return {
                "documentId": document_id,
                "contentHash": content_hash,
                "documentType": document_type,
                "pluginId": plugin_id,
                "status": "COMPLETED",
                "reviewStatus": "PENDING_REVIEW",
                "validation": normalized_data.get("validation", {}),
                "signatureValidation": signature_validation,
                "processingCost": processing_cost,
                "processingTime": processing_time,
                "storage": {"dynamodbTable": TABLE_NAME, "auditS3Key": audit_key},
            }
        except Exception as plugin_err:
            print(f"[PLUGIN] Error in plugin path: {plugin_err}")
            raise

    # ============================================================
    # [LEGACY] Original hardcoded normalization path
    # ============================================================
    print(f"Processing {len(extractions)} extractions for document: {document_id}")
    print(f"Content hash: {content_hash[:16] if content_hash else 'N/A'}...")
    print(f"Upload timestamp: {uploaded_at if uploaded_at else 'N/A'}")

    # Detect document type from extractions
    # Credit Agreement extractions have 'creditAgreementSection' field
    # Loan Agreement extractions have 'isLoanAgreement' field set to True
    is_credit_agreement = any(
        isinstance(ext, dict) and ext.get('creditAgreementSection')
        for ext in extractions
    )
    is_loan_agreement = any(
        isinstance(ext, dict) and ext.get('isLoanAgreement') is True
        for ext in extractions
    )

    if is_credit_agreement:
        document_type = 'CREDIT_AGREEMENT'
    elif is_loan_agreement:
        document_type = 'LOAN_AGREEMENT'
    else:
        document_type = 'LOAN_PACKAGE'
    print(f"Detected document type: {document_type}")

    append_processing_event(document_id, _doc_type_for_events, "normalizer", "Normalizing extracted data...")

    try:
        # 1. Normalize data with Bedrock (Claude Haiku 4.5 for cost optimization)
        print(f"Normalizing data with {BEDROCK_MODEL_ID}...")
        normalization_result = normalize_with_bedrock(extractions, document_id)
        normalized_data = normalization_result['data']
        normalizer_tokens = normalization_result['tokenUsage']
        print(f"Normalization complete. Validation: {normalized_data.get('validation', {})}")

        # Log legacy normalization completion event
        _legacy_confidence = normalized_data.get("validation", {}).get("confidence", "unknown")
        append_processing_event(
            document_id, _doc_type_for_events, "normalizer",
            f"Normalization complete (confidence: {_legacy_confidence})",
        )

        # Post-processing fix for amendment number
        # "Amended and Restated" agreements are NOT amendments - they are restated documents
        # Textract often picks up document reference numbers (like "112") incorrectly
        if is_credit_agreement:
            loan_data = normalized_data.get('loanData', {})
            credit_agreement = loan_data.get('creditAgreement', {})
            agreement_info = credit_agreement.get('agreementInfo', {})
            doc_type = agreement_info.get('documentType', '') or ''
            amendment_num = agreement_info.get('amendmentNumber')

            # If document type contains "Amended and Restated" (case insensitive),
            # amendmentNumber should be null unless it's explicitly an "Amendment No. X to..."
            if 'amended and restated' in doc_type.lower():
                # Check if this is actually an amendment TO an amended and restated agreement
                if not ('amendment no' in doc_type.lower() or 'amendment number' in doc_type.lower()):
                    if amendment_num is not None:
                        print(f"Post-processing: Setting amendmentNumber to null (was '{amendment_num}') for '{doc_type}'")
                        normalized_data['loanData']['creditAgreement']['agreementInfo']['amendmentNumber'] = None

            # Post-processing: Ensure all pricing tiers are preserved from Textract tables
            # Claude Haiku 4.5 sometimes truncates arrays to 3 items
            normalized_data = ensure_all_pricing_tiers(normalized_data, extractions)

        # Post-processing for Loan Agreement defaults
        # Claude sometimes returns null for coded fields - apply defaults here
        if is_loan_agreement:
            normalized_data = apply_loan_agreement_defaults(normalized_data)

        print(f"Normalizer tokens - Input: {normalizer_tokens['inputTokens']}, Output: {normalizer_tokens['outputTokens']}")

        # 2. Extract and add signature validation (global for all document types)
        print("Processing signature validation...")
        signature_validation = extract_signature_validation(extractions)
        print(f"Signature validation: {signature_validation['validationStatus']} ({signature_validation['signatureCount']} signatures found)")

        # Add signature validation to normalized data
        normalized_data['signatureValidation'] = signature_validation

        # Add signature status to validation notes
        if 'validation' not in normalized_data:
            normalized_data['validation'] = {'isValid': False, 'confidence': 'low', 'validationNotes': []}
        if 'validationNotes' not in normalized_data['validation']:
            normalized_data['validation']['validationNotes'] = []

        # Add signature validation note
        if signature_validation['validationStatus'] == 'UNSIGNED':
            normalized_data['validation']['validationNotes'].append(
                'No handwritten signatures detected - document may be unsigned'
            )
        elif signature_validation['validationStatus'] == 'PARTIAL':
            normalized_data['validation']['validationNotes'].append(
                f"Signatures detected but with low confidence ({signature_validation['signatureCount']} found)"
            )
        else:
            pages_str = ', '.join(str(p) for p in signature_validation['pagesWithSignatures'][:5])
            if len(signature_validation['pagesWithSignatures']) > 5:
                pages_str += '...'
            normalized_data['validation']['validationNotes'].append(
                f"Document signed ({signature_validation['highConfidenceCount']} high-confidence signatures on pages: {pages_str})"
            )

        # 3. Calculate Textract pages from extractions
        # Different document types report page counts differently:
        # - Credit Agreement sections: pageCount field
        # - Loan Agreement (HYBRID): varies by extractionMethod
        #   - textract_ocr: ALL pages processed with Textract OCR
        #   - hybrid_pypdf_ocr: ONLY low-quality pages processed with Textract OCR
        #   - pypdf: May use Textract queries for supplemental extraction
        # - Mortgage docs: single pageNumber
        textract_pages = 0
        for ext in extractions:
            if isinstance(ext, dict):
                # LOAN_AGREEMENT (HYBRID extraction): check extractionMethod
                if ext.get('isLoanAgreement'):
                    extraction_method = ext.get('extractionMethod', '')
                    results = ext.get('results', {}) or {}

                    if extraction_method == 'textract_ocr':
                        # Textract OCR was used for ALL pages - fully scanned document
                        pages_processed = ext.get('pagesProcessed', 0)
                        if pages_processed:
                            textract_pages += pages_processed
                            print(f"Loan Agreement Textract OCR (scanned): {pages_processed} pages")
                        else:
                            # Fallback to metadata if pagesProcessed not at top level
                            metadata = ext.get('metadata', {})
                            pages_extracted = metadata.get('pagesExtracted', 1)
                            textract_pages += pages_extracted
                            print(f"Loan Agreement Textract OCR (from metadata): {pages_extracted} pages")

                    elif extraction_method == 'hybrid_pypdf_ocr':
                        # Hybrid mode: Textract OCR was used ONLY for low-quality pages
                        # PyPDF was used for readable pages (free)
                        ocr_pages = results.get('ocrPages', [])
                        if ocr_pages:
                            textract_pages += len(ocr_pages)
                            print(f"Loan Agreement Hybrid OCR: {len(ocr_pages)} pages (OCR'd: {ocr_pages})")
                        else:
                            # Fallback: check ocrTextLength as indicator Textract was used
                            if results.get('ocrTextLength', 0) > 0:
                                # Can't determine exact page count, estimate 1
                                textract_pages += 1
                                print(f"Loan Agreement Hybrid OCR: estimated 1 page (ocrTextLength={results.get('ocrTextLength')})")

                    elif extraction_method == 'pypdf':
                        # Native text PDF - check if Textract queries were used as supplemental
                        queries = results.get('queries', {})
                        if queries and isinstance(queries, dict):
                            # Textract queries were run for supplemental extraction
                            # Count pages that were processed (from pageRange)
                            page_range = ext.get('pageRange', [])
                            if page_range:
                                textract_pages += len(page_range)
                                print(f"Loan Agreement PyPDF + Textract queries: {len(page_range)} pages")
                            else:
                                # Fallback to pagesProcessed
                                pages_processed = ext.get('pagesProcessed', 0)
                                if pages_processed:
                                    textract_pages += pages_processed
                                    print(f"Loan Agreement PyPDF + Textract queries: {pages_processed} pages")
                        else:
                            # Pure PyPDF extraction - no Textract cost
                            print(f"Loan Agreement used {extraction_method} - no Textract cost")

                    else:
                        # Other methods (pypdf_fallback, pypdf_partial) - no Textract cost
                        print(f"Loan Agreement used {extraction_method} - no Textract cost")

                # Credit Agreement sections have pageCount
                elif ext.get('pageCount'):
                    textract_pages += ext['pageCount']
                # Mortgage docs have single pageNumber
                elif ext.get('pageNumber') and ext.get('status') == 'EXTRACTED':
                    textract_pages += 1

        print(f"Total Textract pages processed: {textract_pages}")

        # 2b. Extract REAL router token usage
        # First check top-level event (from router via Step Functions), then check extractions array
        router_tokens = event.get('routerTokenUsage')
        if router_tokens:
            print(f"Found router token usage at TOP LEVEL: Input={router_tokens.get('inputTokens', 0)}, Output={router_tokens.get('outputTokens', 0)}")
        else:
            # Fall back to checking extractions array (parallel state might flatten it)
            for ext in extractions:
                if isinstance(ext, dict) and ext.get('routerTokenUsage'):
                    router_tokens = ext['routerTokenUsage']
                    print(f"Found router token usage in extractions: Input={router_tokens.get('inputTokens', 0)}, Output={router_tokens.get('outputTokens', 0)}")
                    break

        if not router_tokens:
            print("WARNING: routerTokenUsage not found in event or extractions - cost will use estimate")

        # 3. Calculate processing cost (including Step Functions and Lambda costs)
        # Estimate Lambda duration based on page count and document type
        # Credit Agreements with many pages take longer (~40-60s), smaller docs ~15-30s
        estimated_duration_ms = 30000 + (textract_pages * 1000)  # Base 30s + 1s per page
        if is_credit_agreement:
            estimated_duration_ms += 10000  # Credit Agreements have more complex processing

        processing_cost = calculate_processing_cost(
            normalizer_tokens=normalizer_tokens,
            textract_pages=textract_pages,
            router_tokens=router_tokens,  # REAL router tokens from extraction passthrough
            is_credit_agreement=is_credit_agreement,
            lambda_memory_mb=1024,  # Current Lambda memory configuration
            estimated_duration_ms=estimated_duration_ms,
        )
        print(f"Processing cost: ${processing_cost['totalCost']:.4f} (includes Step Functions + Lambda)")

        # 4. Calculate processing time
        processing_time = calculate_processing_time(
            uploaded_at=uploaded_at,
            textract_pages=textract_pages,
        )
        print(f"Processing time: {processing_time['totalSeconds']:.1f}s")

        # 5. Store to DynamoDB (with contentHash, reviewStatus, cost, time, and signature validation)
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
            signature_validation=signature_validation,
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
                'signatureStatus': signature_validation['validationStatus'],
                'signatureCount': signature_validation['signatureCount'],
            }
        elif is_loan_agreement:
            # Loan Agreement summary (simple business/personal loans)
            loan_agreement = loan_data.get('loanAgreement') or {}
            loan_terms = loan_agreement.get('loanTerms') or {}
            document_info = loan_agreement.get('documentInfo') or {}
            parties = loan_agreement.get('parties') or {}
            borrower = parties.get('borrower') or {}
            validation = normalized_data.get('validation') or {}

            summary = {
                'documentType': 'LOAN_AGREEMENT',
                'loanAmount': loan_terms.get('loanAmount'),
                'interestRate': loan_terms.get('interestRate'),
                'borrowerName': borrower.get('name'),
                'maturityDate': loan_terms.get('maturityDate'),
                'isValid': validation.get('isValid', False),
                'confidence': validation.get('confidence', 'low'),
                'signatureStatus': signature_validation['validationStatus'],
                'signatureCount': signature_validation['signatureCount'],
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
                'signatureStatus': signature_validation['validationStatus'],
                'signatureCount': signature_validation['signatureCount'],
            }

        # 8. Return results with processing cost, time, and signature validation
        return {
            'documentId': document_id,
            'contentHash': content_hash,
            'documentType': document_type,
            'status': 'COMPLETED',
            'reviewStatus': 'PENDING_REVIEW',
            'validation': normalized_data.get('validation', {}),
            'signatureValidation': signature_validation,
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
