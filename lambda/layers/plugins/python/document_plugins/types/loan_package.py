"""Loan Package plugin configuration.

Covers the three mortgage document sections extracted in parallel
by the Step Functions ParallelMortgageExtraction state:
  - Promissory Note (QUERIES)
  - Closing Disclosure (QUERIES + TABLES)
  - Form 1003 (FORMS)

Classification keywords sourced from router handler DOCUMENT_TYPES.
Queries sourced from CDK extractPromissoryNote, extractClosingDisclosure,
and extractForm1003 task definitions.
"""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    "plugin_id": "loan_package",
    "plugin_version": "1.0.0",
    "name": "Loan Package (Mortgage)",
    "description": (
        "Mortgage loan package containing a Promissory Note, "
        "Closing Disclosure (TILA-RESPA), and Uniform Residential "
        "Loan Application (Form 1003). The router classifies each "
        "document type by start-page, then each section is extracted "
        "in parallel via Step Functions."
    ),

    # ------------------------------------------------------------------
    # Classification (mirrors router handler DOCUMENT_TYPES entries)
    # ------------------------------------------------------------------
    "classification": {
        "keywords": [
            # Promissory Note keywords
            "promissory note",
            "note",
            "promise to pay",
            "principal amount",
            "interest rate",
            "monthly payment",
            "maturity date",
            "borrower agrees to pay",
            # Closing Disclosure keywords
            "closing disclosure",
            "loan terms",
            "projected payments",
            "closing costs",
            "cash to close",
            "loan estimate",
            "trid",
            "cfpb",
            # Form 1003 keywords
            "uniform residential loan application",
            "form 1003",
            "urla",
            "borrower information",
            "employment information",
            "assets and liabilities",
            "declarations",
        ],
        "has_sections": True,
        "section_names": [
            "promissory_note",
            "closing_disclosure",
            "form_1003",
        ],
        "min_keyword_matches": 3,
        "typical_pages": "5-15 pages total across all three documents",
        "distinguishing_rules": [
            "Each sub-document starts on its own page",
            "Promissory Note is typically 1-3 pages",
            "Closing Disclosure is typically 5 pages (TRID format)",
            "Form 1003 is typically 5-8 pages",
        ],
    },

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------
    "sections": {
        # ==============================================================
        # Promissory Note
        # ==============================================================
        "promissory_note": {
            "name": "Promissory Note",
            "description": (
                "The borrower's written promise to repay the loan. Contains "
                "interest rate, principal, borrower names, maturity date, and "
                "monthly payment."
            ),
            "max_pages": 3,
            "classification_hints": {
                "keywords": [
                    "promissory note",
                    "note",
                    "promise to pay",
                    "principal amount",
                    "interest rate",
                    "monthly payment",
                    "maturity date",
                    "borrower agrees to pay",
                ],
                "min_keyword_matches": 3,
                "max_pages": 3,
                "typical_pages": "1-3 pages",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                # ----- CORE LOAN TERMS -----
                "What is the Interest Rate or Annual Percentage Rate (APR)?",
                "What is the Principal Amount or Loan Amount?",
                "What is the Total Loan Amount including fees?",
                "What is the Maturity Date or Final Payment Date?",
                "What is the Monthly Payment Amount?",
                "What is the First Payment Date?",
                "What is the Payment Due Day of each month?",
                "What is the Loan Term (months or years)?",
                # ----- BORROWER INFORMATION -----
                "Who is the Borrower or Maker of this Note?",
                "Who is the Co-Borrower or Co-Maker?",
                "What is the Borrower Address?",
                # ----- LENDER INFORMATION -----
                "Who is the Lender or Payee?",
                "What is the Lender Address?",
                # ----- INTEREST RATE DETAILS -----
                "Is this a Fixed Rate or Variable Rate loan?",
                "What is the Index Rate used (Prime, SOFR, Term SOFR, Daily SOFR, Fed Funds)?",
                "What is the Margin or Spread added to Index Rate?",
                "What is the Interest Rate Floor or Minimum Rate?",
                "What is the Interest Rate Ceiling or Cap?",
                "What is the Default Interest Rate or Penalty Rate?",
                "How is interest calculated (Actual/360, Actual/365, 30/360)?",
                "What is the Rate Calculation Method or Day Count Basis?",
                # ----- PAYMENT DETAILS -----
                "What is the Total Number of Payments?",
                "How many payments remain?",
                "What is the Balloon Payment Amount?",
                "What is the Late Payment Fee or Late Charge?",
                "What is the Grace Period for late payments?",
                "Is Interest payable In Arrears or In Advance?",
                "What is the Payment Frequency (monthly, quarterly)?",
                # ----- SECURITY AND COLLATERAL -----
                "Is this loan Secured or Unsecured?",
                "What is the Collateral or Security for this loan?",
                "What is the Property Address if secured by real estate?",
                # ----- PREPAYMENT -----
                "Is there a Prepayment Penalty?",
                "What is the Prepayment Penalty Amount or Terms?",
                # ----- DOCUMENT IDENTIFICATION -----
                "What is the Loan Number or Note Number?",
                "What is the Date of this Note?",
                "What is the Effective Date?",
                # ----- LEGAL AND OPERATIONAL -----
                "What is the Governing Law or Jurisdiction?",
                "What is the Currency of this loan (USD)?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "interestRate",
                "principalAmount",
                "totalLoanAmount",
                "maturityDate",
                "monthlyPayment",
                "firstPaymentDate",
                "paymentDueDay",
                "loanTerm",
                "borrowerName",
                "coBorrowerName",
                "borrowerAddress",
                "lenderName",
                "lenderAddress",
                "isFixedRate",
                "indexRate",
                "margin",
                "rateFloor",
                "rateCeiling",
                "defaultRate",
                "rateCalculationMethod",
                "totalPayments",
                "balloonPayment",
                "latePaymentFee",
                "gracePeriodDays",
                "paymentFrequency",
                "isSecured",
                "collateral",
                "propertyAddress",
                "hasPrepaymentPenalty",
                "prepaymentTerms",
                "loanNumber",
                "noteDate",
                "effectiveDate",
                "governingLaw",
                "currency",
            ],
        },

        # ==============================================================
        # Closing Disclosure
        # ==============================================================
        "closing_disclosure": {
            "name": "Closing Disclosure",
            "description": (
                "TILA-RESPA Integrated Disclosure form (5-page standard). "
                "Contains loan amount, fees, closing costs, and cash to close."
            ),
            "max_pages": 5,
            "classification_hints": {
                "keywords": [
                    "closing disclosure",
                    "loan terms",
                    "projected payments",
                    "closing costs",
                    "cash to close",
                    "loan estimate",
                    "trid",
                    "cfpb",
                ],
                "min_keyword_matches": 3,
                "max_pages": 5,
                "typical_pages": "5 pages (TRID standard)",
            },
            "textract_features": ["QUERIES", "TABLES"],
            "queries": [
                # ----- LOAN TERMS (Page 1) -----
                "What is the Loan Term in months or years?",
                "What is the Loan Purpose?",
                "What is the Loan Product type?",
                "What is the Loan Type (Conventional, FHA, VA)?",
                "What is the Loan ID or Loan Number?",
                # ----- LOAN AMOUNT AND INTEREST -----
                "What is the Loan Amount?",
                "What is the Interest Rate?",
                "What is the Annual Percentage Rate (APR)?",
                "Is the Interest Rate Adjustable or Fixed?",
                "Can the Interest Rate Increase?",
                "What is the Index Rate used (Prime, SOFR)?",
                "What is the Margin added to Index Rate?",
                "What is the Interest Rate Floor?",
                "What is the Interest Rate Ceiling or Cap?",
                # ----- MONTHLY PAYMENT -----
                "What is the Monthly Principal and Interest Payment?",
                "What is the Monthly Mortgage Insurance Payment?",
                "What is the Monthly Escrow Payment?",
                "What is the Total Monthly Payment?",
                "Can the Monthly Payment Increase?",
                "What is the First Payment Date?",
                # ----- PROJECTED PAYMENTS -----
                "What is the Estimated Total Monthly Payment?",
                "What are the Projected Payments for Years 1-7?",
                "What are the Projected Payments for Years 8-30?",
                # ----- COSTS AT CLOSING -----
                "What is the Total Closing Costs?",
                "What is the Cash to Close?",
                "What are the Total Loan Costs?",
                "What are the Total Other Costs?",
                "What is the Total Payoffs and Payments?",
                # ----- LOAN COSTS (Section A, B, C) -----
                "What is the Origination Charges total?",
                "What is the Points or Discount Points amount?",
                "What is the Services Borrower Did Not Shop For total?",
                "What is the Services Borrower Did Shop For total?",
                "What is the Appraisal Fee?",
                "What is the Credit Report Fee?",
                # ----- OTHER COSTS (Section E, F, G, H) -----
                "What are the Total Taxes and Government Fees?",
                "What is the Recording Fee?",
                "What is the Transfer Tax?",
                "What are the Prepaids total?",
                "What is the Homeowners Insurance Premium?",
                "What is the Prepaid Interest?",
                "What are the Initial Escrow Payments?",
                # ----- PROPERTY AND TRANSACTION -----
                "What is the Property Address?",
                "What is the Sale Price of Property?",
                "What is the Appraised Value?",
                # ----- PARTIES -----
                "Who is the Borrower Name?",
                "Who is the Co-Borrower Name?",
                "Who is the Seller Name?",
                "Who is the Lender Name?",
                "What is the Lender NMLS ID?",
                "Who is the Loan Officer?",
                # ----- IMPORTANT DATES -----
                "What is the Closing Date?",
                "What is the Disbursement Date?",
                "What is the Settlement Date?",
                "What is the Maturity Date?",
                # ----- ADDITIONAL DISCLOSURES -----
                "Is there a Prepayment Penalty?",
                "Is there a Balloon Payment?",
                "What is the Total Interest Percentage (TIP)?",
                "What is the Late Payment Fee?",
                "What is the Grace Period for late payments?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": True,
            "extract_signatures": False,
            "extraction_fields": [
                "loanAmount",
                "interestRate",
                "apr",
                "monthlyPrincipalAndInterest",
                "estimatedTotalMonthlyPayment",
                "closingCosts",
                "cashToClose",
                "fees",
                "loanTerm",
                "loanPurpose",
                "loanProduct",
                "loanType",
                "loanId",
                "propertyAddress",
                "salePrice",
                "appraisedValue",
                "borrowerName",
                "coBorrowerName",
                "sellerName",
                "lenderName",
                "lenderNmls",
                "loanOfficer",
                "closingDate",
                "disbursementDate",
                "maturityDate",
            ],
        },

        # ==============================================================
        # Form 1003
        # ==============================================================
        "form_1003": {
            "name": "Uniform Residential Loan Application (Form 1003)",
            "description": (
                "URLA / Fannie Mae Form 1003. Pre-printed form with "
                "borrower info, employment, assets/liabilities, and "
                "declarations. Extracted via FORMS features (key-value pairs)."
            ),
            "max_pages": 8,
            "classification_hints": {
                "keywords": [
                    "uniform residential loan application",
                    "form 1003",
                    "urla",
                    "borrower information",
                    "employment information",
                    "assets and liabilities",
                    "declarations",
                ],
                "min_keyword_matches": 2,
                "max_pages": 8,
                "typical_pages": "5-8 pages",
            },
            "textract_features": ["FORMS"],
            "queries": [],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "borrowerName",
                "borrowerSsn",
                "borrowerDateOfBirth",
                "borrowerPhone",
                "borrowerEmail",
                "propertyStreet",
                "propertyCity",
                "propertyState",
                "propertyZipCode",
                "employerName",
                "position",
                "yearsEmployed",
                "monthlyIncome",
            ],
        },
    },

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    "normalization": {
        "prompt_template": "loan_package",
        "llm_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "max_tokens": 8192,
        "temperature": 0.0,
    },

    # ------------------------------------------------------------------
    # Output schema (mirrors frontend LoanData / PromissoryNoteData /
    # ClosingDisclosureData / Form1003Data)
    # ------------------------------------------------------------------
    "output_schema": {
        "type": "object",
        "properties": {
            "promissoryNote": {
                "type": "object",
                "properties": {
                    "interestRate": {"type": "number"},
                    "principalAmount": {"type": "number"},
                    "borrowerName": {"type": "string"},
                    "coBorrowerName": {"type": "string"},
                    "maturityDate": {"type": "string"},
                    "monthlyPayment": {"type": "number"},
                    "firstPaymentDate": {"type": "string"},
                },
            },
            "closingDisclosure": {
                "type": "object",
                "properties": {
                    "loanAmount": {"type": "number"},
                    "interestRate": {"type": "number"},
                    "monthlyPrincipalAndInterest": {"type": "number"},
                    "estimatedTotalMonthlyPayment": {"type": "number"},
                    "closingCosts": {"type": "number"},
                    "cashToClose": {"type": "number"},
                    "fees": {"type": "array"},
                },
            },
            "form1003": {
                "type": "object",
                "properties": {
                    "borrowerInfo": {"type": "object"},
                    "propertyAddress": {"type": "object"},
                    "employmentInfo": {"type": "object"},
                },
            },
        },
    },

    # ------------------------------------------------------------------
    # PII paths -- Form 1003 SSN is already masked by Textract FORMS
    # ------------------------------------------------------------------
    "pii_paths": [],

    # ------------------------------------------------------------------
    # Cost budget (mortgage docs are small, ~5-15 pages total)
    # ------------------------------------------------------------------
    "cost_budget": {
        "max_cost_usd": 0.50,
        "warn_cost_usd": 0.35,
        "textract_cost_per_page": 0.02,
        "section_priority": {
            "promissory_note": 1,
            "closing_disclosure": 2,
            "form_1003": 3,
        },
    },

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    "supports_deduplication": True,
    "supports_review_workflow": True,
    "requires_signatures": False,

    # ------------------------------------------------------------------
    # Legacy mappings for backward compatibility
    # ------------------------------------------------------------------
    "legacy_section_map": {
        "LOAN_PACKAGE": "loan_package",
        "promissory_note": "promissory_note",
        "closing_disclosure": "closing_disclosure",
        "form_1003": "form_1003",
    },
}
