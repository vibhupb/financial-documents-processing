"""Page Object Model for the Baselines list page.

Route: /baselines

Displays compliance baselines in a card grid with status filter tabs
(All, draft, published, archived) and a Create Baseline button.
"""

from playwright.sync_api import Page, Locator


class BaselinesPage:
    """Interact with the Baselines list page."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate(self) -> None:
        """Click the Baselines nav link in the sidebar."""
        self.page.get_by_role("link", name="Baselines").click()
        self.page.wait_for_load_state("networkidle")

    def create_baseline(self, name: str = "", description: str = "") -> None:
        """Click the Create Baseline button.

        The Baselines page auto-creates a baseline named "New Baseline"
        and navigates to the editor.  The name/description parameters
        are for future use if the UI adds a creation form.
        """
        self.page.get_by_role("button", name="Create Baseline").click()
        self.page.wait_for_load_state("networkidle")

    def get_baseline_rows(self) -> list[Locator]:
        """Return all baseline card link elements.

        Each baseline renders as an <a> (Link) with border + rounded-lg.
        """
        return self.page.locator(
            'a[href^="/baselines/"]'
        ).all()

    def click_baseline(self, name: str) -> None:
        """Click a baseline card by its name text."""
        self.page.get_by_role("link", name=name).click()
        self.page.wait_for_load_state("networkidle")

    def filter_by_status(self, status: str) -> None:
        """Click a status filter tab.

        Valid values: 'All', 'draft', 'published', 'archived'
        """
        self.page.get_by_role("button", name=status, exact=True).click()
        self.page.wait_for_load_state("networkidle")

    def get_baseline_names(self) -> list[str]:
        """Return the names of all visible baseline cards."""
        cards = self.get_baseline_rows()
        return [card.locator("h3").inner_text() for card in cards]
