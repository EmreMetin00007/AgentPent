"""AgentPent — WebApp Agent.

Web uygulama güvenlik testi — SQLi, XSS, dizin keşfi.
Browser Vision entegrasyonu ReAct loop'un bir parçası olarak çalışır.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.webapp.tools import setup_webapp_tools
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity
from core.utils import extract_json_from_llm

logger = logging.getLogger("agentpent.agents.webapp")


class WebAppAgent(BaseAgent):
    """Web Uygulama Güvenlik agent'ı."""

    name = "webapp"
    description = "Web app güvenlik testi — SQLi, XSS, dizin keşfi, web vuln tarama"
    phase = AttackPhase.VULNERABILITY_ANALYSIS
    model = None

    def __init__(self):
        super().__init__()
        setup_webapp_tools(self)

    # run() artık BaseAgent'taki ReAct loop'u kullanıyor.
    # Browser Vision tool olarak kayıtlı olduğu için LLM onu çağırabilir.

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        """LLM yanıtından web app bulgularını çıkar."""
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = extract_json_from_llm(response)

        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    finding = Finding(
                        title=f_data.get("title", "WebApp Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        port=f_data.get("port"),
                        service=f_data.get("service"),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        cve_ids=f_data.get("cve_ids", []),
                        exploitable=f_data.get("exploitable", False),
                        remediation=f_data.get("remediation", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    )
                    findings.append(finding)
                except Exception as exc:
                    logger.warning("Finding oluşturma hatası: %s", exc)

            discovered = parsed.get("discovered_paths", [])
            tool_outputs["discovered_paths"] = json.dumps(
                discovered, ensure_ascii=False
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
