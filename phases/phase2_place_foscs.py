#!/usr/bin/env python3
"""
phase2_place_foscs.py
-------------------------------------------------------------------------------
Phase 2: Place FOSCs (Topology-Based)

Strategy:
1. Group cable segments into logical cables (topology-based)
2. Detect junctions between logical cables (endpoint + mid-segment)
3. Categorize junctions: T-cross (2), Y (3), 4+ way
4. Place FOSCs at ALL junctions (2+, 3+, 4+)
5. Place FOSCs every 2km along long cable runs
6. Merge nearby FOSCs (within 50m)
7. Assign unique FOSC IDs

IMPORTANT: FOSCs are placed at:
- ALL cable intersections (junctions) - T-cross, Y, 4+ way
- Long cable runs (every 2km)

Note: Phase 3 will check if any FOSCs on straight segments can be replaced by terminals.
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import defaultdict
from utils.spatial_utils import euclidean_distance
from utils.geojson_utils import create_feature, create_feature_collection
from utils.cable_grouping import group_cables_by_topology
from utils.topology_junctions import detect_junctions_topology

def find_cable_junctions(
    cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0,
    max_junctions: int = 5000  # Limit junctions for performance
) -> List[Dict[str, Any]]:
    """
    Find junctions where cables meet at a point (like road intersections).
    
    A junction is a point where one or more cables start/end, and multiple cables
    share that same point. This is like a road intersection where multiple roads meet.
    
    Based on actual design analysis:
    - 3+ cables meeting: 100% get FOSCs (always place)
    - 2 cables meeting: ~41% get FOSCs (need to determine pattern)
    
    Args:
        cables: List of cable dictionaries with coordinates
        tolerance_m: Distance tolerance for considering endpoints as the same point
        max_junctions: Maximum number of junctions to find (performance limit)
        
    Returns:
        List of junction dictionaries with position and cable count
    """
    import time
    start_time = time.time()
    
    # Build endpoint map: rounded position -> list of cable indices meeting there
    endpoint_map = defaultdict(set)  # (rounded_x, rounded_y) -> set of cable indices
    grid_size = tolerance_m  # Use tolerance as grid size for grouping
    
    for i, cable in enumerate(cables):
        coords = cable["coordinates"]
        if not coords or len(coords) < 2:
            continue
        
        # Get start and end points (these are where cables can meet)
        start_point = coords[0]
        end_point = coords[-1]
        
        # Round to grid to group nearby points
        start_rounded = (
            round(start_point[0] / grid_size) * grid_size,
            round(start_point[1] / grid_size) * grid_size
        )
        end_rounded = (
            round(end_point[0] / grid_size) * grid_size,
            round(end_point[1] / grid_size) * grid_size
        )
        
        # Add cable to both endpoints
        endpoint_map[start_rounded].add(i)
        endpoint_map[end_rounded].add(i)
    
    print(f"      Built endpoint map ({time.time() - start_time:.1f}s)")
    
    # Find junctions: points where 2+ cables meet
    junctions = []
    for pos, cable_indices in endpoint_map.items():
        if len(junctions) >= max_junctions:
            break
        
        unique_cables = list(cable_indices)
        if len(unique_cables) >= 2:
            junctions.append({
                "position": pos,
                "cable_indices": unique_cables,
                "cable_count": len(unique_cables),
                "trigger": "junction"
            })
    
    elapsed = time.time() - start_time
    print(f"      Found {len(junctions)} junction points ({elapsed:.1f}s)")
    if len(junctions) >= max_junctions:
        print(f"      ⚠️  Junction limit reached ({max_junctions}), some junctions may be missing")
    
    return junctions

def find_long_segments(
    cables: List[Dict[str, Any]],
    spacing_m: float = 2000.0
) -> List[Dict[str, Any]]:
    """
    Find long cable segments that require FOSC placement.
    Places FOSCs every 2km along cables that are longer than 2km.
    
    Args:
        cables: List of cable dictionaries with coordinates
        spacing_m: Spacing between FOSCs along long cables (meters, default 2000m = 2km)
        
    Returns:
        List of long segment dictionaries with position and length
    """
    long_segments = []
    
    for i, cable in enumerate(cables):
        coords = cable["coordinates"]
        if len(coords) < 2:
            continue
        
        # Calculate total cable length
        total_length = 0.0
        segment_lengths = []
        for j in range(len(coords) - 1):
            seg_length = euclidean_distance(
                coords[j][0], coords[j][1],
                coords[j+1][0], coords[j+1][1]
            )
            segment_lengths.append(seg_length)
            total_length += seg_length
        
        # If cable is longer than spacing, place FOSCs every spacing_m
        if total_length >= spacing_m:
            # Place FOSCs at regular intervals along the cable
            current_distance = 0.0
            next_fosc_distance = spacing_m  # First FOSC at 2km
            
            for j in range(len(coords) - 1):
                seg_start = coords[j]
                seg_end = coords[j+1]
                seg_length = segment_lengths[j]
                seg_end_distance = current_distance + seg_length
                
                # Place FOSCs in this segment if needed
                while next_fosc_distance <= seg_end_distance and next_fosc_distance < total_length:
                    # Calculate position along this segment
                    offset_in_segment = next_fosc_distance - current_distance
                    t = offset_in_segment / seg_length if seg_length > 0 else 0
                    
                    fosc_pos = (
                        seg_start[0] + t * (seg_end[0] - seg_start[0]),
                        seg_start[1] + t * (seg_end[1] - seg_start[1])
                    )
                    
                    long_segments.append({
                        "position": fosc_pos,
                        "cable_index": i,
                        "distance_from_start": next_fosc_distance,
                        "trigger": "long_segment"
                    })
                    
                    next_fosc_distance += spacing_m  # Next FOSC 2km further
                
                current_distance = seg_end_distance
    
    return long_segments

def merge_nearby_foscs(
    foscs: List[Dict[str, Any]],
    merge_distance_m: float = 50.0
) -> List[Dict[str, Any]]:
    """
    Merge FOSCs that are very close to each other.
    
    Args:
        foscs: List of FOSC dictionaries with position
        merge_distance_m: Distance threshold for merging (meters)
        
    Returns:
        Merged list of FOSCs
    """
    if not foscs:
        return []
    
    merged = []
    used = set()
    
    for i, fosc1 in enumerate(foscs):
        if i in used:
            continue
        
        pos1 = fosc1["position"]
        nearby_foscs = [fosc1]
        used.add(i)
        
        # Find all nearby FOSCs
        for j, fosc2 in enumerate(foscs[i+1:], start=i+1):
            if j in used:
                continue
            
            pos2 = fosc2["position"]
            distance = euclidean_distance(
                pos1[0], pos1[1],
                pos2[0], pos2[1]
            )
            
            if distance <= merge_distance_m:
                nearby_foscs.append(fosc2)
                used.add(j)
        
        # Merge nearby FOSCs
        if len(nearby_foscs) == 1:
            merged.append(fosc1)
        else:
            # Calculate centroid of nearby FOSCs
            avg_x = sum(f["position"][0] for f in nearby_foscs) / len(nearby_foscs)
            avg_y = sum(f["position"][1] for f in nearby_foscs) / len(nearby_foscs)
            
            # Combine triggers
            all_triggers = []
            for f in nearby_foscs:
                trigger = f.get("trigger", "unknown")
                if trigger not in all_triggers:
                    all_triggers.append(trigger)
            
            merged.append({
                "position": (avg_x, avg_y),
                "triggers": all_triggers,
                "merged_count": len(nearby_foscs),
                "trigger": "+".join(all_triggers)
            })
    
    return merged

# REMOVED: find_foscs_for_terminals()
# FOSCs should ONLY be placed at:
# 1. Cable intersections (junctions)
# 2. Long cable runs (every 2km)
# Terminals should connect to existing FOSCs, not create new ones.

def place_foscs_initial(
    fiber_cable_geojson: Dict[str, Any],
    terminals: List[Dict[str, Any]] = None,
    config: Dict[str, Any] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Place FOSCs using topology-based approach:
    1. Group cable segments into logical cables (topology-based)
    2. Detect junctions between logical cables (endpoint + mid-segment)
    3. Place FOSCs at ALL junctions (T-cross, Y, 4+ way)
    4. Place FOSCs every 2km along long cable runs
    
    Args:
        fiber_cable_geojson: Input fiber cable GeoJSON
        terminals: List of terminal dictionaries (ignored - kept for API compatibility)
        config: Design configuration
        
    Returns:
        (foscs_list, summary_stats)
    """
    if config is None:
        config = {}
    
    print("  Placing FOSCs (Topology-Based: All Junctions + 2km Spacing)...")
    
    # Get configuration
    fosc_config = config.get("placement", {}).get("fosc", {})
    spacing_m = fosc_config.get("spacing_m", 2000.0)  # Default: 2km spacing
    junction_tolerance_m = 10.0  # 10m tolerance for junctions
    
    # Step 1: Group cable segments into logical cables (topology-based)
    print(f"    Grouping cable segments into logical cables...")
    logical_cables, grouping_stats = group_cables_by_topology(
        fiber_cable_geojson,
        tolerance_m=junction_tolerance_m
    )
    print(f"    Created {len(logical_cables)} logical cables from {grouping_stats['total_segments']} segments")
    
    # Step 2: Detect junctions between logical cables
    print(f"    Detecting junctions (tolerance: {junction_tolerance_m}m)...")
    junctions = detect_junctions_topology(
        logical_cables,
        tolerance_m=junction_tolerance_m,
        detect_mid_segment=True
    )
    
    # Categorize junctions
    junctions_tcross = [j for j in junctions if j["junction_type"] == "T-cross"]
    junctions_y = [j for j in junctions if j["junction_type"] == "Y"]
    junctions_4plus = [j for j in junctions if j["junction_type"].endswith("+-way")]
    
    print(f"    Junction breakdown:")
    print(f"      T-cross (2 cables): {len(junctions_tcross)}")
    print(f"      Y (3 cables): {len(junctions_y)}")
    print(f"      4+ way: {len(junctions_4plus)}")
    
    # Step 3: Place FOSCs at ALL junctions
    initial_foscs = []
    
    for junction in junctions:
        initial_foscs.append({
            "position": junction["position"],
            "trigger": "junction",
            "junction_type": junction["junction_type"],
            "cable_count": junction["cable_count"],
            "cable_indices": junction["cable_indices"],
            "detection_method": junction.get("detection_method", "topology")
        })
    
    print(f"    Placed FOSCs at {len(junctions)} junctions (ALL junctions)")
    
    # Step 4: Place FOSCs every 2km along long logical cables
    print(f"    Finding long cable runs (placing FOSCs every {spacing_m/1000:.1f}km)...")
    long_segment_foscs = []
    
    for i, logical_cable in enumerate(logical_cables):
        coords = logical_cable.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        # Calculate total length
        total_length = 0.0
        segment_lengths = []
        for j in range(len(coords) - 1):
            seg_length = euclidean_distance(
                coords[j][0], coords[j][1],
                coords[j+1][0], coords[j+1][1]
            )
            segment_lengths.append(seg_length)
            total_length += seg_length
        
        # If cable is longer than spacing, place FOSCs every spacing_m
        if total_length >= spacing_m:
            current_distance = 0.0
            next_fosc_distance = spacing_m  # First FOSC at 2km
            
            for j in range(len(coords) - 1):
                seg_start = coords[j]
                seg_end = coords[j+1]
                seg_length = segment_lengths[j]
                seg_end_distance = current_distance + seg_length
                
                # Place FOSCs in this segment if needed
                while next_fosc_distance <= seg_end_distance and next_fosc_distance < total_length:
                    # Calculate position along this segment
                    offset_in_segment = next_fosc_distance - current_distance
                    t = offset_in_segment / seg_length if seg_length > 0 else 0
                    
                    fosc_pos = (
                        seg_start[0] + t * (seg_end[0] - seg_start[0]),
                        seg_start[1] + t * (seg_end[1] - seg_start[1])
                    )
                    
                    long_segment_foscs.append({
                        "position": fosc_pos,
                        "trigger": "long_segment",
                        "logical_cable_index": i,
                        "distance_from_start": next_fosc_distance
                    })
                    
                    next_fosc_distance += spacing_m
                
                current_distance = seg_end_distance
    
    print(f"    Found {len(long_segment_foscs)} FOSC positions for long cable runs")
    
    # Add long segment FOSCs
    initial_foscs.extend(long_segment_foscs)
    
    # Step 5: Merge nearby FOSCs
    print(f"    Merging nearby FOSCs (within 50m)...")
    merged_foscs = merge_nearby_foscs(initial_foscs, merge_distance_m=50.0)
    print(f"    After merging: {len(merged_foscs)} FOSCs")
    
    # Step 6: Assign FOSC IDs
    foscs = []
    for i, fosc in enumerate(merged_foscs, 1):
        fosc_id = f"F{i:07d}"  # Pattern: F0000001, F0000002, etc.
        fosc["fosc_id"] = fosc_id
        foscs.append(fosc)
    
    # Generate summary
    trigger_counts = defaultdict(int)
    junction_type_counts = defaultdict(int)
    for fosc in foscs:
        trigger = fosc.get("trigger", "unknown")
        trigger_counts[trigger] += 1
        if "junction_type" in fosc:
            junction_type_counts[fosc["junction_type"]] += 1
    
    summary = {
        "total_foscs": len(foscs),
        "logical_cables": len(logical_cables),
        "total_segments": grouping_stats["total_segments"],
        "junctions_total": len(junctions),
        "junctions_tcross": len(junctions_tcross),
        "junctions_y": len(junctions_y),
        "junctions_4plus": len(junctions_4plus),
        "long_segment_foscs": len(long_segment_foscs),
        "merged": len(initial_foscs) - len(merged_foscs),
        "trigger_distribution": dict(trigger_counts),
        "junction_type_distribution": dict(junction_type_counts)
    }
    
    print(f"  ✓ Placed {len(foscs)} FOSCs")
    print(f"    T-cross junctions: {len(junctions_tcross)}, Y junctions: {len(junctions_y)}, 4+ way: {len(junctions_4plus)}")
    print(f"    Long runs (every {spacing_m/1000:.1f}km): {len(long_segment_foscs)}")
    print(f"    Merged: {summary['merged']} nearby FOSCs")
    
    return (foscs, summary)

def generate_fosc_geojson(foscs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate GeoJSON for FOSCs.
    """
    features = []
    
    for fosc in foscs:
        position = fosc["position"]
        
        properties = {
            "ID": fosc["fosc_id"],
            "trigger": fosc.get("trigger", "unknown"),
            "placement_method": "geometry_based"
        }
        
        if "cable_count" in fosc:
            properties["cable_count"] = fosc["cable_count"]
        if "merged_count" in fosc:
            properties["merged_count"] = fosc["merged_count"]
        if "triggers" in fosc:
            properties["triggers"] = ", ".join(fosc["triggers"])
        
        geometry = {
            "type": "Point",
            "coordinates": [position[0], position[1]]
        }
        
        feature = create_feature(geometry, properties)
        features.append(feature)
    
    return create_feature_collection(features, crs="EPSG:32617")


