"""AgentPent — Structured Audit Trail.

Tüm araç çağrıları, LLM istekleri ve karar noktaları için
yapılandırılmış JSON Lines audit log'u.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings

logger = logging.getLogger("agentpent.audit")

# Hassas veri maskeleme desenleri
_SENSITIVE_PATTERNS = [
    (re.compile(r"(api[_-]?key|token|password|secret|credential)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_\-]{8,})", re.IGNORECASE), r"\1=***MASKED***"),
    (re.compile(r"(sk-[a-zA-Z0-9]{20,})"), "***API_KEY_MASKED***"),
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]+", re.IGNORECASE), r"\1***TOKEN_MASKED***"),
]


def _mask_sensitive(text: str) -> str:
    """Hassas verileri maskeler."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class AuditLogger:
    """Mission bazlı yapılandırılmış audit log'u."""

    def __init__(self, log_dir: Optional[str] = None):
        self._log_dir = Path(log_dir or settings.log_dir) / "audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._mission_id: Optional[str] = None
        self._file_handle = None
        self._event_count = 0

    def set_mission(self, mission_id: str) -> None:
        """Aktif mission'ı ayarla ve log dosyasını aç."""
        if self._file_handle:
            self._file_handle.close()
        self._mission_id = mission_id
        log_path = self._log_dir / f"audit_{mission_id}.jsonl"
        self._file_handle = open(log_path, "a", encoding="utf-8")
        self._event_count = 0
        logger.info("Audit log başlatıldı: %s", log_path)

    def log(
        self,
        event_type: str,
        *,
        agent: str = "",
        tool: str = "",
        target: str = "",
        phase: str = "",
        detail: Optional[Dict[str, Any]] = None,
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> None:
        """Tek bir audit kaydı yaz."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "seq": self._event_count,
            "mission_id": self._mission_id or "none",
            "event": event_type,
            "agent": agent,
            "tool": tool,
            "target": target,
            "phase": phase,
            "success": success,
            "duration_ms": round(duration_ms, 1),
        }

        if detail:
            # Hassas verileri maskele
            masked = _mask_sensitive(json.dumps(detail, ensure_ascii=False, default=str))
            entry["detail"] = json.loads(masked)

        self._event_count += 1

        if self._file_handle:
            line = json.dumps(entry, ensure_ascii=False, default=str)
            self._file_handle.write(line + "\n")
            self._file_handle.flush()

        # Ayrıca standart loglama
        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            "[AUDIT] %s | agent=%s tool=%s target=%s success=%s (%.0fms)",
            event_type, agent, tool, target, success, duration_ms,
        )

    # ── Convenience Methods ──────────────────────────────

    def tool_call(
        self, tool: str, target: str, params: Dict, result_success: bool,
        duration_ms: float, agent: str = "", phase: str = "",
    ) -> None:
        self.log(
            "tool_call", tool=tool, target=target, agent=agent, phase=phase,
            success=result_success, duration_ms=duration_ms,
            detail={"params": {k: str(v)[:200] for k, v in params.items()}},
        )

    def llm_call(
        self, agent: str, model: str, prompt_tokens: int = 0,
        duration_ms: float = 0.0, success: bool = True,
    ) -> None:
        self.log(
            "llm_call", agent=agent, success=success, duration_ms=duration_ms,
            detail={"model": model, "prompt_tokens": prompt_tokens},
        )

    def phase_transition(
        self, from_phase: str, to_phase: str, findings_count: int = 0,
    ) -> None:
        self.log(
            "phase_transition",
            detail={"from": from_phase, "to": to_phase, "findings": findings_count},
        )

    def decision(
        self, decision_type: str, agent: str = "commander", detail: Optional[Dict] = None,
    ) -> None:
        self.log("decision", agent=agent, detail=detail or {"type": decision_type})

    def veto(self, vetoed_by: str, reason: str) -> None:
        self.log(
            "veto", agent=vetoed_by, success=False,
            detail={"reason": reason[:500]},
        )

    def close(self) -> None:
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __del__(self):
        self.close()


# Singleton
audit = AuditLogger()
