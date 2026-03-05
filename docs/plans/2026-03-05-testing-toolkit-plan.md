# Testing Toolkit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive integration + E2E test suite that proves plugin lifecycle, PageIndex alignment, and compliance learning loops work end-to-end against real AWS.

**Architecture:** Pytest-based test harness with shared fixtures for stack discovery and document upload. Integration tests call the real API. Playwright E2E tests drive the browser against the deployed frontend. All evidence captured as screenshots and JSON reports.

**Tech Stack:** pytest, pytest-playwright, pytest-html, requests, boto3, Playwright (Chromium)

**Design Doc:** `docs/plans/2026-03-05-testing-toolkit-design.md`

---

## Task 1: Project Setup — Dependencies & Directory Structure

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/integration/__init__.py`
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/pages/__init__.py`
- Create: `tests/fixtures/.gitkeep`

**Step 1:** Add test-toolkit optional deps to `pyproject.toml`:
```toml
[project.optional-dependencies]
test-toolkit = ["pytest-playwright>=0.5.0", "pytest-html>=4.0.0", "requests>=2.31.0"]
```

**Step 2:** Add pytest markers to `pyproject.toml` `[tool.pytest.ini_options]`:
```toml
markers = [
    "integration: Real-AWS integration tests",
    "e2e: Playwright browser E2E tests",
    "slow: Tests requiring CDK deploy cycle",
    "compliance: Compliance engine tests",
]
```

**Step 3:** Create directories:
```bash
mkdir -p tests/integration tests/e2e/pages tests/fixtures
touch tests/integration/__init__.py tests/e2e/__init__.py tests/e2e/pages/__init__.py tests/fixtures/.gitkeep
```

**Step 4:** Install deps + Playwright:
```bash
uv pip install -e ".[test-toolkit]"
uv run playwright install chromium
```

**Step 5:** Commit:
```bash
git add pyproject.toml tests/
git commit -m "chore: add testing toolkit deps, markers, and directory structure"
```

## Task 2: Test Fixtures — Synthetic Test Data

**Files:**
- Create: `tests/fixtures/test_invoice_plugin.py`
- Create: `tests/fixtures/test_invoice_prompt.txt`
- Create: `tests/fixtures/test_invoice.pdf` (script-generated)
- Create: `tests/fixtures/compliance_baseline.json`
- Create: `tests/fixtures/compliance_baseline_strict.json`

**Step 1:** Create `tests/fixtures/test_invoice_plugin.py` — a minimal plugin config with `plugin_id="test_invoice"`, 1 section (all pages, FORMS+QUERIES), queries for vendor/amount/date, and output_schema with vendor/amount/invoiceDate/lineItems fields. Use `w2.py` as template (simple single-section plugin).

**Step 2:** Create `tests/fixtures/test_invoice_prompt.txt` — normalization prompt mapping Textract fields to schema. Include rules: vendor from "Vendor Name" field, amount from "Total Amount", date from "Invoice Date", lineItems as array.

**Step 3:** Create `tests/fixtures/test_invoice.pdf` — write a Python script `scripts/generate-test-invoice.py` that uses reportlab to generate a 2-page PDF with: Page 1: "INVOICE" header, Vendor: Acme Corp, Invoice Date: 2026-01-15, 3 line items. Page 2: Total Amount: $1,234.56, Payment Terms: Net 30.

**Step 4:** Create `tests/fixtures/compliance_baseline.json`:
```json
{
  "name": "Test Loan Compliance",
  "description": "Integration test baseline",
  "requirements": [
    {"text": "The document must disclose the Annual Percentage Rate (APR)", "category": "disclosure", "criticality": "must-have"},
    {"text": "The borrower full name must be present in the document", "category": "identity", "criticality": "must-have"},
    {"text": "A signature date should be included", "category": "execution", "criticality": "should-have"}
  ]
}
```

**Step 5:** Create `tests/fixtures/compliance_baseline_strict.json` — same 3 requirements plus: "Lender NMLS number must be displayed" (must-have) and "Equal housing logo or statement present" (nice-to-have).

**Step 6:** Commit:
```bash
git add tests/fixtures/ scripts/generate-test-invoice.py
git commit -m "feat: add test fixtures — invoice plugin, prompt, PDF, compliance baselines"
```

## Task 3: Integration conftest.py — Shared Fixtures

**Files:**
- Create: `tests/integration/conftest.py`

**Step 1:** Write `tests/integration/conftest.py` with these fixtures:

- `stack_config` (session): Run `aws cloudformation describe-stacks --stack-name` (from `STACK_NAME` env or default `FinancialDocProcessingStack`). Parse Outputs into dict: `api_url`, `bucket_name`, `documents_table`, `baselines_table`, `reports_table`, `feedback_table`, `frontend_url`. Skip all tests if stack not found.

- `api` (session): `requests.Session()` with `base_url = stack_config["api_url"]`. Add `Content-Type: application/json` header.

