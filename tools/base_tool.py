"""AgentPent — Base Tool Wrapper.

Tüm dış araç entegrasyonlarının taban sınıfı.
Her araç çağrısı scope guard'dan geçer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.scope_guard import OutOfScopeError, scope_guard
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


class BaseTool(ABC):
    """Tüm pentest araçlarının taban wrapper sınıfı."""

    name: str = "base_tool"
    binary: str = ""  # CLI binary adı (nmap, nuclei, etc.)
    description: str = ""

    def __init__(self):
        self._available: Optional[bool] = None

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
        """Scope guard'dan geçir ve aracı çalıştır."""
        target = params.get("target", "")
        port = params.get("port")

        # Kapsam kontrolü
        try:
            self.validate_scope(target, port)
        except OutOfScopeError as exc:
            logger.warning("[%s] Kapsam ihlali: %s", self.name, exc)
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )

        # Kullanılabilirlik
        if self.binary and not await self.is_available():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="{} bulunamadı — kurulum gerekli".format(self.binary),
            )

        return await self._run(params)

    @abstractmethod
    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        """Gerçek araç çalıştırma mantığı (alt sınıf implemente eder)."""
        ...

    @abstractmethod
    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Ham çıktıyı yapılandırılmış veriye dönüştür."""
        ...
