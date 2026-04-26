from __future__ import annotations

import os
import warnings
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

_CONFIG_DIR = Path.home() / ".config" / "azathoth"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"

_PREVIEW_TAGS = ("preview", "experimental", "exp")


def _resolve_api_key() -> SecretStr:
    """Check AZATHOTH_GEMINI_API_KEY first, then fall back to GEMINI_API_KEY."""
    key = os.environ.get("AZATHOTH_GEMINI_API_KEY") or os.environ.get(
        "GEMINI_API_KEY", ""
    )
    return SecretStr(key)


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────
    gemini_api_key: SecretStr = Field(default_factory=_resolve_api_key)
    gemini_model: str = "gemini-3.1-flash-lite-preview"

    # MCP Server
    mcp_port: int = Field(default=8001)

    # A2A Agent
    agent_port: int = Field(default=8002)

    # Paths
    config_dir: Path = Field(default=_CONFIG_DIR)

    # Defaults
    default_ingest_format: str = "txt"
    token_model: str = "cl100k_base"

    # ERGONOMICS: Directly to Downloads, no subfolder
    default_output_dir: Path = Field(default=Path.home() / "Downloads")

    model_config = SettingsConfigDict(
        env_prefix="AZATHOTH_",
        extra="ignore",
    )

    @field_validator("gemini_model")
    @classmethod
    def warn_on_preview_model(cls, v: str) -> str:
        """Emit a UserWarning when the configured model name looks like a preview/experimental tag."""
        if any(tag in v.lower() for tag in _PREVIEW_TAGS):
            warnings.warn(
                f"Configured Gemini model '{v}' contains a preview/experimental tag. "
                "Preview models may be deprecated or removed without notice. "
                "Consider pinning a stable model identifier.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, toml_file=_CONFIG_FILE),
        )

    @property
    def directives_dir(self) -> Path:
        path = self.config_dir / "directives"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def reports_dir(self) -> Path:
        # Just use Downloads
        return self.default_output_dir


# Singleton
config = Settings()
