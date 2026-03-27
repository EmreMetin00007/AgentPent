"""AgentPent — Attack Graph Tools.

Ajanların buldukları servis ve zafiyetleri grafik ağına (Graph) 
düğüm ve ilişki olarak eklemesini sağlar.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict

from core.attack_graph import global_attack_graph
from tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger("agentpent.tools.graph")


class GraphAddNodeTool(BaseTool):
    """Zafiyet zinciri grafiğine yeni bir düğüm (Node) ekler."""

    name: ClassVar[str] = "graph_add_node"
    description: ClassVar[str] = (
        "Zafiyet veya bilgi toplama sırasında keşfedilen Host, Port, Servis, Yetki "
        "veyahut Zafiyet'i Attack Graph'a (Saldırı Ağacı) ekler. "
        "Parametreler: id (Benzersiz düğüm ismi, ör: '10.10.10.5_80'), "
        "type (Düğüm tipi: 'host', 'service', 'vuln', 'credential', 'session'), "
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        node_id = params.get("id")
        node_type = params.get("type")

        if not node_id or not node_type:
            return ToolResult(tool_name=self.name, success=False, error="id ve type parametreleri gerekli.")

        is_new = global_attack_graph.add_node(node_id, node_type, {})
        
        msg = f"Düğüm {'eklendi' if is_new else 'güncellendi'}: {node_id} ({node_type})"
        logger.info("[GraphAddNodeTool] %s", msg)

        return ToolResult(
            tool_name=self.name,
            command=f"add_node: {node_id}",
            success=True,
            stdout=msg
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"graph_output": raw}


class GraphAddEdgeTool(BaseTool):
    """Zafiyet zinciri grafiğindeki iki düğüm arasına ilişki (Edge) ekler."""

    name: ClassVar[str] = "graph_add_edge"
    description: ClassVar[str] = (
        "İki düğüm arasındaki ilişkiyi belirtir (Örn: host -> HAS_PORT -> port). "
        "Parametreler: source_id (Kaynak düğüm id), target_id (Hedef düğüm id), "
        "relation (İlişki tipi: 'HAS_PORT', 'HAS_VULN', 'EXPLOITS', 'COMPROMISES')"
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        source_id = params.get("source_id", "")
        target_id = params.get("target_id", "")
        relation = params.get("relation", "")

        if not source_id or not target_id or not relation:
            return ToolResult(tool_name=self.name, success=False, error="source_id, target_id, relation gereklidir.")

        added = global_attack_graph.add_edge(source_id, target_id, relation)
        
        if added:
            msg = f"İlişki Eklendi: {source_id} -[{relation}]-> {target_id}"
        else:
            msg = f"Başarısız: İlişki zaten var veya düğümlerden biri grafikte yok."
            return ToolResult(tool_name=self.name, success=False, error=msg)

        logger.info("[GraphAddEdgeTool] %s", msg)

        return ToolResult(
            tool_name=self.name,
            command=f"add_edge: {source_id}->{target_id}",
            success=True,
            stdout=msg
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"graph_output": raw}


class GraphViewTool(BaseTool):
    """Mevcut Zafiyet Zinciri Grafiğini (Attack Graph) görüntüler."""

    name: ClassVar[str] = "graph_view"
    description: ClassVar[str] = (
        "Şu anki Zafiyet ağacını Mermaid formatında veya JSON formatında gösterir. "
        "Saldırı yönünü ve stratejisini belirlemek için kullanılır. "
        "Parametre: format ('mermaid' veya 'json', varsayılan: 'mermaid')"
    )

    async def _run(self, params: Dict[str, Any]) -> ToolResult:
        fmt = params.get("format", "mermaid")
        
        if fmt == "json":
            out_str = global_attack_graph.to_json()
        else:
            out_str = global_attack_graph.get_mermaid()

        return ToolResult(
            tool_name=self.name,
            command=f"view_graph:{fmt}",
            success=True,
            stdout=out_str
        )

    def parse_output(self, raw: str) -> Dict[str, Any]:
        return {"graph": raw}
