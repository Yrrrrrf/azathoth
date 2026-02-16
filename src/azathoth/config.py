from pathlib import Path
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

_CONFIG_DIR = Path.home() / ".config" / "azathoth"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"


class Settings(BaseSettings):
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
