# CLAUDE.md - AI Development Assistant Configuration

This file provides context and guidance for Claude when working on this project.

## Project Overview

**Project Name**: Financial Documents Processing
**Pattern**: Router Pattern - Cost-Optimized Intelligent Document Processing with Plugin Architecture
**Industry**: Financial Services (Mortgage Loan Processing, Credit Agreements, BSA/KYC Compliance)
**Repository**: https://github.com/vibhupb/financial-documents-processing

### Purpose

This project implements a serverless AWS architecture for processing high-volume financial documents (Loan Packages, Credit Agreements, M&A Contracts) with optimal cost efficiency and precision. It uses a "Router Pattern" to classify documents first, then extract data only from relevant pages. Includes a React dashboard for document management and review workflows.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FINANCIAL DOCUMENT PROCESSING                             │
│                   Router Pattern with React Dashboard                            │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────────────────────────────────────────────┐
│  React Frontend │     │                    AWS BACKEND                          │
│   (CloudFront)  │────▶│                                                         │
│                 │     │  ┌──────────────┐     ┌──────────────────────────────┐  │
│  - Dashboard    │     │  │  API Gateway │────▶│   API Lambda                 │  │
│  - Upload       │     │  │   (REST)     │     │   - Document CRUD            │  │
│  - Review Queue │     │  └──────────────┘     │   - Upload URLs (presigned)  │  │
│  - Doc Viewer   │     │                       │   - Review workflow          │  │
└─────────────────┘     │                       │   - Metrics                  │  │
                        │                       └──────────────────────────────┘  │
                        │                                                         │
                        │  ┌──────────────┐     ┌──────────────────────────────┐  │
                        │  │   S3 Bucket  │────▶│   Trigger Lambda             │  │
                        │  │   (ingest/)  │     │   - SHA-256 content hash     │  │
                        │  └──────────────┘     │   - Deduplication check      │  │
                        │                       │   - Start Step Functions     │  │
                        │                       └──────────────────────────────┘  │
                        │                                    │                    │
                        │  ┌─────────────────────────────────▼──────────────────┐ │
                        │  │              AWS STEP FUNCTIONS                     │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  ROUTER: Classification (Claude Haiku 4.5)  │   │ │
                        │  │  │  - PyPDF text extraction                   │   │ │
                        │  │  │  - Identify document types & page numbers  │   │ │
                        │  │  └─────────────────────────────────────────────┘   │ │
                        │  │                       │                            │ │
                        │  │     ┌─────────────────┼─────────────────┐          │ │
                        │  │     ▼                 ▼                 ▼          │ │
                        │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │ │
                        │  │  │  EXTRACTOR   │  │  PAGEINDEX   │  │COMPLIANCE│ │ │
                        │  │  │  Textract    │  │  Claude Haiku│  │  ENGINE  │ │ │
                        │  │  │  (Targeted   │  │  - Hier. tree│  │  - Ingest│ │ │
                        │  │  │   Pages)     │  │  - Summaries │  │  - Eval  │ │ │
                        │  │  └──────────────┘  │  - Q&A       │  │  - Score │ │ │
                        │  │          │         └──────────────┘  └──────────┘ │ │
                        │  │          ▼                                         │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  NORMALIZER: Claude Haiku 4.5               │   │ │
                        │  │  │  - Normalize, validate, output JSON        │   │ │
                        │  │  └─────────────────────────────────────────────┘   │ │
                        │  └──────────────────────────────────────────────────┘ │
                        │                          │                             │
                        │         ┌────────────────┴────────────────┐            │
                        │         ▼                                 ▼            │
                        │  ┌──────────────┐                 ┌──────────────┐     │
                        │  │   DynamoDB   │                 │   S3 Bucket  │     │
                        │  │  (App Data)  │                 │   (Audit)    │     │
                        │  └──────────────┘                 └──────────────┘     │
                        └─────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Infrastructure | AWS CDK (TypeScript) | Infrastructure as Code |
| Orchestration | AWS Step Functions | Workflow management |
| Storage | Amazon S3 | Document storage & audit trail |
| Database | Amazon DynamoDB | Extracted data storage |
| Classification | Amazon Bedrock (Claude Haiku 4.5) | Fast document routing (~$0.023/doc) |
| Extraction | Amazon Textract | Visual document extraction (~$0.30/doc) |
| Normalization | Amazon Bedrock (Claude Haiku 4.5) | Data refinement (~$0.013/doc) |
| API | AWS API Gateway + Lambda | REST API for frontend |
| Frontend | React + TypeScript + Vite | Dashboard UI |
| PDF Viewing | react-pdf | In-browser PDF rendering |
| Styling | Tailwind CSS | Utility-first CSS framework |
| Plugin Registry | Python TypedDict + pkgutil | Auto-discovery of document type plugins |
| PII Encryption | AWS KMS | Envelope encryption for SSN, DOB, Tax ID fields |
| Authentication | Amazon Cognito | User Pool with Admins/Reviewers/Viewers RBAC |
| PII Audit | Amazon DynamoDB | Access audit trail for compliance |
| PageIndex | Amazon Bedrock (Claude Haiku 4.5) | Hierarchical document tree building |
| Document Q&A | Amazon Bedrock (Claude Haiku 4.5) | Hybrid Q&A over extracted data + tree |
| Compliance Engine | Amazon Bedrock (Claude Haiku 4.5) + DynamoDB | Baseline comparison, requirement evaluation, reviewer overrides |
| Compliance Parsing | python-docx, python-pptx, Pillow | Reference document parsing (DOCX, PPTX, images) |

