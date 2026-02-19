"""BSA Profile plugin configuration.

Covers Bank Secrecy Act / Customer Due Diligence (CDD) forms used for
Know Your Customer (KYC) compliance. The form typically spans 5 pages:
  - Page 1: Legal Entity Information (company name, Tax ID, entity type, NAICS, addresses)
  - Page 2: Risk Assessment (AML, PEP, fraud, cash intensive, sector flags)
  - Pages 3-5: Beneficial Ownership / Controlling Party (up to 4 owners + trust info)

This is the first plugin-native document type (not migrated from hardcoded logic).
Uses FORMS+TABLES features for checkbox/selection element extraction.

Classification keywords are BSA-specific to prevent overlap with Form 1003.
PII paths mark fields for KMS envelope encryption post-normalization.
"""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    "plugin_id": "bsa_profile",
    "plugin_version": "1.0.0",
    "name": "BSA Profile",
    "description": (
        "Bank Secrecy Act Customer Due Diligence (CDD) form for "
        "Know Your Customer (KYC) compliance. Contains legal entity "
        "information, risk assessment with checkbox-based flags, "
        "and beneficial ownership declarations. Received via "
        "email/fax/mail in both digitally-filled and handwritten formats."
    ),

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    "classification": {
        "keywords": [
            # Primary BSA identifiers (must not overlap with Form 1003)
            "bsa profile",
            "customer due diligence",
            "cdd form",
            "cdd profile",
            "know your customer",
            "kyc",
            "fincen",
            # Beneficial ownership
            "beneficial ownership",
            "beneficial owner",
            "controlling party",
            "ownership declaration",
            "25% or more",
            "ownership percentage",
            # Risk assessment
            "risk assessment",
            "risk rating",
            "enhanced due diligence",
            "edd",
            "politically exposed person",
            "pep",
            "anti-money laundering",
            "aml",
            "suspicious activity report",
            "sar",
            "ofac",
            # Entity information
            "naics code",
            "entity type",
            "state of organization",
            "cash intensive",
            "money service business",
        ],
        "has_sections": False,
        "target_all_pages": True,
        "expected_page_count": 5,
        "min_keyword_matches": 3,
        "typical_pages": "5 pages (standardized CDD form)",
        "distinguishing_rules": [
            "BSA Profile is a standardized 5-page KYC/CDD compliance form",
            "Distinguished from Form 1003 by BSA/KYC/FinCEN terminology",
            "Contains checkbox-based risk assessment matrix on page 2",
            "Contains beneficial ownership section with up to 4 owners",
            "Must NOT be confused with generic loan applications",
        ],
    },

    # ------------------------------------------------------------------
    # Sections (single section covering all 5 pages)
    # ------------------------------------------------------------------
    "sections": {
        "bsa_profile_all": {
            "name": "BSA Profile (All Pages)",
            "description": (
                "Full BSA/CDD form extraction across all 5 pages. Uses "
                "FORMS for key-value pairs and TABLES for checkbox/radio "
                "button selection elements embedded in table-structured "
                "risk assessment grids. A single extraction section is "
                "used because all pages need the same feature set and "
                "the form is a unified 5-page document."
            ),
            "max_pages": 5,
            "classification_hints": {
                "keywords": [
                    "bsa profile",
                    "customer due diligence",
                    "beneficial ownership",
                    "risk assessment",
                    "know your customer",
                    "naics code",
                ],
                "min_keyword_matches": 2,
                "max_pages": 5,
                "typical_pages": "all 5 pages",
                "page_bonus_rules": [
                    {
                        "condition": "first_n_pages",
                        "patterns": [],
                        "bonus": 100,
                    },
                ],
            },
            "textract_features": ["FORMS", "TABLES"],
            "queries": [],  # BSA uses FORMS, not QUERIES
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 200,  # Higher DPI for handwritten forms
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": True,
            "extract_signatures": True,  # Certification signature on page 5
            "extraction_fields": [
                # Legal Entity (Page 1)
                "companyName",
                "dbaName",
                "taxId",
                "taxIdType",
                "entityType",
                "stateOfOrganization",
                "countryOfOrganization",
                "dateOfOrganization",
                "naicsCode",
                "naicsDescription",
                "businessDescription",
                "principalAddress",
                "phoneNumber",
                "emailAddress",
                "isPubliclyTraded",
                "stockExchange",
                "tickerSymbol",
                "isExemptEntity",
                "exemptionType",
                # Risk Assessment (Page 2)
                "overallRiskRating",
                "hasAmlHistory",
                "hasPepAssociation",
                "hasFraudHistory",
                "hasSarHistory",
                "isOnOfacList",
                "isCashIntensive",
                "isMoneyServiceBusiness",
                "isThirdPartyPaymentProcessor",
                "industryRiskFlags",
                "requiresEdd",
                "eddReason",
                "riskNotes",
                # Beneficial Owners (Pages 3-5)
                "beneficialOwners",
                # Trust Info (Page 5)
                "trustName",
                "trustType",
                "trusteeName",
                "dateEstablished",
                "stateOfFormation",
                "trustTaxId",
                # Certification (Page 5)
                "signatoryName",
                "signatoryTitle",
                "certificationDate",
                "signatureStatus",
            ],
        },
    },

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    "normalization": {
        "prompt_template": "bsa_profile",
        "llm_model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "max_tokens": 8192,
        "temperature": 0.0,
    },

    # ------------------------------------------------------------------
    # Output schema (mirrors BSA TypeScript interfaces)
    # ------------------------------------------------------------------
    "output_schema": {
        "type": "object",
        "properties": {
            "bsaProfile": {
                "type": "object",
                "properties": {
                    "legalEntity": {
                        "type": "object",
                        "properties": {
                            "companyName": {"type": "string"},
                            "dbaName": {"type": "string"},
                            "taxId": {"type": "string"},
                            "taxIdType": {"type": "string"},
                            "entityType": {
                                "type": "string",
                                "enum": [
                                    "Corporation",
                                    "LLC",
                                    "Partnership",
                                    "Sole Proprietorship",
                                    "Trust",
                                    "Non-Profit / Tax-Exempt Organization",
                                    "Government Entity",
                                    "Other",
                                ],
                            },
                            "stateOfOrganization": {"type": "string"},
                            "countryOfOrganization": {"type": "string"},
                            "dateOfOrganization": {"type": "string", "format": "date"},
                            "naicsCode": {"type": "string"},
                            "naicsDescription": {"type": "string"},
                            "businessDescription": {"type": "string"},
                            "principalAddress": {
                                "type": "object",
                                "properties": {
                                    "street": {"type": "string"},
                                    "city": {"type": "string"},
                                    "state": {"type": "string"},
                                    "zipCode": {"type": "string"},
                                    "country": {"type": "string"},
                                },
                            },
                            "phoneNumber": {"type": "string"},
                            "emailAddress": {"type": "string"},
                            "isPubliclyTraded": {"type": "boolean"},
                            "stockExchange": {"type": "string"},
                            "tickerSymbol": {"type": "string"},
                            "isExemptEntity": {"type": "boolean"},
                            "exemptionType": {"type": "string"},
                        },
                    },
                    "riskAssessment": {
                        "type": "object",
                        "properties": {
                            "overallRiskRating": {
                                "type": "string",
                                "enum": ["LOW", "MEDIUM", "HIGH", "PROHIBITED"],
                            },
                            "hasAmlHistory": {"type": "boolean"},
                            "hasPepAssociation": {"type": "boolean"},
                            "hasFraudHistory": {"type": "boolean"},
                            "hasSarHistory": {"type": "boolean"},
                            "isOnOfacList": {"type": "boolean"},
                            "isCashIntensive": {"type": "boolean"},
                            "isMoneyServiceBusiness": {"type": "boolean"},
                            "isThirdPartyPaymentProcessor": {"type": "boolean"},
                            "industryRiskFlags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "requiresEdd": {"type": "boolean"},
                            "eddReason": {"type": "string"},
                            "riskNotes": {"type": "string"},
                        },
                    },
                    "beneficialOwners": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "fullName": {"type": "string"},
                                "dateOfBirth": {"type": "string", "format": "date"},
                                "ssn": {"type": "string"},
                                "address": {
                                    "type": "object",
                                    "properties": {
                                        "street": {"type": "string"},
                                        "city": {"type": "string"},
                                        "state": {"type": "string"},
                                        "zipCode": {"type": "string"},
                                        "country": {"type": "string"},
                                    },
                                },
                                "citizenship": {"type": "string"},
                                "identificationDocType": {"type": "string"},
                                "identificationDocNumber": {"type": "string"},
                                "identificationDocState": {"type": "string"},
                                "identificationDocExpiration": {"type": "string", "format": "date"},
                                "ownershipPercentage": {"type": "number"},
                                "isPep": {"type": "boolean"},
                                "controlPerson": {"type": "boolean"},
                            },
                        },
                    },
                    "trustInfo": {
                        "type": "object",
                        "properties": {
                            "trustName": {"type": "string"},
                            "trustType": {"type": "string"},
                            "trusteeName": {"type": "string"},
                            "dateEstablished": {"type": "string", "format": "date"},
                            "stateOfFormation": {"type": "string"},
                            "trustTaxId": {"type": "string"},
                        },
                    },
                    "certificationInfo": {
                        "type": "object",
                        "properties": {
                            "signatoryName": {"type": "string"},
                            "signatoryTitle": {"type": "string"},
                            "certificationDate": {"type": "string", "format": "date"},
                            "signatureStatus": {
                                "type": "string",
                                "enum": ["SIGNED", "ELECTRONIC", "UNSIGNED"],
                            },
                        },
                    },
                },
            },
        },
    },

    # ------------------------------------------------------------------
    # PII paths -- BSA Profile contains extensive PII requiring encryption
    # ------------------------------------------------------------------
    "pii_paths": [
        {
            "json_path": "bsaProfile.legalEntity.taxId",
            "pii_type": "tax_id",
            "masking_strategy": "partial",  # Show last 4: **-***6789
        },
        {
            "json_path": "bsaProfile.beneficialOwners[*].ssn",
            "pii_type": "ssn",
            "masking_strategy": "partial",  # Show last 4: ***-**-6789
        },
        {
            "json_path": "bsaProfile.beneficialOwners[*].dateOfBirth",
            "pii_type": "dob",
            "masking_strategy": "full",
        },
        {
            "json_path": "bsaProfile.beneficialOwners[*].identificationDocNumber",
            "pii_type": "government_id",
            "masking_strategy": "partial",  # Show last 4
        },
        {
            "json_path": "bsaProfile.trustInfo.trustTaxId",
            "pii_type": "tax_id",
            "masking_strategy": "partial",
        },
    ],

    # ------------------------------------------------------------------
    # Cost budget (BSA is a small 5-page form)
    # FORMS ($0.050/page) + TABLES ($0.015/page) = $0.065/page
    # 5 pages x $0.065 = $0.325 for extraction
    # SIGNATURES on page 5 only: $0.015
    # Total Textract: ~$0.34
    # ------------------------------------------------------------------
    "cost_budget": {
        "max_cost_usd": 0.50,
        "warn_cost_usd": 0.40,
        "textract_cost_per_page": 0.065,  # FORMS + TABLES combined
        "section_priority": {
            "bsa_profile_all": 1,
        },
    },

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    "supports_deduplication": True,
    "supports_review_workflow": True,
    "requires_signatures": True,

    # ------------------------------------------------------------------
    # Legacy mappings for backward compatibility
    # ------------------------------------------------------------------
    "legacy_section_map": {
        "BSA_PROFILE": "bsa_profile",
        "bsa_profile": "bsa_profile",
        "bsa_profile_all": "bsa_profile_all",
    },
}
