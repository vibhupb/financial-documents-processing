# Financial Documents Processing

## Router Pattern - Cost-Optimized Intelligent Document Processing

A production-ready AWS architecture for processing high-volume financial documents (Loan Packages, M&A Contracts, etc.) with optimal cost efficiency and precision.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        ROUTER PATTERN ARCHITECTURE                               │
│                Cost-Optimized Intelligent Document Processing                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────────────┐
│   User/API   │────▶│   S3 Bucket  │────▶│        AWS Step Functions            │
│              │     │  (ingest/)   │     │      (Orchestrator)                  │
└──────────────┘     └──────────────┘     └──────────────────────────────────────┘
                                                         │
                     ┌───────────────────────────────────┼───────────────────────┐
                     │                                   ▼                       │
                     │  ┌─────────────────────────────────────────────────────┐  │
                     │  │             LAYER 2: THE ROUTER                     │  │
                     │  │         (Classification with Claude Haiku)          │  │
                     │  │                                                     │  │
                     │  │  • Extract text snippets from all pages (PyPDF)    │  │
                     │  │  • Classify document types                         │  │
                     │  │  • Identify key page numbers                       │  │
                     │  │  • Cost: ~$0.01 per 300-page document             │  │
                     │  └─────────────────────────────────────────────────────┘  │
                     │                          │                                │
                     │         ┌────────────────┼────────────────┐               │
                     │         ▼                ▼                ▼               │
                     │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
                     │  │ Promissory  │  │  Closing    │  │  Form 1003  │        │
                     │  │    Note     │  │ Disclosure  │  │             │        │
                     │  │  (Page 5)   │  │  (Page 42)  │  │  (Page 87)  │        │
                     │  └─────────────┘  └─────────────┘  └─────────────┘        │
                     │         │                │                │               │
                     │  ┌─────────────────────────────────────────────────────┐  │
                     │  │             LAYER 3: THE SURGEON                    │  │
                     │  │       (Targeted Extraction with Textract)           │  │
                     │  │                                                     │  │
                     │  │  • Process ONLY identified pages                   │  │
                     │  │  • Queries: Interest Rate, Borrower, Maturity      │  │
                     │  │  • Tables: Fee schedules, Closing costs            │  │
                     │  │  • Forms: Key-value pair extraction                │  │
                     │  │  • Cost: ~$0.03 per document (vs $4.50 brute force)│  │
                     │  └─────────────────────────────────────────────────────┘  │
                     │                          │                                │
                     │                          ▼                                │
                     │  ┌─────────────────────────────────────────────────────┐  │
                     │  │             LAYER 4: THE CLOSER                     │  │
                     │  │      (Normalization with Claude 3.5 Sonnet)         │  │
                     │  │                                                     │  │
                     │  │  • Normalize rates (5.5% → 0.055)                  │  │
                     │  │  • Standardize names (SMITH, JOHN → John Smith)    │  │
                     │  │  • Cross-reference validation                      │  │
                     │  │  • Schema-compliant JSON output                    │  │
                     │  └─────────────────────────────────────────────────────┘  │
                     │                          │                                │
                     └──────────────────────────┼────────────────────────────────┘
                                                │
                              ┌─────────────────┴─────────────────┐
                              ▼                                   ▼
                     ┌──────────────┐                    ┌──────────────┐
                     │   DynamoDB   │                    │   S3 Bucket  │
                     │  (App Data)  │                    │   (Audit)    │
                     └──────────────┘                    └──────────────┘
```

## Key Benefits

| Benefit | Description |
|---------|-------------|
| **Cost Efficiency** | Process only relevant pages (~$0.04/doc vs $6+/doc brute force) |
| **Audit Trail** | Track exactly which page each data point came from |
| **Security** | Only process required pages, minimizing PII exposure |
| **Accuracy** | Visual grounding with Textract + LLM normalization |
| **Scalability** | Serverless architecture handles any volume |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- AWS CLI configured
- AWS CDK installed (`npm install -g aws-cdk`)

### Deploy

```bash
# Clone the repository
git clone https://github.com/vibhupb/financial-documents-processing.git
cd financial-documents-processing

# Install dependencies and deploy
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Upload a Document

```bash
# Upload a PDF to trigger processing
aws s3 cp your-loan-package.pdf s3://financial-docs-<account>-<region>/ingest/
```

## Project Structure

```
financial-documents-processing/
├── bin/
│   └── app.ts                    # CDK app entry point
├── lib/
│   └── stacks/
│       └── document-processing-stack.ts  # Main infrastructure
├── lambda/
│   ├── trigger/                  # S3 event → Step Functions
│   ├── router/                   # Document classification
│   ├── extractor/                # Textract extraction
│   ├── normalizer/               # Data normalization
│   └── layers/
│       └── pypdf/                # PyPDF Lambda layer
├── scripts/
│   ├── deploy.sh                 # Deployment script
│   └── test-local.sh             # Local testing
├── package.json
├── tsconfig.json
├── cdk.json
└── README.md
```

## Cost Analysis

### Per-Document Processing Cost

| Component | Brute Force | Router Pattern | Savings |
|-----------|-------------|----------------|--------|
| Classification | N/A | ~$0.01 (Haiku) | - |
| OCR/Extraction | $4.50 (300 pages) | $0.03 (3 pages) | 99% |
| Normalization | ~$0.05 | ~$0.02 | 60% |
| **Total** | **~$4.55** | **~$0.06** | **98.7%** |

## License

MIT License
