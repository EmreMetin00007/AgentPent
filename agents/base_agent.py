"""AgentPent — Base Agent.

Tüm özelleşmiş agent'ların miras aldığı taban sınıf.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.llm_client import llm
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission

logger = logging.getLogger("agentpent.agent")


class BaseAgent(ABC):
    """Tüm AgentPent agent'larının taban sınıfı."""

    name: str = "base"
    description: str = ""
    phase: AttackPhase = AttackPhase.RECONNAISSANCE
    model: Optional[str] = None

    def __init__(self):
        self._system_prompt: str = ""
        self._tools: Dict[str, Any] = {}
        self._load_prompt()

    # ── Prompt Yükleme ───────────────────────────────────

    def _load_prompt(self) -> None:
        prompt_path = Path(__file__).parent / self.name / "{}.md".format(self.name)
        if prompt_path.exists():
            raw = prompt_path.read_text(encoding="utf-8")
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    self._system_prompt = parts[2].strip()
                else:
                    self._system_prompt = raw
            else:
                self._system_prompt = raw
            logger.debug("Prompt yüklendi: %s (%d chars)", prompt_path, len(self._system_prompt))
        else:
            self._system_prompt = self._default_prompt()

    def _default_prompt(self) -> str:
        return "Sen {} adlı bir pentest agent'ısın. Görevin: {}".format(
            self.name, self.description
        )

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    # ── Tool Kayıt ───────────────────────────────────────

    def register_tool(self, name: str, tool: Any) -> None:
        self._tools[name] = tool

    def get_tool(self, name: str) -> Any:
        return self._tools.get(name)

    @property
    def available_tools(self) -> List[str]:
        return list(self._tools.keys())

    # ── Ana Çalıştırma ───────────────────────────────────

    async def run(
        self,
        task: str,
        mission: Mission,
        memory: ConversationMemory,
        context: str = "",
    ) -> AgentResult:
        logger.info("[%s] Görev başlatıldı: %s", self.name, task[:100])
        memory.add_user(task, agent=self.name, phase=self.phase.value)

        full_context = self._build_context(mission, context)

        response = await llm.agent_call(
            agent_system_prompt=self.system_prompt,
            task=task,
            context=full_context,
            model=self.model,
        )

        memory.add_assistant(response, agent=self.name, phase=self.phase.value)
        result = await self.process_response(response, mission, memory)
        logger.info(
            "[%s] Tamamlandı — %d bulgu", self.name, len(result.findings),
        )
        return result

    def _build_context(self, mission: Mission, extra: str = "") -> str:
        parts = [
            "## Mission Bilgileri",
            "- ID: {}".format(mission.id),
            "- Ad: {}".format(mission.name),
            "- Hedefler: {}".format(", ".join(mission.target_scope)),
            "- Mevcut Faz: {}".format(mission.current_phase.value),
            "- Tamamlanan Fazlar: {}".format(
                ", ".join(p.value for p in mission.phases_completed)
            ),
            "- Mevcut Bulgular: {}".format(mission.stats),
        ]
        if mission.commander_notes:
            parts.append("\n## Commander Notları\n{}".format(mission.commander_notes))
        if extra:
            parts.append("\n## Ek Bağlam\n{}".format(extra))
        return "\n".join(parts)

    @abstractmethod
    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        ...


class AgentResult:
    """Bir agent çalışmasının sonucu."""

    def __init__(
        self,
        agent_name: str,
        raw_response: str = "",
        findings: Optional[List[Finding]] = None,
        tool_outputs: Optional[Dict[str, str]] = None,
        next_actions: Optional[List[str]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.raw_response = raw_response
        self.findings = findings or []
        self.tool_outputs = tool_outputs or {}
        self.next_actions = next_actions or []
        self.success = success
        self.error = error

    def summary(self) -> str:
        status = "✅" if self.success else "❌"
        return "{} [{}] Bulgular: {} | Araçlar: {} | Önerilen Aksiyonlar: {}".format(
            status, self.agent_name, len(self.findings),
            len(self.tool_outputs), len(self.next_actions),
        )
