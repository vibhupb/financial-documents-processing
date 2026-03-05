"""E2E: Upload a loan PDF, wait for processing, verify extracted data.

Uploads sample-loan.pdf via the UploadBar, waits for the document to reach
a terminal processing state, navigates to the document detail page, clicks
the Extracted tab, and asserts that extracted content is visible.
"""

import pytest
from pathlib import Path

from .pages.upload_page import UploadPage
from .pages.documents_page import DocumentsPage
from .pages.document_detail_page import DocumentDetailPage

SAMPLE_LOAN = (
    Path(__file__).resolve().parent.parent / "sample-documents" / "sample-loan.pdf"
)


@pytest.mark.e2e
class TestUploadAndView:
    """Upload sample-loan.pdf and verify extracted data is displayed."""

    def test_upload_process_and_view_extracted_data(
        self, authenticated_page, screenshot_dir
    ):
        page = authenticated_page

        # -- Upload ----------------------------------------------------------
        upload = UploadPage(page)
        upload.navigate()

        assert SAMPLE_LOAN.exists(), f"Sample loan PDF missing: {SAMPLE_LOAN}"
        upload.upload_file(SAMPLE_LOAN)
        upload.submit()  # waits for "uploaded successfully"

        page.screenshot(path=str(screenshot_dir / "upload_success.png"))

        # -- Wait for processing ---------------------------------------------
        # The upload redirects or we navigate to the document list, then open
        # the document detail.  The most recent upload should appear first.
        docs_page = DocumentsPage(page)
        docs_page.navigate()
        page.wait_for_timeout(3000)  # brief pause for table refresh

        # Reload to pick up new document
        page.reload()
        page.wait_for_load_state("networkidle")

        assert docs_page.has_documents(), "No documents visible after upload"

        docs_page.click_first_document()

        # -- Wait for terminal status ----------------------------------------
        detail = DocumentDetailPage(page)
        detail.wait_for_processing(timeout=300_000)

        status = detail.get_status_badge_text()
        page.screenshot(path=str(screenshot_dir / "processing_complete.png"))

        assert status in (
            "Processed",
            "Approved",
            "Pending Review",
        ), f"Unexpected terminal status: {status}"

        # -- Verify Extracted tab has content ---------------------------------
        detail.click_tab("Extracted")
        page.wait_for_timeout(1000)

        extracted_text = detail.get_extracted_data_text()
        page.screenshot(path=str(screenshot_dir / "extracted_data_tab.png"))

        assert len(extracted_text) > 20, (
            f"Extracted data tab appears empty or minimal: "
            f"'{extracted_text[:100]}'"
        )
