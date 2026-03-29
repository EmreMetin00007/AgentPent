"""AgentPent — Persistence Agent.

Kalıcı erişim — cron, systemd, registry, scheduled task.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.persist.tools import setup_persist_tools
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity
from core.utils import extract_json_from_llm

logger = logging.getLogger("agentpent.agents.persist")


class PersistAgent(BaseAgent):
    """Persistence agent'ı."""

    name = "persist"
    description = "Persistence — cron, systemd, registry, scheduled task ile kalıcı erişim"
    phase = AttackPhase.POST_EXPLOITATION
    model = None

    def __init__(self):
        super().__init__()
        setup_persist_tools(self)

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = extract_json_from_llm(response)
        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    findings.append(Finding(
                        title=f_data.get("title", "Persistence Bulgusu"),
                        severity=Severity(f_data.get("severity", "HIGH").upper()),
                        target=f_data.get("target", ""),
                        port=f_data.get("port"),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    ))
                except Exception as exc:
                    logger.warning("Finding hatası: %s", exc)

            mechanisms = parsed.get("mechanisms", [])
            tool_outputs["mechanisms"] = json.dumps(
                mechanisms, ensure_ascii=False
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


