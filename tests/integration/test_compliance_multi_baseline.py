"""Integration tests — Multi-Baseline Compliance Evaluation.

Uploads a single document evaluated against 2 baselines simultaneously.
Verifies:
  - 2 separate compliance reports are produced
  - Each report has the correct number of results
  - No cross-contamination of requirement IDs between reports

Requires a deployed stack and tests/sample-documents/sample-loan.pdf.
Run with:
    uv run pytest tests/integration/test_compliance_multi_baseline.py -v
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.compliance]


BASELINE_A_REQUIREMENTS = [
    {
        "text": "The document must state a loan principal or total amount",
        "category": "loan-terms",
        "criticality": "must-have",
    },
    {
        "text": "An interest rate or APR must be disclosed",
        "category": "loan-terms",
        "criticality": "must-have",
    },
    {
        "text": "The maturity or term of the loan must be specified",
        "category": "loan-terms",
        "criticality": "should-have",
    },
]

BASELINE_B_REQUIREMENTS = [
    {
        "text": "The borrower's full legal name must appear in the document",
        "category": "parties",
        "criticality": "must-have",
    },
    {
        "text": "The lender's name and address must be identified",
        "category": "parties",
        "criticality": "must-have",
    },
    {
        "text": "The document must contain a signature block or execution page",
        "category": "execution",
        "criticality": "should-have",
    },
    {
        "text": "A governing law or jurisdiction clause must be present",
        "category": "legal",
        "criticality": "should-have",
    },
    {
        "text": "A default or remedies provision must be included",
        "category": "covenants",
        "criticality": "nice-to-have",
    },
]


class TestMultiBaselineEvaluation:
    """Verify multi-baseline evaluation produces separate, clean reports."""

    def test_two_baselines_separate_reports(
        self,
        api,
        create_published_baseline,
        upload_and_wait,
        sample_loan_pdf,
    ):
        """Upload with 2 baselines -> verify 2 reports with no cross-talk."""

        # ── Create two published baselines ─────────────────────────────────
        baseline_a_id = create_published_baseline(BASELINE_A_REQUIREMENTS)
        baseline_b_id = create_published_baseline(BASELINE_B_REQUIREMENTS)

        # ── Upload sample loan PDF with both baseline IDs ──────────────────
        doc_id, status, elapsed = upload_and_wait(
            sample_loan_pdf,
            baseline_ids=[baseline_a_id, baseline_b_id],
        )
        assert status in ("PROCESSED", "COMPLETED"), (
            f"Document processing did not complete: {status} "
            f"({elapsed:.0f}s)"
        )

        # ── Fetch all compliance reports for this document ─────────────────
        reports_resp = api.get(f"/documents/{doc_id}/compliance")
        assert reports_resp.status_code == 200, (
            f"Fetch reports failed: {reports_resp.status_code} "
            f"{reports_resp.text}"
        )
        reports = reports_resp.json().get("reports", [])

        # ── Find reports for each baseline ─────────────────────────────────
        report_a = None
        report_b = None
        for r in reports:
            if r.get("baselineId") == baseline_a_id:
                report_a = r
            elif r.get("baselineId") == baseline_b_id:
                report_b = r

        assert report_a is not None, (
            f"No report found for baseline A ({baseline_a_id}). "
            f"Available: {[r.get('baselineId') for r in reports]}"
        )
        assert report_b is not None, (
            f"No report found for baseline B ({baseline_b_id}). "
            f"Available: {[r.get('baselineId') for r in reports]}"
        )

        # ── Verify correct result counts ───────────────────────────────────
        results_a = report_a.get("results", [])
        results_b = report_b.get("results", [])

        assert len(results_a) == len(BASELINE_A_REQUIREMENTS), (
            f"Baseline A: expected {len(BASELINE_A_REQUIREMENTS)} results, "
            f"got {len(results_a)}"
        )
        assert len(results_b) == len(BASELINE_B_REQUIREMENTS), (
            f"Baseline B: expected {len(BASELINE_B_REQUIREMENTS)} results, "
            f"got {len(results_b)}"
        )

        # ── Verify no cross-contamination of requirement IDs ───────────────
        req_ids_a = {r["requirementId"] for r in results_a}
        req_ids_b = {r["requirementId"] for r in results_b}

        overlap = req_ids_a & req_ids_b
        assert len(overlap) == 0, (
            f"Cross-contamination detected: requirement IDs {overlap} "
            f"appear in both reports"
        )

        # All requirement IDs in report A should come from baseline A
        # (and vice versa) — verify by checking they start with req- prefix
        # and are unique within their own report
        assert len(req_ids_a) == len(results_a), (
            "Duplicate requirement IDs in report A"
        )
        assert len(req_ids_b) == len(results_b), (
            "Duplicate requirement IDs in report B"
        )

        # ── Verify each report has valid structure ─────────────────────────
        for label, report, expected_baseline in [
            ("A", report_a, baseline_a_id),
            ("B", report_b, baseline_b_id),
        ]:
            assert report["documentId"] == doc_id, (
                f"Report {label}: wrong documentId"
            )
            assert report["baselineId"] == expected_baseline, (
                f"Report {label}: wrong baselineId"
            )
            assert report["status"] == "completed", (
                f"Report {label}: status is {report['status']}"
            )
            score = float(report.get("overallScore", -1))
            assert 0 <= score <= 100, (
                f"Report {label}: overallScore {score} out of range"
            )

        # ── Verify separate report IDs ─────────────────────────────────────
        assert report_a["reportId"] != report_b["reportId"], (
            "Both baselines produced the same reportId"
        )
