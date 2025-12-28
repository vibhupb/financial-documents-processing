# Financial Documents Processing

## Router Pattern - Cost-Optimized Intelligent Document Processing

A production-ready AWS serverless architecture for processing high-volume financial documents (Loan Packages, Credit Agreements, M&A Contracts) with optimal cost efficiency and precision. Features a React dashboard for document management and review workflows.

## Live Demo

- **Dashboard**: Deployed on CloudFront (S3 + CloudFront)
- **API**: AWS API Gateway + Lambda

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FINANCIAL DOCUMENT PROCESSING                             │
│                   Router Pattern Architecture with Review Dashboard              │
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
                        │  │   (ingest/)  │     │   - Content hash (SHA-256)   │  │
                        │  └──────────────┘     │   - Deduplication check      │  │
                        │                       │   - Start Step Functions     │  │
                        │                       └──────────────────────────────┘  │
                        │                                    │                    │
                        │  ┌─────────────────────────────────▼──────────────────┐ │
                        │  │              AWS STEP FUNCTIONS                     │ │
                        │  │                 (Orchestrator)                      │ │
                        │  │                                                     │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  ROUTER: Classification (Claude 3 Haiku)   │   │ │
                        │  │  │  - PyPDF text extraction (all pages)       │   │ │
                        │  │  │  - Identify document types & page numbers  │   │ │
                        │  │  │  - Cost: ~$0.006 per document              │   │ │
                        │  │  └─────────────────────────────────────────────┘   │ │
                        │  │                       │                            │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  EXTRACTOR: Textract (Targeted Pages)      │   │ │
                        │  │  │  - Queries, Tables, Forms extraction       │   │ │
                        │  │  │  - Process ONLY identified pages           │   │ │
                        │  │  │  - Cost: ~$0.30 per document               │   │ │
                        │  │  └─────────────────────────────────────────────┘   │ │
                        │  │                       │                            │ │
                        │  │  ┌─────────────────────────────────────────────┐   │ │
                        │  │  │  NORMALIZER: Claude 3.5 Haiku              │   │ │
                        │  │  │  - Normalize rates, names, dates           │   │ │
                        │  │  │  - Cross-reference validation              │   │ │
                        │  │  │  - Schema-compliant JSON output            │   │ │
                        │  │  │  - Cost: ~$0.03 per document               │   │ │
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

### Generate Architecture Diagram

Generate a professional AWS architecture diagram with official icons:

```bash
# Create virtual environment and install dependencies
uv venv .venv && source .venv/bin/activate
uv pip install diagrams

# Generate diagrams
python3 scripts/generate-architecture-diagram.py           # Detailed vertical
python3 scripts/generate-architecture-diagram-horizontal.py  # Compact horizontal

# Output: docs/aws-architecture.png, docs/aws-architecture-horizontal.png
```

## Supported Document Types

### Loan Packages
- **Promissory Note**: Interest rate, principal amount, borrower names, maturity date
- **Closing Disclosure (TILA-RESPA)**: Loan amount, fees, cash to close
- **Form 1003**: Borrower info, property address, employment details

### Credit Agreements
- **Agreement Info**: Document type, amendment number, dates
- **Parties**: Borrower, administrative agent, lead arrangers, guarantors
- **Facility Terms**: Revolving credit amounts, LC commitments
- **Applicable Rates**: SOFR spreads, ABR spreads, pricing tiers
- **Lender Commitments**: Per-lender allocations and percentages
- **Payment Terms**: Interest periods, payment dates
- **Covenants**: Financial ratios, coverage requirements

## Key Features

| Feature | Description |
|---------|-------------|
| **Cost Optimization** | Process only relevant pages (~$0.34/doc vs $4.55 brute force) |
| **Document Deduplication** | SHA-256 content hashing prevents reprocessing |
| **Audit Trail** | Track exactly which page each data point came from |
| **Review Workflow** | Approve/Reject/Correct extracted data |
| **PDF Viewer** | Side-by-side PDF and extracted data view |
| **Real-time Status** | Live processing status updates |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.13+
- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)

### Deploy Backend

