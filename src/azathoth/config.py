"""azathoth.config — application settings (pydantic-settings).

Provider selection (Phase 3+):
  - ``Settings.llm_provider``   single-provider override (takes precedence)
  - ``Settings.llm_providers``  ordered fallback chain — accepted as JSON list
                                 OR comma-separated string from env var
  - ``Settings.llm_chain_timeout`` / ``llm_per_provider_timeout``  wall-clock
                                 budgets enforced by the resolver
  - ``Settings.ollama_*``       Ollama daemon config (Phase 4)

``check_preview_model`` is a startup check, not a field validator — see
§5.9 of plan3.md. A validator on the module-scope ``config`` singleton would
fire on every ``import azathoth`` (including test collection and every MCP
server start). The right event is "someone is about to run something", so
each entry point (CLI root callback, every MCP ``run()``) calls it once.
"""

import json
import os
import warnings
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

_CONFIG_DIR = Path.home() / ".config" / "azathoth"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"

# Fields whose env-var values need pre-processing before pydantic-settings'
# decode_complex_value (json.loads) runs.
_LIST_FIELDS_ENV_KEYS = {"AZATHOTH_LLM_PROVIDERS"}


def _unquote(value: str) -> str:
    """Strip whitespace and a single layer of matched surrounding quotes.

    Defends against naive shell-based .env loaders that don't follow the
    dotenv spec (e.g. some nushell helpers that do `export KEY=VALUE` verbatim).
    """
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1]
    return v


def _resolve_api_key() -> SecretStr:
    """Check AZATHOTH_GEMINI_API_KEY first, then fall back to GEMINI_API_KEY."""
    raw = os.environ.get("AZATHOTH_GEMINI_API_KEY") or os.environ.get(
        "GEMINI_API_KEY", ""
    )
    return SecretStr(_unquote(raw))


def _coerce_list_env(raw: str) -> list[str]:
    """Parse a list from either a JSON array or a comma-separated string."""
    stripped = raw.strip()
    if stripped.startswith("["):
        return [str(item) for item in json.loads(stripped)]
    return [item.strip() for item in stripped.split(",") if item.strip()]


class _ListAwareEnvSource(EnvSettingsSource):
    """Custom env source that pre-normalises list fields to JSON before pydantic
    tries to json.loads them.  This makes both ``'a,b'`` and ``'["a","b"]'``
    forms work transparently."""

    def prepare_field_value(
        self,
        field_name: str,
        field: Any,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        env_key = f"AZATHOTH_{field_name.upper()}"
        if env_key in _LIST_FIELDS_ENV_KEYS and isinstance(value, str):
            coerced = _coerce_list_env(value)
            # Re-encode as JSON so the parent's json.loads path succeeds
            value = json.dumps(coerced)
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    # ── LLM provider selection ────────────────────────────────────────────
    #: Single-provider override for CLI/test use; takes precedence over
    #: ``llm_providers`` when set.
    llm_provider: str | None = Field(default=None)

    #: Ordered fallback chain (Phase 6).  The resolver tries each in order,
    #: falling through on ``ProviderUnavailable``.
    #:
    #: Set via AZATHOTH_LLM_PROVIDERS as a JSON list or comma-separated string:
    #:   AZATHOTH_LLM_PROVIDERS='["gemini","ollama"]'
    #:   AZATHOTH_LLM_PROVIDERS='gemini,ollama'
    llm_providers: list[str] = Field(default_factory=lambda: ["gemini", "ollama"])

    #: Total wall-clock budget per generate() call across the entire chain.
    #: Enforced via asyncio.timeout at the resolver level.
    llm_chain_timeout: float = Field(default=120.0)

    #: Wall-clock budget per single provider in the chain.
    llm_per_provider_timeout: float = Field(default=30.0)

    # ── Gemini ────────────────────────────────────────────────────────────
    gemini_api_key: SecretStr = Field(default_factory=_resolve_api_key)
    gemini_model: str = "gemini-3.6-flash"

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
            _ListAwareEnvSource(settings_cls),  # replaces default env_settings
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
        """User directive override directory. Does NOT create it on access —
        a property that mutates the filesystem on read is a trap. Directory
        creation is an explicit step; see ``ensure_dirs``."""
        return self.config_dir / "directives"

    @property
    def reports_dir(self) -> Path:
        return self.default_output_dir

    def ensure_dirs(self) -> None:
        """Create every directory this config points at. Call once at
        startup, not on every property read."""
        self.directives_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


# Singleton
config = Settings()

_PREVIEW_TAGS = ("preview", "experimental", "exp")


def get_config() -> Settings:
    return config


def check_preview_model(settings: Settings | None = None) -> None:
    """Emit a UserWarning if the configured Gemini model looks like a preview
    tag. Called once per invocation from each entry point (CLI root callback,
    every MCP ``run()``) — never at import time. See §5.9 of plan3.md."""
    settings = settings or get_config()
    model = settings.gemini_model.lower()
    if any(tag in model for tag in _PREVIEW_TAGS):
        warnings.warn(
            f"Configured Gemini model '{settings.gemini_model}' contains a "
            "preview/experimental tag. Preview models may be deprecated or "
            "removed without notice. Consider pinning a stable model identifier.",
            UserWarning,
            stacklevel=2,
        )
