"""E2E: Compliance baseline CRUD — create, add requirements, publish.

Navigates to the Baselines page, creates a new baseline, adds three
requirements, publishes the baseline, and verifies the status badge
transitions from draft to published.  Screenshots at each step.
"""

import pytest

from .pages.baselines_page import BaselinesPage
from .pages.baseline_editor_page import BaselineEditorPage


@pytest.mark.e2e
class TestComplianceBaselineManagement:
    """Create a baseline, add requirements, publish, and verify status."""

    def test_create_add_requirements_and_publish(
        self, authenticated_page, screenshot_dir
    ):
        page = authenticated_page

        # -- Navigate to Baselines -------------------------------------------
        baselines = BaselinesPage(page)
        baselines.navigate()
        page.screenshot(
            path=str(screenshot_dir / "baselines_list_before.png")
        )

        # -- Create a new baseline -------------------------------------------
        baselines.create_baseline()
        # After creation, the UI navigates to the baseline editor page
        page.screenshot(
            path=str(screenshot_dir / "baseline_created.png")
        )

        editor = BaselineEditorPage(page)
        baseline_name = editor.get_baseline_name()
        assert baseline_name, "Baseline name should be visible in the editor"

        # Verify initial status is draft (Publish button visible)
        assert editor.get_status_badge_text() == "draft", (
            "Newly created baseline should be in draft status"
        )

        # -- Add three requirements ------------------------------------------
        editor.add_requirement()
        page.wait_for_timeout(500)
        editor.add_requirement()
        page.wait_for_timeout(500)
        editor.add_requirement()
        page.wait_for_timeout(500)

        page.screenshot(
            path=str(screenshot_dir / "baseline_3_requirements.png")
        )

        reqs = editor.get_requirements()
        assert len(reqs) >= 3, (
            f"Expected at least 3 requirements, found {len(reqs)}"
        )

        # -- Publish ---------------------------------------------------------
        editor.publish()
        page.wait_for_timeout(1000)

        page.screenshot(
            path=str(screenshot_dir / "baseline_published.png")
        )

        # After publishing, the Publish button should disappear
        status = editor.get_status_badge_text()
        assert status == "published", (
            f"Baseline should be published after clicking Publish, got: {status}"
        )

        # -- Verify on Baselines list ----------------------------------------
        baselines.navigate()
        baselines.filter_by_status("published")
        page.wait_for_timeout(1000)

        page.screenshot(
            path=str(screenshot_dir / "baselines_published_filter.png")
        )

        names = baselines.get_baseline_names()
        assert any(
            baseline_name in n for n in names
        ), (
            f"Published baseline '{baseline_name}' not found in list: {names}"
        )