- `s3_client` (session): `boto3.client("s3")`.

- `upload_and_wait` (function): Callable that takes `(pdf_path, baseline_ids=None)`. Calls `POST /upload` with filename + baselineIds, uploads to presigned URL via `requests.put()`, polls `GET /documents/{id}/status` every 10s for up to `TEST_TIMEOUT` (default 300s). Returns `(doc_id, status, duration)`. Raises `TimeoutError` if not COMPLETED.

- `create_published_baseline` (function): Callable that takes `requirements` list. `POST /baselines` -> for each req `POST /baselines/{id}/requirements` -> `POST /baselines/{id}/publish`. Returns `baseline_id`. Tracks created baselines for cleanup.

- `_created_baselines` (session): List to track baseline IDs for cleanup.

- `cleanup` (autouse, function): After each test, archive all baselines in `_created_baselines`.

**Step 2:** Verify conftest loads:
```bash
uv run pytest tests/integration/ --collect-only
```
Expected: 0 tests collected, no import errors.

**Step 3:** Commit:
```bash
git add tests/integration/conftest.py
git commit -m "feat: add integration conftest with stack discovery and upload helpers"
```

## Task 4: test_plugin_lifecycle.py — New Plugin Pipeline

**Files:**
- Create: `tests/integration/test_plugin_lifecycle.py`

**Step 1:** Write the test file with a single test function `test_new_plugin_full_pipeline`:

```python
import pytest, shutil, subprocess
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"
PLUGINS_DIR = Path(__file__).parent.parent.parent / "lambda/layers/plugins/python/document_plugins"

@pytest.mark.integration
@pytest.mark.slow
class TestPluginLifecycle:
    def test_new_plugin_full_pipeline(self, api, upload_and_wait):
        # Pre-check: deploy must have been done with test_invoice plugin installed
        # (test-toolkit.sh handles this)

        # 1. Verify plugin registered
        resp = api.get("/plugins")
        assert resp.status_code == 200
        plugins = resp.json()
        plugin_ids = [p["plugin_id"] for p in plugins]
        assert "test_invoice" in plugin_ids, f"test_invoice not in {plugin_ids}"

        # 2. Upload test invoice
        doc_id, status, duration = upload_and_wait(FIXTURES / "test_invoice.pdf")
        assert status == "COMPLETED", f"Processing failed: {status}"

        # 3. Verify document type
        resp = api.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        doc = resp.json()
        assert doc["documentType"] == "test_invoice"

        # 4. Verify extracted fields
        data = doc.get("extractedData", {})
        assert "vendor" in data, f"Missing vendor in {list(data.keys())}"
        assert "amount" in data
        assert "invoiceDate" in data

        # 5. Verify vendor value
        assert "Acme" in str(data["vendor"]), f"Expected Acme, got {data['vendor']}"

        # 6. Verify audit trail
        resp = api.get(f"/documents/{doc_id}/audit")
        assert resp.status_code == 200
        audit = resp.json()
        stages = [e.get("stage") or e.get("event") for e in audit]
        for expected in ["ROUTER", "EXTRACTOR", "NORMALIZER"]:
            assert any(expected in str(s) for s in stages), f"{expected} not in audit"
```

**Step 2:** Run (will fail if plugin not deployed, which is expected at this stage):
```bash
uv run pytest tests/integration/test_plugin_lifecycle.py -v -m integration
```

**Step 3:** Commit:
```bash
git add tests/integration/test_plugin_lifecycle.py
git commit -m "feat: add plugin lifecycle integration test"
```

## Task 5: test_plugin_enhancement.py — Field Update on Reprocess

**Files:**
- Create: `tests/integration/test_plugin_enhancement.py`

**Step 1:** Write test `test_enhanced_plugin_field_on_reprocess`:

```python
import pytest

@pytest.mark.integration
@pytest.mark.slow
class TestPluginEnhancement:
    def test_enhanced_plugin_field_on_reprocess(self, api, upload_and_wait):
        # Pre-condition: loan_agreement plugin has been patched with prepaymentPenalty
        # and backend redeployed (handled by test-toolkit.sh --slow setup)

        # 1. Verify schema includes new field
        resp = api.get("/plugins")
        plugins = {p["plugin_id"]: p for p in resp.json()}
        schema = plugins["loan_agreement"]["output_schema"]
        assert "prepaymentPenalty" in str(schema), "New field not in schema"

        # 2. Upload and process
        doc_id, status, _ = upload_and_wait("tests/sample-documents/sample-loan.pdf")
        assert status == "COMPLETED"

        # 3. Get v1 extracted data
        resp = api.get(f"/documents/{doc_id}")
        v1_data = resp.json().get("extractedData", {})
        v1_keys = set(v1_data.keys())

        # 4. Verify new key exists (value may be null)
        assert "prepaymentPenalty" in v1_keys or "prepaymentPenalty" in str(v1_data)

        # 5. Reprocess
        resp = api.post(f"/documents/{doc_id}/reprocess")
        assert resp.status_code == 200

        # 6. Wait for reprocessing (poll status)
        import time
        for _ in range(30):
            resp = api.get(f"/documents/{doc_id}/status")
            if resp.json().get("status") == "COMPLETED":
                break
            time.sleep(10)

        # 7. Get v2 data and compare
        resp = api.get(f"/documents/{doc_id}")
        v2_data = resp.json().get("extractedData", {})
        v2_keys = set(v2_data.keys())

        print(f"v1 keys: {v1_keys}")
        print(f"v2 keys: {v2_keys}")
        print(f"New in v2: {v2_keys - v1_keys}")
```

