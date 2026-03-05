# Testing Toolkit Design

**Date**: 2026-03-05
**Status**: Approved
**Goal**: Comprehensive integration + E2E test suite proving all major capabilities work end-to-end against real AWS.

## Table of Contents

1. [Architecture & Structure](#1-architecture--structure)
2. [Shared Infrastructure](#2-shared-infrastructure)
3. [Integration Tests — Plugin Scenarios](#3-integration-tests--plugin-scenarios)
4. [Integration Tests — PageIndex Summary](#4-integration-tests--pageindex-summary)
5. [Integration Tests — Compliance Scenarios](#5-integration-tests--compliance-scenarios)
6. [Playwright E2E Tests](#6-playwright-e2e-tests)
7. [Orchestrator & Reporting](#7-orchestrator--reporting)
8. [Dependencies & Setup](#8-dependencies--setup)

---

## 1. Architecture & Structure

### Test Target
All tests run against **real deployed AWS services** (Bedrock, Textract, DynamoDB, S3, Step Functions). No mocking. This proves the actual system works.

### Directory Layout

```
tests/
  integration/                              # Real-AWS pytest tests
    conftest.py                             # Stack config, API client, wait helpers
    test_plugin_lifecycle.py                # New plugin → deploy → process → verify
    test_plugin_enhancement.py              # Plugin field update → reprocess → verify
    test_pageindex_summary.py               # Summary/Q&A aligns with extraction values
    test_compliance_baseline_crud.py        # Baseline lifecycle (draft→publish→archive)
    test_compliance_evaluation.py           # Upload with baselines → eval → verify verdicts
    test_compliance_learning_loop.py        # Override → prompt injection → score delta
    test_compliance_multi_baseline.py       # Same doc against 2+ baselines
  e2e/                                      # Playwright browser tests
    conftest.py                             # Browser fixtures, auth, page helpers
    pages/                                  # Page Object Models
      upload_page.py
      documents_page.py
      document_detail_page.py
      work_queue_page.py
      baselines_page.py
      baseline_editor_page.py
    test_upload_and_view.py                 # Upload → process → verify UI
    test_plugin_rendering.py                # New plugin type in GenericDataFields
    test_compliance_baseline_management.py  # UI: baseline CRUD
    test_compliance_evaluation_ui.py        # UI: ComplianceTab + score gauge
    test_compliance_reviewer_override.py    # UI: submit override → badge change
    test_compliance_learning_proof.py       # UI: before/after score screenshots
    test_compliance_work_queue.py           # UI: compliance column + badges
    test_compliance_evidence_navigation.py  # UI: evidence link → PDF page jump
  fixtures/
    test_invoice.pdf                        # Synthetic 2-page invoice
    test_invoice_plugin.py                  # Plugin config for test_invoice
    test_invoice_prompt.txt                 # Normalization prompt
    compliance_baseline.json                # 3 requirements for testing
    compliance_baseline_strict.json         # 5 requirements for multi-baseline
scripts/
  test-toolkit.sh                           # Orchestrator: run all + generate report
reports/                                    # Generated at runtime
  toolkit-report.html
  screenshots/
  learning-loop-comparison.json
```

### Pytest Markers

| Marker | Purpose | Example |
|--------|---------|---------|
| `@pytest.mark.integration` | Real-AWS API tests | All `tests/integration/` |
| `@pytest.mark.e2e` | Playwright browser tests | All `tests/e2e/` |
| `@pytest.mark.slow` | Tests requiring deploy cycle | Plugin lifecycle/enhancement |
| `@pytest.mark.compliance` | Compliance-specific | All compliance tests |

## 2. Shared Infrastructure

### Integration `conftest.py`

Shared fixtures auto-discover the deployed stack and provide reusable helpers.

**`stack_config` (session-scoped):** Reads CloudFormation outputs via `aws cloudformation describe-stacks`. Returns dict with `api_url`, `bucket_name`, `documents_table`, `baselines_table`, `reports_table`, `feedback_table`.

**`api` (session-scoped):** HTTP client (requests.Session) with `base_url` pre-configured from stack_config. Methods: `get()`, `post()`, `put()`, `delete()`. Auto-adds headers.

**`s3_client` (session-scoped):** Boto3 S3 client for direct bucket operations (upload via presigned URL).

**`upload_and_wait(api, s3_client)` (function-scoped):** Callable fixture. Takes a PDF path + optional baselineIds. Gets presigned URL, uploads file, polls `GET /documents/{id}/status` every 10s until COMPLETED or 5-minute timeout. Returns `(document_id, final_status, duration_seconds)`.

**`create_published_baseline(api)` (function-scoped):** Callable fixture. Takes requirements list (text, category, criticality). Creates draft → adds requirements → publishes. Returns `baseline_id`.

**`cleanup` (autouse):** After each test: archives any baselines created during the test. Does NOT delete documents (audit trail preserved).

### Playwright `conftest.py`

**`authenticated_page` (function-scoped):** Launches browser, navigates to frontend URL (from stack_config), handles Cognito login if REQUIRE_AUTH=true, returns Playwright page object.

**`frontend_url` (session-scoped):** CloudFront distribution URL from stack_config.

### Test Fixtures

| File | Content | Used By |
|------|---------|---------|
| `test_invoice.pdf` | 2-page synthetic invoice: vendor="Acme Corp", amount=$1,234.56, date="2026-01-15", 3 line items | Plugin lifecycle + rendering |
| `test_invoice_plugin.py` | Plugin config: `plugin_id="test_invoice"`, 1 section, FORMS+QUERIES, all pages, schema with vendor/amount/date/lineItems | Plugin lifecycle |
| `test_invoice_prompt.txt` | Normalization rules for invoice fields, maps Textract output to schema | Plugin lifecycle |
| `compliance_baseline.json` | 3 requirements: "APR must be disclosed" (must-have), "Borrower name present" (must-have), "Signature date included" (should-have) | Compliance eval + learning loop |
| `compliance_baseline_strict.json` | 5 requirements: adds "Lender NMLS number" + "Equal housing logo" | Multi-baseline test |

## 3. Integration Tests — Plugin Scenarios

### 3a. `test_plugin_lifecycle.py` — New Plugin Full Pipeline

**Proves**: A brand-new document type goes from plugin file → auto-discovery → routing → extraction → normalization → queryable via API.

**Setup**: Copy `fixtures/test_invoice_plugin.py` → `lambda/layers/plugins/python/document_plugins/types/test_invoice.py` and `fixtures/test_invoice_prompt.txt` → `prompts/test_invoice.txt`. Run `./scripts/deploy-backend.sh` to pick up the new plugin in the Lambda layer.

**Test Steps**:
1. `GET /plugins` → assert `test_invoice` appears in registry with correct schema
2. Upload `fixtures/test_invoice.pdf` via presigned URL → poll status until COMPLETED
3. `GET /documents/{id}` → assert `documentType == "test_invoice"`
4. Assert `extractedData` contains expected fields: `vendor`, `amount`, `invoiceDate`, `lineItems`
5. Assert `vendor == "Acme Corp"` and `amount` contains `1234.56`
6. `GET /documents/{id}/audit` → verify all pipeline stages recorded (ROUTER, EXTRACTOR, NORMALIZER)

**Teardown**: Remove test plugin files, redeploy to restore original state.

**Markers**: `@pytest.mark.integration`, `@pytest.mark.slow`

---

### 3b. `test_plugin_enhancement.py` — Field Addition on Reprocess

**Proves**: When a plugin is updated with a new extraction query, reprocessing the same document picks up the new field.

**Setup**: Record current `loan_agreement` plugin schema. Patch `loan_agreement.py` to add query `"What is the Prepayment Penalty?"` and add `prepaymentPenalty` to output_schema. Patch `loan_agreement.txt` prompt with extraction rule. Deploy backend.

**Test Steps**:
1. `GET /plugins` → verify `loan_agreement` schema now includes `prepaymentPenalty`
2. Upload `sample-loan.pdf` → wait for COMPLETED
3. `GET /documents/{id}` → record `extractedData` as `v1_data`
4. Assert `prepaymentPenalty` key exists in `v1_data` (value may be null if not in doc)
5. `POST /documents/{id}/reprocess` → wait for COMPLETED
6. `GET /documents/{id}` → record `extractedData` as `v2_data`
7. Assert `v2_data` has `prepaymentPenalty` key
8. Compare `v1_data` keys vs `v2_data` keys → log diff

**Teardown**: `git checkout` to revert plugin patches, redeploy.

**Markers**: `@pytest.mark.integration`, `@pytest.mark.slow`

## 4. Integration Tests — PageIndex Summary

### 4a. `test_pageindex_summary.py` — Summary Aligns with Extraction

**Proves**: The Q&A and summary system returns answers grounded in the same values that the extraction pipeline produced — no hallucination or contradiction.

**Setup**: Upload `sample-loan.pdf` → wait for COMPLETED. Fetch `GET /documents/{id}` to capture `extractedData` as ground truth.

**Test Steps**:
1. `POST /documents/{id}/ask` with `{"question": "What is the interest rate?"}`
   → Assert answer contains the interest rate value from `extractedData`
2. `POST /documents/{id}/ask` with `{"question": "Who is the borrower?"}`
   → Assert answer contains borrower name from `extractedData`
3. `POST /documents/{id}/ask` with `{"question": "What is the loan amount?"}`
   → Assert answer contains loan amount from `extractedData`
4. `POST /documents/{id}/section-summary` with `{"sectionId": "loan_terms"}`
   → Assert summary text mentions at least 2 key values from `extractedData`
5. Repeat Q&A call from step 1 → assert response time < 2s (cached)
6. Ask an off-topic question `"What is the weather today?"`
   → Assert response indicates the question is not relevant to the document

**Assertions**:
- Q&A answers must contain extracted values (fuzzy match: normalize currency, percentages)
- Summary must reference key terms from extracted data
- No hallucinated values that contradict `extractedData`
- Caching works (second call significantly faster)

**Markers**: `@pytest.mark.integration`

## 5. Integration Tests — Compliance Scenarios

### 5a. `test_compliance_baseline_crud.py` — Full Lifecycle

**Proves**: Baseline CRUD operations work correctly through draft → published → archived states.

**Test Steps**:
1. `POST /baselines` with name + description → assert `status == "draft"`, get `baseline_id`
2. `POST /baselines/{id}/requirements` → add 3 requirements with varying criticality
3. `GET /baselines/{id}` → assert requirements array has 3 items
4. `PUT /baselines/{id}/requirements/{reqId}` → update one criticality to `nice-to-have`
5. `DELETE /baselines/{id}/requirements/{lastReqId}` → remove one requirement
6. `GET /baselines/{id}` → assert 2 requirements remain
7. `POST /baselines/{id}/publish` → assert `status == "published"`
8. `POST /baselines/{id}/publish` again → assert 409 Conflict (already published)
9. `PUT /baselines/{id}` with `{status: "archived"}` → assert archived
10. `GET /baselines?status=published` → assert this baseline NOT in list

**Markers**: `@pytest.mark.integration`, `@pytest.mark.compliance`

---

### 5b. `test_compliance_evaluation.py` — Evaluation Pipeline

**Proves**: Documents get evaluated against baselines during the upload pipeline, producing verdicts with evidence.

**Setup**: Create + publish baseline with 3 known requirements via `create_published_baseline` fixture.

**Test Steps**:
1. `POST /upload` with `baselineIds=[baseline_id]`
2. Upload `sample-loan.pdf` → wait for COMPLETED
3. `GET /documents/{id}/compliance` → assert at least 1 report exists
4. Assert report `baselineId` matches the one we specified
5. Assert report has `results` array with exactly 3 items (one per requirement)
6. For each result, assert presence of: `verdict` (PASS|FAIL|PARTIAL|NOT_FOUND), `confidence` (0.0-1.0), `evidence` (non-empty string), `evidenceCharStart` (integer), `evidenceCharEnd` (integer)
7. Assert `overallScore` is a number between 0 and 100
8. Validate evidence offsets: for at least 1 result, fetch document text and extract substring at `[evidenceCharStart:evidenceCharEnd]` → assert it contains keywords related to the requirement

**Markers**: `@pytest.mark.integration`, `@pytest.mark.compliance`

---

### 5c. `test_compliance_learning_loop.py` — Few-Shot Feedback Proof

**Proves**: Reviewer overrides are stored as feedback, injected into evaluation prompts, and measurably affect future evaluation scores.

**Setup**: Create + publish baseline. Upload doc → wait → get compliance report (RUN 1).

**Test Steps — Phase 1 (Baseline Scores)**:
1. Record all requirement verdicts + confidences from RUN 1 as `run1_results`
2. Identify a requirement that got `FAIL` or low confidence (< 0.7)

**Test Steps — Phase 2 (Submit Override)**:
3. `POST /documents/{id}/compliance/{reportId}/review` with `{requirementId, overrideVerdict: "PASS", justification: "Section 4.2 on page 3 clearly states the APR is 4.5%"}`
4. Verify response 200 OK
5. Read `compliance-feedback` DynamoDB table directly → assert feedback record exists with `originalVerdict`, `overrideVerdict`, `justification`

**Test Steps — Phase 3 (Verify Prompt Injection)**:
6. Invoke `compliance-evaluate` Lambda directly with a test event that includes the same requirement + document text
7. Capture the prompt sent to Bedrock (via CloudWatch log or Lambda response metadata)
8. Assert the prompt contains the few-shot example: the justification text from step 3

**Test Steps — Phase 4 (Re-evaluate)**:
9. Upload the same document again with the same baselineId (or trigger reprocess)
10. Wait for COMPLETED → `GET /documents/{newId}/compliance` (RUN 2)
11. Record all requirement verdicts + confidences as `run2_results`

**Test Steps — Phase 5 (Compare)**:
12. For the overridden requirement: assert `run2_results[req].verdict` changed OR `run2_results[req].confidence` increased by > 0.1
13. Generate comparison JSON:
    ```json
    {
      "requirement": "APR must be disclosed",
      "run1": {"verdict": "FAIL", "confidence": 0.3},
      "run2": {"verdict": "PASS", "confidence": 0.85},
      "delta_confidence": 0.55,
      "feedback_injected": true
    }
    ```
14. Save to `reports/learning-loop-comparison.json`

**Markers**: `@pytest.mark.integration`, `@pytest.mark.compliance`, `@pytest.mark.slow`

---

### 5d. `test_compliance_multi_baseline.py` — Independent Baseline Evaluation

**Proves**: A single document can be evaluated against multiple baselines independently, with no cross-contamination.

**Setup**: Create + publish `baseline_a` (3 requirements) and `baseline_b` (5 different requirements).

**Test Steps**:
1. Upload doc with `baselineIds=[baseline_a_id, baseline_b_id]` → wait for COMPLETED
2. `GET /documents/{id}/compliance` → assert 2 separate reports
3. Report A: assert `baselineId == baseline_a_id`, 3 results
4. Report B: assert `baselineId == baseline_b_id`, 5 results
5. Assert `overallScore` differs between reports (different requirements = different scores)
6. Assert no requirement from baseline_a appears in report B's results and vice versa

**Markers**: `@pytest.mark.integration`, `@pytest.mark.compliance`

## 6. Playwright E2E Tests

### Page Object Models

Each page has a reusable class in `tests/e2e/pages/`:

| Page Object | Key Methods |
|-------------|------------|
| `UploadPage` | `upload_file(path)`, `select_baselines(ids)`, `submit()`, `wait_for_redirect()` |
| `DocumentsPage` | `get_document_rows()`, `click_document(id)`, `search(query)` |
| `DocumentDetailPage` | `wait_for_processing(timeout)`, `click_tab(name)`, `get_extracted_data()`, `get_pdf_page()` |
| `WorkQueuePage` | `get_queue_rows()`, `get_compliance_column()`, `filter_by_status(status)` |
| `BaselinesPage` | `create_baseline(name, desc)`, `filter_by_status(status)`, `get_baseline_rows()`, `click_baseline(id)` |
| `BaselineEditorPage` | `add_requirement(text, category, criticality)`, `publish()`, `get_requirements()`, `get_status_badge()` |

### E2E Test Scenarios

**`test_upload_and_view.py`** — Upload → Process → View Results:
1. Navigate to Upload page → upload `test_invoice.pdf` → submit
2. Wait for redirect to document detail → wait for processing COMPLETED
3. Click "Extracted Data" tab → assert vendor, amount, date fields rendered
4. Click "PDF" view → assert PDF viewer loads (page count > 0)
5. Screenshot: `reports/screenshots/upload-and-view.png`

**`test_plugin_rendering.py`** — New Plugin Renders in UI:
1. Upload `test_invoice.pdf` (after plugin deployed) → wait COMPLETED
2. Navigate to document detail → click "Extracted Data" tab
3. Assert GenericDataFields renders invoice-specific fields (vendor, lineItems)
4. Assert no "Unknown document type" error
5. Screenshot: `reports/screenshots/plugin-rendering.png`

**`test_compliance_baseline_management.py`** — Baseline CRUD via UI:
1. Navigate to Baselines page → screenshot empty/list state
2. Click "Create Baseline" → fill name + description → submit
3. Click into new baseline → add 3 requirements with form
4. Click "Publish" → assert status badge changes to "Published"
5. Screenshots: `draft-baseline.png`, `adding-requirements.png`, `published-baseline.png`

**`test_compliance_evaluation_ui.py`** — ComplianceTab Rendering:
1. Upload doc with baseline selected → wait COMPLETED
2. Navigate to document detail → click "Compliance" tab
3. Assert score gauge SVG renders with a numeric value
4. Assert verdict badges visible (colored PASS/FAIL/PARTIAL)
5. Assert each requirement row shows evidence text
6. Screenshots: `compliance-tab-overview.png`, `score-gauge.png`

**`test_compliance_reviewer_override.py`** — Override Flow:
1. Navigate to a document with compliance results
2. Find a FAIL verdict → screenshot `before-override.png`
3. Click the requirement → fill override form (verdict=PASS, justification)
4. Submit → assert badge changes from FAIL (red) to PASS (green)
5. Screenshot: `after-override.png`

**`test_compliance_learning_proof.py`** — Visual Before/After:
1. Upload doc with baseline → wait → navigate to ComplianceTab
2. Screenshot all verdict badges as `run1-scores.png`
3. Submit override on a FAIL requirement
4. Trigger re-evaluation (reprocess or re-upload)
5. Wait → navigate to new document's ComplianceTab
6. Screenshot all verdict badges as `run2-scores.png`
7. Assert at least one badge changed color between screenshots

**`test_compliance_work_queue.py`** — Work Queue Badges:
1. Navigate to Work Queue page
2. Assert "Compliance" column header exists
3. Assert at least one row shows a compliance score badge
4. Assert badge colors correspond to score ranges (green > 80, yellow 50-80, red < 50)
5. Screenshot: `work-queue-compliance.png`

**`test_compliance_evidence_navigation.py`** — Evidence Page Jump:
1. Navigate to document detail → Compliance tab
2. Click evidence link on a requirement
3. Assert PDF viewer navigates to the referenced page
4. Assert page number changed from initial view
5. Screenshot: `evidence-page-jump.png`

## 7. Orchestrator & Reporting

### `scripts/test-toolkit.sh`

Single-command orchestrator that runs the full test suite.

**Usage**:
```bash
./scripts/test-toolkit.sh                    # Run all tests
./scripts/test-toolkit.sh --integration      # Integration tests only
./scripts/test-toolkit.sh --e2e              # Playwright E2E only
./scripts/test-toolkit.sh -k compliance      # Only compliance-related tests
./scripts/test-toolkit.sh -k plugin          # Only plugin-related tests
./scripts/test-toolkit.sh --headed           # Run Playwright with visible browser
```

**Workflow**:
1. Source `common.sh` for AWS env validation
2. Verify deployed stack exists (`aws cloudformation describe-stacks`)
3. Create `reports/` directory
4. Run integration tests: `uv run pytest tests/integration/ -m integration --html=reports/integration.html -v`
5. Run E2E tests: `uv run pytest tests/e2e/ -m e2e --html=reports/e2e.html -v`
6. Print summary table: passed/failed/skipped per marker
7. Open `reports/toolkit-report.html` if on macOS

**Report Output**:
```
reports/
  integration.html                  # Pytest HTML report for integration tests
  e2e.html                          # Pytest HTML report for E2E tests
  screenshots/                      # Playwright screenshots (evidence)
    upload-and-view.png
    plugin-rendering.png
    compliance-tab-overview.png
    score-gauge.png
    before-override.png
    after-override.png
    run1-scores.png
    run2-scores.png
    work-queue-compliance.png
    evidence-page-jump.png
  learning-loop-comparison.json     # Before/after score diff
```

## 8. Dependencies & Setup

### New Python Dependencies

Add to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
test-toolkit = [
    "pytest-playwright>=0.5.0",
    "pytest-html>=4.0.0",
    "requests>=2.31.0",
]
```

Install: `uv pip install -e ".[test-toolkit]"`

### Playwright Setup

```bash
uv run playwright install chromium    # Install browser binary
```

### Pytest Configuration

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: Real-AWS integration tests",
    "e2e: Playwright browser E2E tests",
    "slow: Tests requiring CDK deploy cycle",
    "compliance: Compliance engine tests",
]
```

### Prerequisites

- Deployed stack (`./scripts/deploy-backend.sh` + `./scripts/deploy-frontend.sh`)
- AWS credentials configured
- For plugin tests: ability to deploy (CDK + Docker for Lambda layers)
- For E2E tests: Chromium installed via Playwright
- For compliance tests: Bedrock model access enabled in the region

### Environment Variables (Optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `STACK_NAME` | `FinancialDocProcessingStack` | CloudFormation stack name |
| `TEST_TIMEOUT` | `300` | Max seconds to wait for document processing |
| `PLAYWRIGHT_HEADLESS` | `true` | Set `false` for visible browser during debug |
| `SCREENSHOT_DIR` | `reports/screenshots` | Where Playwright saves screenshots |
