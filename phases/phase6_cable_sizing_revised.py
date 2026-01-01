#!/usr/bin/env python3
"""
phase6_cable_sizing_revised.py
-------------------------------------------------------------------------------
Phase 6: Cable Sizing & ID Assignment (Revised)

Key Features:
1. Configuration Override: User can set default_size_override (e.g., 96F) for all cables
2. Formula-Based Sizing: Calculate based on service requirements
3. FOSC Aggregation: At FOSCs, sum incoming cable sizes (from infrastructure/OLT side)
4. Max Size Limit: Cap at max_size (default 288F, configurable)
5. Safety Margin: Use larger size even if formula doesn't require it
6. Cable ID Assignment: Only after FOSCs and terminals are placed

Process:
1. Check for default_size_override (if set, use for all cables)
2. Calculate sizes based on service formula (ONT count → fiber requirement)
3. At FOSCs: Aggregate incoming cable sizes (sum them)
4. Apply max_size limit
5. Assign cable IDs using FOSCs and terminals as FROM/TO nodes
-------------------------------------------------------------------------------
"""

import json
import math
import time
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import defaultdict, deque
from utils.spatial_utils import euclidean_distance, point_to_line_distance
from utils.geojson_utils import create_feature, create_feature_collection
from phases.phase1_place_olts import calculate_required_cable_size
from utils.intersection_utils import find_cable_junctions_geometric


def calculate_required_fibers_from_onts(ont_count: int, config: Dict[str, Any]) -> int:
    """
    Calculate required fiber count based on ONT count using service formula.
    
    Args:
        ont_count: Number of ONTs downstream
        config: Configuration dictionary
        
    Returns:
        Required fiber count
    """
    if ont_count == 0:
        return 0
    
    # Use the existing calculate_required_cable_size function
    return calculate_required_cable_size(ont_count, config)


def aggregate_cables_at_fosc(
    incoming_sizes: List[int],
    standard_sizes: List[int],
    max_size: int
) -> int:
    """
    Aggregate cable sizes at FOSC.
    
    Rule: Sum incoming cable sizes, then round up to next standard size.
    Example: 48F + 48F = 96F (even if formula says 48F is enough)
    
    Args:
        incoming_sizes: List of incoming cable sizes (from infrastructure/OLT side)
        standard_sizes: Available standard cable sizes
        max_size: Maximum allowed cable size
        
    Returns:
        Aggregated cable size
    """
    if not incoming_sizes:
        return 0
    
    # Sum all incoming sizes
    total_fibers = sum(incoming_sizes)
    
    # Round up to next standard size
    matching_sizes = [s for s in standard_sizes if s >= total_fibers]
    if matching_sizes:
        aggregated_size = min(matching_sizes)
    else:
        # Exceeds all standard sizes - use max_size
        aggregated_size = max_size
    
    # Apply max_size limit
    aggregated_size = min(aggregated_size, max_size)
    
    return aggregated_size


