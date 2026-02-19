"""W-2 Wage and Tax Statement plugin configuration."""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    "plugin_id": "w2",
    "plugin_version": "1.0.0",
    "name": "W-2 Wage and Tax Statement",
    "description": (
        "IRS Form W-2 reporting annual wages, tips, and tax withholdings. "
        "Single-page form with employer/employee info and 20 numbered boxes."
    ),

    "classification": {
        "keywords": [
            "w-2", "w2", "wage and tax statement",
            "employer identification number", "ein",
            "employee's social security number",
            "wages tips other compensation",
            "federal income tax withheld",
            "social security wages", "social security tax withheld",
            "medicare wages", "medicare tax withheld",
            "department of the treasury", "internal revenue service",
            "form w-2", "copy b",
        ],
        "has_sections": False,
        "target_all_pages": True,
        "min_keyword_matches": 3,
        "typical_pages": "1-2 pages",
        "distinguishing_rules": [
            "IRS Form W-2 with numbered boxes (1-20) for wage/tax data",
            "NOT a W-9 (Request for Taxpayer ID) or 1099 (Independent Contractor)",
        ],
    },

    "sections": {
        "w2_form": {
            "name": "W-2 Form",
            "description": "Complete W-2 form with employer, employee, and tax data",
            "max_pages": 2,
            "classification_hints": {
                "keywords": ["w-2", "wage and tax statement", "employer identification"],
                "min_keyword_matches": 1,
                "max_pages": 2,
            },
            "textract_features": ["FORMS", "QUERIES"],
            "queries": [
                "What is the Employer's name and address?",
                "What is the Employer Identification Number (EIN)?",
                "What is the Employee's name?",
                "What is the Employee's Social Security Number?",
                "What is the Employee's address?",
                "What are the Wages, tips, other compensation (Box 1)?",
                "What is the Federal income tax withheld (Box 2)?",
                "What are the Social security wages (Box 3)?",
                "What is the Social security tax withheld (Box 4)?",
                "What are the Medicare wages and tips (Box 5)?",
                "What is the Medicare tax withheld (Box 6)?",
                "What are the Social security tips (Box 7)?",
                "What is the Allocated tips (Box 8)?",
                "What is the Dependent care benefits (Box 10)?",
                "What are the Nonqualified plans (Box 11)?",
                "What is the State wages (Box 16)?",
                "What is the State income tax (Box 17)?",
                "What is the Local wages (Box 18)?",
                "What is the Local income tax (Box 19)?",
                "What is the tax year?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 200,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "employer_name", "employer_ein", "employer_address",
                "employee_name", "employee_ssn", "employee_address",
                "box1_wages", "box2_federal_tax", "box3_ss_wages",
                "box4_ss_tax", "box5_medicare_wages", "box6_medicare_tax",
                "box16_state_wages", "box17_state_tax", "tax_year",
            ],
        },
    },

    "normalization": {
        "prompt_template": "w2",
        "llm_model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "max_tokens": 4096,
        "temperature": 0.0,
    },

    "output_schema": {
        "type": "object",
        "properties": {
            "w2": {
                "type": "object",
                "properties": {
                    "taxYear": {"type": ["string", "null"]},
                    "employer": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "ein": {"type": ["string", "null"]},
                            "address": {"type": ["string", "null"]},
                            "stateId": {"type": ["string", "null"]},
                        },
                    },
                    "employee": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "ssn": {"type": ["string", "null"]},
                            "address": {"type": ["string", "null"]},
                        },
                    },
                    "wages": {
                        "type": "object",
                        "properties": {
                            "box1WagesTipsComp": {"type": ["number", "null"]},
                            "box2FederalTaxWithheld": {"type": ["number", "null"]},
                            "box3SocialSecurityWages": {"type": ["number", "null"]},
                            "box4SocialSecurityTax": {"type": ["number", "null"]},
                            "box5MedicareWages": {"type": ["number", "null"]},
                            "box6MedicareTax": {"type": ["number", "null"]},
                            "box7SocialSecurityTips": {"type": ["number", "null"]},
                            "box8AllocatedTips": {"type": ["number", "null"]},
                            "box10DependentCareBenefits": {"type": ["number", "null"]},
                            "box11NonqualifiedPlans": {"type": ["number", "null"]},
                            "box12Codes": {"type": "array"},
                            "box13Statutory": {"type": ["boolean", "null"]},
                            "box13RetirementPlan": {"type": ["boolean", "null"]},
                            "box13ThirdPartySickPay": {"type": ["boolean", "null"]},
                        },
                    },
                    "state": {
                        "type": "object",
                        "properties": {
                            "stateCode": {"type": ["string", "null"]},
                            "box15StateId": {"type": ["string", "null"]},
                            "box16StateWages": {"type": ["number", "null"]},
                            "box17StateIncomeTax": {"type": ["number", "null"]},
                            "box18LocalWages": {"type": ["number", "null"]},
                            "box19LocalIncomeTax": {"type": ["number", "null"]},
                            "box20LocalityName": {"type": ["string", "null"]},
                        },
                    },
                },
            },
        },
    },

    "pii_paths": [
        {"json_path": "w2.employee.ssn", "pii_type": "ssn", "masking_strategy": "partial"},
    ],

    "cost_budget": {
        "max_cost_usd": 0.20,
        "warn_cost_usd": 0.10,
        "textract_cost_per_page": 0.02,
        "section_priority": {"w2_form": 1},
    },

    "supports_deduplication": True,
    "supports_review_workflow": True,
    "requires_signatures": False,

    "legacy_section_map": {
        "W2": "w2",
        "W-2": "w2",
        "w2": "w2",
    },
}
