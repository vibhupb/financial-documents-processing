# Financial Documents Processing

## Router Pattern — Cost-Optimized Intelligent Document Processing

A production-ready AWS serverless system for processing high-volume financial documents (Loan Packages, Credit Agreements, BSA/KYC Compliance) with a plugin architecture, semantic compliance engine, three processing modes (extract, understand, both), and a React dashboard — all at ~$0.42/doc.

![Architecture](docs/aws-architecture.png)

### Key Features

| Feature | Description |
|---------|-------------|
| Cost Optimization | ~$0.42/doc via Router Pattern vs $4.55+ brute-force alternatives |
| Plugin Architecture | 2 files per document type (`types/*.py` + `prompts/*.txt`) |
| Compliance Engine | Semantic evaluation with Sonnet 4.6, evidence grounding, learning loop |
| Processing Modes | Extract (Textract), Understand (compliance-only), Both (parallel) |
| PageIndex Tree | Hierarchical document navigation, on-demand summaries, section-aware Q&A |
| Human Review | Approve/reject/correct workflow with Cognito RBAC |
| Document Deduplication | SHA-256 content hashing prevents reprocessing |
| Real-time Pipeline Tracking | Live stage progress with processing events |
| PII Encryption | KMS envelope encryption for sensitive financial data |

## Architecture

### System Overview

```mermaid
flowchart TB
    subgraph Frontend["Frontend (CloudFront + S3)"]
        React["React Dashboard"]
    end

    subgraph API["API Layer"]
        APIGW["API Gateway"]
        APILambda["API Lambda"]
    end

    subgraph Auth["Security"]
        Cognito["Cognito (RBAC)"]
        KMS["KMS Encryption"]
    end

    subgraph Ingest["Document Ingestion"]
        S3Ingest["S3 Ingest Bucket"]
        Trigger["Trigger Lambda\n(SHA-256 dedup)"]
    end

    subgraph Processing["Step Functions Pipeline"]
        Router["Router\n(Haiku 4.5)"]
        PageIndex["PageIndex\n(Haiku 4.5)"]
        Extractor["Extractor\n(Textract)"]
        CompEval["Compliance Evaluate\n(Sonnet 4.6)"]
        Normalizer["Normalizer\n(Haiku 4.5)"]
    end

    subgraph CompMgmt["Compliance Management"]
        CompIngest["Compliance Ingest\n(Haiku 4.5)"]
    end

    subgraph Storage["Storage"]
        DDB["DynamoDB\n(6 tables)"]
        S3Audit["S3 Audit"]
    end

    React --> APIGW
    APIGW --> Cognito
    APIGW --> APILambda
    APILambda --> DDB
    APILambda --> S3Ingest
    S3Ingest --> Trigger
    Trigger --> DDB
    Trigger -->|Start Execution| Router
    Router --> PageIndex --> Extractor
    Extractor --> CompEval --> Normalizer
    Normalizer --> DDB
    Normalizer --> S3Audit
    CompIngest --> DDB
    KMS -.-> DDB
    KMS -.-> S3Audit

    style Frontend fill:#e0f2fe,stroke:#0284c7
    style Processing fill:#fef3c7,stroke:#d97706
    style Storage fill:#dcfce7,stroke:#16a34a
    style Auth fill:#fce7f3,stroke:#db2777
    style Ingest fill:#f3e8ff,stroke:#9333ea
    style CompMgmt fill:#fff7ed,stroke:#ea580c
```

### Processing Pipeline

