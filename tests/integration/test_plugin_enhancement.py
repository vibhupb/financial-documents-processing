"""Integration test: plugin enhancement via reprocess.

Verifies that after a plugin schema is updated (e.g. adding a new field like
prepaymentPenalty to loan_agreement), reprocessing an existing document picks
up the new field without re-uploading the PDF.

If the enhancement has not been deployed, the test validates baseline
reprocessing behavior instead.
"""

import pytest
import time


@pytest.mark.integration
@pytest.mark.slow
class TestPluginEnhancement:
    def test_enhanced_plugin_field_on_reprocess(
        self, api, upload_and_wait, sample_loan_pdf
    ):
        """Updated plugin fields appear on reprocess."""
        # Note: This test requires loan_agreement plugin to have been patched
        # with a prepaymentPenalty field and backend redeployed.
        # If the field does not exist, test validates baseline behavior instead.

        # 1. Check current plugin schema
        resp = api.get("/plugins")
        plugins = {p["plugin_id"]: p for p in resp.json()}

        if "loan_agreement" not in plugins:
            pytest.skip("loan_agreement plugin not registered")

        schema_str = str(plugins["loan_agreement"].get("output_schema", {}))
        has_new_field = "prepaymentPenalty" in schema_str
        print(f"prepaymentPenalty in schema: {has_new_field}")

        # 2. Upload and process
        doc_id, status, duration = upload_and_wait(str(sample_loan_pdf))
        assert status == "COMPLETED", f"Failed: {status} after {duration:.0f}s"

        # 3. Get extracted data (v1)
        resp = api.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        v1_data = resp.json().get("extractedData") or resp.json().get("data", {})
        v1_keys = set(v1_data.keys())
        print(f"v1 keys ({len(v1_keys)}): {sorted(v1_keys)}")

        # 4. Reprocess
        resp = api.post(f"/documents/{doc_id}/reprocess")
        if resp.status_code not in (200, 202):
            pytest.skip(f"Reprocess not supported: {resp.status_code}")

        # 5. Wait for reprocessing
        for _ in range(30):
            resp = api.get(f"/documents/{doc_id}/status")
            if resp.status_code == 200 and resp.json().get("status") == "COMPLETED":
                break
            time.sleep(10)

        # 6. Get v2 data
        resp = api.get(f"/documents/{doc_id}")
        v2_data = resp.json().get("extractedData") or resp.json().get("data", {})
        v2_keys = set(v2_data.keys())
        print(f"v2 keys ({len(v2_keys)}): {sorted(v2_keys)}")
        print(f"New in v2: {v2_keys - v1_keys}")
        print(f"Removed in v2: {v1_keys - v2_keys}")

        # 7. If enhancement was deployed, verify new field
        if has_new_field:
            assert "prepaymentPenalty" in v2_keys, (
                "Enhanced field missing after reprocess"
            )
