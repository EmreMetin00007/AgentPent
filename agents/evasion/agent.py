"""AgentPent — Evasion Agent.

AV/EDR bypass, payload obfuscation, AMSI bypass.
LLM-driven — harici araç kullanmaz.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.evasion")


class EvasionAgent(BaseAgent):
    """AV/EDR bypass ve evasion agent'ı (LLM-driven)."""

    name = "evasion"
    description = "AV/EDR bypass — payload obfuscation, AMSI bypass, shellcode encoding"
    phase = AttackPhase.EXPLOITATION
    model = None

    def __init__(self):
        super().__init__()
        # LLM-driven — harici araç kaydı yok

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
                        title=f_data.get("title", "Evasion Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    ))
                except Exception as exc:
                    logger.warning("Finding hatası: %s", exc)

            techniques = parsed.get("evasion_techniques", [])
            tool_outputs["evasion_techniques"] = json.dumps(
                techniques, ensure_ascii=False
            )
            tool_outputs["encoded_payloads"] = json.dumps(
                parsed.get("encoded_payloads", []), ensure_ascii=False
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
