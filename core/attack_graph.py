"""AgentPent — Attack Graph (Zafiyet Zincirleme) Modülü.

Hedefteki sistemlerin, servislerin ve zafiyetlerin birbirleriyle 
ilişkisini (Node & Edge) tutar. Saldırı yollarını (Attack Paths) belirler.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("agentpent.attack_graph")


@dataclass
class AttackNode:
    """Grafik üzerindeki tek bir düğüm (Host, Port, Vuln, Session vb.)."""
    id: str  # Benzersiz isim (örn: '10.10.10.5', 'port_80', 'vuln_cve_2021_1234')
    type: str  # host, service, vuln, credential, session
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class AttackEdge:
    """İki düğüm arasındaki ilişki."""
    source_id: str
    target_id: str
    relation: str  # HAS_PORT, HAS_VULN, EXPLOITS, DISCOVERS, COMPROMISES


class AttackGraph:
    """Zafiyet zincirini tutan ana graf yapısı."""

    def __init__(self):
        self.nodes: Dict[str, AttackNode] = {}
        self.edges: List[AttackEdge] = []

    def add_node(self, node_id: str, node_type: str, properties: Optional[Dict[str, str]] = None) -> bool:
        """Yeni bir düğüm ekler."""
        if node_id not in self.nodes:
            self.nodes[node_id] = AttackNode(id=node_id, type=node_type, properties=properties or {})
            logger.debug("[Graph] Node eklendi: %s (%s)", node_id, node_type)
            return True
        else:
            # Sadece property güncelle
            if properties:
                self.nodes[node_id].properties.update(properties)
            return False

    def add_edge(self, source_id: str, target_id: str, relation: str) -> bool:
        """İki düğüm arasına ilişki (kenar) ekler."""
        if source_id not in self.nodes or target_id not in self.nodes:
            logger.warning("[Graph] Edge eklenemedi: Node bulunamadı (%s -> %s)", source_id, target_id)
            return False
            
        edge = AttackEdge(source_id=source_id, target_id=target_id, relation=relation)
        # Duplicate kontrolü
        for e in self.edges:
            if e.source_id == source_id and e.target_id == target_id and e.relation == relation:
                return False
                
        self.edges.append(edge)
        logger.debug("[Graph] Edge eklendi: %s -[%s]-> %s", source_id, relation, target_id)
        return True

    def get_mermaid(self) -> str:
        """Grafiği Commander görselleştirmesi için Mermaid formatında döndürür."""
        if not self.nodes:
            return "graph TD;\n  Empty[Graph Boş]"
            
        lines = ["graph TD;"]
        # Önce nodelar
        for node in self.nodes.values():
            node_label = f"{node.id}\\n({node.type})"
            lines.append(f"  {node.id}[\"{node_label}\"];")
            
        # Sonra edgeler
        for edge in self.edges:
            lines.append(f"  {edge.source_id} -->|{edge.relation}| {edge.target_id};")
            
        return "\n".join(lines)

    def to_json(self) -> str:
        """JSON formatında dışa aktarış."""
        data = {
            "nodes": [
                {"id": n.id, "type": n.type, "properties": n.properties}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source_id, "target": e.target_id, "relation": e.relation}
                for e in self.edges
            ]
        }
        return json.dumps(data, indent=2)

    def get_paths_to(self, target_node_id: str) -> List[List[str]]:
        """Basit bir BFS pathfinding (belirtilen node'a giden yolları bulur)."""
        if target_node_id not in self.nodes:
            return []
            
        # Başlangıç noktalarını bul (hiç hedef olarak gösterilmeyen root node'lar)
        targets = {e.target_id for e in self.edges}
        roots = [n_id for n_id in self.nodes if n_id not in targets]
        
        # Eğer root çıkmazsa, keyfi olarak host node'ları alalım
        if not roots:
            roots = [n.id for n in self.nodes.values() if n.type == "host"]

        paths = []
        for root in roots:
            # BFS
            queue = [[root]]
            visited = set()
            while queue:
                path = queue.pop(0)
                curr = path[-1]
                
                if curr == target_node_id:
                    paths.append(path)
                    continue
                    
                if curr in visited:
                    continue
                visited.add(curr)
                
                for edge in self.edges:
                    if edge.source_id == curr:
                        queue.append(path + [edge.target_id])
                        
        return paths

# Global singleton or per-mission context
# AgentPent Mission bazlı çalıştığı için, normalde Mission'a bağlanmalı.
# Ancak hızlı implementasyon için singleton
global_attack_graph = AttackGraph()
