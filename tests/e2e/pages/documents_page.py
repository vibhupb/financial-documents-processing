"""Page Object Model for the Documents list.

The documents list is actually the Work Queue page (route: /) which serves
as the primary document list view.  This POM provides document-list-focused
methods on top of the same page.
"""

from playwright.sync_api import Page, Locator


class DocumentsPage:
    """Interact with the document list on the Work Queue page."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate(self) -> None:
        """Navigate to the Work Queue which is the documents list.

        The Work Queue is the root route (/) and also accessible via the
        'Work Queue' sidebar link.
        """
        self.page.get_by_role("link", name="Work Queue").click()
        self.page.wait_for_load_state("networkidle")

    def click_first_document(self) -> None:
        """Click the first document row in the table."""
        rows = self.get_document_rows()
        if rows:
            rows[0].click()
            self.page.wait_for_load_state("networkidle")

    def get_document_rows(self) -> list[Locator]:
        """Return all document row elements from the table."""
        return self.page.locator("tbody tr").all()

    def get_document_count(self) -> int:
        """Return the number of documents visible in the table."""
        return len(self.get_document_rows())

    def get_document_names(self) -> list[str]:
        """Return the filenames from all visible document rows.

        The filename is in the first <td> inside a <p> with font-medium.
        """
        rows = self.get_document_rows()
        names = []
        for row in rows:
            name_el = row.locator("td").first.locator("p.text-sm.font-medium")
            if name_el.count() > 0:
                names.append(name_el.first.inner_text().strip())
        return names

    def click_document_by_name(self, name: str) -> None:
        """Click a document row by matching its filename text."""
        row = self.page.locator("tbody tr", has_text=name).first
        row.click()
        self.page.wait_for_load_state("networkidle")

    def has_documents(self) -> bool:
        """Return True if the table has at least one document row."""
        return len(self.get_document_rows()) > 0
