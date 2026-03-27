"""AgentPent — Subfinder Tool Wrapper.

Pasif subdomain keşfi aracı.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.subfinder")


class SubfinderTool(BaseTool):
    """Subfinder — pasif subdomain enumeration wrapper'ı."""

    name = "subfinder"
    binary = "subfinder"
    description = "Pasif subdomain keşif aracı"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        recursive = params.get("recursive", False)
        timeout = params.get("timeout", 300)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = [self.binary]
        args.extend(["-d", target])
        args.extend(["-silent"])
        args.extend(["-json"])

        if recursive:
            args.append("-recursive")

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Subfinder JSON çıktısını parse et."""
        subdomains: List[str] = []
        sources: Dict[str, List[str]] = {}

        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                host = item.get("host", "")
                source = item.get("source", "unknown")
                if host:
                    subdomains.append(host)
                    sources.setdefault(source, []).append(host)
            except json.JSONDecodeError:
                # Düz metin satırı (eski format)
                if "." in line and " " not in line:
                    subdomains.append(line)

        # Deduplicate
        unique = sorted(set(subdomains))

        return {
            "subdomains": unique,
            "total": len(unique),
            "sources": {k: sorted(set(v)) for k, v in sources.items()},
        }
