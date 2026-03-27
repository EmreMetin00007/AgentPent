"""AgentPent — Chisel Tool Wrapper.

TCP tunneling ve pivoting aracı.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.chisel")


class ChiselTool(BaseTool):
    """Chisel — TCP tunneling / pivoting wrapper'ı."""

    name = "chisel"
    binary = "chisel"
    description = "TCP tunneling ve pivoting"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        mode = params.get("mode", "client")
        server_addr = params.get("server", "")
        remote = params.get("remote", "")
        port = params.get("port", "8080")
        reverse = params.get("reverse", False)
        timeout = params.get("timeout", 30)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = [self.binary, mode]

        if mode == "server":
            args.extend(["--port", str(port)])
            if reverse:
                args.append("--reverse")
        elif mode == "client":
            if not server_addr:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error="Client modunda server adresi gerekli",
                )
            args.append(server_addr)
            if remote:
                args.append(remote)

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Chisel çıktısını parse et."""
        data: Dict[str, Any] = {
            "tunnels": [],
            "status": "unknown",
            "listening_port": None,
        }

        for line in raw.splitlines():
            line = line.strip()

            # Server listening
            listen_match = re.search(
                r"server:\s+Listening on\s+(\S+)", line, re.IGNORECASE
            )
            if listen_match:
                data["status"] = "listening"
                data["listening_port"] = listen_match.group(1)

            # Tunnel oluşturuldu
            tunnel_match = re.search(
                r"([\d.]+:\d+)\s*(?:=>|→)\s*([\d.]+:\d+)", line
            )
            if tunnel_match:
                data["tunnels"].append({
                    "local": tunnel_match.group(1),
                    "remote": tunnel_match.group(2),
                })

            # Bağlantı durumu
            if "connected" in line.lower():
                data["status"] = "connected"
            elif "disconnected" in line.lower() or "error" in line.lower():
                data["status"] = "error"

        return data
