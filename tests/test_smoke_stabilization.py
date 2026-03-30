"""Smoke-test stabilization regression tests."""

from __future__ import annotations

from pathlib import Path

from core.utils import TOOL_PARAM_SCHEMAS


ROOT = Path(__file__).resolve().parents[1]


def _read_prompt(*parts: str) -> str:
    return (ROOT / Path(*parts)).read_text(encoding="utf-8")


def test_recon_prompt_uses_tool_contract_without_fake_result_summary():
    prompt = _read_prompt("agents", "recon", "recon.md")

    assert "65.61.137.117" in prompt
    assert "3128" in prompt
    assert "tool_calls" in prompt
    assert "result_summary" not in prompt
    assert "Final yanıtta `tool_calls` alanını ekleme" in prompt


def test_osint_prompt_uses_tool_contract_without_fake_result_summary():
    prompt = _read_prompt("agents", "osint", "osint.md")

    assert "65.61.137.117" in prompt
    assert "tool_calls" in prompt
    assert "result_summary" not in prompt
    assert "Final yanıtta `tool_calls` alanını kullanma" in prompt


def test_web_and_commander_prompts_include_proxy_guardrails():
    webapp_prompt = _read_prompt("agents", "webapp", "webapp.md")
    commander_prompt = _read_prompt("agents", "commander", "commander.md")

    assert "Proxy Authentication Required" in webapp_prompt
    assert "3128" in webapp_prompt
    assert "proxy servisi olarak işaretle" in commander_prompt


def test_tool_param_schemas_match_updated_wrappers():
    assert "url" in TOOL_PARAM_SCHEMAS["browser_vision"]
    assert "topic" in TOOL_PARAM_SCHEMAS["rag_store"]
    assert "payload" in TOOL_PARAM_SCHEMAS["rag_store"]
    assert "context" in TOOL_PARAM_SCHEMAS["rag_store"]
    assert "action" in TOOL_PARAM_SCHEMAS["exploit_builder"]
