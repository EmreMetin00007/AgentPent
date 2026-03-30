"""AgentPent - httpx Tool Wrapper.

Fast HTTP/HTTPS probing with a resilient urllib fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List
from urllib.parse import urlparse

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.httpx")


class HttpxTool(BaseTool):
    """httpx fast probing wrapper."""

    name = "httpx"
    binary = "httpx"
    description = "HTTP/HTTPS probing ve teknoloji tespiti"

    async def is_available(self) -> bool:
        """Allow the built-in urllib fallback even when the CLI is missing."""
        return True

    @staticmethod
    def _looks_like_url(target: str) -> bool:
        return target.startswith("http://") or target.startswith("https://")

    @staticmethod
    def _has_explicit_port(target: str) -> bool:
        if "://" in target:
            host_part = target.split("://", 1)[1].split("/", 1)[0]
        else:
            host_part = target.split("/", 1)[0]
        if host_part.startswith("["):
            return "]:" in host_part
        return host_part.count(":") == 1

    @classmethod
    def _build_probe_targets(cls, target: Any) -> List[str]:
        if isinstance(target, list):
            probe_targets: List[str] = []
            for item in target:
                probe_targets.extend(cls._build_probe_targets(item))
            return list(dict.fromkeys(probe_targets))

        raw_target = str(target).strip().rstrip("/")
        if not raw_target:
            return []

        if cls._looks_like_url(raw_target):
            return [raw_target]

        candidates = [
            f"http://{raw_target}",
            f"https://{raw_target}",
        ]
        if not cls._has_explicit_port(raw_target):
            candidates.extend([
                f"http://{raw_target}:8080",
                f"https://{raw_target}:8443",
                f"http://{raw_target}:3128",
            ])
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _extract_title(body: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return re.sub(r"\s+", " ", match.group(1)).strip()[:200]

    @staticmethod
    def _looks_like_proxy(status: int, headers: Dict[str, str], body: str) -> bool:
        header_keys = {key.lower(): value for key, value in headers.items()}
        body_lower = body.lower()
        indicators = [
            status == 407,
            "proxy-agent" in header_keys,
            "via" in header_keys,
            "forwarded" in header_keys,
            "proxy authentication required" in body_lower,
            "this is a proxy server" in body_lower,
            "squid" in body_lower,
            "proxy error" in body_lower,
        ]
        return any(indicators)

    @classmethod
    def _probe_url(cls, url: str, timeout: int) -> Dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AgentPent-httpx-fallback/1.0"},
            method="GET",
        )
        context = ssl._create_unverified_context()
        start = time.monotonic()

        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                status = response.status
                headers = dict(response.headers)
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            headers = dict(exc.headers)
            body = exc.read().decode("utf-8", errors="replace")
        except Exception as exc:
            return {"url": url, "error": str(exc)}

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        content_type = headers.get("Content-Type", "")
        parsed_url = urlparse(url)

        return {
            "url": url,
            "status_code": status,
            "title": cls._extract_title(body),
            "content_length": len(body),
            "content_type": content_type,
            "host": parsed_url.hostname or "",
            "technologies": [],
            "webserver": headers.get("Server", ""),
            "response_time": f"{elapsed_ms}ms",
            "tls": {"version": "", "cipher": ""},
            "cdn": False,
            "method": "GET",
            "looks_like_proxy": cls._looks_like_proxy(status, headers, body),
        }

    async def _fallback_probe(self, probe_targets: List[str], timeout: int) -> ToolResult:
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        loop = asyncio.get_running_loop()

        for url in probe_targets:
            probe_result = await loop.run_in_executor(None, self._probe_url, url, timeout)
            if probe_result.get("error"):
                errors.append({
                    "url": url,
                    "error": probe_result["error"],
                })
                continue
            results.append(probe_result)

        stdout_lines = [json.dumps(item, ensure_ascii=False) for item in results]
        if errors:
            stdout_lines.append("")
            stdout_lines.append("## Fallback Errors")
            for item in errors:
                stdout_lines.append(f"{item['url']}: {item['error']}")

        live_hosts = [
            item["url"]
            for item in results
            if 200 <= item.get("status_code", 0) < 500
        ]

        return ToolResult(
            tool_name=self.name,
            command="httpx-fallback " + " ".join(probe_targets),
            stdout="\n".join(stdout_lines),
            success=bool(results),
            error=None if results else "httpx fallback probing de başarısız oldu.",
            parsed_data={
                "results": results,
                "total": len(results),
                "live_hosts": live_hosts,
                "attempted_targets": probe_targets,
                "errors": errors,
            },
        )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        tech_detect = params.get("tech_detect", True)
        status_code = params.get("status_code", True)
        title = params.get("title", True)
        follow_redirects = params.get("follow_redirects", True)
        timeout = params.get("timeout", 120)
        extra_flags: List[str] = params.get("extra_flags", [])
        probe_targets = self._build_probe_targets(target)

        args = [self.binary]
        for probe_target in probe_targets:
            args.extend(["-u", probe_target])

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

        if result.success and result.stdout:
            result.parsed_data = self.parse_output(result.stdout)
            result.parsed_data["attempted_targets"] = probe_targets
            return result

        logger.warning(
            "[httpx] CLI probing basarisiz oldu, urllib fallback deneniyor: %s",
            result.error or result.stderr[:200],
        )
        fallback_result = await self._fallback_probe(probe_targets, timeout)
        if fallback_result.success:
            fallback_result.stderr = result.stderr
        return fallback_result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Parse projectdiscovery httpx JSON lines output."""
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
                "looks_like_proxy": self._looks_like_proxy(
                    item.get("status_code", 0),
                    item.get("header", {}) if isinstance(item.get("header"), dict) else {},
                    item.get("body_preview", "") or "",
                ),
            }
            results.append(entry)

        return {
            "results": results,
            "total": len(results),
            "live_hosts": [r["url"] for r in results if 200 <= r.get("status_code", 0) < 400],
        }
