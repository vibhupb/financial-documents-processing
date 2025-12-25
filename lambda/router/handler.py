"""Router Lambda - Document Classification

This Lambda function implements the "Router" pattern:
1. Downloads the PDF from S3 (streaming to minimize memory)
2. Extracts text snippets from each page using PyPDF
3. Uses Claude 3 Haiku to classify and identify key pages
4. Returns the page numbers for targeted extraction

This is the COST OPTIMIZATION layer - we use fast, cheap Haiku
to find the needles in the haystack before expensive extraction.

Supports all document types defined in the classification schema:
- Credit Agreement: Syndicated loans, ABL facilities, Term loans
- Mortgage: Promissory Note, Closing Disclosure, Form 1003, Deed of Trust, etc.
- Loan: Personal Loan, Business Loan, Auto Loan
- Legal: Power of Attorney, Trust Agreement, LLC Operating Agreement, etc.
- Financial: Bank Statement, Pay Stub, P&L, Balance Sheet
- Identity: Driver's License, Passport
- Tax: W-2, Form 1040, Business Tax Returns
- Insurance: Homeowners, Flood
"""

import io
import json
import os
from datetime import datetime
from typing import Any

import boto3
from pypdf import PdfReader

# Initialize AWS clients
s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")

# Configuration
BUCKET_NAME = os.environ.get("BUCKET_NAME")
TABLE_NAME = os.environ.get("TABLE_NAME", "financial-documents")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-haiku-20240307-v1:0"
)

# Text extraction settings
MAX_CHARS_PER_PAGE = 1500  # Chars per page for classification
BATCH_SIZE = 50  # Pages per Bedrock request


