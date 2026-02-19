"""Document classification and extraction schemas.

DEPRECATED: This module is superseded by the plugin architecture in
lambda/layers/plugins/python/document_plugins/. These schemas are NOT
imported by any Lambda function. Use document_plugins.registry instead.

Migration: All classification keywords, extraction fields, and validation
rules now live in per-document-type plugin configs under types/.
"""

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
