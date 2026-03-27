"""AgentPent — FFUF Tool Wrapper.

Hızlı web fuzzer — dizin/dosya keşfi, vhost ve parametre fuzzing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.ffuf")

# Varsayılan wordlist yolları (platformdan bağımsız kontrol)
DEFAULT_WORDLISTS = {
    "dir": "/usr/share/wordlists/dirb/common.txt",
    "vhost": "/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt",
    "param": "/usr/share/wordlists/seclists/Discovery/Web-Content/burp-parameter-names.txt",
}


class FFUFTool(BaseTool):
    """FFUF — hızlı web fuzzer wrapper'ı."""

    name = "ffuf"
    binary = "ffuf"
    description = "Web fuzzing — dizin keşfi, vhost, parametre fuzzing"

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        wordlist = params.get("wordlist", DEFAULT_WORDLISTS.get("dir", ""))
        mode = params.get("mode", "dir")
        extensions = params.get("extensions")
        filter_status = params.get("filter_status", "404")
        filter_size = params.get("filter_size")
        threads = params.get("threads", 40)
        timeout = params.get("timeout", 300)
        extra_flags: List[str] = params.get("extra_flags", [])

        args = [self.binary]
        args.extend(["-u", target])
        args.extend(["-w", wordlist])
        args.extend(["-of", "json"])  # JSON çıktı
        args.extend(["-o", "/dev/stdout"])  # stdout'a yaz
        args.extend(["-t", str(threads)])
        args.extend(["-mc", "all"])  # Tüm status kodlarını eşle

        if filter_status:
            args.extend(["-fc", str(filter_status)])

        if filter_size:
            args.extend(["-fs", str(filter_size)])

        if extensions:
            args.extend(["-e", str(extensions)])

        # Mod bazlı ayarlar
        if mode == "vhost":
            args.extend(["-H", "Host: FUZZ.{}".format(
                target.replace("http://", "").replace("https://", "").split("/")[0]
            )])

        args.extend(extra_flags)

        result = await self.run_command(args, timeout=timeout)

        if result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """FFUF JSON çıktısını parse et."""
        data: Dict[str, Any] = {
            "results": [],
            "total": 0,
            "config": {},
        }

        try:
            output = json.loads(raw)
        except json.JSONDecodeError:
            # JSON olmayan çıktıyı satır satır dene
            return self._parse_text_output(raw)

        data["config"] = {
            "url": output.get("commandline", ""),
        }

        results = output.get("results", [])
        parsed_results: List[Dict[str, Any]] = []

        for item in results:
            entry = {
                "url": item.get("url", ""),
                "input": item.get("input", {}).get("FUZZ", ""),
                "status": item.get("status", 0),
                "length": item.get("length", 0),
                "words": item.get("words", 0),
                "lines": item.get("lines", 0),
                "content_type": item.get("content-type", ""),
                "redirect_location": item.get("redirectlocation", ""),
                "duration_ms": item.get("duration", 0),
            }
            parsed_results.append(entry)

        data["results"] = parsed_results
        data["total"] = len(parsed_results)

        # Status bazlı grupla
        status_groups: Dict[int, List[str]] = {}
        for r in parsed_results:
            sc = r["status"]
            status_groups.setdefault(sc, []).append(r["input"])
        data["status_groups"] = status_groups

        return data

    def _parse_text_output(self, raw: str) -> Dict[str, Any]:
        """Düz metin çıktısını parse et (fallback)."""
        import re
        results = []
        for line in raw.splitlines():
            # Tipik FFUF çıktı formatı: [Status XXX, Size YYYY, ...]
            match = re.search(
                r"(\S+)\s+\[Status:\s*(\d+),\s*Size:\s*(\d+)", line
            )
            if match:
                results.append({
                    "input": match.group(1),
                    "status": int(match.group(2)),
                    "length": int(match.group(3)),
                })
        return {"results": results, "total": len(results)}