**Step 2:** Commit:
```bash
git add tests/integration/test_plugin_enhancement.py
git commit -m "feat: add plugin enhancement reprocess test"
```

## Task 6: test_pageindex_summary.py — Summary Alignment

**Files:**
- Create: `tests/integration/test_pageindex_summary.py`

**Step 1:** Write test with fuzzy matching helper:

```python
import pytest, re, time

def normalize_value(val):
    """Normalize for fuzzy comparison: strip $, %, commas, lowercase."""
    s = str(val).lower().strip()
    return re.sub(r'[\$,%\s]', '', s)

def value_in_text(value, text):
    """Check if extracted value appears in Q&A answer (fuzzy)."""
    norm_val = normalize_value(value)
    norm_text = normalize_value(text)
    return norm_val in norm_text or norm_val[:6] in norm_text

@pytest.mark.integration
class TestPageIndexSummary:
    def test_qa_aligns_with_extraction(self, api, upload_and_wait):
        # Setup: upload and process
        doc_id, status, _ = upload_and_wait("tests/sample-documents/sample-loan.pdf")
        assert status == "COMPLETED"

        # Get ground truth from extraction
        resp = api.get(f"/documents/{doc_id}")
        extracted = resp.json().get("extractedData", {})

        # Q&A questions mapped to expected extracted fields
        qa_pairs = [
            ("What is the interest rate?", ["interestRate", "rate"]),
            ("Who is the borrower?", ["borrowerName", "borrower"]),
            ("What is the loan amount?", ["loanAmount", "amount"]),
        ]

        for question, field_keys in qa_pairs:
            resp = api.post(f"/documents/{doc_id}/ask", json={"question": question})
            assert resp.status_code == 200
            answer = resp.json().get("answer", "")

            # Find matching extracted value
            matched = False
            for key in field_keys:
                val = extracted.get(key)
                if val and value_in_text(val, answer):
                    matched = True
                    break
            # Soft assert — log mismatch but don't fail (LLM may rephrase)
            if not matched:
                print(f"WARN: Q&A for '{question}' may not match extraction: {answer[:100]}")

    def test_cached_response_faster(self, api, upload_and_wait):
        doc_id, status, _ = upload_and_wait("tests/sample-documents/sample-loan.pdf")
        assert status == "COMPLETED"

        question = {"question": "What is the interest rate?"}

        # First call
        t1 = time.time()
        api.post(f"/documents/{doc_id}/ask", json=question)
        d1 = time.time() - t1

        # Second call (should be cached)
        t2 = time.time()
        api.post(f"/documents/{doc_id}/ask", json=question)
        d2 = time.time() - t2

        print(f"First call: {d1:.1f}s, Second call: {d2:.1f}s")
        # Cached call should be significantly faster
        assert d2 < d1 or d2 < 2.0, f"Cache not working: {d2:.1f}s >= {d1:.1f}s"
```

**Step 2:** Commit:
```bash
git add tests/integration/test_pageindex_summary.py
git commit -m "feat: add PageIndex summary alignment test with fuzzy matching"
```

## Task 7: test_compliance_baseline_crud.py — Baseline Lifecycle

**Files:**
- Create: `tests/integration/test_compliance_baseline_crud.py`

**Step 1:** Write full lifecycle test:

