"""AgentPent — Base Tool Wrapper.

Tüm dış araç entegrasyonlarının taban sınıfı.
Her araç çağrısı scope guard + rate limiter + audit'ten geçer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.scope_guard import OutOfScopeError, scope_guard
from core.rate_limiter import rate_limiter
from core.audit import audit
from config.settings import settings

logger = logging.getLogger("agentpent.tools")


@dataclass
class ToolResult:
    """Bir araç çalıştırmasının sonucu."""

    tool_name: str
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None

    @property
    def short(self) -> str:
        status = "✅" if self.success else "❌"
        return "{} [{}] {:.0f}ms".format(status, self.tool_name, self.duration_ms)


# ── Tool Metrikleri ──────────────────────────────────────

class _ToolMetrics:
    """Araç kullanım istatistikleri."""

    def __init__(self):
        self.total_calls = 0
        self.successful = 0
        self.failed = 0
        self.total_duration_ms = 0.0

    def record(self, success: bool, duration_ms: float) -> None:
        self.total_calls += 1
        if success:
            self.successful += 1
        else:
            self.failed += 1
        self.total_duration_ms += duration_ms

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / max(self.total_calls, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total_calls,
            "success": self.successful,
            "failed": self.failed,
            "avg_ms": round(self.avg_duration_ms, 1),
        }


class BaseTool(ABC):
    """Tüm pentest araçlarının taban wrapper sınıfı."""

    name: str = "base_tool"
    binary: str = ""  # CLI binary adı (nmap, nuclei, etc.)
    description: str = ""

    def __init__(self):
        self._available: Optional[bool] = None
        self._metrics = _ToolMetrics()

    # ── Kullanılabilirlik Kontrolü ────────────────────────

    async def is_available(self) -> bool:
        """Aracın sistemde kurulu olup olmadığını kontrol eder."""
        if self._available is not None:
            return self._available
        try:
            proc = await asyncio.create_subprocess_exec(
                self.binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            self._available = proc.returncode == 0
        except FileNotFoundError:
            self._available = False
        logger.debug("[%s] Kullanılabilirlik: %s", self.name, self._available)
        return self._available

    # ── Kapsam Kontrolü ──────────────────────────────────

    def validate_scope(self, target: str, port: Optional[int] = None) -> bool:
        """Hedefin kapsamda olduğunu doğrula. Kapsam dışıysa exception fırlatır."""
        return scope_guard.validate_target(target, port)

    @staticmethod
    def _normalize_targets(target: Any) -> List[str]:
        if isinstance(target, (list, tuple, set)):
            normalized: List[str] = []
            for item in target:
                text = str(item).strip()
                if text:
                    normalized.append(text)
            return normalized

        text = str(target).strip() if target is not None else ""
        return [text] if text else []

    # ── Komut Çalıştırma ─────────────────────────────────

    async def run_command(
        self,
        args: List[str],
        *,
        timeout: int = 300,
        cwd: Optional[str] = None,
    ) -> ToolResult:
        """Shell komutu çalıştır ve sonucu dön."""
        cmd_str = " ".join(args)
        logger.info("[%s] Komut: %s", self.name, cmd_str)
        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            elapsed = (time.monotonic() - start) * 1000

            return ToolResult(
                tool_name=self.name,
                command=cmd_str,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                return_code=proc.returncode or 0,
                duration_ms=elapsed,
                success=proc.returncode == 0,
            )

        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                command=cmd_str,
                duration_ms=elapsed,
                success=False,
                error="Zaman aşımı ({}s)".format(timeout),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                command=cmd_str,
                duration_ms=elapsed,
                success=False,
                error=str(exc),
            )

    # ── Ana Giriş Noktası ────────────────────────────────

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Scope guard + rate limiter + audit'ten geçir ve aracı çalıştır."""
        target = params.get("target", "")
        normalized_targets = self._normalize_targets(target)
        port = params.get("port")
        start = time.monotonic()

        # 1. Kapsam kontrolü
        try:
            if normalized_targets:
                for single_target in normalized_targets:
                    self.validate_scope(single_target, port)
            else:
                self.validate_scope("", port)
        except OutOfScopeError as exc:
            logger.warning("[%s] Kapsam ihlali: %s", self.name, exc)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )

        # 2. Kullanılabilirlik
        if self.binary and not await self.is_available():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="{} bulunamadı — kurulum gerekli".format(self.binary),
            )

        # 3. Rate limiter — target bazlı throttle + jitter
        rate_limit_key = normalized_targets[0] if normalized_targets else "global"
        await rate_limiter.acquire(rate_limit_key)

        try:
            result = await self._run(params)
        finally:
            rate_limiter.release()

        # 4. Metrik kaydet
        elapsed = (time.monotonic() - start) * 1000
        self._metrics.record(result.success, elapsed)

        return result

    @property
    def metrics(self) -> Dict[str, Any]:
        return self._metrics.to_dict()

    @abstractmethod
    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        """Gerçek araç çalıştırma mantığı (alt sınıf implemente eder)."""
        ...

    @abstractmethod
    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Ham çıktıyı yapılandırılmış veriye dönüştür."""
        ...
