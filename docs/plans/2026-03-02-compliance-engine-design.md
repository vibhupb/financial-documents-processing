# Compliance Engine — Baseline Document Comparison & Requirement Fulfillment

**Date**: 2026-03-02
**Status**: Approved (pending implementation)
**Author**: AI-assisted design session

---

## 1. Problem Statement

The current platform excels at extracting structured data from financial documents but has no way to evaluate whether a document meets a set of requirements defined by a reference/baseline document. Real-world use cases include:

- **Regulatory compliance**: Does this loan package meet all OCC/FDIC requirements?
- **Contract conformity**: Does this executed agreement match the approved template?
- **Report completeness**: Does this quarterly filing cover all required disclosures?

Today, compliance officers manually compare documents against checklists — a slow, error-prone process that doesn't scale.

## 2. Goals

1. **Flexible baseline system** — support regulatory compliance, contract conformity, and report completeness from a single engine
2. **Hybrid baseline building** — auto-extract requirements from reference docs (Word, PPT, PDF) + manual admin curation
3. **Full-fidelity document parsing** — extract text, tables, images, charts, and diagrams from Word/PPT/PDF with OCR and vision
4. **Actionable review workflow** — compliance reports with per-requirement verdicts, evidence citations, and reviewer override capability
5. **Continuous improvement** — reviewer feedback refines requirement matching over time via few-shot injection and confidence calibration
6. **Cost efficiency** — reuse existing Q&A pattern (tree navigation → page extraction → LLM evaluation) with batched requirements

## 3. Core Concept

### How It Works

The Compliance Engine extends the existing document processing pipeline with two new flows:

**Admin Flow (Baseline Building):**
1. Admin uploads a reference document (Word, PPT, or PDF)
2. System parses with full fidelity (text + tables + images/charts via OCR + Haiku vision)
3. System builds a PageIndex tree for the reference document
4. LLM extracts candidate requirements from the parsed content
5. Admin curates in UI: edit wording, add/remove requirements, set criticality, group into categories
6. Published baseline is stored in DynamoDB, available for matching

**User Flow (Compliance Evaluation):**
1. User uploads a document for processing (existing flow)
2. Step Functions triggers extraction (existing) AND compliance evaluation (NEW, parallel branch)
3. Compliance Lambda finds applicable baselines (by plugin type and/or explicit selection)
4. For each baseline, the engine batches requirements (5-8 per LLM call) and evaluates using the Q&A pattern:
   - Navigate PageIndex tree to find relevant sections
   - Extract page content for those sections
   - LLM evaluates requirements against page content
5. Compliance report is stored with per-requirement verdicts (PASS/FAIL/PARTIAL/NOT_FOUND)
6. Report appears in Review Queue alongside extraction results

### Reinforcement Learning Fit

Classical RLHF (fine-tuning with human preference data) isn't practical with managed Bedrock models. Instead, the system uses three complementary learning mechanisms:

| Mechanism | How It Works | Benefit |
|-----------|-------------|---------|
| **Few-shot injection** | Past reviewer corrections (3-5 recent examples) injected into evaluation prompts | LLM learns from precedent without fine-tuning |
| **Confidence calibration** | Track accuracy per requirement over time; surface low-confidence items to admin | Admins refine ambiguous requirements proactively |
| **Requirement refinement** | Analytics show which requirements frequently fail/get overridden → admin suggestions | Baselines improve through usage patterns |

## 4. Data Model

### New DynamoDB Tables

**Table: `compliance-baselines`**

| Attribute | Type | Description |
|-----------|------|-------------|
| `baselineId` (PK) | String | UUID |
| `name` | String | Human-readable name (e.g., "OCC Mortgage Requirements 2026") |
| `description` | String | Purpose and scope |
| `status` | String | `draft` / `published` / `archived` |
| `pluginIds` | List[String] | Associated plugin types (empty = standalone) |
| `sourceDocumentKey` | String | S3 key of original reference document |
| `sourceFormat` | String | `pdf` / `docx` / `pptx` |
| `requirements` | List[Map] | Array of requirement objects (see below) |
| `categories` | List[String] | Requirement groupings |
| `version` | Number | Incremented on each publish |
| `createdBy` | String | Cognito user ID |
| `createdAt` | String | ISO 8601 timestamp |
| `updatedAt` | String | ISO 8601 timestamp |

