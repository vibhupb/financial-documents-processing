"""Extraction field definitions for each document type.

DEPRECATED: Use document_plugins per-section configs instead. Queries and
extraction fields now live in plugin SectionConfig.queries and
SectionConfig.extraction_fields. See lambda/layers/plugins/python/document_plugins/types/.

This module defines the specific fields to extract from each document type,
including field metadata, validation rules, and Textract query configurations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FieldType(str, Enum):
    """Data types for extracted fields."""

    STRING = "string"
    NUMBER = "number"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    BOOLEAN = "boolean"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    SSN = "ssn"  # Social Security Number (masked)
    EIN = "ein"  # Employer Identification Number
    ACCOUNT_NUMBER = "account_number"


class ExtractionMethod(str, Enum):
    """Methods for extracting data from documents."""

    TEXTRACT_QUERY = "query"  # Amazon Textract AnalyzeDocument with queries
    TEXTRACT_FORM = "form"  # Amazon Textract form extraction (key-value pairs)
    TEXTRACT_TABLE = "table"  # Amazon Textract table extraction
    LLM_EXTRACTION = "llm"  # Use LLM (Bedrock) for extraction
    REGEX = "regex"  # Regular expression matching
    OCR_REGION = "ocr_region"  # OCR specific region of document


@dataclass
class ExtractionField:
    """Definition of a single field to extract."""

    id: str  # Unique field identifier
    name: str  # Display name
    field_type: FieldType
    description: str
    required: bool = False
    method: ExtractionMethod = ExtractionMethod.TEXTRACT_QUERY
    query: Optional[str] = None  # Textract query string
    regex_pattern: Optional[str] = None  # Regex pattern for extraction
    validation_regex: Optional[str] = None  # Regex for validation
    min_value: Optional[float] = None  # For numeric fields
    max_value: Optional[float] = None  # For numeric fields
    aliases: list[str] = field(default_factory=list)  # Alternative field names
    pii: bool = False  # Contains PII - should be masked in logs
    cross_reference: Optional[str] = None  # Field to cross-reference with


@dataclass
class ExtractionSchema:
    """Complete extraction schema for a document type."""

    id: str  # Schema identifier (matches document type ID)
    name: str  # Display name
    description: str
    fields: list[ExtractionField]
    textract_features: list[str] = field(default_factory=list)  # QUERIES, TABLES, FORMS
    llm_model: Optional[str] = None  # For LLM extraction


# ============================================================
# PROMISSORY NOTE EXTRACTION SCHEMA
# ============================================================

PROMISSORY_NOTE_SCHEMA = ExtractionSchema(
    id="promissory_note",
    name="Promissory Note",
    description="Extract key terms from promissory note",
    textract_features=["QUERIES"],
    fields=[
        ExtractionField(
            id="principal_amount",
            name="Principal Amount",
            field_type=FieldType.CURRENCY,
            description="Original loan principal amount",
            required=True,
            query="What is the principal amount or loan amount?",
            min_value=1000,
            max_value=100000000,
            cross_reference="closing_disclosure.loan_amount",
        ),
        ExtractionField(
            id="interest_rate",
            name="Interest Rate",
            field_type=FieldType.PERCENTAGE,
            description="Annual interest rate",
            required=True,
            query="What is the interest rate or annual percentage rate?",
            min_value=0,
            max_value=30,
            cross_reference="closing_disclosure.interest_rate",
        ),
        ExtractionField(
            id="borrower_name",
            name="Borrower Name",
            field_type=FieldType.STRING,
            description="Primary borrower's full legal name",
            required=True,
            query="Who is the borrower or maker of this note?",
            pii=True,
            cross_reference="form_1003.borrower_name",
        ),
        ExtractionField(
            id="co_borrower_name",
            name="Co-Borrower Name",
            field_type=FieldType.STRING,
            description="Co-borrower's full legal name",
            required=False,
            query="Who is the co-borrower or co-maker?",
            pii=True,
        ),
        ExtractionField(
            id="lender_name",
            name="Lender Name",
            field_type=FieldType.STRING,
            description="Lender or payee name",
            required=True,
            query="Who is the lender or payee?",
        ),
        ExtractionField(
            id="monthly_payment",
            name="Monthly Payment",
            field_type=FieldType.CURRENCY,
            description="Monthly principal and interest payment",
            required=True,
            query="What is the monthly payment amount?",
            cross_reference="closing_disclosure.monthly_pi",
        ),
        ExtractionField(
            id="first_payment_date",
            name="First Payment Date",
            field_type=FieldType.DATE,
            description="Date of first payment",
            required=True,
            query="What is the first payment date?",
        ),
        ExtractionField(
            id="maturity_date",
            name="Maturity Date",
            field_type=FieldType.DATE,
            description="Loan maturity or final payment date",
            required=True,
            query="What is the maturity date or final payment date?",
        ),
        ExtractionField(
            id="late_charge_percent",
            name="Late Charge Percentage",
            field_type=FieldType.PERCENTAGE,
            description="Late payment charge percentage",
            required=False,
            query="What is the late charge percentage?",
        ),
        ExtractionField(
            id="late_charge_grace_days",
            name="Late Charge Grace Period",
            field_type=FieldType.NUMBER,
            description="Days before late charge applies",
            required=False,
            query="How many days before a late charge is applied?",
        ),
        ExtractionField(
            id="prepayment_penalty",
            name="Prepayment Penalty",
            field_type=FieldType.BOOLEAN,
            description="Whether prepayment penalty applies",
            required=False,
            query="Is there a prepayment penalty?",
        ),
        ExtractionField(
            id="property_address",
            name="Property Address",
            field_type=FieldType.ADDRESS,
            description="Address of the secured property",
            required=True,
            query="What is the property address?",
            cross_reference="closing_disclosure.property_address",
        ),
        ExtractionField(
            id="note_date",
            name="Note Date",
            field_type=FieldType.DATE,
            description="Date the note was signed",
            required=True,
            query="What is the date of this note?",
        ),
    ],
)

# ============================================================
# CLOSING DISCLOSURE EXTRACTION SCHEMA
# ============================================================

CLOSING_DISCLOSURE_SCHEMA = ExtractionSchema(
    id="closing_disclosure",
    name="Closing Disclosure",
    description="Extract loan terms and closing costs",
    textract_features=["QUERIES", "TABLES"],
    fields=[
        ExtractionField(
            id="loan_amount",
            name="Loan Amount",
            field_type=FieldType.CURRENCY,
            description="Total loan amount",
            required=True,
            query="What is the loan amount?",
        ),
        ExtractionField(
            id="interest_rate",
            name="Interest Rate",
            field_type=FieldType.PERCENTAGE,
            description="Annual interest rate",
            required=True,
            query="What is the interest rate?",
        ),
        ExtractionField(
            id="monthly_pi",
            name="Monthly Principal & Interest",
            field_type=FieldType.CURRENCY,
            description="Monthly P&I payment",
            required=True,
            query="What is the monthly principal and interest payment?",
        ),
        ExtractionField(
            id="estimated_total_monthly",
            name="Estimated Total Monthly Payment",
            field_type=FieldType.CURRENCY,
            description="Total monthly including escrow",
            required=True,
            query="What is the estimated total monthly payment?",
        ),
        ExtractionField(
            id="closing_costs",
            name="Total Closing Costs",
            field_type=FieldType.CURRENCY,
            description="Total closing costs (Section D)",
            required=True,
            query="What is the total closing costs?",
        ),
        ExtractionField(
            id="cash_to_close",
            name="Cash to Close",
            field_type=FieldType.CURRENCY,
            description="Final cash to close amount",
            required=True,
            query="What is the cash to close amount?",
        ),
        ExtractionField(
            id="loan_term",
            name="Loan Term",
            field_type=FieldType.NUMBER,
            description="Loan term in years",
            required=True,
            query="What is the loan term in years?",
        ),
        ExtractionField(
            id="loan_purpose",
            name="Loan Purpose",
            field_type=FieldType.STRING,
            description="Purpose (Purchase, Refinance, etc.)",
            required=True,
            query="What is the purpose of the loan?",
        ),
        ExtractionField(
            id="loan_type",
            name="Loan Type",
            field_type=FieldType.STRING,
            description="Loan type (Conventional, FHA, VA, etc.)",
            required=True,
            query="What is the loan type?",
        ),
        ExtractionField(
            id="property_address",
            name="Property Address",
            field_type=FieldType.ADDRESS,
            description="Subject property address",
            required=True,
            query="What is the property address?",
        ),
        ExtractionField(
            id="sale_price",
            name="Sale Price",
            field_type=FieldType.CURRENCY,
            description="Property sale/purchase price",
            required=False,
            query="What is the sale price of the property?",
        ),
        ExtractionField(
            id="appraised_value",
            name="Appraised Value",
            field_type=FieldType.CURRENCY,
            description="Appraised property value",
            required=False,
            query="What is the appraised value?",
        ),
        ExtractionField(
            id="origination_charges",
            name="Origination Charges",
            field_type=FieldType.CURRENCY,
            description="Total origination charges (Section A)",
            required=True,
            method=ExtractionMethod.TEXTRACT_TABLE,
        ),
        ExtractionField(
            id="services_borrower_did_shop",
            name="Services Borrower Did Shop For",
            field_type=FieldType.CURRENCY,
            description="Total services borrower shopped for (Section C)",
            required=False,
            method=ExtractionMethod.TEXTRACT_TABLE,
        ),
        ExtractionField(
            id="closing_date",
            name="Closing Date",
            field_type=FieldType.DATE,
            description="Loan closing date",
            required=True,
            query="What is the closing date?",
        ),
        ExtractionField(
            id="disbursement_date",
            name="Disbursement Date",
            field_type=FieldType.DATE,
            description="Funds disbursement date",
            required=False,
            query="What is the disbursement date?",
        ),
    ],
)

# ============================================================
# FORM 1003 (URLA) EXTRACTION SCHEMA
# ============================================================

FORM_1003_SCHEMA = ExtractionSchema(
    id="form_1003",
    name="Uniform Residential Loan Application",
    description="Extract borrower and loan information from Form 1003",
    textract_features=["FORMS", "QUERIES"],
    fields=[
        # Borrower Information
        ExtractionField(
            id="borrower_name",
            name="Borrower Full Name",
            field_type=FieldType.STRING,
            description="Borrower's full legal name",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="borrower_ssn",
            name="Borrower SSN",
            field_type=FieldType.SSN,
            description="Borrower's Social Security Number",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
            validation_regex=r"^\d{3}-?\d{2}-?\d{4}$",
        ),
        ExtractionField(
            id="borrower_dob",
            name="Borrower Date of Birth",
            field_type=FieldType.DATE,
            description="Borrower's date of birth",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="borrower_phone",
            name="Borrower Phone",
            field_type=FieldType.PHONE,
            description="Borrower's phone number",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="borrower_email",
            name="Borrower Email",
            field_type=FieldType.EMAIL,
            description="Borrower's email address",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="borrower_current_address",
            name="Borrower Current Address",
            field_type=FieldType.ADDRESS,
            description="Borrower's current residence address",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="borrower_years_at_address",
            name="Years at Current Address",
            field_type=FieldType.NUMBER,
            description="Years living at current address",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="marital_status",
            name="Marital Status",
            field_type=FieldType.STRING,
            description="Borrower's marital status",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="dependents_count",
            name="Number of Dependents",
            field_type=FieldType.NUMBER,
            description="Number of dependents",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        # Employment Information
        ExtractionField(
            id="employer_name",
            name="Current Employer Name",
            field_type=FieldType.STRING,
            description="Name of current employer",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="employer_address",
            name="Employer Address",
            field_type=FieldType.ADDRESS,
            description="Employer's address",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="job_title",
            name="Job Title/Position",
            field_type=FieldType.STRING,
            description="Borrower's job title or position",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="employer_phone",
            name="Employer Phone",
            field_type=FieldType.PHONE,
            description="Employer's phone number",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="years_employed",
            name="Years on This Job",
            field_type=FieldType.NUMBER,
            description="Years employed at current job",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="years_in_profession",
            name="Years in Profession",
            field_type=FieldType.NUMBER,
            description="Total years in this line of work",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="self_employed",
            name="Self Employed",
            field_type=FieldType.BOOLEAN,
            description="Is borrower self-employed?",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        # Income
        ExtractionField(
            id="base_income_monthly",
            name="Monthly Base Income",
            field_type=FieldType.CURRENCY,
            description="Monthly base/salary income",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="overtime_monthly",
            name="Monthly Overtime",
            field_type=FieldType.CURRENCY,
            description="Monthly overtime income",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="bonus_monthly",
            name="Monthly Bonus",
            field_type=FieldType.CURRENCY,
            description="Monthly bonus income",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="commission_monthly",
            name="Monthly Commission",
            field_type=FieldType.CURRENCY,
            description="Monthly commission income",
            required=False,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="total_monthly_income",
            name="Total Monthly Income",
            field_type=FieldType.CURRENCY,
            description="Total combined monthly income",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        # Property Information
        ExtractionField(
            id="property_address",
            name="Subject Property Address",
            field_type=FieldType.ADDRESS,
            description="Address of property being financed",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="property_value",
            name="Property Value",
            field_type=FieldType.CURRENCY,
            description="Estimated or appraised value",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="loan_amount_requested",
            name="Loan Amount Requested",
            field_type=FieldType.CURRENCY,
            description="Requested loan amount",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="loan_purpose",
            name="Loan Purpose",
            field_type=FieldType.STRING,
            description="Purpose (Purchase, Refinance, etc.)",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="occupancy_type",
            name="Occupancy Type",
            field_type=FieldType.STRING,
            description="Primary, Secondary, or Investment",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
    ],
)

# ============================================================
# DEED OF TRUST EXTRACTION SCHEMA
# ============================================================

DEED_OF_TRUST_SCHEMA = ExtractionSchema(
    id="deed_of_trust",
    name="Deed of Trust",
    description="Extract key terms from deed of trust/mortgage",
    textract_features=["QUERIES"],
    fields=[
        ExtractionField(
            id="grantor_name",
            name="Grantor/Borrower Name",
            field_type=FieldType.STRING,
            description="Name of the grantor (borrower)",
            required=True,
            query="Who is the grantor or borrower?",
            pii=True,
        ),
        ExtractionField(
            id="beneficiary_name",
            name="Beneficiary/Lender Name",
            field_type=FieldType.STRING,
            description="Name of the beneficiary (lender)",
            required=True,
            query="Who is the beneficiary or lender?",
        ),
        ExtractionField(
            id="trustee_name",
            name="Trustee Name",
            field_type=FieldType.STRING,
            description="Name of the trustee",
            required=True,
            query="Who is the trustee?",
        ),
        ExtractionField(
            id="property_address",
            name="Property Address",
            field_type=FieldType.ADDRESS,
            description="Address of the secured property",
            required=True,
            query="What is the property address?",
        ),
        ExtractionField(
            id="legal_description",
            name="Legal Description",
            field_type=FieldType.STRING,
            description="Legal description of the property",
            required=True,
            query="What is the legal description of the property?",
        ),
        ExtractionField(
            id="parcel_number",
            name="Parcel/APN Number",
            field_type=FieldType.STRING,
            description="Assessor's parcel number",
            required=False,
            query="What is the parcel number or APN?",
        ),
        ExtractionField(
            id="recording_date",
            name="Recording Date",
            field_type=FieldType.DATE,
            description="Date recorded with county",
            required=False,
            query="What is the recording date?",
        ),
        ExtractionField(
            id="instrument_number",
            name="Instrument/Document Number",
            field_type=FieldType.STRING,
            description="Recording instrument number",
            required=False,
            query="What is the instrument or document number?",
        ),
    ],
)

# ============================================================
# BANK STATEMENT EXTRACTION SCHEMA
# ============================================================

BANK_STATEMENT_SCHEMA = ExtractionSchema(
    id="bank_statement",
    name="Bank Statement",
    description="Extract account information from bank statements",
    textract_features=["TABLES", "QUERIES"],
    fields=[
        ExtractionField(
            id="account_holder_name",
            name="Account Holder Name",
            field_type=FieldType.STRING,
            description="Name on the account",
            required=True,
            query="What is the account holder's name?",
            pii=True,
        ),
        ExtractionField(
            id="account_number",
            name="Account Number",
            field_type=FieldType.ACCOUNT_NUMBER,
            description="Bank account number",
            required=True,
            query="What is the account number?",
            pii=True,
        ),
        ExtractionField(
            id="bank_name",
            name="Bank Name",
            field_type=FieldType.STRING,
            description="Financial institution name",
            required=True,
            query="What is the bank or financial institution name?",
        ),
        ExtractionField(
            id="statement_period_start",
            name="Statement Start Date",
            field_type=FieldType.DATE,
            description="Statement period start date",
            required=True,
            query="What is the statement start date?",
        ),
        ExtractionField(
            id="statement_period_end",
            name="Statement End Date",
            field_type=FieldType.DATE,
            description="Statement period end date",
            required=True,
            query="What is the statement end date?",
        ),
        ExtractionField(
            id="beginning_balance",
            name="Beginning Balance",
            field_type=FieldType.CURRENCY,
            description="Balance at start of period",
            required=True,
            query="What is the beginning balance?",
        ),
        ExtractionField(
            id="ending_balance",
            name="Ending Balance",
            field_type=FieldType.CURRENCY,
            description="Balance at end of period",
            required=True,
            query="What is the ending balance?",
        ),
        ExtractionField(
            id="total_deposits",
            name="Total Deposits",
            field_type=FieldType.CURRENCY,
            description="Total deposits during period",
            required=False,
            query="What is the total deposits?",
        ),
        ExtractionField(
            id="total_withdrawals",
            name="Total Withdrawals",
            field_type=FieldType.CURRENCY,
            description="Total withdrawals during period",
            required=False,
            query="What is the total withdrawals?",
        ),
        ExtractionField(
            id="average_balance",
            name="Average Balance",
            field_type=FieldType.CURRENCY,
            description="Average daily balance",
            required=False,
            query="What is the average daily balance?",
        ),
    ],
)

# ============================================================
# W-2 EXTRACTION SCHEMA
# ============================================================

W2_SCHEMA = ExtractionSchema(
    id="w2",
    name="W-2 Wage and Tax Statement",
    description="Extract income and tax information from W-2",
    textract_features=["FORMS"],
    fields=[
        ExtractionField(
            id="employee_ssn",
            name="Employee SSN",
            field_type=FieldType.SSN,
            description="Employee's Social Security Number",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="employer_ein",
            name="Employer EIN",
            field_type=FieldType.EIN,
            description="Employer Identification Number",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="employer_name",
            name="Employer Name",
            field_type=FieldType.STRING,
            description="Employer's name",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="employee_name",
            name="Employee Name",
            field_type=FieldType.STRING,
            description="Employee's full name",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
            pii=True,
        ),
        ExtractionField(
            id="wages_tips_compensation",
            name="Wages, Tips, Other Compensation",
            field_type=FieldType.CURRENCY,
            description="Box 1: Total wages",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="federal_income_tax_withheld",
            name="Federal Income Tax Withheld",
            field_type=FieldType.CURRENCY,
            description="Box 2: Federal tax withheld",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="social_security_wages",
            name="Social Security Wages",
            field_type=FieldType.CURRENCY,
            description="Box 3: SS wages",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="social_security_tax_withheld",
            name="Social Security Tax Withheld",
            field_type=FieldType.CURRENCY,
            description="Box 4: SS tax withheld",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="medicare_wages",
            name="Medicare Wages",
            field_type=FieldType.CURRENCY,
            description="Box 5: Medicare wages",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="medicare_tax_withheld",
            name="Medicare Tax Withheld",
            field_type=FieldType.CURRENCY,
            description="Box 6: Medicare tax withheld",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
        ExtractionField(
            id="tax_year",
            name="Tax Year",
            field_type=FieldType.NUMBER,
            description="Tax year for this W-2",
            required=True,
            method=ExtractionMethod.TEXTRACT_FORM,
        ),
    ],
)

# ============================================================
# CREDIT AGREEMENT EXTRACTION SCHEMA
# Based on loan_prompts_map field definitions for syndicated loans
# ============================================================

CREDIT_AGREEMENT_SCHEMA = ExtractionSchema(
    id="credit_agreement",
    name="Credit Agreement",
    description="Extract key terms from syndicated loan Credit Agreements",
    textract_features=["QUERIES", "TABLES"],
    llm_model="anthropic.claude-3-5-haiku-20241022-v1:0",  # For normalization
    fields=[
        # === Agreement Information (from loan_master_fields_section_1) ===
        ExtractionField(
            id="document_type",
            name="Document Type",
            field_type=FieldType.STRING,
            description="Type of agreement (Credit Agreement, Amendment, etc.)",
            required=True,
            query="What is the document title or type?",
        ),
        ExtractionField(
            id="agreement_date",
            name="Agreement Date",
            field_type=FieldType.DATE,
            description="Date of the agreement",
            required=True,
            query="What is the agreement date or dated as of date?",
            aliases=["dated as of", "effective as of", "closing date"],
        ),
        ExtractionField(
            id="maturity_date",
            name="Maturity Date",
            field_type=FieldType.DATE,
            description="Loan maturity or termination date",
            required=True,
            query="What is the Maturity Date?",
            aliases=["termination date", "expires on"],
        ),
        ExtractionField(
            id="borrower_name",
            name="Borrower Name",
            field_type=FieldType.STRING,
            description="Primary borrower's legal name",
            required=True,
            query="Who is the Borrower?",
            aliases=["the company", "as borrower"],
        ),
        ExtractionField(
            id="borrower_jurisdiction",
            name="Borrower Jurisdiction",
            field_type=FieldType.STRING,
            description="Borrower's state of incorporation",
            required=False,
            query="What is the Borrower's jurisdiction or state of incorporation?",
        ),
        ExtractionField(
            id="administrative_agent",
            name="Administrative Agent",
            field_type=FieldType.STRING,
            description="Bank acting as administrative agent",
            required=True,
            query="Who is the Administrative Agent?",
            aliases=["as agent"],
        ),
        ExtractionField(
            id="lead_arrangers",
            name="Lead Arrangers",
            field_type=FieldType.STRING,
            description="Lead arrangers and bookrunners",
            required=False,
            query="Who are the Lead Arrangers or Bookrunners?",
        ),
        ExtractionField(
            id="amendment_number",
            name="Amendment Number",
            field_type=FieldType.STRING,
            description="Amendment number if applicable",
            required=False,
            query="What is the Amendment Number?",
        ),
        # === Facility Terms (from loan_master_fields_section_2) ===
        ExtractionField(
            id="aggregate_max_revolving_credit",
            name="Aggregate Maximum Revolving Credit Amount",
            field_type=FieldType.CURRENCY,
            description="Maximum revolving credit facility size",
            required=True,
            query="What is the Aggregate Maximum Revolving Credit Amount?",
        ),
        ExtractionField(
            id="aggregate_elected_revolving_commitment",
            name="Aggregate Elected Revolving Credit Commitment",
            field_type=FieldType.CURRENCY,
            description="Current elected revolving commitment",
            required=True,
            query="What is the Aggregate Elected Revolving Credit Commitment?",
        ),
        ExtractionField(
            id="lc_commitment",
            name="LC Commitment",
            field_type=FieldType.CURRENCY,
            description="Letter of Credit commitment amount",
            required=False,
            query="What is the LC Commitment?",
        ),
        ExtractionField(
            id="lc_sublimit",
            name="LC Sublimit",
            field_type=FieldType.STRING,
            description="Letter of Credit sublimit (may be percentage)",
            required=False,
            query="What is the Letter of Credit Sublimit?",
        ),
        ExtractionField(
            id="swingline_sublimit",
            name="Swingline Sublimit",
            field_type=FieldType.CURRENCY,
            description="Swingline sublimit amount",
            required=False,
            query="What is the Swingline Sublimit?",
        ),
        ExtractionField(
            id="term_loan_commitment",
            name="Term Loan Commitment",
            field_type=FieldType.CURRENCY,
            description="Term loan commitment amount",
            required=False,
            query="What is the Term Loan Commitment?",
        ),
        # === Applicable Rates (from loan_accrual_fields) ===
        ExtractionField(
            id="reference_rate",
            name="Reference Rate",
            field_type=FieldType.STRING,
            description="Base reference rate (Term SOFR, ABR, etc.)",
            required=True,
            query="What is the reference rate or base rate?",
            aliases=["term sofr", "term benchmark", "abr", "prime"],
        ),
        ExtractionField(
            id="floor_rate",
            name="Floor Rate",
            field_type=FieldType.PERCENTAGE,
            description="Interest rate floor",
            required=False,
            query="What is the floor rate?",
            min_value=0,
            max_value=5,
        ),
        ExtractionField(
            id="pricing_tiers",
            name="Pricing Tiers",
            field_type=FieldType.STRING,
            description="Pricing grid with availability/leverage tiers",
            required=True,
            method=ExtractionMethod.TEXTRACT_TABLE,
        ),
        ExtractionField(
            id="term_sofr_spread",
            name="Term SOFR Spread",
            field_type=FieldType.PERCENTAGE,
            description="Spread over Term SOFR",
            required=False,
            query="What is the Term SOFR spread or margin?",
        ),
        ExtractionField(
            id="abr_spread",
            name="ABR Spread",
            field_type=FieldType.PERCENTAGE,
            description="Spread over ABR (Alternate Base Rate)",
            required=False,
            query="What is the ABR spread?",
        ),
        # === Fees (from loan_accrual_fields_section_3) ===
        ExtractionField(
            id="commitment_fee_rate",
            name="Commitment Fee Rate",
            field_type=FieldType.PERCENTAGE,
            description="Unused commitment fee rate",
            required=True,
            query="What is the Commitment Fee or Unused Fee rate?",
            min_value=0,
            max_value=1,
        ),
        ExtractionField(
            id="lc_fee_rate",
            name="LC Fee Rate",
            field_type=FieldType.PERCENTAGE,
            description="Letter of Credit fee rate",
            required=False,
            query="What is the Letter of Credit Fee rate?",
        ),
        ExtractionField(
            id="fronting_fee_rate",
            name="Fronting Fee Rate",
            field_type=FieldType.PERCENTAGE,
            description="LC fronting fee rate",
            required=False,
            query="What is the Fronting Fee rate?",
        ),
        ExtractionField(
            id="agency_fee",
            name="Agency Fee",
            field_type=FieldType.CURRENCY,
            description="Annual administrative agent fee",
            required=False,
            query="What is the Agency Fee?",
        ),
        # === Financial Covenants ===
        ExtractionField(
            id="fixed_charge_coverage_ratio_min",
            name="Fixed Charge Coverage Ratio Minimum",
            field_type=FieldType.NUMBER,
            description="Minimum FCCR requirement",
            required=False,
            query="What is the minimum Fixed Charge Coverage Ratio?",
            min_value=0.5,
            max_value=3.0,
        ),
        ExtractionField(
            id="leverage_ratio_max",
            name="Maximum Leverage Ratio",
            field_type=FieldType.NUMBER,
            description="Maximum leverage ratio",
            required=False,
            query="What is the maximum Leverage Ratio or Debt to EBITDA?",
        ),
        ExtractionField(
            id="covenant_test_period",
            name="Covenant Test Period",
            field_type=FieldType.STRING,
            description="Testing period for financial covenants",
            required=False,
            query="What is the testing period for financial covenants?",
        ),
        # === Lender Commitments (from Schedule 2.01) ===
        ExtractionField(
            id="lender_commitments",
            name="Lender Commitments",
            field_type=FieldType.STRING,
            description="Individual lender commitment schedule",
            required=True,
            method=ExtractionMethod.TEXTRACT_TABLE,
        ),
        ExtractionField(
            id="total_lender_commitment",
            name="Total Lender Commitment",
            field_type=FieldType.CURRENCY,
            description="Total commitment from all lenders",
            required=True,
            query="What is the total commitment amount from all lenders?",
        ),
    ],
)


# ============================================================
# ALL EXTRACTION SCHEMAS REGISTRY
# ============================================================

EXTRACTION_SCHEMAS: dict[str, ExtractionSchema] = {
    PROMISSORY_NOTE_SCHEMA.id: PROMISSORY_NOTE_SCHEMA,
    CLOSING_DISCLOSURE_SCHEMA.id: CLOSING_DISCLOSURE_SCHEMA,
    FORM_1003_SCHEMA.id: FORM_1003_SCHEMA,
    DEED_OF_TRUST_SCHEMA.id: DEED_OF_TRUST_SCHEMA,
    BANK_STATEMENT_SCHEMA.id: BANK_STATEMENT_SCHEMA,
    W2_SCHEMA.id: W2_SCHEMA,
    CREDIT_AGREEMENT_SCHEMA.id: CREDIT_AGREEMENT_SCHEMA,
}


def get_extraction_schema(schema_id: str) -> Optional[ExtractionSchema]:
    """Get extraction schema by ID."""
    return EXTRACTION_SCHEMAS.get(schema_id)


def get_textract_queries(schema_id: str) -> list[str]:
    """Get all Textract queries for a schema."""
    schema = get_extraction_schema(schema_id)
    if not schema:
        return []

    queries = []
    for field in schema.fields:
        if field.method == ExtractionMethod.TEXTRACT_QUERY and field.query:
            queries.append(field.query)

    return queries


def get_required_fields(schema_id: str) -> list[ExtractionField]:
    """Get all required fields for a schema."""
    schema = get_extraction_schema(schema_id)
    if not schema:
        return []

    return [f for f in schema.fields if f.required]


def get_pii_fields(schema_id: str) -> list[ExtractionField]:
    """Get all PII fields for a schema (for masking/security)."""
    schema = get_extraction_schema(schema_id)
    if not schema:
        return []

    return [f for f in schema.fields if f.pii]
