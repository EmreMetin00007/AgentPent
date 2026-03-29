"""AgentPent — Reporter Agent.

Mission bulgularından profesyonel rapor üretir.
LLM ile executive summary ve risk değerlendirmesi oluşturur.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentResult, BaseAgent
from core.memory import ConversationMemory
from core.mission import AttackPhase, Finding, Mission, Severity
from core.report_generator import ReportGenerator, ReportData
from core.utils import extract_json_from_llm

logger = logging.getLogger("agentpent.agents.reporter")


class ReporterAgent(BaseAgent):
    """Raporlama agent'ı."""

    name = "reporter"
    description = "Raporlama — executive summary, risk değerlendirmesi, HTML/MD/JSON rapor üretimi"
    phase = AttackPhase.REPORTING
    model = None

    def __init__(self):
        super().__init__()
        self._generator = ReportGenerator()

    async def process_response(
        self,
        response: str,
        mission: Mission,
        memory: ConversationMemory,
    ) -> AgentResult:
        findings: List[Finding] = []
        tool_outputs: Dict[str, str] = {}
        next_actions: List[str] = []

        parsed = extract_json_from_llm(response)
        if parsed:
            executive_summary = parsed.get("executive_summary", "")
            risk_rating = parsed.get("risk_rating", "")
            remediation_priority = parsed.get("remediation_priority", [])

            tool_outputs["executive_summary"] = executive_summary
            tool_outputs["risk_rating"] = risk_rating
            tool_outputs["remediation_priority"] = json.dumps(
                remediation_priority, ensure_ascii=False
            )
            next_actions = parsed.get("next_recommendations", [])

            for f_data in parsed.get("findings", []):
                try:
                    findings.append(Finding(
                        title=f_data.get("title", "Rapor Bulgusu"),
                        severity=Severity(f_data.get("severity", "INFO").upper()),
                        target=f_data.get("target", ""),
                        description=f_data.get("description", ""),
                        agent_source=self.name,
                        phase=self.phase,
                    ))
                except Exception as exc:
                    logger.warning("Finding hatası: %s", exc)

        return AgentResult(
            agent_name=self.name,
            raw_response=response,
            findings=findings,
            tool_outputs=tool_outputs,
            next_actions=next_actions,
            success=True,
        )

    def generate_report(
        self,
        mission: Mission,
        format: str = "html",
        output_path: Optional[str] = None,
        executive_summary: str = "",
    ) -> str:
        """Rapor oluştur."""
        return self._generator.generate(
            mission=mission,
            format=format,
            output_path=output_path,
            executive_summary=executive_summary,
        )