## Project Structure

```
financial-documents-processing/
├── bin/
│   └── app.ts                        # CDK app entry point
├── lib/
│   └── stacks/
│       └── document-processing-stack.ts  # Main infrastructure (CDK)
├── lambda/
│   ├── api/                          # REST API Lambda
│   │   └── handler.py                # Document CRUD, upload, review workflow
│   ├── trigger/                      # S3 event trigger
│   │   └── handler.py                # Deduplication, start Step Functions
│   ├── router/                       # Document classification
│   │   └── handler.py                # Claude Haiku classification
│   ├── extractor/                    # Data extraction
│   │   └── handler.py                # Textract targeted extraction
│   ├── normalizer/                   # Data normalization
│   │   └── handler.py                # Claude Haiku 4.5 normalization
│   ├── pageindex/                    # Hierarchical document tree + Q&A
│   │   ├── handler.py                # Lambda entry point (tree, summary, ask)
│   │   ├── tree_builder.py           # Build hierarchical tree from PDF text
│   │   ├── llm_client.py             # Bedrock LLM calls for summaries & Q&A
│   │   └── token_counter.py          # Token counting utilities
│   ├── compliance-ingest/            # Compliance baseline ingestion
│   │   ├── handler.py                # Lambda entry: parse ref docs, extract requirements
│   │   ├── parser.py                 # Reference doc parser (PDF, DOCX, PPTX, images)
│   │   ├── extractor.py              # LLM requirement extraction from parsed text
│   │   └── image_describer.py        # Bedrock image description for visual docs
│   ├── compliance-evaluate/          # Compliance evaluation against baselines
│   │   ├── handler.py                # Lambda entry: batch evaluation orchestrator
│   │   └── evaluate.py               # Per-requirement LLM evaluation with evidence grounding
│   ├── compliance-api/               # Compliance-specific API (unused — routes in api/)
│   │   └── handler.py                # Stub (compliance routes handled by main API Lambda)
│   └── layers/
│       ├── pypdf/                    # PyPDF Lambda layer
│       │   ├── requirements.txt
│       │   └── build.sh
│       ├── compliance-parsers/       # Compliance doc parsing layer
│       │   ├── requirements.txt      # python-docx, python-pptx, Pillow
│       │   └── build.sh
│       └── plugins/                  # Document type plugin layer (auto-discovered)
│           └── python/document_plugins/
│               ├── contract.py       # TypedDict plugin contract (10 types)
│               ├── registry.py       # Auto-discovery via pkgutil
│               ├── safe_log.py       # PII-safe logging (redacts SSN, DOB, etc.)
│               ├── pii_crypto.py     # KMS envelope encryption for PII fields
│               ├── types/            # One file per document type
│               │   ├── loan_package.py, credit_agreement.py, loan_agreement.py
│               │   ├── bsa_profile.py, w2.py, drivers_license.py
│               │   └── (add new doc types here - auto-discovered)
│               └── prompts/          # Normalization templates per type
│                   ├── common_preamble.txt, common_footer.txt
│                   └── {doc_type}.txt (one per plugin)
├── frontend/                         # React Dashboard
│   ├── src/
│   │   ├── components/               # Reusable UI components
│   │   │   ├── DocumentViewer.tsx    # PDF + extracted data viewer
│   │   │   ├── ExtractedValuesPanel.tsx  # Formatted data display
│   │   │   ├── ProcessingMetricsPanel.tsx  # Cost & time breakdown panel
│   │   │   ├── GenericDataFields.tsx # Schema-driven renderer (any doc type)
│   │   │   ├── BSAProfileFields.tsx  # BSA Profile custom renderer
│   │   │   ├── BooleanFlag.tsx       # Yes/No badge component
│   │   │   ├── PIIIndicator.tsx      # PII masking lock icon
│   │   │   ├── PDFViewer.tsx         # PDF rendering with react-pdf
│   │   │   ├── StatusBadge.tsx       # Processing status indicator
│   │   │   ├── DocumentTreeView.tsx  # Tree TOC with on-demand section summaries
│   │   │   ├── DocumentQA.tsx        # Hybrid Q&A (extracted data + tree navigation)
│   │   │   ├── RawJsonView.tsx       # Raw JSON viewer for extracted data
│   │   │   ├── DataViewTabs.tsx      # Tab switcher (Summary/Extracted/JSON/Compliance)
│   │   │   ├── ExtractionTrigger.tsx # Deferred extraction trigger button
│   │   │   ├── ComplianceTab.tsx     # Compliance results with evidence + page-jump
│   │   │   ├── ComplianceScoreGauge.tsx  # SVG donut chart for compliance score
│   │   │   ├── VerdictBadge.tsx      # Color-coded PASS/FAIL/PARTIAL/NOT_FOUND badge
│   │   │   └── ReviewerOverride.tsx  # Inline reviewer override form
│   │   ├── pages/                    # Route pages
│   │   │   ├── Dashboard.tsx         # Overview & metrics
│   │   │   ├── Upload.tsx            # Document upload with drag-drop
│   │   │   ├── Documents.tsx         # Document list
│   │   │   ├── DocumentDetail.tsx    # Document viewer page
│   │   │   ├── ReviewDocument.tsx    # Review workflow page
│   │   │   ├── WorkQueue.tsx         # Work queue page (+ compliance score column)
│   │   │   ├── Baselines.tsx         # Compliance baselines list with status filter
│   │   │   └── BaselineEditor.tsx    # Baseline requirement editor with publish
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx        # Cognito auth context + useAuth hook
│   │   ├── services/
│   │   │   ├── api.ts                # API client (TanStack Query)
│   │   │   └── auth.ts               # Cognito authentication service
│   │   └── types/
│   │       └── index.ts              # TypeScript interfaces
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── src/                              # Python source modules
│   └── financial_docs/
│       ├── common/                   # Shared utilities
│       ├── schemas/                  # Data schemas (DEPRECATED - use plugins)
│       └── utils/                    # Helper functions
├── tests/                            # Python tests (47 plugin + 33 compliance tests)
│   ├── sample-documents/             # Test PDFs with synthetic data
│   ├── test_api_baselines.py         # Baseline CRUD API tests (15 tests)
│   ├── test_api_compliance_reports.py # Compliance report API tests (5 tests)
│   ├── test_compliance_parser.py     # Reference doc parser tests
│   ├── test_compliance_extractor.py  # Requirement extraction tests
│   ├── test_compliance_evaluate.py   # Evaluation engine tests
│   └── test_compliance_feedback.py   # Few-shot feedback loop tests
├── scripts/
│   ├── common.sh                     # Shared env preamble (AWS validation, helpers)
│   ├── deploy-backend.sh             # CDK stack deployment
│   ├── deploy-frontend.sh            # React build + S3 sync + CloudFront invalidation
│   ├── deploy.sh                     # Full deployment (backend + frontend)
│   ├── cleanup.sh                    # Reset S3 and DynamoDB for testing
│   ├── setup-dev.sh                  # Development environment setup
│   ├── upload-test-doc.sh            # Test document upload
│   ├── encrypt-existing-pii.py       # PII encryption migration (--dry-run default)
│   ├── decrypt-for-rollback.py       # PII decryption for rollback (--confirm required)
│   ├── generate-sample-bsa.py        # Fill BSA template with synthetic data
│   └── test-compliance-e2e.sh        # Compliance Engine E2E test (baseline→upload→evaluate)
├── .vscode/                          # VS Code configuration
├── package.json                      # CDK dependencies
├── tsconfig.json                     # TypeScript config
├── pyproject.toml                    # Python project config
├── cdk.json                          # CDK configuration
├── CLAUDE.md                         # This file
└── README.md                         # Project documentation
```