**Requirement Object Schema:**

```json
{
  "requirementId": "req-001",
  "text": "Loan agreement must specify the annual percentage rate (APR)",
  "category": "Interest & Rates",
  "criticality": "must-have",
  "sourceReference": "Section 3.2, page 12 of reference doc",
  "evaluationHint": "Look for APR, annual percentage rate, interest rate disclosure",
  "confidenceThreshold": 0.8,
  "status": "active"
}
```

**Table: `compliance-reports`**

| Attribute | Type | Description |
|-----------|------|-------------|
| `reportId` (PK) | String | UUID |
| `documentId` (SK) | String | Document being evaluated |
| `baselineId` | String | Baseline used for evaluation |
| `baselineVersion` | Number | Version of baseline at evaluation time |
| `status` | String | `pending` / `completed` / `reviewed` |
| `overallScore` | Number | Percentage of requirements met (0-100) |
| `results` | List[Map] | Per-requirement verdicts (see below) |
| `evaluatedAt` | String | ISO 8601 timestamp |
| `reviewedBy` | String | Cognito user ID (if reviewed) |
| `reviewedAt` | String | ISO 8601 timestamp |

**Result Object Schema:**

```json
{
  "requirementId": "req-001",
  "verdict": "PASS",
  "confidence": 0.92,
  "evidence": "Page 15: 'The Annual Percentage Rate (APR) shall be 6.75%'",
  "pageReferences": [15],
  "reviewerOverride": null,
  "reviewerNote": null
}
```

Verdict values: `PASS` | `FAIL` | `PARTIAL` | `NOT_FOUND`

**Table: `compliance-feedback`**

| Attribute | Type | Description |
|-----------|------|-------------|
| `feedbackId` (PK) | String | UUID |
| `baselineId` (SK) | String | Associated baseline |
| `requirementId` | String | Specific requirement |
| `documentId` | String | Document that triggered the feedback |
| `originalVerdict` | String | LLM's verdict before override |
| `correctedVerdict` | String | Reviewer's corrected verdict |
| `reviewerNote` | String | Explanation of the correction |
| `createdAt` | String | ISO 8601 timestamp |

### GSI Indexes

| Table | GSI Name | PK | SK | Purpose |
|-------|----------|----|----|---------|
| `compliance-baselines` | `pluginId-index` | `pluginIds` | `status` | Find baselines by document type |
| `compliance-reports` | `documentId-index` | `documentId` | `evaluatedAt` | All reports for a document |
| `compliance-reports` | `baselineId-index` | `baselineId` | `evaluatedAt` | All reports using a baseline |
| `compliance-feedback` | `requirementId-index` | `requirementId` | `createdAt` | Feedback history per requirement |

## 5. Processing Pipelines

### Pipeline A: Reference Document Ingestion (Admin Flow)

```
Upload reference doc (Word/PPT/PDF)
        │
        ▼
  Parse with full fidelity
  ┌─────────────────────────────────┐
  │ PDF:  PyPDF text + Textract     │
  │ Word: python-docx (text+tables) │
  │       + embedded image extract  │
  │       → Textract OCR            │
  │       → Haiku vision (charts)   │
  │ PPT:  python-pptx (text+tables) │
  │       + slide image extract     │
  │       → Textract OCR            │
  │       → Haiku vision (diagrams) │
  └─────────────────────────────────┘
        │
        ▼
  Build PageIndex tree (reuse existing)
        │
        ▼
  LLM requirement extraction
  ┌─────────────────────────────────┐
  │ Prompt: "Extract all testable   │
  │ requirements, conditions, and   │
  │ criteria from this document.    │
  │ For each, provide:              │
  │ - Requirement text              │
  │ - Category                      │
  │ - Source reference (section/pg) │
  │ - Evaluation hint (keywords)"   │
  └─────────────────────────────────┘
        │
        ▼
  Store as draft baseline
        │
        ▼
  Admin curates in UI → Publish
```

