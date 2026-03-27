"""AgentPent — Network Agent.

İç ağ keşfi, MITM, trafik analizi, pivoting.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.network.tools import setup_network_tools
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.network")


class NetworkAgent(BaseAgent):
    """Ağ analizi ve pivoting agent'ı."""

    name = "network"
    description = "Ağ analizi — iç ağ keşfi, MITM, hash yakalama, pivoting"
    phase = AttackPhase.POST_EXPLOITATION
    model = None

    def __init__(self):
        super().__init__()
        setup_network_tools(self)

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = self._extract_json(response)
        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    findings.append(Finding(
                        title=f_data.get("title", "Network Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        port=f_data.get("port"),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    ))
                except Exception as exc:
                    logger.warning("Finding hatası: %s", exc)

            tool_outputs["internal_hosts"] = json.dumps(
                parsed.get("internal_hosts", []), ensure_ascii=False
            )
            tool_outputs["tunnels"] = json.dumps(
                parsed.get("tunnels", []), ensure_ascii=False
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

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        try:
            if "```json" in text:
                return json.loads(text.split("```json")[1].split("```")[0].strip())
            elif "```" in text:
                return json.loads(text.split("```")[1].split("```")[0].strip())
            return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return None
