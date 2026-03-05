"""Integration test fixtures — auto-discover deployed stack and provide helpers.

Fixtures:
    stack_config  – CloudFormation output key→value map (session-scoped)
    api           – requests.Session pre-configured with the API base URL
    s3_client     – boto3 S3 client for direct bucket operations
    upload_and_wait – upload a PDF via presigned POST and poll until terminal status
    create_published_baseline – create, add requirements, and publish a baseline
    cleanup       – auto-archive baselines created during tests (autouse)
"""

import json
import os
import time
import uuid
from io import BytesIO
from pathlib import Path

import boto3
import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STACK_NAME = os.environ.get("STACK_NAME", "FinancialDocProcessingStack")
TEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT", "300"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent / "sample-documents"

# ---------------------------------------------------------------------------
# Session-scoped: stack discovery
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stack_config():
    """Discover deployed stack outputs from CloudFormation.

    Reads CfnOutput entries defined in document-processing-stack.ts and maps
    them to friendly names.  Skips the entire test session when the stack is
    not deployed.

    Known output keys (from CDK stack):
        ApiEndpoint, DocumentBucketName, FrontendBucketName,
        CloudFrontUrl, DocumentTableName, StateMachineArn,
        UserPoolId, UserPoolClientId, PIIEncryptionKeyArn,
        PIIAuditTableName, PluginConfigsTableName
    """
    cf = boto3.client("cloudformation")
    try:
        resp = cf.describe_stacks(StackName=STACK_NAME)
    except cf.exceptions.ClientError:
        pytest.skip(f"Stack {STACK_NAME} not deployed — skipping integration tests")

    outputs = {
        o["OutputKey"]: o["OutputValue"]
        for o in resp["Stacks"][0].get("Outputs", [])
    }

    config = {
        "api_url": outputs.get("ApiEndpoint", "").rstrip("/"),
        "bucket_name": outputs.get("DocumentBucketName", ""),
        "frontend_bucket": outputs.get("FrontendBucketName", ""),
        "frontend_url": outputs.get("CloudFrontUrl", ""),
        "table_name": outputs.get("DocumentTableName", ""),
        "state_machine_arn": outputs.get("StateMachineArn", ""),
        "user_pool_id": outputs.get("UserPoolId", ""),
        "user_pool_client_id": outputs.get("UserPoolClientId", ""),
        "pii_key_arn": outputs.get("PIIEncryptionKeyArn", ""),
        # Keep the raw outputs dict for ad-hoc lookups
        "raw_outputs": outputs,
    }

    assert config["api_url"], (
        f"Could not find ApiEndpoint in stack outputs. "
        f"Available keys: {sorted(outputs.keys())}"
    )
    return config


# ---------------------------------------------------------------------------
# Session-scoped: HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api(stack_config):
    """HTTP client pre-configured with the deployed API base URL.

    Usage in tests:
        resp = api.get("/documents")
        resp = api.post("/upload", json={...})

    Paths without a scheme are automatically prepended with the base URL.
    """
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    base_url = stack_config["api_url"]

    original_request = session.request

    def _patched_request(method, url, **kwargs):
        if not url.startswith("http"):
            url = f"{base_url}{url}"
        return original_request(method, url, **kwargs)

    session.request = _patched_request
    return session


# ---------------------------------------------------------------------------
# Session-scoped: AWS clients
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def s3_client():
    """Boto3 S3 client for direct bucket operations."""
    return boto3.client("s3")


@pytest.fixture(scope="session")
def dynamodb_resource():
    """Boto3 DynamoDB resource for direct table access."""
    return boto3.resource("dynamodb")


# ---------------------------------------------------------------------------
# Helpers: sample documents
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_loan_pdf():
    """Path to the sample loan PDF in tests/sample-documents/."""
    p = SAMPLE_DOCS_DIR / "sample-loan.pdf"
    assert p.exists(), f"Sample loan PDF missing: {p}"
    return p


@pytest.fixture(scope="session")
def sample_bsa_pdf():
    """Path to the sample BSA profile PDF."""
    p = SAMPLE_DOCS_DIR / "sample-bsa-profile-filled.pdf"
    if not p.exists():
        p = SAMPLE_DOCS_DIR / "sample-bsa-profile.pdf"
    assert p.exists(), f"Sample BSA PDF missing: {p}"
    return p


# ---------------------------------------------------------------------------
# Upload + wait helper
# ---------------------------------------------------------------------------

# Tracks document IDs created during tests for potential cleanup
_created_doc_ids: list[str] = []


