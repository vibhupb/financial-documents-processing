"""Loan Agreement plugin configuration.

Covers simple bilateral business/personal loans (NOT syndicated).
Distinguished from credit_agreement by absence of syndication indicators.
Distinguished from loan_package by absence of mortgage sub-documents.

Sources migrated into this config:
  - lambda/router/handler.py: LOAN_AGREEMENT_SECTIONS (lines 385-659),
    DOCUMENT_TYPES["loan_agreement"] (lines 692-718)
  - lib/stacks/document-processing-stack.ts: extractLoanAgreement queries (lines 571-701)
  - lambda/normalizer/handler.py: build_loan_agreement_prompt() (lines 321-728),
    apply_loan_agreement_defaults() (lines 1603-1721)

Extraction strategy: HYBRID
  1. PyPDF text extraction for readable pages (fast, free)
  2. Textract OCR for low-quality pages (garbled font encoding)
  3. Claude LLM normalization with coded field values
"""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    "plugin_id": "loan_agreement",
    "plugin_version": "1.0.0",
    "name": "Loan Agreement",
    "description": (
        "Simple bilateral business or personal loan agreement between "
        "one borrower and one lender. Contains loan terms, interest rate "
        "details, payment schedule, parties, collateral, fees, covenants, "
        "and default events. Typically 5-30 pages. Uses hybrid extraction "
        "(PyPDF + Textract OCR). NOT syndicated -- for syndicated "
        "facilities use credit_agreement plugin."
    ),

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    "classification": {
        "keywords": [
            "loan agreement",
            "business loan",
            "commercial loan",
            "promissory note",
            "borrower",
            "lender",
            "principal amount",
            "interest rate",
            "maturity date",
            "repayment",
            "monthly payment",
            "collateral",
            "security agreement",
            "default",
            "loan amount",
            "term loan",
            "line of credit",
            "note date",
            "promise to pay",
            "due date",
            "payment schedule",
        ],
        "has_sections": False,
        "min_keyword_matches": 3,
        "typical_pages": "5-30 pages",
        "distinguishing_rules": [
            "Simple BILATERAL loan between ONE borrower and ONE lender",
            "If document has indicators of syndication (multiple lenders, "
            "administrative agent, lead arrangers, commitment schedule, "
            "pro rata share), classify as 'credit_agreement', NOT 'loan_agreement'",
            "If document contains mortgage sub-documents (Closing Disclosure, "
            "Form 1003, TRID), classify as 'loan_package', NOT 'loan_agreement'",
        ],
    },

    # ------------------------------------------------------------------
    # Sections (8 sections for keyword_density page identification)
    # ------------------------------------------------------------------
    "sections": {
        "loanTerms": {
            "name": "Loan Terms & Principal",
            "description": (
                "Core loan terms including principal amount, credit limit, "
                "interest rate, maturity date, and instrument type."
            ),
            "max_pages": 5,
            "classification_hints": {
                "keywords": [
                    "loan amount", "principal amount", "principal sum",
                    "credit limit", "maximum amount", "commitment amount",
                    "interest rate", "annual percentage rate", "apr",
                    "per annum", "rate of interest",
                    "maturity date", "due date", "term of loan", "loan term",
                    "termination date", "final payment date", "payable in full",
                    "term loan", "line of credit", "revolving", "demand note",
                    "$",
                ],
                "min_keyword_matches": 3,
                "max_pages": 5,
                "typical_pages": "first few pages with loan terms",
                "page_bonus_rules": [
                    {"condition": "first_n_pages", "patterns": ["3"], "bonus": 3},
                    {"condition": "first_n_pages", "patterns": ["5"], "bonus": 1},
                ],
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "What type of loan agreement is this?",
                "What is the Loan Number or Agreement Number?",
                "What is the Agreement Date or Effective Date?",
                "What is the Closing Date?",
                "What is the Instrument or Product Code?",
                "What is the Loan Amount or Principal Amount?",
                "What is the Total Credit Limit or Maximum Amount?",
                "What is the Total Facility Amount or Commitment?",
                "What is the Maturity Date or Expiration Date?",
                "What is the Loan Term (months or years)?",
                "Is this a Revolving Credit Facility or Term Loan?",
                "What is the Purpose of this loan or Use of Proceeds?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "loan_amount", "credit_limit", "interest_rate",
                "maturity_date", "loan_term_months", "instrument_type",
                "loan_number", "agreement_date", "effective_date", "closing_date",
            ],
        },

        "interestDetails": {
            "name": "Interest Rate Details",
            "description": (
                "Interest rate structure: fixed vs. variable, index rate, "
                "margin/spread, floor/ceiling, day count convention."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "fixed rate", "variable rate", "floating rate", "adjustable rate",
                    "prime rate", "wall street journal prime", "sofr", "libor",
                    "federal funds", "margin", "spread", "plus", "above prime",
                    "above sofr", "basis points", "floor", "ceiling", "cap",
                    "minimum rate", "maximum rate", "day count", "360 day",
                    "365 day", "actual/360", "actual/365",
                    "default rate", "default interest",
                ],
                "min_keyword_matches": 2,
                "max_pages": 3,
                "typical_pages": "interest rate section",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "What is the Interest Rate?",
                "Is this a Fixed Rate or Variable/Floating Rate loan?",
                "What is the Annual Percentage Rate (APR)?",
                "What is the Index Rate used (Prime, SOFR, Term SOFR, Daily SOFR, Fed Funds)?",
                "What is the Margin or Spread over the Index Rate?",
                "What is the Interest Rate Floor or Minimum Rate?",
                "What is the Interest Rate Ceiling or Cap?",
                "What is the Default Interest Rate or Penalty Rate?",
                "How is interest calculated (Actual/360, Actual/365, 30/360)?",
                "What is the Rate Calculation Method or Day Count Basis?",
                "What is the Rate Setting Mechanism or how is the rate determined?",
                "What is the Rate Reset Frequency or Interest Period (1 Month, 3 Month, Daily)?",
                "How many Business Days before the Interest Period does the rate get set?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "rate_type", "index_rate", "margin", "floor",
                "ceiling", "day_count_basis", "default_rate",
                "rate_setting", "rate_reset_frequency",
            ],
        },

        "paymentInfo": {
            "name": "Payment Schedule",
            "description": (
                "Payment structure: amount, frequency, first payment date, "
                "balloon payment, billing type, repayment schedule."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "payment amount", "monthly payment", "installment",
                    "periodic payment", "minimum payment",
                    "payment schedule", "repayment", "amortization",
                    "interest only", "principal and interest",
                    "monthly", "quarterly", "annually", "on demand",
                    "payment frequency",
                    "first payment", "payment due", "due date",
                    "payment day", "beginning", "commencing",
                    "balloon payment", "balloon", "final payment",
                ],
                "min_keyword_matches": 2,
                "max_pages": 3,
                "typical_pages": "payment terms section",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "What is the Monthly Payment Amount?",
                "What is the First Payment Date?",
                "When are payments due each month?",
                "What is the Payment Frequency (monthly, quarterly, semi-annually)?",
                "What is the Total Number of Payments?",
                "Is there a Balloon Payment? What amount?",
                "Is Interest payable In Arrears or In Advance?",
                "What is the Billing Type (Interest Only, Principal and Interest)?",
                "What is the Repayment Schedule?",
                "Are there Principal Reductions or Amortization required?",
                "Is there an Interest Only Period? How long?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "monthly_payment", "first_payment_date", "payment_frequency",
                "number_of_payments", "balloon_payment", "billing_type",
                "repayment_schedule", "interest_only_period",
            ],
        },

        "parties": {
            "name": "Parties & Addresses",
            "description": (
                "Borrower, lender, and guarantor identification with "
                "legal names, entity types, and addresses."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "borrower", "debtor", "maker", "obligor", "company",
                    "lender", "bank", "creditor", "holder", "payee",
                    "guarantor", "guarantee", "personal guarantee",
                    "jointly and severally",
                    "address", "principal place of business", "located at",
                    "organized under", "jurisdiction",
                    "inc", "llc", "corporation", "limited liability",
                ],
                "min_keyword_matches": 2,
                "max_pages": 3,
                "typical_pages": "first pages with party definitions",
                "page_bonus_rules": [
                    {"condition": "first_n_pages", "patterns": ["3"], "bonus": 3},
                ],
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "Who is the Borrower or Company Name?",
                "What is the Borrower Address?",
                "Who is the Guarantor or Co-Signer?",
                "Who is the Lender?",
                "What is the Lender Address?",
                "Who is the Administrative Agent (if any)?",
                "Who is the Collateral Agent (if any)?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "borrower_name", "borrower_address",
                "lender_name", "lender_address", "guarantor_name",
            ],
        },

        "security": {
            "name": "Security & Collateral",
            "description": (
                "Security interest, collateral pledged, UCC filing "
                "references, lien positions, and asset types."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "security interest", "security agreement", "secured by",
                    "collateral", "pledge",
                    "ucc", "uniform commercial code", "financing statement",
                    "equipment", "inventory", "accounts receivable",
                    "real property", "personal property",
                    "lien", "first lien", "senior lien", "subordinate",
                ],
                "min_keyword_matches": 2,
                "max_pages": 3,
                "typical_pages": "security/collateral section",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "Is this loan Secured or Unsecured?",
                "What is the Collateral for this loan?",
                "What is the Property Address if secured?",
                "What assets are pledged as Collateral?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "is_secured", "collateral_description", "property_address",
            ],
        },

        "fees": {
            "name": "Fees & Charges",
            "description": (
                "Origination fees, late charges, grace period, closing "
                "costs, annual fees, commitment fees, and prepayment terms."
            ),
            "max_pages": 2,
            "classification_hints": {
                "keywords": [
                    "origination fee", "loan fee", "commitment fee",
                    "closing cost", "prepayment penalty", "prepayment fee",
                    "late fee", "late charge", "late payment",
                    "grace period", "annual fee",
                    "%", "percent",
                ],
                "min_keyword_matches": 2,
                "max_pages": 2,
                "typical_pages": "fee schedule",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "What is the Origination Fee?",
                "What is the Late Payment Fee or Late Charge?",
                "What is the Grace Period for late payments?",
                "What are the Closing Costs?",
                "Are there any Annual Fees or Facility Fees?",
                "What is the Commitment Fee or Unused Fee rate?",
                "What is the Late Charge Grace Days?",
                "Is there a Prepayment Penalty?",
                "What are the Prepayment Terms or Make-Whole provisions?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "origination_fee", "late_payment_fee", "grace_period_days",
                "closing_costs", "annual_fee", "commitment_fee",
                "prepayment_penalty", "prepayment_terms",
            ],
        },

        "covenants": {
            "name": "Covenants & Default Events",
            "description": (
                "Financial maintenance covenants (DSCR, current ratio, "
                "leverage), negative covenants, events of default, "
                "remedies, and governing law."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "financial covenant", "debt service coverage", "dscr",
                    "current ratio", "leverage ratio", "minimum liquidity",
                    "event of default", "default", "remedies",
                    "acceleration", "cross-default",
                    "negative covenant", "restriction", "shall not", "prohibited",
                ],
                "min_keyword_matches": 2,
                "max_pages": 3,
                "typical_pages": "covenant and default articles",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "What are the Financial Covenants required?",
                "What is the required Debt Service Coverage Ratio (DSCR)?",
                "What is the required Current Ratio?",
                "What is the Minimum Liquidity Requirement?",
                "What is the Maximum Leverage Ratio or Debt to Equity?",
                "What is the Covenant Testing Frequency (monthly, quarterly)?",
                "What are the Negative Covenants or Restrictions?",
                "What constitutes an Event of Default?",
                "What are the Remedies upon Default?",
                "What is the Governing Law or Jurisdiction?",
                "What is the Currency of this loan (USD, EUR, GBP)?",
                # Legal and Operational (migrated from old CDK extractLoanAgreement)
                "Is this loan Assignable or Transferable?",
                "What Business Day Calendar is used (New York, London)?",
                "What are the Reporting Requirements or Financial Statements required?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "financial_covenants", "dscr", "current_ratio",
                "leverage_ratio", "events_of_default", "remedies",
                "governing_law", "currency",
            ],
        },

        "signatures": {
            "name": "Signatures",
            "description": (
                "Signature blocks, execution dates, witnesses, and notary "
                "acknowledgements. Always checks the last 3 pages."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "signature", "signed", "executed", "witness",
                    "notary", "acknowledged", "sworn",
                    "in witness whereof", "intending to be legally bound",
                    "duly authorized",
                    "dated as of", "effective as of",
                    "by:", "name:", "title:", "date:",
                ],
                "min_keyword_matches": 3,
                "max_pages": 3,
                "typical_pages": "last pages with signatures",
                "search_last_pages": True,
                "page_bonus_rules": [
                    {"condition": "last_n_pages", "patterns": ["3"], "bonus": 10},
                    {"condition": "last_n_pages", "patterns": ["5"], "bonus": 5},
                    {
                        "condition": "contains_any",
                        "patterns": ["in witness whereof", "witness whereof"],
                        "bonus": 5,
                    },
                    {
                        "condition": "contains_all",
                        "patterns": ["executed", "date"],
                        "bonus": 3,
                    },
                ],
            },
            "textract_features": ["QUERIES"],
            "queries": [],  # No Textract queries -- uses signature detection
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": False,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": True,
            "extraction_fields": ["signature_detected", "execution_date"],
        },
    },

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    "normalization": {
        "prompt_template": "loan_agreement",
        "llm_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "max_tokens": 8192,
        "temperature": 0.0,
        "field_overrides": {
            "loanData.loanAgreement._extractedCodes.billingFrequency": "C:MONTHLY",
            "loanData.loanAgreement._extractedCodes.currency": "USD:US DOLLAR",
            "loanData.loanAgreement._extractedCodes.rateCalculationMethod": "360ACTUAL:ACTUAL DAYS / 360 DAY YEAR",
            "loanData.loanAgreement.interestDetails.dayCountBasis": "360ACTUAL:ACTUAL DAYS / 360 DAY YEAR",
        },
    },

    # ------------------------------------------------------------------
    # Output schema
    # ------------------------------------------------------------------
    "output_schema": {
        "type": "object",
        "properties": {
            "loanAgreement": {
                "type": "object",
                "properties": {
                    "documentInfo": {
                        "type": "object",
                        "properties": {
                            "documentType": {"type": "string"},
                            "loanNumber": {"type": ["string", "null"]},
                            "agreementDate": {"type": ["string", "null"]},
                            "effectiveDate": {"type": ["string", "null"]},
                            "closingDate": {"type": ["string", "null"]},
                        },
                    },
                    "loanTerms": {
                        "type": "object",
                        "properties": {
                            "loanAmount": {"type": ["number", "null"]},
                            "creditLimit": {"type": ["number", "null"]},
                            "interestRate": {"type": ["number", "null"]},
                            "annualPercentageRate": {"type": ["number", "null"]},
                            "isFixedRate": {"type": ["boolean", "null"]},
                            "maturityDate": {"type": ["string", "null"]},
                            "loanTermMonths": {"type": ["number", "null"]},
                        },
                    },
                    "interestDetails": {
                        "type": "object",
                        "properties": {
                            "rateType": {"type": "string"},
                            "indexRate": {"type": "string"},
                            "margin": {"type": ["number", "null"]},
                            "floor": {"type": ["number", "null"]},
                            "ceiling": {"type": ["number", "null"]},
                            "defaultRate": {"type": ["number", "null"]},
                            "dayCountBasis": {"type": "string"},
                        },
                    },
                    "paymentInfo": {
                        "type": "object",
                        "properties": {
                            "monthlyPayment": {"type": ["number", "null"]},
                            "firstPaymentDate": {"type": ["string", "null"]},
                            "paymentDueDay": {"type": ["number", "null"]},
                            "paymentFrequency": {"type": "string"},
                            "numberOfPayments": {"type": ["number", "null"]},
                            "balloonPayment": {"type": ["number", "null"]},
                        },
                    },
                    "parties": {
                        "type": "object",
                        "properties": {
                            "borrower": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": ["string", "null"]},
                                    "address": {"type": ["string", "null"]},
                                },
                            },
                            "guarantor": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": ["string", "null"]},
                                    "address": {"type": ["string", "null"]},
                                },
                            },
                            "lender": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": ["string", "null"]},
                                    "address": {"type": ["string", "null"]},
                                },
                            },
                        },
                    },
                    "security": {
                        "type": "object",
                        "properties": {
                            "isSecured": {"type": ["boolean", "null"]},
                            "collateralDescription": {"type": ["string", "null"]},
                            "propertyAddress": {"type": ["string", "null"]},
                        },
                    },
                    "fees": {
                        "type": "object",
                        "properties": {
                            "originationFee": {"type": ["number", "null"]},
                            "latePaymentFee": {"type": ["number", "null"]},
                            "gracePeriodDays": {"type": ["number", "null"]},
                            "closingCosts": {"type": ["number", "null"]},
                            "annualFee": {"type": ["number", "null"]},
                        },
                    },
                    "prepayment": {
                        "type": "object",
                        "properties": {
                            "hasPenalty": {"type": ["boolean", "null"]},
                            "penaltyTerms": {"type": ["string", "null"]},
                        },
                    },
                    "covenants": {
                        "type": "object",
                        "properties": {
                            "financialCovenants": {"type": "array", "items": {"type": "string"}},
                            "debtServiceCoverageRatio": {"type": ["number", "null"]},
                            "currentRatio": {"type": ["number", "null"]},
                        },
                    },
                    "repayment": {
                        "type": "object",
                        "properties": {
                            "schedule": {"type": ["string", "null"]},
                            "principalReductions": {"type": ["string", "null"]},
                            "interestOnlyPeriod": {"type": ["string", "null"]},
                        },
                    },
                    "default": {
                        "type": "object",
                        "properties": {
                            "eventsOfDefault": {"type": "array", "items": {"type": "string"}},
                            "remedies": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "_extractedCodes": {
                        "type": "object",
                        "description": "Raw coded values for downstream banking system compatibility",
                        "properties": {
                            "instrumentType": {"type": "string"},
                            "interestRateType": {"type": "string"},
                            "rateIndex": {"type": "string"},
                            "rateCalculationMethod": {"type": "string"},
                            "billingType": {"type": "string"},
                            "billingFrequency": {"type": "string"},
                            "prepaymentIndicator": {"type": "string"},
                            "currency": {"type": "string"},
                        },
                    },
                },
            },
        },
    },

    # ------------------------------------------------------------------
    # PII paths -- loan agreements have no SSN/DOB
    # ------------------------------------------------------------------
    "pii_paths": [],

    # ------------------------------------------------------------------
    # Cost budget
    # ------------------------------------------------------------------
    "cost_budget": {
        "max_cost_usd": 0.60,
        "warn_cost_usd": 0.35,
        "textract_cost_per_page": 0.02,
        "section_priority": {
            "loanTerms": 1,
            "interestDetails": 2,
            "paymentInfo": 3,
            "parties": 4,
            "fees": 5,
            "security": 6,
            "covenants": 7,
            "signatures": 8,
        },
    },

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    "supports_deduplication": True,
    "supports_review_workflow": True,
    "requires_signatures": True,

    # ------------------------------------------------------------------
    # Legacy mappings
    # ------------------------------------------------------------------
    "legacy_section_map": {
        "LOAN_AGREEMENT": "loan_agreement",
        "loan_agreement": "loan_agreement",
    },
}
