"""AgentPent — Vuln Analyzer & Exploit Agent Unit Tests."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mission import AttackPhase, Finding, Mission, Severity


# ── Vuln Analyzer Tests ─────────────────────────────────


class TestVulnAnalyzerAgent:

    def setup_method(self):
        from agents.vuln_analyzer.agent import VulnAnalyzerAgent
        self.agent = VulnAnalyzerAgent()

    def test_metadata(self):
        assert self.agent.name == "vuln_analyzer"
        assert self.agent.phase == AttackPhase.VULNERABILITY_ANALYSIS

    @pytest.mark.asyncio
    async def test_process_response_with_vulns(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "Apache httpd 2.4.49 — CVE-2021-41773",
                    "severity": "CRITICAL",
                    "target": "10.10.10.5",
                    "port": 80,
                    "service": "Apache httpd 2.4.49",
                    "cve_ids": ["CVE-2021-41773"],
                    "cvss_score": 9.8,
                    "exploitable": True,
                    "remediation": "Apache 2.4.51+ sürümüne güncelle",
                    "description": "Path traversal zafiyeti",
                    "evidence": "NVD API",
                },
                {
                    "title": "OpenSSH 8.9 — CVE-2023-38408",
                    "severity": "HIGH",
                    "target": "10.10.10.5",
                    "port": 22,
                    "service": "OpenSSH 8.9p1",
                    "cve_ids": ["CVE-2023-38408"],
                    "cvss_score": 7.5,
                    "exploitable": False,
                    "description": "PKCS#11 feature allows remote code execution",
                },
            ],
            "risk_summary": {"critical": 1, "high": 1},
            "priority_targets": ["10.10.10.5:80"],
            "next_recommendations": ["CVE-2021-41773 exploit dene"],
        })

        result = await self.agent.process_response(response, mission, memory)

        assert result.success
        assert len(result.findings) == 2
        assert result.findings[0].severity == Severity.CRITICAL
        assert result.findings[0].cvss_score == 9.8
        assert result.findings[0].exploitable is True
        assert "CVE-2021-41773" in result.findings[0].cve_ids
        assert result.findings[1].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_process_response_empty(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        result = await self.agent.process_response(
            "Zafiyet bulunamadı", mission, memory
        )
        assert result.success
        assert len(result.findings) == 0


# ── Exploit Agent Tests ──────────────────────────────────


class TestExploitAgent:

    def setup_method(self):
        from agents.exploit.agent import ExploitAgent
        self.agent = ExploitAgent()

    def test_metadata(self):
        assert self.agent.name == "exploit"
        assert self.agent.phase == AttackPhase.EXPLOITATION

    def test_tools_registered(self):
        assert "metasploit" in self.agent.available_tools

    def test_approval_gate_request(self):
        result = self.agent.request_approval(
            module="exploit/multi/http/apache_normalize_path_rce",
            target="10.10.10.5",
            options={"RPORT": "80"},
        )
        assert result["status"] == "pending"
        assert self.agent.has_pending_approval is True

    def test_approval_gate_approve(self):
        self.agent.request_approval(
            module="exploit/test",
            target="10.10.10.5",
            options={},
        )
        assert self.agent.approve() is True
        assert self.agent.has_pending_approval is False

    def test_approval_gate_reject(self):
        self.agent.request_approval(
            module="exploit/test",
            target="10.10.10.5",
            options={},
        )
        assert self.agent.reject() is True
        assert self.agent.has_pending_approval is False

    def test_no_pending_approval(self):
        assert self.agent.has_pending_approval is False
        assert self.agent.approve() is False

    @pytest.mark.asyncio
    async def test_process_response_with_session(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "Shell elde edildi — 10.10.10.5",
                    "severity": "CRITICAL",
                    "target": "10.10.10.5",
                    "port": 80,
                    "exploit_result": "session_opened",
                    "evidence": "Meterpreter session #1 opened",
                    "description": "CVE-2021-41773 exploit başarılı",
                }
            ],
            "sessions": [
                {
                    "id": 1,
                    "type": "meterpreter",
                    "target": "10.10.10.5:80",
                }
            ],
            "next_recommendations": ["Post-exploitation başlat"],
        })

        result = await self.agent.process_response(response, mission, memory)

        assert result.success
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL
        assert result.findings[0].exploitable is True


# ── WebApp Agent Tests ───────────────────────────────────


class TestWebAppAgent:

    def setup_method(self):
        from agents.webapp.agent import WebAppAgent
        self.agent = WebAppAgent()

    def test_metadata(self):
        assert self.agent.name == "webapp"
        assert self.agent.phase == AttackPhase.VULNERABILITY_ANALYSIS

    def test_tools_registered(self):
        tools = self.agent.available_tools
        assert "sqlmap" in tools
        assert "ffuf" in tools
        assert "xsstrike" in tools
        assert "nikto" in tools

    @pytest.mark.asyncio
    async def test_process_response_sqli(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "SQL Injection — login.php?username",
                    "severity": "CRITICAL",
                    "target": "http://10.10.10.5/login.php",
                    "description": "Boolean-based blind SQLi",
                    "exploitable": True,
                    "remediation": "Parameterized query kullan",
                }
            ],
            "discovered_paths": ["/admin", "/backup", "/.git"],
            "next_recommendations": ["admin brute-force dene"],
        })

        result = await self.agent.process_response(response, mission, memory)

        assert result.success
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL
        assert "/admin" in result.tool_outputs["discovered_paths"]


# ── CVE DB Tests ─────────────────────────────────────────


class TestCVEEntry:

    def test_severity_critical(self):
        from knowledge.cve_db import CVEEntry
        entry = CVEEntry(cve_id="CVE-2021-44228", cvss_v3_score=10.0)
        assert entry.severity == "CRITICAL"

    def test_severity_high(self):
        from knowledge.cve_db import CVEEntry
        entry = CVEEntry(cve_id="CVE-2023-38408", cvss_v3_score=7.5)
        assert entry.severity == "HIGH"

    def test_severity_medium(self):
        from knowledge.cve_db import CVEEntry
        entry = CVEEntry(cve_id="CVE-2023-0001", cvss_v3_score=5.0)
        assert entry.severity == "MEDIUM"

    def test_severity_low(self):
        from knowledge.cve_db import CVEEntry
        entry = CVEEntry(cve_id="CVE-2023-0002", cvss_v3_score=2.0)
        assert entry.severity == "LOW"

    def test_severity_none(self):
        from knowledge.cve_db import CVEEntry
        entry = CVEEntry(cve_id="CVE-2023-0003")
        assert entry.severity == "UNKNOWN"
