from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MCP Server Settings
    mcp_port: int = Field(default=8001, alias="AZATHOTH_MCP_PORT")
    
    # A2A Agent Settings
    agent_port: int = Field(default=8002, alias="AZATHOTH_AGENT_PORT")
    
    # Paths
    config_dir: Path = Field(
        default=Path.home() / ".config" / "azathoth",
        alias="AZATHOTH_CONFIG_DIR"
    )
    
    @property
    def directives_dir(self) -> Path:
        return self.config_dir / "directives"
    
    @property
    def reports_dir(self) -> Path:
        return self.config_dir / "reports"

    # Defaults
    default_ingest_format: str = "xml"
    token_model: str = "cl100k_base"
    
    # Environment & Config File
    model_config = SettingsConfigDict(
        env_prefix="AZATHOTH_",
        toml_file=Path.home() / ".config" / "azathoth" / "config.toml",
        extra="ignore"
    )

# Singleton instance
config = Settings()