## Supported Document Types (Plugin Registry)

All document types are auto-discovered from `lambda/layers/plugins/python/document_plugins/types/`. Query `GET /plugins` API for live registry.

| Plugin ID | Name | Sections | Page Strategy | PII | Cost |
|-----------|------|----------|---------------|-----|------|
| `loan_package` | Loan Package (Mortgage) | 3 (promissory note, closing disclosure, Form 1003) | LLM start-page detection | No | ~$0.34 |
| `credit_agreement` | Credit Agreement | 7 (agreement info, rates, terms, lenders, covenants, fees, definitions) | Keyword density → targeted pages | No | ~$0.40-$2.00 |
| `loan_agreement` | Loan Agreement | 8 (loan terms, interest, payment, parties, security, fees, covenants, signatures) | Keyword density → targeted pages | No | ~$0.18-$0.60 |
| `bsa_profile` | BSA Profile (KYC/CDD) | 1 (all pages, FORMS+TABLES) | All pages (5-page form) | Yes (SSN, DOB, Tax ID) | ~$0.13 |
| `w2` | W-2 Wage and Tax Statement | 1 (FORMS+QUERIES) | All pages (1-2 pages) | Yes (SSN) | ~$0.10 |
| `drivers_license` | Driver's License | 1 (QUERIES+FORMS, 300 DPI) | All pages (1 page) | Yes (DOB, License#) | ~$0.08 |

## Plugin Architecture

### Self-Registering Pattern

Adding a new document type requires **exactly 2 files** — no router, normalizer, frontend, or CDK changes:

```
lambda/layers/plugins/python/document_plugins/
  types/{doc_type}.py      ← Plugin config (classification, extraction, schema)
  prompts/{doc_type}.txt   ← Normalization prompt template
```

