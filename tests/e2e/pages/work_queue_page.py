"""Page Object Model for the Work Queue page.

Route: / (root)

The main page showing the UploadBar, MetricsStrip, and a document table
with columns: Document, Type, Status, Compliance, Cost, Time, Actions.
"""

from playwright.sync_api import Page, Locator


class WorkQueuePage:
    """Interact with the WorkQueue page."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate(self) -> None:
        """Click the Work Queue nav link in the sidebar."""
        self.page.get_by_role("link", name="Work Queue").click()
        self.page.wait_for_load_state("networkidle")

    def get_column_headers(self) -> list[str]:
        """Return the text of all table column headers.

        The table renders <th> elements with uppercase text.
        """
        headers = self.page.locator("th").all()
        return [h.inner_text().strip() for h in headers]

    def get_compliance_badges(self) -> list[Locator]:
        """Return compliance score badge elements from the table.

        Compliance badges show percentage text like "85%" with color
        coding (green/yellow/red based on score).
        """
        # Compliance badges are in the 4th column (index 3) of each row,
        # rendered as <span> with rounded + text-xs + font-medium
        return self.page.locator(
            'td:nth-child(4) span[class*="rounded"]'
        ).all()

    def get_document_rows(self) -> list[Locator]:
        """Return all document table row elements."""
        return self.page.locator("tbody tr").all()

    def click_document_row(self, index: int = 0) -> None:
        """Click a document row by index (0-based)."""
        rows = self.get_document_rows()
        if rows and index < len(rows):
            rows[index].click()
            self.page.wait_for_load_state("networkidle")

    def search(self, query: str) -> None:
        """Type into the search input to filter documents."""
        search_input = self.page.get_by_placeholder(
            "Search by filename or ID..."
        )
        search_input.fill(query)

    def filter_by_status(self, status_label: str) -> None:
        """Select a status filter from the dropdown.

        Valid labels: All, Processing, Needs Review, Approved, Rejected, Failed
        """
        self.page.locator("select").first.select_option(label=status_label)
        self.page.wait_for_load_state("networkidle")

    def get_empty_state_text(self) -> str:
        """Return the empty state message when no documents exist."""
        empty = self.page.locator("text=No documents yet")
        if empty.count() > 0:
            return empty.first.inner_text()
        return ""