```mermaid
flowchart TD
    Start([Start]) --> Classify["ClassifyDocument\n(Router)"]
    Classify --> ModeChoice{processingMode?}

    ModeChoice -->|understand| SyncPI["BuildPageIndex\n(sync)"]
    SyncPI --> CompEvalU["EvaluateCompliance\n(Sonnet 4.6)"]
    CompEvalU --> NormU["Normalize"]
    NormU --> Done([ProcessingComplete])

    ModeChoice -->|extract / both| AsyncPI["BuildPageIndex\n(async)"]
    AsyncPI --> ExtParallel

    subgraph ExtParallel["Parallel: Extraction + Compliance"]
        direction LR
        subgraph ExtBranch["Extraction"]
            RouteChoice{plugin?}
            RouteChoice -->|yes| MapState[/"Map State\n(max 10 concurrent)"/]
            RouteChoice -->|no| DocType{docType?}
            DocType -->|credit| Credit["7 Parallel\nSections"]
            DocType -->|mortgage| Mortgage["3 Parallel\nSections"]
            DocType -->|loan| LoanExt["Single\nExtraction"]
            MapState --> Ext["Extractor\n(Textract)"]
            Credit --> Ext
            Mortgage --> Ext
            LoanExt --> Ext
        end
        subgraph CompBranch["Compliance"]
            HasBL{baselines?}
            HasBL -->|yes| CompEvalE["EvaluateCompliance\n(Sonnet 4.6)"]
            HasBL -->|no| Skip["Skip\n(Pass)"]
        end
    end

    ExtParallel --> NormE["Normalize"]
    NormE --> Done

    style ModeChoice fill:#e9d5ff,stroke:#7c3aed
    style RouteChoice fill:#e9d5ff,stroke:#7c3aed
    style DocType fill:#e9d5ff,stroke:#7c3aed
    style HasBL fill:#e9d5ff,stroke:#7c3aed
    style Classify fill:#fed7aa,stroke:#ea580c
    style SyncPI fill:#fed7aa,stroke:#ea580c
    style AsyncPI fill:#fed7aa,stroke:#ea580c
    style CompEvalU fill:#fed7aa,stroke:#ea580c
    style CompEvalE fill:#fed7aa,stroke:#ea580c
    style Ext fill:#fed7aa,stroke:#ea580c
    style NormU fill:#fed7aa,stroke:#ea580c
    style NormE fill:#fed7aa,stroke:#ea580c
    style ExtParallel fill:#dbeafe,stroke:#2563eb
    style MapState fill:#cffafe,stroke:#0891b2
    style Done fill:#bbf7d0,stroke:#16a34a
    style Start fill:#bbf7d0,stroke:#16a34a
    style Skip fill:#f5f5f4,stroke:#78716c
```

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend
    participant API
    participant S3
    participant Trigger
    participant SFN as Step Functions
    participant Router
    participant PI as PageIndex
    participant Ext as Extractor
    participant Comp as Compliance
    participant Norm as Normalizer
    participant DDB as DynamoDB

    User->>FE: Upload PDF (mode, plugin, baselines)
    FE->>API: POST /upload
    API-->>FE: Presigned URL
    FE->>S3: PUT PDF to ingest/
    S3->>Trigger: S3 Event
    Trigger->>DDB: SHA-256 dedup check
    Trigger->>SFN: Start execution

    rect rgb(254, 243, 199)
        Note over SFN,Norm: Step Functions Pipeline
        SFN->>Router: Classify (Haiku 4.5)
        Router-->>SFN: docType, pages, extractionPlan
        SFN->>PI: Build tree (async/sync)
        SFN->>Ext: Targeted pages (Textract)
        SFN->>Comp: Evaluate vs baselines (Sonnet 4.6)
        SFN->>Norm: Normalize (Haiku 4.5)
        Norm->>DDB: Store (status=PROCESSED)
    end

    FE->>API: Poll GET /documents/{id}
    API->>DDB: Fetch
    API-->>FE: Results + compliance report
