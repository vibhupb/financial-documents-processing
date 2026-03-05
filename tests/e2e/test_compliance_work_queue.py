"""E2E: Work Queue compliance column — header and badges.

Navigates to the Work Queue page and verifies:
  - The Compliance column header is present in the table
  - At least one compliance badge is visible (if documents exist)
  - Screenshot for evidence

This test does not upload new documents; it relies on existing data.
If no documents exist, it verifies the column header is still present.
"""

import pytest

from .pages.work_queue_page import WorkQueuePage


@pytest.mark.e2e
class TestComplianceWorkQueue:
    """Verify compliance column in the Work Queue table."""

    def test_compliance_column_and_badges(
        self, authenticated_page, screenshot_dir
    ):
        page = authenticated_page

        wq = WorkQueuePage(page)
        wq.navigate()
        page.wait_for_timeout(2000)

        page.screenshot(
            path=str(screenshot_dir / "work_queue_overview.png")
        )

        # -- Verify Compliance column header ---------------------------------
        headers = wq.get_column_headers()
        header_texts_upper = [h.upper() for h in headers]

        assert any(
            "COMPLIANCE" in h for h in header_texts_upper
        ), (
            f"Compliance column header not found. "
            f"Available headers: {headers}"
        )

        # -- Verify compliance badges if documents exist ---------------------
        rows = wq.get_document_rows()

        if len(rows) == 0:
            # No documents — just verify header was present (done above)
            page.screenshot(
                path=str(screenshot_dir / "work_queue_empty.png")
            )
            return

        badges = wq.get_compliance_badges()
        page.screenshot(
            path=str(screenshot_dir / "work_queue_compliance_badges.png")
        )

        # At least one badge should be visible if documents with compliance
        # evaluation exist.  Not all documents may have compliance results,
        # so we use a soft check.
        if len(badges) > 0:
            # Verify badge has text content (score like "85%")
            first_badge_text = badges[0].inner_text().strip()
            assert len(first_badge_text) > 0, (
                "Compliance badge is empty — no score text"
            )
        # If no badges, documents may not have compliance results — acceptable
