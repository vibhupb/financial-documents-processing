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
