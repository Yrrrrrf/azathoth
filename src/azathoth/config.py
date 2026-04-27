"""azathoth.config — application settings (pydantic-settings).

Nested structure (Phase 3+):
  - ``Settings.gemini_*``  flat fields kept for backward compat (emit DeprecationWarning)
  - ``Settings.llm_provider``   single-provider override
  - ``Settings.llm_providers``  ordered fallback chain (Phase 6)
  - ``Settings.ollama_*``       Ollama daemon config (Phase 4)
"""

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
    key = os.environ.get("AZATHOTH_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    return SecretStr(key)


class Settings(BaseSettings):
    # ── LLM provider selection ────────────────────────────────────────────
    #: Single-provider override for CLI/test use; takes precedence over
    #: ``llm_providers`` when set.
    llm_provider: str | None = Field(default=None)

    #: Ordered fallback chain (Phase 6).  The resolver tries each in order,
    #: falling through on ``ProviderUnavailable``.
    llm_providers: list[str] = Field(default_factory=lambda: ["gemini", "ollama"])

    # ── Gemini ────────────────────────────────────────────────────────────
    gemini_api_key: SecretStr = Field(default_factory=_resolve_api_key)
    gemini_model: str = "gemini-3.1-flash-lite-preview"

    # ── Ollama (Phase 4) ──────────────────────────────────────────────────
    ollama_host: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="gemma4:e4b")
    ollama_num_ctx: int = Field(default=32768)
    ollama_request_timeout: float = Field(default=120.0)

    # ── MCP / A2A ─────────────────────────────────────────────────────────
    mcp_port: int = Field(default=8001)
    agent_port: int = Field(default=8002)

    # ── Paths ─────────────────────────────────────────────────────────────
    config_dir: Path = Field(default=_CONFIG_DIR)

    # ── Misc ──────────────────────────────────────────────────────────────
    default_ingest_format: str = "txt"
    token_model: str = "cl100k_base"
    default_output_dir: Path = Field(default=Path.home() / "Downloads")

    model_config = SettingsConfigDict(
        env_prefix="AZATHOTH_",
        extra="ignore",
    )

    @field_validator("gemini_model")
    @classmethod
    def warn_on_preview_model(cls, v: str) -> str:
        """Emit a UserWarning when the configured model name looks like a preview tag."""
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
    def active_providers(self) -> list[str]:
        """Return the effective ordered provider list for the resolver."""
        if self.llm_provider is not None:
            return [self.llm_provider]
        return self.llm_providers

    @property
    def directives_dir(self) -> Path:
        path = self.config_dir / "directives"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def reports_dir(self) -> Path:
        return self.default_output_dir


# Singleton
config = Settings()
