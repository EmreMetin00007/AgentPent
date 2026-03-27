"""AgentPent — Recon Agent.

Pasif ve aktif keşif. Subdomain, WHOIS, teknoloji stack,
ön port taraması gerçekleştirir.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.recon.tools import setup_recon_tools
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.recon")


class ReconAgent(BaseAgent):
    """Keşif (Reconnaissance) agent'ı."""

    name = "recon"
    description = "Pasif ve aktif keşif — subdomain, WHOIS, teknoloji stack, port ön tarama"
    phase = AttackPhase.RECONNAISSANCE
    model = None  # settings.default_model kullanılır

    def __init__(self):
        super().__init__()
        setup_recon_tools(self)

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        """LLM yanıtından bulguları ve araç çağrılarını çıkar."""
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        # JSON yanıtı parse et
        parsed = self._extract_json(response)

        if parsed:
            # Bulguları çıkar
            for f_data in parsed.get("findings", []):
                try:
                    finding = Finding(
                        title=f_data.get("title", "Keşif Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        agent_source=self.name,
                        phase=self.phase,
                        port=f_data.get("port"),
                        service=f_data.get("service"),
                    )
                    findings.append(finding)
                except Exception as exc:
                    logger.warning("Finding oluşturma hatası: %s", exc)

            # Araç çıktılarını kaydet
            for tc in parsed.get("tool_calls", []):
                tool_name = tc.get("tool", "unknown")
                tool_outputs[tool_name] = tc.get("result_summary", "")

            # Sonraki adım önerileri
            next_actions = parsed.get("next_recommendations", [])

        return AgentResult(
            agent_name=self.name,
            raw_response=response,
            findings=findings,
            tool_outputs=tool_outputs,
            next_actions=next_actions,
            success=True,
        )

    async def run_tools(self, mission: Mission) -> Dict[str, Any]:
        """Kayıtlı araçları sırayla çalıştır ve sonuçları topla."""
        results: Dict[str, Any] = {}

        for target in mission.target_scope:
            target_results: Dict[str, Any] = {}

            # 1. Subfinder — subdomain keşfi (sadece domain hedefler için)
            subfinder = self.get_tool("subfinder")
            if subfinder and not self._is_ip(target):
                logger.info("[recon] Subfinder: %s", target)
                sf_result = await subfinder.execute({"target": target})
                target_results["subdomains"] = sf_result.parsed_data
                if sf_result.success:
                    subdomains = sf_result.parsed_data.get("subdomains", [])
                    logger.info("[recon] %d subdomain bulundu", len(subdomains))

            # 2. WHOIS
            whois = self.get_tool("whois")
            if whois:
                logger.info("[recon] WHOIS: %s", target)
                wh_result = await whois.execute({"target": target})
                target_results["whois"] = wh_result.parsed_data

            # 3. httpx — web probing
            httpx = self.get_tool("httpx")
            if httpx:
                probe_targets = [target]
                # Subdomain'leri de ekle
                if "subdomains" in target_results:
                    subs = target_results["subdomains"].get("subdomains", [])
                    probe_targets.extend(subs[:20])  # İlk 20 subdomain
                logger.info("[recon] httpx: %d hedef", len(probe_targets))
                for pt in probe_targets:
                    hx_result = await httpx.execute({"target": pt})
                    target_results.setdefault("web_probes", []).append({
                        "target": pt,
                        "data": hx_result.parsed_data,
                    })

            # 4. Nmap quick scan
            nmap = self.get_tool("nmap")
            if nmap:
                logger.info("[recon] Nmap quick: %s", target)
                nm_result = await nmap.execute({
                    "target": target,
                    "scan_type": "quick",
                })
                target_results["nmap_quick"] = nm_result.parsed_data

            results[target] = target_results

        return results

    @staticmethod
    def _is_ip(target: str) -> bool:
        """Basit IP kontrolü."""
        parts = target.split(".")
        if len(parts) == 4:
            return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        return False

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """LLM yanıtından JSON bloğunu çıkar."""
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            else:
                return json.loads(text.strip())
        except (json.JSONDecodeError, IndexError):
            return None
