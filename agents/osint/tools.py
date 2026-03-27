"""AgentPent — OSINT Agent Tool Registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

from tools.theharvester_tool import TheHarvesterTool
from tools.whois_tool import WhoisTool

from tools.rag_tools import RAGSearchTool, RAGStoreTool
from tools.graph_tools import GraphAddNodeTool, GraphAddEdgeTool, GraphViewTool
logger = logging.getLogger("agentpent.agents.osint.tools")


def setup_osint_tools(agent: BaseAgent) -> None:
    """OSINT agent'ına gerekli araçları kaydet."""
    agent.register_tool("theharvester", TheHarvesterTool())
    agent.register_tool("whois", WhoisTool())
    agent.register_tool("rag_search", RAGSearchTool())
    agent.register_tool("rag_store", RAGStoreTool())
    agent.register_tool("graph_add_node", GraphAddNodeTool())
    agent.register_tool("graph_add_edge", GraphAddEdgeTool())
    agent.register_tool("graph_view", GraphViewTool())
    logger.debug("OSINT araçları kaydedildi: %s", agent.available_tools)
