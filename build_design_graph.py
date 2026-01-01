#!/usr/bin/env python3
"""
build_design_graph.py
-------------------------------------------------------------------------------
Design Graph Builder
-------------------------------------------------------------------------------
Consumes discovered_relationships.json and builds a directed multigraph
using NetworkX or adjacency dictionaries.

Input:
- discovered_relationships.json

Output:
- auto_design_graph.json (node-link graph format)
- graph_metrics.txt (statistics and metrics)
- Optional: JSON-LD export
-------------------------------------------------------------------------------
"""

import json
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
import statistics

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    print("  ⚠ NetworkX not available - using adjacency dictionaries")


# ============================================================================
# DATA LOADING
# ============================================================================

def load_relationships(filepath: str = "discovered_relationships.json") -> List[Dict[str, Any]]:
    """Load discovered relationships."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    relationships = data.get("relationships", [])
    print(f"  ✓ Loaded {len(relationships)} relationships")
    return relationships


# ============================================================================
# NODE NORMALIZATION
# ============================================================================

def normalize_node_id(node_id: str, layer: str) -> str:
    """Normalize node identifier to 'layer:id' format."""
    return f"{layer}:{node_id}"


def parse_normalized_id(normalized_id: str) -> Tuple[str, str]:
    """Parse normalized ID back to layer and node_id."""
    if ':' in normalized_id:
        layer, node_id = normalized_id.split(':', 1)
        return layer, node_id
    return "unknown", normalized_id


# ============================================================================
# GRAPH BUILDING
# ============================================================================

def build_graph_with_networkx(relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build graph using NetworkX."""
    print("\nBuilding graph with NetworkX...")
    
    G = nx.MultiDiGraph()
    
    # Add nodes and edges
    nodes_set = set()
    for rel in relationships:
        source_id = rel.get("source_id")
        source_layer = rel.get("source_layer")
        target_id = rel.get("target_id")
        target_layer = rel.get("target_layer")
        
        if not source_id or not target_id:
            continue
        
        source_node = normalize_node_id(source_id, source_layer)
        target_node = normalize_node_id(target_id, target_layer)
        
        nodes_set.add(source_node)
        nodes_set.add(target_node)
        
        # Add edge with attributes
        G.add_edge(
            source_node,
            target_node,
            relationship_type=rel.get("relationship_type", "unknown"),
            match_type=rel.get("match_type", "unknown"),
            confidence=rel.get("confidence", 0.0),
            description=rel.get("description", ""),
            source_prefix=rel.get("source_prefix", ""),
            target_prefix=rel.get("target_prefix", "")
        )
    
    # Convert to node-link format
    graph_data = nx.node_link_data(G)
    
    print(f"  ✓ Built graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return graph_data, G


def build_graph_with_adjacency(relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build graph using adjacency dictionaries (no NetworkX dependency)."""
    print("\nBuilding graph with adjacency dictionaries...")
    
    nodes = {}
    links = []
    adjacency = defaultdict(list)
    
    # Process relationships
    for rel in relationships:
        source_id = rel.get("source_id")
        source_layer = rel.get("source_layer")
        target_id = rel.get("target_id")
        target_layer = rel.get("target_layer")
        
        if not source_id or not target_id:
            continue
        
        source_node = normalize_node_id(source_id, source_layer)
        target_node = normalize_node_id(target_id, target_layer)
        
        # Add nodes
        if source_node not in nodes:
            nodes[source_node] = {
                "id": source_node,
                "layer": source_layer,
                "node_id": source_id,
                "prefix": rel.get("source_prefix", "")
            }
        
        if target_node not in nodes:
            nodes[target_node] = {
                "id": target_node,
                "layer": target_layer,
                "node_id": target_id,
                "prefix": rel.get("target_prefix", "")
            }
        
        # Add link
        link = {
            "source": source_node,
            "target": target_node,
            "relationship_type": rel.get("relationship_type", "unknown"),
            "match_type": rel.get("match_type", "unknown"),
            "confidence": rel.get("confidence", 0.0),
            "description": rel.get("description", ""),
            "source_layer": source_layer,
            "target_layer": target_layer
        }
        
        if "reference_field" in rel:
            link["reference_field"] = rel["reference_field"]
        
        links.append(link)
        adjacency[source_node].append(target_node)
    
    # Convert to node-link format
    graph_data = {
        "nodes": list(nodes.values()),
        "links": links
    }
    
    print(f"  ✓ Built graph with {len(nodes)} nodes, {len(links)} edges")
    return graph_data, adjacency


# ============================================================================
# GRAPH METRICS
# ============================================================================

def calculate_metrics_networkx(G) -> Dict[str, Any]:
    """Calculate graph metrics using NetworkX."""
    metrics = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "is_directed": G.is_directed(),
        "is_multigraph": G.is_multigraph(),
        "number_of_selfloops": G.number_of_selfloops()
    }
    
    # Degree distribution
    in_degrees = [d for n, d in G.in_degree()]
    out_degrees = [d for n, d in G.out_degree()]
    
    if in_degrees:
        metrics["in_degree"] = {
            "mean": round(statistics.mean(in_degrees), 2),
            "median": round(statistics.median(in_degrees), 2),
            "min": min(in_degrees),
            "max": max(in_degrees)
        }
    
    if out_degrees:
        metrics["out_degree"] = {
            "mean": round(statistics.mean(out_degrees), 2),
            "median": round(statistics.median(out_degrees), 2),
            "min": min(out_degrees),
            "max": max(out_degrees)
        }
    
    # Connected components (for undirected version)
    G_undirected = G.to_undirected()
    components = list(nx.connected_components(G_undirected))
    metrics["connected_components"] = len(components)
    metrics["largest_component_size"] = len(max(components, key=len)) if components else 0
    
    # Weakly connected components (for directed)
    if G.is_directed():
        wcc = list(nx.weakly_connected_components(G))
        metrics["weakly_connected_components"] = len(wcc)
        metrics["largest_wcc_size"] = len(max(wcc, key=len)) if wcc else 0
    
    # Layer distribution
    layer_counts = defaultdict(int)
    for node in G.nodes():
        layer, _ = parse_normalized_id(node)
        layer_counts[layer] += 1
    
    metrics["nodes_by_layer"] = dict(layer_counts)
    
    # Relationship type distribution
    rel_type_counts = defaultdict(int)
    for u, v, data in G.edges(data=True):
        rel_type = data.get("relationship_type", "unknown")
        rel_type_counts[rel_type] += 1
    
    metrics["edges_by_relationship_type"] = dict(rel_type_counts)
    
    return metrics


def calculate_metrics_adjacency(graph_data: Dict[str, Any], 
                                adjacency: Dict[str, List[str]]) -> Dict[str, Any]:
    """Calculate graph metrics using adjacency dictionaries."""
    nodes = graph_data.get("nodes", [])
    links = graph_data.get("links", [])
    
    metrics = {
        "total_nodes": len(nodes),
        "total_edges": len(links),
        "is_directed": True,
        "is_multigraph": True
    }
    
    # Build reverse adjacency for in-degree calculation
    reverse_adjacency = defaultdict(list)
    for link in links:
        source = link.get("source")
        target = link.get("target")
        if source and target:
            reverse_adjacency[target].append(source)
    
    # Calculate degrees
    in_degrees = [len(reverse_adjacency.get(node["id"], [])) for node in nodes]
    out_degrees = [len(adjacency.get(node["id"], [])) for node in nodes]
    
    if in_degrees:
        metrics["in_degree"] = {
            "mean": round(statistics.mean(in_degrees), 2),
            "median": round(statistics.median(in_degrees), 2),
            "min": min(in_degrees),
            "max": max(in_degrees)
        }
    
    if out_degrees:
        metrics["out_degree"] = {
            "mean": round(statistics.mean(out_degrees), 2),
            "median": round(statistics.median(out_degrees), 2),
            "min": min(out_degrees),
            "max": max(out_degrees)
        }
    
    # Layer distribution
    layer_counts = defaultdict(int)
    for node in nodes:
        layer = node.get("layer", "unknown")
        layer_counts[layer] += 1
    
    metrics["nodes_by_layer"] = dict(layer_counts)
    
    # Relationship type distribution
    rel_type_counts = defaultdict(int)
    for link in links:
        rel_type = link.get("relationship_type", "unknown")
        rel_type_counts[rel_type] += 1
    
    metrics["edges_by_relationship_type"] = dict(rel_type_counts)
    
    # Simple connectivity analysis
    all_nodes = {node["id"] for node in nodes}
    visited = set()
    components = []
    
    def dfs(node_id: str, component: Set[str]):
        if node_id in visited:
            return
        visited.add(node_id)
        component.add(node_id)
        
        # Follow both directions (undirected)
        for neighbor in adjacency.get(node_id, []):
            if neighbor not in visited:
                dfs(neighbor, component)
        for source in [s for s, targets in adjacency.items() if node_id in targets]:
            if source not in visited:
                dfs(source, component)
    
    for node_id in all_nodes:
        if node_id not in visited:
            component = set()
            dfs(node_id, component)
            if component:
                components.append(component)
    
    metrics["connected_components"] = len(components)
    metrics["largest_component_size"] = len(max(components, key=len)) if components else 0
    
    return metrics


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_graph_json(graph_data: Dict[str, Any], 
                       output_file: str = "auto_design_graph.json") -> None:
    """Generate auto_design_graph.json."""
    print(f"\nGenerating {output_file}...")
    
    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "graph": graph_data
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"  ✓ Saved {output_file}")


def generate_metrics_txt(metrics: Dict[str, Any], 
                        output_file: str = "graph_metrics.txt") -> None:
    """Generate graph_metrics.txt."""
    print(f"\nGenerating {output_file}...")
    
    output = "=" * 80 + "\n"
    output += "DESIGN GRAPH METRICS\n"
    output += "=" * 80 + "\n\n"
    output += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Basic statistics
    output += "BASIC STATISTICS:\n"
    output += "-" * 80 + "\n\n"
    output += f"Total Nodes: {metrics.get('total_nodes', 0)}\n"
    output += f"Total Edges: {metrics.get('total_edges', 0)}\n"
    output += f"Directed: {metrics.get('is_directed', False)}\n"
    output += f"Multigraph: {metrics.get('is_multigraph', False)}\n"
    if "number_of_selfloops" in metrics:
        output += f"Self-loops: {metrics.get('number_of_selfloops', 0)}\n"
    output += "\n"
    
    # Degree distribution
    if "in_degree" in metrics:
        in_deg = metrics["in_degree"]
        output += "IN-DEGREE DISTRIBUTION:\n"
        output += "-" * 80 + "\n\n"
        output += f"Mean: {in_deg.get('mean', 0)}\n"
        output += f"Median: {in_deg.get('median', 0)}\n"
        output += f"Min: {in_deg.get('min', 0)}\n"
        output += f"Max: {in_deg.get('max', 0)}\n\n"
    
    if "out_degree" in metrics:
        out_deg = metrics["out_degree"]
        output += "OUT-DEGREE DISTRIBUTION:\n"
        output += "-" * 80 + "\n\n"
        output += f"Mean: {out_deg.get('mean', 0)}\n"
        output += f"Median: {out_deg.get('median', 0)}\n"
        output += f"Min: {out_deg.get('min', 0)}\n"
        output += f"Max: {out_deg.get('max', 0)}\n\n"
    
    # Connectivity
    output += "CONNECTIVITY:\n"
    output += "-" * 80 + "\n\n"
    output += f"Connected Components: {metrics.get('connected_components', 0)}\n"
    output += f"Largest Component Size: {metrics.get('largest_component_size', 0)}\n"
    if "weakly_connected_components" in metrics:
        output += f"Weakly Connected Components: {metrics.get('weakly_connected_components', 0)}\n"
        output += f"Largest WCC Size: {metrics.get('largest_wcc_size', 0)}\n"
    output += "\n"
    
    # Layer distribution
    if "nodes_by_layer" in metrics:
        output += "NODES BY LAYER:\n"
        output += "-" * 80 + "\n\n"
        for layer, count in sorted(metrics["nodes_by_layer"].items(), key=lambda x: -x[1]):
            output += f"  {layer}: {count}\n"
        output += "\n"
    
    # Relationship type distribution
    if "edges_by_relationship_type" in metrics:
        output += "EDGES BY RELATIONSHIP TYPE:\n"
        output += "-" * 80 + "\n\n"
        for rel_type, count in sorted(metrics["edges_by_relationship_type"].items(), key=lambda x: -x[1]):
            output += f"  {rel_type}: {count}\n"
        output += "\n"
    
    output += "=" * 80 + "\n"
    output += "END OF METRICS\n"
    output += "=" * 80 + "\n"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)
    
    print(f"  ✓ Saved {output_file}")


def generate_json_ld(graph_data: Dict[str, Any], 
                     output_file: str = "auto_design_graph.jsonld") -> None:
    """Generate JSON-LD export (optional)."""
    print(f"\nGenerating {output_file}...")
    
    context = {
        "@context": {
            "@vocab": "https://example.org/design#",
            "nodes": "@graph",
            "links": {
                "@id": "@edge",
                "@container": "@list"
            }
        }
    }
    
    jsonld_data = {
        "@context": context["@context"],
        "@id": "https://example.org/design-graph",
        "@type": "DesignGraph",
        "nodes": [
            {
                "@id": f"node:{node['id']}",
                "@type": f"DesignNode:{node.get('layer', 'unknown')}",
                "layer": node.get("layer"),
                "node_id": node.get("node_id"),
                "prefix": node.get("prefix")
            }
            for node in graph_data.get("nodes", [])
        ],
        "links": [
            {
                "@id": f"edge:{i}",
                "@type": f"DesignLink:{link.get('relationship_type', 'unknown')}",
                "source": {"@id": f"node:{link.get('source')}"},
                "target": {"@id": f"node:{link.get('target')}"},
                "relationship_type": link.get("relationship_type"),
                "confidence": link.get("confidence"),
                "match_type": link.get("match_type")
            }
            for i, link in enumerate(graph_data.get("links", []))
        ]
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(jsonld_data, f, indent=2)
    
    print(f"  ✓ Saved {output_file}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main execution pipeline."""
    print("=" * 80)
    print("DESIGN GRAPH BUILDER")
    print("=" * 80)
    
    # Step 1: Load relationships
    relationships = load_relationships()
    
    # Step 2: Build graph
    if NETWORKX_AVAILABLE:
        graph_data, graph_obj = build_graph_with_networkx(relationships)
        metrics = calculate_metrics_networkx(graph_obj)
    else:
        graph_data, adjacency = build_graph_with_adjacency(relationships)
        metrics = calculate_metrics_adjacency(graph_data, adjacency)
    
    # Step 3: Generate outputs
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)
    
    generate_graph_json(graph_data)
    generate_metrics_txt(metrics)
    
    # Optional: JSON-LD export
    try:
        generate_json_ld(graph_data)
    except Exception as e:
        print(f"  ⚠ JSON-LD export skipped: {e}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ GRAPH BUILD COMPLETE")
    print("=" * 80)
    print(f"\nBuilt graph with:")
    print(f"  Nodes: {metrics.get('total_nodes', 0)}")
    print(f"  Edges: {metrics.get('total_edges', 0)}")
    print(f"  Connected Components: {metrics.get('connected_components', 0)}")
    print(f"\nGenerated files:")
    print(f"  📄 auto_design_graph.json")
    print(f"  📄 graph_metrics.txt")
    try:
        with open("auto_design_graph.jsonld", "r"):
            print(f"  📄 auto_design_graph.jsonld")
    except:
        pass
    print()


if __name__ == "__main__":
    main()





