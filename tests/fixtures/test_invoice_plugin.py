"""Synthetic invoice plugin configuration for integration testing.

This is NOT a production plugin -- it lives in tests/fixtures/ and is loaded
dynamically by integration tests to verify the plugin registry, router,
extractor, and normalizer without requiring a real document type deployment.
"""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    "plugin_id": "test_invoice",
    "plugin_version": "1.0.0",
    "name": "Test Invoice",
    "description": (
        "Synthetic invoice for integration testing. "
        "Short-form document with vendor info, line items, and payment terms."
    ),

    "classification": {
        "keywords": [
            "invoice", "vendor", "amount due",
            "line items", "payment terms",
        ],
        "has_sections": False,
        "target_all_pages": True,
        "min_keyword_matches": 2,
        "typical_pages": "1-2 pages",
        "distinguishing_rules": [
            "Commercial invoice with vendor name, line items table, and total amount",
            "NOT a purchase order, receipt, or statement of account",
        ],
    },

    "sections": {
        "invoice_data": {
            "name": "Invoice Data",
            "description": "Complete invoice with vendor, line items, and payment terms",
            "max_pages": 3,
            "classification_hints": {
                "keywords": ["invoice", "amount due", "vendor", "total"],
                "min_keyword_matches": 1,
                "max_pages": 3,
            },
            "textract_features": ["FORMS", "QUERIES"],
            "queries": [
                "What is the vendor name?",
                "What is the total amount?",
                "What is the invoice date?",
            ],
            "include_pypdf_text": True,
            "render_as_images": False,
            "render_dpi": 150,
            "low_quality_fallback": False,
            "parallel_extraction": False,
            "extract_tables": True,
            "extract_signatures": False,
            "extraction_fields": [
                "vendor", "amount", "invoice_date",
                "line_items", "payment_terms",
            ],
        },
    },

    "normalization": {
        "prompt_template": "test_invoice",
        "llm_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "max_tokens": 4096,
        "temperature": 0.0,
    },

    "output_schema": {
        "type": "object",
        "properties": {
            "invoice": {
                "type": "object",
                "properties": {
                    "vendor": {"type": ["string", "null"]},
                    "amount": {"type": ["string", "null"]},
                    "invoiceDate": {"type": ["string", "null"]},
                    "lineItems": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": ["string", "null"]},
                                "amount": {"type": ["number", "null"]},
                            },
                        },
                    },
                    "paymentTerms": {"type": ["string", "null"]},
                },
            },
        },
    },

    "pii_paths": [],

    "cost_budget": {
        "max_cost_usd": 0.15,
        "warn_cost_usd": 0.08,
        "textract_cost_per_page": 0.02,
        "section_priority": {"invoice_data": 1},
    },

    "supports_deduplication": True,
    "supports_review_workflow": False,
    "requires_signatures": False,

    "legacy_section_map": {
        "Invoice": "invoice_data",
        "invoice": "invoice_data",
    },
}
