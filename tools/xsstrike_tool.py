"""AgentPent — XSStrike Tool Wrapper.

XSS zafiyet tespiti aracı.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.xsstrike")


class XSStrikeTool(BaseTool):
    """XSStrike — XSS zafiyet tespiti wrapper'ı."""

    name = "xsstrike"
    binary = "xsstrike"
    description = "XSS zafiyet tespiti ve analizi"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        crawl = params.get("crawl", False)
        params_list = params.get("params")
        data = params.get("data")
        timeout = params.get("timeout", 300)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = ["python3", "-m", "xsstrike"]
        args.extend(["-u", target])
        args.append("--skip")  # WAF bypass denemelerini atla

        if crawl:
            args.append("--crawl")

        if data:
            args.extend(["--data", str(data)])

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """XSStrike çıktısını parse et."""
        data: Dict[str, Any] = {
            "vulnerabilities": [],
            "waf_detected": False,
            "waf_name": "",
            "reflections": 0,
            "total_vulns": 0,
        }

        for line in raw.splitlines():
            line = line.strip()

            # WAF tespiti
            waf_match = re.search(r"WAF detected:\s*(.+)", line, re.IGNORECASE)
            if waf_match:
                data["waf_detected"] = True
                data["waf_name"] = waf_match.group(1).strip()

            # XSS bulundu
            if re.search(r"(?:XSS|Vulnerable|payload)", line, re.IGNORECASE):
                if "confidence" in line.lower() or "payload" in line.lower():
                    vuln = {
                        "type": "XSS",
                        "detail": line,
                    }
                    # Payload çıkar
                    payload_match = re.search(r"Payload:\s*(.+)", line, re.IGNORECASE)
                    if payload_match:
                        vuln["payload"] = payload_match.group(1).strip()

                    # Confidence
                    conf_match = re.search(r"Confidence:\s*(\d+)", line, re.IGNORECASE)
                    if conf_match:
                        vuln["confidence"] = int(conf_match.group(1))

                    data["vulnerabilities"].append(vuln)

            # Reflection sayısı
            ref_match = re.search(r"(\d+)\s+(?:reflection|parameter)", line, re.IGNORECASE)
            if ref_match:
                data["reflections"] = max(data["reflections"], int(ref_match.group(1)))

        data["total_vulns"] = len(data["vulnerabilities"])
        return data
