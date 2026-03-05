"""Page Object Model for the Document Detail page.

Route: /documents/:documentId

Shows document header with status badge, and in completed state renders
the DocumentViewer with PDF panel + tabbed data panel (Summary, Extracted,
JSON, Compliance).  Status bar at the bottom shows current page number.
"""

from playwright.sync_api import Page, Locator, expect


class DocumentDetailPage:
    """Interact with the DocumentDetail page."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def wait_for_processing(self, timeout: int = 300_000) -> None:
        """Wait until the document status shows a completed state.

        Polls the StatusBadge component for terminal labels:
        Processed, Approved, Pending Review, Failed, Skipped.
        """
        # StatusBadge renders text like "Processed", "Approved", etc.
        # Wait for any terminal status to appear in the header area
        self.page.wait_for_function(
            """() => {
                const badges = document.querySelectorAll('span.rounded-full');
                const terminal = ['Processed', 'Approved', 'Pending Review',
                                  'Failed', 'Skipped', 'Rejected'];
                return Array.from(badges).some(
                    el => terminal.includes(el.textContent?.trim() || '')
                );
            }""",
            timeout=timeout,
        )

    def click_tab(self, tab_name: str) -> None:
        """Click a data view tab by its label text.

        Valid tab names: Summary, Extracted, JSON, Compliance
        """
        self.page.get_by_role("button", name=tab_name).click()

    def get_extracted_data_text(self) -> str:
        """Return the text content of the extracted data panel.

        Assumes the Extracted tab is currently active.
        """
        # The extracted values panel is the scrollable area inside the
        # right panel when the Extracted tab is active
        panel = self.page.locator('[class*="overflow-auto"]').last
        return panel.inner_text()

    def get_pdf_page_number(self) -> str:
        """Return the current page number text from the status bar.

        The status bar shows "Current Page: X / Y" at the bottom.
        """
        status_bar = self.page.locator("text=Current Page:")
        if status_bar.count() == 0:
            return ""
        return status_bar.first.inner_text()

    def get_status_badge_text(self) -> str:
        """Return the status badge text from the document header."""
        badge = self.page.locator("span.rounded-full").first
        return badge.inner_text().strip()

    def get_document_title(self) -> str:
        """Return the document title (filename) from the header."""
        heading = self.page.locator("h1").first
        return heading.inner_text().strip()

    def get_compliance_score(self) -> str:
        """Return the compliance score text when ComplianceTab is active.

        The ComplianceScoreGauge renders the score as an SVG donut chart
        with text.
        """
        self.click_tab("Compliance")
        self.page.wait_for_load_state("networkidle")
        # The score gauge renders score text inside the component
        gauge = self.page.locator('[class*="space-y-4"]').first
        return gauge.inner_text()

    def get_verdict_badges(self) -> list[Locator]:
        """Return VerdictBadge elements from the Compliance tab."""
        return self.page.locator('[class*="rounded"][class*="text-xs"]').all()