Everything else auto-derives:
- **Router**: Builds classification prompt from plugin registry keywords
- **Extractor**: Reads Textract features + queries from plugin section config
- **Normalizer**: Loads prompt template from plugin's `normalization.prompt_template`
- **Frontend**: `GenericDataFields` component renders ANY document type dynamically
- **API**: `GET /plugins` returns all registered types with schemas

### Three Page-Targeting Strategies

The Router Pattern's cost optimization is preserved through per-plugin configuration:

| Strategy | Config | When | Savings |
|----------|--------|------|---------|
| **KEYWORD DENSITY** | `has_sections: True` | Large docs (50-300+ pages) | ~90% (extract 30 of 300 pages) |
| **LLM START-PAGE** | `section_names: [...]` | Multi-doc packages | ~70% |
| **ALL PAGES** | `target_all_pages: True` | Small forms (1-5 pages) | N/A (already cheap) |

### Plugin Contract (DocumentPluginConfig)

Each plugin exports `PLUGIN_CONFIG: DocumentPluginConfig` with:
- `plugin_id`, `name`, `description`, `plugin_version`
- `classification` — keywords, page strategy, distinguishing rules
- `sections` — per-section Textract features, queries, keywords for page targeting
- `normalization` — prompt template name, LLM model, max tokens, field overrides
- `output_schema` — JSON Schema defining the normalized output structure
- `pii_paths` — JSON path markers for PII encryption (`beneficialOwners[*].ssn`)
- `cost_budget` — max/warn thresholds, section priority for budget trimming

## Compliance Engine

The Compliance Engine evaluates processed documents against user-defined regulatory baselines. It runs as a **non-blocking parallel branch** in Step Functions alongside the extraction pipeline.

### Architecture

```
Upload (with baselineIds) → Step Functions Parallel:
  Branch 1: Router → Extractor → Normalizer (existing pipeline)
  Branch 2: Compliance Ingest → Compliance Evaluate (new)
```

### Three DynamoDB Tables

| Table | Key | Purpose |
|-------|-----|---------|
| `compliance-baselines` | `baselineId` | Baseline definitions with embedded requirements array |
| `compliance-reports` | `reportId` (GSI: `documentId`) | Evaluation results per document per baseline |
| `compliance-feedback` | `feedbackId` (GSI: `requirementId`) | Reviewer overrides → few-shot learning examples |

### Key Components

- **Baselines**: Named sets of requirements (draft → published → archived lifecycle)
- **Requirements**: Text rules with category, criticality (must-have/should-have/nice-to-have), confidence threshold
- **Ingest Lambda**: Parses reference documents (PDF/DOCX/PPTX/images), extracts requirements via LLM
- **Evaluate Lambda**: Compares document text against each requirement, produces PASS/FAIL/PARTIAL/NOT_FOUND verdicts with character-offset evidence grounding
- **Few-shot Learning**: Reviewer overrides stored as feedback, injected into future evaluation prompts
- **Frontend**: Baselines CRUD pages, ComplianceTab with score gauge + verdict badges, ReviewerOverride inline form, baseline selection on upload

### DynamoDB Gotcha

DynamoDB rejects Python `float` types — always wrap numeric values with `Decimal(str(value))` before `put_item`/`update_item`. This applies to `confidenceThreshold` and any other numeric fields.

### Frontend Testing

Frontend tests use vitest with jsdom. **Must run from `frontend/` directory** (not project root):
```bash
cd frontend && npx vitest run
```

### API Routes (Compliance)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/baselines` | List baselines (optional `?status=` filter) |
| POST | `/baselines` | Create draft baseline |
| GET | `/baselines/{id}` | Get baseline with requirements |
| PUT | `/baselines/{id}` | Update baseline metadata |
| POST | `/baselines/{id}/publish` | Publish baseline (requires ≥1 requirement) |
| POST | `/baselines/{id}/requirements` | Add requirement to baseline |
| PUT | `/baselines/{id}/requirements/{reqId}` | Update requirement |
| DELETE | `/baselines/{id}/requirements/{reqId}` | Remove requirement |
| GET | `/documents/{id}/compliance` | Get compliance reports for document |
| GET | `/documents/{id}/compliance/{reportId}` | Get specific report |
| POST | `/documents/{id}/compliance/{reportId}/review` | Submit reviewer override |

## Development Guidelines

### Code Style

**TypeScript (CDK Infrastructure & Frontend)**:
- Use strict TypeScript settings
- Prefer `const` over `let`
- Use meaningful variable names
- Document complex logic with comments
- Use TanStack Query for data fetching in React

**Python (Lambda Functions)**:
- Follow PEP 8 style guide
- Use type hints for function signatures
- Document functions with docstrings
- Handle errors explicitly with try/except

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| CDK Constructs | PascalCase | `DocumentBucket` |
| Lambda Functions | kebab-case | `doc-processor-router` |
| Environment Variables | SCREAMING_SNAKE | `BUCKET_NAME` |
| Python functions | snake_case | `extract_page_snippets` |
| TypeScript functions | camelCase | `createStateMachine` |
| React Components | PascalCase | `DocumentViewer` |
| CSS Classes | kebab-case | `btn-primary` |

