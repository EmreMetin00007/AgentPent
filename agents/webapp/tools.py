"""AgentPent — WebApp Agent Tool Registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

from tools.sqlmap_tool import SQLMapTool
from tools.ffuf_tool import FFUFTool
from tools.xsstrike_tool import XSStrikeTool
from tools.nikto_tool import NiktoTool
from tools.kali_terminal import KaliTerminalTool

from tools.rag_tools import RAGSearchTool, RAGStoreTool
from tools.c2_tools import C2StartListenerTool, C2ListSessionsTool, C2InteractTool
from tools.graph_tools import GraphAddNodeTool, GraphAddEdgeTool, GraphViewTool
from tools.browser_tool import BrowserVisionTool
from tools.http_repeater_tool import HttpRepeaterTool
logger = logging.getLogger("agentpent.agents.webapp.tools")


def setup_webapp_tools(agent: BaseAgent) -> None:
    """WebApp agent'ına gerekli araçları kaydet."""
    agent.register_tool("sqlmap", SQLMapTool())
    agent.register_tool("ffuf", FFUFTool())
    agent.register_tool("xsstrike", XSStrikeTool())
    agent.register_tool("nikto", NiktoTool())
    agent.register_tool("kaliterminal", KaliTerminalTool())
    agent.register_tool("rag_search", RAGSearchTool())
    agent.register_tool("rag_store", RAGStoreTool())
    agent.register_tool("c2_start_listener", C2StartListenerTool())
    agent.register_tool("c2_list_sessions", C2ListSessionsTool())
    agent.register_tool("c2_interact", C2InteractTool())
    agent.register_tool("graph_add_node", GraphAddNodeTool())
    agent.register_tool("graph_add_edge", GraphAddEdgeTool())
    agent.register_tool("graph_view", GraphViewTool())
    agent.register_tool("http_repeater", HttpRepeaterTool())
    agent.register_tool("browser_vision", BrowserVisionTool())
    logger.debug("WebApp araçları kaydedildi: %s", agent.available_tools)
