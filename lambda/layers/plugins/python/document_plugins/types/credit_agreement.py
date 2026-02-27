"""Credit Agreement plugin configuration.

Migrated from three hardcoded sources into a single plugin config:
  - lambda/router/handler.py: CREDIT_AGREEMENT_SECTIONS (lines 56-380),
    DOCUMENT_TYPES["credit_agreement"] (lines 663-689)
  - lambda/extractor/handler.py: CREDIT_AGREEMENT_QUERIES (lines 64-287)
  - lambda/normalizer/handler.py: build_credit_agreement_prompt()

Classification keywords sourced from router handler DOCUMENT_TYPES.
Section keywords sourced from router handler CREDIT_AGREEMENT_SECTIONS.
Queries sourced from extractor handler CREDIT_AGREEMENT_QUERIES.
"""

from document_plugins.contract import DocumentPluginConfig

PLUGIN_CONFIG: DocumentPluginConfig = {
    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    "plugin_id": "credit_agreement",
    "plugin_version": "1.0.0",
    "name": "Credit Agreement",
    "description": (
        "Complex syndicated loan facilities with multiple lenders, "
        "administrative agent, pricing grids, LC commitments, and "
        "lender commitment schedules. Typically 50-300+ pages with "
        "7 extraction sections."
    ),

    # ------------------------------------------------------------------
    # Classification (migrated from DOCUMENT_TYPES["credit_agreement"])
    # ------------------------------------------------------------------
    "classification": {
        "keywords": [
            "credit agreement",
            "revolving credit",
            "term loan",
            "borrowing base",
            "administrative agent",
            "lender commitment",
            "applicable rate",
            "maturity date",
            "interest period",
            "lc commitment",
            "letters of credit",
            "unused revolving credit commitment",
            "lead arranger",
            "guarantor",
            # Syndicated loan indicators
            "syndicated",
            "syndication",
            "multiple lenders",
            "pro rata share",
            "commitment schedule",
        ],
        "has_sections": True,
        "min_keyword_matches": 3,
        "typical_pages": "50-300+ pages",
        "distinguishing_rules": [
            "Complex SYNDICATED facilities with MULTIPLE LENDERS, "
            "Administrative Agent, Lead Arrangers, Commitment Schedules, "
            "Pricing Grids, LC Commitments, Swingline sublimits",
            "If document is titled 'Loan Agreement' WITHOUT indicators "
            "of syndication (multiple lenders, administrative agent), "
            "classify as 'loan_agreement', NOT 'credit_agreement'",
        ],
    },

    # ------------------------------------------------------------------
    # Sections (7 sections, migrated from CREDIT_AGREEMENT_SECTIONS
    # and CREDIT_AGREEMENT_QUERIES)
    # ------------------------------------------------------------------
    "sections": {
        # ==============================================================
        # Agreement Information (first 5 pages, no keyword matching)
        # ==============================================================
        "agreementInfo": {
            "name": "Agreement Information",
            "description": (
                "Document type, dates, parties, amendment tracking. "
                "Always the first 5 pages of the document."
            ),
            "max_pages": 5,
            "classification_hints": {
                "keywords": [],  # No keywords - always use first 5 pages
                "typical_pages": "first 5 pages",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                # Document identification
                "What type of agreement is this?",
                "What is the document title or type?",
                "What is the Instrument Type or Loan Type?",
                # Dates
                "What is the date this agreement is dated as of?",
                "What is the agreement date or effective date?",
                "What is the Effective Date of this agreement?",
                "What is the Closing Date?",
                "What is the Maturity Date?",
                "What is the Termination Date?",
                # Parties - joint borrower extraction
                "Who are all the companies listed as Borrower?",
                "List all company names that together are the Borrower",
                "What companies are named as Borrower in this agreement?",
                "Who is the Borrower?",
                "Who are the Borrowers identified in the first paragraph?",
                "What companies together constitute the Borrower?",
                "Who is the Company or Primary Obligor?",
                "Who is the Ultimate Holdings or Parent Company?",
                "Who is the Intermediate Holdings?",
                "Who is the Administrative Agent?",
                "Who is the Collateral Agent?",
                # Amendment tracking
                "What is the Amendment Number in the document title?",
                "Is this document titled as an amendment? What number?",
                "Is this an amendment and restatement?",
                # Jurisdiction
                "What state or jurisdiction is the borrower organized in?",
                "What is the governing law jurisdiction?",
                "What state or jurisdiction is the borrower incorporated in?",
                # Currency
                "What is the currency of this loan?",
                "What currency are amounts denominated in?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": False,
            "extract_signatures": True,  # Legal document signature validation
            "extraction_fields": [
                "documentType",
                "agreementDate",
                "effectiveDate",
                "maturityDate",
                "amendmentNumber",
                "borrowerName",
                "coBorrowerNames",
                "ultimateHoldings",
                "intermediateHoldings",
                "administrativeAgent",
                "collateralAgent",
                "currency",
            ],
        },

        # ==============================================================
        # Key Definitions
        # ==============================================================
        "definitions": {
            "name": "Key Definitions",
            "description": (
                "Business day, interest period, maturity date, EBITDA, "
                "borrowing base, lead arranger, LC, and commitment fee "
                "definitions from the definitions article."
            ),
            "max_pages": 10,
            "classification_hints": {
                "keywords": [
                    # Business day calculation
                    "business day",
                    '"business day" means',
                    "business day calculation",
                    "banking day",
                    # Interest payment date / Interest period
                    "interest payment date",
                    '"interest payment date" means',
                    "interest period",
                    '"interest period" means',
                    "payment date means",
                    # Lead Arranger
                    "lead arranger",
                    '"lead arranger" means',
                    "joint lead arranger",
                    "lead bookrunner",
                    "joint bookrunner",
                    # Maturity date definition
                    "maturity date",
                    "maturity date means",
                    "scheduled maturity",
                    "termination date",
                    "termination date means",
                    # Unused Revolving Credit Commitment
                    "unused revolving credit",
                    '"unused revolving" means',
                    "unused commitment",
                    "unused portion",
                    "available commitment",
                    # Letter of credit
                    "letter of credit",
                    '"letter of credit" means',
                    "l/c",
                    "lc commitment",
                    '"lc commitment" means',
                    "lc expiration date",
                    "letter of credit expiration",
                    # Commitment Fee
                    "commitment fee",
                    '"commitment fee" means',
                    "unused commitment fee",
                    "fee rate",
                    "per annum fee",
                ],
                "min_keyword_matches": 2,
                "typical_pages": "pages 5-60 (definitions section)",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                # Rate definitions
                "What is the definition of Applicable Rate?",
                "What is the definition of Applicable Margin?",
                "What is the definition of Base Rate?",
                # EBITDA
                "What is the definition of EBITDA?",
                "What is the definition of Adjusted EBITDA?",
                "What adjustments are made to EBITDA?",
                # Borrowing Base
                "What is the definition of Borrowing Base?",
                "How is Borrowing Base calculated?",
                # Maturity Date
                "What is the definition of Maturity Date?",
                "What date is the Maturity Date?",
                # Guarantors
                "Who are the Guarantors?",
                "Who are the Credit Parties?",
                # Business Day
                "What is the definition of Business Day?",
                # Interest Period
                "What is the definition of Interest Payment Date?",
                "What is the definition of Interest Period?",
                # Lead Arranger
                "Who is the Lead Arranger or Joint Lead Arranger?",
                # Unused Commitment
                "What is the definition of Unused Revolving Credit Commitment?",
                "How is unused commitment determined?",
                # LC definitions
                "What is the definition of Letter of Credit?",
                "What is the LC Expiration Date?",
                # Commitment Fee
                "What is the definition of Commitment Fee?",
                # Material Adverse Effect
                "What is the definition of Material Adverse Effect?",
            ],
            "include_pypdf_text": True,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "businessDayDefinition",
                "interestPaymentDate",
                "interestPeriod",
                "leadArranger",
                "maturityDate",
                "unusedRevolvingCreditCommitment",
                "letterOfCredit",
                "lcExpirationDate",
                "commitmentFee",
            ],
        },

        # ==============================================================
        # Applicable Rates / Pricing Grid
        # ==============================================================
        "applicableRates": {
            "name": "Applicable Rates/Pricing Grid",
            "description": (
                "Interest rate definitions, SOFR/ABR spreads, pricing "
                "tiers, floor rates, day count conventions, and fee rates "
                "within the rate schedule."
            ),
            "max_pages": 8,
            "classification_hints": {
                "keywords": [
                    # Pricing level table headers
                    "pricing level",
                    "level i",
                    "level ii",
                    "level iii",
                    "level iv",
                    "level v",
                    # Rate spread columns
                    "term sofr spread",
                    "sofr spread",
                    "abr spread",
                    "base rate spread",
                    "eurodollar spread",
                    "unused commitment fee",
                    # Definition section keywords
                    "applicable rate",
                    "applicable margin",
                    '"applicable rate" means',
                    '"applicable margin" means',
                    "rate means",
                    "margin means",
                    # SOFR related
                    "term sofr",
                    "adjusted term sofr",
                    "daily simple sofr",
                    "sofr rate",
                    "cme term sofr",
                    # Rate index references
                    "rate index",
                    "reference rate",
                    "benchmark rate",
                    # Interest type identification
                    "interest rate type",
                    "fixed rate",
                    "floating rate",
                    "variable rate",
                    # Year basis / day count
                    "year basis",
                    "day count",
                    "actual/360",
                    "actual/365",
                    "360 day year",
                    "365 day year",
                    # Typical spread values
                    "0.25%",
                    "0.50%",
                    "0.75%",
                    "1.00%",
                    "1.25%",
                    "1.50%",
                    "2.00%",
                    "2.25%",
                    "2.50%",
                    # Basis points
                    "basis points",
                    "bps",
                ],
                "min_keyword_matches": 2,
                "typical_pages": "within definitions section (pages 5-50)",
            },
            "textract_features": ["QUERIES", "TABLES"],
            "queries": [
                # Rate Index
                "What is the Rate Index used (SOFR, LIBOR, Prime)?",
                "Is the loan rate based on Term SOFR?",
                "What benchmark rate is used for interest calculation?",
                "What is the Reference Rate or Index Rate?",
                # Rate/Margin
                "What is the Applicable Rate or Applicable Margin?",
                "What is the Spread added to the index rate?",
                "What is the Base Rate?",
                # SOFR - specific queries
                "What is the Term SOFR spread or margin?",
                "What is the Daily Simple SOFR spread?",
                "What is the Adjusted Term SOFR spread?",
                "What is the SOFR floor rate?",
                # Rate type
                "Is the interest rate Fixed or Variable/Floating?",
                "Does this loan use SOFR or Prime as the base rate?",
                # ABR/Prime
                "What is the ABR spread or Base Rate spread?",
                "What is the Prime Rate margin?",
                "What is the Alternate Base Rate?",
                # Day Count
                "What is the Day Count Convention?",
                "What year basis is used for interest calculation (360 or 365)?",
                # Fees within rates
                "What is the commitment fee rate?",
                "What is the unused commitment fee?",
                "What is the LC fee rate?",
                "What is the Letter of Credit participation fee?",
                # Floor
                "What is the floor rate or interest rate floor?",
                "What is the minimum interest rate?",
                # Pricing grid
                "What is the pricing grid or applicable margins by tier?",
                "What are the pricing levels based on availability or usage?",
                "What is the Applicable Margin for each Pricing Level?",
                "What spread applies at each tier or level?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": True,
            "extract_signatures": False,
            "extraction_fields": [
                "referenceRate",
                "floor",
                "pricingBasis",
                "pricingTiers",
                "termSOFRSpread",
                "abrSpread",
                "interestRateType",
                "dayCountConvention",
            ],
        },

        # ==============================================================
        # Facility Terms & Commitments
        # ==============================================================
        "facilityTerms": {
            "name": "Facility Terms & Commitments",
            "description": (
                "Aggregate revolving amounts, LC/swingline sublimits, "
                "term loan commitments, maturity dates, and schedule "
                "references for commitment amounts."
            ),
            "max_pages": 10,
            "classification_hints": {
                "keywords": [
                    # Aggregate/Total amounts
                    "aggregate maximum revolving",
                    "aggregate elected revolving",
                    "total commitment",
                    "total revolving credit",
                    "maximum credit amount",
                    "aggregate commitment",
                    "facility amount",
                    "credit facility",
                    # Specific facility types
                    "lc commitment",
                    "letter of credit commitment",
                    "lc sublimit",
                    "letter of credit sublimit",
                    "swingline sublimit",
                    "swingline commitment",
                    "swing line",
                    "term loan commitment",
                    "delayed draw",
                    "incremental facility",
                    "accordion",
                    # Schedule references
                    "schedule 1.01",
                    "schedule 2.01",
                    "schedule of commitments",
                    # Dollar amount patterns
                    "$900,000,000",
                    "$800,000,000",
                    "$700,000,000",
                    "$600,000,000",
                    "$500,000,000",
                    "$400,000,000",
                    "$300,000,000",
                    "$200,000,000",
                    "$100,000,000",
                    "$50,000,000",
                    "$25,000,000",
                    # Key dates
                    "maturity date",
                    "termination date",
                    "effective date",
                    "closing date",
                    # Loan identifiers
                    "instrument type",
                    "loan type",
                    "product type",
                    # Borrower/Agent identification
                    "borrower",
                    "administrative agent",
                    "collateral agent",
                ],
                "min_keyword_matches": 2,
                "typical_pages": "article II and Schedules",
            },
            "textract_features": ["QUERIES", "TABLES"],  # TABLES for commitment amounts, sublimits
            "queries": [
                # Total Facility
                "What is the Total Credit Facility amount?",
                "What is the Aggregate Commitment amount?",
                # Revolving
                "What is the Total Revolving Credit Amount?",
                "What is the Maximum Revolving Credit Amount?",
                "What is the Aggregate Maximum Revolving Credit Amount?",
                "What is the Revolving Commitment?",
                "What is the Aggregate Elected Revolving Credit Commitment?",
                # LC
                "What is the Letter of Credit Sublimit?",
                "What is the LC Commitment?",
                "What is the maximum amount for Letters of Credit?",
                # Swingline
                "What is the Swingline Sublimit?",
                "What is the Swingline Commitment?",
                # Term Loan
                "What is the Term Loan Commitment?",
                "What is the Term Facility amount?",
                "What is the Term Loan A Commitment amount?",
                "What dollar amount is the Term Loan A Commitment?",
                "What is the Term Loan B Commitment?",
                "What is the Term Loan Bond Redemption Commitment?",
                "What is the Term Loan Bond Redemption amount?",
                # Delayed Draw / Incremental
                "What is the Delayed Draw Term Loan or DDTL Commitment?",
                "What is the Incremental Facility or Accordion amount?",
                # Maturity
                "When does the facility mature?",
                "What is the Maturity Date?",
                "What is the Revolving Credit Maturity Date?",
                "What is the Term Loan Maturity Date?",
                "What is the Term Loan A Maturity Date?",
                "What is the Term Loan Bond Redemption Maturity Date?",
                # Schedule
                "What amounts are shown in Schedule 1.01?",
                "What amounts are shown in Schedule 2.01?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "aggregateMaxRevolvingCreditAmount",
                "aggregateElectedRevolvingCreditCommitment",
                "lcCommitment",
                "lcSublimit",
                "swinglineSublimit",
                "termLoanACommitment",
                "termLoanBCommitment",
                "termLoanBondRedemption",
                "termCommitment",
                "maturityDate",
                "effectiveDate",
            ],
        },

        # ==============================================================
        # Lender Commitments (Schedule 2.01)
        # ==============================================================
        "lenderCommitments": {
            "name": "Lender Schedule (Schedule 2.01)",
            "description": (
                "Per-lender commitment amounts and applicable percentages "
                "from the commitment schedule, typically near the end of "
                "the document."
            ),
            "max_pages": 10,
            "classification_hints": {
                "keywords": [
                    # Schedule references
                    "schedule 2.01",
                    "schedule 1.01",
                    "schedule i",
                    "schedule ii",
                    "schedule of commitments",
                    "commitment schedule",
                    "lender schedule",
                    "exhibit a",
                    "annex a",
                    # Column headers in commitment tables
                    "applicable percentage",
                    "pro rata share",
                    "ratable portion",
                    "commitment percentage",
                    # Commitment types
                    "revolving credit commitment",
                    "revolving loan commitment",
                    "term loan commitment",
                    "total commitment",
                    "aggregate commitment",
                    # Percentage totals
                    "100.000000%",
                    "100.00%",
                    "100%",
                    # Common lenders (helps identify lender tables)
                    "wells fargo bank",
                    "bank of america",
                    "jpmorgan chase",
                    "citibank",
                    "goldman sachs",
                    "morgan stanley",
                    "barclays",
                    "credit suisse",
                    "deutsche bank",
                    "ubs",
                    # Dollar amounts common in commitment tables
                    "$",
                    "commitment amount",
                ],
                "min_keyword_matches": 2,
                "typical_pages": "Schedules section near end of document",
                "search_schedule_pages": True,
                "page_bonus_rules": [
                    {
                        "condition": "contains_any",
                        "patterns": [
                            "schedule 2.01",
                            "schedule 1.01",
                            "schedule of commitments",
                            "commitment schedule",
                            "lender schedule",
                            "schedule i",
                            "commitments and applicable percentages",
                        ],
                        "bonus": 10,
                    },
                    {
                        "condition": "contains_any",
                        "patterns": [
                            "100.00%",
                            "100.000000%",
                            "applicable percentage",
                            "pro rata share",
                        ],
                        "bonus": 5,
                    },
                ],
            },
            "textract_features": ["QUERIES", "TABLES"],
            "queries": [
                # Lender identification
                "Who are the Lenders?",
                "What is each Lender's name?",
                "List all Lender names",
                "Who are the Banks?",
                # Lead Arranger
                "Who is the Lead Arranger?",
                "Who are the Joint Lead Arrangers?",
                "Who is the Bookrunner?",
                # Swingline Lender
                "Who is the Swingline Lender?",
                # L/C Issuer
                "Who is the L/C Issuer?",
                "Who is the Issuing Bank?",
                "Who is the Letter of Credit Issuer?",
                # Percentage
                "What is each Lender's Applicable Percentage?",
                "What percentage commitment does each Lender have?",
                # Commitment amounts
                "What is each Lender's Revolving Credit Commitment?",
                "What is each Lender's Revolving Commitment amount?",
                "What dollar amount is each Lender's Revolving Commitment?",
                "What is each Lender's Term Loan Commitment?",
                "What is each Lender's Term Commitment?",
                "What dollar amount is each Lender's Term Loan Commitment?",
                "What is each Lender's Term Loan A Commitment?",
                "What is each Lender's Term Loan Bond Redemption Commitment?",
                # Aggregates
                "What is the Aggregate Revolving Commitment?",
                "What is the total commitment amount?",
                # Schedule
                "What commitments are shown in Schedule 1.01?",
                "What commitments are shown in Schedule 2.01?",
                "What is in the Schedule of Lenders and Commitments?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": True,
            "extract_signatures": False,
            "extraction_fields": [
                "lenderName",
                "applicablePercentage",
                "revolvingCreditCommitment",
                "electedRevolvingCreditCommitment",
                "maxRevolvingCreditAmount",
                "termCommitment",
                "termLoanACommitment",
            ],
        },

        # ==============================================================
        # Financial Covenants
        # ==============================================================
        "covenants": {
            "name": "Financial Covenants",
            "description": (
                "Fixed charge coverage ratio, leverage ratio, interest "
                "coverage, liquidity requirements, asset coverage, "
                "borrowing base utilization, and testing periods."
            ),
            "max_pages": 4,
            "classification_hints": {
                "keywords": [
                    "fixed charge coverage ratio",
                    "fccr",
                    "1.15:1.00",
                    "1.10:1.00",
                    "1.00:1.00",
                    "minimum fixed charge",
                    "leverage ratio",
                    "debt to ebitda",
                    # RBL-specific covenants
                    "current ratio",
                    "asset coverage ratio",
                    "borrowing base utilization",
                    "net worth",
                    "minimum net worth",
                    "tangible net worth",
                    "consolidated net income",
                    "total net leverage",
                    "senior secured leverage",
                    "interest coverage ratio",
                    "debt service coverage",
                    "financial covenants",
                    "section 6",
                    "section 7",
                    "article vi",
                    "article vii",
                ],
                "min_keyword_matches": 2,
                "typical_pages": "articles VI-VII",
            },
            "textract_features": ["QUERIES"],
            "queries": [
                # Fixed Charge Coverage
                "What is the Fixed Charge Coverage Ratio (FCCR) requirement?",
                # Leverage
                "What is the maximum Leverage Ratio or Debt to EBITDA requirement?",
                "What is the Total Net Leverage Ratio?",
                # Coverage ratios
                "What is the Interest Coverage Ratio requirement?",
                "What is the Current Ratio requirement?",
                "What is the Asset Coverage Ratio?",
                # Net worth / liquidity
                "What is the minimum Net Worth or Tangible Net Worth requirement?",
                "What is the minimum Liquidity or Cash requirement?",
                # General covenants
                "What are the financial maintenance covenants and their required levels?",
                "What are the negative covenants?",
                # Testing
                "What is the testing period for financial covenants?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "fixedChargeCoverageRatioMinimum",
                "leverageRatio",
                "testPeriod",
                "otherCovenants",
            ],
        },

        # ==============================================================
        # Fees
        # ==============================================================
        "fees": {
            "name": "Fees",
            "description": (
                "Commitment fee, LC fee, fronting fee, agency fee, "
                "upfront/closing fees, and penalty rates."
            ),
            "max_pages": 2,
            "classification_hints": {
                "keywords": [
                    "commitment fee",
                    "fronting fee",
                    "0.125%",
                    "0.20%",
                    "0.25%",
                    "letter of credit fee",
                    "agency fee",
                ],
                "min_keyword_matches": 2,
                "typical_pages": "article II or separate section",
            },
            "textract_features": ["QUERIES", "TABLES"],  # TABLES for fee schedules/grids
            "queries": [
                # Commitment Fee
                "What is the Commitment Fee?",
                "What is the Unused Fee or Facility Fee?",
                # LC Fee
                "What is the Letter of Credit Fee?",
                "What is the LC Participation Fee?",
                # Fronting Fee
                "What is the Fronting Fee or Issuing Bank Fee?",
                # Agency Fee
                "What is the Agency Fee or Administrative Agent Fee?",
                # Upfront Fees
                "What is the Upfront Fee or Closing Fee?",
                "What are the arrangement fees?",
                # Other fees
                "What is the Prepayment Penalty?",
                "What is the Late Charge fee?",
                "What is the Default Interest rate?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": True,
            "parallel_extraction": True,
            "extract_tables": False,
            "extract_signatures": False,
            "extraction_fields": [
                "commitmentFeeRate",
                "lcFeeRate",
                "frontingFeeRate",
                "agencyFee",
            ],
        },

        # ==============================================================
        # Signatures (last pages of the document)
        # ==============================================================
        "signatures": {
            "name": "Signatures",
            "description": (
                "Signature blocks, execution dates, witnesses, and "
                "notarizations on the last pages of the agreement."
            ),
            "max_pages": 10,
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
                "max_pages": 10,
                "typical_pages": "last 5-10 pages with signatures",
                "search_last_pages": True,
                "page_bonus_rules": [
                    {"condition": "last_n_pages", "patterns": ["10"], "bonus": 10},
                    {"condition": "last_n_pages", "patterns": ["15"], "bonus": 5},
                    {
                        "condition": "contains_any",
                        "patterns": ["in witness whereof", "witness whereof"],
                        "bonus": 5,
                    },
                    {
                        "condition": "contains_any",
                        "patterns": ["by:", "name:", "title:"],
                        "bonus": 3,
                    },
                ],
            },
            "textract_features": ["QUERIES"],
            "queries": [
                "Who signed this document as Borrower?",
                "Who signed this document as Administrative Agent?",
                "Who signed as Lender and what is their commitment amount?",
                "What date was this document executed or signed?",
                "What is the title of each signatory?",
                "Who is the witness or notary?",
            ],
            "include_pypdf_text": False,
            "render_as_images": True,
            "render_dpi": 150,
            "low_quality_fallback": False,
            "parallel_extraction": False,
            "extract_tables": False,
            "extract_signatures": True,
            "extraction_fields": [
                "signature_detected", "execution_date",
                "borrower_signatory", "agent_signatory",
                "lender_signatories",
            ],
        },
    },

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    "normalization": {
        "prompt_template": "credit_agreement",
        "llm_model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "max_tokens": 8192,
        "temperature": 0.0,
    },

    # ------------------------------------------------------------------
    # Output schema (mirrors frontend CreditAgreement TypeScript interface
    # and normalizer build_credit_agreement_prompt output format)
    # ------------------------------------------------------------------
    "output_schema": {
        "type": "object",
        "properties": {
            "creditAgreement": {
                "type": "object",
                "properties": {
                    "agreementInfo": {
                        "type": "object",
                        "properties": {
                            "documentType": {"type": "string"},
                            "agreementDate": {"type": "string"},
                            "effectiveDate": {"type": "string"},
                            "maturityDate": {"type": "string"},
                            "amendmentNumber": {"type": "string"},
                        },
                    },
                    "parties": {
                        "type": "object",
                        "properties": {
                            "borrower": {"type": "object"},
                            "coBorrowers": {"type": "array"},
                            "ultimateHoldings": {"type": "object"},
                            "intermediateHoldings": {"type": "object"},
                            "administrativeAgent": {"type": "string"},
                            "leadArrangers": {"type": "array"},
                            "swinglineLender": {"type": "string"},
                            "lcIssuer": {"type": "string"},
                            "guarantors": {"type": "array"},
                        },
                    },
                    "facilities": {"type": "array"},
                    "facilityTerms": {
                        "type": "object",
                        "properties": {
                            "aggregateMaxRevolvingCreditAmount": {"type": "number"},
                            "aggregateElectedRevolvingCreditCommitment": {"type": "number"},
                            "lcCommitment": {"type": "number"},
                            "lcSublimit": {"type": ["string", "number"]},
                            "swinglineSublimit": {"type": "number"},
                            "termLoanACommitment": {"type": "number"},
                            "termLoanBCommitment": {"type": "number"},
                            "termLoanBondRedemption": {"type": "number"},
                            "termCommitment": {"type": "number"},
                        },
                    },
                    "applicableRates": {
                        "type": "object",
                        "properties": {
                            "referenceRate": {"type": "string"},
                            "floor": {"type": "number"},
                            "pricingBasis": {"type": "string"},
                            "tiers": {"type": "array"},
                        },
                    },
                    "fees": {
                        "type": "object",
                        "properties": {
                            "commitmentFeeRate": {"type": "number"},
                            "lcFeeRate": {"type": "number"},
                            "frontingFeeRate": {"type": "number"},
                            "agencyFee": {"type": "number"},
                        },
                    },
                    "paymentTerms": {
                        "type": "object",
                        "properties": {
                            "interestPaymentDates": {"type": "array"},
                            "interestPeriodOptions": {"type": "array"},
                            "paymentDay": {"type": "string"},
                        },
                    },
                    "covenants": {
                        "type": "object",
                        "properties": {
                            "fixedChargeCoverageRatio": {"type": "object"},
                            "otherCovenants": {"type": "array"},
                        },
                    },
                    "lenderCommitments": {"type": "array"},
                },
            },
        },
    },

    # ------------------------------------------------------------------
    # PII paths -- Credit agreements have party names but no SSN/DOB
    # ------------------------------------------------------------------
    "pii_paths": [],

    # ------------------------------------------------------------------
    # Cost budget (credit agreements are large, 50-300+ pages,
    # but we only extract ~30-50 targeted pages)
    # ------------------------------------------------------------------
    "cost_budget": {
        "max_cost_usd": 2.00,
        "warn_cost_usd": 1.00,
        "textract_cost_per_page": 0.02,
        "section_priority": {
            "agreementInfo": 1,
            "facilityTerms": 2,
            "applicableRates": 3,
            "lenderCommitments": 4,
            "fees": 5,
            "covenants": 6,
            "definitions": 7,
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
    # Legacy mappings for backward compatibility
    # ------------------------------------------------------------------
    "legacy_section_map": {
        "CREDIT_AGREEMENT": "credit_agreement",
        "credit_agreement": "credit_agreement",
    },
}