### AWS Resource Naming

- S3 Bucket: `financial-docs-{account}-{region}`
- S3 Frontend Bucket: `financial-docs-frontend-{account}-{region}`
- DynamoDB Table: `financial-documents`
- Step Functions: `financial-doc-processor`
- Lambda: `doc-processor-{function}`
- API Gateway: `doc-processor-api`
- CloudFront: For frontend distribution
- DynamoDB (Compliance): `compliance-baselines`, `compliance-reports`, `compliance-feedback`

## Key Design Decisions

### 1. Cost Optimization Strategy
- **Why**: Processing 300-page documents with full OCR costs ~$4.50
- **Solution**: Use Claude Haiku 4.5 ($0.023) to classify first, then extract only needed pages ($0.30)
- **Result**: ~91% cost reduction (~$0.42 vs $4.55)

### 2. PyPDF for Text Extraction
- **Why**: Faster and cheaper than OCR for text-based PDFs
- **Trade-off**: Won't work for scanned images (would need Textract for those)
- **Solution**: Check if page has extractable text; fallback to Textract if needed

### 3. Content-Based Deduplication
- **Why**: Avoid reprocessing identical documents
- **Solution**: SHA-256 hash of document content stored in DynamoDB GSI
- **Benefit**: Returns cached results instantly for duplicates

### 4. Parallel Extraction
- **Why**: Different document types need different extraction methods
- **Solution**: Step Functions Parallel state runs Queries, Tables, Forms extraction concurrently

### 5. Dual Storage (DynamoDB + S3)
- **DynamoDB**: Fast queries for application use, GSIs for status/review filtering
- **S3**: Complete audit trail for compliance, presigned URLs for PDF viewing

### 6. React Frontend with CloudFront
- **Why**: Modern, responsive UI for document management
- **Solution**: Vite + React + TypeScript, deployed to S3 + CloudFront
- **Features**: PDF viewer, side-by-side extracted data, review workflow

### 7. Plugin Architecture (Self-Registering)
- **Why**: Adding Credit Agreements required changes to 6+ files; doesn't scale
- **Solution**: Each document type is a self-contained plugin config + prompt template
- **Result**: New doc types = 2 files, zero changes elsewhere. GenericDataFields auto-renders UI.

### 8. Blue/Green Step Functions Routing
- **Why**: Can't break existing workflows during migration to Map state
- **Solution**: ExtractionRouteChoice checks for `extractionPlan` first, falls back to legacy Parallel branches
- **Result**: Both old and new paths coexist safely

### 9. PII Field-Level Encryption
- **Why**: BSA/KYC documents contain SSN, DOB, Tax ID
- **Solution**: KMS envelope encryption (1 API call per record, AES-256-GCM per field)
- **Modules**: `pii_crypto.py` (encrypt/decrypt), `safe_log.py` (redact in CloudWatch)

### 10. Cognito Authentication (RBAC)
- **Why**: API had zero authentication, PII would be publicly accessible
- **Solution**: Cognito User Pool with Admins/Reviewers/Viewers groups
- **Status**: User Pool provisioned, `REQUIRE_AUTH=false` (backward compat default)

### 11. Compliance Engine (Non-Blocking Parallel Branch)
- **Why**: Financial documents must be checked against regulatory baselines (OCC, CFPB, etc.)
- **Solution**: Step Functions Parallel state runs compliance evaluation alongside extraction — no added latency
- **Evidence Grounding**: Character-offset evidence (`evidenceCharStart`/`evidenceCharEnd`) for audit trail
- **Few-shot Learning**: Reviewer overrides stored as feedback, injected into future evaluation prompts
- **Result**: Automated compliance scoring with human-in-the-loop corrections that improve over time

## Architectural Design Rationale: Router Pattern vs Alternatives

### Why Not Use Expensive LLMs (Opus 4.5, GPT-4) with Tool Calling?

Many document processing solutions use expensive foundation models with tool calling or schema-constrained outputs. While powerful, this approach has critical limitations:

| Approach | Cost/300-page Doc | Limitations |
|----------|-------------------|-------------|
| Claude Opus 4.5 (tool calling) | ~$15-25 | Token limits truncate large docs; cost prohibitive at scale |
| GPT-4 Turbo (function calling) | ~$8-15 | Rate limits; same truncation issues |
| Bedrock Data Automation (BDA) | ~$2-5 | Processes entire document; limited customization |
| **Router Pattern** | **~$0.42** | Surgical precision; ~91% cost reduction |

### The Router Pattern Philosophy

> **"Use a cheap model to figure out WHERE to look, then use specialized tools to extract WHAT you need."**

**Key Insights:**
1. **Classification is cheap** - Claude Haiku 4.5 excels at understanding document structure (~$0.023)
2. **OCR is specialized** - Textract beats LLM vision for tables/forms ($0.02/page)
3. **Normalization needs intelligence** - But not $75/M output token intelligence (~$0.013)

