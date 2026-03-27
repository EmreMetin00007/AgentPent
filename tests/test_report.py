"""AgentPent — Report Generator & Reporter Agent Tests."""

import json
import os
import tempfile

import pytest

from core.mission import AttackPhase, Finding, Mission, Severity
from core.report_generator import ReportData, ReportGenerator


# ── ReportData Tests ─────────────────────────────────────


class TestReportData:

    def _make_mission(self) -> Mission:
        m = Mission(name="Test Mission", target_scope=["10.10.10.5"])
        m.add_finding(Finding(
            title="Critical Vuln", severity=Severity.CRITICAL,
            target="10.10.10.5", port=80, cve_ids=["CVE-2021-41773"],
            cvss_score=9.8, exploitable=True, agent_source="scanner",
            description="Test", phase=AttackPhase.SCANNING,
        ))
        m.add_finding(Finding(
            title="Info Finding", severity=Severity.INFO,
            target="10.10.10.5", port=22, agent_source="recon",
            description="SSH açık", phase=AttackPhase.RECONNAISSANCE,
        ))
        m.add_finding(Finding(
            title="Medium Vuln", severity=Severity.MEDIUM,
            target="10.10.10.5", port=443, agent_source="webapp",
            description="Test", phase=AttackPhase.VULNERABILITY_ANALYSIS,
        ))
        return m

    def test_total_findings(self):
        m = self._make_mission()
        data = ReportData(m)
        assert data.total_findings == 3

    def test_stats(self):
        m = self._make_mission()
        data = ReportData(m)
        assert data.stats["CRITICAL"] == 1
        assert data.stats["INFO"] == 1
        assert data.stats["MEDIUM"] == 1

    def test_overall_risk(self):
        m = self._make_mission()
        data = ReportData(m)
        assert data.overall_risk == "CRITICAL"

    def test_overall_risk_no_critical(self):
        m = Mission(name="Test", target_scope=["10.10.10.5"])
        m.add_finding(Finding(
            title="Low", severity=Severity.LOW, target="10.10.10.5",
            description="test", agent_source="recon",
        ))
        data = ReportData(m)
        assert data.overall_risk == "LOW"

    def test_findings_by_severity(self):
        m = self._make_mission()
        data = ReportData(m)
        groups = data.findings_by_severity
        assert len(groups["CRITICAL"]) == 1
        assert groups["CRITICAL"][0].title == "Critical Vuln"

    def test_findings_by_agent(self):
        m = self._make_mission()
        data = ReportData(m)
        groups = data.findings_by_agent
        assert "scanner" in groups
        assert "recon" in groups

    def test_cve_list(self):
        m = self._make_mission()
        data = ReportData(m)
        assert "CVE-2021-41773" in data.cve_list

    def test_exploitable_findings(self):
        m = self._make_mission()
        data = ReportData(m)
        assert len(data.exploitable_findings) == 1

    def test_to_dict(self):
        m = self._make_mission()
        data = ReportData(m)
        d = data.to_dict()
        assert d["mission"]["name"] == "Test Mission"
        assert d["report"]["total_findings"] == 3
        assert len(d["findings"]) == 3


# ── ReportGenerator Tests ────────────────────────────────


class TestReportGenerator:

    def _make_mission(self) -> Mission:
        m = Mission(name="Test Mission", target_scope=["10.10.10.5"])
        m.add_finding(Finding(
            title="SQL Injection", severity=Severity.CRITICAL,
            target="10.10.10.5", port=80, cve_ids=["CVE-2024-0001"],
            cvss_score=9.1, agent_source="webapp",
            description="Boolean blind SQLi", remediation="Parameterized query",
            phase=AttackPhase.VULNERABILITY_ANALYSIS,
        ))
        m.add_finding(Finding(
            title="Open SSH", severity=Severity.INFO,
            target="10.10.10.5", port=22, agent_source="recon",
            description="SSH port open", phase=AttackPhase.RECONNAISSANCE,
        ))
        return m

    def test_generate_json(self):
        m = self._make_mission()
        gen = ReportGenerator()
        content = gen.generate(m, format="json", executive_summary="Test özet")
        data = json.loads(content)
        assert data["report"]["total_findings"] == 2
        assert data["report"]["executive_summary"] == "Test özet"

    def test_generate_markdown(self):
        m = self._make_mission()
        gen = ReportGenerator()
        content = gen.generate(m, format="markdown")
        assert "# Pentest Raporu" in content
        assert "SQL Injection" in content
        assert "CRITICAL" in content

    def test_generate_html(self):
        m = self._make_mission()
        gen = ReportGenerator()
        content = gen.generate(m, format="html")
        assert "<!DOCTYPE html>" in content
        assert "SQL Injection" in content
        assert "CRITICAL" in content

    def test_generate_to_file(self):
        m = self._make_mission()
        gen = ReportGenerator()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            gen.generate(m, format="json", output_path=path)
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            assert data["report"]["total_findings"] == 2
        finally:
            os.unlink(path)

    def test_empty_mission(self):
        m = Mission(name="Empty", target_scope=["10.10.10.5"])
        gen = ReportGenerator()
        content = gen.generate(m, format="json")
        data = json.loads(content)
        assert data["report"]["total_findings"] == 0


# ── Reporter Agent Tests ─────────────────────────────────


class TestReporterAgent:

    def setup_method(self):
        from agents.reporter.agent import ReporterAgent
        self.agent = ReporterAgent()

    def test_metadata(self):
        assert self.agent.name == "reporter"
        assert self.agent.phase == AttackPhase.REPORTING

    @pytest.mark.asyncio
    async def test_process_response(self):
        mission = Mission(name="Test", target_scope=["10.10.10.5"])
        from core.memory import ConversationMemory
        memory = ConversationMemory()

        response = json.dumps({
            "executive_summary": "Hedefde 3 kritik zafiyet bulundu.",
            "risk_rating": "CRITICAL",
            "remediation_priority": [
                {"priority": 1, "title": "Apache güncelle", "severity": "CRITICAL"}
            ],
            "findings": [],
            "next_recommendations": [],
        })

        result = await self.agent.process_response(response, mission, memory)
        assert result.success
        assert result.tool_outputs["executive_summary"] == "Hedefde 3 kritik zafiyet bulundu."
        assert result.tool_outputs["risk_rating"] == "CRITICAL"

    def test_generate_report(self):
        m = Mission(name="Test", target_scope=["10.10.10.5"])
        m.add_finding(Finding(
            title="Test", severity=Severity.HIGH, target="10.10.10.5",
            description="test", agent_source="scanner",
        ))
        content = self.agent.generate_report(m, format="json")
        data = json.loads(content)
        assert data["report"]["total_findings"] == 1
