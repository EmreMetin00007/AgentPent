"""AgentPent — Kali Terminal Tool.

Genel amaçlı bir Command/Terminal wrapper'ı.
Diğer özel tool'lar (nmap, sqlmap) yetersiz kaldığında
Kali Linux içindeki arbitary araçların çalıştırılmasına olanak tanır.
"""

from __future__ import annotations

import asyncio
import logging
from typing import ClassVar, Dict, List, Any

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.kali_terminal")


class KaliTerminalTool(BaseTool):
    """Herhangi bir kabuk komutunu (bash) çalıştıran araç."""

    name: ClassVar[str] = "kaliterminal"
    description: ClassVar[str] = (
        "Genel amaçlı terminal/shell aracı. Özel araçların yetersiz olduğu "
        "durumlarda doğrudan Kali Linux kabuğu üzerinden komut (ör. wfuzz, smbclient, awk) yürütür."
    )

    timeout: int = 120  # Smoke testlerde kilitlenmeyi önlemek için daha kısa
    allowed_commands: List[str] = []  # Kısıtlama uygulanmayacak, LLM her şeyi çalıştırabilir.

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        """
        Yerel bir komutu shell üzerinden çalıştırır.
        """
        command = params.get("command", "")
        if not command:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="'command' parametresi gerekli."
            )

        logger.info("[KaliTerminal] Executing command: %s", command)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                kill_result = process.kill()
                if asyncio.iscoroutine(kill_result):
                    await kill_result
                await process.communicate()
                logger.error("[KaliTerminal] Command timed out: %s", command)
                return ToolResult(
                    tool_name=self.name, command=command, success=False, error=f"Command timed out after {self.timeout} seconds"
                )

            out_str = stdout.decode("utf-8", errors="replace").strip()
            err_str = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode != 0:
                logger.warning("[KaliTerminal] Command failed Exit %s: %s", process.returncode, err_str)
                return ToolResult(
                    tool_name=self.name, command=command, stdout=out_str, stderr=err_str,
                    return_code=process.returncode, success=False,
                    error=f"Command failed (Exit code {process.returncode})"
                )

            if len(out_str) > 15000:
                out_str = out_str[:15000] + "\n...[TRUNCATED: Output too long]..."

            return ToolResult(
                tool_name=self.name, command=command, stdout=out_str,
                stderr=err_str, return_code=0, success=True,
                parsed_data={"raw_terminal_output": out_str}
            )

        except Exception as exc:
            logger.exception("[KaliTerminal] Execution exception: %s", exc)
            return ToolResult(
                tool_name=self.name, command=command, success=False, error=str(exc)
            )

    def parse_output(self, raw_output: str) -> Dict[str, str]:
        """Terminal çıktısını doğrudan döndürür. Manuel parsing LLM'e bırakılır."""
        return {"raw_terminal_output": raw_output}
