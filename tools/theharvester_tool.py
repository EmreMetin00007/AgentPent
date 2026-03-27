"""AgentPent — theHarvester Tool Wrapper.

OSINT veri toplama — email, subdomain, IP.
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.theharvester")

DEFAULT_SOURCES = ["google", "bing", "crtsh", "dnsdumpster", "hackertarget"]


class TheHarvesterTool(BaseTool):
    """theHarvester — OSINT veri toplama wrapper'ı."""

    name = "theharvester"
    binary = "theHarvester"
    description = "Email, subdomain ve IP toplama (OSINT)"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        sources = params.get("sources", DEFAULT_SOURCES)
        limit = params.get("limit", 200)
        timeout = params.get("timeout", 300)
        extra_flags: List[str] = params.get("extra_flags", [])

        if isinstance(sources, list):
            source_str = ",".join(sources)
        else:
            source_str = str(sources)

        args = [self.binary]
        args.extend(["-d", target])
        args.extend(["-b", source_str])
        args.extend(["-l", str(limit)])

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """theHarvester metin çıktısını parse et."""
        data: Dict[str, Any] = {
            "emails": [],
            "hosts": [],
            "ips": [],
            "interesting_urls": [],
        }

        # Email adresleri
        email_pattern = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
        emails = set(email_pattern.findall(raw))
        data["emails"] = sorted(emails)

        # Hosts / subdomain'ler
        section = ""
        for line in raw.splitlines():
            line = line.strip()

            if "Hosts found" in line or "[*] Hosts found" in line:
                section = "hosts"
                continue
            elif "IPs found" in line or "[*] IPs found" in line:
                section = "ips"
                continue
            elif "Emails found" in line or "[*] Emails found" in line:
                section = "emails"
                continue
            elif "Interesting Urls" in line or "[*] Interesting Urls" in line:
                section = "urls"
                continue
            elif line.startswith("[*]") or line.startswith("-----"):
                section = ""
                continue

            if not line or line.startswith("["):
                continue

            if section == "hosts":
                # format: subdomain.example.com:IP
                parts = line.split(":")
                host = parts[0].strip()
                if "." in host:
                    data["hosts"].append(host)
                if len(parts) > 1:
                    ip = parts[1].strip()
                    if re.match(r"\d+\.\d+\.\d+\.\d+", ip):
                        data["ips"].append(ip)
            elif section == "ips":
                if re.match(r"\d+\.\d+\.\d+\.\d+", line):
                    data["ips"].append(line)
            elif section == "urls":
                if line.startswith("http"):
                    data["interesting_urls"].append(line)

        # Deduplicate
        data["hosts"] = sorted(set(data["hosts"]))
        data["ips"] = sorted(set(data["ips"]))
        data["interesting_urls"] = sorted(set(data["interesting_urls"]))

        return data
