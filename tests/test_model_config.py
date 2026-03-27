"""Model configuration tests."""

from __future__ import annotations

from agents.thinker.agent import ThinkerAgent
from config.settings import settings


def test_model_defaults_match_selected_stack():
    assert settings.default_model == "openai/gpt-5.4"
    assert settings.planning_model == "anthropic/claude-sonnet-4.6"
    assert settings.thinking_model == "qwen/qwen3-max-thinking"


def test_thinker_uses_configured_thinking_model():
    thinker = ThinkerAgent()
    assert thinker.model == settings.thinking_model
