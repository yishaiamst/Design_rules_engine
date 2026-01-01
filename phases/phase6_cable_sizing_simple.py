#!/usr/bin/env python3
"""
phase6_cable_sizing_simple.py
-------------------------------------------------------------------------------
Phase 6: Cable Sizing & ID Allocation (Simplified, Fast Version)

Simplified strategy for performance:
1. Assign ONTs to nearest cable (spatial proximity)
2. Count ONTs per cable
3. Calculate required cable size
4. Assign cable IDs

This is much faster than building a full connectivity graph.
-------------------------------------------------------------------------------
"""

import json
import math
import time
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from utils.spatial_utils import euclidean_distance, point_to_line_distance
from utils.geojson_utils import create_feature, create_feature_collection
from phases.phase1_place_olts import calculate_required_cable_size

MAX_ONT_TO_CABLE_DISTANCE_M = 500.0  # Maximum distance for ONT to cable assignment

def assign_onts_to_cables(
    cables: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any]
) -> Dict[int, List[str]]:
    """
    Assign ONTs to nearest cable using spatial proximity.
    Much faster than building full connectivity graph.
    """
    print("  Assigning ONTs to cables (spatial proximity)...")
    start_time = time.time()
    
    # Extract ONTs
    onts = []
    for feature in ont_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                onts.append({
                    "id": props.get("ID") or props.get("id", ""),
                    "position": (coords[0], coords[1])
                })
    
    print(f"    Loaded {len(onts)} ONTs")
    
    # Assign each ONT to nearest cable
    cable_ont_assignments = defaultdict(list)
    
    for ont_idx, ont in enumerate(onts):
        if ont_idx % 1000 == 0 and ont_idx > 0:
            elapsed = time.time() - start_time
            print(f"      Processed {ont_idx}/{len(onts)} ONTs ({elapsed:.1f}s)...")
        
        ont_pos = ont["position"]
        nearest_cable_idx = None
        min_dist = float('inf')
        
        for cable_idx, cable in enumerate(cables):
            coords = cable["coordinates"]
            
            # Quick bounding box check
            min_x = min(c[0] for c in coords)
            max_x = max(c[0] for c in coords)
            min_y = min(c[1] for c in coords)
            max_y = max(c[1] for c in coords)
            
            if (ont_pos[0] < min_x - MAX_ONT_TO_CABLE_DISTANCE_M or
                ont_pos[0] > max_x + MAX_ONT_TO_CABLE_DISTANCE_M or
                ont_pos[1] < min_y - MAX_ONT_TO_CABLE_DISTANCE_M or
                ont_pos[1] > max_y + MAX_ONT_TO_CABLE_DISTANCE_M):
                continue
            
            # Find minimum distance to cable
            for i in range(len(coords) - 1):
                dist = point_to_line_distance(
                    ont_pos,
                    coords[i],
                    coords[i + 1]
                )
                if dist < min_dist:
                    min_dist = dist
                    nearest_cable_idx = cable_idx
                
                # Early termination if very close
                if min_dist < 10.0:
                    break
        
        # Assign ONT to nearest cable if within threshold
        if nearest_cable_idx is not None and min_dist <= MAX_ONT_TO_CABLE_DISTANCE_M:
            cable_ont_assignments[nearest_cable_idx].append(ont["id"])
    
    elapsed = time.time() - start_time
    total_assigned = sum(len(onts) for onts in cable_ont_assignments.values())
    print(f"    Assigned {total_assigned} ONTs to {len(cable_ont_assignments)} cables ({elapsed:.1f}s)")
    
    return dict(cable_ont_assignments)

