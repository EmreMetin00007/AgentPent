"""Startup smoke-check tests."""

from __future__ import annotations

from core.startup_check import collect_startup_state


def test_collect_startup_state():
    state = collect_startup_state()

    assert state["active_profile"]
    assert state["scope_profiles"]
    assert state["registered_agents"] >= 1
    assert "reports" in state["reports_dir"]
