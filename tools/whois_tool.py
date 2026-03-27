"""AgentPent — WHOIS Tool Wrapper.

Domain/IP kayıt bilgisi sorgulama.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.whois")

# WHOIS alanlarını çıkarmak için regex pattern'ler
_PATTERNS = {
    "registrar": re.compile(r"Registrar:\s*(.+)", re.IGNORECASE),
    "creation_date": re.compile(r"Creat(?:ion|ed)\s*Date:\s*(.+)", re.IGNORECASE),
    "expiration_date": re.compile(r"Expir(?:ation|y)\s*Date:\s*(.+)", re.IGNORECASE),
    "updated_date": re.compile(r"Updated?\s*Date:\s*(.+)", re.IGNORECASE),
    "registrant_org": re.compile(r"Registrant\s*Organi[sz]ation:\s*(.+)", re.IGNORECASE),
    "registrant_country": re.compile(r"Registrant\s*Country:\s*(.+)", re.IGNORECASE),
    "dnssec": re.compile(r"DNSSEC:\s*(.+)", re.IGNORECASE),
    "status": re.compile(r"(?:Domain\s*)?Status:\s*(.+)", re.IGNORECASE),
}

_NS_PATTERN = re.compile(r"Name\s*Server:\s*(.+)", re.IGNORECASE)


class WhoisTool(BaseTool):
    """WHOIS sorgulama wrapper'ı."""

    name = "whois"
    binary = "whois"
    description = "Domain/IP WHOIS kayıt bilgisi sorgulama"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        timeout = params.get("timeout", 30)

        args = [self.binary, target]

        result = await self.run_command(args, timeout=timeout)

        if result.success and result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """WHOIS çıktısını parse et."""
        data: Dict[str, Any] = {}

        # Tekil alanlar
        for field_name, pattern in _PATTERNS.items():
            match = pattern.search(raw)
            if match:
                value = match.group(1).strip()
                if field_name == "status":
                    # Status birden çok satırda olabilir
                    statuses = pattern.findall(raw)
                    data[field_name] = [s.strip() for s in statuses]
                else:
                    data[field_name] = value

        # Name server'lar
        ns_matches = _NS_PATTERN.findall(raw)
        if ns_matches:
            data["nameservers"] = sorted(
                set(ns.strip().lower() for ns in ns_matches)
            )

        # Email adresleri
        emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw))
        if emails:
            data["emails"] = sorted(emails)

        return data