**Full-Fidelity Parsing Details:**

| Content Type | Extraction Method | Output Format |
|-------------|-------------------|---------------|
| Plain text | python-docx / python-pptx / PyPDF | Raw text |
| Tables | python-docx / python-pptx table API | Markdown tables |
| Embedded images | Extract binary → Textract OCR | OCR text |
| Charts/graphs | Extract binary → Claude Haiku 4.5 vision | Structured description (axes, values, trends) |
| Diagrams/flowcharts | Extract binary → Claude Haiku 4.5 vision | Structured description (nodes, connections, flow) |
| Headers/footers | python-docx section API | Tagged text |
| Slide notes | python-pptx notes API | Tagged text |

**Cost Estimate (Reference Doc Ingestion):**

| Step | Service | Cost |
|------|---------|------|
| Parse 50-page Word doc | python-docx (local) | $0.00 |
| OCR 10 embedded images | Textract | ~$0.20 |
| Vision on 5 charts | Haiku 4.5 (~2K tokens each) | ~$0.05 |
| Build PageIndex tree | Haiku 4.5 | ~$0.10 |
| Extract requirements | Haiku 4.5 (~10K in, 3K out) | ~$0.025 |
| **Total** | | **~$0.38** |

### Pipeline B: Compliance Evaluation (User Flow)

```
Document uploaded (existing trigger)
        │
        ▼
  Step Functions orchestrator
        │
  ┌─────┴─────┐
  │           │
  ▼           ▼
Extraction   Compliance         ← NEW parallel branch
(existing)   Evaluation
  │           │
  │     Find applicable baselines
  │     (by pluginId or explicit)
  │           │
  │     For each baseline:
  │     ┌─────────────────────────┐
  │     │ Batch requirements      │
  │     │ (5-8 per LLM call)     │
  │     │                         │
  │     │ For each batch:         │
  │     │   1. Navigate tree      │
  │     │   2. Extract pages      │
  │     │   3. LLM evaluate       │
  │     │      (with few-shot     │
  │     │       examples from     │
  │     │       feedback table)   │
  │     └─────────────────────────┘
  │           │
  │     Store compliance report
  │           │
  └─────┬─────┘
        │
        ▼
  ProcessingComplete
  (extraction + compliance results)
```

**Evaluation Prompt Structure:**

```
You are evaluating a financial document against compliance requirements.

PRIOR CORRECTIONS (learn from these):
- Requirement "Must specify APR": Previously marked FAIL but reviewer corrected to PASS
  because the rate was expressed as "annual interest rate" instead of "APR".
  Treat equivalent terminology as meeting the requirement.

REQUIREMENTS TO EVALUATE:
1. [req-001] Loan agreement must specify the APR
   Hint: Look for APR, annual percentage rate, interest rate disclosure
2. [req-002] Must include borrower signature page
   Hint: Look for signature lines, execution page, signing page
...

DOCUMENT CONTENT:
[Page content from tree-navigated sections]

For each requirement, respond with:
- verdict: PASS/FAIL/PARTIAL/NOT_FOUND
- confidence: 0.0-1.0
- evidence: Direct quote from the document (with page number)
```

**Cost Estimate (Compliance Evaluation — 42 requirements):**

| Step | Service | Cost |
|------|---------|------|
| Tree navigation (6 batches) | Haiku 4.5 | ~$0.03 |
| Page extraction | PyPDF (local) | $0.00 |
| Requirement evaluation (6 batches) | Haiku 4.5 (~8K in, 2K out each) | ~$0.08 |
| DynamoDB writes | DynamoDB | ~$0.001 |
| **Total per baseline** | | **~$0.11** |
| **Total for 3 baselines** | | **~$0.33** |

## 6. Frontend & API Design

### New Pages

| Page | Route | Purpose |
|------|-------|---------|
| Baseline Manager | `/baselines` | List, create, edit, archive baselines |
| Baseline Editor | `/baselines/:id` | Curate requirements, set criticality, categorize |
| Compliance Report | `/documents/:id/compliance/:reportId` | View per-requirement results, override verdicts |