### Why This Pattern is Superior

**vs. Claude Opus 4.5 with Tool Calling:**
- ❌ Cost prohibitive: $15/M input + $75/M output tokens
- ❌ Context limits may truncate 300-page documents
- ❌ No page-level audit trail for compliance
- ❌ Overkill: Using a genius to do a librarian's job

**vs. Bedrock Data Automation (BDA):**
- ❌ Still processes entire document (no intelligent page selection)
- ❌ Limited schema customization (pre-defined templates)
- ❌ Higher per-document cost (~$2-5 vs $0.34)
- ❌ Less control (black-box pipeline)

**Router Pattern Advantages:**
- ✅ ~91% cost reduction: $0.42/doc vs $4.55 (Textract) or $15+ (Opus)
- ✅ Page-level audit trail: Know exactly which page data came from
- ✅ Schema flexibility: Custom extraction for any document type
- ✅ Parallel extraction: Process sections simultaneously
- ✅ Deduplication: SHA-256 prevents reprocessing identical documents
- ✅ Human-in-the-loop: Built-in review workflow

### Cost Comparison at Scale

| Volume | Router Pattern | BDA | Opus 4.5 |
|--------|----------------|-----|----------|
| 100 docs/month | $42 | ~$300 | ~$2,000 |
| 1,000 docs/month | $420 | ~$3,000 | ~$20,000 |
| 10,000 docs/month | **$4,200** | ~$30,000 | ~$200,000 |

### When to Use Router Pattern

| Use Case | Recommendation |
|----------|----------------|
| High-volume financial docs (1000+/month) | ✅ Router Pattern |
| Documents >50 pages | ✅ Router Pattern |
| Need page-level audit trail | ✅ Router Pattern |
| One-off complex analysis | Consider Opus 4.5 |
| Simple single-page forms | BDA or direct Textract |

## Common Tasks

### Adding a New Document Type (2-File Plugin)

**Step 1: Create the plugin config**
```
lambda/layers/plugins/python/document_plugins/types/{doc_type}.py
```
Export `PLUGIN_CONFIG: DocumentPluginConfig` with classification keywords, sections with Textract queries, normalization config, output schema, and PII paths. Use existing plugins as templates (e.g., `w2.py` for simple forms, `credit_agreement.py` for multi-section documents).

**Step 2: Create the normalization prompt**
```
lambda/layers/plugins/python/document_plugins/prompts/{doc_type}.txt
```
Document-type-specific rules. Gets sandwiched between `common_preamble.txt` and `common_footer.txt`. Use `{{`/`}}` for JSON braces. Include explicit Textract field name → schema field mappings.

**Step 3: Deploy**
```bash
./scripts/deploy-backend.sh   # CDK auto-includes new files in plugins layer
```

**That's it.** No router, normalizer, frontend, or CDK changes needed. The plugin registry auto-discovers the new file. GenericDataFields renders it in the UI automatically.

**Optional: Custom UI component** — For polished UX, add `frontend/src/components/{DocType}Fields.tsx` and register it in `ExtractedValuesPanel.tsx`. Without this, GenericDataFields renders all fields dynamically.

### Adding New Fields to an Existing Document Type

1. Add queries to the plugin's `sections.{sectionId}.queries` list
2. Update the plugin's `output_schema` with new field definitions
3. Update the plugin's prompt template with extraction rules for the new field
4. Deploy: `./scripts/deploy-backend.sh`

### Deploying

```bash
./scripts/deploy-backend.sh    # Build layers + CDK deploy (sources common.sh)
./scripts/deploy-frontend.sh   # Build React + S3 sync + CloudFront invalidation
./scripts/cleanup.sh           # Reset S3 and DynamoDB for testing
```

### Modifying Extraction Queries

Queries now live in plugin configs, not CDK. Edit the plugin file directly:
```python
# lambda/layers/plugins/python/document_plugins/types/{doc_type}.py
"sections": {
    "my_section": {
        "queries": [
            "What is the Interest Rate?",
            "Your new query here",
        ],
    },
}
```

### Adding New Lambda Environment Variables

1. Add to CDK stack in `document-processing-stack.ts`:
```typescript
environment: {
  NEW_VAR: 'value',
},
```

