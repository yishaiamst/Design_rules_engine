#!/usr/bin/env python3
"""
Drop Cable Builder
Creates drop cables to connect ONTs to terminals (Aerial or MST).
This enables proper path finding from ONT to OLT.
"""

from typing import Dict, List, Any, Tuple
from collections import defaultdict
from utils.spatial_utils import euclidean_distance


def create_drop_cables_for_onts(
    ont_geojson: Dict[str, Any],
    terminals: List[Dict[str, Any]],
    config: Dict[str, Any] = None,
    tolerance_m: float = 1000.0  # Large default - find nearest regardless
) -> List[Dict[str, Any]]:
    """
    Create drop cables connecting ONTs to their nearest terminals (Aerial or MST).
    Uses shortest distance to find the best terminal for each ONT.
    
    Args:
        ont_geojson: ONT GeoJSON
        terminals: List of terminals (Aerial or MST)
        config: Configuration dictionary (for drop cable size)
        tolerance_m: Maximum distance for ONT-to-terminal connection (default: 1000m, effectively unlimited)
    
    Returns:
        List of drop cable dictionaries
    """
    # Get drop cable size from config (default: 1F)
    drop_cable_size = 1
    if config:
        drop_cable_config = config.get("cables", {}).get("drop_cable", {})
        drop_cable_size = drop_cable_config.get("default_size", 1)
    
    drop_cables = []
    
    # Build terminal list with positions
    terminal_list = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id") or terminal.get("id", "")
        terminal_pos = terminal.get("position")
        terminal_type = terminal.get("type", "Unknown")
        
        if terminal_id and terminal_pos:
            terminal_list.append({
                "id": terminal_id,
                "position": terminal_pos,
                "type": terminal_type,
                "terminal": terminal
            })
    
    print(f"    Searching for nearest terminals among {len(terminal_list)} terminals (Aerial and MST)")
    
    # Process ONTs - find nearest terminal for each
    ont_count = 0
    connected_count = 0
    terminal_usage = defaultdict(int)  # Track how many ONTs per terminal
    
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        ont_id = props.get("ID") or props.get("id") or props.get("ont_id", "")
        coords = geometry.get("coordinates", [])
        
        if not ont_id:
            continue
        
        # Handle different coordinate formats
        if not coords or len(coords) < 2:
            # Try LatLong field if coordinates not in geometry
            latlong = props.get("LatLong", "")
            if latlong and isinstance(latlong, str):
                try:
                    # Parse "lat,lon" format
                    parts = latlong.split(",")
                    if len(parts) == 2:
                        coords = [float(parts[1].strip()), float(parts[0].strip())]  # lon, lat
                except:
                    pass
        
        if not coords or len(coords) < 2:
            continue
        
        ont_pos = (float(coords[0]), float(coords[1]))
        ont_count += 1
        
        # Find nearest terminal (shortest distance)
        min_dist = float('inf')
        nearest_terminal = None
        
        for term_info in terminal_list:
            term_pos = term_info["position"]
            dist = euclidean_distance(ont_pos[0], ont_pos[1], term_pos[0], term_pos[1])
            
            if dist < min_dist and dist <= tolerance_m:
                min_dist = dist
                nearest_terminal = term_info
        
        if nearest_terminal:
            terminal_id = nearest_terminal["id"]
            terminal_pos = nearest_terminal["position"]
            terminal_type = nearest_terminal["type"]
            
            # Create drop cable from ONT to terminal
            drop_cable = {
                "drop_cable_id": f"DROP_{ont_id}",
                "ont_id": ont_id,
                "terminal_id": terminal_id,
                "terminal_type": terminal_type,
                "coordinates": [ont_pos, terminal_pos],
                "length_m": min_dist,
                "fiber_count": drop_cable_size,
                "properties": {
                    "ID": f"DROP_{ont_id}",
                    "Type": "drop cable",
                    "Size": f"{drop_cable_size}F",
                    "From": ont_id,
                    "To": terminal_id,
                    "TerminalType": terminal_type
                }
            }
            drop_cables.append(drop_cable)
            connected_count += 1
            terminal_usage[terminal_id] += 1
    
    # Print statistics
    print(f"    Created {len(drop_cables)} drop cables ({connected_count}/{ont_count} ONTs connected)")
    if terminal_usage:
        avg_onts_per_terminal = sum(terminal_usage.values()) / len(terminal_usage)
        max_onts_per_terminal = max(terminal_usage.values())
        print(f"    Average ONTs per terminal: {avg_onts_per_terminal:.1f}")
        print(f"    Max ONTs per terminal: {max_onts_per_terminal}")
        print(f"    Drop cable size: {drop_cable_size}F")
    
    return drop_cables


def add_drop_cables_to_graph(
    graph,
    drop_cables: List[Dict[str, Any]]
):
    """
    Add drop cables to the network graph.
    This creates edges between ONTs and terminals.
    """
    for drop_cable in drop_cables:
        ont_id = drop_cable.get("ont_id")
        terminal_id = drop_cable.get("terminal_id")
        coords = drop_cable.get("coordinates", [])
        
        if not ont_id or not terminal_id or len(coords) < 2:
            continue
        
        # Ensure ONT node exists
        ont_pos = coords[0]
        if ont_id not in graph.nodes:
            graph.add_node(ont_id, "ont", ont_pos, {"ont_id": ont_id})
        
        # Ensure terminal node exists (should already exist from Phase 3)
        terminal_pos = coords[-1]
        if terminal_id not in graph.nodes:
            graph.add_node(terminal_id, "terminal", terminal_pos, {"terminal_id": terminal_id})
        
        # Create edge between ONT and terminal
        ont_node = graph.nodes[ont_id]
        terminal_node = graph.nodes[terminal_id]
        
        # Add edge from ONT to terminal
        if (terminal_id, None, "drop_cable") not in ont_node.edges:
            ont_node.edges.append((terminal_id, None, "drop_cable"))
        
        # Add edge from terminal to ONT
        if (ont_id, None, "drop_cable") not in terminal_node.edges:
            terminal_node.edges.append((ont_id, None, "drop_cable"))
    
    print(f"    Added {len(drop_cables)} drop cable connections to graph")
