"""AgentPent — httpx Tool Wrapper.

Hızlı HTTP/HTTPS probing ve teknoloji tespiti.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.httpx")


class HttpxTool(BaseTool):
    """httpx — hızlı web probing wrapper'ı."""

    name = "httpx"
    binary = "httpx"
    description = "HTTP/HTTPS probing ve teknoloji tespiti"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        tech_detect = params.get("tech_detect", True)
        status_code = params.get("status_code", True)
        title = params.get("title", True)
        follow_redirects = params.get("follow_redirects", True)
        timeout = params.get("timeout", 120)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = [self.binary]

        # Hedef (tekil veya liste)
        if isinstance(target, list):
            for t in target:
                args.extend(["-u", t])
        else:
            args.extend(["-u", target])

        args.extend(["-json", "-silent"])

        if tech_detect:
            args.append("-tech-detect")
        if status_code:
            args.append("-status-code")
        if title:
            args.append("-title")
        if follow_redirects:
            args.append("-follow-redirects")

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """httpx JSON çıktısını parse et."""
        results: List[Dict[str, Any]] = []

        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry = {
                "url": item.get("url", ""),
                "status_code": item.get("status_code", 0),
                "title": item.get("title", ""),
                "content_length": item.get("content_length", 0),
                "content_type": item.get("content_type", ""),
                "host": item.get("host", ""),
                "technologies": item.get("tech", []),
                "webserver": item.get("webserver", ""),
                "response_time": item.get("response_time", ""),
                "tls": {
                    "version": item.get("tls", {}).get("version", "") if isinstance(item.get("tls"), dict) else "",
                    "cipher": item.get("tls", {}).get("cipher", "") if isinstance(item.get("tls"), dict) else "",
                },
                "cdn": item.get("cdn", False),
                "method": item.get("method", "GET"),
            }
            results.append(entry)

        return {
            "results": results,
            "total": len(results),
            "live_hosts": [r["url"] for r in results if 200 <= r.get("status_code", 0) < 400],
        }