@pytest.fixture
def upload_and_wait(api):
    """Upload a PDF via presigned POST and poll until processing completes.

    Returns a callable:
        doc_id, final_status, elapsed = upload_and_wait(pdf_path, baseline_ids=None)

    The upload uses the presigned POST flow that the real frontend uses:
        1. POST /upload → {documentId, uploadUrl, fields}
        2. POST to uploadUrl with form fields + file
        3. Poll GET /documents/{id}/status until terminal state

    Terminal states: COMPLETED, FAILED, ERROR
    """
    def _upload(pdf_path, baseline_ids=None, processing_mode="extract"):
        pdf_path = Path(pdf_path)
        assert pdf_path.exists(), f"PDF not found: {pdf_path}"

        # Step 1: Get presigned POST URL
        payload = {
            "filename": pdf_path.name,
            "contentType": "application/pdf",
            "processingMode": processing_mode,
        }
        if baseline_ids:
            payload["baselineIds"] = baseline_ids

        resp = api.post("/upload", json=payload)
        assert resp.status_code == 200, (
            f"Upload URL request failed: {resp.status_code} {resp.text}"
        )
        upload_data = resp.json()

        doc_id = upload_data["documentId"]
        upload_url = upload_data["uploadUrl"]
        form_fields = upload_data["fields"]

        _created_doc_ids.append(doc_id)

        # Step 2: Upload file via presigned POST (multipart form)
        # Append a random trailer comment to the PDF bytes so that each upload
        # produces a unique SHA-256 hash.  Without this, the Trigger Lambda's
        # content-based deduplication detects the same sample PDF and skips
        # processing — the new documentId never gets a DynamoDB record, causing
        # status polling to return NOT_FOUND indefinitely.
        pdf_bytes = pdf_path.read_bytes()
        nonce = f"\n% unique-test-nonce {uuid.uuid4().hex}\n".encode()
        unique_pdf = pdf_bytes + nonce

        files = {"file": (pdf_path.name, BytesIO(unique_pdf), "application/pdf")}
        put_resp = requests.post(upload_url, data=form_fields, files=files)
        assert put_resp.status_code in (200, 204), (
            f"S3 presigned POST upload failed: {put_resp.status_code} "
            f"{put_resp.text[:200]}"
        )

        # Step 3: Poll for terminal status
        start = time.time()
        status = "PENDING"
        while time.time() - start < TEST_TIMEOUT:
            status_resp = api.get(f"/documents/{doc_id}/status")
            if status_resp.status_code == 200:
                body = status_resp.json()
                status = body.get("status", "UNKNOWN")
                if status in ("COMPLETED", "FAILED", "ERROR"):
                    break
            time.sleep(POLL_INTERVAL)

        elapsed = time.time() - start
        return doc_id, status, elapsed

    return _upload


# ---------------------------------------------------------------------------
# Baseline helpers
# ---------------------------------------------------------------------------

# Tracks baseline IDs created during tests for cleanup
_created_baselines: list[str] = []


@pytest.fixture
def create_published_baseline(api):
    """Create a compliance baseline with requirements and publish it.

    Returns a callable:
        baseline_id = create_published_baseline(requirements)

    Each requirement dict should have at minimum: {"text": "..."}
    Optional keys: category, criticality, confidenceThreshold

    Response shapes (from API handler):
        POST /baselines          → full baseline item with baselineId
        POST /baselines/{id}/requirements → {baselineId, requirement: {...}}
        POST /baselines/{id}/publish     → {baselineId, status, version}
    """
    def _create(requirements):
        assert requirements, "Must provide at least one requirement"

        # Create draft baseline
        resp = api.post("/baselines", json={
            "name": f"Integration Test Baseline {uuid.uuid4().hex[:8]}",
            "description": "Auto-created by integration test suite",
        })
        assert resp.status_code == 200, (
            f"Create baseline failed: {resp.status_code} {resp.text}"
        )
        baseline_data = resp.json()
        baseline_id = baseline_data["baselineId"]
        _created_baselines.append(baseline_id)

        # Add each requirement
        for req in requirements:
            req_payload = {"text": req["text"]}
            if "category" in req:
                req_payload["category"] = req["category"]
            if "criticality" in req:
                req_payload["criticality"] = req["criticality"]
            if "confidenceThreshold" in req:
                req_payload["confidenceThreshold"] = req["confidenceThreshold"]

            add_resp = api.post(
                f"/baselines/{baseline_id}/requirements", json=req_payload
            )
            assert add_resp.status_code == 200, (
                f"Add requirement failed: {add_resp.status_code} {add_resp.text}"
            )

        # Publish
        pub_resp = api.post(f"/baselines/{baseline_id}/publish")
        assert pub_resp.status_code == 200, (
            f"Publish baseline failed: {pub_resp.status_code} {pub_resp.text}"
        )
        pub_data = pub_resp.json()
        assert pub_data.get("status") == "published", (
            f"Baseline not published: {pub_data}"
        )

        return baseline_id

    return _create


@pytest.fixture
def create_draft_baseline(api):
    """Create a draft baseline (without publishing). Returns baseline_id."""
    def _create(name=None, description=None):
        resp = api.post("/baselines", json={
            "name": name or f"Draft Baseline {uuid.uuid4().hex[:8]}",
            "description": description or "Draft baseline for testing",
        })
        assert resp.status_code == 200, (
            f"Create baseline failed: {resp.status_code} {resp.text}"
        )
        baseline_id = resp.json()["baselineId"]
        _created_baselines.append(baseline_id)
        return baseline_id

    return _create


# ---------------------------------------------------------------------------
# Cleanup (autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_baselines(api):
    """Archive any baselines created during each test (autouse)."""
    yield
    for bid in _created_baselines[:]:
        try:
            api.put(f"/baselines/{bid}", json={"status": "archived"})
        except Exception:
            pass
    _created_baselines.clear()
