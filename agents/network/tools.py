"""AgentPent — Network Agent Tool Registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

from tools.responder_tool import ResponderTool
from tools.chisel_tool import ChiselTool
from tools.nmap_tool import NmapTool
from tools.kali_terminal import KaliTerminalTool

from tools.rag_tools import RAGSearchTool, RAGStoreTool
from tools.c2_tools import C2StartListenerTool, C2ListSessionsTool, C2InteractTool
from tools.graph_tools import GraphAddNodeTool, GraphAddEdgeTool, GraphViewTool
logger = logging.getLogger("agentpent.agents.network.tools")


def setup_network_tools(agent: BaseAgent) -> None:
    """Network agent'ına gerekli araçları kaydet."""
    agent.register_tool("responder", ResponderTool())
    agent.register_tool("chisel", ChiselTool())
    agent.register_tool("nmap", NmapTool())
    agent.register_tool("kaliterminal", KaliTerminalTool())
    agent.register_tool("rag_search", RAGSearchTool())
    agent.register_tool("rag_store", RAGStoreTool())
    agent.register_tool("c2_start_listener", C2StartListenerTool())
    agent.register_tool("c2_list_sessions", C2ListSessionsTool())
    agent.register_tool("c2_interact", C2InteractTool())
    agent.register_tool("graph_add_node", GraphAddNodeTool())
    agent.register_tool("graph_add_edge", GraphAddEdgeTool())
    agent.register_tool("graph_view", GraphViewTool())
    logger.debug("Network araçları kaydedildi: %s", agent.available_tools)
