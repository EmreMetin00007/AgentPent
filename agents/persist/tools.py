"""AgentPent — Persist Agent Tool Registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

from tools.metasploit_tool import MetasploitTool

from tools.rag_tools import RAGSearchTool, RAGStoreTool
from tools.graph_tools import GraphAddNodeTool, GraphAddEdgeTool, GraphViewTool
logger = logging.getLogger("agentpent.agents.persist.tools")


def setup_persist_tools(agent: BaseAgent) -> None:
    """Persist agent'ına gerekli araçları kaydet."""
    agent.register_tool("metasploit", MetasploitTool())
    agent.register_tool("rag_search", RAGSearchTool())
    agent.register_tool("rag_store", RAGStoreTool())
    agent.register_tool("graph_add_node", GraphAddNodeTool())
    agent.register_tool("graph_add_edge", GraphAddEdgeTool())
    agent.register_tool("graph_view", GraphViewTool())
    logger.debug("Persist araçları kaydedildi: %s", agent.available_tools)
