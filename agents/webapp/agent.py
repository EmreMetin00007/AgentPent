"""AgentPent — WebApp Agent.

Web uygulama güvenlik testi — SQLi, XSS, dizin keşfi.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from agents.webapp.tools import setup_webapp_tools
from core.llm_client import llm
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity

logger = logging.getLogger("agentpent.agents.webapp")


class WebAppAgent(BaseAgent):
    """Web Uygulama Güvenlik agent'ı."""

    name = "webapp"
    description = "Web app güvenlik testi — SQLi, XSS, dizin keşfi, web vuln tarama"
    phase = AttackPhase.VULNERABILITY_ANALYSIS
    model = None

    def __init__(self):
        super().__init__()
        setup_webapp_tools(self)

    async def run(
        self,
        task: str,
        mission: Mission,
        memory: ConversationMemory,
        context: str = "",
    ) -> AgentResult:
        logger.info("[%s] Görev başlatıldı: %s", self.name, task[:100])
        memory.add_user(task, agent=self.name, phase=self.phase.value)

        # 1. Browser Vision entegrasyonu (Arayüz analizi ve Ekran Görüntüsü)
        vision_images = []
        vision_context_parts = []
        browser = self.get_tool("browser_vision")
        if browser:
            for target in mission.target_scope:
                logger.info("[webapp] Browser Vision çalışıyor: %s", target)
                res = await browser.execute({"url": target})
                if res.success and "image_base64" in res.parsed_data:
                    vision_images.append(res.parsed_data["image_base64"])
                    vision_context_parts.append(res.stdout)
        
        if vision_context_parts:
            context += "\n\n## 👁️ Browser Vision Analizi:\n" + "\n---\n".join(vision_context_parts)

        # 2. Bağlamı oluştur
        full_context = self._build_context(mission, context)

        # 3. LLM'e (Vision API ile) gönder
        response = await llm.agent_call(
            agent_system_prompt=self.system_prompt,
            task=task,
            context=full_context,
            model=self.model,
            images=vision_images if vision_images else None,
        )

        memory.add_assistant(response, agent=self.name, phase=self.phase.value)
        result = await self.process_response(response, mission, memory)
        logger.info(
            "[%s] Tamamlandı — %d bulgu", self.name, len(result.findings),
        )
        return result

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        """LLM yanıtından web app bulgularını çıkar."""
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = self._extract_json(response)

        if parsed:
            for f_data in parsed.get("findings", []):
                try:
                    finding = Finding(
                        title=f_data.get("title", "WebApp Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        port=f_data.get("port"),
                        service=f_data.get("service"),
                        description=f_data.get("description", ""),
                        evidence=f_data.get("evidence", ""),
                        cve_ids=f_data.get("cve_ids", []),
                        exploitable=f_data.get("exploitable", False),
                        remediation=f_data.get("remediation", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    )
                    findings.append(finding)
                except Exception as exc:
                    logger.warning("Finding oluşturma hatası: %s", exc)

            discovered = parsed.get("discovered_paths", [])
            tool_outputs["discovered_paths"] = json.dumps(
                discovered, ensure_ascii=False
            )
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
        """Web app testlerini sırayla çalıştır."""
        results: Dict[str, Any] = {}

        for target in mission.target_scope:
            target_results: Dict[str, Any] = {}

            # 1. FFUF — dizin keşfi
            ffuf = self.get_tool("ffuf")
            if ffuf:
                logger.info("[webapp] FFUF dizin keşfi: %s", target)
                url = target if "://" in target else "http://{}".format(target)
                ffuf_result = await ffuf.execute({
                    "target": "{}/FUZZ".format(url.rstrip("/")),
                    "wordlist": "/usr/share/wordlists/dirb/common.txt",
                    "mode": "dir",
                })
                target_results["ffuf"] = ffuf_result.parsed_data

            # 2. Nikto — genel web vuln scan
            nikto = self.get_tool("nikto")
            if nikto:
                logger.info("[webapp] Nikto scan: %s", target)
                nikto_result = await nikto.execute({"target": target})
                target_results["nikto"] = nikto_result.parsed_data

            # 3. SQLMap — SQL injection (bulunan dizinlerde)
            sqlmap = self.get_tool("sqlmap")
            if sqlmap:
                url = target if "://" in target else "http://{}".format(target)
                logger.info("[webapp] SQLMap: %s", url)
                sql_result = await sqlmap.execute({
                    "target": url,
                    "level": 2,
                    "risk": 1,
                })
                target_results["sqlmap"] = sql_result.parsed_data

            # 4. XSStrike — XSS
            xsstrike = self.get_tool("xsstrike")
            if xsstrike:
                url = target if "://" in target else "http://{}".format(target)
                logger.info("[webapp] XSStrike: %s", url)
                xss_result = await xsstrike.execute({"target": url})
                target_results["xsstrike"] = xss_result.parsed_data

            results[target] = target_results

        return results

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
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