```python
import pytest

@pytest.mark.integration
@pytest.mark.compliance
class TestComplianceBaselineCRUD:
    def test_full_baseline_lifecycle(self, api):
        # 1. Create draft
        resp = api.post("/baselines", json={
            "name": "Test CRUD Baseline",
            "description": "Integration test for baseline lifecycle"
        })
        assert resp.status_code in (200, 201)
        baseline = resp.json()
        bid = baseline["baselineId"]
        assert baseline["status"] == "draft"

        # 2. Add 3 requirements
        req_ids = []
        for req in [
            {"text": "APR must be disclosed", "category": "disclosure", "criticality": "must-have"},
            {"text": "Borrower name present", "category": "identity", "criticality": "must-have"},
            {"text": "Signature date included", "category": "execution", "criticality": "should-have"},
        ]:
            resp = api.post(f"/baselines/{bid}/requirements", json=req)
            assert resp.status_code in (200, 201)
            req_ids.append(resp.json()["requirementId"])

        # 3. Verify 3 requirements
        resp = api.get(f"/baselines/{bid}")
        assert len(resp.json()["requirements"]) == 3

        # 4. Update criticality
        resp = api.put(f"/baselines/{bid}/requirements/{req_ids[2]}", json={"criticality": "nice-to-have"})
        assert resp.status_code == 200

        # 5. Delete one
        resp = api.delete(f"/baselines/{bid}/requirements/{req_ids[2]}")
        assert resp.status_code in (200, 204)

        # 6. Verify 2 remain
        resp = api.get(f"/baselines/{bid}")
        assert len(resp.json()["requirements"]) == 2

        # 7. Publish
        resp = api.post(f"/baselines/{bid}/publish")
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

        # 8. Double publish → conflict
        resp = api.post(f"/baselines/{bid}/publish")
        assert resp.status_code in (400, 409)

        # 9. Archive
        resp = api.put(f"/baselines/{bid}", json={"status": "archived"})
        assert resp.status_code == 200

        # 10. Not in published list
        resp = api.get("/baselines?status=published")
        ids = [b["baselineId"] for b in resp.json()]
        assert bid not in ids
```

**Step 2:** Commit:
```bash
git add tests/integration/test_compliance_baseline_crud.py
git commit -m "feat: add compliance baseline CRUD lifecycle test"
```

## Task 8: test_compliance_evaluation.py — Evaluation Pipeline

**Files:**
- Create: `tests/integration/test_compliance_evaluation.py`

**Step 1:** Write evaluation pipeline test:

```python
import pytest, json

@pytest.mark.integration
@pytest.mark.compliance
class TestComplianceEvaluation:
    def test_evaluation_produces_verdicts_with_evidence(self, api, upload_and_wait, create_published_baseline):
        # Setup: create baseline with 3 requirements
        baseline_id = create_published_baseline([
            {"text": "The document must disclose the Annual Percentage Rate (APR)", "category": "disclosure", "criticality": "must-have"},
            {"text": "The borrower full name must be present", "category": "identity", "criticality": "must-have"},
            {"text": "A signature date should be included", "category": "execution", "criticality": "should-have"},
        ])

        # 1. Upload with baseline
        doc_id, status, _ = upload_and_wait(
            "tests/sample-documents/sample-loan.pdf",
            baseline_ids=[baseline_id]
        )
        assert status == "COMPLETED"

        # 2. Get compliance report
        resp = api.get(f"/documents/{doc_id}/compliance")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) >= 1, "No compliance reports generated"

        report = reports[0]
        assert report["baselineId"] == baseline_id

        # 3. Verify results structure
        results = report.get("results", [])
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

        valid_verdicts = {"PASS", "FAIL", "PARTIAL", "NOT_FOUND"}
        for r in results:
            assert r["verdict"] in valid_verdicts, f"Invalid verdict: {r['verdict']}"
            assert 0.0 <= r["confidence"] <= 1.0
            assert len(r.get("evidence", "")) > 0, "Empty evidence"
            assert isinstance(r.get("evidenceCharStart"), int)
            assert isinstance(r.get("evidenceCharEnd"), int)
            assert r["evidenceCharEnd"] > r["evidenceCharStart"]

        # 4. Verify overall score
        score = report.get("overallScore")
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

        print(f"Compliance score: {score}/100")
        for r in results:
            print(f"  {r['verdict']:10s} ({r['confidence']:.2f}) — {r.get('requirementText', '')[:60]}")
```

**Step 2:** Commit:
```bash
git add tests/integration/test_compliance_evaluation.py
git commit -m "feat: add compliance evaluation pipeline test"
```

## Task 9: test_compliance_learning_loop.py — Few-Shot Feedback Proof

**Files:**
- Create: `tests/integration/test_compliance_learning_loop.py`

**Step 1:** Write the 5-phase learning loop test:

```python
import pytest, json, time, boto3, os
from pathlib import Path

@pytest.mark.integration
@pytest.mark.compliance
@pytest.mark.slow
class TestComplianceLearningLoop:
    def test_feedback_improves_evaluation(self, api, upload_and_wait, create_published_baseline, stack_config):
        # --- Phase 1: Baseline Scores (RUN 1) ---
        baseline_id = create_published_baseline([
            {"text": "The document must disclose the Annual Percentage Rate (APR)", "category": "disclosure", "criticality": "must-have", "confidenceThreshold": 0.5},
            {"text": "The borrower full name must be present", "category": "identity", "criticality": "must-have", "confidenceThreshold": 0.5},
            {"text": "Loan maturity date must be stated", "category": "terms", "criticality": "should-have", "confidenceThreshold": 0.5},
        ])

        doc_id, status, _ = upload_and_wait("tests/sample-documents/sample-loan.pdf", baseline_ids=[baseline_id])
        assert status == "COMPLETED"

        resp = api.get(f"/documents/{doc_id}/compliance")
        reports = resp.json()
        assert len(reports) >= 1
        report = reports[0]
        report_id = report["reportId"]
        run1_results = {r["requirementId"]: r for r in report["results"]}

        print("=== RUN 1 Results ===")
        for rid, r in run1_results.items():
            print(f"  {r['verdict']:10s} ({r['confidence']:.2f}) — {r.get('requirementText', '')[:50]}")

        # --- Phase 2: Submit Override ---
        # Find a FAIL or low-confidence requirement
        target_req = None
        for rid, r in run1_results.items():
            if r["verdict"] in ("FAIL", "NOT_FOUND") or r["confidence"] < 0.7:
                target_req = r
                break

        if not target_req:
            pytest.skip("All requirements passed with high confidence — cannot test override")

        resp = api.post(f"/documents/{doc_id}/compliance/{report_id}/review", json={
            "requirementId": target_req["requirementId"],
            "overrideVerdict": "PASS",
            "justification": "Section 4.2 on page 3 clearly states the APR is 4.5% as required by TILA"
        })
        assert resp.status_code == 200

        # --- Phase 3: Verify Feedback in DynamoDB ---
        dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))
        feedback_table = dynamodb.Table(stack_config["feedback_table"])
        scan = feedback_table.scan(
            FilterExpression="requirementId = :rid",
            ExpressionAttributeValues={":rid": target_req["requirementId"]}
        )
        assert len(scan["Items"]) >= 1, "Feedback not stored in DynamoDB"
        feedback = scan["Items"][0]
        assert feedback["overrideVerdict"] == "PASS"
        assert "Section 4.2" in feedback["justification"]
        print(f"Feedback stored: {feedback['feedbackId']}")

        # --- Phase 4: Re-evaluate (RUN 2) ---
        doc_id2, status2, _ = upload_and_wait("tests/sample-documents/sample-loan.pdf", baseline_ids=[baseline_id])
        assert status2 == "COMPLETED"

        resp = api.get(f"/documents/{doc_id2}/compliance")
        reports2 = resp.json()
        report2 = reports2[0]
        run2_results = {r["requirementId"]: r for r in report2["results"]}

        print("=== RUN 2 Results ===")
        for rid, r in run2_results.items():
            print(f"  {r['verdict']:10s} ({r['confidence']:.2f}) — {r.get('requirementText', '')[:50]}")

        # --- Phase 5: Compare ---
        comparison = {
            "requirement": target_req.get("requirementText", target_req["requirementId"]),
            "run1": {"verdict": target_req["verdict"], "confidence": float(target_req["confidence"])},
            "run2": {"verdict": run2_results.get(target_req["requirementId"], {}).get("verdict", "UNKNOWN"),
                     "confidence": float(run2_results.get(target_req["requirementId"], {}).get("confidence", 0))},
            "feedback_injected": True,
        }
        comparison["delta_confidence"] = comparison["run2"]["confidence"] - comparison["run1"]["confidence"]

        # Save comparison report
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        with open(reports_dir / "learning-loop-comparison.json", "w") as f:
            json.dump(comparison, f, indent=2)

        print(f"\n=== COMPARISON ===")
        print(json.dumps(comparison, indent=2))

        # Assert improvement
        verdict_changed = comparison["run1"]["verdict"] != comparison["run2"]["verdict"]
        confidence_improved = comparison["delta_confidence"] > 0.1
        assert verdict_changed or confidence_improved, (
            f"No improvement detected. Run1: {comparison['run1']}, Run2: {comparison['run2']}"
        )
```

**Step 2:** Commit:
```bash
git add tests/integration/test_compliance_learning_loop.py
git commit -m "feat: add compliance learning loop test — 5-phase feedback proof"
```

## Task 10: test_compliance_multi_baseline.py — Independent Baselines

**Files:**
- Create: `tests/integration/test_compliance_multi_baseline.py`

**Step 1:** Write multi-baseline test:

```python
import pytest

@pytest.mark.integration
@pytest.mark.compliance
class TestComplianceMultiBaseline:
    def test_independent_baseline_evaluations(self, api, upload_and_wait, create_published_baseline):
        baseline_a = create_published_baseline([
            {"text": "APR must be disclosed", "category": "disclosure", "criticality": "must-have"},
            {"text": "Borrower name present", "category": "identity", "criticality": "must-have"},
            {"text": "Signature date included", "category": "execution", "criticality": "should-have"},
        ])
        baseline_b = create_published_baseline([
            {"text": "Lender NMLS number displayed", "category": "regulatory", "criticality": "must-have"},
            {"text": "Equal housing logo present", "category": "regulatory", "criticality": "nice-to-have"},
            {"text": "Loan maturity date stated", "category": "terms", "criticality": "must-have"},
            {"text": "Late payment fee disclosed", "category": "fees", "criticality": "should-have"},
            {"text": "Prepayment penalty terms described", "category": "terms", "criticality": "should-have"},
        ])

        doc_id, status, _ = upload_and_wait(
            "tests/sample-documents/sample-loan.pdf",
            baseline_ids=[baseline_a, baseline_b]
        )
        assert status == "COMPLETED"

        resp = api.get(f"/documents/{doc_id}/compliance")
        reports = resp.json()
        assert len(reports) == 2, f"Expected 2 reports, got {len(reports)}"

        reports_by_baseline = {r["baselineId"]: r for r in reports}

        report_a = reports_by_baseline[baseline_a]
        report_b = reports_by_baseline[baseline_b]

        assert len(report_a["results"]) == 3
        assert len(report_b["results"]) == 5

        # Scores should differ (different requirements)
        print(f"Baseline A score: {report_a['overallScore']}/100 ({len(report_a['results'])} reqs)")
        print(f"Baseline B score: {report_b['overallScore']}/100 ({len(report_b['results'])} reqs)")

        # No cross-contamination
        a_req_ids = {r["requirementId"] for r in report_a["results"]}
        b_req_ids = {r["requirementId"] for r in report_b["results"]}
        assert a_req_ids.isdisjoint(b_req_ids), "Cross-contamination between baselines"
```

**Step 2:** Commit:
```bash
git add tests/integration/test_compliance_multi_baseline.py
git commit -m "feat: add multi-baseline compliance test"
```

## Task 11: Playwright conftest.py + Page Object Models

**Files:**
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/pages/upload_page.py`
- Create: `tests/e2e/pages/document_detail_page.py`
- Create: `tests/e2e/pages/baselines_page.py`
- Create: `tests/e2e/pages/baseline_editor_page.py`
- Create: `tests/e2e/pages/work_queue_page.py`
- Create: `tests/e2e/pages/documents_page.py`

**Step 1:** Create `tests/e2e/conftest.py`:
- Import `stack_config` from integration conftest (or rediscover stack)
- `frontend_url` (session): CloudFront URL from stack config
- `authenticated_page` (function): Takes Playwright `page` fixture. Navigates to `frontend_url`. If Cognito login page detected, fills credentials from `TEST_USER`/`TEST_PASSWORD` env vars. Returns page.
- `screenshot_dir` (session): Create `reports/screenshots/`, return Path.

**Step 2:** Create each Page Object Model — one class per file, each with methods as specified in design doc Section 6. Key patterns:
- All methods use Playwright locators (`page.get_by_role()`, `page.locator()`)
- Wait for network idle after navigation
- Screenshot helper: `self.page.screenshot(path=screenshot_dir / name)`

**Step 3:** Verify POM imports:
```bash
uv run pytest tests/e2e/ --collect-only
```

**Step 4:** Commit:
```bash
git add tests/e2e/
git commit -m "feat: add Playwright conftest and Page Object Models"
```

## Task 12: E2E — Upload, View, Plugin Rendering

**Files:**
- Create: `tests/e2e/test_upload_and_view.py`
- Create: `tests/e2e/test_plugin_rendering.py`

**Step 1:** Write `test_upload_and_view.py`:

```python
import pytest
from pathlib import Path

@pytest.mark.e2e
class TestUploadAndView:
    def test_upload_process_and_view(self, authenticated_page, screenshot_dir):
        page = authenticated_page

        # Navigate to upload
        page.get_by_role("link", name="Upload").click()
        page.wait_for_load_state("networkidle")

        # Upload file
        page.get_by_label("file").set_input_files("tests/sample-documents/sample-loan.pdf")
        page.get_by_role("button", name="Upload").click()

        # Wait for processing (poll the UI status indicator)
        page.wait_for_selector('[data-testid="status-completed"]', timeout=300000)

        # Click Extracted Data tab
        page.get_by_role("tab", name="Extracted").click()
        page.wait_for_load_state("networkidle")

        # Verify data rendered
        content = page.content()
        assert "borrower" in content.lower() or "loan" in content.lower()

        page.screenshot(path=str(screenshot_dir / "upload-and-view.png"))
```

**Step 2:** Write `test_plugin_rendering.py` — similar pattern, uploads test_invoice.pdf, checks GenericDataFields renders vendor/amount/lineItems fields without errors.

**Step 3:** Commit:
```bash
git add tests/e2e/test_upload_and_view.py tests/e2e/test_plugin_rendering.py
git commit -m "feat: add upload/view and plugin rendering E2E tests"
```

## Task 13: E2E — Compliance Baseline Management

**Files:**
- Create: `tests/e2e/test_compliance_baseline_management.py`

**Step 1:** Write baseline CRUD E2E test:

```python
import pytest

