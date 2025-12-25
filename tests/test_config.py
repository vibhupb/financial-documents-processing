"""Tests for configuration management."""

import os
import pytest
from src.financial_docs.common.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self):
        """Test default configuration values."""
        settings = Settings()

        assert settings.router_model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert settings.normalizer_model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert settings.table_name == "financial-documents"
        assert settings.max_chars_per_page == 1000
        assert settings.page_batch_size == 50
        assert settings.enable_audit_trail is True

    def test_from_env(self, monkeypatch):
        """Test loading settings from environment variables."""
        monkeypatch.setenv("BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("TABLE_NAME", "test-table")
        monkeypatch.setenv("MAX_CHARS_PER_PAGE", "2000")

        settings = Settings.from_env()

        assert settings.bucket_name == "test-bucket"
        assert settings.table_name == "test-table"
        assert settings.max_chars_per_page == 2000

    def test_validate_missing_bucket(self):
        """Test validation fails without bucket name."""
        settings = Settings(bucket_name="")

        with pytest.raises(ValueError, match="BUCKET_NAME"):
            settings.validate()

    def test_validate_success(self):
        """Test validation passes with required settings."""
        settings = Settings(bucket_name="test-bucket")

        # Should not raise
        settings.validate()
