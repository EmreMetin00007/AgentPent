"""AgentPent — Orchestrator & ReAct Loop Tests."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.base_agent import AgentResult, BaseAgent
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, MissionStatus, Severity
from core.utils import extract_json_from_llm
from tools.base_tool import ToolResult


# ── extract_json_from_llm Tests ─────────────────────────


class TestExtractJson:
    def test_plain_json(self):
        result = extract_json_from_llm('{"decision": "next_phase"}')
        assert result == {"decision": "next_phase"}

    def test_json_in_code_block(self):
        text = 'Açıklama:\n```json\n{"approved": true, "reason": "OK"}\n```\nDevam.'
        result = extract_json_from_llm(text)
        assert result["approved"] is True

    def test_json_in_plain_code_block(self):
        text = '```\n{"key": "value"}\n```'
        result = extract_json_from_llm(text)
        assert result["key"] == "value"

    def test_json_embedded_in_text(self):
        text = 'Sonuç aşağıda: {"findings": []} devam ediyor.'
        result = extract_json_from_llm(text)
        assert result == {"findings": []}

    def test_empty_input(self):
        assert extract_json_from_llm("") is None
        assert extract_json_from_llm("   ") is None

    def test_invalid_json(self):
        assert extract_json_from_llm("bu json değil") is None

    def test_none_input(self):
        assert extract_json_from_llm(None) is None


# ── Mission Attack Graph Tests ──────────────────────────


class TestMissionAttackGraph:
    def test_add_finding_rebuilds_graph(self):
        mission = Mission(name="Test", target_scope=["10.0.0.1"])
        finding = Finding(
            title="Test Vuln",
            severity=Severity.HIGH,
            target="10.0.0.1",
            port=80,
            service="Apache",
            agent_source="scanner",
            phase=AttackPhase.SCANNING,
        )
        mission.add_finding(finding)
        assert mission.attack_graph is not None
        assert len(mission.attack_graph.nodes) > 0

    def test_graph_from_multiple_findings(self):
        mission = Mission(name="Test", target_scope=["10.0.0.1"])
        for i in range(3):
            mission.add_finding(Finding(
                title=f"Vuln {i}",
                severity=Severity.MEDIUM,
                target="10.0.0.1",
                port=80 + i,
                service=f"svc_{i}",
                agent_source="scanner",
                phase=AttackPhase.SCANNING,
            ))
        assert len(mission.attack_graph.nodes) >= 4  # host + 3 services


# ── Orchestrator Tests ──────────────────────────────────


class TestOrchestrator:
    def test_create_mission(self):
        with patch("core.scope_guard.scope_guard") as mock_sg:
            mock_sg.set_profile = MagicMock()
            from core.orchestrator import Orchestrator
            orch = Orchestrator()
            mission = orch.create_mission("Test", ["10.0.0.1"])
            assert mission.name == "Test"
            assert mission.status == MissionStatus.PLANNING

    def test_registered_agents(self):
        from core.orchestrator import Orchestrator
        orch = Orchestrator()
        agents = orch.registered_agents
        assert isinstance(agents, list)

    @pytest.mark.asyncio
    async def test_run_single_phase_updates_mission_state_and_findings(self):
        from core.orchestrator import Orchestrator

        finding = Finding(
            title="Open proxy detected",
            severity=Severity.INFO,
            target="10.0.0.5",
            port=3128,
            agent_source="scanner",
            phase=AttackPhase.SCANNING,
        )

        orch = Orchestrator()
        mission = Mission(name="Smoke", target_scope=["10.0.0.5"])
        orch._mission = mission
        orch._run_agents = AsyncMock(return_value=[
            AgentResult(agent_name="scanner", findings=[finding]),
        ])

        results = await orch.run_single_phase(AttackPhase.SCANNING, mission)

        assert len(results) == 1
        assert mission.status == MissionStatus.COMPLETED
        assert mission.current_phase == AttackPhase.SCANNING
        assert mission.findings == [finding]
        assert mission.phases_completed == [AttackPhase.SCANNING]


# ── AgentResult Tests ───────────────────────────────────


class TestAgentResult:
    def test_summary_success(self):
        r = AgentResult(agent_name="test", success=True, findings=[])
        assert "✅" in r.summary()

    def test_summary_failure(self):
        r = AgentResult(agent_name="test", success=False, error="fail")
        assert "❌" in r.summary()


# ── Retry Tests ─────────────────────────────────────────


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_failure(self):
        from core.orchestrator import _retry_async

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("flaky error")
            return "success"

        result = await _retry_async(flaky, max_retries=3, label="test")
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        from core.orchestrator import _retry_async

        async def always_fail():
            raise RuntimeError("permanent error")

        with pytest.raises(RuntimeError, match="permanent error"):
            await _retry_async(always_fail, max_retries=2, label="test")


class _DummyRepeatAgent(BaseAgent):
    name = "dummy_repeat"
    description = "repeat guard regression"
    phase = AttackPhase.RECONNAISSANCE

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            raw_response=response,
            findings=[],
            tool_outputs={},
            next_actions=[],
            success=True,
        )


class TestBaseAgentLoop:
    @pytest.mark.asyncio
    async def test_repeated_tool_calls_execute_once_and_exit_early(self, monkeypatch):
        agent = _DummyRepeatAgent()
        fake_tool = AsyncMock()
        fake_tool.execute = AsyncMock(return_value=ToolResult(
            tool_name="nmap",
            stdout="ok",
            success=True,
        ))
        agent.register_tool("nmap", fake_tool)

        mission = Mission(name="Loop", target_scope=["10.10.10.5"])
        memory = ConversationMemory()

        repeated_response = json.dumps({
            "tool_calls": [
                {
                    "tool": "nmap",
                    "params": {
                        "target": "10.10.10.5",
                        "scan_type": "quick",
                    },
                }
            ]
        })
        llm_mock = AsyncMock(side_effect=[
            repeated_response,
            repeated_response,
            repeated_response,
        ])

        monkeypatch.setattr("agents.base_agent.llm.chat_with_fallback", llm_mock)
        monkeypatch.setattr("agents.base_agent.settings.max_react_iterations", 5)

        result = await agent.run("repeat test", mission, memory)

        assert fake_tool.execute.await_count == 1
        assert llm_mock.await_count == 3
        assert result.tool_outputs["nmap_1"] == "ok"
        assert result.tool_outputs["_react_iterations"] == "3"
