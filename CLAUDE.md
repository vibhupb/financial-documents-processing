# CLAUDE.md - Financial Documents Processing

**Pattern**: Router Pattern — Cost-Optimized Intelligent Document Processing with Plugin Architecture
**Industry**: Financial Services (Mortgage Loan Processing, Credit Agreements, BSA/KYC Compliance)
**Repository**: https://github.com/vibhupb/financial-documents-processing

## Architecture

```
S3 Upload → Trigger (SHA-256 dedup) → Step Functions:
  ├─ Router (Claude Haiku 4.5, ~$0.023) → classify doc type + pages
  ├─ Extractor (Textract, targeted pages) → OCR tables/forms/queries
  ├─ Normalizer (Claude Haiku 4.5) → validate + JSON output
  ├─ PageIndex (Claude Haiku 4.5) → hierarchical tree + Q&A
  └─ Compliance Engine (parallel) → evaluate against baselines
React Dashboard (CloudFront) → API Gateway → API Lambda → DynamoDB + S3
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| IaC | AWS CDK (TypeScript) |
| Orchestration | Step Functions |
| Storage | S3 + DynamoDB |
| Classification | Bedrock Claude Haiku 4.5 |
| Extraction | Amazon Textract |
| Frontend | React + TypeScript + Vite + Tailwind |
| Auth | Cognito (RBAC) |
| PII | KMS envelope encryption |

## Commands

```bash
# Deploy
./scripts/deploy-backend.sh     # Lambda/CDK (sources common.sh)
./scripts/deploy-frontend.sh    # React build + S3 sync + CloudFront invalidation
./scripts/deploy.sh             # Full deploy (use --force)
./scripts/cleanup.sh            # Reset S3 + DynamoDB for testing

# Test
uv run pytest tests/            # Python tests (80 tests)
cd frontend && npx vitest run   # Frontend tests (MUST run from frontend/)
npm test                        # CDK tests

# Dev
cd frontend && npm run dev      # Vite dev server at localhost:5173
```

## Project Structure (Key Paths)

```
bin/app.ts                              # CDK entry
lib/stacks/document-processing-stack.ts # Main infra
lambda/
  api/handler.py                        # REST API (CRUD, upload, review, compliance)
  trigger/handler.py                    # S3 event → dedup → Step Functions
  router/handler.py                     # Classification (Claude Haiku 4.5)
  extractor/handler.py                  # Textract targeted extraction
  normalizer/handler.py                 # Data normalization (Claude Haiku 4.5)
  pageindex/                            # Hierarchical tree + Q&A
  compliance-ingest/                    # Parse ref docs, extract requirements
  compliance-evaluate/                  # LLM evaluation with evidence grounding
  layers/plugins/python/document_plugins/
    types/*.py                          # Plugin configs (auto-discovered)
    prompts/*.txt                       # Normalization templates
frontend/src/
  pages/                                # Dashboard, Upload, Documents, WorkQueue, Baselines
  components/                           # DocumentViewer, ComplianceTab, GenericDataFields
  services/api.ts                       # TanStack Query API client
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List documents |
| GET | `/documents/{id}` | Document details |
| GET | `/documents/{id}/pdf` | Presigned PDF URL |
| POST | `/upload` | Get presigned upload URL |
| GET | `/review` | Documents pending review |
| POST | `/review/{id}/approve` | Approve document |
| POST | `/review/{id}/reject` | Reject document |
| GET | `/plugins` | Registered plugin types |
| POST | `/documents/{id}/ask` | Hybrid Q&A |
| POST | `/documents/{id}/extract` | Trigger deferred extraction |
| GET/POST | `/baselines[/{id}]` | Baseline CRUD |
| GET | `/documents/{id}/compliance` | Compliance reports |
| POST | `/documents/{id}/compliance/{reportId}/review` | Reviewer override |

## Key Rules

- **New doc types = 2 files only**: `types/{type}.py` + `prompts/{type}.txt` (plugin architecture)
- **Never bare `python`** — always `uv run python` via `run_python()`
- **All scripts source `common.sh`** for AWS env validation
- **Use `safe_log()`** for any PII-adjacent logging — never `print()` raw financial data
- **DynamoDB numerics**: Always `Decimal(str(value))` — floats rejected
- **Frontend tests**: Must run from `frontend/` directory (jsdom in vite.config.ts)
- **Cost-first thinking**: Router Pattern = ~$0.42/doc vs $4.55+ alternatives

## Context Organization

Detailed guidelines are split across path-scoped rules and on-demand skills:

| File | Loads When |
|------|-----------|
| `.claude/rules/core-conventions.md` | Every session (naming, DO/DON'T rules) |
| `.claude/rules/backend-lambda.md` | Working on `lambda/**/*.py` |
| `.claude/rules/frontend-react.md` | Working on `frontend/**` |
| `.claude/rules/plugin-architecture.md` | Working on plugins/router/extractor |
| `.claude/rules/compliance-engine.md` | Working on compliance code |
| `.claude/rules/testing.md` | Working on tests |
| `.claude/rules/testing-toolkit.md` | Working on `tests/integration/`, `tests/e2e/` |
| `.claude/skills/router-pattern/` | On-demand: architecture rationale |
| `.claude/skills/cost-analysis/` | On-demand: pricing & cost optimization |
| `.claude/skills/troubleshooting/` | On-demand: common issues & fixes |
| `.claude/skills/testing-toolkit/` | On-demand: integration + E2E test design |
| `docs/VERSION_HISTORY.md` | Reference only |
| `docs/CREDITS.md` | Reference only |
| `docs/plans/2026-03-05-testing-toolkit-design.md` | Testing toolkit design doc |
