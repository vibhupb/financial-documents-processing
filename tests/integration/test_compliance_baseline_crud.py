"""Integration tests — Compliance Baseline CRUD lifecycle.

Tests the full baseline lifecycle through the deployed API:
  create draft -> add requirements -> verify count -> update criticality ->
  delete one -> verify count -> publish -> double-publish -> archive ->
  verify not in published list.

Requires a deployed stack.  Run with:
    uv run pytest tests/integration/test_compliance_baseline_crud.py -v
"""

import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.compliance]


REQUIREMENTS = [
    {
        "text": "Borrower income must be verified with W-2 or pay stubs",
        "category": "income-verification",
        "criticality": "must-have",
        "confidenceThreshold": 0.85,
    },
    {
        "text": "Loan-to-value ratio must not exceed 80% without PMI",
        "category": "ltv-limits",
        "criticality": "must-have",
        "confidenceThreshold": 0.9,
    },
    {
        "text": "Property appraisal must be dated within 120 days of closing",
        "category": "appraisal",
        "criticality": "should-have",
        "confidenceThreshold": 0.75,
    },
]


class TestBaselineCRUDLifecycle:
    """Full 10-step baseline lifecycle test."""

    def test_full_lifecycle(self, api):
        """Create -> add reqs -> verify -> update -> delete -> publish -> archive."""

        # ── Step 1: Create draft baseline ──────────────────────────────────
        create_resp = api.post("/baselines", json={
            "name": f"CRUD Lifecycle Test {uuid.uuid4().hex[:8]}",
            "description": "Integration test — full CRUD lifecycle",
        })
        assert create_resp.status_code == 200, (
            f"Create baseline failed: {create_resp.status_code} {create_resp.text}"
        )
        baseline = create_resp.json()
        baseline_id = baseline["baselineId"]
        assert baseline["status"] == "draft"
        assert baseline["version"] == 0
        assert baseline["requirements"] == []

        try:
            # ── Step 2: Add 3 requirements ─────────────────────────────────
            req_ids = []
            for req in REQUIREMENTS:
                resp = api.post(
                    f"/baselines/{baseline_id}/requirements", json=req
                )
                assert resp.status_code == 200, (
                    f"Add requirement failed: {resp.status_code} {resp.text}"
                )
                data = resp.json()
                assert "requirement" in data
                req_ids.append(data["requirement"]["requirementId"])

            assert len(req_ids) == 3, f"Expected 3 requirement IDs, got {len(req_ids)}"

            # ── Step 3: Verify 3 requirements stored ───────────────────────
            get_resp = api.get(f"/baselines/{baseline_id}")
            assert get_resp.status_code == 200
            bl_data = get_resp.json()["baseline"]
            assert len(bl_data["requirements"]) == 3, (
                f"Expected 3 requirements, got {len(bl_data['requirements'])}"
            )

            # ── Step 4: Update criticality of first requirement ────────────
            update_resp = api.put(
                f"/baselines/{baseline_id}/requirements/{req_ids[0]}",
                json={"criticality": "nice-to-have"},
            )
            assert update_resp.status_code == 200
            assert update_resp.json().get("updated") is True

            # Verify the update persisted
            get_resp = api.get(f"/baselines/{baseline_id}")
            reqs = get_resp.json()["baseline"]["requirements"]
            updated_req = next(
                r for r in reqs if r["requirementId"] == req_ids[0]
            )
            assert updated_req["criticality"] == "nice-to-have"

            # ── Step 5: Delete second requirement ──────────────────────────
            del_resp = api.delete(
                f"/baselines/{baseline_id}/requirements/{req_ids[1]}"
            )
            assert del_resp.status_code == 200
            assert del_resp.json().get("deleted") is True

            # ── Step 6: Verify 2 requirements remain ──────────────────────
            get_resp = api.get(f"/baselines/{baseline_id}")
            reqs = get_resp.json()["baseline"]["requirements"]
            assert len(reqs) == 2, (
                f"Expected 2 requirements after delete, got {len(reqs)}"
            )
            remaining_ids = {r["requirementId"] for r in reqs}
            assert req_ids[1] not in remaining_ids, (
                "Deleted requirement still present"
            )
            assert req_ids[0] in remaining_ids
            assert req_ids[2] in remaining_ids

            # ── Step 7: Publish baseline ───────────────────────────────────
            pub_resp = api.post(f"/baselines/{baseline_id}/publish")
            assert pub_resp.status_code == 200
            pub_data = pub_resp.json()
            assert pub_data["status"] == "published"
            assert pub_data["version"] >= 1

            first_version = pub_data["version"]

            # ── Step 8: Double-publish — should succeed with version bump ──
            pub2_resp = api.post(f"/baselines/{baseline_id}/publish")
            assert pub2_resp.status_code == 200
            pub2_data = pub2_resp.json()
            assert pub2_data["status"] == "published"
            # Version should increment on each publish
            assert pub2_data["version"] == first_version + 1, (
                f"Expected version {first_version + 1}, "
                f"got {pub2_data['version']}"
            )

            # ── Step 9: Archive baseline ───────────────────────────────────
            arch_resp = api.put(
                f"/baselines/{baseline_id}",
                json={"status": "archived"},
            )
            # The API update_baseline only handles name/description/pluginIds.
            # Use the DELETE endpoint which calls archive_baseline.
            arch_resp = api.delete(f"/baselines/{baseline_id}")
            assert arch_resp.status_code == 200
            arch_data = arch_resp.json()
            assert arch_data["status"] == "archived"

            # ── Step 10: Verify archived baseline not in published list ────
            list_resp = api.get("/baselines?status=published")
            assert list_resp.status_code == 200
            published_ids = {
                b["baselineId"]
                for b in list_resp.json().get("baselines", [])
            }
            assert baseline_id not in published_ids, (
                "Archived baseline still appears in published list"
            )

        finally:
            # Cleanup: attempt archive regardless of test outcome
            try:
                api.delete(f"/baselines/{baseline_id}")
            except Exception:
                pass