```bash
# Clone the repository
git clone https://github.com/vibhupb/financial-documents-processing.git
cd financial-documents-processing

# Install dependencies
npm install

# Deploy infrastructure
cdk deploy --all

# Or use the deployment script
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Deploy Frontend

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local with your API endpoint
echo "VITE_API_URL=https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/prod" > .env.local

# Build for production
npm run build

# Deploy to S3 (update bucket name)
aws s3 sync dist/ s3://your-frontend-bucket/ --delete

# Invalidate CloudFront cache (update distribution ID)
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### Upload a Document

Via Frontend:
1. Navigate to the Upload page
2. Drag & drop a PDF or click to browse
3. Monitor processing in real-time

Via CLI:
```bash
aws s3 cp your-document.pdf s3://financial-docs-<account>-<region>/ingest/
```

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
│   │   └── handler.py                # Document CRUD, upload, review
│   ├── trigger/                      # S3 event trigger
│   │   └── handler.py                # Deduplication, start workflow
│   ├── router/                       # Document classification
│   │   └── handler.py                # Claude Haiku classification
│   ├── extractor/                    # Data extraction
│   │   └── handler.py                # Textract targeted extraction
│   ├── normalizer/                   # Data normalization
│   │   └── handler.py                # Claude 3.5 Haiku normalization
│   └── layers/
│       └── pypdf/                    # PyPDF Lambda layer
├── frontend/                         # React Dashboard
│   ├── src/
│   │   ├── components/               # Reusable UI components
│   │   │   ├── DocumentViewer.tsx    # PDF + extracted data viewer
│   │   │   ├── ExtractedValuesPanel.tsx  # Formatted data display
│   │   │   └── PDFViewer.tsx         # PDF rendering
│   │   ├── pages/                    # Route pages
│   │   │   ├── Dashboard.tsx         # Overview & metrics
│   │   │   ├── Upload.tsx            # Document upload
│   │   │   ├── Documents.tsx         # Document list
│   │   │   ├── DocumentDetail.tsx    # Document viewer
│   │   │   └── ReviewDocument.tsx    # Review workflow
│   │   ├── services/
│   │   │   └── api.ts                # API client
│   │   └── types/
│   │       └── index.ts              # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
├── src/                              # Python source modules
│   └── financial_docs/
│       ├── common/                   # Shared utilities
│       ├── schemas/                  # Data schemas
│       └── utils/                    # Helper functions
├── tests/                            # Python tests
├── scripts/
│   ├── deploy.sh                     # Full deployment script
│   └── upload-test-doc.sh            # Test document upload
├── package.json                      # CDK dependencies
├── tsconfig.json                     # TypeScript config
├── pyproject.toml                    # Python project config
├── cdk.json                          # CDK configuration
├── CLAUDE.md                         # AI assistant context
└── README.md                         # This file
```

## Cost Analysis

### Per-Document Processing Cost (Credit Agreement ~300 pages)

| Component | Service | Details | Cost |
|-----------|---------|---------|------|
| **Router** | Claude 3 Haiku | ~20K input + 500 output tokens | ~$0.006 |
| **Extractor** | Textract | ~15 pages (Tables + Queries) | ~$0.30 |
| **Normalizer** | Claude 3.5 Haiku | ~10K input + 4K output tokens | ~$0.03 |
| **Total** | | | **~$0.34** |

### Savings vs Brute Force

| Approach | Cost | Savings |
|----------|------|---------|
| Brute Force (OCR all pages) | ~$4.55 | - |
| Router Pattern | ~$0.34 | **92.5%** |

### Monthly Cost Estimates

| Volume | Per-Doc Cost | Monthly Cost |
|--------|--------------|--------------|
| 100 docs | $0.34 | $34 |
| 1,000 docs | $0.34 | $340 |
| 10,000 docs | $0.34 | $3,400 |

## Why Router Pattern? Comparison vs Alternative Approaches

### The Problem with Brute-Force LLM Approaches

Many document processing solutions use expensive foundation models (Claude Opus 4.5, GPT-4) with tool calling or schema-constrained outputs to extract data. While powerful, this approach has critical limitations for high-volume financial document processing:

| Approach | Cost/300-page Doc | Issues |
|----------|-------------------|--------|
| **Claude Opus 4.5** (tool calling) | ~$15-25 | Extremely expensive at scale; token limits may truncate large documents |
| **GPT-4 Turbo** (function calling) | ~$8-15 | Same issues; rate limits at high volume |
| **Bedrock Data Automation (BDA)** | ~$2-5 | Better, but still processes entire document; limited customization |
| **Full Textract OCR** | ~$4.55 | Brute force all pages; no intelligence about relevance |
| **Router Pattern** | **~$0.34** | **92.5% cheaper**; surgical precision |

### Router Pattern: Key Technical Differentiators

#### 1. **Intelligent Page Selection** (Not Brute Force)
Instead of feeding an entire 300-page Credit Agreement to an expensive model, the Router Pattern:
- Uses **cheap Claude 3 Haiku** (~$0.006) to classify and identify relevant pages
- Extracts **only 15-30 pages** that contain actual data (vs 300 pages)
- Reduces downstream processing by **90%+**

```
Traditional: 300 pages × $0.015/page = $4.50
Router Pattern: 15 pages × $0.02/page = $0.30 (+ $0.04 for classification/normalization)
```

#### 2. **Specialized Tools for Each Stage**
The pattern uses the **right tool for each job**, not a single expensive model:

| Stage | Tool | Why This Choice |
|-------|------|-----------------|
| **Classification** | Claude 3 Haiku | Fast, cheap, excellent at understanding document structure |
| **OCR/Extraction** | Amazon Textract | Purpose-built for tables, forms, queries; better than LLM vision |
| **Normalization** | Claude 3.5 Haiku | Great at data cleanup, schema compliance, cross-validation |

#### 3. **Why Not Just Use Opus 4.5 or BDA?**

**Claude Opus 4.5 with Tool Calling:**
- ❌ **Cost prohibitive**: $15/M input + $75/M output tokens
- ❌ **Context limits**: May truncate 300-page documents
- ❌ **No page-level audit**: Can't trace which page data came from
- ❌ **Overkill**: Using a genius to do a librarian's job

**Bedrock Data Automation (BDA):**
- ❌ **Still processes entire document**: No intelligent page selection
- ❌ **Limited schema customization**: Pre-defined extraction templates
- ❌ **Higher per-document cost**: ~$2-5 vs $0.34
- ❌ **Less control**: Black-box processing pipeline

**Router Pattern Advantages:**
- ✅ **92.5% cost reduction**: $0.34 vs $4.55 (Textract) or $15+ (Opus)
- ✅ **Page-level audit trail**: Know exactly which page each data point came from
- ✅ **Schema flexibility**: Custom extraction for any document type
- ✅ **Parallel extraction**: Process different document sections simultaneously
- ✅ **Deduplication**: SHA-256 hashing prevents reprocessing identical documents
- ✅ **Human-in-the-loop**: Built-in review workflow for corrections

#### 4. **Production-Ready Features**

| Feature | Router Pattern | BDA | Opus Tool Calling |
|---------|----------------|-----|-------------------|
| Page-level audit trail | ✅ | ❌ | ❌ |
| Content deduplication | ✅ | ❌ | ❌ |
| Human review workflow | ✅ | Limited | ❌ |
| Custom document types | ✅ Easy | Limited | ✅ |
| Cost at 10K docs/month | **$3,400** | ~$25,000 | ~$150,000+ |
| Processing time | ~2-3 min | ~5-10 min | ~5-15 min |

### When to Use Router Pattern vs Alternatives

| Use Case | Recommended Approach |
|----------|---------------------|
| **High-volume financial docs** (1000+/month) | ✅ Router Pattern |
| **Documents >50 pages** | ✅ Router Pattern |
| **Need page-level audit trail** | ✅ Router Pattern |
| **One-off complex analysis** | Consider Opus 4.5 |
| **Simple single-page forms** | BDA or direct Textract |
| **Unstructured text extraction** | Direct LLM call |

### The Core Insight

> **"Use a cheap model to figure out WHERE to look, then use specialized tools to extract WHAT you need."**

This is fundamentally different from the "throw Opus at it" approach. The Router Pattern recognizes that:
1. **Classification is cheap** - Claude Haiku excels at understanding document structure
2. **OCR is specialized** - Textract beats LLM vision for tables and forms
3. **Normalization needs intelligence** - But not $75/M output token intelligence

The result: **Enterprise-grade document processing at startup costs**.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List all documents |
| GET | `/documents/{id}` | Get document details |
| GET | `/documents/{id}/pdf` | Get presigned PDF URL |
| GET | `/documents/{id}/status` | Get processing status |
| POST | `/upload` | Get presigned upload URL |
| GET | `/metrics` | Get processing metrics |
| GET | `/review` | List documents pending review |
| GET | `/review/{id}` | Get document for review |
| POST | `/review/{id}/approve` | Approve document |
| POST | `/review/{id}/reject` | Reject document |
| PUT | `/documents/{id}/fields` | Correct field values |
| POST | `/documents/{id}/reprocess` | Trigger reprocessing |

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Infrastructure | AWS CDK (TypeScript) | Infrastructure as Code |
| Orchestration | AWS Step Functions | Workflow management |
| Storage | Amazon S3 | Document storage & audit trail |
| Database | Amazon DynamoDB | Extracted data & metadata |
| Classification | Amazon Bedrock (Claude 3 Haiku) | Fast document routing |
| Extraction | Amazon Textract | Visual document extraction |
| Normalization | Amazon Bedrock (Claude 3.5 Haiku) | Data refinement |
| API | API Gateway + Lambda | REST API |
| Frontend | React + TypeScript + Vite | Dashboard UI |
| PDF Viewing | react-pdf | In-browser PDF rendering |
| Styling | Tailwind CSS | Utility-first CSS |

## Environment Variables

### Backend (Lambda)
- `BUCKET_NAME`: S3 bucket for documents
- `TABLE_NAME`: DynamoDB table name
- `STATE_MACHINE_ARN`: Step Functions ARN
- `CORS_ORIGIN`: Allowed CORS origin

### Frontend
- `VITE_API_URL`: Backend API endpoint

## License

MIT License
