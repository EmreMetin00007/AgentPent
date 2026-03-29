"""AgentPent — OSINT Agent.

Açık kaynak istihbarat toplama — email, subdomain, IP.
theHarvester + WHOIS korelasyon.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.osint.tools import setup_osint_tools
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity
from core.utils import extract_json_from_llm

logger = logging.getLogger("agentpent.agents.osint")


class OSINTAgent(BaseAgent):
    """Açık Kaynak İstihbarat (OSINT) agent'ı."""

    name = "osint"
    description = "OSINT — email, subdomain, IP toplama ve korelasyon"
    phase = AttackPhase.RECONNAISSANCE
    model = None

    def __init__(self):
        super().__init__()
        setup_osint_tools(self)

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        """LLM yanıtından OSINT bulgularını çıkar."""
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = extract_json_from_llm(response)

        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    finding = Finding(
                        title=f_data.get("title", "OSINT Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    )
                    findings.append(finding)
                except Exception as exc:
                    logger.warning("Finding oluşturma hatası: %s", exc)

            collected = parsed.get("collected_data", {})
            if collected:
                tool_outputs["emails"] = json.dumps(
                    collected.get("emails", []), ensure_ascii=False
                )
                tool_outputs["subdomains"] = json.dumps(
                    collected.get("subdomains", []), ensure_ascii=False
                )
                tool_outputs["ips"] = json.dumps(
                    collected.get("ips", []), ensure_ascii=False
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

    async def run_tools(self, mission: Mission) -> Dict[str, Any]:
        """OSINT araçlarını çalıştır."""
        results: Dict[str, Any] = {}

        for target in mission.target_scope:
            target_results: Dict[str, Any] = {}

            # 1. theHarvester — email/subdomain/IP
            harvester = self.get_tool("theharvester")
            if harvester and not self._is_ip(target):
                logger.info("[osint] theHarvester: %s", target)
                th_result = await harvester.execute({"target": target})
                target_results["theharvester"] = th_result.parsed_data

            # 2. WHOIS — kayıt bilgileri
            whois = self.get_tool("whois")
            if whois:
                logger.info("[osint] WHOIS: %s", target)
                wh_result = await whois.execute({"target": target})
                target_results["whois"] = wh_result.parsed_data

                # Bulunan IP'ler için de WHOIS
                if harvester and "theharvester" in target_results:
                    ips = target_results["theharvester"].get("ips", [])
                    ip_whois = {}
                    for ip in ips[:5]:  # İlk 5 IP
                        ip_wh = await whois.execute({"target": ip})
                        ip_whois[ip] = ip_wh.parsed_data
                    if ip_whois:
                        target_results["ip_whois"] = ip_whois

            results[target] = target_results

        return results

    @staticmethod
    def _is_ip(target: str) -> bool:
        parts = target.split(".")
        if len(parts) == 4:
            return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        return False


