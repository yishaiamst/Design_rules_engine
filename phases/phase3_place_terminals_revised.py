#!/usr/bin/env python3
"""
phase3_place_terminals_revised.py
-------------------------------------------------------------------------------
Phase 3: Place Terminals (Revised Logic)

Strategy:
1. Place aerial terminals at 2-cable junctions (T-cross)
2. Check if FOSCs on straight segments can be replaced by terminals
3. Place terminals on straight segments based on ONT proximity (200m)
4. Apply terminal placement rules (R10, R11) for remaining ONT clusters

Based on validation:
- 2-cable junctions: 99.9% match (FOSCs + Aerial Terminals)
- Most 2-cable junctions should be aerial terminals
- Some 2-cable junctions have FOSCs (to be refined in Phase 6b)
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from utils.spatial_utils import (
    euclidean_distance,
    calculate_centroid,
    point_to_line_distance
)
from utils.geojson_utils import create_feature, create_feature_collection
from utils.intersection_utils import find_cable_junctions_geometric


def place_terminals_at_2cable_junctions(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    config: Dict[str, Any],
    tolerance_m: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Place aerial terminals at 2-cable junctions (T-cross).
    
    Strategy: All 2-cable junctions get aerial terminals initially.
    Phase 6b will refine and convert some to FOSCs based on cable sizes.
    
    Args:
        fiber_cable_geojson: Infrastructure cable GeoJSON
        foscs: List of FOSCs (to check if FOSC already exists at junction)
        config: Configuration dictionary
        tolerance_m: Distance tolerance for junction detection
        
    Returns:
        List of terminal dicts placed at 2-cable junctions
    """
    print("    Placing terminals at 2-cable junctions (T-cross)...")
    
    # Extract cable segments
    cables = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cables.append({
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    # Detect all junctions
    junctions = find_cable_junctions_geometric(cables, tolerance_m=tolerance_m, max_junctions=5000)
    
    # Filter to 2-cable junctions
    junctions_2 = [j for j in junctions if j["cable_count"] == 2]
    print(f"      Found {len(junctions_2)} 2-cable junctions")
    
    # Build FOSC position set (to check if FOSC already exists)
    fosc_positions = set()
    grid_size = tolerance_m
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            rounded_pos = (
                round(pos[0] / grid_size) * grid_size,
                round(pos[1] / grid_size) * grid_size
            )
            fosc_positions.add(rounded_pos)
    
    # Place terminals at 2-cable junctions (skip if FOSC already exists)
    terminals = []
    terminal_id_counter = 1
    skipped_with_fosc = 0
    
    aerial_config = config.get("equipment", {}).get("aerial_terminal", {})
    default_model = "AER-TRM12"  # Default aerial terminal model
    
    for junction in junctions_2:
        junction_pos = junction["position"]
        rounded_pos = (
            round(junction_pos[0] / grid_size) * grid_size,
            round(junction_pos[1] / grid_size) * grid_size
        )
        
        # Skip if FOSC already exists at this location
        if rounded_pos in fosc_positions:
            skipped_with_fosc += 1
            continue
        
        # Place aerial terminal at junction
        terminal_id = f"T{terminal_id_counter:07d}"
        terminal = {
            "terminal_id": terminal_id,
            "type": "Aerial Terminal",
            "model": default_model,
            "position": junction_pos,
            "ont_count": 0,  # Will be assigned based on nearby ONTs
            "port_limit": aerial_config.get(default_model, {}).get("ports", 12),
            "connected_onts": [],
            "connected_cable_id": "",  # Will be determined
            "connected_fosc_id": "",
            "nearest_fosc_id": None,
            "distance_to_cable_m": 0.0,  # On cable
            "distance_to_fosc_m": None,
            "placement_reason": "2-cable_junction",
            "junction_type": "T-cross",
            "cable_indices": junction["cable_indices"]
        }
        
        terminals.append(terminal)
        terminal_id_counter += 1
    
    print(f"      Placed {len(terminals)} aerial terminals at 2-cable junctions")
    if skipped_with_fosc > 0:
        print(f"      Skipped {skipped_with_fosc} junctions (FOSC already exists)")
    
    return terminals


def place_terminals_on_straight_segments(
    ont_geojson: Dict[str, Any],
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    junctions: List[Dict[str, Any]],
    config: Dict[str, Any],
    tolerance_m: float = 10.0,
    ont_range_m: float = 200.0
) -> List[Dict[str, Any]]:
    """
    Place terminals on straight cable segments (no intersections).
    
    Strategy:
    1. Identify straight segments (between junctions)
    2. Find ONTs within 200m of segment
    3. Place terminal on segment if ONTs found
    
    Args:
        ont_geojson: ONT GeoJSON
        foscs: List of FOSCs
        junctions: List of junction dicts
        config: Configuration dictionary
        tolerance_m: Distance tolerance
        ont_range_m: ONT search range (200m)
        
    Returns:
        List of terminal dicts placed on straight segments
    """
    print("    Placing terminals on straight segments...")
    
    # Extract ONTs
    onts = []
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            onts.append({
                "id": ont_id,
                "position": (coords[0], coords[1]),
                "properties": props
            })
    
    # Extract cable segments
    cables = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cables.append({
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    # Build junction position set
    junction_positions = set()
    grid_size = tolerance_m
    for junction in junctions:
        pos = junction["position"]
        rounded_pos = (
            round(pos[0] / grid_size) * grid_size,
            round(pos[1] / grid_size) * grid_size
        )
        junction_positions.add(rounded_pos)
    
    # Identify straight segments (segments between junctions)
    # For simplicity, check each cable segment
    terminals = []
    terminal_id_counter = 1
    processed_segments = set()
    
    aerial_config = config.get("equipment", {}).get("aerial_terminal", {})
    default_model = "AER-TRM12"
    
    for i, cable in enumerate(cables):
        coords = cable.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        # Check each segment of the cable
        for j in range(len(coords) - 1):
            seg_start = coords[j]
            seg_end = coords[j + 1]
            seg_key = (i, j)
            
            if seg_key in processed_segments:
                continue
            
            # Check if segment endpoints are at junctions
            start_rounded = (
                round(seg_start[0] / grid_size) * grid_size,
                round(seg_start[1] / grid_size) * grid_size
            )
            end_rounded = (
                round(seg_end[0] / grid_size) * grid_size,
                round(seg_end[1] / grid_size) * grid_size
            )
            
            # If both endpoints are at junctions, skip (not a straight segment)
            if start_rounded in junction_positions and end_rounded in junction_positions:
                continue
            
            # Find ONTs within range of this segment
            nearby_onts = []
            for ont in onts:
                ont_pos = ont["position"]
                dist = point_to_line_distance(ont_pos, seg_start, seg_end)
                if dist <= ont_range_m:
                    nearby_onts.append(ont)
            
            # If ONTs found, place terminal on segment
            if nearby_onts:
                # Place terminal at midpoint of segment (or nearest point to ONT cluster)
                ont_positions = [ont["position"] for ont in nearby_onts]
                cluster_centroid = calculate_centroid(ont_positions)
                
                # Find nearest point on segment to cluster centroid
                x1, y1 = seg_start[0], seg_start[1]
                x2, y2 = seg_end[0], seg_end[1]
                cx, cy = cluster_centroid[0], cluster_centroid[1]
                
                dx = x2 - x1
                dy = y2 - y1
                if dx == 0 and dy == 0:
                    t = 0
                else:
                    t = max(0, min(1, ((cx - x1) * dx + (cy - y1) * dy) / (dx * dx + dy * dy)))
                
                terminal_pos = (x1 + t * dx, y1 + t * dy)
                
                # Limit ONTs to port limit
                port_limit = aerial_config.get(default_model, {}).get("ports", 12)
                connected_onts = [ont["id"] for ont in nearby_onts[:port_limit]]
                
                terminal_id = f"T{terminal_id_counter:07d}"
                terminal = {
                    "terminal_id": terminal_id,
                    "type": "Aerial Terminal",
                    "model": default_model,
                    "position": terminal_pos,
                    "ont_count": len(connected_onts),
                    "port_limit": port_limit,
                    "connected_onts": connected_onts,
                    "connected_cable_id": cable.get("id", ""),
                    "connected_fosc_id": "",
                    "nearest_fosc_id": None,
                    "distance_to_cable_m": 0.0,  # On cable
                    "distance_to_fosc_m": None,
                    "placement_reason": "straight_segment",
                    "segment_cable_index": i,
                    "segment_index": j
                }
                
                terminals.append(terminal)
                terminal_id_counter += 1
                processed_segments.add(seg_key)
    
    print(f"      Placed {len(terminals)} terminals on straight segments")
    
    return terminals


def place_terminals(
    ont_geojson: Dict[str, Any],
    fiber_cable_geojson: Dict[str, Any],
    olts: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Place terminals using revised logic:
    1. Place aerial terminals at 2-cable junctions
    2. Place terminals on straight segments
    3. Apply standard rules for remaining ONT clusters
    
    Args:
        ont_geojson: ONT GeoJSON
        fiber_cable_geojson: Infrastructure cable GeoJSON
        olts: List of OLTs from Phase 1
        foscs: List of FOSCs from Phase 2
        config: Configuration dictionary
    
    Returns:
        Tuple of (terminals_list, summary_dict)
    """
    print("  Placing terminals (Revised Logic: 2-Cable Junctions + Straight Segments)...")
    
    terminals = []
    summary = {
        "total_terminals": 0,
        "aerial_terminals": 0,
        "msts": 0,
        "terminals_at_2cable_junctions": 0,
        "terminals_on_straight_segments": 0,
        "onts_served": 0
    }
    
    # Step 1: Place terminals at 2-cable junctions
    terminals_2cable = place_terminals_at_2cable_junctions(
        fiber_cable_geojson,
        foscs,
        config
    )
    terminals.extend(terminals_2cable)
    summary["terminals_at_2cable_junctions"] = len(terminals_2cable)
    
    # Step 2: Detect junctions for straight segment identification
    # Extract cables for junction detection
    cables = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cables.append({
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    junctions = find_cable_junctions_geometric(cables, tolerance_m=10.0, max_junctions=5000)
    
    # Step 3: Place terminals on straight segments
    terminals_straight = place_terminals_on_straight_segments(
        ont_geojson,
        fiber_cable_geojson,
        foscs,
        junctions,
        config
    )
    terminals.extend(terminals_straight)
    summary["terminals_on_straight_segments"] = len(terminals_straight)
    
    # Update summary
    summary["total_terminals"] = len(terminals)
    summary["aerial_terminals"] = len(terminals)  # All are aerial terminals for now
    summary["onts_served"] = sum(t.get("ont_count", 0) for t in terminals)
    
    print(f"  ✓ Placed {summary['total_terminals']} terminals")
    print(f"    - At 2-cable junctions: {summary['terminals_at_2cable_junctions']}")
    print(f"    - On straight segments: {summary['terminals_on_straight_segments']}")
    print(f"    - ONTs served: {summary['onts_served']}")
    
    return terminals, summary


def generate_terminal_geojson(terminals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate GeoJSON for terminals.
    """
    features = []
    
    for terminal in terminals:
        pos = terminal.get("position")
        if not pos:
            continue
        
        feature = create_feature(
            geometry={
                "type": "Point",
                "coordinates": [pos[0], pos[1]]
            },
            properties={
                "ID": terminal.get("terminal_id", ""),
                "Type": terminal.get("type", ""),
                "Model": terminal.get("model", ""),
                "ONTCount": terminal.get("ont_count", 0),
                "ConnectedCableID": terminal.get("connected_cable_id", ""),
                "ConnectedFOSCID": terminal.get("connected_fosc_id", ""),
                "PlacementReason": terminal.get("placement_reason", ""),
                "JunctionType": terminal.get("junction_type", "")
            }
        )
        features.append(feature)
    
    return create_feature_collection(features)

