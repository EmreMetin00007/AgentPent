"""AgentPent — Metasploit Tool Wrapper.

msfconsole üzerinden exploit çalıştırma.
CRITICAL seviyeli exploitlerde operatör onayı gerektirir.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.metasploit")


class MetasploitTool(BaseTool):
    """Metasploit Framework wrapper'ı."""

    name = "metasploit"
    binary = "msfconsole"
    description = "Metasploit Framework — exploit çalıştırma"

    # Operatör onayı gerektiren modüller
    REQUIRES_APPROVAL = True

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        module = params.get("module", "")
        options = params.get("options", {})
        payload = params.get("payload")
        check_only = params.get("check_only", True)
        timeout = params.get("timeout", 300)

        if not module:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Metasploit modülü belirtilmedi",
            )

        # Komut dizisi oluştur
        commands = self._build_commands(module, options, payload, check_only)
        rc_commands = "; ".join(commands)

        args = [self.binary, "-q", "-x", rc_commands]

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)
            result.parsed_data["module"] = module
            result.parsed_data["check_only"] = check_only

        return result

    def _build_commands(
        self,
        module: str,
        options: Dict[str, str],
        payload: Optional[str],
        check_only: bool,
    ) -> List[str]:
        """msfconsole komut dizisi oluştur."""
        cmds = ["use {}".format(module)]

        for key, value in options.items():
            cmds.append("set {} {}".format(key, value))

        if payload:
            cmds.append("set PAYLOAD {}".format(payload))

        if check_only:
            cmds.append("check")
        else:
            cmds.append("exploit -z")  # -z: background session

        cmds.append("exit")
        return cmds

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Metasploit çıktısını parse et."""
        data: Dict[str, Any] = {
            "vulnerable": False,
            "session_opened": False,
            "session_type": "",
            "session_id": None,
            "exploit_result": "unknown",
            "details": [],
        }

        lines = raw.splitlines()
        for line in lines:
            line_clean = line.strip()

            # Vulnerable kontrolü
            if re.search(r"\[\+\].*(?:vulnerable|is vulnerable)", line_clean, re.IGNORECASE):
                data["vulnerable"] = True
                data["exploit_result"] = "vulnerable"

            # Not vulnerable
            if re.search(r"\[-\].*(?:not vulnerable|safe)", line_clean, re.IGNORECASE):
                data["exploit_result"] = "not_vulnerable"

            # Session açıldı
            session_match = re.search(
                r"\[\*\].*(?:session|shell)\s+(\d+)\s+opened",
                line_clean, re.IGNORECASE,
            )
            if session_match:
                data["session_opened"] = True
                data["session_id"] = int(session_match.group(1))

            # Meterpreter session
            if "meterpreter" in line_clean.lower():
                data["session_type"] = "meterpreter"
            elif "command shell" in line_clean.lower():
                data["session_type"] = "shell"

            # Exploit tamamlandı
            if re.search(r"\[\+\].*exploit completed", line_clean, re.IGNORECASE):
                data["exploit_result"] = "success"

            # Exploit başarısız
            if re.search(r"\[-\].*(?:exploit failed|exploit completed.*no session)", line_clean, re.IGNORECASE):
                data["exploit_result"] = "failed"

            # Önemli bilgiler
            if line_clean.startswith("[+]") or line_clean.startswith("[*]"):
                data["details"].append(line_clean)

        return data

    def build_exploit_summary(self, parsed: Dict[str, Any]) -> str:
        """Exploit sonucunun kısa özetini oluştur."""
        module = parsed.get("module", "unknown")
        result = parsed.get("exploit_result", "unknown")

        if parsed.get("session_opened"):
            return "✅ {} — Session #{} ({}) açıldı".format(
                module, parsed["session_id"], parsed["session_type"]
            )
        elif parsed.get("vulnerable"):
            return "⚠️ {} — Hedef vulnerable (exploit çalıştırılmadı)".format(module)
        elif result == "failed":
            return "❌ {} — Exploit başarısız".format(module)
        elif result == "not_vulnerable":
            return "🛡️ {} — Hedef vulnerable değil".format(module)
        else:
            return "❓ {} — Sonuç belirsiz".format(module)