def find_cables_at_fosc(
    fosc_position: Tuple[float, float],
    cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[int]:
    """
    Find cables that connect to a FOSC (within tolerance).
    
    Args:
        fosc_position: FOSC position (x, y)
        cables: List of cable dicts
        tolerance_m: Distance tolerance
        
    Returns:
        List of cable indices that connect to this FOSC
    """
    connected_cables = []
    
    for i, cable in enumerate(cables):
        coords = cable.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        # Check if FOSC is at cable start or end
        start = coords[0]
        end = coords[-1]
        
        dist_to_start = euclidean_distance(
            fosc_position[0], fosc_position[1],
            start[0], start[1]
        )
        dist_to_end = euclidean_distance(
            fosc_position[0], fosc_position[1],
            end[0], end[1]
        )
        
        if dist_to_start <= tolerance_m or dist_to_end <= tolerance_m:
            connected_cables.append(i)
    
    return connected_cables


def determine_cable_direction_at_fosc(
    fosc_position: Tuple[float, float],
    cable_idx: int,
    cables: List[Dict[str, Any]],
    olts: List[Dict[str, Any]]
) -> str:
    """
    Determine if cable is incoming (from infrastructure/OLT) or outgoing (to ONTs).
    
    Strategy:
    - Incoming: Cable endpoint closer to FOSC is closer to OLT
    - Outgoing: Cable endpoint closer to FOSC is farther from OLT
    
    Args:
        fosc_position: FOSC position
        cable_idx: Cable index
        cables: List of cable dicts
        olts: List of OLTs
        
    Returns:
        "incoming" or "outgoing"
    """
    cable = cables[cable_idx]
    coords = cable.get("coordinates", [])
    if len(coords) < 2:
        return "outgoing"
    
    start = coords[0]
    end = coords[-1]
    
    # Find nearest OLT
    min_olt_dist = float('inf')
    nearest_olt_pos = None
    
    for olt in olts:
        olt_pos = olt.get("position")
        if olt_pos:
            dist = euclidean_distance(
                fosc_position[0], fosc_position[1],
                olt_pos[0], olt_pos[1]
            )
            if dist < min_olt_dist:
                min_olt_dist = dist
                nearest_olt_pos = olt_pos
    
    if not nearest_olt_pos:
        return "outgoing"
    
    # Check which endpoint is closer to OLT
    dist_start_to_olt = euclidean_distance(
        start[0], start[1],
        nearest_olt_pos[0], nearest_olt_pos[1]
    )
    dist_end_to_olt = euclidean_distance(
        end[0], end[1],
        nearest_olt_pos[0], nearest_olt_pos[1]
    )
    
    # Check which endpoint is at FOSC
    dist_start_to_fosc = euclidean_distance(
        start[0], start[1],
        fosc_position[0], fosc_position[1]
    )
    dist_end_to_fosc = euclidean_distance(
        end[0], end[1],
        fosc_position[0], fosc_position[1]
    )
    
    # If start is at FOSC and start is closer to OLT → incoming
    # If end is at FOSC and end is closer to OLT → incoming
    if dist_start_to_fosc < dist_end_to_fosc:
        # Start is at FOSC
        if dist_start_to_olt < dist_end_to_olt:
            return "incoming"
        else:
            return "outgoing"
    else:
        # End is at FOSC
        if dist_end_to_olt < dist_start_to_olt:
            return "incoming"
        else:
            return "outgoing"


def size_cables(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    olts: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Size cables with FOSC aggregation logic.
    
    Args:
        fiber_cable_geojson: Input cable GeoJSON
        foscs: List of FOSCs (for aggregation)
        terminals: List of terminals (for context)
        olts: List of OLTs
        ont_geojson: ONT GeoJSON
        config: Configuration dictionary
        
    Returns:
        Tuple of (sized_cables_list, summary_dict)
    """
    print("  Sizing cables (Service Formula + FOSC Aggregation)...")
    start_time = time.time()
    
    # Get configuration
    infrastructure_config = config.get("cables", {}).get("infrastructure_cable", {})
    standard_sizes = infrastructure_config.get("standard_sizes", [12, 24, 48, 72, 96, 144, 288])
    default_size_override = infrastructure_config.get("default_size_override")  # User override
    max_size = infrastructure_config.get("max_size", 288)  # Maximum cable size
    min_infrastructure_size = 48  # Minimum infrastructure size
    
    # Check for default size override
    if default_size_override is not None:
        print(f"    ⚠️  Using default size override: {default_size_override}F for all infrastructure cables")
        print(f"    (This takes priority over formula-based sizing)")
    
    # Extract cables
    print("    Extracting cables...")
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
    
    print(f"    Loaded {len(cables)} cables")
    
    # Extract ONTs for capacity calculation
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
    
    print(f"    Loaded {len(onts)} ONTs")
    
    # Step 1: If default_size_override is set, use it for all cables
    if default_size_override is not None:
        print(f"    Applying default size override: {default_size_override}F")
        sized_cables = []
        for cable in cables:
            sized_cables.append({
                "index": cable["index"],
                "original_id": cable.get("id", ""),
                "coordinates": cable["coordinates"],
                "fiber_count": default_size_override,
                "required_fibers": default_size_override,
                "downstream_onts": 0,
                "sizing_method": "default_override",
                "properties": cable.get("properties", {})
            })
        
        # Assign cable IDs
        print("    Assigning cable IDs...")
        sized_cables = assign_cable_ids(sized_cables, foscs, terminals, olts)
        
        summary = {
            "total_cables": len(sized_cables),
            "default_size_override": default_size_override,
            "sizing_method": "default_override"
        }
        
        print(f"  ✓ Sized {len(sized_cables)} cables using default override ({default_size_override}F)")
        return sized_cables, summary
    
    # Step 2: Calculate initial sizes based on service formula
    print("    Calculating initial sizes from service formula...")
    cable_sizes = {}  # cable_idx -> fiber_count
    cable_ont_counts = {}  # cable_idx -> ONT count
    
    # Map OLTs to cables
    cable_olt_map = defaultdict(list)
    for olt in olts:
        olt_pos = olt.get("position")
        olt_id = olt.get("olt_id")
        ont_count = olt.get("ont_count", 0)
        
        if not olt_pos or ont_count == 0:
            continue
        
        # Find nearest cable to OLT
        nearest_cable_idx = None
        min_dist = float('inf')
        
        for i, cable in enumerate(cables):
            coords = cable.get("coordinates", [])
            if len(coords) < 2:
                continue
            
            # Check distance to cable
            for j in range(len(coords) - 1):
                dist = point_to_line_distance(olt_pos, coords[j], coords[j + 1])
                if dist < min_dist:
                    min_dist = dist
                    nearest_cable_idx = i
        
        if nearest_cable_idx is not None and min_dist < 1000.0:  # Within 1km
            cable_olt_map[nearest_cable_idx].append({
                "olt_id": olt_id,
                "ont_count": ont_count
            })
    
    # Calculate sizes for OLT-connected cables
    for cable_idx, olt_list in cable_olt_map.items():
        total_onts = sum(olt["ont_count"] for olt in olt_list)
        cable_ont_counts[cable_idx] = total_onts
        
        # Calculate required fibers from service formula
        required_fibers = calculate_required_fibers_from_onts(total_onts, config)
        required_fibers = max(required_fibers, min_infrastructure_size)
        
        # Round to standard size
        matching_sizes = [s for s in standard_sizes if s >= required_fibers]
        if matching_sizes:
            cable_size = min(matching_sizes)
        else:
            cable_size = max_size
        
        # Apply max_size limit
        cable_size = min(cable_size, max_size)
        cable_sizes[cable_idx] = cable_size
    
    # Initialize other cables with minimum size
    for i in range(len(cables)):
        if i not in cable_sizes:
            cable_sizes[i] = min_infrastructure_size
    
    print(f"    Initialized {len(cable_olt_map)} cables with OLT connections")
    
    # Step 3: Apply FOSC aggregation logic
    print("    Applying FOSC aggregation logic...")
    fosc_aggregations = 0
    
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            continue
        
        # Find cables at this FOSC
        connected_cable_indices = find_cables_at_fosc(fosc_pos, cables, tolerance_m=10.0)
        
        if len(connected_cable_indices) < 2:
            continue  # Need at least 2 cables for aggregation
        
        # Separate incoming (from infrastructure/OLT) and outgoing (to ONTs)
        incoming_cables = []
        outgoing_cables = []
        
        for cable_idx in connected_cable_indices:
            direction = determine_cable_direction_at_fosc(fosc_pos, cable_idx, cables, olts)
            if direction == "incoming":
                incoming_cables.append(cable_idx)
            else:
                outgoing_cables.append(cable_idx)
        
        # Aggregate incoming cable sizes
        if len(incoming_cables) >= 2:
            incoming_sizes = [cable_sizes.get(idx, min_infrastructure_size) for idx in incoming_cables]
            aggregated_size = aggregate_cables_at_fosc(incoming_sizes, standard_sizes, max_size)
            
            # Apply aggregated size to all outgoing cables at this FOSC
            for outgoing_idx in outgoing_cables:
                current_size = cable_sizes.get(outgoing_idx, min_infrastructure_size)
                # Use larger of current size or aggregated size (safety margin)
                cable_sizes[outgoing_idx] = max(current_size, aggregated_size)
                fosc_aggregations += 1
        
        # Also update incoming cables if they need to match
        if len(incoming_cables) >= 2:
            incoming_sizes = [cable_sizes.get(idx, min_infrastructure_size) for idx in incoming_cables]
            aggregated_size = aggregate_cables_at_fosc(incoming_sizes, standard_sizes, max_size)
            
            # Ensure at least one incoming cable has aggregated size
            max_incoming_size = max(incoming_sizes)
            if aggregated_size > max_incoming_size:
                # Update the cable closest to OLT
                incoming_cables.sort(key=lambda idx: min(
                    euclidean_distance(fosc_pos[0], fosc_pos[1], cables[idx]["coordinates"][0][0], cables[idx]["coordinates"][0][1]),
                    euclidean_distance(fosc_pos[0], fosc_pos[1], cables[idx]["coordinates"][-1][0], cables[idx]["coordinates"][-1][1])
                ))
                cable_sizes[incoming_cables[0]] = aggregated_size
    
    print(f"    Applied {fosc_aggregations} FOSC aggregations")
    
    # Step 4: Create sized cables
    print("    Creating sized cable list...")
    sized_cables = []
    size_distribution = defaultdict(int)
    
    for i, cable in enumerate(cables):
        fiber_count = cable_sizes.get(i, min_infrastructure_size)
        ont_count = cable_olt_map.get(i, [])
        total_onts = sum(olt["ont_count"] for olt in ont_count)
        
        sized_cables.append({
            "index": i,
            "original_id": cable.get("id", ""),
            "coordinates": cable["coordinates"],
            "fiber_count": fiber_count,
            "required_fibers": fiber_count,  # Will be refined
            "downstream_onts": total_onts,
            "olt_connections": ont_count,
            "connected_olts": [olt["olt_id"] for olt in ont_count],
            "properties": cable.get("properties", {}),
            "sizing_method": "formula_and_aggregation"
        })
        
        size_distribution[fiber_count] += 1
    
    # Step 5: Assign cable IDs (after FOSCs and terminals are placed)
    print("    Assigning cable IDs...")
    sized_cables = assign_cable_ids(sized_cables, foscs, terminals, olts)
    
    # Generate summary
    total_time = time.time() - start_time
    summary = {
        "total_cables": len(sized_cables),
        "size_distribution": dict(size_distribution),
        "cables_with_olts": len(cable_olt_map),
        "fosc_aggregations": fosc_aggregations,
        "max_size": max_size,
        "default_size_override": default_size_override,
        "total_onts_served": sum(sum(olt["ont_count"] for olt in cable_olt_map.get(i, [])) for i in range(len(cables))),
        "processing_time_seconds": total_time
    }
    
    print(f"  ✓ Sized {len(sized_cables)} cables ({total_time:.1f}s)")
    print(f"    Size distribution: {dict(size_distribution)}")
    print(f"    FOSC aggregations: {fosc_aggregations}")
    print(f"    Max size limit: {max_size}F")
    
    return sized_cables, summary


def assign_cable_ids(
    sized_cables: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    olts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Assign cable IDs following pattern: {SIZE}FOC/{FROM_ID}/{TO_ID}
    
    Uses FOSCs, terminals, and OLTs as FROM/TO nodes.
    
    Args:
        sized_cables: List of sized cable dicts
        foscs: List of FOSC dicts
        terminals: List of terminal dicts
        olts: List of OLT dicts
        
    Returns:
        Updated sized_cables with cable_id, from_id, to_id
    """
    # Build index of nodes by position
    node_by_position = {}
    tolerance_m = 50.0
    
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            node_by_position[tuple(pos)] = {
                "id": fosc.get("fosc_id", ""),
                "type": "FOSC"
            }
    
    for terminal in terminals:
        pos = terminal.get("position")
        if pos:
            node_by_position[tuple(pos)] = {
                "id": terminal.get("terminal_id", ""),
                "type": "Terminal"
            }
    
    for olt in olts:
        pos = olt.get("position")
        if pos:
            node_by_position[tuple(pos)] = {
                "id": olt.get("olt_id", ""),
                "type": "OLT"
            }
    
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
        
        for pos, node_info in node_by_position.items():
            dist_start = euclidean_distance(start_point[0], start_point[1], pos[0], pos[1])
            dist_end = euclidean_distance(end_point[0], end_point[1], pos[0], pos[1])
            
            if dist_start < min_dist_start and dist_start < tolerance_m:
                min_dist_start = dist_start
                from_node = node_info["id"]
            
            if dist_end < min_dist_end and dist_end < tolerance_m:
                min_dist_end = dist_end
                to_node = node_info["id"]
        
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
    
    return sized_cables


def generate_sized_cable_geojson(sized_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for sized cables."""
    features = []
    
    for cable in sized_cables:
        coords = cable.get("coordinates", [])
        if not coords:
            continue
        
        # Convert to GeoJSON format
        geojson_coords = [[c[0], c[1]] for c in coords]
        
        feature = create_feature(
            geometry={
                "type": "LineString",
                "coordinates": geojson_coords
            },
            properties={
                "ID": cable.get("cable_id") or cable.get("original_id", ""),
                "Size": f"{cable.get('fiber_count', 0)}F",
                "FiberCount": cable.get("fiber_count", 0),
                "from_id": cable.get("from_id", ""),
                "to_id": cable.get("to_id", ""),
                "required_fibers": cable.get("required_fibers", 0),
                "downstream_onts": cable.get("downstream_onts", 0),
                "connected_olts": cable.get("connected_olts", []),
                "sizing_method": cable.get("sizing_method", "")
            }
        )
        features.append(feature)
    
    return create_feature_collection(features)