def assign_cable_ids(
    sized_cables: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    olts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Assign cable IDs following pattern: {SIZE}FOC/{FROM_ID}/{TO_ID}"""
    print("  Assigning cable IDs...")
    
    # Build index of nodes by position
    node_by_position = {}
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            node_by_position[pos] = fosc.get("fosc_id", "")
    
    for olt in olts:
        pos = olt.get("position")
        if pos:
            node_by_position[pos] = olt.get("olt_id", "")
    
    # Assign IDs
    cable_id_counter = 1
    for cable in sized_cables:
        size = cable.get("fiber_count", 0)
        coords = cable.get("coordinates", [])
        
        if not coords:
            continue
        
        # Find FROM and TO nodes
        start_point = coords[0]
        end_point = coords[-1]
        
        from_node = None
        to_node = None
        min_dist_start = float('inf')
        min_dist_end = float('inf')
        
        for pos, node_id in node_by_position.items():
            dist_start = euclidean_distance(start_point[0], start_point[1], pos[0], pos[1])
            dist_end = euclidean_distance(end_point[0], end_point[1], pos[0], pos[1])
            
            if dist_start < min_dist_start:
                min_dist_start = dist_start
                from_node = node_id
            
            if dist_end < min_dist_end:
                min_dist_end = dist_end
                to_node = node_id
        
        # Generate placeholder IDs if needed
        if not from_node:
            from_node = f"F{cable_id_counter:07d}"
        if not to_node:
            to_node = f"F{cable_id_counter + 1:07d}"
        
        cable_id = f"{size}FOC/{from_node}/{to_node}"
        cable["cable_id"] = cable_id
        cable["from_id"] = from_node
        cable["to_id"] = to_node
        
        cable_id_counter += 2
    
    print(f"    Assigned IDs to {len(sized_cables)} cables")
    return sized_cables

def size_cables(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    olts: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Size all cables and assign IDs (simplified, fast version)."""
    print("  Sizing cables and assigning IDs (simplified approach)...")
    start_time = time.time()
    
    # Extract cables
    cables = []
    for i, feature in enumerate(fiber_cable_geojson.get("features", [])):
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
                    "index": i,
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    print(f"    Loaded {len(cables)} cables ({time.time() - start_time:.1f}s)")
    
    # Assign ONTs to cables
    cable_ont_assignments = assign_onts_to_cables(cables, ont_geojson)
    
    # Calculate required size for each cable
    print("  Calculating required cable sizes...")
    sized_cables = []
    size_distribution = defaultdict(int)
    
    for i, cable in enumerate(cables):
        ont_count = len(cable_ont_assignments.get(i, []))
        required_size = calculate_required_cable_size(ont_count, config)
        
        sized_cable = {
            "index": i,
            "original_id": cable.get("id", ""),
            "coordinates": cable["coordinates"],
            "fiber_count": required_size,
            "downstream_onts": ont_count,
            "properties": cable.get("properties", {})
        }
        
        sized_cables.append(sized_cable)
        size_distribution[required_size] += 1
    
    # Assign cable IDs
    sized_cables = assign_cable_ids(sized_cables, foscs, olts)
    
    # Generate summary
    total_time = time.time() - start_time
    summary = {
        "total_cables": len(sized_cables),
        "size_distribution": dict(size_distribution),
        "total_onts_assigned": sum(len(onts) for onts in cable_ont_assignments.values()),
        "average_onts_per_cable": sum(len(onts) for onts in cable_ont_assignments.values()) / len(cable_ont_assignments) if cable_ont_assignments else 0,
        "processing_time_seconds": total_time
    }
    
    print(f"  ✓ Sized {len(sized_cables)} cables ({total_time:.1f}s total)")
    print(f"    Size distribution: {dict(size_distribution)}")
    
    return (sized_cables, summary)

def generate_sized_cable_geojson(sized_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for sized cables."""
    features = []
    
    for cable in sized_cables:
        coords = cable["coordinates"]
        
        properties = {
            "ID": cable.get("cable_id", ""),
            "Size": f"{cable.get('fiber_count', 0)}F",
            "FiberCount": str(cable.get("fiber_count", 0)),
            "downstream_onts": cable.get("downstream_onts", 0),
            "From_ID": cable.get("from_id", ""),
            "To_ID": cable.get("to_id", "")
        }
        
        original_props = cable.get("properties", {})
        for key in ["Owner", "CableCateg", "CableType", "Placement", "Status"]:
            if key in original_props:
                properties[key] = original_props[key]
        
        geometry = {
            "type": "LineString" if len(coords) > 0 else "MultiLineString",
            "coordinates": coords if len(coords) > 0 else [coords]
        }
        
        feature = create_feature(geometry, properties)
        features.append(feature)
    
    return create_feature_collection(features)


