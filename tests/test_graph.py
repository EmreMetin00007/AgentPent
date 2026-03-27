"""AgentPent — Attack Graph Tests."""

import json
import pytest
from core.attack_graph import AttackGraph

def test_attack_graph_nodes():
    graph = AttackGraph()
    assert graph.add_node("10.10.10.5", "host") is True
    
    # Tekrar eklendiğinde False dönmeli (update)
    assert graph.add_node("10.10.10.5", "host", {"os": "Linux"}) is False
    assert graph.nodes["10.10.10.5"].properties["os"] == "Linux"

def test_attack_graph_edges():
    graph = AttackGraph()
    graph.add_node("10.10.10.5", "host")
    graph.add_node("port_80", "service")
    
    assert graph.add_edge("10.10.10.5", "port_80", "HAS_PORT") is True
    # Duplicate edge
    assert graph.add_edge("10.10.10.5", "port_80", "HAS_PORT") is False
    # Missing source node
    assert graph.add_edge("unknown", "port_80", "HAS_PORT") is False

def test_attack_graph_pathfinding():
    graph = AttackGraph()
    graph.add_node("Attacker", "host")
    graph.add_node("Target_Web", "service")
    graph.add_node("Vuln_SQLi", "vuln")
    graph.add_node("Target_DB", "host")
    
    graph.add_edge("Attacker", "Target_Web", "SCANS")
    graph.add_edge("Target_Web", "Vuln_SQLi", "HAS_VULN")
    graph.add_edge("Vuln_SQLi", "Target_DB", "COMPROMISES")
    
    paths = graph.get_paths_to("Target_DB")
    assert len(paths) == 1
    assert paths[0] == ["Attacker", "Target_Web", "Vuln_SQLi", "Target_DB"]

def test_attack_graph_mermaid():
    graph = AttackGraph()
    graph.add_node("A", "host")
    graph.add_node("B", "vuln")
    graph.add_edge("A", "B", "HAS")
    
    mermaid = graph.get_mermaid()
    assert "graph TD;" in mermaid
    assert "A[\"A\\n(host)\"];" in mermaid
    assert "A -->|HAS| B;" in mermaid

def test_attack_graph_json():
    graph = AttackGraph()
    graph.add_node("A", "host", {"ip": "1.1.1.1"})
    
    data = json.loads(graph.to_json())
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "A"
    assert data["nodes"][0]["properties"]["ip"] == "1.1.1.1"
