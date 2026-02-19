"""Tests for plugin registry and plugin config compliance."""

import sys
import os
import pytest

# Add plugin layer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'layers', 'plugins', 'python'))

from document_plugins.registry import (
    get_plugin,
    get_all_plugins,
    get_plugin_ids,
    get_classification_hints,
    get_plugin_for_document_type,
)
from document_plugins.contract import DocumentPluginConfig


class TestPluginDiscovery:
    """Test that the registry discovers all expected plugins."""

    def test_discover_all_plugins(self):
        plugins = get_all_plugins()
        assert len(plugins) >= 4
        assert "loan_package" in plugins
        assert "credit_agreement" in plugins
        assert "loan_agreement" in plugins
        assert "bsa_profile" in plugins

    def test_get_plugin_ids(self):
        ids = get_plugin_ids()
        assert isinstance(ids, list)
        assert set(ids) >= {"loan_package", "credit_agreement", "loan_agreement", "bsa_profile"}

    def test_get_plugin_by_id(self):
        for pid in ["loan_package", "credit_agreement", "loan_agreement", "bsa_profile"]:
            plugin = get_plugin(pid)
            assert plugin["plugin_id"] == pid
            assert plugin["name"]

    def test_get_nonexistent_plugin_raises(self):
        with pytest.raises(KeyError):
            get_plugin("nonexistent_type")

    def test_get_classification_hints(self):
        hints = get_classification_hints()
        assert isinstance(hints, dict)
        assert len(hints) >= 4
        for pid, config in hints.items():
            assert "keywords" in config
            assert isinstance(config["keywords"], list)
            assert len(config["keywords"]) > 0


class TestPluginContractCompliance:
    """Test that every plugin has the required keys from DocumentPluginConfig."""

    REQUIRED_TOP_LEVEL_KEYS = [
        "plugin_id", "plugin_version", "name", "description",
        "classification", "sections", "normalization", "output_schema",
        "pii_paths", "cost_budget",
    ]

    @pytest.fixture(params=["loan_package", "credit_agreement", "loan_agreement", "bsa_profile"])
    def plugin(self, request):
        return get_plugin(request.param)

    def test_has_required_keys(self, plugin):
        for key in self.REQUIRED_TOP_LEVEL_KEYS:
            assert key in plugin, f"Plugin '{plugin['plugin_id']}' missing key: {key}"

    def test_classification_has_keywords(self, plugin):
        cls = plugin["classification"]
        assert "keywords" in cls
        assert len(cls["keywords"]) >= 3, f"Plugin '{plugin['plugin_id']}' has too few keywords"

    def test_sections_are_dict(self, plugin):
        assert isinstance(plugin["sections"], dict)
        assert len(plugin["sections"]) >= 1

    def test_each_section_has_textract_features(self, plugin):
        for section_id, section in plugin["sections"].items():
            assert "textract_features" in section, (
                f"Plugin '{plugin['plugin_id']}' section '{section_id}' missing textract_features"
            )
            assert isinstance(section["textract_features"], list)

    def test_normalization_has_prompt_template(self, plugin):
        norm = plugin["normalization"]
        assert "prompt_template" in norm
        assert "llm_model" in norm

    def test_output_schema_is_dict(self, plugin):
        schema = plugin["output_schema"]
        assert isinstance(schema, dict)
        assert "type" in schema
        assert "properties" in schema

    def test_pii_paths_is_list(self, plugin):
        assert isinstance(plugin["pii_paths"], list)

    def test_cost_budget_has_max(self, plugin):
        budget = plugin["cost_budget"]
        assert "max_cost_usd" in budget
        assert budget["max_cost_usd"] > 0


class TestPluginSpecificFeatures:
    """Test plugin-specific features and distinguishing characteristics."""

    def test_loan_agreement_requires_signatures(self):
        la = get_plugin("loan_agreement")
        assert la["requires_signatures"] is True

    def test_credit_agreement_does_not_require_signatures(self):
        ca = get_plugin("credit_agreement")
        assert ca["requires_signatures"] is False

    def test_bsa_profile_has_pii_paths(self):
        bsa = get_plugin("bsa_profile")
        assert len(bsa["pii_paths"]) >= 3
        pii_types = {p["pii_type"] for p in bsa["pii_paths"]}
        assert "ssn" in pii_types
        assert "dob" in pii_types

    def test_loan_agreement_has_extracted_codes_schema(self):
        la = get_plugin("loan_agreement")
        la_schema = la["output_schema"]["properties"]["loanAgreement"]["properties"]
        assert "_extractedCodes" in la_schema
        codes = la_schema["_extractedCodes"]["properties"]
        assert "instrumentType" in codes
        assert "billingFrequency" in codes
        assert "currency" in codes

    def test_credit_agreement_has_seven_sections(self):
        ca = get_plugin("credit_agreement")
        assert len(ca["sections"]) == 7

    def test_loan_agreement_has_eight_sections(self):
        la = get_plugin("loan_agreement")
        assert len(la["sections"]) == 8

    def test_bsa_profile_targets_all_pages(self):
        bsa = get_plugin("bsa_profile")
        assert bsa["classification"].get("target_all_pages") is True

    def test_loan_package_has_section_names(self):
        lp = get_plugin("loan_package")
        cls = lp["classification"]
        assert "section_names" in cls
        assert "promissory_note" in cls["section_names"]

    def test_legacy_section_map(self):
        """Test backward-compatible document type lookups."""
        for legacy_type in ["LOAN_PACKAGE", "CREDIT_AGREEMENT", "LOAN_AGREEMENT"]:
            plugin = get_plugin_for_document_type(legacy_type)
            assert plugin is not None, f"No plugin found for legacy type '{legacy_type}'"

    def test_prompt_template_files_exist(self):
        """Verify each plugin's prompt template file exists on disk."""
        prompts_dir = os.path.join(
            os.path.dirname(__file__), '..', 'lambda', 'layers', 'plugins',
            'python', 'document_plugins', 'prompts'
        )
        for pid in get_plugin_ids():
            plugin = get_plugin(pid)
            template = plugin["normalization"]["prompt_template"]
            path = os.path.join(prompts_dir, f"{template}.txt")
            assert os.path.exists(path), (
                f"Plugin '{pid}' references prompt template '{template}.txt' but file not found at {path}"
            )