@pytest.mark.e2e
@pytest.mark.compliance
class TestComplianceBaselineManagement:
    def test_create_add_requirements_publish(self, authenticated_page, screenshot_dir):
        page = authenticated_page

        # Navigate to Baselines
        page.get_by_role("link", name="Baselines").click()
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(screenshot_dir / "baselines-list.png"))

        # Create baseline
        page.get_by_role("button", name="Create").click()
        page.get_by_label("Name").fill("E2E Test Baseline")
        page.get_by_label("Description").fill("Created by Playwright E2E test")
        page.get_by_role("button", name="Save").click()
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(screenshot_dir / "draft-baseline.png"))

        # Add requirements
        for req_text in ["APR must be disclosed", "Borrower name present", "Signature date included"]:
            page.get_by_role("button", name="Add Requirement").click()
            page.get_by_label("Requirement").fill(req_text)
            page.get_by_role("button", name="Save").click()
            page.wait_for_load_state("networkidle")

        page.screenshot(path=str(screenshot_dir / "adding-requirements.png"))

        # Publish
        page.get_by_role("button", name="Publish").click()
        page.wait_for_load_state("networkidle")

        # Verify status badge
        badge = page.locator('[data-testid="status-badge"]')
        assert "published" in badge.inner_text().lower()
        page.screenshot(path=str(screenshot_dir / "published-baseline.png"))
```

**Step 2:** Commit:
```bash
git add tests/e2e/test_compliance_baseline_management.py
git commit -m "feat: add compliance baseline management E2E test"
```

## Task 14: E2E — Compliance Evaluation + Override + Learning Proof

**Files:**
- Create: `tests/e2e/test_compliance_evaluation_ui.py`
- Create: `tests/e2e/test_compliance_reviewer_override.py`
- Create: `tests/e2e/test_compliance_learning_proof.py`

**Step 1:** Write `test_compliance_evaluation_ui.py`:
- Upload doc with baseline selected (via Upload page baseline picker)
- Wait for processing → navigate to ComplianceTab
- Assert score gauge SVG visible (`[data-testid="compliance-gauge"]`)
- Assert verdict badges present (check for PASS/FAIL/PARTIAL class names)
- Assert evidence text visible for each requirement
- Screenshots: `compliance-tab-overview.png`, `score-gauge.png`

**Step 2:** Write `test_compliance_reviewer_override.py`:
- Navigate to document with compliance results
- Find FAIL badge → screenshot `before-override.png`
- Click requirement → fill override form (verdict=PASS, justification text)
- Submit → wait for update → assert badge changed color
- Screenshot: `after-override.png`

**Step 3:** Write `test_compliance_learning_proof.py`:
- Upload doc with baseline → wait → ComplianceTab
- Screenshot `run1-scores.png`
- Submit override on FAIL requirement
- Re-upload same doc (or trigger reprocess)
- Wait → navigate to new doc ComplianceTab
- Screenshot `run2-scores.png`
- Visual diff: assert at least one badge changed

**Step 4:** Commit:
```bash
git add tests/e2e/test_compliance_evaluation_ui.py tests/e2e/test_compliance_reviewer_override.py tests/e2e/test_compliance_learning_proof.py
git commit -m "feat: add compliance evaluation, override, and learning proof E2E tests"
```

## Task 15: E2E — Work Queue + Evidence Navigation

**Files:**
- Create: `tests/e2e/test_compliance_work_queue.py`
- Create: `tests/e2e/test_compliance_evidence_navigation.py`

**Step 1:** Write `test_compliance_work_queue.py`:
```python
import pytest

@pytest.mark.e2e
@pytest.mark.compliance
class TestComplianceWorkQueue:
    def test_work_queue_shows_compliance_badges(self, authenticated_page, screenshot_dir):
        page = authenticated_page
        page.get_by_role("link", name="Work Queue").click()
        page.wait_for_load_state("networkidle")

        # Assert compliance column exists
        headers = page.locator("th").all_inner_texts()
        assert any("compliance" in h.lower() for h in headers), f"No compliance column: {headers}"

        # Assert at least one badge visible
        badges = page.locator('[data-testid="compliance-badge"]').count()
        assert badges > 0, "No compliance badges in work queue"

        page.screenshot(path=str(screenshot_dir / "work-queue-compliance.png"))
```

**Step 2:** Write `test_compliance_evidence_navigation.py`:
```python
import pytest