2. Access in Lambda handler:
```python
new_var = os.environ.get('NEW_VAR')
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List all documents |
| GET | `/documents/{id}` | Get document details |
| GET | `/documents/{id}/pdf` | Get presigned PDF URL |
| GET | `/documents/{id}/status` | Get processing status |
| GET | `/documents/{id}/audit` | Get audit trail |
| POST | `/upload` | Get presigned upload URL |
| GET | `/metrics` | Get processing metrics |
| GET | `/review` | List documents pending review |
| GET | `/review/{id}` | Get document for review |
| POST | `/review/{id}/approve` | Approve document |
| POST | `/review/{id}/reject` | Reject document |
| PUT | `/documents/{id}/fields` | Correct field values |
| POST | `/documents/{id}/reprocess` | Trigger reprocessing |
| GET | `/plugins` | List registered document type plugins with schemas |
| POST | `/documents/{id}/ask` | Hybrid Q&A (extracted data + tree navigation) |
| POST | `/documents/{id}/section-summary` | On-demand section summary with caching |
| POST | `/documents/{id}/extract` | Trigger deferred extraction |
| GET | `/baselines` | List compliance baselines |
| POST | `/baselines` | Create draft baseline |
| GET | `/baselines/{id}` | Get baseline with requirements |
| PUT | `/baselines/{id}` | Update baseline metadata |
| POST | `/baselines/{id}/publish` | Publish baseline |
| POST | `/baselines/{id}/requirements` | Add requirement |
| PUT | `/baselines/{id}/requirements/{reqId}` | Update requirement |
| DELETE | `/baselines/{id}/requirements/{reqId}` | Delete requirement |
| GET | `/documents/{id}/compliance` | Get compliance reports |
| POST | `/documents/{id}/compliance/{reportId}/review` | Submit reviewer override |

## Testing

### Local Development
```bash
cd frontend
npm run dev  # Start Vite dev server at localhost:5173
```

### Integration Testing
```bash
# Deploy to AWS
./scripts/deploy.sh

# Upload a test document
./scripts/upload-test-doc.sh path/to/test.pdf

