"""AgentPent — Nikto Tool Wrapper.

Web sunucu güvenlik tarayıcısı.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.nikto")


class NiktoTool(BaseTool):
    """Nikto — web sunucu güvenlik tarayıcısı wrapper'ı."""

    name = "nikto"
    binary = "nikto"
    description = "Web sunucu güvenlik tarayıcısı"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        port = params.get("port")
        tuning = params.get("tuning")
        ssl = params.get("ssl", False)
        timeout = params.get("timeout", 600)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = [self.binary]
        args.extend(["-h", target])
        args.extend(["-Format", "json"])
        args.extend(["-o", "-"])  # stdout'a yaz

        if port:
            args.extend(["-p", str(port)])

        if tuning:
            args.extend(["-Tuning", str(tuning)])

        if ssl:
            args.append("-ssl")

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Nikto çıktısını parse et."""
        data: Dict[str, Any] = {
            "vulnerabilities": [],
            "server_info": {},
            "total": 0,
        }

        # JSON parse denemesi
        try:
            output = json.loads(raw)
            if isinstance(output, dict):
                return self._parse_json(output)
            elif isinstance(output, list) and output:
                return self._parse_json(output[0])
        except json.JSONDecodeError:
            pass

        # Metin parse (fallback)
        return self._parse_text(raw)

    def _parse_json(self, output: Dict) -> Dict[str, Any]:
        """JSON formatındaki Nikto çıktısını parse et."""
        data: Dict[str, Any] = {
            "vulnerabilities": [],
            "server_info": {},
            "total": 0,
        }

        # Host bilgisi
        host_info = output.get("host", output.get("ip", ""))
        port_info = output.get("port", "")
        data["server_info"] = {
            "host": host_info,
            "port": port_info,
            "banner": output.get("banner", ""),
        }

        # Vulnerabilities
        vulns = output.get("vulnerabilities", [])
        for vuln in vulns:
            entry = {
                "id": vuln.get("id", ""),
                "osvdb": vuln.get("OSVDB", vuln.get("osvdb", "")),
                "method": vuln.get("method", "GET"),
                "url": vuln.get("url", ""),
                "description": vuln.get("msg", vuln.get("description", "")),
                "references": vuln.get("references", {}),
            }
            data["vulnerabilities"].append(entry)

        data["total"] = len(data["vulnerabilities"])
        return data

    def _parse_text(self, raw: str) -> Dict[str, Any]:
        """Metin formatındaki Nikto çıktısını parse et."""
        data: Dict[str, Any] = {
            "vulnerabilities": [],
            "server_info": {},
            "total": 0,
        }

        for line in raw.splitlines():
            line = line.strip()

            # Server bilgisi
            server_match = re.search(r"Server:\s*(.+)", line, re.IGNORECASE)
            if server_match:
                data["server_info"]["banner"] = server_match.group(1).strip()

            # OSVDB bulguları
            osvdb_match = re.search(
                r"\+\s*(?:OSVDB-(\d+):)?\s*(.+)", line
            )
            if osvdb_match and "items checked" not in line.lower():
                data["vulnerabilities"].append({
                    "osvdb": osvdb_match.group(1) or "",
                    "description": osvdb_match.group(2).strip(),
                })

        data["total"] = len(data["vulnerabilities"])
        return data