```

### Compliance Engine

```mermaid
flowchart LR
    subgraph Ingest["Baseline Ingest"]
        RefDocs["Reference Docs\n(PDF/DOCX/PPTX/XLSX)"]
        IngestLambda["Compliance Ingest\n(Haiku 4.5)"]
        RefDocs --> IngestLambda
    end

    subgraph Store["Baseline Storage"]
        BaseDDB[("compliance-baselines")]
    end
    IngestLambda --> BaseDDB

    subgraph Evaluate["Document Evaluation"]
        DocTree["Document +\nPageIndex Tree"]
        EvalLambda["Compliance Evaluate\nTree nav: Haiku\nEval: Sonnet 4.6"]
        DocTree --> EvalLambda
    end
    BaseDDB --> EvalLambda

    subgraph Reports["Reporting"]
        ReportDDB[("compliance-reports")]
        Verdicts["PASS / PARTIAL\nFAIL / NOT_APPLICABLE"]
    end
    EvalLambda --> ReportDDB --> Verdicts

    subgraph Learning["Feedback Loop"]
        ReviewUI["Reviewer Override"]
        FeedbackDDB[("compliance-feedback")]
    end
    ReportDDB --> ReviewUI --> FeedbackDDB
    FeedbackDDB -.->|Few-shot examples| EvalLambda

    style Ingest fill:#fef3c7,stroke:#d97706
    style Evaluate fill:#dbeafe,stroke:#2563eb
    style Reports fill:#dcfce7,stroke:#16a34a
    style Learning fill:#fce7f3,stroke:#db2777
    style Store fill:#f3e8ff,stroke:#9333ea
```

### Plugin Architecture

```mermaid
flowchart TD
    subgraph Studio["Plugin Studio"]
        Upload["Upload Samples"] --> Analyze["Textract Analyze"]
        Analyze --> Generate["AI Generate\n(Haiku 4.5)"]
        Generate --> Refine["Refine via NL"]
        Refine --> Test["Test on Sample"]
        Test --> Publish["Publish"]
    end

    subgraph Registry["Plugin Registry"]
        DDB[("document-plugin-configs\n60s TTL refresh")]
    end
    Publish --> DDB

    subgraph Runtime["Runtime Pipeline"]
        RouterR["Router"] --> Choice{plugin\nregistered?}
        Choice -->|yes| MapPath[/"Map State\n(max 10 concurrent)"/]
        Choice -->|no| LegacyPath["Legacy Parallel\n(by doc type)"]
        MapPath --> ExtR["Extractor\n(Textract)"]
        LegacyPath --> ExtR
        ExtR --> NormR["Normalizer"]
    end
    DDB --> RouterR

    style Studio fill:#e0f2fe,stroke:#0284c7
    style Registry fill:#f3e8ff,stroke:#9333ea
    style Runtime fill:#fef3c7,stroke:#d97706
    style Choice fill:#e9d5ff,stroke:#7c3aed
    style MapPath fill:#cffafe,stroke:#0891b2
