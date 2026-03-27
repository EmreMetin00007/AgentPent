"""AgentPent global settings via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Centralized, env-driven configuration."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="AGENTPENT_",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = Field(default="", description="OpenAI-compatible API key")
    openai_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for the OpenAI-compatible API",
    )
    default_model: str = Field(
        default="openai/gpt-5.4",
        description="Default model for agent calls",
    )
    planning_model: str = Field(
        default="anthropic/claude-sonnet-4.6",
        description="Model used for commander / planning tasks",
    )
    thinking_model: str = Field(
        default="qwen/qwen3-max-thinking",
        description="Model used for deep reasoning / thinker tasks",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)

    # Database
    db_path: str = Field(
        default=str(_PROJECT_ROOT / "data" / "agentpent.db"),
        description="SQLite database path",
    )

    # Scope and safety
    scopes_file: str = Field(
        default=str(_PROJECT_ROOT / "config" / "scopes.yaml"),
        description="YAML file defining allowed target scopes",
    )
    require_scope: bool = Field(
        default=True,
        description="Enforce scope checking on every tool call",
    )
    max_concurrent_tools: int = Field(default=5, ge=1)
    rate_limit_rps: float = Field(
        default=10.0,
        description="Max requests-per-second to any single target",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_dir: str = Field(
        default=str(_PROJECT_ROOT / "logs"),
        description="Directory for audit / debug logs",
    )

    # Reports
    reports_dir: str = Field(
        default=str(_PROJECT_ROOT / "reports" / "output"),
        description="Directory for generated reports",
    )


settings = Settings()
