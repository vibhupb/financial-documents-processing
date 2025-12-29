# CLAUDE.md - AI Development Assistant Configuration

This file provides context and guidance for Claude (Opus 4.5) when working on this project.

## Project Overview

**Project Name**: Financial Documents Processing
**Pattern**: Router Pattern - Cost-Optimized Intelligent Document Processing
**Industry**: Financial Services (Mortgage Loan Processing, Credit Agreements)
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
                        │  │  │  ROUTER: Classification (Claude 3 Haiku)   │   │ │
                        │  │  │  - PyPDF text extraction                   │   │ │
                        │  │  │  - Identify document types & page numbers  │   │ │
                        │  │  └─────────────────────────────────────────────┘   │ │
                        │  │                       │                            │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  EXTRACTOR: Textract (Targeted Pages)      │   │ │
                        │  │  │  - Queries, Tables, Forms extraction       │   │ │
                        │  │  └─────────────────────────────────────────────┘   │ │
                        │  │                       │                            │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  NORMALIZER: Claude 3.5 Haiku              │   │ │
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
| Classification | Amazon Bedrock (Claude 3 Haiku) | Fast document routing (~$0.006/doc) |
| Extraction | Amazon Textract | Visual document extraction (~$0.30/doc) |
| Normalization | Amazon Bedrock (Claude 3.5 Haiku) | Data refinement (~$0.03/doc) |
| API | AWS API Gateway + Lambda | REST API for frontend |
| Frontend | React + TypeScript + Vite | Dashboard UI |
| PDF Viewing | react-pdf | In-browser PDF rendering |
| Styling | Tailwind CSS | Utility-first CSS framework |

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
│   │   └── handler.py                # Claude 3.5 Haiku normalization
│   └── layers/
│       └── pypdf/                    # PyPDF Lambda layer
│           ├── requirements.txt
│           └── build.sh
├── frontend/                         # React Dashboard
│   ├── src/
│   │   ├── components/               # Reusable UI components
│   │   │   ├── DocumentViewer.tsx    # PDF + extracted data viewer
│   │   │   ├── ExtractedValuesPanel.tsx  # Formatted data display
│   │   │   ├── ProcessingMetricsPanel.tsx  # Cost & time breakdown panel
│   │   │   ├── PDFViewer.tsx         # PDF rendering with react-pdf
│   │   │   └── StatusBadge.tsx       # Processing status indicator
│   │   ├── pages/                    # Route pages
│   │   │   ├── Dashboard.tsx         # Overview & metrics
│   │   │   ├── Upload.tsx            # Document upload with drag-drop
│   │   │   ├── Documents.tsx         # Document list
│   │   │   ├── DocumentDetail.tsx    # Document viewer page
│   │   │   └── ReviewDocument.tsx    # Review workflow page
│   │   ├── services/
│   │   │   └── api.ts                # API client (TanStack Query)
│   │   └── types/
│   │       └── index.ts              # TypeScript interfaces
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── src/                              # Python source modules
│   └── financial_docs/
│       ├── common/                   # Shared utilities
│       ├── schemas/                  # Data schemas
│       └── utils/                    # Helper functions
├── tests/                            # Python tests
├── scripts/
│   ├── deploy.sh                     # Full deployment script
│   ├── cleanup.sh                    # Reset S3 and DynamoDB for testing
│   ├── setup-dev.sh                  # Development environment setup
│   ├── generate-architecture-diagram.py  # AWS architecture diagram generator
│   └── upload-test-doc.sh            # Test document upload
├── .vscode/                          # VS Code configuration
├── package.json                      # CDK dependencies
├── tsconfig.json                     # TypeScript config
├── pyproject.toml                    # Python project config
├── cdk.json                          # CDK configuration
├── CLAUDE.md                         # This file
└── README.md                         # Project documentation
```

## Supported Document Types

### Loan Packages
- **Promissory Note**: Interest rate, principal amount, borrower names, maturity date, monthly payment
- **Closing Disclosure (TILA-RESPA)**: Loan amount, fees, closing costs, cash to close
- **Form 1003**: Borrower info, property address, employment details, SSN (masked)

### Credit Agreements
- **Agreement Info**: Document type, amendment number, agreement/effective/maturity dates
- **Parties**: Borrower, ultimate holdings, administrative agent, lead arrangers, guarantors
- **Facility Terms**: Max revolving credit, elected commitment, LC commitment/sublimit, swingline sublimit
- **Facilities**: Facility type, name, commitment amount, maturity date
- **Applicable Rates**: Reference rate, pricing basis, floor, pricing tiers (SOFR/ABR spreads, unused fees)
- **Payment Terms**: Interest period options, interest payment dates
- **Fees**: Commitment fee rate, LC fee rate, fronting fee rate, agency fee
- **Lender Commitments**: Per-lender allocations (name, percentage, term/revolving commitments)
- **Covenants**: Fixed charge coverage ratio, other covenants

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

## Key Design Decisions

### 1. Cost Optimization Strategy
- **Why**: Processing 300-page documents with full OCR costs ~$4.50
- **Solution**: Use cheap Claude Haiku ($0.006) to classify first, then extract only needed pages ($0.30)
- **Result**: 92.5% cost reduction (~$0.34 vs $4.55)

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

## Architectural Design Rationale: Router Pattern vs Alternatives

### Why Not Use Expensive LLMs (Opus 4.5, GPT-4) with Tool Calling?

Many document processing solutions use expensive foundation models with tool calling or schema-constrained outputs. While powerful, this approach has critical limitations:

| Approach | Cost/300-page Doc | Limitations |
|----------|-------------------|-------------|
| Claude Opus 4.5 (tool calling) | ~$15-25 | Token limits truncate large docs; cost prohibitive at scale |
| GPT-4 Turbo (function calling) | ~$8-15 | Rate limits; same truncation issues |
| Bedrock Data Automation (BDA) | ~$2-5 | Processes entire document; limited customization |
| **Router Pattern** | **~$0.34** | Surgical precision; 92.5% cost reduction |

### The Router Pattern Philosophy

> **"Use a cheap model to figure out WHERE to look, then use specialized tools to extract WHAT you need."**

**Key Insights:**
1. **Classification is cheap** - Claude Haiku excels at understanding document structure (~$0.006)
2. **OCR is specialized** - Textract beats LLM vision for tables/forms ($0.02/page)
3. **Normalization needs intelligence** - But not $75/M output token intelligence (~$0.03)

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
- ✅ 92.5% cost reduction: $0.34/doc vs $4.55 (Textract) or $15+ (Opus)
- ✅ Page-level audit trail: Know exactly which page data came from
- ✅ Schema flexibility: Custom extraction for any document type
- ✅ Parallel extraction: Process sections simultaneously
- ✅ Deduplication: SHA-256 prevents reprocessing identical documents
- ✅ Human-in-the-loop: Built-in review workflow

### Cost Comparison at Scale

| Volume | Router Pattern | BDA | Opus 4.5 |
|--------|----------------|-----|----------|
| 100 docs/month | $34 | ~$300 | ~$2,000 |
| 1,000 docs/month | $340 | ~$3,000 | ~$20,000 |
| 10,000 docs/month | **$3,400** | ~$30,000 | ~$200,000 |

### When to Use Router Pattern

| Use Case | Recommendation |
|----------|----------------|
| High-volume financial docs (1000+/month) | ✅ Router Pattern |
| Documents >50 pages | ✅ Router Pattern |
| Need page-level audit trail | ✅ Router Pattern |
| One-off complex analysis | Consider Opus 4.5 |
| Simple single-page forms | BDA or direct Textract |

## Common Tasks

### Adding a New Document Type

1. Update `lambda/router/handler.py`:
   - Add document type to the classification prompt
   - Add corresponding key to the JSON response

2. Update `lib/stacks/document-processing-stack.ts`:
   - Add new extraction branch in `parallelExtraction`
   - Configure appropriate Textract features

3. Update `lambda/normalizer/handler.py`:
   - Add normalization rules for the new document type
   - Update the output schema

4. Update `frontend/src/types/index.ts`:
   - Add TypeScript interface for new document type
   - Add to `LoanData` or `CreditAgreementData`

5. Update `frontend/src/components/ExtractedValuesPanel.tsx`:
   - Add new section for displaying extracted data
   - Create field component for the document type

### Adding New Fields to Credit Agreement

1. Update `lambda/normalizer/handler.py`:
   - Add field extraction in the normalization prompt

2. Update `frontend/src/types/index.ts`:
   - Add field to `CreditAgreement` interface

3. Update `frontend/src/components/ExtractedValuesPanel.tsx`:
   - Add `<FieldRow>` in `CreditAgreementFields` component

4. Update `frontend/src/pages/ReviewDocument.tsx`:
   - Add field in `renderCreditAgreementData` function

### Deploying Frontend Changes

```bash
cd frontend
npm run build
aws s3 sync dist/ s3://financial-docs-frontend-{account}-{region}/ --delete
aws cloudfront create-invalidation --distribution-id {DIST_ID} --paths "/*"
```

### Modifying Extraction Queries

Edit `lib/stacks/document-processing-stack.ts` in the `extractPromissoryNote` task:
```typescript
queries: [
  'What is the Interest Rate?',
  'Your new query here',
],
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
npm test          # CDK tests
pytest tests/     # Python tests
```

## Deployment

### Prerequisites
- Node.js 18+
- Python 3.13+
- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)

### Deploy Backend
```bash
npm install
npm run build
cdk deploy --all
```

### Deploy Frontend
```bash
cd frontend
npm install
npm run build
aws s3 sync dist/ s3://financial-docs-frontend-{account}-{region}/ --delete
aws cloudfront create-invalidation --distribution-id {DIST_ID} --paths "/*"
```

### Destroy Infrastructure
```bash
cdk destroy --all
```

## AI Assistant Instructions

When working on this project, Claude should:

### DO:
- Follow the established code patterns and naming conventions
- Maintain cost-optimization as a primary concern
- Keep Lambda functions focused and single-purpose
- Document any non-obvious design decisions
- Ensure error handling is comprehensive
- Consider audit trail requirements for financial compliance
- Keep frontend and backend types synchronized
- Use TanStack Query for data fetching in React
- Test changes locally before suggesting deployment

### DON'T:
- Introduce dependencies without justification
- Break the existing Step Functions workflow without updating all consumers
- Store PII in logs
- Use synchronous Textract for multi-page documents (use async for >1 page)
- Hardcode AWS account IDs or regions
- Skip error handling in Lambda functions
- Forget to update both frontend pages when changing data structures

### When Adding Features:
1. Consider impact on cost (is there a cheaper way?)
2. Update CLAUDE.md if architecture changes
3. Ensure backward compatibility with existing documents
4. Add appropriate CloudWatch metrics/alarms
5. Update README.md with usage instructions
6. Update frontend types and components together

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

**CORS Errors**:
- API Lambda returns CORS headers for all responses
- Check `CORS_ORIGIN` environment variable
- Ensure presigned URLs use regional S3 endpoint

## Cost Monitoring

### Per-Document Cost Breakdown (20-page Credit Agreement)

| Stage | Service | Details | Cost |
|-------|---------|---------|------|
| **Router** | Claude 3 Haiku | ~20K input + 500 output tokens | ~$0.006 |
| **Textract** | Tables + Queries | ~19 pages × $0.02/page | ~$0.38 |
| **Normalizer** | Claude 3.5 Haiku | ~6K input + 1.4K output tokens | ~$0.013 |
| **Step Functions** | Standard Workflow | 11 state transitions × $0.000025 | ~$0.0003 |
| **Lambda** | Compute | 4 invocations + ~50 GB-seconds | ~$0.0008 |
| **Total** | | | **~$0.40** |

### AWS Service Pricing Reference

| Service | Pricing | Use Case |
|---------|---------|----------|
| Claude 3 Haiku | $0.00025/1K input, $0.00125/1K output | Router |
| Claude 3.5 Haiku | $0.001/1K input, $0.005/1K output | Normalizer |
| Textract (Tables + Queries) | $0.02/page | Extraction |
| Step Functions (Standard) | $0.000025/state transition | Orchestration |
| Lambda | $0.0000002/invocation + $0.0000166667/GB-sec | Compute |

### Monthly Cost Estimates

| Volume | Per-Doc Cost | Monthly Cost |
|--------|-------------|--------------|
| 100 docs | $0.40 | $40 |
| 1,000 docs | $0.40 | $400 |
| 10,000 docs | $0.40 | $4,000 |

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
5. **Claude 3.5 Haiku** for normalization saves ~70% vs Sonnet 4
6. Content deduplication prevents reprocessing identical documents
7. **MAX_PARALLEL_WORKERS=30** for faster Textract processing (utilizes ~60% of 50 TPS quota)
8. **2GB Lambda memory** for Router/Normalizer/Extractor provides 1 vCPU for CPU-bound operations

## Version History

| Version | Date | Changes |
|---------|------|---------|
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

*This CLAUDE.md file is designed to provide context to Claude (Opus 4.5) for AI-assisted development. Keep it updated as the project evolves.*
