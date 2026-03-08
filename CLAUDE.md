# CLAUDE.md - Financial Documents Processing

**Pattern**: Router Pattern — Cost-Optimized Intelligent Document Processing with Plugin Architecture
**Industry**: Financial Services (Mortgage Loan Processing, Credit Agreements, BSA/KYC Compliance)
**Repository**: https://github.com/vibhupb/financial-documents-processing

## Architecture

```
S3 Upload → Upload Dialog (mode/plugin/baselines) → Trigger (SHA-256 dedup) → Step Functions:
  Extract mode:  Router → async PageIndex → Extractor → Compliance (parallel) → Normalizer
  Understand mode: Router → sync PageIndex → Compliance Evaluate → Normalizer
  Both mode:     Router → async PageIndex → Extractor + Compliance (parallel) → Normalizer
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
./scripts/cleanup.sh            # Reset S3 + DynamoDB (--compliance --plugins --all)

# Test
uv run pytest tests/            # Python unit tests (80 tests)
cd frontend && npx vitest run   # Frontend tests (MUST run from frontend/)
npm test                        # CDK tests

# Integration + E2E Testing Toolkit (real AWS)
./scripts/test-toolkit.sh                # Run all integration + E2E tests
./scripts/test-toolkit.sh --integration  # API-level integration tests only
./scripts/test-toolkit.sh --e2e          # Playwright browser tests only
./scripts/test-toolkit.sh -k compliance  # Compliance subset
./scripts/test-toolkit.sh --headed       # Playwright with visible browser

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
| POST | `/upload` | Get presigned upload URL (accepts processingMode, baselineIds, pluginId) |
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
| `docs/plans/2026-03-05-testing-toolkit-plan.md` | Implementation plan (17 tasks) |

## Version History

See `docs/VERSION_HISTORY.md` for full history. Current: **v5.2.0** (2026-03-06)

### v5.1.0 — Testing Toolkit + Bug Fixes (2026-03-05)

- **CLAUDE.md reorganization**: Split 41KB CLAUDE.md into path-scoped `.claude/rules/` (6 files) + on-demand `.claude/skills/` (4 skills). Context per request reduced ~87%.
- **Integration test suite**: 9 real-AWS tests covering plugin lifecycle, plugin enhancement reprocess, PageIndex Q&A alignment, compliance baseline CRUD, evaluation pipeline, few-shot learning loop, multi-baseline evaluation.
- **Playwright E2E suite**: 8 browser tests with Page Object Models covering upload/view, plugin rendering, compliance baseline management, evaluation UI, reviewer override, learning proof, work queue badges, evidence navigation.
- **Orchestrator**: `scripts/test-toolkit.sh` with `--integration`/`--e2e`/`-k`/`--headed` modes, HTML reports, screenshots.
- **Bug fix**: LLM JSON response parsing in compliance-evaluate (extra text after JSON array).
- **Bug fix**: Multi-baseline compliance now creates separate report per baseline (was merging into one).
- **Test fixtures**: Synthetic invoice plugin + PDF generator, compliance baseline JSON fixtures.

### v5.2.0 — Upload Mode Dialog + Compliance Pipeline (2026-03-08)

- **Upload Mode Dialog**: File drop opens modal with processing mode radio (Extract/Compliance/Both), plugin selector dropdown (auto-detect + registered plugins), baseline checkboxes (required for compliance modes)
- **Conditional tab visibility**: DataViewTabs filters by `processingMode` — extract hides Compliance, understand hides Extracted/JSON. DocumentViewer syncs active tab via useEffect when processingMode arrives from polling.
- **Compliance pipeline**: Step Functions understand-only path runs Compliance Evaluate → Normalizer. Extract-only path skips compliance via Choice+Pass (no unnecessary baseline lookups).
- **Compliance event tracking**: compliance-evaluate Lambda emits processingEvents (start/progress/complete), PipelineTracker shows 4th Compliance stage, LiveResultsStream adds amber compliance + cyan indexing colors
- **processingMode persistence**: Trigger Lambda stores processingMode in DynamoDB; Normalizer preserves it through put_item (was being wiped)
- **pluginId upload support**: API accepts optional pluginId, stored as S3 metadata for router skip
- **UI naming**: Sidebar "Baselines" → "Compliance Policies"; understand-mode documents show "Compliance Review" instead of router doc type in header and Work Queue
- **Baseline editing**: BaselineEditor name/description inline-editable in draft mode
- **Cleanup enhancements**: `--compliance` `--plugins` `--all` flags for cleanup.sh
- **Compliance-ingest fix**: maxTokens 4096→8192, salvage complete objects from truncated JSON
- **Bug fix**: Compliance evaluate JSON parsing handles LLM text before JSON array
- **Bug fix**: Step Functions catch on compliance failure preserves state for normalizer
