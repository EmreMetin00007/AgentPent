"""AgentPent — Commander Agent.

Orchestrator agent — tüm pentesting operasyonunu yönetir.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from core.llm_client import llm
from core.memory import ConversationMemory
from core.mission import AttackPhase, Mission

logger = logging.getLogger("agentpent.commander")


class CommanderAgent(BaseAgent):
    name = "commander"
    description = "Orchestrator — saldırı stratejisi, agent koordinasyonu, sonuç korelasyonu"
    phase = AttackPhase.RECONNAISSANCE
    model = None

    PHASE_AGENTS: Dict[AttackPhase, Dict] = {
        AttackPhase.RECONNAISSANCE: {
            "agents": ["recon", "osint"],
            "parallel": True,
        },
        AttackPhase.SCANNING: {
            "agents": ["scanner"],
            "parallel": False,
        },
        AttackPhase.VULNERABILITY_ANALYSIS: {
            "agents": ["vuln_analyzer", "webapp"],
            "parallel": True,
        },
        AttackPhase.EXPLOITATION: {
            "agents": ["exploit"],
            "parallel": False,
        },
        AttackPhase.POST_EXPLOITATION: {
            "agents": ["post_exploit"],
            "parallel": False,
        },
        AttackPhase.REPORTING: {
            "agents": ["reporter"],
            "parallel": False,
        },
    }

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        decision = self._parse_decision(response)
        return AgentResult(
            agent_name=self.name,
            raw_response=response,
            findings=[],
            tool_outputs={"decision": json.dumps(decision, ensure_ascii=False)},
            next_actions=self._extract_actions(decision),
            success=True,
        )

    async def decide_next(
        self,
        mission: Mission,
        memory: ConversationMemory,
        last_results: Optional[List[AgentResult]] = None,
    ) -> Dict:
        context_parts = [
            "## Mevcut Durum",
            "- Faz: {}".format(mission.current_phase.value),
            "- Tamamlanan Fazlar: {}".format(
                [p.value for p in mission.phases_completed]
            ),
            "- Toplam Bulgu: {}".format(sum(mission.stats.values())),
            "- Bulgu Dağılımı: {}".format(mission.stats),
            "- Hedefler: {}".format(mission.target_scope),
        ]

        if last_results:
            context_parts.append("\n## Son Agent Sonuçları")
            for r in last_results:
                context_parts.append("- {}".format(r.summary()))
                if r.findings:
                    for f in r.findings[:5]:
                        context_parts.append("  - {}".format(f.short()))

        context = "\n".join(context_parts)

        task = (
            "Mevcut pentest operasyonunun durumunu analiz et ve "
            "sonraki adıma karar ver. JSON formatında yanıt döndür: "
            '{"decision": "...", "target_agents": [...], "parallel": bool, '
            '"tasks": [...], "reasoning": "...", "notes": "..."}'
        )

        response = await llm.agent_call_json(
            agent_system_prompt=self.system_prompt,
            task=task,
            context=context,
            model=self.model,
        )
        return response

    def get_phase_agents(self, phase: AttackPhase) -> Dict:
        return self.PHASE_AGENTS.get(phase, {"agents": [], "parallel": False})

    def _parse_decision(self, raw: str) -> Dict:
        try:
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw.strip()
            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Commander kararı parse edilemedi, ham yanıt kullanılıyor")
            return {
                "decision": "next_phase",
                "target_agents": [],
                "parallel": False,
                "tasks": [],
                "reasoning": raw[:500],
                "notes": "",
            }

    def _extract_actions(self, decision: Dict) -> List[str]:
        actions = []
        for task_item in decision.get("tasks", []):
            agent = task_item.get("agent", "unknown")
            task = task_item.get("task", "")
            actions.append("{}: {}".format(agent, task))
        return actions
