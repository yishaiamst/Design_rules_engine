#!/usr/bin/env python3
"""
Visualize Network Layers (Separate Files)
Creates separate GeoJSON files for each layer for easier debugging.
Also creates a connections visualization showing relationships.
"""

import json
import os
from utils.geojson_utils import load_geojson, create_feature, create_feature_collection
from utils.config_loader import load_config
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from utils.drop_cable_builder import create_drop_cables_for_onts
from utils.network_graph import build_network_graph


def save_layer_geojson(features, layer_name, output_dir="test_output"):
    """Save a single layer as a GeoJSON file."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{layer_name}.geojson")
    
    geojson = create_feature_collection(features)
    with open(path, "w") as f:
        json.dump(geojson, f, indent=2)
    
    print(f"  ✓ Saved {layer_name}: {len(features)} features → {path}")
    return path


def create_connections_visualization(graph, terminals, foscs, olts):
    """
    Create a visualization showing connections between components.
    This helps debug why paths aren't being found.
    """
    connection_lines = []
    
    # Terminal to Cable connections
    print("  Analyzing terminal-to-cable connections...")
    terminal_connections = 0
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id") or terminal.get("id", "")
        terminal_pos = terminal.get("position")
        
        if terminal_id and terminal_pos and terminal_id in graph.nodes:
            terminal_node = graph.nodes[terminal_id]
            # Check if terminal has edges to cable endpoints
            for neighbor_id, cable_idx, direction in terminal_node.edges:
                if neighbor_id.startswith("cable_"):
                    # Terminal is connected to a cable
                    neighbor_node = graph.nodes.get(neighbor_id)
                    if neighbor_node:
                        connection_lines.append({
                            "type": "LineString",
                            "coordinates": [
                                [terminal_pos[0], terminal_pos[1]],
                                [neighbor_node.position[0], neighbor_node.position[1]]
                            ],
                            "properties": {
                                "layer": "connection",
                                "from": "terminal",
                                "to": "cable",
                                "from_id": terminal_id,
                                "to_id": neighbor_id,
                                "stroke": "#FF00FF",
                                "stroke-width": 1,
                                "stroke-opacity": 0.5
                            }
                        })
                        terminal_connections += 1
    
    print(f"    Found {terminal_connections} terminal-to-cable connections")
    
    # FOSC to Cable connections
    print("  Analyzing FOSC-to-cable connections...")
    fosc_connections = 0
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id") or fosc.get("id", "")
        fosc_pos = fosc.get("position")
        
        if fosc_id and fosc_pos:
            # Find FOSC node (might be merged with cable endpoint)
            fosc_node_id = None
            for node_id, node in graph.nodes.items():
                if node.type == "fosc" and (node.data.get("fosc_id") == fosc_id or node_id == fosc_id):
                    fosc_node_id = node_id
                    break
            
            if fosc_node_id:
                fosc_node = graph.nodes[fosc_node_id]
                # Check connections
                for neighbor_id, cable_idx, direction in fosc_node.edges:
                    if neighbor_id.startswith("cable_"):
                        neighbor_node = graph.nodes.get(neighbor_id)
                        if neighbor_node:
                            connection_lines.append({
                                "type": "LineString",
                                "coordinates": [
                                    [fosc_pos[0], fosc_pos[1]],
                                    [neighbor_node.position[0], neighbor_node.position[1]]
                                ],
                                "properties": {
                                    "layer": "connection",
                                    "from": "fosc",
                                    "to": "cable",
                                    "from_id": fosc_id,
                                    "to_id": neighbor_id,
                                    "stroke": "#FF0000",
                                    "stroke-width": 2,
                                    "stroke-opacity": 0.7
                                }
                            })
                            fosc_connections += 1
    
    print(f"    Found {fosc_connections} FOSC-to-cable connections")
    
    # OLT to Cable connections
    print("  Analyzing OLT-to-cable connections...")
    olt_connections = 0
    for olt in olts:
        olt_id = olt.get("olt_id") or olt.get("id", "")
        olt_pos = olt.get("position")
        
        if olt_id and olt_pos and olt_id in graph.nodes:
            olt_node = graph.nodes[olt_id]
            for neighbor_id, cable_idx, direction in olt_node.edges:
                if neighbor_id.startswith("cable_"):
                    neighbor_node = graph.nodes.get(neighbor_id)
                    if neighbor_node:
                        connection_lines.append({
                            "type": "LineString",
                            "coordinates": [
                                [olt_pos[0], olt_pos[1]],
                                [neighbor_node.position[0], neighbor_node.position[1]]
                            ],
                            "properties": {
                                "layer": "connection",
                                "from": "olt",
                                "to": "cable",
                                "from_id": olt_id,
                                "to_id": neighbor_id,
                                "stroke": "#00FFFF",
                                "stroke-width": 3,
                                "stroke-opacity": 0.8
                            }
                        })
                        olt_connections += 1
    
    print(f"    Found {olt_connections} OLT-to-cable connections")
    
    # Create features
    features = []
    for line in connection_lines:
        features.append(create_feature(
            geometry=line,
            properties=line["properties"]
        ))
    
    return features


def main():
    print("=" * 80)
    print("NETWORK LAYERS VISUALIZATION (SEPARATE FILES)")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Run pipeline
    print()
    print("Running pipeline...")
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
    terminals, foscs, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, config)
    
    # Create drop cables
    print("Creating drop cables...")
    drop_cables = create_drop_cables_for_onts(ont_geojson, terminals, config=config, tolerance_m=1000.0)
    
    # Build graph
    print("Building network graph...")
    graph = build_network_graph(
        fiber_cable_geojson,
        olts,
        ont_geojson,
        foscs=foscs,
        terminals=terminals,
        config=config,
        tolerance_m=10.0
    )
    
    # Create separate layer files
    print()
    print("Creating separate layer files...")
    output_dir = "test_output/layers"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Fiber Cables
    fiber_features = []
    for feature in fiber_cable_geojson.get("features", []):
        props = feature.get("properties", {})
        props["layer"] = "fiber_cable"
        fiber_features.append(create_feature(
            geometry=feature.get("geometry", {}),
            properties=props
        ))
    save_layer_geojson(fiber_features, "01_fiber_cables", output_dir)
    
    # 2. FOSCs
    fosc_features = []
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_features.append(create_feature(
                geometry={"type": "Point", "coordinates": [fosc_pos[0], fosc_pos[1]]},
                properties={"layer": "fosc", **fosc}
            ))
    save_layer_geojson(fosc_features, "02_foscs", output_dir)
    
    # 3. Terminals
    terminal_features = []
    for terminal in terminals:
        terminal_pos = terminal.get("position")
        if terminal_pos:
            terminal_features.append(create_feature(
                geometry={"type": "Point", "coordinates": [terminal_pos[0], terminal_pos[1]]},
                properties={"layer": "terminal", **terminal}
            ))
    save_layer_geojson(terminal_features, "03_terminals", output_dir)
    
    # 4. Drop Cables
    drop_features = []
    for drop_cable in drop_cables:
        coords = drop_cable.get("coordinates", [])
        if len(coords) >= 2:
            drop_features.append(create_feature(
                geometry={
                    "type": "LineString",
                    "coordinates": [[c[0], c[1]] for c in coords]
                },
                properties={"layer": "drop_cable", **drop_cable}
            ))
    save_layer_geojson(drop_features, "04_drop_cables", output_dir)
    
    # 5. ONTs
    ont_features = []
    for feature in ont_geojson.get("features", []):
        if feature.get("geometry", {}).get("type") == "Point":
            props = feature.get("properties", {})
            props["layer"] = "ont"
            ont_features.append(create_feature(
                geometry=feature.get("geometry", {}),
                properties=props
            ))
    save_layer_geojson(ont_features, "05_onts", output_dir)
    
    # 6. OLTs
    olt_features = []
    for olt in olts:
        olt_pos = olt.get("position")
        if olt_pos:
            olt_features.append(create_feature(
                geometry={"type": "Point", "coordinates": [olt_pos[0], olt_pos[1]]},
                properties={"layer": "olt", **olt}
            ))
    save_layer_geojson(olt_features, "06_olts", output_dir)
    
    # 7. Connections (for debugging)
    print()
    print("Creating connections visualization...")
    connection_features = create_connections_visualization(graph, terminals, foscs, olts)
    save_layer_geojson(connection_features, "07_connections", output_dir)
    
    print()
    print("=" * 80)
    print("VISUALIZATION COMPLETE")
    print("=" * 80)
    print()
    print(f"✓ All layer files saved to: {output_dir}/")
    print()
    print("Files created:")
    print("  01_fiber_cables.geojson - Infrastructure fiber cables")
    print("  02_foscs.geojson - FOSC locations")
    print("  03_terminals.geojson - Terminal locations (Aerial and MST)")
    print("  04_drop_cables.geojson - Drop cables (ONT to Terminal)")
    print("  05_onts.geojson - ONT locations")
    print("  06_olts.geojson - OLT locations")
    print("  07_connections.geojson - Connection lines (for debugging)")
    print()
    print("You can load these files in QGIS or any GeoJSON viewer.")
    print("The connections file shows how terminals/FOSCs/OLTs connect to cables.")
    print()


if __name__ == "__main__":
    main()
