"""AgentPent — Social Engineering Agent.

Phishing simülasyonu, pretexting, vishing.
LLM-driven — harici araç kullanmaz.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.social_eng")


class SocialEngAgent(BaseAgent):
    """Sosyal mühendislik simülasyonu agent'ı (LLM-driven)."""

    name = "social_eng"
    description = "Sosyal mühendislik — phishing simülasyonu, pretexting, vishing"
    phase = AttackPhase.RECONNAISSANCE
    model = None

    def __init__(self):
        super().__init__()

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
                        title=f_data.get("title", "Social Eng Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    ))
                except Exception as exc:
                    logger.warning("Finding hatası: %s", exc)

            templates = parsed.get("templates", [])
            tool_outputs["templates"] = json.dumps(
                templates, ensure_ascii=False
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
