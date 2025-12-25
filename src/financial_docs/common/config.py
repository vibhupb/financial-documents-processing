"""Configuration management for Financial Documents Processing."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # S3 Configuration
    bucket_name: str = field(default_factory=lambda: os.environ.get("BUCKET_NAME", ""))

    # DynamoDB Configuration
    table_name: str = field(default_factory=lambda: os.environ.get("TABLE_NAME", "financial-documents"))

    # Bedrock Configuration
    router_model_id: str = field(
        default_factory=lambda: os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-3-haiku-20240307-v1:0"
        )
    )
    normalizer_model_id: str = field(
        default_factory=lambda: os.environ.get(
            "NORMALIZER_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0"
        )
    )

    # Step Functions Configuration
    state_machine_arn: str = field(
        default_factory=lambda: os.environ.get("STATE_MACHINE_ARN", "")
    )

    # Processing Configuration
    max_chars_per_page: int = field(
        default_factory=lambda: int(os.environ.get("MAX_CHARS_PER_PAGE", "1000"))
    )
    page_batch_size: int = field(
        default_factory=lambda: int(os.environ.get("PAGE_BATCH_SIZE", "50"))
    )

    # Feature Flags
    enable_audit_trail: bool = field(
        default_factory=lambda: os.environ.get("ENABLE_AUDIT_TRAIL", "true").lower() == "true"
    )

    @classmethod
    def from_env(cls) -> "Settings":
        """Create Settings instance from environment variables."""
        return cls()

    def validate(self) -> None:
        """Validate required settings are present."""
        if not self.bucket_name:
            raise ValueError("BUCKET_NAME environment variable is required")


# Global settings instance (lazy loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