```

> New document type = 2 files: `types/{type}.py` + `prompts/{type}.txt`

## Supported Document Types

- **Loan Packages**: Promissory Note, Closing Disclosure (TILA-RESPA), Form 1003
- **Credit Agreements**: Agreement Info, Parties, Facility Terms, Rates, Lender Commitments, Covenants
- **Custom Documents**: Any type via Plugin Studio (upload samples, AI-generate config)
- **Unknown Documents**: PageIndex tree for hierarchical browsing and Q&A

## Quick Start

### Prerequisites

- Node.js 18+, Python 3.13+, AWS CLI configured, [uv](https://github.com/astral-sh/uv)

### Deploy

```bash
git clone https://github.com/vibhupb/financial-documents-processing.git
cd financial-documents-processing
npm install                         # CDK dependencies
cd frontend && npm install && cd .. # Frontend dependencies
./scripts/deploy.sh --force         # Full deploy (backend + frontend)
```

Individual deploys: `./scripts/deploy-backend.sh` (Lambda/CDK) | `./scripts/deploy-frontend.sh` (React + S3 + CloudFront)

### Upload a Document

1. Open CloudFront URL from deploy output
2. Navigate to Upload page
3. Drop a PDF — select processing mode, plugin, and compliance baselines
4. Monitor real-time pipeline progress

## Project Structure

```
├── bin/app.ts                          # CDK entry point
├── lib/stacks/                         # CDK stack definitions
├── lambda/
│   ├── api/                            # REST API (CRUD, upload, review, compliance)
│   ├── trigger/                        # S3 event → SHA-256 dedup → Step Functions
│   ├── router/                         # Classification (Claude Haiku 4.5)
│   ├── extractor/                      # Textract targeted extraction
│   ├── normalizer/                     # Data normalization (Claude Haiku 4.5)
│   ├── pageindex/                      # Hierarchical tree builder + Q&A
│   ├── compliance-ingest/              # Parse reference docs, extract requirements
│   ├── compliance-evaluate/            # LLM evaluation with evidence grounding
│   ├── compliance-api/                 # Compliance baseline CRUD
│   └── layers/
│       ├── plugins/                    # Plugin registry + doc type configs
│       └── compliance-parsers/         # DOCX/PPTX/XLSX parsers
├── frontend/src/
│   ├── pages/                          # Dashboard, Upload, Documents, WorkQueue, Baselines
│   ├── components/                     # DocumentViewer, ComplianceTab, PipelineTracker
│   └── services/api.ts                # TanStack Query API client
├── tests/
│   ├── unit/                           # pytest (80+ tests)
│   ├── integration/                    # Real-AWS API tests (9 tests)
│   └── e2e/                            # Playwright browser tests (8 tests)
├── scripts/                            # deploy, cleanup, test-toolkit
└── docs/                               # ARCHITECTURE.md, VERSION_HISTORY.md
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Infrastructure | AWS CDK (TypeScript) | Infrastructure as Code |
| Orchestration | AWS Step Functions | Multi-mode document pipeline |
| Storage | Amazon S3 (2 buckets) | Documents + frontend hosting |
| Database | Amazon DynamoDB (6 tables) | Documents, plugins, baselines, reports, feedback, audit |
| Classification | Bedrock Claude Haiku 4.5 | Router — document type detection |
| Extraction | Amazon Textract | Targeted form/table/query extraction |
| Normalization | Bedrock Claude Haiku 4.5 | Field mapping and schema compliance |
| Compliance | Bedrock Claude Sonnet 4.6 | Semantic requirement evaluation |
| PageIndex | Bedrock Claude Haiku 4.5 | Hierarchical tree + Q&A |
| API | API Gateway + Lambda (Python 3.13) | 40+ REST endpoints |
| Frontend | React + TypeScript + Vite + Tailwind | Single-page dashboard |
| Auth | Amazon Cognito | RBAC (Admin/Reviewer/Viewer) |
| Encryption | AWS KMS | PII envelope encryption |
| PDF Rendering | react-pdf | In-browser PDF viewer |
| Monitoring | Amazon CloudWatch | Logs, metrics, alarms |

## Documentation

- [Architecture Deep Dive](docs/ARCHITECTURE.md) — cost analysis, API endpoints, DynamoDB schema, security model
- [Version History](docs/VERSION_HISTORY.md) — all releases from v1.0.0 to v5.5.0
- [Credits](docs/CREDITS.md) — open source acknowledgments

## Acknowledgments

| Project | License | Usage |
|---------|---------|-------|
| [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) | MIT | Core tree-building algorithm. Adapted for AWS Bedrock with async processing. |
| [GAIK](https://github.com/Sankgreall/GAIK) | MIT | Inspired double-pass text extraction (PyPDF + PyMuPDF fallback). |
| [PyPDF](https://github.com/py-pdf/pypdf) | BSD-3 | Primary PDF text extraction. |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 | Secondary extraction for scanned/custom-font PDFs. |
| [react-pdf](https://github.com/wojtekmaj/react-pdf) | MIT | In-browser PDF rendering. |

## License

MIT License