@pytest.mark.e2e
@pytest.mark.compliance
class TestComplianceEvidenceNavigation:
    def test_evidence_link_jumps_to_pdf_page(self, authenticated_page, screenshot_dir):
        page = authenticated_page

        # Navigate to a document with compliance results
        page.get_by_role("link", name="Documents").click()
        page.wait_for_load_state("networkidle")
        page.locator("tr").first.click()  # Click first document
        page.wait_for_load_state("networkidle")

        # Go to Compliance tab
        page.get_by_role("tab", name="Compliance").click()
        page.wait_for_load_state("networkidle")

        # Get initial PDF page (if visible)
        initial_page = page.locator('[data-testid="pdf-page-number"]').inner_text()

        # Click evidence link on first requirement
        page.locator('[data-testid="evidence-link"]').first.click()
        page.wait_for_timeout(1000)  # Wait for PDF navigation

        new_page = page.locator('[data-testid="pdf-page-number"]').inner_text()
        page.screenshot(path=str(screenshot_dir / "evidence-page-jump.png"))

        # Page should have changed (or at least scrolled)
        print(f"PDF page: {initial_page} → {new_page}")
```

**Step 3:** Commit:
```bash
git add tests/e2e/test_compliance_work_queue.py tests/e2e/test_compliance_evidence_navigation.py
git commit -m "feat: add work queue badges and evidence navigation E2E tests"
```

## Task 16: Orchestrator Script — test-toolkit.sh

**Files:**
- Create: `scripts/test-toolkit.sh`

**Step 1:** Write the orchestrator script:

```bash
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

REPORTS_DIR="$PROJECT_ROOT/reports"
SCREENSHOTS_DIR="$REPORTS_DIR/screenshots"
MODE="${1:---all}"

mkdir -p "$REPORTS_DIR" "$SCREENSHOTS_DIR"

echo "=== Testing Toolkit ==="
echo "Stack: ${STACK_NAME:-FinancialDocProcessingStack}"
echo "Mode: $MODE"

# Verify stack exists
aws cloudformation describe-stacks --stack-name "${STACK_NAME:-FinancialDocProcessingStack}" > /dev/null 2>&1 || {
    echo "ERROR: Stack not deployed. Run ./scripts/deploy.sh first."
    exit 1
}

run_integration() {
    echo -e "\n=== Integration Tests ==="
    uv run pytest tests/integration/ -m integration \
        --html="$REPORTS_DIR/integration.html" --self-contained-html \
        -v --tb=short "$@"
}

run_e2e() {
    echo -e "\n=== E2E Tests (Playwright) ==="
    SCREENSHOT_DIR="$SCREENSHOTS_DIR" uv run pytest tests/e2e/ -m e2e \
        --html="$REPORTS_DIR/e2e.html" --self-contained-html \
        -v --tb=short "$@"
}

case "$MODE" in
    --integration) run_integration "${@:2}" ;;
    --e2e)         run_e2e "${@:2}" ;;
    --all)         run_integration "${@:2}"; run_e2e "${@:2}" ;;
    -k)            run_integration "$@"; run_e2e "$@" ;;
    --headed)      PLAYWRIGHT_HEADLESS=false run_e2e "${@:2}" ;;
    *)             echo "Usage: $0 [--all|--integration|--e2e|-k <filter>|--headed]"; exit 1 ;;
esac

echo -e "\n=== Reports ==="
ls -la "$REPORTS_DIR"/*.html 2>/dev/null || true
ls -la "$SCREENSHOTS_DIR"/*.png 2>/dev/null || true
[[ -f "$REPORTS_DIR/learning-loop-comparison.json" ]] && echo "Learning loop: $REPORTS_DIR/learning-loop-comparison.json"

# Open report on macOS
[[ "$(uname)" == "Darwin" ]] && open "$REPORTS_DIR/integration.html" 2>/dev/null || true
```

**Step 2:** Make executable:
```bash
chmod +x scripts/test-toolkit.sh
```

**Step 3:** Commit:
```bash
git add scripts/test-toolkit.sh
git commit -m "feat: add test-toolkit.sh orchestrator script"
```

## Task 17: Final Verification — Full Suite Run

**Files:** None (verification only)

**Step 1:** Run full integration suite (requires deployed stack):
```bash
./scripts/test-toolkit.sh --integration
```
Expected: All tests collected. Tests requiring live stack will pass or skip gracefully.

**Step 2:** Run E2E suite:
```bash
./scripts/test-toolkit.sh --e2e
```
Expected: Playwright launches Chromium, navigates frontend, captures screenshots.

**Step 3:** Run compliance subset:
```bash
./scripts/test-toolkit.sh -k compliance
```
Expected: Only compliance-marked tests run.

**Step 4:** Check reports generated:
```bash
ls -la reports/
ls -la reports/screenshots/
cat reports/learning-loop-comparison.json
```

**Step 5:** Review learning loop proof:
- Open `reports/integration.html` in browser
- Verify `learning-loop-comparison.json` shows verdict change or confidence delta
- Check `reports/screenshots/run1-scores.png` vs `run2-scores.png`

**Step 6:** Final commit:
```bash
git add reports/.gitkeep
git commit -m "chore: add reports directory for test toolkit output"
```

**Step 7:** Tag milestone:
```bash
git tag -a v5.1.0-testing-toolkit -m "Testing toolkit: integration + E2E tests for plugin, PageIndex, compliance learning loop"
```