### New DocumentViewer Tab

Add a **Compliance** tab alongside existing Summary / Extracted Values / Raw JSON tabs:

- Shows all compliance reports for the document
- Per-requirement verdict badges (green PASS, red FAIL, yellow PARTIAL, gray NOT_FOUND)
- Click requirement → highlights evidence in PDF viewer (page jump)
- Overall compliance score gauge
- Reviewer can override individual verdicts with notes

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/baselines` | List all baselines (with status filter) |
| POST | `/baselines` | Create new baseline (upload reference doc) |
| GET | `/baselines/:id` | Get baseline with all requirements |
| PUT | `/baselines/:id` | Update baseline metadata |
| DELETE | `/baselines/:id` | Archive baseline (soft delete) |
| POST | `/baselines/:id/publish` | Publish draft baseline |
| POST | `/baselines/:id/requirements` | Add requirement |
| PUT | `/baselines/:id/requirements/:reqId` | Edit requirement |
| DELETE | `/baselines/:id/requirements/:reqId` | Remove requirement |
| POST | `/baselines/:id/ingest` | Trigger reference doc re-parsing |
| GET | `/documents/:id/compliance` | List compliance reports for a document |
| GET | `/documents/:id/compliance/:reportId` | Get detailed compliance report |
| POST | `/documents/:id/compliance/:reportId/review` | Submit reviewer overrides |
| GET | `/baselines/:id/analytics` | Requirement accuracy analytics |
| POST | `/baselines/:id/suggestions` | Generate admin improvement suggestions |

### New Frontend Components

| Component | Purpose |
|-----------|---------|
| `BaselineList.tsx` | Card grid of baselines with status badges |
| `BaselineEditor.tsx` | Requirement curation UI (drag-drop categories, inline edit) |
| `RequirementRow.tsx` | Single requirement with criticality, category, edit controls |
| `ComplianceTab.tsx` | DocumentViewer tab showing compliance results |
| `ComplianceScoreGauge.tsx` | Circular gauge showing overall pass rate |
| `VerdictBadge.tsx` | Color-coded PASS/FAIL/PARTIAL/NOT_FOUND badge |
| `EvidenceHighlight.tsx` | Click-to-jump evidence citation linked to PDF viewer |
| `ReviewerOverride.tsx` | Override form (new verdict + note) |
| `ComplianceSuggestions.tsx` | Admin panel showing improvement recommendations |

## 7. Integration Points

### Step Functions Changes

Add a **Parallel** branch after classification that runs compliance evaluation alongside extraction:

```
ClassifyDocument
      │
      ▼
 ProcessingModeChoice
      │
      ▼ (default)
 PageIndexRouteChoice
      │
      ▼
 ExtractionRouteChoice
      │
 ┌────┴────┐
 │         │
 ▼         ▼
Extraction  ComplianceEvaluation   ← NEW parallel branch
(existing)  (Lambda)
 │         │
 └────┬────┘
      │
      ▼
 NormalizeData
      │
      ▼
 ProcessingComplete