# Credit Agreement section definitions for targeted extraction
# Keywords are derived from the actual fields we need to extract (from loan_prompts_map):
# - Loan Master Fields: effective_date, maturity_date, pricing_option, instrument_type
# - Loan Accrual Fields: base_rate, spread_rate, rate_index, year_basis
# - Schedules/Repayment: billing_frequency, payment_amount
# NOTE: agreementInfo is ALWAYS first 5 pages - no keyword matching needed
CREDIT_AGREEMENT_SECTIONS = {
    "agreementInfo": {
        "name": "Agreement Information",
        "keywords": [],  # No keywords - always use first 5 pages
        "max_pages": 5,  # Hard limit - agreement info is always at the start
        "typical_pages": "first 5 pages",
        "extraction_fields": [
            "instrument_type",
            "loan_effective_date",
            "borrower_name",
            "administrative_agent",
            "amendment_number",
        ],
    },
    "definitions": {
        "name": "Key Definitions",
        "keywords": [
            # Business day calculation (page ~8)
            "business day",
            '"business day" means',
            "business day calculation",
            "banking day",
            # Interest payment date / Interest period (page ~22)
            "interest payment date",
            '"interest payment date" means',
            "interest period",
            '"interest period" means',
            "payment date means",
            # Lead Arranger (page ~23)
            "lead arranger",
            '"lead arranger" means',
            "joint lead arranger",
            "lead bookrunner",
            "joint bookrunner",
            # Maturity date definition (page ~25-31)
            # Using simpler patterns that work with both curly and straight quotes
            "maturity date",
            "maturity date means",
            "means may 24",  # specific date pattern from this agreement
            "may 24, 2027",  # the actual date
            "scheduled maturity",
            "termination date",
            "termination date means",
            # Unused Revolving Credit Commitment (page ~40)
            "unused revolving credit",
            '"unused revolving" means',
            "unused commitment",
            "unused portion",
            "available commitment",
            # Letter of credit (pages ~48-49)
            "letter of credit",
            '"letter of credit" means',
            "l/c",
            "lc commitment",
            '"lc commitment" means',
            "lc expiration date",
            "letter of credit expiration",
            # Commitment Fee (page ~59)
            "commitment fee",
            '"commitment fee" means',
            "unused commitment fee",
            "fee rate",
            "per annum fee",
        ],
        "max_pages": 10,  # Include key definition pages for critical fields
        "min_keyword_matches": 2,
        "typical_pages": "pages 5-60 (definitions section)",
        "extraction_fields": [
            "business_day_definition",
            "interest_payment_date",
            "interest_period",
            "lead_arranger",
            "maturity_date",
            "unused_revolving_credit_commitment",
            "letter_of_credit",
            "lc_expiration_date",
            "commitment_fee",
        ],
    },
    "applicableRates": {
        "name": "Applicable Rates/Pricing Grid",
        # Specific keywords from extraction fields - look for actual pricing tables
        # Also include definition page keywords (often page 5-15)
        "keywords": [
            # Pricing level table headers
            "pricing level",
            "level i",
            "level ii",
            "level iii",
            "level iv",
            "level v",
            # Rate spread columns
            "term sofr spread",
            "sofr spread",
            "abr spread",
            "base rate spread",
            "eurodollar spread",
            "unused commitment fee",
            # Definition section keywords (often page 5-15)
            "applicable rate",
            "applicable margin",
            '"applicable rate" means',
            '"applicable margin" means',
            "rate means",
            "margin means",
            # SOFR related (from loan_prompts_map)
            "term sofr",
            "adjusted term sofr",
            "daily simple sofr",
            "sofr rate",
            "cme term sofr",
            # Rate index references
            "rate index",
            "reference rate",
            "benchmark rate",
            # Interest type identification
            "interest rate type",
            "fixed rate",
            "floating rate",
            "variable rate",
            # Year basis / day count
            "year basis",
            "day count",
            "actual/360",
            "actual/365",
            "360 day year",
            "365 day year",
            # Typical spread values
            "0.25%",
            "0.50%",
            "0.75%",
            "1.00%",
            "1.25%",
            "1.50%",
            "2.00%",
            "2.25%",
            "2.50%",
            # Basis points
            "basis points",
            "bps",
        ],
        "max_pages": 8,  # Increased - definitions + pricing grid can span more pages
        "min_keyword_matches": 2,  # Lower threshold to catch definition pages
        "typical_pages": "within definitions section (pages 5-50)",
        "extraction_fields": [
            "base_rate",
            "spread_rate",
            "rate_index",
            "rate_calculation_method",
            "floor_rate",
            "pricing_tiers",
            "interest_rate_type",
            "year_basis",
        ],
    },
    "facilityTerms": {
        "name": "Facility Terms & Commitments",
        # Specific dollar amounts and commitment keywords - enhanced from loan_prompts_map
        "keywords": [
            # Aggregate/Total amounts (primary extraction targets)
            "aggregate maximum revolving",
            "aggregate elected revolving",
            "total commitment",
            "total revolving credit",
            "maximum credit amount",
            "aggregate commitment",
            "facility amount",
            "credit facility",
            # Specific facility types
            "lc commitment",
            "letter of credit commitment",
            "lc sublimit",
            "letter of credit sublimit",
            "swingline sublimit",
            "swingline commitment",
            "swing line",
            "term loan commitment",
            "delayed draw",
            "incremental facility",
            "accordion",
            # Schedule references where amounts are defined
            "schedule 1.01",
            "schedule 2.01",
            "schedule of commitments",
            # Dollar amount patterns
            "$900,000,000",
            "$800,000,000",
            "$700,000,000",
            "$600,000,000",
            "$500,000,000",
            "$400,000,000",
            "$300,000,000",
            "$200,000,000",
            "$100,000,000",
            "$50,000,000",
            "$25,000,000",
            # Key dates (from loan_prompts_map)
            "maturity date",
            "termination date",
            "effective date",
            "closing date",
            # Loan identifiers
            "instrument type",
            "loan type",
            "product type",
            # Borrower/Agent identification
            "borrower",
            "administrative agent",
            "collateral agent",
        ],
        "max_pages": 10,  # Increased - facility terms can span cover page + multiple sections
        "min_keyword_matches": 2,
        "typical_pages": "article II and Schedules",
        "extraction_fields": [
            "aggregate_max_revolving_credit",
            "aggregate_elected_revolving_commitment",
            "lc_commitment",
            "lc_sublimit",
            "swingline_sublimit",
            "term_loan_commitment",
            "maturity_date",
            "effective_date",
            "instrument_type",
        ],
    },
    "lenderCommitments": {
        "name": "Lender Schedule (Schedule 2.01)",
        # Very specific keywords for lender schedule - expanded for variations
        "keywords": [
            # Schedule references - various numbering schemes
            "schedule 2.01",
            "schedule 1.01",
            "schedule i",
            "schedule ii",
            "schedule of commitments",
            "commitment schedule",
            "lender schedule",
            "exhibit a",
            "annex a",
            # Column headers in commitment tables
            "applicable percentage",
            "pro rata share",
            "ratable portion",
            "commitment percentage",
            # Commitment types
            "revolving credit commitment",
            "revolving loan commitment",
            "term loan commitment",
            "total commitment",
            "aggregate commitment",
            # Percentage totals (common in lender tables)
            "100.000000%",
            "100.00%",
            "100%",
            # Common lenders (helps identify lender tables)
            "wells fargo bank",
            "bank of america",
            "jpmorgan chase",
            "citibank",
            "goldman sachs",
            "morgan stanley",
            "barclays",
            "credit suisse",
            "deutsche bank",
            "ubs",
            # Dollar amounts common in commitment tables
            "$",
            "commitment amount",
        ],
        "max_pages": 10,  # Increased - lender tables can span multiple pages
        "min_keyword_matches": 2,
        "typical_pages": "Schedules section near end of document",
        "search_schedule_pages": True,  # Flag to search Schedule pages specifically
        "extraction_fields": [
            "lender_name",
            "applicable_percentage",
            "revolving_credit_commitment",
            "term_commitment",
        ],
    },
    "covenants": {
        "name": "Financial Covenants",
        # Specific covenant terms
        "keywords": [
            "fixed charge coverage ratio",  # Primary covenant we extract
            "fccr",  # Abbreviation
            "1.15:1.00",  # Typical covenant ratio
            "1.10:1.00",
            "1.00:1.00",
            "minimum fixed charge",
            "leverage ratio",
            "debt to ebitda",
        ],
        "max_pages": 3,  # Covenants are typically 1-2 pages
        "min_keyword_matches": 2,
        "typical_pages": "articles VI-VII",
        "extraction_fields": [
            "fixed_charge_coverage_ratio_minimum",
            "leverage_ratio",
            "test_period",
        ],
    },
    "fees": {
        "name": "Fees",
        # Fee-specific keywords with percentages
        "keywords": [
            "commitment fee",  # Field we extract
            "fronting fee",  # Field we extract
            "0.125%",  # Typical fronting fee
            "0.20%",  # Typical commitment fee
            "0.25%",  # Typical fee rate
            "letter of credit fee",
            "agency fee",
        ],
        "max_pages": 2,  # Fee section is typically 1 page
        "min_keyword_matches": 2,
        "typical_pages": "article II or separate section",
        "extraction_fields": [
            "commitment_fee_rate",
            "lc_fee_rate",
            "fronting_fee_rate",
            "agency_fee",
        ],
    },
}

