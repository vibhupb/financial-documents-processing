---
paths:
  - "lambda/compliance-*/**"
  - "tests/test_compliance_*"
  - "frontend/src/components/Compliance*"
  - "frontend/src/components/VerdictBadge*"
  - "frontend/src/components/ReviewerOverride*"
  - "frontend/src/pages/Baseline*"
---
# Compliance Engine

Evaluates processed documents against user-defined regulatory baselines. Runs as a **non-blocking parallel branch** in Step Functions alongside extraction.

## Architecture
```
Upload Dialog (mode + baselines + optional pluginId) → Step Functions:
  Extract mode:    Router → Extractor + Compliance (parallel) → Normalizer
  Understand mode: Router → sync PageIndex → Compliance Evaluate → Normalizer
  Both mode:       Router → async PageIndex → Extractor + Compliance (parallel) → Normalizer
```

## Three DynamoDB Tables

| Table | Key | Purpose |
|-------|-----|---------|
| `compliance-baselines` | `baselineId` | Baseline definitions with embedded requirements array |
| `compliance-reports` | `reportId` (GSI: `documentId`) | Evaluation results per document per baseline |
| `compliance-feedback` | `feedbackId` (GSI: `requirementId`) | Reviewer overrides → few-shot learning examples |

## Key Components
- **Baselines**: Named sets of requirements (draft → published → archived lifecycle)
- **Requirements**: Text rules with category, criticality (must-have/should-have/nice-to-have), confidence threshold
- **Ingest Lambda**: Parses reference docs (PDF/DOCX/PPTX/images), extracts requirements via LLM
- **Evaluate Lambda**: Compares doc text against each requirement, produces PASS/FAIL/PARTIAL/NOT_FOUND with char-offset evidence
- **Few-shot Learning**: Reviewer overrides stored as feedback, injected into future evaluation prompts
- **Processing Events**: Compliance evaluate emits `stage: "compliance"` events to DynamoDB processingEvents (start, per-batch progress, completion with score)
- **Processing Modes**: `processingMode` field on documents controls pipeline routing and frontend tab visibility

## API Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/baselines` | List baselines (optional `?status=` filter) |
| POST | `/baselines` | Create draft baseline |
| GET | `/baselines/{id}` | Get baseline with requirements |
| PUT | `/baselines/{id}` | Update baseline metadata |
| POST | `/baselines/{id}/publish` | Publish baseline (requires ≥1 requirement) |
| POST | `/baselines/{id}/requirements` | Add requirement |
| PUT | `/baselines/{id}/requirements/{reqId}` | Update requirement |
| DELETE | `/baselines/{id}/requirements/{reqId}` | Delete requirement |
| GET | `/documents/{id}/compliance` | Get compliance reports |
| GET | `/documents/{id}/compliance/{reportId}` | Get specific report |
| POST | `/documents/{id}/compliance/{reportId}/review` | Submit reviewer override |

## E2E Testing
```bash
./scripts/test-compliance-e2e.sh  # baseline → requirements → publish → upload → evaluate
```
