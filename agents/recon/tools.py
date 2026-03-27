"""AgentPent — Recon Agent Tool Registry.

Recon agent'ına özel araç kayıtları.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

from tools.nmap_tool import NmapTool
from tools.subfinder_tool import SubfinderTool
from tools.whois_tool import WhoisTool
from tools.httpx_tool import HttpxTool
from tools.kali_terminal import KaliTerminalTool

from tools.rag_tools import RAGSearchTool, RAGStoreTool
from tools.graph_tools import GraphAddNodeTool, GraphAddEdgeTool, GraphViewTool
from tools.http_repeater_tool import HttpRepeaterTool
logger = logging.getLogger("agentpent.agents.recon.tools")


def setup_recon_tools(agent: BaseAgent) -> None:
    """Recon agent'ına gerekli araçları kaydet."""
    agent.register_tool("nmap", NmapTool())
    agent.register_tool("subfinder", SubfinderTool())
    agent.register_tool("whois", WhoisTool())
    agent.register_tool("httpx", HttpxTool())
    agent.register_tool("kaliterminal", KaliTerminalTool())
    agent.register_tool("rag_search", RAGSearchTool())
    agent.register_tool("rag_store", RAGStoreTool())
    agent.register_tool("graph_add_node", GraphAddNodeTool())
    agent.register_tool("graph_add_edge", GraphAddEdgeTool())
    agent.register_tool("graph_view", GraphViewTool())
    agent.register_tool("http_repeater", HttpRepeaterTool())
    logger.debug("Recon araçları kaydedildi: %s", agent.available_tools)