# Document type definitions with keywords for classification
DOCUMENT_TYPES = {
    # Credit Agreement Documents
    "credit_agreement": {
        "name": "Credit Agreement",
        "keywords": [
            "credit agreement",
            "revolving credit",
            "term loan",
            "borrowing base",
            "administrative agent",
            "lender commitment",
            "applicable rate",
            "maturity date",
            "interest period",
            "lc commitment",
            "letters of credit",
            "unused revolving credit commitment",
            "lead arranger",
            "guarantor",
        ],
        "has_sections": True,  # Flag to indicate this doc type has section breakdown
    },
    # Mortgage Documents
    "promissory_note": {
        "name": "Promissory Note",
        "keywords": [
            "promissory note",
            "note",
            "promise to pay",
            "principal amount",
            "interest rate",
            "monthly payment",
            "maturity date",
            "borrower agrees to pay",
        ],
    },
    "closing_disclosure": {
        "name": "Closing Disclosure",
        "keywords": [
            "closing disclosure",
            "loan terms",
            "projected payments",
            "closing costs",
            "cash to close",
            "loan estimate",
            "trid",
            "cfpb",
        ],
    },
    "form_1003": {
        "name": "Uniform Residential Loan Application (Form 1003)",
        "keywords": [
            "uniform residential loan application",
            "form 1003",
            "urla",
            "borrower information",
            "employment information",
            "assets and liabilities",
            "declarations",
        ],
    },
    "deed_of_trust": {
        "name": "Deed of Trust",
        "keywords": [
            "deed of trust",
            "security instrument",
            "trustee",
            "beneficiary",
            "grantor",
            "property description",
            "legal description",
        ],
    },
    # Financial Documents
    "bank_statement": {
        "name": "Bank Statement",
        "keywords": [
            "bank statement",
            "account statement",
            "checking account",
            "savings account",
            "beginning balance",
            "ending balance",
        ],
    },
    "pay_stub": {
        "name": "Pay Stub",
        "keywords": [
            "pay stub",
            "earnings statement",
            "gross pay",
            "net pay",
            "ytd",
            "deductions",
            "federal withholding",
        ],
    },
    # Tax Documents
    "w2": {
        "name": "W-2 Form",
        "keywords": [
            "w-2",
            "w2",
            "wage and tax statement",
            "federal income tax withheld",
            "social security wages",
            "employer identification number",
        ],
    },
    "tax_return_1040": {
        "name": "Tax Return (Form 1040)",
        "keywords": [
            "form 1040",
            "tax return",
            "adjusted gross income",
            "taxable income",
            "total tax",
            "irs",
        ],
    },
    # Legal Documents
    "power_of_attorney": {
        "name": "Power of Attorney",
        "keywords": [
            "power of attorney",
            "poa",
            "attorney-in-fact",
            "principal",
            "durable power",
        ],
    },
    # Insurance Documents
    "homeowners_insurance": {
        "name": "Homeowners Insurance Policy",
        "keywords": [
            "homeowners insurance",
            "dwelling coverage",
            "liability coverage",
            "declarations page",
            "premium",
            "deductible",
        ],
    },
}


