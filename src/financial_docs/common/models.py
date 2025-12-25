"""Data models for Financial Documents Processing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum


class DocumentType(str, Enum):
    """Types of documents that can be classified."""
    PROMISSORY_NOTE = "promissoryNote"
    CLOSING_DISCLOSURE = "closingDisclosure"
    FORM_1003 = "form1003"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """Processing status for documents."""
    PENDING = "PENDING"
    CLASSIFIED = "CLASSIFIED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    NORMALIZING = "NORMALIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ConfidenceLevel(str, Enum):
    """Confidence level for classifications and extractions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DocumentClassification:
    """Result of document classification by the Router."""

    promissory_note_page: Optional[int] = None
    closing_disclosure_page: Optional[int] = None
    form_1003_page: Optional[int] = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    total_pages_analyzed: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "promissoryNote": self.promissory_note_page,
            "closingDisclosure": self.closing_disclosure_page,
            "form1003": self.form_1003_page,
            "confidence": self.confidence.value,
            "totalPagesAnalyzed": self.total_pages_analyzed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentClassification":
        """Create from dictionary."""
        return cls(
            promissory_note_page=data.get("promissoryNote"),
            closing_disclosure_page=data.get("closingDisclosure"),
            form_1003_page=data.get("form1003"),
            confidence=ConfidenceLevel(data.get("confidence", "low")),
            total_pages_analyzed=data.get("totalPagesAnalyzed", 0),
        )


@dataclass
class ExtractionResult:
    """Result of Textract extraction from a specific page."""

    document_id: str
    extraction_type: str  # QUERIES, TABLES, FORMS
    page_number: Optional[int]
    status: ProcessingStatus
    results: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "documentId": self.document_id,
            "extractionType": self.extraction_type,
            "pageNumber": self.page_number,
            "status": self.status.value,
            "results": self.results,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class PromissoryNoteData:
    """Normalized data from Promissory Note."""
    interest_rate: Optional[float] = None
    principal_amount: Optional[float] = None
    borrower_name: Optional[str] = None
    co_borrower_name: Optional[str] = None
    maturity_date: Optional[str] = None  # ISO format
    monthly_payment: Optional[float] = None
    first_payment_date: Optional[str] = None


@dataclass
class ClosingDisclosureData:
    """Normalized data from Closing Disclosure."""
    loan_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    monthly_principal_and_interest: Optional[float] = None
    estimated_total_monthly_payment: Optional[float] = None
    closing_costs: Optional[float] = None
    cash_to_close: Optional[float] = None
    fees: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BorrowerInfo:
    """Borrower information from Form 1003."""
    name: Optional[str] = None
    ssn: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


@dataclass
class PropertyAddress:
    """Property address from Form 1003."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


@dataclass
class EmploymentInfo:
    """Employment information from Form 1003."""
    employer_name: Optional[str] = None
    position: Optional[str] = None
    years_employed: Optional[int] = None
    monthly_income: Optional[float] = None


@dataclass
class Form1003Data:
    """Normalized data from Form 1003."""
    borrower_info: BorrowerInfo = field(default_factory=BorrowerInfo)
    property_address: PropertyAddress = field(default_factory=PropertyAddress)
    employment_info: EmploymentInfo = field(default_factory=EmploymentInfo)


@dataclass
class ValidationResult:
    """Validation result for normalized data."""
    is_valid: bool = False
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    cross_reference_checks: list[dict[str, Any]] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    missing_required_fields: list[str] = field(default_factory=list)


@dataclass
class NormalizedLoanData:
    """Complete normalized loan data package."""

    document_id: str
    promissory_note: PromissoryNoteData = field(default_factory=PromissoryNoteData)
    closing_disclosure: ClosingDisclosureData = field(default_factory=ClosingDisclosureData)
    form_1003: Form1003Data = field(default_factory=Form1003Data)
    validation: ValidationResult = field(default_factory=ValidationResult)
    processed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "documentId": self.document_id,
            "loanData": {
                "promissoryNote": {
                    "interestRate": self.promissory_note.interest_rate,
                    "principalAmount": self.promissory_note.principal_amount,
                    "borrowerName": self.promissory_note.borrower_name,
                    "coBorrowerName": self.promissory_note.co_borrower_name,
                    "maturityDate": self.promissory_note.maturity_date,
                    "monthlyPayment": self.promissory_note.monthly_payment,
                    "firstPaymentDate": self.promissory_note.first_payment_date,
                },
                "closingDisclosure": {
                    "loanAmount": self.closing_disclosure.loan_amount,
                    "interestRate": self.closing_disclosure.interest_rate,
                    "monthlyPrincipalAndInterest": self.closing_disclosure.monthly_principal_and_interest,
                    "estimatedTotalMonthlyPayment": self.closing_disclosure.estimated_total_monthly_payment,
                    "closingCosts": self.closing_disclosure.closing_costs,
                    "cashToClose": self.closing_disclosure.cash_to_close,
                    "fees": self.closing_disclosure.fees,
                },
                "form1003": {
                    "borrowerInfo": {
                        "name": self.form_1003.borrower_info.name,
                        "ssn": self.form_1003.borrower_info.ssn,
                        "dateOfBirth": self.form_1003.borrower_info.date_of_birth,
                        "phone": self.form_1003.borrower_info.phone,
                        "email": self.form_1003.borrower_info.email,
                    },
                    "propertyAddress": {
                        "street": self.form_1003.property_address.street,
                        "city": self.form_1003.property_address.city,
                        "state": self.form_1003.property_address.state,
                        "zipCode": self.form_1003.property_address.zip_code,
                    },
                    "employmentInfo": {
                        "employerName": self.form_1003.employment_info.employer_name,
                        "position": self.form_1003.employment_info.position,
                        "yearsEmployed": self.form_1003.employment_info.years_employed,
                        "monthlyIncome": self.form_1003.employment_info.monthly_income,
                    },
                },
            },
            "validation": {
                "isValid": self.validation.is_valid,
                "confidence": self.validation.confidence.value,
                "crossReferenceChecks": self.validation.cross_reference_checks,
                "validationNotes": self.validation.validation_notes,
                "missingRequiredFields": self.validation.missing_required_fields,
            },
            "processedAt": self.processed_at,
        }
