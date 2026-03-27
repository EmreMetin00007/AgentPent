"""AgentPent — Phase 4 Agent Unit Tests."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.mission import AttackPhase, Finding, Mission, Severity


# ── Post-Exploit Tests ───────────────────────────────────


class TestPostExploitAgent:

    def setup_method(self):
        from agents.post_exploit.agent import PostExploitAgent
        self.agent = PostExploitAgent()

    def test_metadata(self):
        assert self.agent.name == "post_exploit"
        assert self.agent.phase == AttackPhase.POST_EXPLOITATION

    def test_tools_registered(self):
        assert "linpeas" in self.agent.available_tools
        assert "metasploit" in self.agent.available_tools

    @pytest.mark.asyncio
    async def test_process_response_privesc(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "Root erişimi — SUID python3",
                    "severity": "CRITICAL",
                    "target": "10.10.10.5",
                    "description": "SUID python3 ile root shell",
                    "evidence": "linpeas çıktısı",
                }
            ],
            "credentials": [
                {"type": "hash", "user": "admin", "value": "$6$abc"}
            ],
            "privesc_vectors": ["SUID python3", "writable /etc/cron.d"],
            "next_recommendations": ["Lateral movement"],
        })

        result = await self.agent.process_response(response, mission, memory)
        assert result.success
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL
        assert "admin" in result.tool_outputs["credentials"]


# ── Network Agent Tests ──────────────────────────────────


class TestNetworkAgent:

    def setup_method(self):
        from agents.network.agent import NetworkAgent
        self.agent = NetworkAgent()

    def test_metadata(self):
        assert self.agent.name == "network"
        assert self.agent.phase == AttackPhase.POST_EXPLOITATION

    def test_tools_registered(self):
        assert "responder" in self.agent.available_tools
        assert "chisel" in self.agent.available_tools
        assert "nmap" in self.agent.available_tools

    @pytest.mark.asyncio
    async def test_process_response_hash(self):
        mission = Mission(name="Test", target_scope=["10.10.10.0/24"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "NTLMv2 hash yakalandı",
                    "severity": "HIGH",
                    "target": "10.10.10.5",
                    "description": "LLMNR poisoning ile hash",
                }
            ],
            "internal_hosts": ["10.10.10.1", "10.10.10.5"],
            "tunnels": [{"local": "127.0.0.1:8888", "remote": "10.10.10.5:80"}],
        })

        result = await self.agent.process_response(response, mission, memory)
        assert result.success
        assert len(result.findings) == 1


# ── Evasion Agent Tests ──────────────────────────────────


class TestEvasionAgent:

    def setup_method(self):
        from agents.evasion.agent import EvasionAgent
        self.agent = EvasionAgent()

    def test_metadata(self):
        assert self.agent.name == "evasion"
        assert self.agent.phase == AttackPhase.EXPLOITATION

    def test_no_tools(self):
        # LLM-driven agent, harici araç yok
        assert len(self.agent.available_tools) == 0

    @pytest.mark.asyncio
    async def test_process_evasion_techniques(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [],
            "evasion_techniques": [
                {
                    "name": "AMSI Bypass",
                    "type": "amsi_bypass",
                    "language": "powershell",
                    "code": "[Ref].Assembly...",
                }
            ],
            "encoded_payloads": [
                {"original": "calc.exe", "encoding": "xor", "output": "encoded"}
            ],
        })

        result = await self.agent.process_response(response, mission, memory)
        assert result.success
        assert "AMSI Bypass" in result.tool_outputs["evasion_techniques"]


# ── Social Eng Agent Tests ───────────────────────────────


class TestSocialEngAgent:

    def setup_method(self):
        from agents.social_eng.agent import SocialEngAgent
        self.agent = SocialEngAgent()

    def test_metadata(self):
        assert self.agent.name == "social_eng"
        assert self.agent.phase == AttackPhase.RECONNAISSANCE

    @pytest.mark.asyncio
    async def test_process_templates(self):
        mission = Mission(name="Test", target_scope=["example.com"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [],
            "templates": [
                {
                    "type": "phishing_email",
                    "subject": "Şifre Sıfırlama",
                    "body": "IT admin burada...",
                    "success_probability": "high",
                }
            ],
        })

        result = await self.agent.process_response(response, mission, memory)
        assert result.success
        assert "phishing_email" in result.tool_outputs["templates"]


# ── Persist Agent Tests ──────────────────────────────────


class TestPersistAgent:

    def setup_method(self):
        from agents.persist.agent import PersistAgent
        self.agent = PersistAgent()

    def test_metadata(self):
        assert self.agent.name == "persist"
        assert self.agent.phase == AttackPhase.POST_EXPLOITATION

    def test_tools_registered(self):
        assert "metasploit" in self.agent.available_tools

    @pytest.mark.asyncio
    async def test_process_mechanisms(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "findings": [
                {
                    "title": "Persistence kuruldu — cron",
                    "severity": "CRITICAL",
                    "target": "10.10.10.5",
                    "description": "Cron job reverse shell",
                }
            ],
            "mechanisms": [
                {
                    "type": "cron",
                    "platform": "linux",
                    "persistence_score": 8,
                }
            ],
        })

        result = await self.agent.process_response(response, mission, memory)
        assert result.success
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL
        assert "cron" in result.tool_outputs["mechanisms"]


# ── LinPEAS Tool Tests ───────────────────────────────────


class TestLinPEASTool:

    def setup_method(self):
        from tools.linpeas_tool import LinPEASTool
        self.tool = LinPEASTool()

    def test_metadata(self):
        assert self.tool.name == "linpeas"

    def test_parse_suid(self):
        output = """
═══════════════════════════════════════════
╔══════════╣ SUID - Check easy privesc
/usr/bin/python3
/usr/bin/pkexec
/usr/bin/sudo
═══════════════════════════════════════════
╔══════════╣ CRON JOBS
* * * * * root /opt/backup.sh
═══════════════════════════════════════════
╔══════════╣ WRITABLE directories
/tmp
/var/tmp
"""
        result = self.tool.parse_output(output)
        assert "/usr/bin/python3" in result["suid_binaries"]
        assert "/usr/bin/pkexec" in result["suid_binaries"]
        assert len(result["cron_jobs"]) >= 1
        assert "/tmp" in result["writable_dirs"]
