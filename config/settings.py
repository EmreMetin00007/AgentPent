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
        env_ignore_empty=True,
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
    offensive_model: str = Field(
        default="nousresearch/hermes-3-llama-3.1-405b",
        description="Uncensored model for exploit/evasion/post-exploit agents",
    )
    fallback_models: str = Field(
        default="nousresearch/hermes-3-llama-3.1-405b,cognitivecomputations/dolphin3.0-r1-mistral-24b",
        description="Comma-separated fallback model chain (tried on refusal)",
    )
    enable_fallback_chain: bool = Field(
        default=True,
        description="Enable automatic model fallback on refusal detection",
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
        default=3.0,
        description="Max requests-per-second to any single target",
    )
    rate_limit_jitter_min: float = Field(
        default=0.1,
        description="Minimum random delay (seconds) between requests",
    )
    rate_limit_jitter_max: float = Field(
        default=0.8,
        description="Maximum random delay (seconds) between requests — IDS evasion",
    )
    max_react_iterations: int = Field(
        default=20,
        ge=1,
        description="Maximum ReAct loop iterations per agent run",
    )
    mission_timeout_seconds: int = Field(
        default=1800,
        description="Maximum total mission runtime in seconds (30 min)",
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
