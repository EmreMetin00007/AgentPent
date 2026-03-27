"""AgentPent — Responder Tool Wrapper.

LLMNR/NBT-NS/mDNS poisoning ve hash yakalama.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.responder")


class ResponderTool(BaseTool):
    """Responder — LLMNR/NBT-NS poisoning wrapper'ı."""

    name = "responder"
    binary = "responder"
    description = "LLMNR/NBT-NS poisoning, hash yakalama"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        interface = params.get("interface", "eth0")
        analyze = params.get("analyze", True)
        timeout = params.get("timeout", 120)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = [self.binary]
        args.extend(["-I", interface])

        if analyze:
            args.append("-A")  # Analyze mode (poison etme)

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Responder çıktısını parse et."""
        data: Dict[str, Any] = {
            "captured_hashes": [],
            "poisoned_requests": [],
            "detected_hosts": [],
            "protocols": [],
        }

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue

            # Hash yakalama
            hash_match = re.search(
                r"(NTLMv[12]|NetNTLMv[12]|NTLM).*?::\s*(.+)",
                line, re.IGNORECASE,
            )
            if hash_match:
                data["captured_hashes"].append({
                    "type": hash_match.group(1),
                    "hash": hash_match.group(2).strip()[:200],
                })

            # Poisoned requests
            poison_match = re.search(
                r"\[(\w+)\]\s+Poisoned answer sent to\s+(\S+)",
                line, re.IGNORECASE,
            )
            if poison_match:
                data["poisoned_requests"].append({
                    "protocol": poison_match.group(1),
                    "target": poison_match.group(2),
                })

            # Host tespiti
            host_match = re.search(
                r"\[\*\]\s+.*?(\d+\.\d+\.\d+\.\d+)", line
            )
            if host_match:
                ip = host_match.group(1)
                if ip not in data["detected_hosts"]:
                    data["detected_hosts"].append(ip)

            # Protokol tespiti
            for proto in ["LLMNR", "NBT-NS", "mDNS", "HTTP", "SMB", "LDAP", "FTP"]:
                if proto in line.upper() and proto not in data["protocols"]:
                    data["protocols"].append(proto)

        return data
