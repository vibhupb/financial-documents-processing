"""Integration tests — Compliance Evaluation Pipeline.

Creates a published baseline with 3 requirements, uploads a sample loan PDF
with baselineIds, waits for COMPLETED status, then validates the compliance
report structure.

Requires a deployed stack and tests/sample-documents/sample-loan.pdf.
Run with:
    uv run pytest tests/integration/test_compliance_evaluation.py -v
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.compliance]


LOAN_REQUIREMENTS = [
    {
        "text": "The document must contain a stated loan amount or principal balance",
        "category": "loan-terms",
        "criticality": "must-have",
        "confidenceThreshold": 0.8,
    },
    {
        "text": "An interest rate or APR must be disclosed in the document",
        "category": "loan-terms",
        "criticality": "must-have",
        "confidenceThreshold": 0.8,
    },
    {
        "text": "The document must identify the borrower by name",
        "category": "parties",
        "criticality": "should-have",
        "confidenceThreshold": 0.7,
    },
]

VALID_VERDICTS = {"PASS", "FAIL", "PARTIAL", "NOT_FOUND"}


class TestComplianceEvaluation:
    """Validate the end-to-end compliance evaluation pipeline."""

    def test_evaluation_pipeline(
        self,
        api,
        create_published_baseline,
        upload_and_wait,
        sample_loan_pdf,
    ):
        """Upload with baseline -> wait -> validate report structure."""

        # ── Create published baseline ──────────────────────────────────────
        baseline_id = create_published_baseline(LOAN_REQUIREMENTS)

        # ── Upload sample loan PDF with baselineIds ────────────────────────
        doc_id, status, elapsed = upload_and_wait(
            sample_loan_pdf, baseline_ids=[baseline_id]
        )
        assert status in ("PROCESSED", "COMPLETED"), (
            f"Document processing did not complete: status={status} "
            f"(elapsed={elapsed:.0f}s)"
        )

        # ── Fetch compliance reports ───────────────────────────────────────
        reports_resp = api.get(f"/documents/{doc_id}/compliance")
        assert reports_resp.status_code == 200, (
            f"Get compliance reports failed: {reports_resp.status_code} "
            f"{reports_resp.text}"
        )
        reports_data = reports_resp.json()
        reports = reports_data.get("reports", [])
        assert len(reports) >= 1, (
            f"Expected at least 1 compliance report, got {len(reports)}. "
            f"Response: {reports_data}"
        )

        # Find the report for our baseline
        report = None
        for r in reports:
            if r.get("baselineId") == baseline_id:
                report = r
                break

        assert report is not None, (
            f"No report found for baseline {baseline_id}. "
            f"Available baseline IDs: "
            f"{[r.get('baselineId') for r in reports]}"
        )

        # ── Validate report top-level structure ────────────────────────────
        assert "reportId" in report, "Report missing reportId"
        assert report["documentId"] == doc_id
        assert report["baselineId"] == baseline_id
        assert report["status"] == "completed"

        overall_score = report.get("overallScore")
        assert overall_score is not None, "Report missing overallScore"
        # DynamoDB may return Decimal, convert to float for comparison
        score = float(overall_score)
        assert 0 <= score <= 100, (
            f"overallScore out of range: {score}"
        )

        # ── Validate individual results ────────────────────────────────────
        results = report.get("results", [])
        assert len(results) == len(LOAN_REQUIREMENTS), (
            f"Expected {len(LOAN_REQUIREMENTS)} results, got {len(results)}"
        )

        for i, result in enumerate(results):
            # Verdict must be one of the valid values
            verdict = result.get("verdict")
            assert verdict in VALID_VERDICTS, (
                f"Result {i}: invalid verdict '{verdict}', "
                f"expected one of {VALID_VERDICTS}"
            )

            # Confidence must be between 0 and 1
            confidence = float(result.get("confidence", -1))
            assert 0 <= confidence <= 1, (
                f"Result {i}: confidence {confidence} out of [0, 1] range"
            )

            # Evidence must be non-empty string
            evidence = result.get("evidence", "")
            assert isinstance(evidence, str) and len(evidence) > 0, (
                f"Result {i}: evidence is empty or not a string"
            )

            # Character offsets must be integers
            char_start = result.get("evidenceCharStart")
            char_end = result.get("evidenceCharEnd")
            assert isinstance(char_start, (int, float)), (
                f"Result {i}: evidenceCharStart is not numeric: "
                f"{type(char_start)}"
            )
            assert isinstance(char_end, (int, float)), (
                f"Result {i}: evidenceCharEnd is not numeric: "
                f"{type(char_end)}"
            )
            assert int(char_start) >= 0, (
                f"Result {i}: evidenceCharStart negative: {char_start}"
            )
            assert int(char_end) >= int(char_start), (
                f"Result {i}: evidenceCharEnd ({char_end}) < "
                f"evidenceCharStart ({char_start})"
            )

            # requirementId must be present
            assert "requirementId" in result, (
                f"Result {i}: missing requirementId"
            )

    def test_report_accessible_by_id(
        self,
        api,
        create_published_baseline,
        upload_and_wait,
        sample_loan_pdf,
    ):
        """Verify individual report can be fetched by reportId."""

        baseline_id = create_published_baseline(LOAN_REQUIREMENTS)
        doc_id, status, _ = upload_and_wait(
            sample_loan_pdf, baseline_ids=[baseline_id]
        )
        assert status in ("PROCESSED", "COMPLETED")

        # Get all reports
        reports_resp = api.get(f"/documents/{doc_id}/compliance")
        reports = reports_resp.json().get("reports", [])
        assert len(reports) >= 1

        report = next(
            (r for r in reports if r.get("baselineId") == baseline_id), None
        )
        assert report is not None

        # Fetch individual report
        report_id = report["reportId"]
        detail_resp = api.get(
            f"/documents/{doc_id}/compliance/{report_id}"
        )
        assert detail_resp.status_code == 200
        detail = detail_resp.json().get("report")
        assert detail is not None, (
            f"Single report fetch returned no report: {detail_resp.json()}"
        )
        assert detail["reportId"] == report_id
        assert detail["documentId"] == doc_id
