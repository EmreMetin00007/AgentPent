"""AgentPent — Scanner Agent.

Detaylı port/servis tarama ve vulnerability scanning.
Nmap full scan + Nuclei entegrasyonu.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.scanner.tools import setup_scanner_tools
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.scanner")


class ScannerAgent(BaseAgent):
    """Tarama (Scanning) agent'ı."""

    name = "scanner"
    description = "Port/servis tarama ve vulnerability scanning — nmap full + nuclei"
    phase = AttackPhase.SCANNING
    model = None

    def __init__(self):
        super().__init__()
        setup_scanner_tools(self)

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        """LLM yanıtından bulguları çıkar."""
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = self._extract_json(response)

        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    finding = Finding(
                        title=f_data.get("title", "Tarama Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        port=f_data.get("port"),
                        service=f_data.get("service"),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        cve_ids=f_data.get("cve_ids", []),
                        cvss_score=f_data.get("cvss_score"),
                        agent_source=self.name,
                        phase=self.phase,
                    )
                    findings.append(finding)
                except Exception as exc:
                    logger.warning("Finding oluşturma hatası: %s", exc)

            tool_outputs["open_ports"] = json.dumps(
                parsed.get("open_ports_summary", {}), ensure_ascii=False
            )
            tool_outputs["vuln_count"] = str(
                parsed.get("vulnerabilities_found", 0)
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
        """Nmap full scan + Nuclei vuln scan çalıştır."""
        results: Dict[str, Any] = {}

        for target in mission.target_scope:
            target_results: Dict[str, Any] = {}

            # 1. Nmap — tam port + servis versiyon taraması
            nmap = self.get_tool("nmap")
            if nmap:
                logger.info("[scanner] Nmap full scan: %s", target)
                nm_result = await nmap.execute({
                    "target": target,
                    "scan_type": "full",
                })
                target_results["nmap_full"] = nm_result.parsed_data

                # Servis versiyon detayı
                if nm_result.success:
                    logger.info("[scanner] Nmap service scan: %s", target)
                    svc_result = await nmap.execute({
                        "target": target,
                        "scan_type": "service",
                    })
                    target_results["nmap_service"] = svc_result.parsed_data

            # 2. Nuclei — vulnerability scan
            nuclei = self.get_tool("nuclei")
            if nuclei:
                logger.info("[scanner] Nuclei vuln scan: %s", target)

                # Önce critical/high
                nucl_result = await nuclei.execute({
                    "target": target,
                    "severity": "critical,high",
                })
                target_results["nuclei_critical"] = nucl_result.parsed_data

                # Sonra medium/low
                nucl_med = await nuclei.execute({
                    "target": target,
                    "severity": "medium,low",
                })
                target_results["nuclei_medium"] = nucl_med.parsed_data

            results[target] = target_results

        return results

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """LLM yanıtından JSON bloğunu çıkar."""
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
