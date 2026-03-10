# Architecture Diagrams & README Restructure — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace outdated diagrams with accurate v5.5.0 architecture visuals and streamline README.

**Architecture:** 7 Mermaid diagrams (5 in README, 2 in docs/ARCHITECTURE.md) + 1 Python-generated AWS icon PNG. README restructured to be concise with detailed content moved to docs/ARCHITECTURE.md.

**Tech Stack:** Mermaid (GitHub-native), Python `diagrams` library (AWS icons), Markdown

---

### Task 1: Rewrite Python Architecture Diagram Script

**Files:**
- Modify: `scripts/generate-architecture-diagram.py`

Rewrite to reflect full v5.5.0 architecture. Keep existing light theme styling. Replace content with:

- **Frontend Cluster**: CloudFront → S3 frontend bucket
- **API Layer Cluster**: API Gateway → API Lambda, Compliance API Lambda
- **Document Ingestion Cluster**: S3 docs bucket → Trigger Lambda (SHA-256 dedup)
- **Step Functions Cluster** with sub-clusters:
  - *Router Pipeline*: Router (Haiku) → PageIndex (Haiku) → Extractor (Textract) → Normalizer (Haiku)
  - *Compliance Pipeline*: Compliance Ingest (Haiku) → Compliance Evaluate (Sonnet 4.6)
- **AI Services**: Bedrock (Haiku 4.5 + Sonnet 4.6), Textract
- **Plugin Registry**: DynamoDB `document-plugin-configs`
- **Data Storage**: 6 DynamoDB tables, S3 Audit
- **Security**: Cognito (3 RBAC groups), KMS (PII encryption)
- **Monitoring**: CloudWatch

Output: `docs/aws-architecture.png`. Use `diagrams` library with `diagrams.aws.*` providers. If Bedrock has no native icon, use `Custom` node or `Sagemaker` labeled "Bedrock".

**Verify:** `python -c "import ast; ast.parse(open('scripts/generate-architecture-diagram.py').read()); print('OK')"`

---

### Task 2: Generate Hero PNG Diagram

**Run:**
```bash
cd /Users/vibhupb/financial-documents-processing && uv run python scripts/generate-architecture-diagram.py
```

**Verify:** `ls -la docs/aws-architecture.png` — should exist and be >50KB. If script fails due to missing icon, fix with `Custom` node fallback and re-run.

---

### Task 3: Create docs/ARCHITECTURE.md Skeleton

**Files:**
- Create: `docs/ARCHITECTURE.md`

Write skeleton with section headers only: Cost Analysis, Why Router Pattern, API Endpoints, Performance Optimization, DynamoDB Schema, Frontend Component Map, Security & Auth, Environment Variables.

**Verify:** `test -f docs/ARCHITECTURE.md && head -3 docs/ARCHITECTURE.md`

---

### Task 4: Fill ARCHITECTURE.md — Cost Analysis + Why Router Pattern

**Files:**
- Modify: `docs/ARCHITECTURE.md`

Move from README and update:

**Cost Analysis** — per-document breakdown updated to ~$0.42 (includes PageIndex Haiku + compliance Sonnet 4.6). Monthly estimates: 100→$42, 1K→$420, 10K→$4,200.

**Why Router Pattern** — comparison table vs Opus (~$4.55), BDA (~$2.10), GPT-4 (~$3.20), brute-force Textract (~$0.90). Key insight: cheap models for classification/indexing/normalization, expensive models only for deep reasoning (compliance).

**Verify:** `grep '0.42' docs/ARCHITECTURE.md` should match at least twice.

---

### Task 5: Fill ARCHITECTURE.md — API Endpoints

**Files:**
- Modify: `docs/ARCHITECTURE.md`

Full endpoint reference grouped by category:
- **Documents** (14): CRUD, PDF, status, audit, tree, compliance, Q&A, extract, reprocess
- **Upload** (1): POST /upload (processingMode, baselineIds, pluginId)
- **Plugins** (9): CRUD, publish, analyze, generate, refine, test
- **Compliance Baselines** (10): CRUD, publish, requirements CRUD, upload-reference, generate-requirements
- **Review** (4): list, detail, approve, reject
- **Misc** (2): metrics, build-tree

**Verify:** Count table rows — should total ~40 endpoints.

---

