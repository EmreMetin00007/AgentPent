"""AgentPent — LinPEAS / WinPEAS Tool Wrapper.

Privilege escalation enumeration aracı.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.linpeas")

# Renk kodlarını temizle
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class LinPEASTool(BaseTool):
    """LinPEAS/WinPEAS — privilege escalation enumeration wrapper'ı."""

    name = "linpeas"
    binary = "linpeas.sh"
    description = "Privilege escalation enumeration (Linux/Windows)"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        platform = params.get("platform", "linux")
        intensity = params.get("intensity", "quick")
        timeout = params.get("timeout", 600)
        extra_flags: List[str] = params.get("extra_flags", [])

        if platform == "windows":
            self.binary = "winPEASx64.exe"
            args = [self.binary]
        else:
            self.binary = "linpeas.sh"
            args = ["bash", self.binary]
            if intensity == "quick":
                args.append("-a")

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """LinPEAS çıktısını parse et."""
        clean = _ANSI_RE.sub("", raw)
        data: Dict[str, Any] = {
            "suid_binaries": [],
            "writable_dirs": [],
            "cron_jobs": [],
            "credentials": [],
            "interesting_files": [],
            "kernel_exploits": [],
            "capabilities": [],
            "network_info": [],
            "highlights": [],
        }

        section = ""
        for line in clean.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            # Seksiyon tespiti
            if "SUID" in stripped.upper():
                section = "suid"
            elif "CRON" in stripped.upper() or "TIMER" in stripped.upper():
                section = "cron"
            elif "WRITABLE" in stripped.upper():
                section = "writable"
            elif "PASSWORD" in stripped.upper() or "CREDENTIAL" in stripped.upper():
                section = "creds"
            elif "CAPABILITIES" in stripped.upper():
                section = "caps"
            elif "INTERESTING" in stripped.upper() and "FILE" in stripped.upper():
                section = "files"
            elif "KERNEL" in stripped.upper() and "EXPLOIT" in stripped.upper():
                section = "kernel"
            elif stripped.startswith("═") or stripped.startswith("╔"):
                continue

            # İçerik okuma
            if section == "suid" and stripped.startswith("/"):
                data["suid_binaries"].append(stripped.split()[0])
            elif section == "cron" and ("*" in stripped or "/" in stripped):
                data["cron_jobs"].append(stripped)
            elif section == "writable" and stripped.startswith("/"):
                data["writable_dirs"].append(stripped.split()[0])
            elif section == "creds":
                if re.search(r"(?:password|passwd|pwd|secret|token|key)\s*[=:]", stripped, re.I):
                    data["credentials"].append(stripped[:200])
            elif section == "caps" and "cap_" in stripped.lower():
                data["capabilities"].append(stripped)
            elif section == "files" and stripped.startswith("/"):
                data["interesting_files"].append(stripped.split()[0])
            elif section == "kernel":
                data["kernel_exploits"].append(stripped)

            # Yüksek risk öğeleri (95%+ / kırmızı highlight)
            if "95%" in stripped or "99%" in stripped or "HIGH" in stripped.upper():
                data["highlights"].append(stripped[:200])

        # Deduplicate
        for key in data:
            if isinstance(data[key], list):
                data[key] = sorted(set(data[key]))

        return data
