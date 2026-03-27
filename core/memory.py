"""AgentPent — Conversation & Mission Memory.

Agent'lar arası bağlam paylaşımı ve mission geçmişini yönetir.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import settings

logger = logging.getLogger("agentpent.memory")


class MemoryEntry:
    """Bellekteki tek bir kayıt."""

    __slots__ = ("role", "agent", "content", "phase", "timestamp", "metadata")

    def __init__(
        self,
        role: str,
        content: str,
        agent: str = "",
        phase: str = "",
        metadata: Optional[dict] = None,
    ):
        self.role = role
        self.agent = agent
        self.content = content
        self.phase = phase
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "agent": self.agent,
            "content": self.content,
            "phase": self.phase,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def to_message(self) -> dict[str, str]:
        """OpenAI chat mesajına dönüştür."""
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """Mission bazlı konuşma geçmişi yönetir."""

    def __init__(self, max_entries: int = 200):
        self._entries: list[MemoryEntry] = []
        self._max = max_entries

    # ── Ekleme ───────────────────────────────────────────

    def add(
        self,
        role: str,
        content: str,
        agent: str = "",
        phase: str = "",
        metadata: Optional[dict] = None,
    ) -> None:
        entry = MemoryEntry(role, content, agent, phase, metadata)
        self._entries.append(entry)
        # Taşma kontrolü — en eski kayıtları sil
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max :]

    def add_system(self, content: str, **kw) -> None:
        self.add("system", content, **kw)

    def add_user(self, content: str, **kw) -> None:
        self.add("user", content, **kw)

    def add_assistant(self, content: str, **kw) -> None:
        self.add("assistant", content, **kw)

    def add_tool_result(self, content: str, agent: str = "", **kw) -> None:
        self.add("user", f"[Tool Result]\n{content}", agent=agent, **kw)

    # ── Sorgulama ────────────────────────────────────────

    @property
    def messages(self) -> list[dict[str, str]]:
        """Tüm kayıtları OpenAI chat formatında döner."""
        return [e.to_message() for e in self._entries]

    def get_by_agent(self, agent: str) -> list[MemoryEntry]:
        return [e for e in self._entries if e.agent == agent]

    def get_by_phase(self, phase: str) -> list[MemoryEntry]:
        return [e for e in self._entries if e.phase == phase]

    def get_last(self, n: int = 10) -> list[MemoryEntry]:
        return self._entries[-n:]

    def get_summary(self) -> str:
        """Bellek özetini döner."""
        total = len(self._entries)
        agents = set(e.agent for e in self._entries if e.agent)
        phases = set(e.phase for e in self._entries if e.phase)
        return (
            f"Toplam {total} kayıt | "
            f"Agent'lar: {', '.join(agents) or 'yok'} | "
            f"Fazlar: {', '.join(phases) or 'yok'}"
        )

    # ── Persistence ──────────────────────────────────────

    def save(self, mission_id: str) -> Path:
        """Belleği JSON olarak diske kaydeder."""
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"memory_{mission_id}.json"
        data = [e.to_dict() for e in self._entries]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Bellek kaydedildi: %s (%d kayıt)", path, len(data))
        return path

    def load(self, mission_id: str) -> bool:
        """Daha önce kaydedilmiş belleği yükler."""
        path = Path(settings.log_dir) / f"memory_{mission_id}.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        self._entries = [
            MemoryEntry(
                role=d["role"],
                content=d["content"],
                agent=d.get("agent", ""),
                phase=d.get("phase", ""),
                metadata=d.get("metadata"),
            )
            for d in data
        ]
        logger.info("Bellek yüklendi: %s (%d kayıt)", path, len(self._entries))
        return True

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
