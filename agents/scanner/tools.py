"""AgentPent — Scanner Agent Tool Registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

from tools.nmap_tool import NmapTool
from tools.nuclei_tool import NucleiTool
from tools.kali_terminal import KaliTerminalTool

from tools.rag_tools import RAGSearchTool, RAGStoreTool
from tools.graph_tools import GraphAddNodeTool, GraphAddEdgeTool, GraphViewTool
from tools.http_repeater_tool import HttpRepeaterTool
logger = logging.getLogger("agentpent.agents.scanner.tools")


def setup_scanner_tools(agent: BaseAgent) -> None:
    """Scanner agent'ına gerekli araçları kaydet."""
    agent.register_tool("nmap", NmapTool())
    agent.register_tool("nuclei", NucleiTool())
    agent.register_tool("kaliterminal", KaliTerminalTool())
    agent.register_tool("rag_search", RAGSearchTool())
    agent.register_tool("rag_store", RAGStoreTool())
    agent.register_tool("graph_add_node", GraphAddNodeTool())
    agent.register_tool("graph_add_edge", GraphAddEdgeTool())
    agent.register_tool("graph_view", GraphViewTool())
    agent.register_tool("http_repeater", HttpRepeaterTool())
    logger.debug("Scanner araçları kaydedildi: %s", agent.available_tools)
