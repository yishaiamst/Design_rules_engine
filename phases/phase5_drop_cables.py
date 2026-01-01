#!/usr/bin/env python3
"""
phase5_drop_cables.py
-------------------------------------------------------------------------------
Phase 5: Create Drop and Stub Cables

Strategy:
1. Drop Cables: Terminal → ONT (1F, configurable)
2. Stub Cables: MST → FOSC (size matches MST type)
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from utils.spatial_utils import euclidean_distance
from utils.geojson_utils import create_feature, create_feature_collection

def get_terminal_port_capacity(terminal: Dict[str, Any], config: Dict[str, Any]) -> int:
    """Get port capacity for a terminal based on its type and model."""
    terminal_type = terminal.get("type", "")
    terminal_model = terminal.get("model", "")
    
    if terminal_type == "MST":
        mst_config = config.get("equipment", {}).get("mst", {})
        ports = mst_config.get(terminal_model, {}).get("ports", 12)
        return ports
    elif terminal_type == "Aerial Terminal":
        aerial_config = config.get("equipment", {}).get("aerial_terminal", {})
        ports = aerial_config.get(terminal_model, {}).get("ports", 12)
        return ports
    
    return 12  # Default

def create_drop_cables(
    terminals: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Create drop cables from terminals to ONTs.
    
    Args:
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        config: Configuration dictionary
    
    Returns:
        (drop_cables_list, summary_stats)
    """
    print("  Creating drop cables (Terminal → ONT)...")
    
    # Get configuration
    drop_cable_config = config.get("cables", {}).get("drop_cable", {})
    default_drop_size = drop_cable_config.get("default_size", 1)
    
    # Load ONTs
    onts = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            onts[ont_id] = {
                "id": ont_id,
                "position": (coords[0], coords[1])
            }
    
    print(f"    Loaded {len(onts)} ONTs")
    
    # Create drop cables for each terminal
    drop_cables = []
    drop_cable_id_counter = 1
    summary = {
        "total_drop_cables": 0,
        "total_length_m": 0.0,
        "by_terminal_type": defaultdict(int),
        "terminals_at_capacity": 0,
        "onts_not_connected": 0,
        "length_stats": {
            "min": float('inf'),
            "max": 0.0,
            "total": 0.0,
            "count": 0
        }
    }
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id")
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        connected_ont_ids = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_ont_ids:
            continue
        
        # Get terminal port capacity from model
        port_capacity = get_terminal_port_capacity(terminal, config)
        
        # IMPORTANT: Respect terminal port limit
        # Only create drop cables up to the port capacity
        original_ont_count = len(connected_ont_ids)
        ont_ids_to_connect = connected_ont_ids[:port_capacity]
        
        if original_ont_count > port_capacity:
            summary["terminals_at_capacity"] += 1
            summary["onts_not_connected"] += original_ont_count - port_capacity
            print(f"    ⚠️  Terminal {terminal_id} ({terminal_type} {terminal.get('model', '')}) has {original_ont_count} ONTs but only {port_capacity} ports. Limiting to {port_capacity} drop cables.")
        
        # Create drop cable for each ONT (up to port capacity)
        for ont_id in ont_ids_to_connect:
            if ont_id not in onts:
                continue
            
            ont_pos = onts[ont_id]["position"]
            
            # Calculate drop cable length
            length = euclidean_distance(
                terminal_pos[0], terminal_pos[1],
                ont_pos[0], ont_pos[1]
            )
            
            # Create drop cable feature
            drop_cable_id = f"DC{drop_cable_id_counter:07d}"
            drop_cable = {
                "cable_id": drop_cable_id,
                "from_id": terminal_id,
                "to_id": ont_id,
                "from_type": "terminal",
                "to_type": "ont",
                "size": default_drop_size,
                "length_m": length,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [terminal_pos[0], terminal_pos[1]],
                        [ont_pos[0], ont_pos[1]]
                    ]
                }
            }
            
            drop_cables.append(drop_cable)
            drop_cable_id_counter += 1
            summary["total_drop_cables"] += 1
            summary["total_length_m"] += length
            summary["by_terminal_type"][terminal_type] += 1
            
            # Update length stats
            if length < summary["length_stats"]["min"]:
                summary["length_stats"]["min"] = length
            if length > summary["length_stats"]["max"]:
                summary["length_stats"]["max"] = length
            summary["length_stats"]["total"] += length
            summary["length_stats"]["count"] += 1
    
    # Calculate average length
    if summary["length_stats"]["count"] > 0:
        summary["length_stats"]["average"] = summary["length_stats"]["total"] / summary["length_stats"]["count"]
        sorted_lengths = sorted([dc["length_m"] for dc in drop_cables])
        summary["length_stats"]["median"] = sorted_lengths[len(sorted_lengths) // 2] if sorted_lengths else 0.0
    else:
        summary["length_stats"]["average"] = 0.0
        summary["length_stats"]["median"] = 0.0
        summary["length_stats"]["min"] = 0.0
    
    print(f"  ✓ Created {summary['total_drop_cables']} drop cables")
    print(f"    Total length: {summary['total_length_m']:.1f}m")
    print(f"    Average length: {summary['length_stats']['average']:.1f}m")
    print(f"    Median length: {summary['length_stats']['median']:.1f}m")
    print(f"    By type: {dict(summary['by_terminal_type'])}")
    
    return (drop_cables, summary)

def create_stub_cables(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Create stub cables from MST terminals to FOSCs.
    IMPORTANT: Stub cable size matches MST port count (MST12 → 12F, MST6 → 6F, etc.)
    
    Args:
        terminals: List of terminal dictionaries (only MSTs will be used)
        foscs: List of FOSC dictionaries
        config: Configuration dictionary
    
    Returns:
        (stub_cables_list, summary_stats)
    """
    print("  Creating stub cables (MST → FOSC)...")
    
    # Get MST configuration
    mst_config = config.get("equipment", {}).get("mst", {})
    
    # Build FOSC position map
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id")
        fosc_pos = fosc.get("position")
        if fosc_id and fosc_pos:
            fosc_positions[fosc_id] = fosc_pos
    
    print(f"    Loaded {len(fosc_positions)} FOSCs")
    
    # Create stub cables for MST terminals
    stub_cables = []
    stub_cable_id_counter = 1
    summary = {
        "total_stub_cables": 0,
        "total_length_m": 0.0,
        "by_mst_type": defaultdict(int),
        "length_stats": {
            "min": float('inf'),
            "max": 0.0,
            "total": 0.0,
            "count": 0
        }
    }
    
    for terminal in terminals:
        terminal_type = terminal.get("type", "")
        if terminal_type != "MST":
            continue
        
        terminal_id = terminal.get("terminal_id")
        terminal_pos = terminal.get("position")
        terminal_model = terminal.get("model", "MST12")
        nearest_fosc_id = terminal.get("nearest_fosc_id")
        distance_to_fosc = terminal.get("distance_to_fosc_m")
        
        if not terminal_pos:
            continue
        
        # Find FOSC for this MST
        target_fosc_id = None
        target_fosc_pos = None
        
        if nearest_fosc_id and nearest_fosc_id in fosc_positions:
            target_fosc_id = nearest_fosc_id
            target_fosc_pos = fosc_positions[nearest_fosc_id]
        else:
            # Find nearest FOSC
            min_dist = float('inf')
            for fosc_id, fosc_pos in fosc_positions.items():
                dist = euclidean_distance(
                    terminal_pos[0], terminal_pos[1],
                    fosc_pos[0], fosc_pos[1]
                )
                if dist < min_dist:
                    min_dist = dist
                    target_fosc_id = fosc_id
                    target_fosc_pos = fosc_pos
        
        if not target_fosc_id or not target_fosc_pos:
            continue
        
        # Calculate stub cable length
        length = euclidean_distance(
            terminal_pos[0], terminal_pos[1],
            target_fosc_pos[0], target_fosc_pos[1]
        )
        
        # Get stub cable size from MST model
        # CRITICAL: Stub cable size MUST match MST port count
        # MST4=4F, MST6=6F, MST8=8F, MST12=12F
        # This is the key relationship: stub cable size = MST port count
        stub_size = mst_config.get(terminal_model, {}).get("ports", 12)
        
        # Create stub cable feature
        stub_cable_id = f"SC{stub_cable_id_counter:07d}"
        stub_cable = {
            "cable_id": stub_cable_id,
            "from_id": terminal_id,
            "to_id": target_fosc_id,
            "from_type": "terminal",
            "to_type": "fosc",
            "size": stub_size,
            "length_m": length,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [terminal_pos[0], terminal_pos[1]],
                    [target_fosc_pos[0], target_fosc_pos[1]]
                ]
            }
        }
        
        stub_cables.append(stub_cable)
        stub_cable_id_counter += 1
        summary["total_stub_cables"] += 1
        summary["total_length_m"] += length
        summary["by_mst_type"][terminal_model] += 1
        
        # Update length stats
        if length < summary["length_stats"]["min"]:
            summary["length_stats"]["min"] = length
        if length > summary["length_stats"]["max"]:
            summary["length_stats"]["max"] = length
        summary["length_stats"]["total"] += length
        summary["length_stats"]["count"] += 1
    
    # Calculate average length
    if summary["length_stats"]["count"] > 0:
        summary["length_stats"]["average"] = summary["length_stats"]["total"] / summary["length_stats"]["count"]
        sorted_lengths = sorted([sc["length_m"] for sc in stub_cables])
        summary["length_stats"]["median"] = sorted_lengths[len(sorted_lengths) // 2] if sorted_lengths else 0.0
    else:
        summary["length_stats"]["average"] = 0.0
        summary["length_stats"]["median"] = 0.0
        summary["length_stats"]["min"] = 0.0
    
    print(f"  ✓ Created {summary['total_stub_cables']} stub cables")
    print(f"    Total length: {summary['total_length_m']:.1f}m")
    print(f"    Average length: {summary['length_stats']['average']:.1f}m")
    print(f"    Median length: {summary['length_stats']['median']:.1f}m")
    print(f"    By MST type: {dict(summary['by_mst_type'])}")
    
    return (stub_cables, summary)

def generate_drop_cable_geojson(drop_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for drop cables."""
    features = []
    
    for cable in drop_cables:
        properties = {
            "ID": cable["cable_id"],
            "From": cable["from_id"],
            "To": cable["to_id"],
            "Size": f"{cable['size']}F",
            "Length_m": round(cable["length_m"], 2)
        }
        
        geometry = cable["geometry"]
        feature = create_feature(geometry, properties)
        features.append(feature)
    
    return create_feature_collection(features)

def generate_stub_cable_geojson(stub_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for stub cables."""
    features = []
    
    for cable in stub_cables:
        properties = {
            "ID": cable["cable_id"],
            "From": cable["from_id"],
            "To": cable["to_id"],
            "Size": f"{cable['size']}F",
            "Length_m": round(cable["length_m"], 2)
        }
        
        geometry = cable["geometry"]
        feature = create_feature(geometry, properties)
        features.append(feature)
    
    return create_feature_collection(features)

