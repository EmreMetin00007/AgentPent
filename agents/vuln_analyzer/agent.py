"""AgentPent — Vuln Analyzer Agent.

Zafiyet analizi, CVE eşleştirme, CVSS değerlendirme
ve önceliklendirme.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.vuln_analyzer")


class VulnAnalyzerAgent(BaseAgent):
    """Zafiyet Analiz agent'ı."""

    name = "vuln_analyzer"
    description = "Zafiyet analizi — CVE/NVD eşleştirme, CVSS değerlendirme, önceliklendirme"
    phase = AttackPhase.VULNERABILITY_ANALYSIS
    model = None

    def __init__(self):
        super().__init__()
        self._cve_db = None

    def _get_cve_db(self):
        """Lazy init CVE DB."""
        if self._cve_db is None:
            from knowledge.cve_db import cve_db
            self._cve_db = cve_db
        return self._cve_db

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        """LLM yanıtından zafiyet bulgularını çıkar."""
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = self._extract_json(response)

        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    finding = Finding(
                        title=f_data.get("title", "Zafiyet Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        port=f_data.get("port"),
                        service=f_data.get("service"),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        cve_ids=f_data.get("cve_ids", []),
                        cvss_score=f_data.get("cvss_score"),
                        exploitable=f_data.get("exploitable", False),
                        remediation=f_data.get("remediation", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    )
                    findings.append(finding)
                except Exception as exc:
                    logger.warning("Finding oluşturma hatası: %s", exc)

            risk_summary = parsed.get("risk_summary", {})
            tool_outputs["risk_summary"] = json.dumps(risk_summary, ensure_ascii=False)
            tool_outputs["priority_targets"] = json.dumps(
                parsed.get("priority_targets", []), ensure_ascii=False
            )
            next_actions = parsed.get("next_recommendations", [])

        return AgentResult(
            agent_name=self.name,
            raw_response=response,
            findings=findings,
            tool_outputs=tool_outputs,
            next_actions=next_actions,
            success=True,
        )

    async def analyze_services(
        self, services: List[Dict[str, Any]], mission: Mission
    ) -> List[Finding]:
        """Servis listesini CVE veritabanıyla eşleştir."""
        findings: List[Finding] = []
        cve_db = self._get_cve_db()

        for svc in services:
            product = svc.get("product", "")
            version = svc.get("version", "")
            target = svc.get("target", "")
            port = svc.get("port")

            if not product:
                continue

            logger.info(
                "[vuln_analyzer] CVE arama: %s %s (%s:%s)",
                product, version, target, port,
            )

            cves = await cve_db.search_by_cpe(
                product=product,
                version=version,
            )

            for cve in cves:
                if cve.cvss_v3_score and cve.cvss_v3_score >= 4.0:
                    finding = Finding(
                        title="{} {} — {}".format(product, version, cve.cve_id),
                        severity=Severity(cve.severity),
                        target=target,
                        port=port,
                        service="{} {}".format(product, version),
                        cve_ids=[cve.cve_id],
                        cvss_score=cve.cvss_v3_score,
                        description=cve.description[:500],
                        evidence="NVD API — CVSS: {}, AV: {}, AC: {}".format(
                            cve.cvss_v3_score,
                            cve.attack_vector,
                            cve.attack_complexity,
                        ),
                        exploitable=bool(
                            cve.exploitability_score
                            and cve.exploitability_score >= 2.0
                        ),
                        agent_source=self.name,
                        phase=self.phase,
                    )
                    findings.append(finding)

        # CVSS skoruna göre sırala
        findings.sort(key=lambda f: f.cvss_score or 0, reverse=True)
        return findings

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            else:
                return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return None
