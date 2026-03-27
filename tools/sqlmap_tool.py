"""AgentPent — SQLMap Tool Wrapper.

Otomatik SQL injection tespiti ve exploit.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.sqlmap")


class SQLMapTool(BaseTool):
    """SQLMap — otomatik SQL injection wrapper'ı."""

    name = "sqlmap"
    binary = "sqlmap"
    description = "Otomatik SQL injection tespiti ve exploit"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        method = params.get("method", "GET")
        data = params.get("data")
        level = params.get("level", 1)
        risk = params.get("risk", 1)
        technique = params.get("technique")
        dbs = params.get("dbs", False)
        tables = params.get("tables")
        dump = params.get("dump", False)
        timeout = params.get("timeout", 600)
        extra_flags: List[str] = params.get("extra_flags", [])

        # Geçici çıktı dizini
        output_dir = tempfile.mkdtemp(prefix="agentpent_sqlmap_")

        args = [self.binary]
        args.extend(["-u", target])
        args.extend(["--batch"])  # Otomatik mod
        args.extend(["--level", str(level)])
        args.extend(["--risk", str(risk)])
        args.extend(["--output-dir", output_dir])
        args.extend(["--flush-session"])

        if method.upper() == "POST" and data:
            args.extend(["--method", "POST"])
            args.extend(["--data", data])

        if technique:
            args.extend(["--technique", str(technique)])

        if dbs:
            args.append("--dbs")
        if tables:
            args.extend(["--tables", "-D", str(tables)])
        if dump:
            args.append("--dump")

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)
            result.parsed_data["output_dir"] = output_dir

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """SQLMap çıktısını parse et."""
        data: Dict[str, Any] = {
            "injectable": False,
            "injection_types": [],
            "databases": [],
            "tables": [],
            "backend_dbms": "",
            "web_server": "",
            "parameters": [],
        }

        # Injectable parametre tespiti
        injectable_pattern = re.compile(
            r"Parameter:\s+(.+?)\s+\((.+?)\)", re.IGNORECASE
        )
        for match in injectable_pattern.finditer(raw):
            param_name = match.group(1).strip()
            inject_type = match.group(2).strip()
            data["injectable"] = True
            data["parameters"].append({
                "name": param_name,
                "type": inject_type,
            })
            if inject_type not in data["injection_types"]:
                data["injection_types"].append(inject_type)

        # Backend DBMS
        dbms_match = re.search(
            r"back-end DBMS:\s*(.+)", raw, re.IGNORECASE
        )
        if dbms_match:
            data["backend_dbms"] = dbms_match.group(1).strip()

        # Web server
        ws_match = re.search(
            r"web (?:server|application) technology:\s*(.+)",
            raw, re.IGNORECASE,
        )
        if ws_match:
            data["web_server"] = ws_match.group(1).strip()

        # Veritabanları
        db_section = re.search(
            r"available databases.*?:\s*\n((?:\[\*\]\s+.+\n)+)",
            raw, re.IGNORECASE,
        )
        if db_section:
            for db_match in re.finditer(r"\[\*\]\s+(.+)", db_section.group(1)):
                data["databases"].append(db_match.group(1).strip())

        # Tablolar
        table_matches = re.findall(
            r"\|\s+(\S+)\s+\|", raw
        )
        if table_matches:
            data["tables"] = list(set(table_matches))

        return data