# Monitor execution
aws stepfunctions list-executions --state-machine-arn <arn>
```

### Unit Testing
```bash
npm test                    # CDK tests
uv run pytest tests/        # Python tests (47 plugin + 33 compliance)
cd frontend && npx vitest run  # Frontend tests (MUST run from frontend/ dir)
```

### Compliance E2E Testing
```bash
./scripts/test-compliance-e2e.sh  # Create baseline → add requirements → publish → upload → evaluate
```

## Deployment

### Prerequisites
- Node.js 18+
- Python 3.13+
- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)

### Deploy Backend
```bash
./scripts/deploy-backend.sh   # Sources common.sh, validates AWS env, builds layers + CDK deploy
```

### Deploy Frontend
```bash
./scripts/deploy-frontend.sh  # Sources common.sh, npm build, S3 sync, CloudFront invalidation
```

### Destroy Infrastructure
```bash
cdk destroy --all
```

## AI Assistant Instructions

When working on this project, Claude should:

### DO:
- **Use plugin architecture** for new document types (never hardcode in router/normalizer/frontend)
- **All scripts must source `common.sh`** for AWS env validation, `uv run python`, and helpers
- Maintain cost-optimization as a primary concern (Router Pattern)
- Use `safe_log()` for any logging that might contain PII — never `print()` raw financial data
- Follow the established code patterns and naming conventions
- Keep Lambda functions focused and single-purpose
- Ensure error handling is comprehensive
- Consider audit trail requirements for financial compliance
- Use TanStack Query for data fetching in React
- Test changes locally before suggesting deployment

### DON'T:
- **Don't add document-type-specific code to router, normalizer, or frontend** — use plugin configs
- **Don't use bare `python` or `python3`** — always use `uv run python` via `run_python()`
- **Don't deploy frontend with `--skip-build`** — always rebuild before syncing to S3
- Don't introduce dependencies without justification
- Don't store PII in logs (use safe_log module)
- Don't hardcode AWS account IDs or regions (use `common.sh` helpers)
- Don't skip error handling in Lambda functions

### When Adding Features:
1. **New document type?** Create 2 files: `types/{type}.py` + `prompts/{type}.txt` (see Plugin Architecture)
2. Consider impact on cost (is there a cheaper way?)
3. Update CLAUDE.md if architecture changes
4. Ensure backward compatibility with existing documents
5. Run `uv run pytest tests/` to verify plugin registry tests pass

## Troubleshooting

### Common Issues

**Lambda Timeout**:
- Router: Increase memory to speed up PDF processing
- Extractor: Check if Textract is running async for large docs

**Textract Errors**:
- Ensure S3 bucket is in the same region as Textract
- Check IAM permissions for textract:AnalyzeDocument

**Bedrock Errors**:
- Verify model access is enabled in AWS Console
- Check that region supports the model ID

**Step Functions Failures**:
- Check CloudWatch Logs for detailed error messages
- Verify Lambda function permissions

**Frontend Not Showing Data**:
- Check if `extractedData` vs `data` is being accessed correctly
- Verify API response structure matches TypeScript types
- Check browser console for errors
- Hard refresh (Cmd+Shift+R) after CloudFront invalidation

**DynamoDB Float Error** (`Float types are not supported`):
- Always use `Decimal(str(value))` for numeric fields in DynamoDB items
- Common in compliance baselines (`confidenceThreshold`) and scores

**Frontend Tests Fail with "document is not defined"**:
- Vitest must be run from `frontend/` directory, not project root
- The jsdom environment is configured in `frontend/vite.config.ts`

**CORS Errors**:
- API Lambda returns CORS headers for all responses
- Check `CORS_ORIGIN` environment variable
- Ensure presigned URLs use regional S3 endpoint

## Cost Monitoring

### Per-Document Cost Breakdown (20-page Credit Agreement)

| Stage | Service | Details | Cost |
|-------|---------|---------|------|
| **Router** | Claude Haiku 4.5 | ~20K input + 500 output tokens | ~$0.023 |
| **Textract** | Tables + Queries | ~19 pages × $0.02/page | ~$0.38 |
| **Normalizer** | Claude Haiku 4.5 | ~6K input + 1.4K output tokens | ~$0.013 |
| **Step Functions** | Standard Workflow | 11 state transitions × $0.000025 | ~$0.0003 |
| **Lambda** | Compute | 4 invocations + ~50 GB-seconds | ~$0.0008 |
| **Total** | | | **~$0.42** |

### AWS Service Pricing Reference

| Service | Pricing | Use Case |
|---------|---------|----------|
| Claude Haiku 4.5 | $0.001/1K input, $0.005/1K output | Router & Normalizer |
| Textract (Tables + Queries) | $0.02/page | Extraction |
| Step Functions (Standard) | $0.000025/state transition | Orchestration |
| Lambda | $0.0000002/invocation + $0.0000166667/GB-sec | Compute |

### Monthly Cost Estimates

| Volume | Per-Doc Cost | Monthly Cost |
|--------|-------------|--------------|
| 100 docs | $0.42 | $42 |
| 1,000 docs | $0.42 | $420 |
| 10,000 docs | $0.42 | $4,200 |

### Key Metrics to Track
- Bedrock token usage (per model)
- Textract API calls (AnalyzeDocument)
- Lambda invocations and duration
- Step Functions state transitions
- S3 storage and requests
- DynamoDB read/write capacity
- CloudFront requests and data transfer

### Cost Optimization Tips
1. Use Intelligent Tiering for S3 processed documents
2. Set DynamoDB TTL to auto-delete old records
3. Monitor Bedrock token usage with CloudWatch
4. Use reserved concurrency for predictable Lambda costs
5. **Claude Haiku 4.5** for classification + normalization (unified model, $1.00/MTok in, $5.00/MTok out)
6. Content deduplication prevents reprocessing identical documents
7. **MAX_PARALLEL_WORKERS=30** for faster Textract processing (utilizes ~60% of 50 TPS quota)
8. **2GB Lambda memory** for Router/Normalizer/Extractor provides 1 vCPU for CPU-bound operations

## Acknowledgments & Third-Party Credits

| Project | License | Usage in This Project |
|---------|---------|----------------------|
| [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) | MIT | Core tree-building algorithm (`lambda/pageindex/tree_builder.py`). Adapted for AWS Bedrock, async processing, on-demand summaries, and tree-assisted extraction. |
| [GAIK](https://github.com/Sankgreall/GAIK) | MIT | Inspired the double-pass text extraction approach in `lambda/router/handler.py` (PyPDF + PyMuPDF fallback for robust PDF parsing). |
| [PyPDF](https://github.com/py-pdf/pypdf) | BSD-3 | Primary PDF text extraction across Router, PageIndex, and API Lambdas. |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 | Fallback PDF extraction for custom fonts and scanned documents. |
| [react-pdf](https://github.com/wojtekmaj/react-pdf) | MIT | In-browser PDF rendering for the document viewer. |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 5.0.0 | 2026-03-02 | Compliance Engine: baseline CRUD, requirement management, parallel evaluation branch in Step Functions, LLM evidence grounding with char-offsets, reviewer overrides with few-shot learning, compliance-parsers layer (DOCX/PPTX/images), frontend (Baselines pages, ComplianceTab, score gauge, verdict badges, reviewer override), upload baseline selection, work queue compliance badges, E2E test script |
| 4.0.0 | 2026-03-01 | PageIndex integration: hierarchical document tree, on-demand section summaries (LLM + cached), hybrid Q&A (extracted data + tree navigation), SPA layout fix, view tabs (Summary/Extracted/JSON), processing mode toggle, deferred extraction |
| 3.0.0 | 2026-02-19 | Plugin architecture: self-registering document types (6 plugins), Map state, KMS encryption, Cognito auth, BSA Profile, W-2, Driver's License, GenericDataFields, common.sh scripts |
| 2.2.0 | 2024-12-29 | Performance optimization: 2GB Lambda memory, 30 parallel workers, ~35s processing time; Add cleanup.sh script; Add ProcessingMetricsPanel component |
| 2.1.0 | 2024-12-29 | Complete cost tracking: Add Step Functions + Lambda costs |
| 2.0.0 | 2024-12-25 | Add React dashboard, Review workflow, Credit Agreement support |
| 1.1.0 | 2024-12-21 | Cost optimization: Switch normalizer from Sonnet 4 to Claude 3.5 Haiku |
| 1.0.0 | 2024-12-21 | Initial implementation |

## Contact & Support

For questions about this project or AI-assisted development, refer to:
- Project README.md
- AWS Documentation
- Claude Code documentation

---

*This CLAUDE.md file is designed to provide context to Claude for AI-assisted development. Keep it updated as the project evolves.*
