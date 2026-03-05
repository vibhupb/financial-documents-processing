"""Page Object Model for the Baseline Editor page.

Route: /baselines/:baselineId

Shows the baseline name, description, status, a list of requirements with
inline edit/delete, an Add Requirement button, and a Publish button
(visible only for draft baselines).
"""

from playwright.sync_api import Page, Locator


class BaselineEditorPage:
    """Interact with the BaselineEditor page."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def add_requirement(
        self,
        text: str = "",
        category: str = "",
        criticality: str = "",
    ) -> None:
        """Click the Add Requirement button.

        The editor adds a default requirement ("New requirement",
        category "General", criticality "should-have").  The text,
        category, and criticality parameters are for future use
        if the UI adds inline creation fields.
        """
        self.page.get_by_role("button", name="Add Requirement").click()
        self.page.wait_for_load_state("networkidle")

    def publish(self) -> None:
        """Click the Publish button to publish the baseline."""
        self.page.get_by_role("button", name="Publish").click()
        self.page.wait_for_load_state("networkidle")

    def get_requirements(self) -> list[Locator]:
        """Return all requirement card elements.

        Each requirement renders as a div with border + rounded-lg + bg-white.
        """
        return self.page.locator(
            'div.border.rounded-lg.bg-white'
        ).all()

    def get_status_badge_text(self) -> str:
        """Return the baseline status by inspecting the page content.

        After publishing, the Publish button disappears and the baseline
        status changes.  We look for status indicators in the page.
        """
        # The BaselineEditor doesn't render a status badge directly,
        # but the Publish button is only visible for draft baselines.
        publish_btn = self.page.get_by_role("button", name="Publish")
        if publish_btn.count() > 0 and publish_btn.is_visible():
            return "draft"
        return "published"

    def get_requirement_texts(self) -> list[str]:
        """Return the text of all requirements."""
        reqs = self.get_requirements()
        texts = []
        for req in reqs:
            # The requirement text is in a <p> inside the flex-1 div
            p_el = req.locator("p.text-sm").first
            if p_el.count() > 0:
                texts.append(p_el.inner_text())
        return texts

    def get_baseline_name(self) -> str:
        """Return the baseline name from the page heading."""
        return self.page.locator("h1").first.inner_text().strip()

    def delete_requirement(self, index: int = 0) -> None:
        """Delete the requirement at the given index (0-based).

        Clicks the trash icon button on the specified requirement card.
        """
        reqs = self.get_requirements()
        if index < len(reqs):
            # The delete button is the last button in each requirement card
            delete_btn = reqs[index].locator("button").last
            delete_btn.click()
            self.page.wait_for_load_state("networkidle")
