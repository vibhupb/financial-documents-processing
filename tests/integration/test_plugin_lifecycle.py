"""Integration test: full plugin lifecycle from discovery through extraction.

Verifies that a newly registered document type plugin (test_invoice) is
correctly discovered by the registry, routed during classification, extracted
by Textract, normalized by the LLM, and queryable via the API.

Requires:
    - Deployed stack with the test_invoice plugin in the plugins layer
    - tests/fixtures/test_invoice.pdf generated via:
        uv run python scripts/generate-test-invoice.py
"""

import pytest
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.integration
@pytest.mark.slow
class TestPluginLifecycle:
    def test_new_plugin_full_pipeline(self, api, upload_and_wait):
        """New doc type: plugin discovery -> routing -> extraction -> normalization -> API."""
        # 1. Verify plugin registered
        resp = api.get("/plugins")
        assert resp.status_code == 200
        data = resp.json()
        plugins = data.get("plugins", data)  # {"plugins": {id: {...}}} or flat dict
        plugin_ids = list(plugins.keys()) if isinstance(plugins, dict) else [p.get("pluginId", p.get("plugin_id")) for p in plugins]
        assert "test_invoice" in plugin_ids, f"test_invoice not in {plugin_ids}"

        # 2. Upload test invoice
        pdf_path = FIXTURES / "test_invoice.pdf"
        if not pdf_path.exists():
            pytest.skip(
                "test_invoice.pdf not generated -- "
                "run scripts/generate-test-invoice.py first"
            )

        doc_id, status, duration = upload_and_wait(str(pdf_path))
        assert status in ("PROCESSED", "COMPLETED"), (
            f"Processing failed with status: {status} after {duration:.0f}s"
        )
        print(f"Processing completed in {duration:.0f}s")

        # 3. Verify document type
        resp = api.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        doc = resp.json()
        assert doc.get("documentType") == "test_invoice", (
            f"Got type: {doc.get('documentType')}"
        )

        # 4. Verify extracted fields
        data = doc.get("extractedData") or doc.get("data", {})
        assert "vendor" in data, f"Missing vendor in {list(data.keys())}"
        assert "amount" in data, f"Missing amount in {list(data.keys())}"
        assert "invoiceDate" in data, f"Missing invoiceDate in {list(data.keys())}"

        # 5. Verify vendor value
        assert "Acme" in str(data.get("vendor", "")), (
            f"Expected Acme, got {data.get('vendor')}"
        )

        # 6. Verify audit trail
        resp = api.get(f"/documents/{doc_id}/audit")
        if resp.status_code == 200:
            audit = resp.json()
            audit_text = str(audit)
            for stage in ["ROUTER", "EXTRACTOR", "NORMALIZER"]:
                assert stage in audit_text or stage.lower() in audit_text.lower(), (
                    f"{stage} not in audit"
                )
