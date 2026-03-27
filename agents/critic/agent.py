"""AgentPent — Critic Agent."""

import json
from agents.base_agent import BaseAgent

class CriticAgent(BaseAgent):
    """Şeytanın Avukatı: Kararları eleştirir ve onaylar."""
    name = "critic"
    description = "Şeytanın Avukatı: Kararları eleştirir ve onaylar."

    def __init__(self):
        super().__init__()

    def _parse_output(self, raw_text: str) -> None:
        """Sadece validate eder, state'e kaydetmez."""
        try:
            # Sadece geçerli JSON olup olmadığına bakar
            json.loads(raw_text)
        except json.JSONDecodeError:
            pass

    async def process_response(self, response: str, mission, memory):
        from agents.base_agent import AgentResult
        return AgentResult(agent_name=self.name, raw_response=response)