### Task 6: Fill ARCHITECTURE.md — Performance + DynamoDB Schema

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Performance:** Lambda memory/timeout table (9 Lambdas). Processing time breakdown (Router 1-3s, PageIndex 15-45s, Extractor 10-30s, Compliance 30-120s, Normalizer 3-8s).

**DynamoDB Schema:** All 6 tables with PK, SK, GSIs, purpose:
- financial-documents (3 GSIs)
- compliance-baselines (pluginId-index)
- compliance-reports (documentId-index, baselineId-index)
- compliance-feedback (requirementId-index)
- document-plugin-configs (StatusIndex)
- financial-documents-pii-audit (AccessorIndex)

All PAY_PER_REQUEST, PITR enabled.

**Verify:** Cross-check GSI names against `lib/stacks/document-processing-stack.ts`.

---

### Task 7: Fill ARCHITECTURE.md — Diagrams 6 & 7

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Diagram 6 — Frontend Component Map** (Mermaid flowchart TB):
Pages (Dashboard, DocumentDetail, Upload, WorkQueue, Baselines, BaselineEditor, PluginList, PluginEditor, Login) → Components (DocumentViewer, DataViewTabs, ComplianceTab, PipelineTracker, LiveResultsStream, DocumentTreeView, DocumentQA, GenericDataFields, UploadBar) → API Layer (services/api.ts via TanStack Query).

**Diagram 7 — Security & Auth** (Mermaid flowchart LR):
User → Cognito → JWT → API Gateway Authorizer → Lambda → Role check (Admin: full+decrypt, Reviewer: review+decrypt, Viewer: read+masked) → KMS encrypt/decrypt → PII Audit Trail (DynamoDB, 7-year retention).

**Verify:** Confirm page/component names match `frontend/src/pages/` and `frontend/src/components/`.

---

### Task 8: Fill ARCHITECTURE.md — Environment Variables

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Backend** table: BUCKET_NAME, TABLE_NAME, STATE_MACHINE_ARN, CORS_ORIGIN, BEDROCK_MODEL_ID, COMPLIANCE_BASELINES_TABLE, COMPLIANCE_REPORTS_TABLE, COMPLIANCE_FEEDBACK_TABLE, PLUGIN_CONFIGS_TABLE, PII_ENCRYPTION_KEY_ID, REQUIRE_AUTH.

**Frontend** table: VITE_API_URL, VITE_COGNITO_USER_POOL_ID, VITE_COGNITO_CLIENT_ID, VITE_REQUIRE_AUTH. Note: baked at build time, requires rebuild+redeploy.

**Verify:** `grep -r 'process.env' lambda/ | grep -v __pycache__` and `grep -r 'import.meta.env' frontend/src/` to confirm coverage.

---

### Task 9: Rewrite README.md — Header, Hero PNG, Key Features

**Files:**
- Modify: `README.md`

Replace entire README. New content:
- Title + subtitle
- One-paragraph description (plugin architecture, compliance engine, 3 modes, React dashboard, ~$0.42/doc)
- Hero PNG: `![Architecture](docs/aws-architecture.png)`
- Key Features table (9 rows: Cost Optimization, Plugin Architecture, Compliance Engine, Processing Modes, PageIndex Tree, Human Review, Deduplication, Real-time Tracking, PII Encryption)
- 5 placeholder comments for Mermaid diagrams (`<!-- DIAGRAM N -->`)

**Verify:** `grep -c '<!-- DIAGRAM' README.md` should return 5.

---

### Task 10: Add to README — Diagram 1 (System Overview Mermaid)

**Files:**
- Modify: `README.md`

Replace `<!-- DIAGRAM 1 -->` with `## Architecture` → `### System Overview` containing a Mermaid flowchart TB:
- Subgraphs: Frontend, API Layer, Security, Ingest Pipeline, Processing (Step Functions), Storage, Compliance Management
- Simplified connections between services
- Color-coded styles per cluster

**Verify:** `grep 'DIAGRAM 1' README.md` returns nothing (replaced). `grep -c 'flowchart TB' README.md` returns 1.

---

### Task 11: Add to README — Diagram 2 (Step Functions Pipeline)

**Files:**
- Modify: `README.md`

Replace `<!-- DIAGRAM 2 -->` with `### Processing Pipeline` containing Mermaid flowchart TD showing:
- 3 processing modes branching from ProcessingModeChoice
- Understand: sync PageIndex → Compliance → Normalize
- Extract/Both: async PageIndex → Parallel(Extraction + Compliance) → Normalize
- Extraction: plugin Map vs legacy Parallel by doc type
- Color-coded: Choice (purple), Task (orange), Parallel (blue), Map (cyan), Success (green)