def extract_page_snippets(pdf_stream: io.BytesIO) -> list[dict[str, Any]]:
    """Extract text snippets from each page of the PDF.

    Args:
        pdf_stream: BytesIO stream containing the PDF

    Returns:
        List of dicts with page number and text snippet
    """
    reader = PdfReader(pdf_stream)
    page_snippets = []

    for i, page in enumerate(reader.pages):
        try:
            # Extract text (PyPDF is fast for text extraction)
            text = page.extract_text() or ""

            # Take only the first N characters for classification
            snippet = text[:MAX_CHARS_PER_PAGE].strip()

            page_snippets.append(
                {
                    "page_number": i + 1,  # 1-indexed for human readability
                    "snippet": snippet,
                    "has_text": len(snippet) > 50,  # Flag if page has meaningful text
                }
            )
        except Exception as e:
            print(f"Error extracting page {i + 1}: {str(e)}")
            page_snippets.append(
                {
                    "page_number": i + 1,
                    "snippet": "",
                    "has_text": False,
                    "error": str(e),
                }
            )

    return page_snippets


def identify_credit_agreement_sections(
    page_snippets: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """Identify Credit Agreement sections using intelligent keyword density scoring.

    COST-OPTIMIZED APPROACH:
    - Score each page by keyword density (matches / total keywords)
    - Select only TOP N pages per section (not all pages above threshold)
    - Use specific header detection for Schedule pages
    - Strict page limits to minimize Textract costs

    Args:
        page_snippets: List of page snippets from extract_page_snippets

    Returns:
        Dict mapping section names to lists of candidate page numbers
    """
    # Page limits per section (strict limits for cost control)
    SECTION_PAGE_LIMITS = {
        "agreementInfo": 5,      # First 5 pages only
        "applicableRates": 5,    # Pricing grid + definitions
        "facilityTerms": 5,      # Commitment amounts
        "lenderCommitments": 5,  # Schedule with lender table
        "covenants": 3,          # Financial covenants
        "fees": 3,               # Fee section
        "definitions": 10,       # Key definitions (business day, interest period, maturity, LC, etc.)
    }

    section_pages: dict[str, list[int]] = {
        section: [] for section in CREDIT_AGREEMENT_SECTIONS
    }

    total_pages = len(page_snippets)

    # SPECIAL CASE: agreementInfo is ALWAYS first 5 pages
    section_pages["agreementInfo"] = list(range(1, min(6, total_pages + 1)))

    # Score all pages for each section using keyword density
    section_scores: dict[str, list[tuple[int, float, int]]] = {
        section: [] for section in CREDIT_AGREEMENT_SECTIONS
    }

    # High-value Schedule indicators (strong signals for lenderCommitments)
    SCHEDULE_HEADERS = [
        "schedule 2.01",
        "schedule 1.01",
        "schedule of commitments",
        "commitment schedule",
        "lender schedule",
        "schedule i",
        "commitments and applicable percentages",
    ]

    # Table indicators ($ amounts + percentages = likely commitment table)
    TABLE_PATTERNS = [
        "100.00%",
        "100.000000%",
        "applicable percentage",
        "pro rata share",
    ]

    for page in page_snippets:
        if not page["has_text"]:
            continue

        page_num = page["page_number"]
        text_lower = page["snippet"].lower()

        for section_id, section_info in CREDIT_AGREEMENT_SECTIONS.items():
            # Skip agreementInfo (always first 5 pages)
            if section_id == "agreementInfo":
                continue

            keywords = section_info.get("keywords", [])
            if not keywords:
                continue

            # Count keyword matches
            matches = sum(1 for kw in keywords if kw.lower() in text_lower)

            # For lenderCommitments, give BONUS points for Schedule headers
            bonus = 0
            if section_id == "lenderCommitments":
                # Strong bonus for explicit Schedule headers
                for header in SCHEDULE_HEADERS:
                    if header in text_lower:
                        bonus += 10  # Strong signal
                        break

                # Bonus for table patterns (percentages totaling 100%)
                for pattern in TABLE_PATTERNS:
                    if pattern in text_lower:
                        bonus += 5
                        break

                # Bonus for having both lender name patterns and $ amounts
                has_dollar = "$" in text_lower
                has_bank = any(bank in text_lower for bank in [
                    "bank", "capital", "chase", "wells fargo", "citibank"
                ])
                if has_dollar and has_bank:
                    bonus += 3

            # Calculate score (matches + bonus)
            score = matches + bonus

            # Only consider pages with meaningful matches
            min_matches = section_info.get("min_keyword_matches", 2)
            if score >= min_matches:
                section_scores[section_id].append((page_num, score, matches))

    # Select TOP N pages per section by score
    for section_id, scores in section_scores.items():
        if not scores:
            continue

        # Sort by score (descending), then by page number (ascending for ties)
        scores.sort(key=lambda x: (-x[1], x[0]))

        # Get page limit for this section
        limit = SECTION_PAGE_LIMITS.get(section_id, 5)

        # Select top pages
        top_pages = [page_num for page_num, score, matches in scores[:limit]]
        section_pages[section_id] = sorted(top_pages)

        # Log selection for debugging
        if top_pages:
            top_3 = scores[:3]
            print(f"Section '{section_id}': Selected {len(top_pages)} pages. "
                  f"Top scores: {[(p, s) for p, s, m in top_3]}")

    return section_pages


def classify_credit_agreement_with_bedrock(
    page_snippets: list[dict[str, Any]],
    candidate_sections: dict[str, list[int]],
) -> dict[str, Any]:
    """Use Claude Haiku to refine Credit Agreement section identification.

    Args:
        page_snippets: List of page snippets from extract_page_snippets
        candidate_sections: Pre-identified candidate pages per section

    Returns:
        Dict with refined section page ranges and classification metadata
    """
    # Filter to only pages with text
    text_pages = [p for p in page_snippets if p["has_text"]]

    # Build section descriptions for the prompt
    section_descriptions = []
    for section_id, section_info in CREDIT_AGREEMENT_SECTIONS.items():
        candidates = candidate_sections.get(section_id, [])
        candidate_str = f"Candidate pages: {candidates}" if candidates else "No candidates found"
        section_descriptions.append(
            f"- **{section_id}**: {section_info['name']}\n  {candidate_str}"
        )

    sections_text = "\n".join(section_descriptions)

    # COST-OPTIMIZED: Only include candidate pages identified by keyword scoring
    # No wasteful page range expansion - trust the intelligent page selection
    all_candidate_pages = set()
    for pages in candidate_sections.values():
        all_candidate_pages.update(pages)

    # Always include first 5 pages for context (agreement info)
    all_candidate_pages.update(range(1, min(6, len(text_pages) + 1)))

    print(f"LLM will analyze {len(all_candidate_pages)} candidate pages (vs {len(text_pages)} total)")

    # Format relevant pages for the prompt
    relevant_pages = [p for p in text_pages if p["page_number"] in all_candidate_pages]
    formatted_pages = "\n\n".join(
        [f"=== PAGE {p['page_number']} ===\n{p['snippet']}" for p in relevant_pages]
    )

    prompt = f"""You are a legal document analyzer specializing in Credit Agreements and syndicated loan documents.

Analyze the following page snippets from a Credit Agreement document. Your task is to identify the page numbers containing each of these sections:

{sections_text}

RELEVANT PAGE SNIPPETS:
{formatted_pages}

IMPORTANT RULES (COST-OPTIMIZED):
- Return ONLY the MOST RELEVANT pages for each section (max 3-5 pages per section)
- Prioritize pages with the highest information density for each section
- If a section is not found, return an empty array []
- Quality over quantity - fewer high-value pages is better than many low-value pages

SECTION-SPECIFIC GUIDANCE:
- **lenderCommitments**: Look for the ACTUAL Schedule page with the lender commitment table (usually 1-2 pages). Key indicators: "Schedule 2.01", column headers like "Lender", "Revolving Loan Commitment", "Applicable Percentage", percentages totaling 100%.
- **applicableRates**: Find the page with the pricing grid/tier table (Level I, II, III) and the "Applicable Rate" definition. Usually 2-3 pages.
- **facilityTerms**: Find pages with aggregate commitment amounts ($X million), maturity date. Usually 2-3 pages.
- **agreementInfo**: First 5 pages - document title, parties, effective date.
- **covenants**: Find the specific covenant ratio requirements (FCCR, leverage ratio). Usually 1-2 pages.
- **fees**: Find the fee schedule (commitment fee, LC fee rates). Usually 1-2 pages.

Respond with ONLY valid JSON in this exact format:
{{
  "sections": {{
    "agreementInfo": [<page numbers>],
    "definitions": [<page numbers>],
    "applicableRates": [<page numbers>],
    "facilityTerms": [<page numbers>],
    "lenderCommitments": [<page numbers>],
    "covenants": [<page numbers>],
    "fees": [<page numbers>]
  }},
  "documentSubtype": "syndicated_loan" | "abl_facility" | "term_loan" | "mixed",
  "confidence": "high" | "medium" | "low",
  "notes": "<any relevant observations about the document structure>"
}}"""

    # Call Bedrock
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )

    # Parse response
    response_body = json.loads(response["body"].read())
    content = response_body["content"][0]["text"]

    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())
    except json.JSONDecodeError as e:
        print(f"Error parsing Credit Agreement section response: {content}")
        # Fall back to candidate sections
        return {
            "sections": candidate_sections,
            "documentSubtype": "unknown",
            "confidence": "low",
            "notes": f"Failed to parse LLM response: {str(e)}",
        }


