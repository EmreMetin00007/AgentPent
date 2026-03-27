"""AgentPent — Recon Agent Unit Tests."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.recon.agent import ReconAgent
from core.mission import AttackPhase, Finding, Mission, Severity


# ── Tests ────────────────────────────────────────────────


class TestReconAgent:

    def setup_method(self):
        self.agent = ReconAgent()

    def test_metadata(self):
        assert self.agent.name == "recon"
        assert self.agent.phase == AttackPhase.RECONNAISSANCE

    def test_tools_registered(self):
        tools = self.agent.available_tools
        assert "nmap" in tools
        assert "subfinder" in tools
        assert "whois" in tools
        assert "httpx" in tools

    def test_is_ip(self):
        assert ReconAgent._is_ip("10.10.10.5") is True
        assert ReconAgent._is_ip("192.168.1.1") is True
        assert ReconAgent._is_ip("example.com") is False
        assert ReconAgent._is_ip("256.1.1.1") is False

    def test_extract_json_from_codeblock(self):
        text = 'Some text\n```json\n{"findings": [{"title": "Test"}]}\n```\nMore text'
        result = ReconAgent._extract_json(text)
        assert result is not None
        assert result["findings"][0]["title"] == "Test"

    def test_extract_json_direct(self):
        text = '{"findings": [{"title": "Direct"}]}'
        result = ReconAgent._extract_json(text)
        assert result is not None
        assert result["findings"][0]["title"] == "Direct"

    def test_extract_json_invalid(self):
        result = ReconAgent._extract_json("not json at all")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_response_with_findings(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "SSH Port Açık",
                    "severity": "INFO",
                    "target": "10.10.10.5",
                    "port": 22,
                    "service": "ssh",
                    "description": "SSH portu açık",
                    "evidence": "nmap çıktısı",
                },
                {
                    "title": "Apache Tespit Edildi",
                    "severity": "LOW",
                    "target": "10.10.10.5",
                    "port": 80,
                    "service": "http",
                    "description": "Apache 2.4.54 çalışıyor",
                },
            ],
            "tool_calls": [
                {"tool": "nmap", "result_summary": "3 açık port bulundu"}
            ],
            "next_recommendations": ["Detaylı port taraması"],
        })

        result = await self.agent.process_response(response, mission, memory)

        assert result.success
        assert len(result.findings) == 2
        assert result.findings[0].title == "SSH Port Açık"
        assert result.findings[0].severity == Severity.INFO
        assert result.findings[0].port == 22
        assert result.findings[1].severity == Severity.LOW
        assert result.tool_outputs["nmap"] == "3 açık port bulundu"
        assert "Detaylı port taraması" in result.next_actions

    @pytest.mark.asyncio
    async def test_process_response_empty(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        result = await self.agent.process_response(
            "Bu bir düz metin yanıttır", mission, memory
        )
        assert result.success
        assert len(result.findings) == 0


class TestScannerAgent:

    def setup_method(self):
        from agents.scanner.agent import ScannerAgent
        self.agent = ScannerAgent()

    def test_metadata(self):
        assert self.agent.name == "scanner"
        assert self.agent.phase == AttackPhase.SCANNING

    def test_tools_registered(self):
        tools = self.agent.available_tools
        assert "nmap" in tools
        assert "nuclei" in tools

    @pytest.mark.asyncio
    async def test_process_response_with_vulns(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "Apache Path Traversal",
                    "severity": "CRITICAL",
                    "target": "10.10.10.5",
                    "port": 80,
                    "service": "http",
                    "cve_ids": ["CVE-2021-41773"],
                    "description": "Path traversal zafiyet",
                    "evidence": "nuclei çıktısı",
                }
            ],
            "open_ports_summary": {"22": "ssh", "80": "http"},
            "vulnerabilities_found": 1,
            "next_recommendations": ["Exploit dene"],
        })

        result = await self.agent.process_response(response, mission, memory)

        assert result.success
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL
        assert "CVE-2021-41773" in result.findings[0].cve_ids
