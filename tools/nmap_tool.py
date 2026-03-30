"""AgentPent — Nmap Tool Wrapper.

Port/servis tarama aracı. XML çıktısını parse ederek
yapılandırılmış veri döner.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.nmap")

# ── Tarama Profilleri ────────────────────────────────────

SCAN_PROFILES: Dict[str, List[str]] = {
    "quick": ["-Pn", "-T4", "-F", "--open"],
    "full": ["-Pn", "-T4", "--top-ports", "5000", "-sV", "--open"],
    "service": ["-Pn", "-sV", "-sC", "--open"],
    "vuln": ["-Pn", "-sV", "--script=vuln", "--open"],
    "stealth": ["-Pn", "-sS", "-T3", "--open"],
    "udp": ["-Pn", "-sU", "-T4", "--top-ports", "50", "--open"],
}

PROTECTED_SCAN_TYPES = {"quick", "service", "vuln"}


def _is_full_range_ports(value: str) -> bool:
    normalized = value.replace(" ", "")
    return normalized in {"1-65535", "1-65534", "1-65536"}


class NmapTool(BaseTool):
    """Nmap port/servis tarama wrapper'ı."""

    name = "nmap"
    binary = "nmap"
    description = "Port ve servis tarama aracı"

    @staticmethod
    def _sanitize_extra_flags(scan_type: str, extra_flags: List[str]) -> List[str]:
        sanitized: List[str] = []
        idx = 0

        while idx < len(extra_flags):
            flag = str(extra_flags[idx]).strip()
            if not flag:
                idx += 1
                continue

            if scan_type in PROTECTED_SCAN_TYPES:
                if flag in {"-O", "--osscan-guess", "-p-", "--script-trace"}:
                    idx += 1
                    continue

                if flag in {"-p", "--top-ports", "--script"}:
                    idx += 2 if idx + 1 < len(extra_flags) else 1
                    continue

                if flag.startswith("--script="):
                    idx += 1
                    continue

                if flag.startswith("-p") and _is_full_range_ports(flag[2:]):
                    raise ValueError("Korunan scan tiplerinde tam port aralığı override edilemez")

            sanitized.append(flag)
            idx += 1

        return sanitized

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        target = params["target"]
        scan_type = params.get("scan_type", "quick")
        ports = params.get("ports")
        extra_flags: List[str] = params.get("extra_flags", [])
        timeout = params.get("timeout", 180)  # 3 dakika — T4 ile yeterli

        if scan_type in {"service", "vuln"} and not ports:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="'service' ve 'vuln' scan_type için explicit ports gerekli.",
            )

        if scan_type in PROTECTED_SCAN_TYPES and ports and _is_full_range_ports(str(ports)):
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Korunan scan tiplerinde tam port aralığı kullanılamaz.",
            )

        try:
            extra_flags = self._sanitize_extra_flags(scan_type, extra_flags)
        except ValueError as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )

        # Komut oluştur
        args = [self.binary]
        args.extend(SCAN_PROFILES.get(scan_type, SCAN_PROFILES["quick"]))

        if ports:
            args.extend(["-p", str(ports)])

        # XML çıktısını stdout'a yaz
        args.extend(["-oX", "-"])

        args.extend(extra_flags)
        args.append(target)

        result = await self.run_command(args, timeout=timeout)

        if result.success and result.stdout:
            result.parsed_data = self.parse_output(result.stdout)

        return result

    def parse_output(self, raw: str) -> Dict[str, Any]:
        """Nmap XML çıktısını parse et."""
        data: Dict[str, Any] = {"hosts": [], "scan_info": {}}

        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            logger.warning("Nmap XML parse hatası — ham çıktı kullanılıyor")
            return {"raw": raw[:5000]}

        # Scan bilgisi
        scan_info = root.find("scaninfo")
        if scan_info is not None:
            data["scan_info"] = {
                "type": scan_info.get("type", ""),
                "protocol": scan_info.get("protocol", ""),
                "services": scan_info.get("services", ""),
            }

        # Host bilgileri
        for host_el in root.findall("host"):
            host_data: Dict[str, Any] = {"addresses": [], "ports": [], "hostnames": []}

            # Adresler
            for addr in host_el.findall("address"):
                host_data["addresses"].append({
                    "addr": addr.get("addr", ""),
                    "type": addr.get("addrtype", ""),
                })

            # Hostname'ler
            hostnames_el = host_el.find("hostnames")
            if hostnames_el is not None:
                for hn in hostnames_el.findall("hostname"):
                    host_data["hostnames"].append(hn.get("name", ""))

            # Status
            status = host_el.find("status")
            if status is not None:
                host_data["status"] = status.get("state", "unknown")

            # Portlar
            ports_el = host_el.find("ports")
            if ports_el is not None:
                for port_el in ports_el.findall("port"):
                    port_info: Dict[str, Any] = {
                        "port": int(port_el.get("portid", 0)),
                        "protocol": port_el.get("protocol", "tcp"),
                    }
                    state = port_el.find("state")
                    if state is not None:
                        port_info["state"] = state.get("state", "")

                    service = port_el.find("service")
                    if service is not None:
                        port_info["service"] = {
                            "name": service.get("name", ""),
                            "product": service.get("product", ""),
                            "version": service.get("version", ""),
                            "extra": service.get("extrainfo", ""),
                        }

                    # Script çıktıları
                    scripts = []
                    for script_el in port_el.findall("script"):
                        scripts.append({
                            "id": script_el.get("id", ""),
                            "output": script_el.get("output", ""),
                        })
                    if scripts:
                        port_info["scripts"] = scripts

                    host_data["ports"].append(port_info)

            data["hosts"].append(host_data)

        # OS Detection
        for host_el in root.findall("host"):
            os_el = host_el.find("os")
            if os_el is not None:
                os_matches = []
                for match in os_el.findall("osmatch"):
                    os_matches.append({
                        "name": match.get("name", ""),
                        "accuracy": match.get("accuracy", ""),
                    })
                if os_matches:
                    # İlk host'a ekle (basitleştirilmiş)
                    if data["hosts"]:
                        data["hosts"][0]["os_matches"] = os_matches

        return data
