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

import datetime
import io
import json
import os
import re
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

# Loan Agreement section definitions for targeted extraction
# Simple business/personal loans have fewer sections than Credit Agreements
# Keywords derived from loan_prompts_map field specifications
LOAN_AGREEMENT_SECTIONS = {
    "loanTerms": {
        "name": "Loan Terms & Principal",
        "keywords": [
            # Loan amount / Principal
            "loan amount",
            "principal amount",
            "principal sum",
            "credit limit",
            "maximum amount",
            "commitment amount",
            # Interest rate
            "interest rate",
            "annual percentage rate",
            "apr",
            "per annum",
            "rate of interest",
            # Maturity / Term
            "maturity date",
            "due date",
            "term of loan",
            "loan term",
            "termination date",
            "final payment date",
            "payable in full",
            # Loan type
            "term loan",
            "line of credit",
            "revolving",
            "demand note",
            # Dollar amount patterns
            "$",
        ],
        "max_pages": 5,
        "min_keyword_matches": 3,
        "typical_pages": "first few pages with loan terms",
        "extraction_fields": [
            "loan_amount",
            "credit_limit",
            "interest_rate",
            "maturity_date",
            "loan_term_months",
        ],
    },
    "interestDetails": {
        "name": "Interest Rate Details",
        "keywords": [
            # Rate type
            "fixed rate",
            "variable rate",
            "floating rate",
            "adjustable rate",
            # Index rates
            "prime rate",
            "wall street journal prime",
            "sofr",
            "libor",
            "federal funds",
            # Margin / Spread
            "margin",
            "spread",
            "plus",
            "above prime",
            "above sofr",
            "basis points",
            # Floor / Ceiling
            "floor",
            "ceiling",
            "cap",
            "minimum rate",
            "maximum rate",
            # Day count
            "day count",
            "360 day",
            "365 day",
            "actual/360",
            "actual/365",
            # Default rate
            "default rate",
            "default interest",
        ],
        "max_pages": 3,
        "min_keyword_matches": 2,
        "typical_pages": "interest rate section",
        "extraction_fields": [
            "rate_type",
            "index_rate",
            "margin",
            "floor",
            "ceiling",
            "day_count_basis",
        ],
    },
    "paymentInfo": {
        "name": "Payment Schedule",
        "keywords": [
            # Payment amount
            "payment amount",
            "monthly payment",
            "installment",
            "periodic payment",
            "minimum payment",
            # Payment schedule
            "payment schedule",
            "repayment",
            "amortization",
            "interest only",
            "principal and interest",
            # Payment frequency
            "monthly",
            "quarterly",
            "annually",
            "on demand",
            "payment frequency",
            # Payment dates
            "first payment",
            "payment due",
            "due date",
            "payment day",
            "beginning",
            "commencing",
            # Balloon
            "balloon payment",
            "balloon",
            "final payment",
        ],
        "max_pages": 3,
        "min_keyword_matches": 2,
        "typical_pages": "payment terms section",
        "extraction_fields": [
            "monthly_payment",
            "first_payment_date",
            "payment_frequency",
            "number_of_payments",
            "balloon_payment",
        ],
    },
    "parties": {
        "name": "Parties & Addresses",
        "keywords": [
            # Borrower
            "borrower",
            "debtor",
            "maker",
            "obligor",
            "company",
            # Lender
            "lender",
            "bank",
            "creditor",
            "holder",
            "payee",
            # Guarantor
            "guarantor",
            "guarantee",
            "personal guarantee",
            "jointly and severally",
            # Address indicators
            "address",
            "principal place of business",
            "located at",
            "organized under",
            "jurisdiction",
            # Common entity types
            "inc",
            "llc",
            "corporation",
            "limited liability",
        ],
        "max_pages": 3,
        "min_keyword_matches": 2,
        "typical_pages": "first pages with party definitions",
        "extraction_fields": [
            "borrower_name",
            "borrower_address",
            "lender_name",
            "guarantor_name",
        ],
    },
    "security": {
        "name": "Security & Collateral",
        "keywords": [
            # Security interest
            "security interest",
            "security agreement",
            "secured by",
            "collateral",
            "pledge",
            # UCC
            "ucc",
            "uniform commercial code",
            "financing statement",
            # Asset types
            "equipment",
            "inventory",
            "accounts receivable",
            "real property",
            "personal property",
            # Lien
            "lien",
            "first lien",
            "senior lien",
            "subordinate",
        ],
        "max_pages": 3,
        "min_keyword_matches": 2,
        "typical_pages": "security/collateral section",
        "extraction_fields": [
            "is_secured",
            "collateral_description",
            "property_address",
        ],
    },
    "fees": {
        "name": "Fees & Charges",
        "keywords": [
            # Fee types
            "origination fee",
            "loan fee",
            "commitment fee",
            "closing cost",
            "prepayment penalty",
            "prepayment fee",
            "late fee",
            "late charge",
            "late payment",
            "grace period",
            "annual fee",
            # Percentage patterns
            "%",
            "percent",
        ],
        "max_pages": 2,
        "min_keyword_matches": 2,
        "typical_pages": "fee schedule",
        "extraction_fields": [
            "origination_fee",
            "late_payment_fee",
            "grace_period_days",
            "prepayment_penalty",
        ],
    },
    "signatures": {
        "name": "Signatures",
        "keywords": [
            # Signature indicators
            "signature",
            "signed",
            "executed",
            "witness",
            "notary",
            "acknowledged",
            "sworn",
            "in witness whereof",
            "intending to be legally bound",
            "duly authorized",
            # Date of execution
            "dated as of",
            "effective as of",
            # Signature blocks
            "by:",
            "name:",
            "title:",
            "date:",
        ],
        "max_pages": 3,
        "min_keyword_matches": 3,
        "search_last_pages": True,  # Flag to prioritize last pages
        "typical_pages": "last pages with signatures",
        "extraction_fields": [
            "signature_detected",
            "execution_date",
        ],
    },
}