**Verify:** `grep 'processingMode' README.md` appears in diagram.

---

### Task 12: Add to README — Diagram 3 (Data Flow Sequence)

**Files:**
- Modify: `README.md`

Replace `<!-- DIAGRAM 3 -->` with `### Data Flow` containing Mermaid sequence diagram:
- 12 participants: User, Frontend, API, S3, Trigger, StepFunctions, Router, PageIndex, Extractor, Compliance, Normalizer, DynamoDB
- 17 arrows showing full upload → process → display lifecycle
- Rect highlight for Step Functions pipeline section

**Verify:** `grep 'sequenceDiagram' README.md` returns 1 match.

---

### Task 13: Add to README — Diagrams 4 & 5 (Compliance + Plugins)

**Files:**
- Modify: `README.md`

**Diagram 4** — Replace `<!-- DIAGRAM 4 -->` with `### Compliance Engine` (Mermaid flowchart LR):
Subgraphs: Baseline Ingest, Storage, Document Evaluation, Reporting, Learning Loop.
Shows: RefDocs → Ingest(Haiku) → baselines DDB → Evaluate(Sonnet) → reports DDB → Reviewer Override → feedback DDB → few-shot loop back to Evaluate.

**Diagram 5** — Replace `<!-- DIAGRAM 5 -->` with `### Plugin Architecture` (Mermaid flowchart TD):
Subgraphs: Plugin Studio, Plugin Registry, Runtime Pipeline.
Shows: Studio workflow → DDB registry (60s TTL) → Router → plugin Map vs legacy Parallel → Extractor → Normalizer.

**Verify:** `grep -c 'flowchart' README.md` returns 4. `grep -c 'sequenceDiagram' README.md` returns 1.

---

### Task 14: Add to README — Remaining Sections

**Files:**
- Modify: `README.md`

Add after diagrams:
- **Supported Document Types**: Loan Packages, Credit Agreements, Custom (Plugin Studio), Unknown (PageIndex)
- **Quick Start**: `npm install` → `./scripts/deploy.sh --force` → open CloudFront URL
- **Project Structure**: Updated tree (7 lambda dirs, 3 layers, tests/{unit,integration,e2e})
- **Tech Stack**: Full table (15 services including Cognito, KMS, CloudWatch)
- **Documentation**: Links to ARCHITECTURE.md, VERSION_HISTORY.md, CREDITS.md
- **Acknowledgments**: Keep existing
- **License**: Keep MIT

**Verify:** `wc -l README.md` — should be ~350-450 lines (streamlined vs old 470).

---

### Task 15: Delete Obsolete Files

```bash
rm -f scripts/generate-architecture-diagram-horizontal.py
rm -f docs/aws-architecture-horizontal.png
rm -f scripts/generate-stepfunctions-diagram.py
```

**Verify:** `grep -rn 'horizontal' README.md docs/ARCHITECTURE.md` returns empty.

---

### Task 16: Verify All Diagrams Render

1. **Mermaid syntax**: subgraph/end counts must match in both README.md and ARCHITECTURE.md
2. **PNG exists**: `ls -la docs/aws-architecture.png` (>0 bytes)
3. **Image refs resolve**: `grep '!\[' README.md` — verify path exists
4. **Doc links resolve**: Verify docs/ARCHITECTURE.md, docs/VERSION_HISTORY.md, docs/CREDITS.md exist
5. **No deleted file refs**: `grep -rn 'horizontal\|stepfunctions_graph' README.md docs/` returns empty

---

### Task 17: Commit All Changes

```bash
git add README.md docs/ARCHITECTURE.md docs/aws-architecture.png scripts/generate-architecture-diagram.py
git add -u  # stage deletions
git commit -m "docs: enterprise architecture diagrams and README restructure

- 5 Mermaid diagrams in README (system overview, pipeline, data flow, compliance, plugins)
- 2 Mermaid diagrams in docs/ARCHITECTURE.md (frontend components, security & auth)
- Updated Python AWS icon diagram with all v5.5.0 services
- Streamlined README with links to detailed docs/ARCHITECTURE.md
- Moved cost analysis, API endpoints, performance to ARCHITECTURE.md"
```

**Verify:** `git log --oneline -1` shows the commit. `git diff HEAD~1 --stat` lists all changed files.
