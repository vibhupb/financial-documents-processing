"""Document classification types and categories.

This module defines all supported document types for classification.
Each document type has:
- A unique identifier
- Display name
- Category (mortgage, legal, financial, etc.)
- Keywords for classification
- Required extraction schema
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DocumentCategory(str, Enum):
    """High-level document categories."""

    MORTGAGE = "mortgage"
    LOAN = "loan"
    LEGAL = "legal"
    FINANCIAL = "financial"
    IDENTITY = "identity"
    INSURANCE = "insurance"
    TAX = "tax"
    UNKNOWN = "unknown"


@dataclass
class DocumentType:
    """Definition of a document type for classification."""

    id: str  # Unique identifier (e.g., "promissory_note")
    name: str  # Display name (e.g., "Promissory Note")
    category: DocumentCategory
    description: str
    keywords: list[str] = field(default_factory=list)  # Keywords for classification
    aliases: list[str] = field(default_factory=list)  # Alternative names
    required: bool = False  # Required for the document package
    extraction_schema: Optional[str] = None  # Schema ID for extraction
    typical_pages: int = 1  # Typical number of pages


# ============================================================
# MORTGAGE DOCUMENTS
# ============================================================

PROMISSORY_NOTE = DocumentType(
    id="promissory_note",
    name="Promissory Note",
    category=DocumentCategory.MORTGAGE,
    description="Legal promise to repay the mortgage loan",
    keywords=[
        "promissory note",
        "note",
        "promise to pay",
        "principal amount",
        "interest rate",
        "monthly payment",
        "maturity date",
        "borrower agrees to pay",
    ],
    aliases=["mortgage note", "loan note"],
    required=True,
    extraction_schema="promissory_note",
    typical_pages=3,
)

CLOSING_DISCLOSURE = DocumentType(
    id="closing_disclosure",
    name="Closing Disclosure",
    category=DocumentCategory.MORTGAGE,
    description="Final statement of loan terms and closing costs",
    keywords=[
        "closing disclosure",
        "loan terms",
        "projected payments",
        "closing costs",
        "cash to close",
        "loan estimate",
        "trid",
        "cfpb",
    ],
    aliases=["cd", "hud-1", "settlement statement"],
    required=True,
    extraction_schema="closing_disclosure",
    typical_pages=5,
)

UNIFORM_RESIDENTIAL_LOAN_APPLICATION = DocumentType(
    id="form_1003",
    name="Uniform Residential Loan Application (Form 1003)",
    category=DocumentCategory.MORTGAGE,
    description="Standard mortgage application form",
    keywords=[
        "uniform residential loan application",
        "form 1003",
        "urla",
        "borrower information",
        "employment information",
        "assets and liabilities",
        "declarations",
    ],
    aliases=["1003", "urla", "fnma 1003", "loan application"],
    required=True,
    extraction_schema="form_1003",
    typical_pages=8,
)

DEED_OF_TRUST = DocumentType(
    id="deed_of_trust",
    name="Deed of Trust",
    category=DocumentCategory.MORTGAGE,
    description="Security instrument that pledges property as collateral",
    keywords=[
        "deed of trust",
        "security instrument",
        "trustee",
        "beneficiary",
        "grantor",
        "property description",
        "legal description",
    ],
    aliases=["mortgage deed", "trust deed", "security deed"],
    required=True,
    extraction_schema="deed_of_trust",
    typical_pages=15,
)

APPRAISAL_REPORT = DocumentType(
    id="appraisal",
    name="Appraisal Report",
    category=DocumentCategory.MORTGAGE,
    description="Professional property valuation",
    keywords=[
        "appraisal",
        "appraised value",
        "market value",
        "comparable sales",
        "urar",
        "property valuation",
    ],
    aliases=["urar", "property appraisal"],
    required=False,
    extraction_schema="appraisal",
    typical_pages=30,
)

TITLE_INSURANCE = DocumentType(
    id="title_insurance",
    name="Title Insurance Policy",
    category=DocumentCategory.MORTGAGE,
    description="Insurance protecting against title defects",
    keywords=[
        "title insurance",
        "title policy",
        "alta",
        "endorsement",
        "schedule a",
        "schedule b",
    ],
    aliases=["title policy", "alta policy"],
    required=False,
    extraction_schema="title_insurance",
    typical_pages=10,
)

# ============================================================
# LOAN DOCUMENTS (Non-Mortgage)
# ============================================================

PERSONAL_LOAN_AGREEMENT = DocumentType(
    id="personal_loan",
    name="Personal Loan Agreement",
    category=DocumentCategory.LOAN,
    description="Agreement for personal/consumer loan",
    keywords=[
        "personal loan",
        "consumer loan",
        "loan agreement",
        "repayment terms",
        "annual percentage rate",
        "apr",
    ],
    aliases=["consumer loan agreement"],
    required=True,
    extraction_schema="personal_loan",
    typical_pages=5,
)

BUSINESS_LOAN_AGREEMENT = DocumentType(
    id="business_loan",
    name="Business Loan Agreement",
    category=DocumentCategory.LOAN,
    description="Commercial/business loan documentation",
    keywords=[
        "business loan",
        "commercial loan",
        "term loan",
        "line of credit",
        "sba loan",
        "business credit",
    ],
    aliases=["commercial loan", "term loan agreement"],
    required=True,
    extraction_schema="business_loan",
    typical_pages=20,
)

AUTO_LOAN_CONTRACT = DocumentType(
    id="auto_loan",
    name="Auto Loan Contract",
    category=DocumentCategory.LOAN,
    description="Vehicle financing agreement",
    keywords=[
        "auto loan",
        "vehicle loan",
        "retail installment",
        "vin",
        "vehicle identification",
        "motor vehicle",
    ],
    aliases=["car loan", "vehicle financing"],
    required=True,
    extraction_schema="auto_loan",
    typical_pages=4,
)

# ============================================================
# LEGAL DOCUMENTS
# ============================================================

POWER_OF_ATTORNEY = DocumentType(
    id="power_of_attorney",
    name="Power of Attorney",
    category=DocumentCategory.LEGAL,
    description="Legal authorization to act on behalf of another",
    keywords=[
        "power of attorney",
        "poa",
        "attorney-in-fact",
        "principal",
        "durable power",
        "limited power",
    ],
    aliases=["poa", "limited poa", "durable poa"],
    required=False,
    extraction_schema="power_of_attorney",
    typical_pages=5,
)

TRUST_AGREEMENT = DocumentType(
    id="trust_agreement",
    name="Trust Agreement",
    category=DocumentCategory.LEGAL,
    description="Legal document establishing a trust",
    keywords=[
        "trust agreement",
        "revocable trust",
        "irrevocable trust",
        "trustee",
        "beneficiary",
        "grantor",
        "living trust",
    ],
    aliases=["trust document", "declaration of trust"],
    required=False,
    extraction_schema="trust_agreement",
    typical_pages=20,
)

LLC_OPERATING_AGREEMENT = DocumentType(
    id="llc_operating_agreement",
    name="LLC Operating Agreement",
    category=DocumentCategory.LEGAL,
    description="Governance document for LLC",
    keywords=[
        "operating agreement",
        "llc",
        "limited liability",
        "member",
        "manager",
        "membership interest",
    ],
    aliases=["llc agreement", "operating agreement"],
    required=False,
    extraction_schema="llc_operating_agreement",
    typical_pages=15,
)

ARTICLES_OF_INCORPORATION = DocumentType(
    id="articles_of_incorporation",
    name="Articles of Incorporation",
    category=DocumentCategory.LEGAL,
    description="Corporate formation document",
    keywords=[
        "articles of incorporation",
        "certificate of incorporation",
        "corporate charter",
        "incorporator",
        "registered agent",
    ],
    aliases=["certificate of incorporation", "corporate charter"],
    required=False,
    extraction_schema="articles_of_incorporation",
    typical_pages=5,
)

# ============================================================
# FINANCIAL DOCUMENTS
# ============================================================

BANK_STATEMENT = DocumentType(
    id="bank_statement",
    name="Bank Statement",
    category=DocumentCategory.FINANCIAL,
    description="Monthly account statement from financial institution",
    keywords=[
        "bank statement",
        "account statement",
        "checking account",
        "savings account",
        "beginning balance",
        "ending balance",
    ],
    aliases=["account statement"],
    required=False,
    extraction_schema="bank_statement",
    typical_pages=5,
)

PAY_STUB = DocumentType(
    id="pay_stub",
    name="Pay Stub",
    category=DocumentCategory.FINANCIAL,
    description="Earnings statement from employer",
    keywords=[
        "pay stub",
        "earnings statement",
        "gross pay",
        "net pay",
        "ytd",
        "deductions",
        "federal withholding",
    ],
    aliases=["paycheck stub", "earnings statement"],
    required=False,
    extraction_schema="pay_stub",
    typical_pages=2,
)

PROFIT_LOSS_STATEMENT = DocumentType(
    id="profit_loss",
    name="Profit & Loss Statement",
    category=DocumentCategory.FINANCIAL,
    description="Business income statement",
    keywords=[
        "profit and loss",
        "p&l",
        "income statement",
        "revenue",
        "expenses",
        "net income",
        "gross profit",
    ],
    aliases=["p&l", "income statement"],
    required=False,
    extraction_schema="profit_loss",
    typical_pages=3,
)

BALANCE_SHEET = DocumentType(
    id="balance_sheet",
    name="Balance Sheet",
    category=DocumentCategory.FINANCIAL,
    description="Statement of assets and liabilities",
    keywords=[
        "balance sheet",
        "assets",
        "liabilities",
        "equity",
        "current assets",
        "fixed assets",
    ],
    aliases=["statement of financial position"],
    required=False,
    extraction_schema="balance_sheet",
    typical_pages=2,
)

# ============================================================
# IDENTITY DOCUMENTS
# ============================================================

DRIVERS_LICENSE = DocumentType(
    id="drivers_license",
    name="Driver's License",
    category=DocumentCategory.IDENTITY,
    description="State-issued identification",
    keywords=[
        "driver license",
        "drivers license",
        "dl",
        "date of birth",
        "expiration date",
        "license number",
    ],
    aliases=["dl", "state id"],
    required=False,
    extraction_schema="drivers_license",
    typical_pages=1,
)

PASSPORT = DocumentType(
    id="passport",
    name="Passport",
    category=DocumentCategory.IDENTITY,
    description="Government-issued travel document",
    keywords=[
        "passport",
        "passport number",
        "nationality",
        "date of birth",
        "place of birth",
    ],
    aliases=[],
    required=False,
    extraction_schema="passport",
    typical_pages=2,
)

# ============================================================
# TAX DOCUMENTS
# ============================================================

W2_FORM = DocumentType(
    id="w2",
    name="W-2 Form",
    category=DocumentCategory.TAX,
    description="Wage and Tax Statement",
    keywords=[
        "w-2",
        "w2",
        "wage and tax statement",
        "federal income tax withheld",
        "social security wages",
        "employer identification number",
    ],
    aliases=["wage statement"],
    required=False,
    extraction_schema="w2",
    typical_pages=1,
)

TAX_RETURN_1040 = DocumentType(
    id="tax_return_1040",
    name="Tax Return (Form 1040)",
    category=DocumentCategory.TAX,
    description="Individual income tax return",
    keywords=[
        "form 1040",
        "tax return",
        "adjusted gross income",
        "taxable income",
        "total tax",
        "irs",
    ],
    aliases=["1040", "individual tax return"],
    required=False,
    extraction_schema="tax_return_1040",
    typical_pages=10,
)

TAX_RETURN_BUSINESS = DocumentType(
    id="tax_return_business",
    name="Business Tax Return",
    category=DocumentCategory.TAX,
    description="Business income tax return (1120, 1120S, 1065)",
    keywords=[
        "form 1120",
        "form 1065",
        "corporate tax return",
        "partnership return",
        "s corporation",
    ],
    aliases=["corporate tax return", "partnership return"],
    required=False,
    extraction_schema="tax_return_business",
    typical_pages=30,
)

# ============================================================
# INSURANCE DOCUMENTS
# ============================================================

HOMEOWNERS_INSURANCE = DocumentType(
    id="homeowners_insurance",
    name="Homeowners Insurance Policy",
    category=DocumentCategory.INSURANCE,
    description="Property insurance declarations page",
    keywords=[
        "homeowners insurance",
        "dwelling coverage",
        "liability coverage",
        "declarations page",
        "premium",
        "deductible",
    ],
    aliases=["ho policy", "property insurance"],
    required=False,
    extraction_schema="homeowners_insurance",
    typical_pages=20,
)

FLOOD_INSURANCE = DocumentType(
    id="flood_insurance",
    name="Flood Insurance Policy",
    category=DocumentCategory.INSURANCE,
    description="National Flood Insurance Program policy",
    keywords=[
        "flood insurance",
        "nfip",
        "flood zone",
        "building coverage",
        "contents coverage",
    ],
    aliases=["nfip policy"],
    required=False,
    extraction_schema="flood_insurance",
    typical_pages=10,
)

# ============================================================
# ALL DOCUMENT TYPES REGISTRY
# ============================================================

DOCUMENT_TYPES: dict[str, DocumentType] = {
    # Mortgage
    PROMISSORY_NOTE.id: PROMISSORY_NOTE,
    CLOSING_DISCLOSURE.id: CLOSING_DISCLOSURE,
    UNIFORM_RESIDENTIAL_LOAN_APPLICATION.id: UNIFORM_RESIDENTIAL_LOAN_APPLICATION,
    DEED_OF_TRUST.id: DEED_OF_TRUST,
    APPRAISAL_REPORT.id: APPRAISAL_REPORT,
    TITLE_INSURANCE.id: TITLE_INSURANCE,
    # Loan
    PERSONAL_LOAN_AGREEMENT.id: PERSONAL_LOAN_AGREEMENT,
    BUSINESS_LOAN_AGREEMENT.id: BUSINESS_LOAN_AGREEMENT,
    AUTO_LOAN_CONTRACT.id: AUTO_LOAN_CONTRACT,
    # Legal
    POWER_OF_ATTORNEY.id: POWER_OF_ATTORNEY,
    TRUST_AGREEMENT.id: TRUST_AGREEMENT,
    LLC_OPERATING_AGREEMENT.id: LLC_OPERATING_AGREEMENT,
    ARTICLES_OF_INCORPORATION.id: ARTICLES_OF_INCORPORATION,
    # Financial
    BANK_STATEMENT.id: BANK_STATEMENT,
    PAY_STUB.id: PAY_STUB,
    PROFIT_LOSS_STATEMENT.id: PROFIT_LOSS_STATEMENT,
    BALANCE_SHEET.id: BALANCE_SHEET,
    # Identity
    DRIVERS_LICENSE.id: DRIVERS_LICENSE,
    PASSPORT.id: PASSPORT,
    # Tax
    W2_FORM.id: W2_FORM,
    TAX_RETURN_1040.id: TAX_RETURN_1040,
    TAX_RETURN_BUSINESS.id: TAX_RETURN_BUSINESS,
    # Insurance
    HOMEOWNERS_INSURANCE.id: HOMEOWNERS_INSURANCE,
    FLOOD_INSURANCE.id: FLOOD_INSURANCE,
}


def get_document_type(type_id: str) -> Optional[DocumentType]:
    """Get document type by ID."""
    return DOCUMENT_TYPES.get(type_id)


def get_category_types(category: DocumentCategory) -> list[DocumentType]:
    """Get all document types in a category."""
    return [dt for dt in DOCUMENT_TYPES.values() if dt.category == category]


def get_required_types(category: Optional[DocumentCategory] = None) -> list[DocumentType]:
    """Get all required document types, optionally filtered by category."""
    types = DOCUMENT_TYPES.values()
    if category:
        types = [dt for dt in types if dt.category == category]
    return [dt for dt in types if dt.required]


def get_classification_prompt() -> str:
    """Generate classification prompt for LLM."""
    categories = {}
    for dt in DOCUMENT_TYPES.values():
        if dt.category not in categories:
            categories[dt.category] = []
        categories[dt.category].append(dt)

    prompt_parts = ["Classify the document into one of these types:\n"]

    for category, types in categories.items():
        prompt_parts.append(f"\n## {category.value.upper()}\n")
        for dt in types:
            keywords = ", ".join(dt.keywords[:5])
            prompt_parts.append(f"- **{dt.id}**: {dt.name} (keywords: {keywords})")

    return "\n".join(prompt_parts)
