"""Page Object Model for the Upload (UploadBar) component.

The upload functionality lives in the UploadBar component embedded in the
WorkQueue page (route: /).  It uses react-dropzone for drag-and-drop PDF
uploads with optional baseline selection checkboxes.
"""

from pathlib import Path
from playwright.sync_api import Page, expect


class UploadPage:
    """Interact with the UploadBar component on the Work Queue page."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def navigate(self) -> None:
        """Navigate to the Work Queue page where upload lives."""
        self.page.get_by_role("link", name="Work Queue").click()
        self.page.wait_for_load_state("networkidle")

    def upload_file(self, file_path: str | Path) -> None:
        """Set the file input via the dropzone hidden input.

        react-dropzone renders a hidden <input type="file"> inside the
        dropzone div.  We use set_input_files to feed it a file.
        """
        file_path = str(file_path)
        # The dropzone input is the first file input on the page
        file_input = self.page.locator('input[type="file"]').first
        file_input.set_input_files(file_path)

    def select_baselines(self, baseline_names: list[str]) -> None:
        """Check baseline checkboxes by their label text.

        Baseline checkboxes appear below the upload bar when published
        baselines exist.  Each is a <label> wrapping a checkbox + name.
        """
        for name in baseline_names:
            checkbox = self.page.get_by_label(name)
            if not checkbox.is_checked():
                checkbox.check()

    def submit(self) -> None:
        """Wait for the upload to complete.

        The UploadBar auto-submits on file drop (no separate submit button).
        Wait for the success message to appear indicating upload completed.
        """
        # Wait for the success indicator (green "uploaded successfully" text)
        self.page.wait_for_selector(
            "text=uploaded successfully", timeout=30_000
        )

    def get_status_text(self) -> str:
        """Return the current status text from the upload bar."""
        # The status text is inside the dropzone container
        dropzone = self.page.locator('[class*="rounded-lg border"]').first
        return dropzone.inner_text()

    def wait_for_idle(self) -> None:
        """Wait for the upload bar to return to idle state."""
        self.page.wait_for_selector(
            "text=Drop a PDF here or click to upload", timeout=10_000
        )