# Document type definitions with keywords for classification
DOCUMENT_TYPES = {
    # Credit Agreement Documents (Complex syndicated facilities)
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
            # Syndicated loan indicators
            "syndicated",
            "syndication",
            "multiple lenders",
            "pro rata share",
            "commitment schedule",
        ],
        "has_sections": True,  # Flag to indicate this doc type has section breakdown
    },
    # Simple Loan Agreement (Business loans, personal loans - NOT syndicated)
    "loan_agreement": {
        "name": "Loan Agreement",
        "keywords": [
            "loan agreement",
            "business loan",
            "commercial loan",
            "promissory note",
            "borrower",
            "lender",
            "principal amount",
            "interest rate",
            "maturity date",
            "repayment",
            "monthly payment",
            "collateral",
            "security agreement",
            "default",
            "loan amount",
            "term loan",
            "line of credit",
            "note date",
            "promise to pay",
            "due date",
            "payment schedule",
        ],
        "has_sections": False,  # Simpler structure - extract all pages
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


# ==========================================
# Plugin-Driven Classification Functions
# ==========================================


def _evaluate_bonus_rule(
    rule: dict[str, Any],
    page_text: str,
    page_index: int,
    total_pages: int,
) -> int:
    """Evaluate a PageBonusRule from plugin config against a page.

    Returns the bonus score if the condition matches, else 0.
    """
    condition = rule.get("condition", "")
    patterns = rule.get("patterns", [])
    bonus = rule.get("bonus", 0)

    if condition == "contains_any":
        for pattern in patterns:
            if pattern.lower() in page_text:
                return bonus
        return 0
    elif condition == "contains_all":
        for pattern in patterns:
            if pattern.lower() not in page_text:
                return 0
        return bonus
    elif condition == "first_n_pages":
        n = int(patterns[0]) if patterns and patterns[0].isdigit() else 5
        return bonus if page_index < n else 0
    elif condition == "last_n_pages":
        n = int(patterns[0]) if patterns and patterns[0].isdigit() else 3
        return bonus if page_index >= total_pages - n else 0
    elif condition == "regex_match":
        for pattern in patterns:
            try:
                if re.search(pattern, page_text, re.IGNORECASE):
                    return bonus
            except re.error:
                continue
        return 0
    return 0


def build_classification_prompt(
    page_snippets: list[dict[str, Any]],
    all_plugins: dict[str, Any],
) -> str:
    """Build a dynamic Bedrock classification prompt from all registered plugins."""
    text_pages = [p for p in page_snippets if p["has_text"]]
    formatted_pages = "\n\n".join(
        [f"=== PAGE {p['page_number']} ===\n{p['snippet']}" for p in text_pages]
    )

    doc_type_blocks = []
    distinguishing_rules = []
    response_keys = []

    for plugin_id, plugin_config in all_plugins.items():
        classification = plugin_config.get("classification", {})
        keywords = classification.get("keywords", [])
        name = plugin_config.get("name", plugin_id)
        description = plugin_config.get("description", "")
        keyword_sample = ", ".join(keywords[:8])
        doc_type_blocks.append(
            f"- **{plugin_id}**: {name}\n  Description: {description}\n  Keywords: {keyword_sample}"
        )
        for rule in classification.get("distinguishing_rules", []):
            distinguishing_rules.append(f"- **{plugin_id}**: {rule}")
        if classification.get("section_names"):
            for section_name in classification["section_names"]:
                response_keys.append(f'    "{section_name}": <page_number or null>')
        else:
            response_keys.append(f'    "{plugin_id}": <page_number or null>')

    doc_types_text = "\n".join(doc_type_blocks)
    response_keys_text = ",\n".join(response_keys)
    distinguishing_section = ""
    if distinguishing_rules:
        distinguishing_section = (
            "\n\nCRITICAL DISTINCTIONS BETWEEN DOCUMENT TYPES:\n"
            + "\n".join(distinguishing_rules)
        )

    return f"""You are a financial document classifier specializing in loan packages and financial documents.

Analyze the following page snippets. Identify the FIRST page number where each document type begins:

{doc_types_text}
{distinguishing_section}

PAGE SNIPPETS:
{formatted_pages}

IMPORTANT RULES:
- Return ONLY the page number where each document STARTS
- If a document type is not found, use null
- Be conservative - only identify if you're confident
- A document may span multiple pages; return only the first page

Respond with ONLY valid JSON:
{{
{response_keys_text},
    "primary_document_type": "<most important document type found>",
    "confidence": "high" | "medium" | "low",
    "totalPagesAnalyzed": {len(text_pages)}
}}"""


def identify_sections_generic(
    page_snippets: list[dict[str, Any]],
    plugin: dict[str, Any],
    page_count: int,
) -> dict[str, list[int]]:
    """Generic section identification using keyword density scoring from plugin config."""
    sections_config = plugin.get("sections", {})
    section_pages: dict[str, list[int]] = {sid: [] for sid in sections_config}
    section_scores: dict[str, list[tuple[int, float, int]]] = {sid: [] for sid in sections_config}
    total_pages = len(page_snippets)

    for page in page_snippets:
        if not page["has_text"]:
            continue
        page_num = page["page_number"]
        page_index = page_num - 1
        text_lower = page["snippet"].lower()

        for section_id, section_config in sections_config.items():
            hints = section_config.get("classification_hints", {})
            keywords = hints.get("keywords", [])

            if not keywords:
                max_p = hints.get("max_pages", section_config.get("max_pages", 5))
                if page_num <= max_p:
                    section_pages[section_id].append(page_num)
                continue

            matches = sum(1 for kw in keywords if kw.lower() in text_lower)
            bonus = sum(
                _evaluate_bonus_rule(rule, text_lower, page_index, total_pages)
                for rule in hints.get("page_bonus_rules", [])
            )
            score = matches + bonus
            min_matches = hints.get("min_keyword_matches", 2)
            if score >= min_matches:
                section_scores[section_id].append((page_num, score, matches))

    for section_id, scores in section_scores.items():
        if not scores:
            continue
        scores.sort(key=lambda x: (-x[1], x[0]))
        section_config = sections_config[section_id]
        limit = section_config.get("classification_hints", {}).get(
            "max_pages", section_config.get("max_pages", 5)
        )
        top_pages = [pn for pn, s, m in scores[:limit]]
        section_pages[section_id] = sorted(top_pages)

    return section_pages


def build_extraction_plan(
    plugin: dict[str, Any],
    classification_result: dict[str, Any],
    page_snippets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the extraction plan array that Step Functions Map state iterates over."""
    plugin_id = plugin["plugin_id"]
    sections_config = plugin.get("sections", {})
    classification = plugin.get("classification", {})
    total_pages = len(page_snippets)
    extraction_sections = []

    if classification.get("target_all_pages"):
        all_pages = list(range(1, total_pages + 1))
        for section_id, section_config in sections_config.items():
            max_p = section_config.get("max_pages", total_pages)
            extraction_sections.append({
                "sectionId": section_id,
                "sectionPages": all_pages[:max_p],
                "sectionConfig": section_config,
                "pluginId": plugin_id,
                "textractFeatures": section_config.get("textract_features", ["QUERIES"]),
                "queries": section_config.get("queries", []),
            })
    elif classification.get("section_names"):
        starts = []
        for section_name in classification["section_names"]:
            start = classification_result.get(section_name)
            if start is not None:
                starts.append((section_name, int(start)))
        starts.sort(key=lambda x: x[1])
        for i, (sname, start_page) in enumerate(starts):
            if sname not in sections_config:
                continue
            sc = sections_config[sname]
            max_p = sc.get("max_pages", 10)
            end = starts[i + 1][1] - 1 if i + 1 < len(starts) else total_pages
            end = min(end, start_page + max_p - 1)
            extraction_sections.append({
                "sectionId": sname,
                "sectionPages": list(range(start_page, end + 1)),
                "sectionConfig": sc,
                "pluginId": plugin_id,
                "textractFeatures": sc.get("textract_features", ["QUERIES"]),
                "queries": sc.get("queries", []),
            })
    else:
        identified = classification_result.get("sections", {})
        for section_id, sc in sections_config.items():
            pages = identified.get(section_id, [])
            if not pages:
                continue
            extraction_sections.append({
                "sectionId": section_id,
                "sectionPages": sorted(pages),
                "sectionConfig": sc,
                "pluginId": plugin_id,
                "textractFeatures": sc.get("textract_features", ["QUERIES"]),
                "queries": sc.get("queries", []),
            })

    return extraction_sections


def _resolve_plugin(
    classification_result: dict[str, Any],
    all_plugins: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve which plugin handles this document based on LLM classification."""
    primary_type = classification_result.get("primary_document_type", "").lower()

    if primary_type in all_plugins:
        return all_plugins[primary_type]

    for plugin_id, plugin_config in all_plugins.items():
        section_names = plugin_config.get("classification", {}).get("section_names", [])
        if primary_type in section_names:
            return plugin_config

    for plugin_id, plugin_config in all_plugins.items():
        legacy_map = plugin_config.get("legacy_section_map", {})
        if primary_type in legacy_map or primary_type.upper() in legacy_map:
            return plugin_config

    return None


def add_backward_compatible_keys(
    result: dict[str, Any],
    plugin_id: str,
    extraction_plan: list[dict[str, Any]],
    classification: dict[str, Any],
) -> None:
    """Add legacy output keys alongside extractionPlan for Step Functions transition."""
    if plugin_id == "credit_agreement":
        legacy_sections = {}
        for sec in extraction_plan:
            legacy_sections[sec["sectionId"]] = sec["sectionPages"]
        result["creditAgreementSections"] = {
            "sections": legacy_sections,
            "confidence": classification.get("confidence", "unknown"),
        }
    elif plugin_id == "loan_package":
        classification["promissoryNote"] = classification.get("promissory_note")
        classification["closingDisclosure"] = classification.get("closing_disclosure")
        classification["form1003"] = classification.get("form_1003")
        result["classification"] = classification
    elif plugin_id == "loan_agreement":
        legacy_sections = {}
        for sec in extraction_plan:
            legacy_sections[sec["sectionId"]] = sec["sectionPages"]
        result["loanAgreementSections"] = {"sections": legacy_sections}
        classification["loanAgreement"] = classification.get("loan_agreement")
        result["classification"] = classification


def detect_text_quality(text: str) -> dict[str, Any]:
    """Detect text quality to identify garbled/corrupt text from font encoding issues.

    PyPDF can fail to extract readable text when PDFs use custom embedded fonts,
    returning glyph indices like '/0 /1 /2 /3' instead of actual characters.

    This function detects such issues by analyzing text patterns:
    1. High ratio of non-alphanumeric characters
    2. Presence of glyph index patterns (e.g., /0 /1 /2)
    3. Lack of common English words
    4. High ratio of whitespace or special characters

    Args:
        text: Extracted text to analyze

    Returns:
        Dict with quality metrics:
        - quality_score: 0.0 (unreadable) to 1.0 (good quality)
        - is_readable: Boolean indicating if text is usable for keyword matching
        - issues: List of detected quality issues
        - metrics: Detailed metrics used for scoring
    """
    if not text or len(text.strip()) < 10:
        return {
            "quality_score": 0.0,
            "is_readable": False,
            "issues": ["insufficient_text"],
            "metrics": {"text_length": len(text) if text else 0},
        }

    issues = []
    metrics = {}

    # Metric 1: Check for glyph index patterns (e.g., /0 /1 /2 /3)
    # This is the primary indicator of font encoding failure
    glyph_pattern = r"/\d+\s*/\d+"  # Matches patterns like "/0 /1" or "/12 /34"
    glyph_matches = re.findall(glyph_pattern, text)
    glyph_ratio = len(glyph_matches) / max(1, len(text) / 10)  # Per 10 chars
    metrics["glyph_index_ratio"] = round(glyph_ratio, 3)

    if glyph_ratio > 0.05:  # More than 5% glyph patterns
        issues.append("glyph_indices_detected")

    # Metric 2: Ratio of alphanumeric characters
    # Readable text should have mostly letters, numbers, and common punctuation
    alnum_chars = sum(1 for c in text if c.isalnum())
    alnum_ratio = alnum_chars / len(text) if text else 0
    metrics["alphanumeric_ratio"] = round(alnum_ratio, 3)

    if alnum_ratio < 0.3:  # Less than 30% alphanumeric
        issues.append("low_alphanumeric_ratio")

    # Metric 3: Check for common English words (basic sanity check)
    # If text is readable, it should contain at least some common words
    common_words = [
        "the", "and", "for", "that", "this", "with", "from", "have",
        "date", "loan", "amount", "payment", "interest", "rate",
        "borrower", "lender", "agreement", "note", "shall", "will",
        "section", "article", "page", "total", "principal"
    ]
    text_lower = text.lower()
    found_words = sum(1 for word in common_words if word in text_lower)
    word_score = min(1.0, found_words / 5)  # Cap at 1.0 if 5+ words found
    metrics["common_words_found"] = found_words
    metrics["word_score"] = round(word_score, 3)

    if found_words == 0:
        issues.append("no_common_words")

    # Metric 4: Check for excessive whitespace/special characters
    space_ratio = text.count(" ") / len(text) if text else 0
    special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    special_ratio = special_chars / len(text) if text else 0
    metrics["space_ratio"] = round(space_ratio, 3)
    metrics["special_char_ratio"] = round(special_ratio, 3)

    if special_ratio > 0.3:  # More than 30% special characters
        issues.append("high_special_char_ratio")

    # Calculate overall quality score (weighted combination)
    # Lower is worse for issues, higher is better for positive metrics
    quality_score = (
        (1.0 - min(1.0, glyph_ratio * 10)) * 0.4 +  # Glyph patterns (40% weight)
        alnum_ratio * 0.3 +                          # Alphanumeric ratio (30% weight)
        word_score * 0.3                              # Common words (30% weight)
    )

    # Clamp to 0-1 range
    quality_score = max(0.0, min(1.0, quality_score))

    # Text is readable if quality score is above threshold and no critical issues
    is_readable = quality_score >= 0.4 and "glyph_indices_detected" not in issues

    return {
        "quality_score": round(quality_score, 3),
        "is_readable": is_readable,
        "issues": issues,
        "metrics": metrics,
    }


def extract_page_snippets(pdf_stream: io.BytesIO) -> list[dict[str, Any]]:
    """Extract text snippets from each page of the PDF with quality detection.

    Args:
        pdf_stream: BytesIO stream containing the PDF

    Returns:
        List of dicts with page number, text snippet, and quality metrics
    """
    reader = PdfReader(pdf_stream)
    page_snippets = []

    for i, page in enumerate(reader.pages):
        try:
            # Extract text (PyPDF is fast for text extraction)
            text = page.extract_text() or ""

            # Take only the first N characters for classification
            snippet = text[:MAX_CHARS_PER_PAGE].strip()

            # Detect text quality to identify garbled/corrupt text
            quality = detect_text_quality(snippet)

            page_snippets.append(
                {
                    "page_number": i + 1,  # 1-indexed for human readability
                    "snippet": snippet,
                    "has_text": len(snippet) > 50,  # Flag if page has meaningful text
                    "text_quality": quality,  # Quality metrics for intelligent routing
                }
            )
        except Exception as e:
            print(f"Error extracting page {i + 1}: {str(e)}")
            page_snippets.append(
                {
                    "page_number": i + 1,
                    "snippet": "",
                    "has_text": False,
                    "text_quality": {
                        "quality_score": 0.0,
                        "is_readable": False,
                        "issues": ["extraction_error"],
                        "metrics": {},
                    },
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


def identify_loan_agreement_sections(
    page_snippets: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """Identify Loan Agreement sections using intelligent keyword density scoring.

    COST-OPTIMIZED APPROACH (same pattern as Credit Agreement):
    - Score each page by keyword density (matches / total keywords)
    - Select only TOP N pages per section (not all pages above threshold)
    - Use special handling for signatures section (prioritize last pages)
    - Strict page limits to minimize Textract costs

    Args:
        page_snippets: List of page snippets from extract_page_snippets

    Returns:
        Dict mapping section names to lists of candidate page numbers
    """
    # Page limits per section (strict limits for cost control)
    SECTION_PAGE_LIMITS = {
        "loanTerms": 5,       # Core terms like amount, rate, maturity
        "interestDetails": 3, # Interest rate specifics
        "paymentInfo": 3,     # Payment schedule
        "parties": 3,         # Borrower/Lender info
        "security": 3,        # Collateral
        "fees": 2,            # Fee schedule
        "signatures": 3,      # Signature pages
    }

    section_pages: dict[str, list[int]] = {
        section: [] for section in LOAN_AGREEMENT_SECTIONS
    }

    total_pages = len(page_snippets)

    # Score all pages for each section using keyword density
    section_scores: dict[str, list[tuple[int, float, int]]] = {
        section: [] for section in LOAN_AGREEMENT_SECTIONS
    }

    for page in page_snippets:
        if not page["has_text"]:
            continue

        page_num = page["page_number"]
        text_lower = page["snippet"].lower()

        for section_id, section_info in LOAN_AGREEMENT_SECTIONS.items():
            keywords = section_info.get("keywords", [])
            if not keywords:
                continue

            # Count keyword matches
            matches = sum(1 for kw in keywords if kw.lower() in text_lower)

            # SPECIAL HANDLING: signatures section prioritizes last pages
            bonus = 0
            if section_id == "signatures":
                # Strong bonus for last 3 pages
                if page_num >= total_pages - 2:
                    bonus += 10
                elif page_num >= total_pages - 4:
                    bonus += 5

                # Bonus for signature block indicators
                if "witness whereof" in text_lower or "in witness" in text_lower:
                    bonus += 5
                if "executed" in text_lower and "date" in text_lower:
                    bonus += 3

            # SPECIAL HANDLING: loanTerms section prioritizes first pages
            if section_id == "loanTerms":
                # First few pages often have key terms
                if page_num <= 3:
                    bonus += 3
                elif page_num <= 5:
                    bonus += 1

            # SPECIAL HANDLING: parties section prioritizes first pages
            if section_id == "parties":
                if page_num <= 3:
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
        limit = SECTION_PAGE_LIMITS.get(section_id, 3)

        # Select top pages
        top_pages = [page_num for page_num, score, matches in scores[:limit]]
        section_pages[section_id] = sorted(top_pages)

        # Log selection for debugging
        if top_pages:
            top_3 = scores[:3]
            print(f"[LoanAgreement] Section '{section_id}': Selected {len(top_pages)} pages. "
                  f"Top scores: {[(p, s) for p, s, m in top_3]}")

    # ALWAYS include last 3 pages for signature detection (even if no keyword matches)
    # This is critical for legal document validation
    if not section_pages.get("signatures"):
        last_pages = list(range(max(1, total_pages - 2), total_pages + 1))
        section_pages["signatures"] = last_pages
        print(f"[LoanAgreement] Section 'signatures': Defaulting to last pages {last_pages}")

    # =========================================================================
    # INTELLIGENT TEXT QUALITY-BASED FALLBACK
    # =========================================================================
    # Instead of hardcoding "first 10 pages", we intelligently detect pages where
    # keyword matching failed due to poor text extraction quality (garbled text
    # from custom fonts). These pages need Textract OCR for proper extraction.
    #
    # This is the proper fix - let the router INTELLIGENTLY identify pages that
    # need alternative extraction, rather than blindly including arbitrary pages.
    # =========================================================================

    # Identify pages with poor text quality (keyword matching won't work)
    low_quality_pages = []
    high_quality_pages = []

    for page in page_snippets:
        page_num = page["page_number"]
        quality = page.get("text_quality", {})
        is_readable = quality.get("is_readable", True)
        quality_score = quality.get("quality_score", 1.0)
        issues = quality.get("issues", [])

        if not is_readable or quality_score < 0.4:
            low_quality_pages.append(page_num)
            print(f"[LoanAgreement] Page {page_num}: LOW QUALITY (score={quality_score:.2f}, issues={issues})")
        else:
            high_quality_pages.append(page_num)

    # Log quality summary
    print(f"[LoanAgreement] Text quality summary: {len(high_quality_pages)} readable, {len(low_quality_pages)} low-quality pages")

    # Collect all pages found via keyword matching
    all_found_pages = set()
    for pages in section_pages.values():
        all_found_pages.update(pages)

    print(f"[LoanAgreement] Keyword matching found {len(all_found_pages)} pages: {sorted(all_found_pages)}")

    # INTELLIGENT FALLBACK: Add low-quality pages for Textract extraction
    # These pages have garbled text (e.g., glyph indices), so keyword matching failed.
    # Textract OCR can properly read them, so include them for extraction.
    if low_quality_pages:
        print(f"[LoanAgreement] Adding {len(low_quality_pages)} low-quality pages for Textract OCR: {sorted(low_quality_pages)}")
        # Add low-quality pages to loanTerms (most likely to have key info)
        existing_loan_terms = set(section_pages.get("loanTerms", []))
        section_pages["loanTerms"] = sorted(list(existing_loan_terms.union(set(low_quality_pages))))

    # SAFETY CHECK: If very few pages found and document has many pages with text,
    # we may have missed critical pages. Add pages near keyword matches.
    if len(all_found_pages) < 5 and total_pages > 10:
        # Expand around found pages (±1 page)
        expanded_pages = set()
        for page_num in all_found_pages:
            expanded_pages.add(page_num)
            if page_num > 1:
                expanded_pages.add(page_num - 1)
            if page_num < total_pages:
                expanded_pages.add(page_num + 1)

        new_pages = expanded_pages - all_found_pages
        if new_pages:
            print(f"[LoanAgreement] Few pages found - expanding search to adjacent pages: {sorted(new_pages)}")
            existing_loan_terms = set(section_pages.get("loanTerms", []))
            section_pages["loanTerms"] = sorted(list(existing_loan_terms.union(new_pages)))

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

    # Capture REAL token usage from Bedrock response
    usage = response_body.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        # Add REAL token usage for accurate cost tracking
        result["_tokenUsage"] = {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
        }
        return result
    except json.JSONDecodeError as e:
        print(f"Error parsing Credit Agreement section response: {content}")
        # Fall back to candidate sections - still include token usage
        return {
            "sections": candidate_sections,
            "documentSubtype": "unknown",
            "confidence": "low",
            "notes": f"Failed to parse LLM response: {str(e)}",
            "_tokenUsage": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
            },
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
    # Merge hardcoded DOCUMENT_TYPES with plugin registry types
    doc_type_descriptions = []
    known_type_ids = set()

    # First: add plugin-registered types (authoritative source)
    try:
        from document_plugins.registry import get_all_plugins
        for plugin_id, plugin_config in get_all_plugins().items():
            cls = plugin_config.get("classification", {})
            keywords = ", ".join(cls.get("keywords", [])[:5])
            name = plugin_config.get("name", plugin_id)
            desc = plugin_config.get("description", "")[:100]
            doc_type_descriptions.append(
                f"- **{plugin_id}**: {name}\n  Description: {desc}\n  Keywords: {keywords}"
            )
            known_type_ids.add(plugin_id)
    except (ImportError, Exception) as e:
        print(f"Warning: Plugin registry not available for classification: {e}")

    # Then: add legacy types not covered by plugins
    for type_id, type_info in DOCUMENT_TYPES.items():
        if type_id not in known_type_ids:
            keywords = ", ".join(type_info["keywords"][:5])
            doc_type_descriptions.append(
                f"- **{type_id}**: {type_info['name']}\n  Keywords: {keywords}"
            )
            known_type_ids.add(type_id)

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

CRITICAL DISTINCTION - Credit Agreement vs Loan Agreement:
- **credit_agreement**: Complex SYNDICATED facilities with MULTIPLE LENDERS, Administrative Agent,
  Lead Arrangers, Commitment Schedules, Pricing Grids, LC Commitments, Swingline sublimits.
  Usually 50+ pages with formal legal structure.
- **loan_agreement**: SIMPLE business/personal loans with ONE lender and ONE borrower.
  Terms like "Loan Agreement", "Business Loan", "Commercial Loan", "Line of Credit".
  Usually 5-30 pages, straightforward structure.

If the document is titled "Loan Agreement" WITHOUT indicators of syndication (multiple lenders,
administrative agent, lead arrangers), classify as "loan_agreement", NOT "credit_agreement".

Respond with ONLY valid JSON in this exact format:
{{
  "credit_agreement": <page_number or null>,
  "loan_agreement": <page_number or null>,
  "loan_package": <page_number or null>,
  "bsa_profile": <page_number or null>,
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

    # Capture REAL token usage from Bedrock response
    usage = response_body.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

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
        classification["loanAgreement"] = classification.get("loan_agreement")

        # Add REAL token usage for accurate cost tracking
        classification["_tokenUsage"] = {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
        }

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

        # 2. Extract page snippets (fast, no OCR) with text quality detection
        print("Extracting page snippets...")
        page_snippets = extract_page_snippets(pdf_stream)
        total_pages = len(page_snippets)
        print(f"Extracted snippets from {total_pages} pages")

        # 2b. Analyze text quality across all pages
        low_quality_pages = []
        for page in page_snippets:
            quality = page.get("text_quality", {})
            if not quality.get("is_readable", True):
                low_quality_pages.append(page["page_number"])

        if low_quality_pages:
            print(f"Detected {len(low_quality_pages)} pages with low text quality (need OCR): {low_quality_pages}")

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

        # Resolve existing DynamoDB documentType for event logging
        _existing_doc_type = "PROCESSING"
        try:
            _q = dynamodb.Table(TABLE_NAME).query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("documentId").eq(document_id),
                Limit=1,
            )
            if _q.get("Items"):
                _existing_doc_type = _q["Items"][0].get("documentType", "PROCESSING")
        except Exception:
            pass

        # Log classification event
        primary_type = classification.get("primary_document_type", "unknown")
        confidence_str = classification.get("confidence", "unknown")
        append_processing_event(
            document_id, _existing_doc_type, "router",
            f"Classified as {primary_type} (confidence: {confidence_str})",
        )

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

            # VALIDATION: Check if this is really a syndicated Credit Agreement
            # Real Credit Agreements have multiple sections with content (rates, lenders, etc.)
            # If only agreementInfo has pages and other critical sections are empty,
            # this is likely a simple Loan Agreement that was misclassified
            if credit_agreement_sections:
                sections = credit_agreement_sections.get("sections", {})
                # Key sections that must have content for a real Credit Agreement
                critical_sections = ["applicableRates", "facilityTerms", "lenderCommitments"]
                has_critical_content = any(
                    len(sections.get(section, [])) > 0 for section in critical_sections
                )

                # Count how many sections have actual pages
                sections_with_content = sum(
                    1 for pages in sections.values() if len(pages) > 0
                )

                if not has_critical_content or sections_with_content <= 1:
                    print(f"WARNING: Credit Agreement sections mostly empty ({sections_with_content} sections with content)")
                    print(f"Critical sections present: {has_critical_content}")

                    # This is likely a simple Loan Agreement misclassified as Credit Agreement
                    # Reclassify as Loan Agreement regardless of whether loan_agreement was detected
                    print("Reclassifying as Loan Agreement (Credit Agreement sections insufficient)")
                    credit_agreement_sections = None
                    # Clear credit_agreement from classification to prevent Credit Agreement path
                    classification["credit_agreement"] = None
                    # Set loan_agreement page (use page 1 as the starting page)
                    classification["loan_agreement"] = 1
                    classification["loanAgreement"] = 1
                    classification["primary_document_type"] = "loan_agreement"

        # 4b. If Loan Agreement detected (and not a Credit Agreement), identify sections with page ranges
        loan_agreement_sections = None
        if classification.get("loan_agreement") is not None and credit_agreement_sections is None:
            print("Loan Agreement detected - identifying sections...")

            # Fast keyword-based section identification
            loan_agreement_sections = identify_loan_agreement_sections(page_snippets)
            print(f"Loan Agreement sections: {json.dumps(loan_agreement_sections)}")

            # Calculate total targeted pages
            all_section_pages = set()
            for pages in loan_agreement_sections.values():
                all_section_pages.update(pages)
            print(f"Loan Agreement: {len(all_section_pages)} targeted pages identified")

        # 5. Aggregate REAL token usage from all Bedrock calls
        # Classification call token usage
        classification_tokens = classification.get("_tokenUsage", {})
        total_input_tokens = classification_tokens.get("inputTokens", 0)
        total_output_tokens = classification_tokens.get("outputTokens", 0)

        # Credit Agreement section call token usage (if applicable)
        if credit_agreement_sections:
            ca_tokens = credit_agreement_sections.get("_tokenUsage", {})
            total_input_tokens += ca_tokens.get("inputTokens", 0)
            total_output_tokens += ca_tokens.get("outputTokens", 0)

        print(f"Router REAL token usage - Input: {total_input_tokens}, Output: {total_output_tokens}")

        # 6. Prepare output for Step Functions
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
            # REAL router token usage for accurate cost calculation in normalizer
            "routerTokenUsage": {
                "inputTokens": total_input_tokens,
                "outputTokens": total_output_tokens,
            },
            # TOP-LEVEL lowQualityPages for Step Functions to pass to extractor
            # These pages have garbled text (font encoding issues) and need Textract OCR
            "lowQualityPages": low_quality_pages,
            "metadata": {
                "routerModel": BEDROCK_MODEL_ID,
                "pagesWithText": len([p for p in page_snippets if p["has_text"]]),
                "documentTypesFound": len(identified_docs),
                "primaryDocumentType": classification.get("primary_document_type"),
                "classificationConfidence": classification.get("confidence", "unknown"),
                # Text quality info - pages that need Textract OCR due to garbled text
                "lowQualityPages": low_quality_pages,
                "lowQualityPageCount": len(low_quality_pages),
            },
        }

        # ============================================================
        # Plugin-driven extraction plan (dual-format output)
        # When ROUTER_OUTPUT_FORMAT=dual, emit extractionPlan alongside legacy keys
        # ============================================================
        router_output_format = os.environ.get("ROUTER_OUTPUT_FORMAT", "legacy")
        if router_output_format == "dual":
            try:
                from document_plugins.registry import get_all_plugins

                all_plugins = get_all_plugins()
                plugin = _resolve_plugin(classification, all_plugins)
                if plugin:
                    plugin_id = plugin["plugin_id"]
                    plugin_cls = plugin.get("classification", {})

                    # Build section pages based on plugin type
                    if plugin_cls.get("target_all_pages"):
                        section_result = classification
                    elif plugin_cls.get("section_names"):
                        section_result = classification
                    elif plugin_cls.get("has_sections") or plugin.get("sections"):
                        keyword_sections = identify_sections_generic(
                            page_snippets, plugin, total_pages
                        )
                        section_result = {"sections": keyword_sections}
                    else:
                        section_result = classification

                    extraction_plan = build_extraction_plan(
                        plugin, section_result, page_snippets
                    )
                    # Inject document-level fields into each plan item
                    # (Map state itemSelector passes these to ExtractSection Lambda)
                    for item in extraction_plan:
                        item["documentId"] = document_id
                        item["bucket"] = bucket
                        item["key"] = key
                        item["contentHash"] = content_hash
                        item["size"] = file_size
                    result["extractionPlan"] = extraction_plan
                    result["pluginId"] = plugin_id
                    result["metadata"]["pluginId"] = plugin_id
                    result["metadata"]["pluginVersion"] = plugin.get("plugin_version", "unknown")

                    # Add backward-compatible legacy keys
                    add_backward_compatible_keys(
                        result, plugin_id, extraction_plan, classification
                    )
                    print(f"Plugin extraction plan: {len(extraction_plan)} sections for {plugin_id}")

                    # Log page-targeting event
                    targeted_page_set = set()
                    for sec in extraction_plan:
                        targeted_page_set.update(sec.get("sectionPages", []))
                    append_processing_event(
                        document_id, _existing_doc_type, "router",
                        f"Targeted {len(targeted_page_set)}/{total_pages} pages across {len(extraction_plan)} sections",
                    )
            except Exception as plugin_err:
                print(f"Warning: Plugin extraction plan failed, using legacy path: {plugin_err}")

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
            # Log legacy page-targeting event for Credit Agreement
            num_ca_sections = sum(1 for p in credit_agreement_sections.get("sections", {}).values() if p)
            append_processing_event(
                document_id, _existing_doc_type, "router",
                f"Targeted {len(all_section_pages)}/{total_pages} pages across {num_ca_sections} sections",
            )

        # Add Loan Agreement section details if detected
        if loan_agreement_sections:
            result["loanAgreementSections"] = {"sections": loan_agreement_sections}
            # Calculate targeted pages for cost estimate
            all_section_pages = set()
            for pages in loan_agreement_sections.values():
                all_section_pages.update(pages)
            result["metadata"]["loanAgreementTargetedPages"] = len(all_section_pages)
            # Log legacy page-targeting event for Loan Agreement
            num_la_sections = sum(1 for p in loan_agreement_sections.values() if p)
            append_processing_event(
                document_id, _existing_doc_type, "router",
                f"Targeted {len(all_section_pages)}/{total_pages} pages across {num_la_sections} sections",
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
