"""E2E test fixtures for Playwright browser tests against deployed frontend.

Fixtures:
    stack_config    - CloudFormation output key->value map (session-scoped)
    frontend_url    - HTTPS URL of the CloudFront distribution
    screenshot_dir  - Directory for saving failure screenshots
    authenticated_page - Playwright page navigated to frontend with Cognito auth
"""

import os

import boto3
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STACK_NAME = os.environ.get("STACK_NAME", "FinancialDocProcessingStack")
SCREENSHOT_DIR = Path(os.environ.get("SCREENSHOT_DIR", "reports/screenshots"))


# ---------------------------------------------------------------------------
# Session-scoped: stack discovery
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stack_config():
    """Discover deployed stack from CloudFormation."""
    cf = boto3.client("cloudformation")
    try:
        resp = cf.describe_stacks(StackName=STACK_NAME)
    except Exception:
        pytest.skip(f"Stack {STACK_NAME} not deployed")
    outputs = {
        o["OutputKey"]: o["OutputValue"]
        for o in resp["Stacks"][0].get("Outputs", [])
    }
    return {
        "api_url": outputs.get("ApiEndpoint", "").rstrip("/"),
        "frontend_url": outputs.get("CloudFrontUrl", "").rstrip("/"),
    }


@pytest.fixture(scope="session")
def frontend_url(stack_config):
    """Return the HTTPS frontend URL from stack outputs."""
    url = stack_config["frontend_url"]
    assert url, "Frontend URL not found in stack outputs"
    # Ensure https://
    if not url.startswith("http"):
        url = f"https://{url}"
    return url


@pytest.fixture(scope="session")
def screenshot_dir():
    """Create and return the screenshot output directory."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR


@pytest.fixture
def authenticated_page(page, frontend_url):
    """Navigate to frontend, handle Cognito auth if needed.

    If REQUIRE_AUTH is enabled and the page redirects to Cognito hosted UI,
    this fixture fills the login form using TEST_USER / TEST_PASSWORD env vars.
    Skips the test when credentials are required but not provided.
    """
    page.goto(frontend_url)
    page.wait_for_load_state("networkidle")

    # If redirected to Cognito login, handle it
    if "cognito" in page.url.lower() or "signin" in page.url.lower():
        test_user = os.environ.get("TEST_USER", "")
        test_pass = os.environ.get("TEST_PASSWORD", "")
        if not test_user or not test_pass:
            pytest.skip(
                "Cognito auth required but TEST_USER/TEST_PASSWORD not set"
            )
        page.fill('[name="username"]', test_user)
        page.fill('[name="password"]', test_pass)
        page.click('[type="submit"]')
        page.wait_for_load_state("networkidle")

    return page
