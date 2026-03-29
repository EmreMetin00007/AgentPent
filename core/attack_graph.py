"""AgentPent — Attack Graph (Zafiyet Zincirleme) Modülü.

Hedefteki sistemlerin, servislerin ve zafiyetlerin birbirleriyle
ilişkisini (Node & Edge) tutar. Saldırı yollarını (Attack Paths) belirler.

Her Mission kendi AttackGraph instance'ını taşır (singleton yok).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.mission import Finding

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
    """Zafiyet zincirini tutan graf yapısı. Mission bazlı instance."""

    def __init__(self):
        self.nodes: Dict[str, AttackNode] = {}
        self.edges: List[AttackEdge] = []

    def add_node(self, node_id: str, node_type: str, properties: Optional[Dict[str, str]] = None) -> bool:
        if node_id not in self.nodes:
            self.nodes[node_id] = AttackNode(id=node_id, type=node_type, properties=properties or {})
            logger.debug("[Graph] Node eklendi: %s (%s)", node_id, node_type)
            return True
        else:
            if properties:
                self.nodes[node_id].properties.update(properties)
            return False

    def add_edge(self, source_id: str, target_id: str, relation: str) -> bool:
        if source_id not in self.nodes or target_id not in self.nodes:
            logger.warning("[Graph] Edge eklenemedi: Node bulunamadı (%s -> %s)", source_id, target_id)
            return False

        # Duplicate kontrolü
        for e in self.edges:
            if e.source_id == source_id and e.target_id == target_id and e.relation == relation:
                return False

        edge = AttackEdge(source_id=source_id, target_id=target_id, relation=relation)
        self.edges.append(edge)
        logger.debug("[Graph] Edge eklendi: %s -[%s]-> %s", source_id, relation, target_id)
        return True

    @classmethod
    def from_findings(cls, findings: list) -> "AttackGraph":
        """Finding listesinden otomatik AttackGraph oluşturur."""
        graph = cls()

        for f in findings:
            target = f.target
            # Host node
            graph.add_node(target, "host")

            # Port/Service node
            if f.port:
                port_id = "{}_port_{}".format(target, f.port)
                svc_name = f.service or "unknown"
                graph.add_node(port_id, "service", {
                    "port": str(f.port),
                    "service": svc_name,
                })
                graph.add_edge(target, port_id, "HAS_PORT")

                # Vuln node
                vuln_id = "vuln_{}".format(f.id)
                graph.add_node(vuln_id, "vuln", {
                    "title": f.title,
                    "severity": f.severity.value,
                    "exploitable": str(f.exploitable),
                })
                graph.add_edge(port_id, vuln_id, "HAS_VULN")

                # CVE nodes
                for cve in getattr(f, "cve_ids", []):
                    cve_id = cve.upper()
                    graph.add_node(cve_id, "cve", {"cve_id": cve_id})
                    graph.add_edge(vuln_id, cve_id, "REFERENCES")
            else:
                # Port olmadan direkt vuln
                vuln_id = "vuln_{}".format(f.id)
                graph.add_node(vuln_id, "vuln", {
                    "title": f.title,
                    "severity": f.severity.value,
                })
                graph.add_edge(target, vuln_id, "HAS_VULN")

        return graph

    def get_attack_paths(self, max_paths: int = 5) -> List[Dict[str, Any]]:
        """En yüksek etkiye sahip saldırı yollarını sıralar."""
        # Exploitable vuln node'larını bul
        exploit_nodes = [
            n for n in self.nodes.values()
            if n.type == "vuln" and n.properties.get("exploitable") == "True"
        ]

        paths = []
        for target_node in exploit_nodes:
            found_paths = self.get_paths_to(target_node.id)
            for p in found_paths:
                severity = target_node.properties.get("severity", "INFO")
                severity_score = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}
                paths.append({
                    "path": p,
                    "target_vuln": target_node.properties.get("title", ""),
                    "severity": severity,
                    "score": severity_score.get(severity, 0),
                    "depth": len(p),
                })

        paths.sort(key=lambda x: x["score"], reverse=True)
        return paths[:max_paths]

    def get_mermaid(self) -> str:
        if not self.nodes:
            return "graph TD;\n  Empty[Graph Boş]"

        lines = ["graph TD;"]
        for node in self.nodes.values():
            node_label = "{}\\n({})".format(node.id, node.type)
            lines.append('  {}["{}"];'.format(node.id, node_label))

        for edge in self.edges:
            lines.append("  {} -->|{}| {};".format(edge.source_id, edge.relation, edge.target_id))

        return "\n".join(lines)

    def to_json(self) -> str:
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
        if target_node_id not in self.nodes:
            return []

        targets = {e.target_id for e in self.edges}
        roots = [n_id for n_id in self.nodes if n_id not in targets]

        if not roots:
            roots = [n.id for n in self.nodes.values() if n.type == "host"]

        paths = []
        for root in roots:
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

    @property
    def summary(self) -> str:
        hosts = sum(1 for n in self.nodes.values() if n.type == "host")
        services = sum(1 for n in self.nodes.values() if n.type == "service")
        vulns = sum(1 for n in self.nodes.values() if n.type == "vuln")
        return "Graph: {} host, {} servis, {} zafiyet, {} ilişki".format(
            hosts, services, vulns, len(self.edges)
        )