def classify_pages_with_bedrock(
    page_snippets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Use Claude Haiku to classify pages and identify document types.

    Args:
        page_snippets: List of page snippets from extract_page_snippets

    Returns:
        Dict mapping document type to page number and classification metadata
    """
    # Filter to only pages with text
    text_pages = [p for p in page_snippets if p["has_text"]]

    # Format pages for the prompt
    formatted_pages = "\n\n".join(
        [f"=== PAGE {p['page_number']} ===\n{p['snippet']}" for p in text_pages]
    )

    # Build document type descriptions for the prompt
    doc_type_descriptions = []
    for type_id, type_info in DOCUMENT_TYPES.items():
        keywords = ", ".join(type_info["keywords"][:5])
        doc_type_descriptions.append(
            f"- **{type_id}**: {type_info['name']}\n  Keywords: {keywords}"
        )

    doc_types_text = "\n".join(doc_type_descriptions)

    prompt = f"""You are a financial document classifier specializing in loan packages and financial documents.

Analyze the following page snippets from a document package. Your task is to identify the FIRST page number where each of these document types begins:

{doc_types_text}

PAGE SNIPPETS:
{formatted_pages}

IMPORTANT RULES:
- Return ONLY the page number where each document STARTS
- If a document type is not found, use null
- Be conservative - only identify if you're confident
- A document may span multiple pages; return only the first page
- Focus on the most common financial documents first

Respond with ONLY valid JSON in this exact format:
{{
  "credit_agreement": <page_number or null>,
  "promissory_note": <page_number or null>,
  "closing_disclosure": <page_number or null>,
  "form_1003": <page_number or null>,
  "deed_of_trust": <page_number or null>,
  "bank_statement": <page_number or null>,
  "pay_stub": <page_number or null>,
  "w2": <page_number or null>,
  "tax_return_1040": <page_number or null>,
  "power_of_attorney": <page_number or null>,
  "homeowners_insurance": <page_number or null>,
  "primary_document_type": "<most important document type found>",
  "confidence": "high" | "medium" | "low",
  "totalPagesAnalyzed": <number>
}}"""

    # Call Bedrock
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0,  # Deterministic for classification
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )

    # Parse response
    response_body = json.loads(response["body"].read())
    content = response_body["content"][0]["text"]

    # Extract JSON from response
    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        classification = json.loads(content.strip())

        # Add legacy keys for backward compatibility with existing Step Functions
        classification["promissoryNote"] = classification.get("promissory_note")
        classification["closingDisclosure"] = classification.get("closing_disclosure")
        classification["form1003"] = classification.get("form_1003")

        return classification
    except json.JSONDecodeError as e:
        print(f"Error parsing classification response: {content}")
        raise ValueError(f"Failed to parse Bedrock response: {str(e)}")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main Lambda handler for document classification.

    Args:
        event: Input event containing documentId, bucket, key, and contentHash
        context: Lambda context

    Returns:
        Dict with classification results and metadata for next steps
    """
    print(f"Router Lambda received event: {json.dumps(event)}")

    # Extract input parameters
    document_id = event["documentId"]
    bucket = event.get("bucket", BUCKET_NAME)
    key = event["key"]
    content_hash = event.get("contentHash")  # Pass through for deduplication
    file_size = event.get("size")
    uploaded_at = event.get("uploadedAt")

    print(f"Processing document: {document_id} from s3://{bucket}/{key}")
    if content_hash:
        print(f"Content hash: {content_hash[:16]}...")

    try:
        # 1. Download PDF from S3 as stream
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        pdf_stream = io.BytesIO(s3_response["Body"].read())

        # 2. Extract page snippets (fast, no OCR)
        print("Extracting page snippets...")
        page_snippets = extract_page_snippets(pdf_stream)
        total_pages = len(page_snippets)
        print(f"Extracted snippets from {total_pages} pages")

        # 3. Classify pages using Bedrock
        print("Classifying pages with Claude Haiku...")
        classification = classify_pages_with_bedrock(page_snippets)
        print(f"Classification result: {json.dumps(classification)}")

        # Count identified documents
        identified_docs = [
            doc_type
            for doc_type in DOCUMENT_TYPES.keys()
            if classification.get(doc_type) is not None
        ]

        # 4. If Credit Agreement detected, identify sections with page ranges
        credit_agreement_sections = None
        if classification.get("credit_agreement") is not None:
            print("Credit Agreement detected - identifying sections...")

            # Fast keyword-based pre-pass
            candidate_sections = identify_credit_agreement_sections(page_snippets)
            print(f"Candidate sections from keyword matching: {json.dumps(candidate_sections)}")

            # LLM-refined section identification
            credit_agreement_sections = classify_credit_agreement_with_bedrock(
                page_snippets, candidate_sections
            )
            print(f"Refined Credit Agreement sections: {json.dumps(credit_agreement_sections)}")

        # 5. Prepare output for Step Functions
        # Pass through contentHash for the normalizer to save to DynamoDB
        result = {
            "documentId": document_id,
            "bucket": bucket,
            "key": key,
            "contentHash": content_hash,  # Pass through for deduplication
            "size": file_size,
            "uploadedAt": uploaded_at,
            "totalPages": total_pages,
            "classification": classification,
            "identifiedDocuments": identified_docs,
            "status": "CLASSIFIED",
            "metadata": {
                "routerModel": BEDROCK_MODEL_ID,
                "pagesWithText": len([p for p in page_snippets if p["has_text"]]),
                "documentTypesFound": len(identified_docs),
                "primaryDocumentType": classification.get("primary_document_type"),
                "classificationConfidence": classification.get("confidence", "unknown"),
                "costEstimate": {
                    "classificationTokens": total_pages * 150,  # Rough estimate
                    "targetedPages": len(identified_docs),
                },
            },
        }

        # Add Credit Agreement section details if detected
        if credit_agreement_sections:
            result["creditAgreementSections"] = credit_agreement_sections
            # Calculate targeted pages for cost estimate
            all_section_pages = set()
            for pages in credit_agreement_sections.get("sections", {}).values():
                all_section_pages.update(pages)
            result["metadata"]["creditAgreementTargetedPages"] = len(all_section_pages)
            result["metadata"]["creditAgreementSubtype"] = credit_agreement_sections.get(
                "documentSubtype", "unknown"
            )

        # Update DynamoDB status to CLASSIFIED for progress tracking
        # Note: Table has composite key (documentId + documentType), so we query first
        try:
            table = dynamodb.Table(TABLE_NAME)
            from boto3.dynamodb.conditions import Key as DynamoKey

            # Query to find the existing PROCESSING record
            query_result = table.query(
                KeyConditionExpression=DynamoKey("documentId").eq(document_id),
                Limit=1,
            )

            if query_result.get("Items"):
                existing_doc_type = query_result["Items"][0].get("documentType", "PROCESSING")

                table.update_item(
                    Key={"documentId": document_id, "documentType": existing_doc_type},
                    UpdateExpression="SET #status = :status, updatedAt = :updatedAt, totalPages = :totalPages",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": "CLASSIFIED",
                        ":updatedAt": datetime.utcnow().isoformat() + "Z",
                        ":totalPages": total_pages,
                    },
                )
                print(f"Updated DynamoDB status to CLASSIFIED for document: {document_id}")
            else:
                print(f"Warning: No existing record found for document: {document_id}")
        except Exception as db_err:
            print(f"Warning: Failed to update DynamoDB status: {str(db_err)}")
            # Continue even if status update fails - main processing succeeded

        return result

    except Exception as e:
        print(f"Error in Router Lambda: {str(e)}")
        raise
