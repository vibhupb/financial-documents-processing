"""Driver's License plugin configuration."""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    "plugin_id": "drivers_license",
    "plugin_version": "1.0.0",
    "name": "Driver's License",
    "description": (
        "US state-issued driver's license or identification card. "
        "Single-page ID document with photo, personal info, and license details."
    ),

    "classification": {
        "keywords": [
            "driver license", "driver's license", "drivers license",
            "identification card", "state id",
            "class", "endorsements", "restrictions",
            "date of birth", "dob", "exp", "expires",
            "iss", "issued", "height", "weight", "eyes",
            "department of motor vehicles", "dmv",
            "operator license", "real id",
        ],
        "has_sections": False,
        "target_all_pages": True,
        "min_keyword_matches": 3,
        "typical_pages": "1 page",
        "distinguishing_rules": [
            "Physical ID card with photo, barcode, and personal details",
            "NOT a passport (no visa pages or country of citizenship fields)",
        ],
    },

    "sections": {
        "id_card": {
            "name": "Driver's License / ID Card",
            "description": "Complete ID card with personal info and license details",
            "max_pages": 2,
            "classification_hints": {
                "keywords": ["driver", "license", "identification", "class", "exp"],
                "min_keyword_matches": 2,
                "max_pages": 2,
            },
            "textract_features": ["QUERIES", "FORMS"],
            "queries": [
                "What is the full name on this ID?",
                "What is the date of birth?",
                "What is the address?",
                "What is the license or ID number?",
                "What is the expiration date?",
                "What is the issue date?",
                "What is the license class?",
                "What state issued this ID?",
                "What is the sex/gender?",
                "What is the height?",
                "What is the eye color?",
                "What are the restrictions or endorsements?",
                "Is this a REAL ID?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 300,
            "low_quality_fallback": False,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "full_name", "date_of_birth", "address", "license_number",
                "expiration_date", "issue_date", "class", "state",
                "sex", "height", "eye_color", "restrictions",
            ],
        },
    },

    "normalization": {
        "prompt_template": "drivers_license",
        "llm_model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "max_tokens": 2048,
        "temperature": 0.0,
    },

    "output_schema": {
        "type": "object",
        "properties": {
            "driversLicense": {
                "type": "object",
                "properties": {
                    "fullName": {"type": ["string", "null"]},
                    "firstName": {"type": ["string", "null"]},
                    "middleName": {"type": ["string", "null"]},
                    "lastName": {"type": ["string", "null"]},
                    "dateOfBirth": {"type": ["string", "null"]},
                    "address": {
                        "type": "object",
                        "properties": {
                            "street": {"type": ["string", "null"]},
                            "city": {"type": ["string", "null"]},
                            "state": {"type": ["string", "null"]},
                            "zipCode": {"type": ["string", "null"]},
                        },
                    },
                    "licenseNumber": {"type": ["string", "null"]},
                    "licenseClass": {"type": ["string", "null"]},
                    "issuingState": {"type": ["string", "null"]},
                    "issueDate": {"type": ["string", "null"]},
                    "expirationDate": {"type": ["string", "null"]},
                    "sex": {"type": ["string", "null"]},
                    "height": {"type": ["string", "null"]},
                    "weight": {"type": ["string", "null"]},
                    "eyeColor": {"type": ["string", "null"]},
                    "hairColor": {"type": ["string", "null"]},
                    "restrictions": {"type": ["string", "null"]},
                    "endorsements": {"type": ["string", "null"]},
                    "isRealId": {"type": ["boolean", "null"]},
                    "documentType": {"type": ["string", "null"]},
                },
            },
        },
    },

    "pii_paths": [
        {"json_path": "driversLicense.dateOfBirth", "pii_type": "dob", "masking_strategy": "full"},
        {"json_path": "driversLicense.licenseNumber", "pii_type": "government_id", "masking_strategy": "partial"},
    ],

    "cost_budget": {
        "max_cost_usd": 0.15,
        "warn_cost_usd": 0.08,
        "textract_cost_per_page": 0.02,
        "section_priority": {"id_card": 1},
    },

    "supports_deduplication": True,
    "supports_review_workflow": True,
    "requires_signatures": False,

    "legacy_section_map": {
        "DRIVERS_LICENSE": "drivers_license",
        "drivers_license": "drivers_license",
        "IDENTITY": "drivers_license",
    },
}
