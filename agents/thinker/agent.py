"""AgentPent Thinker Agent."""

from __future__ import annotations

from agents.base_agent import BaseAgent
from config.settings import settings


class ThinkerAgent(BaseAgent):
    """Deep reasoning agent for reviewing command decisions."""

    name = "thinker"
    description = "Derin Dusunur: planlari bastan uca analiz eder ve mantik hatalarini yakalar."

    def __init__(self):
        super().__init__()
        self.model = settings.thinking_model

    async def process_response(self, response: str, mission, memory):
        from agents.base_agent import AgentResult

        return AgentResult(agent_name=self.name, raw_response=response)
