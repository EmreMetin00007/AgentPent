"""AgentPent — Thinker Agent."""

import json
from agents.base_agent import BaseAgent

class ThinkerAgent(BaseAgent):
    """Derin Düşünür: Planları baştan uca analiz eder ve mantık hatalarını yakalar."""
    name = "thinker"
    description = "Derin Düşünür: Planları baştan uca analiz eder ve mantık hatalarını yakalar."

    def __init__(self):
        super().__init__()
        # Kullanıcının özel olarak istediği Qwen 3 Max Thinking modeli atanır
        self.model = "qwen/qwen3-max-thinking"

    async def process_response(self, response: str, mission, memory):
        from agents.base_agent import AgentResult
        return AgentResult(agent_name=self.name, raw_response=response)
