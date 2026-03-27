"""Model configuration tests."""

from __future__ import annotations

from pathlib import Path

from agents.thinker.agent import ThinkerAgent
from config.settings import Settings, settings


def test_model_defaults_match_selected_stack():
    assert settings.default_model == "openai/gpt-5.4"
    assert settings.planning_model == "anthropic/claude-sonnet-4.6"
    assert settings.thinking_model == "qwen/qwen3-max-thinking"


def test_thinker_uses_configured_thinking_model():
    thinker = ThinkerAgent()
    assert thinker.model == settings.thinking_model


def test_blank_env_values_fall_back_to_defaults(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "AGENTPENT_OPENAI_API_KEY=",
                "AGENTPENT_OPENAI_BASE_URL=",
                "AGENTPENT_DEFAULT_MODEL=",
                "AGENTPENT_PLANNING_MODEL=",
                "AGENTPENT_THINKING_MODEL=",
                "AGENTPENT_TEMPERATURE=",
                "AGENTPENT_MAX_TOKENS=",
                "AGENTPENT_REQUIRE_SCOPE=",
                "AGENTPENT_LOG_LEVEL=",
                "",
            ]
        ),
        encoding="utf-8",
    )

    loaded = Settings(_env_file=str(env_file))

    assert loaded.openai_api_key == ""
    assert loaded.openai_base_url == "https://openrouter.ai/api/v1"
    assert loaded.default_model == "openai/gpt-5.4"
    assert loaded.planning_model == "anthropic/claude-sonnet-4.6"
    assert loaded.thinking_model == "qwen/qwen3-max-thinking"
    assert loaded.temperature == 0.2
    assert loaded.max_tokens == 4096
    assert loaded.require_scope is True
    assert loaded.log_level == "INFO"