```

The compliance branch is **non-blocking** — if no baselines apply, it returns immediately. If compliance fails, extraction results are still saved.

### Work Queue Integration

- Work Queue shows compliance badge next to each document (score % or "N/A")
- Filter by compliance status: All / Compliant (>90%) / Non-compliant / Not evaluated
- Sort by compliance score

### Upload Flow Integration

- Upload dialog gains optional "Evaluate against baseline" dropdown
- If a plugin type has associated baselines, they're auto-selected
- User can also select standalone baselines manually

### Review Workflow Integration

- Review page shows extraction results (existing) + compliance results (new) side by side
- Reviewer can approve/reject extraction AND override compliance verdicts in one pass
- Override actions automatically create feedback records for the learning loop

### New Lambda Functions

| Lambda | Purpose | Memory | Timeout |
|--------|---------|--------|---------|
| `doc-processor-compliance-ingest` | Parse reference docs, extract requirements | 2GB | 300s |
| `doc-processor-compliance-evaluate` | Evaluate document against baselines | 2GB | 300s |
| `doc-processor-compliance-api` | CRUD for baselines, reports, feedback | 512MB | 30s |

### New Lambda Layer

| Layer | Contents | Purpose |
|-------|----------|---------|
| `compliance-parsers` | python-docx, python-pptx, Pillow | Full-fidelity Word/PPT parsing with image extraction |

### CDK Changes

- 3 new DynamoDB tables with GSIs
- 3 new Lambda functions
- 1 new Lambda layer (compliance-parsers)
- Step Functions state machine update (parallel compliance branch)
- API Gateway: new `/baselines` and `/compliance` route groups
- S3: new `baselines/` prefix in ingest bucket for reference documents
- IAM: compliance Lambdas need Bedrock, Textract, DynamoDB, S3 access

## 8. Complete Data Flow

```
                  ADMIN FLOW                              USER FLOW
                  ──────────                              ─────────

          Upload Word/PPT/PDF                      Upload document
                  │                                       │
                  ▼                                       ▼
          Parse (text+tables+                      Trigger Lambda
          images+charts+diagrams)                        │
                  │                                       ▼
                  ▼                                 Step Functions
          Build PageIndex tree                    ┌──────┴──────┐
                  │                               │             │
                  ▼                          Extraction    Compliance
          LLM extract requirements           (existing)   (NEW)
                  │                               │             │
                  ▼                               │        Find baselines
          Admin curates in UI                     │             │
          (edit/add/remove/refine)                │        Batch evaluate
                  │                               │        (reuse Q&A pattern)
                  ▼                               │             │
          Publish baseline                        │        Store report
          (DynamoDB)                              │             │
                  │                               ▼             ▼
                  │                          ProcessingComplete
                  │                               │
                  │                               ▼
                  │                          Review Queue
                  │                          (extraction + compliance)
                  │                               │
                  │                               ▼
                  │                          Reviewer overrides
                  │                               │
                  └───────────────────────────────┘
                            │
                            ▼
                  Feedback table (learning loop)
                            │
                            ▼
                  Analytics → Admin suggestions
                            │
                            ▼
                  Admin refines baseline (cycle repeats)
```

## 9. Scope

### In Scope

- Reference document ingestion (Word, PPT, PDF) with full-fidelity parsing
- Admin baseline curation UI (create, edit, publish, archive)
- Automated compliance evaluation as Step Functions parallel branch
- Per-requirement verdicts with evidence citations and page references
- Reviewer override workflow with feedback capture
- Few-shot learning from reviewer corrections
- Confidence tracking and admin analytics
- Cost-efficient batched evaluation (~$0.11 per baseline)

### Out of Scope

- Vector database / embeddings (PageIndex + DynamoDB is sufficient)
- Real-time streaming of evaluation progress
- Cross-document compliance (comparing two uploaded documents against each other)
- Automated baseline generation from regulatory websites
- Email/Slack notifications for compliance failures
- Multi-language document support
- Fine-tuning / RLHF on Bedrock models

### Dependencies

- Existing PageIndex tree builder (Lambda + Bedrock)
- Existing Q&A pattern (tree navigation → page extraction → LLM)
- Cognito authentication (for admin/reviewer roles)
- Plugin registry (for plugin-type baseline association)

## 10. Cost Summary

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Reference doc ingestion | ~$0.38 | Once per baseline |
| Compliance evaluation (per baseline) | ~$0.11 | Per document upload |
| Compliance evaluation (3 baselines) | ~$0.33 | Per document upload |
| Total per-document cost (extraction + compliance) | ~$0.75 | Per document upload |
| DynamoDB storage (3 tables) | ~$5/month | Ongoing |
| Lambda compute | ~$2/month | At 1000 docs/month |

### Monthly Estimates

| Volume | Extraction Only | With Compliance (3 baselines) | Delta |
|--------|----------------|-------------------------------|-------|
| 100 docs/month | $42 | $75 | +$33 |
| 1,000 docs/month | $420 | $750 | +$330 |
| 10,000 docs/month | $4,200 | $7,500 | +$3,300 |

---

*Design approved 2026-03-02. Ready for implementation planning.*
