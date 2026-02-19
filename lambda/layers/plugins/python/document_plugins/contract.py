"""Plugin Contract - TypedDict hierarchy defining the structure all plugin configs must conform to.

This module defines the canonical shape of a document plugin configuration.
Every plugin in types/ must export a PLUGIN_CONFIG dict that matches
DocumentPluginConfig.

Design decision: TypedDicts over Pydantic for zero-dependency, zero-import-cost,
native JSON serialization. Pydantic adds 15MB and 200ms Lambda cold start.
"""

from typing import TypedDict, List, Optional, Dict, Any, NotRequired


# ---------------------------------------------------------------------------
# Validation & Field Definitions
# ---------------------------------------------------------------------------

class ValidationConstraint(TypedDict, total=False):
    """Constraints for field-level validation during normalization."""
    min_value: float
    max_value: float
    regex: str
    allowed_values: List[str]


class FieldDefinition(TypedDict, total=False):
    """A single extractable field within a section."""
    id: str
    name: str
    field_type: str  # "string" | "number" | "currency" | "percentage" | "date" | "boolean"
    required: bool
    method: str  # "query" | "table" | "form" | "text"
    description: str
    validation: ValidationConstraint


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class PageBonusRule(TypedDict):
    """Declarative scoring rule for page ranking during section identification.

    Replaces the hardcoded Credit Agreement-specific scoring in
    identify_credit_agreement_sections() with generic, config-driven rules.
    """
    condition: str  # "contains_any" | "contains_all" | "regex_match" | "last_n_pages" | "first_n_pages"
    patterns: List[str]
    bonus: int


class ClassificationConfig(TypedDict, total=False):
    """How the router identifies this document type and locates sections."""
    keywords: List[str]
    has_sections: bool
    section_names: List[str]
    target_all_pages: bool
    expected_page_count: int
    min_keyword_matches: int
    typical_pages: str
    distinguishing_rules: List[str]
    page_bonus_rules: List[PageBonusRule]


# ---------------------------------------------------------------------------
# Section-Level Extraction Config
# ---------------------------------------------------------------------------

class SectionClassificationHints(TypedDict, total=False):
    """Per-section keyword scoring for the generic identify_sections() algorithm."""
    keywords: List[str]
    min_keyword_matches: int
    max_pages: int
    typical_pages: str
    search_schedule_pages: bool
    search_last_pages: bool
    page_bonus_rules: List[PageBonusRule]


class SectionConfig(TypedDict, total=False):
    """Configuration for a single extraction section within a document type.

    Each section maps to one iteration of the Step Functions Map state.
    The extractor Lambda reads these fields to determine what Textract
    features to invoke and which queries to run.
    """
    name: str
    description: str
    max_pages: int
    classification_hints: SectionClassificationHints
    textract_features: List[str]  # ["QUERIES"] | ["TABLES"] | ["FORMS"] | ["FORMS", "TABLES"] | ["QUERIES", "TABLES"]
    queries: List[str]
    include_pypdf_text: bool
    render_as_images: bool
    render_dpi: int
    low_quality_fallback: bool
    parallel_extraction: bool
    extract_tables: bool
    extract_signatures: bool
    extraction_fields: List[str]
    fields: List[FieldDefinition]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

class NormalizationConfig(TypedDict, total=False):
    """How the normalizer Lambda processes raw extraction results."""
    prompt_template: str  # Filename in prompts/ directory or inline template key
    llm_model: str  # e.g. "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    max_tokens: int
    temperature: float
    field_overrides: Dict[str, str]  # field_name -> override instruction


# ---------------------------------------------------------------------------
# PII Markers
# ---------------------------------------------------------------------------

class PIIPathMarker(TypedDict):
    """JSON-path-based PII field marker for encryption/masking.

    Uses path patterns to support deeply nested structures like
    beneficial owners arrays: "beneficialOwners[*].ssn"
    """
    json_path: str  # e.g., "beneficialOwners[*].ssn", "legalEntity.taxId"
    pii_type: str  # "ssn" | "dob" | "tax_id" | "government_id" | "email" | "phone"
    masking_strategy: str  # "partial" | "full" | "hash"


# ---------------------------------------------------------------------------
# Cost Budget
# ---------------------------------------------------------------------------

class CostBudget(TypedDict, total=False):
    """Cost monitoring thresholds per document."""
    max_cost_usd: float
    warn_cost_usd: float
    textract_cost_per_page: float
    section_priority: Dict[str, int]  # section_id -> priority (lower = higher priority)


# ---------------------------------------------------------------------------
# Top-Level Plugin Config
# ---------------------------------------------------------------------------

class DocumentPluginConfig(TypedDict, total=False):
    """The complete plugin configuration for a document type.

    Every plugin module in types/ must export a PLUGIN_CONFIG dict
    conforming to this shape. The registry auto-discovers and validates
    these configs at import time.
    """
    plugin_id: str
    plugin_version: str
    name: str
    description: str
    classification: ClassificationConfig
    sections: Dict[str, SectionConfig]
    normalization: NormalizationConfig
    output_schema: Dict[str, Any]  # JSON Schema
    pii_paths: List[PIIPathMarker]
    cost_budget: CostBudget
    supports_deduplication: bool
    supports_review_workflow: bool
    requires_signatures: bool
    # Legacy section name mappings for backward compatibility during transition
    legacy_section_map: Dict[str, str]
