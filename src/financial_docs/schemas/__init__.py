"""Document classification and extraction schemas."""

from .document_types import (
    DocumentCategory,
    DocumentType,
    DOCUMENT_TYPES,
    get_document_type,
    get_category_types,
)
from .extraction_fields import (
    FieldType,
    ExtractionField,
    ExtractionSchema,
    EXTRACTION_SCHEMAS,
    get_extraction_schema,
)
from .validation_rules import (
    ValidationRule,
    CrossReferenceRule,
    VALIDATION_RULES,
    get_validation_rules,
)

__all__ = [
    # Document Types
    "DocumentCategory",
    "DocumentType",
    "DOCUMENT_TYPES",
    "get_document_type",
    "get_category_types",
    # Extraction Fields
    "FieldType",
    "ExtractionField",
    "ExtractionSchema",
    "EXTRACTION_SCHEMAS",
    "get_extraction_schema",
    # Validation Rules
    "ValidationRule",
    "CrossReferenceRule",
    "VALIDATION_RULES",
    "get_validation_rules",
]
