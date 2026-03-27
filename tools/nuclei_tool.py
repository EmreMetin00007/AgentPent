"""AgentPent — Nuclei Tool Wrapper.

Template-based vulnerability scanner. JSONL çıktısını
parse ederek Finding nesneleri üretir.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult
from config.settings import settings

logger = logging.getLogger("agentpent.tools.nuclei")

# Severity mapping: nuclei → AgentPent
SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "info": "INFO",
    "unknown": "INFO",
}


class NucleiTool(BaseTool):
    """Nuclei vulnerability scanner wrapper'ı."""

    name = "nuclei"
    binary = "nuclei"
    description = "Template-based vulnerability scanner"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        templates = params.get("templates")
        severity = params.get("severity")
        rate_limit = params.get("rate_limit", int(settings.rate_limit_rps))
        extra_flags: List[str] = params.get("extra_flags", [])
        timeout = params.get("timeout", 900)

        # Komut oluştur
        args = [self.binary]
        args.extend(["-target", target])
        args.extend(["-jsonl"])  # JSONL çıktı
        args.extend(["-silent"])
        args.extend(["-rate-limit", str(rate_limit)])

        if templates:
            if isinstance(templates, list):
                for t in templates:
                    args.extend(["-tags", t])
            else:
                args.extend(["-tags", str(templates)])

        if severity:
            if isinstance(severity, list):
                args.extend(["-severity", ",".join(severity)])
            else:
                args.extend(["-severity", str(severity)])

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Nuclei JSONL çıktısını parse et."""
        findings: List[Dict[str, Any]] = []
        stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            sev = item.get("info", {}).get("severity", "info").lower()
            stats[sev] = stats.get(sev, 0) + 1

            finding = {
                "template_id": item.get("template-id", ""),
                "template_name": item.get("info", {}).get("name", ""),
                "severity": SEVERITY_MAP.get(sev, "INFO"),
                "host": item.get("host", ""),
                "matched_at": item.get("matched-at", ""),
                "matcher_name": item.get("matcher-name", ""),
                "description": item.get("info", {}).get("description", ""),
                "reference": item.get("info", {}).get("reference", []),
                "tags": item.get("info", {}).get("tags", []),
                "curl_command": item.get("curl-command", ""),
                "extracted_results": item.get("extracted-results", []),
                "cve_ids": _extract_cves(item),
            }
            findings.append(finding)

        return {
            "findings": findings,
            "stats": stats,
            "total": len(findings),
        }


def _extract_cves(item: Dict) -> List[str]:
    """Nuclei sonucundan CVE ID'lerini çıkar."""
    cves = []
    # classification alanından
    classification = item.get("info", {}).get("classification", {})
    if classification:
        cve_id = classification.get("cve-id")
        if cve_id:
            if isinstance(cve_id, list):
                cves.extend(cve_id)
            else:
                cves.append(str(cve_id))
    # tags'ten
    tags = item.get("info", {}).get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.upper().startswith("CVE-"):
                cves.append(tag.upper())
    return list(set(cves))
