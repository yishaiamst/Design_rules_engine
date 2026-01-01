#!/usr/bin/env python3
"""
phase2_place_foscs_revised.py
-------------------------------------------------------------------------------
Phase 2: Place FOSCs (Revised - Topology-Based)

Strategy:
1. Group cable segments into logical cables (topology-based)
2. Detect junctions between logical cables (endpoints + mid-segments)
3. Place FOSCs at ALL junctions (2+, 3+, 4+)
4. Place FOSCs every 2km along long cable runs
5. Merge nearby FOSCs (within 50m)
6. Assign unique FOSC IDs

REVISED APPROACH:
- Uses logical cable grouping (not one feature = one cable)
- Detects junctions between logical cables
- Places FOSC at ALL junctions (T-cross, Y, 4+ way)
- Also detects mid-segment intersections
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import defaultdict
from utils.spatial_utils import euclidean_distance
from utils.geojson_utils import create_feature, create_feature_collection
from utils.cable_grouping import group_cables_by_topology
from utils.junction_detection import find_all_junctions


def find_long_segments_on_logical_cables(
    logical_cables: List[Dict[str, Any]],
    spacing_m: float = 2000.0
) -> List[Dict[str, Any]]:
    """
    Find long segments on logical cables that require FOSC placement.
    Places FOSCs every 2km along logical cables.
    
    Args:
        logical_cables: List of logical cable dicts with 'coordinates'
        spacing_m: Spacing between FOSCs along long cables (meters, default 2000m = 2km)
        
    Returns:
        List of long segment dictionaries with position and length
    """
    long_segments = []
    
    for i, cable in enumerate(logical_cables):
        coords = cable.get("coordinates", [])
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
                        "logical_cable_index": i,
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
            
            # Combine triggers and junction types
            all_triggers = []
            all_junction_types = []
            for f in nearby_foscs:
                trigger = f.get("trigger", "unknown")
                if trigger not in all_triggers:
                    all_triggers.append(trigger)
                junction_type = f.get("junction_type")
                if junction_type and junction_type not in all_junction_types:
                    all_junction_types.append(junction_type)
            
            merged.append({
                "position": (avg_x, avg_y),
                "triggers": all_triggers,
                "merged_count": len(nearby_foscs),
                "trigger": "+".join(all_triggers),
                "junction_type": "/".join(all_junction_types) if all_junction_types else None
            })
    
    return merged


def place_foscs_initial(
    fiber_cable_geojson: Dict[str, Any],
    terminals: List[Dict[str, Any]] = None,
    config: Dict[str, Any] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Place FOSCs using topology-based approach:
    1. Group segments into logical cables
    2. Detect junctions between logical cables (endpoints + mid-segments)
    3. Place FOSCs at ALL junctions (2+, 3+, 4+)
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
    
    print("  Placing FOSCs (Topology-Based: Logical Cables + All Junctions)...")
    
    # Get configuration
    fosc_config = config.get("placement", {}).get("fosc", {})
    spacing_m = fosc_config.get("spacing_m", 2000.0)  # Default: 2km spacing
    junction_tolerance_m = 10.0  # 10m tolerance for junctions
    
    # Step 1: Group segments into logical cables (topology-based)
    print(f"    Grouping cable segments into logical cables (tolerance: {junction_tolerance_m}m)...")
    logical_cables, grouping_stats = group_cables_by_topology(
        fiber_cable_geojson,
        tolerance_m=junction_tolerance_m
    )
    print(f"    Created {len(logical_cables)} logical cables from {grouping_stats['total_segments']} segments")
    
    # Step 2: Find all junctions between logical cables
    print(f"    Finding junctions between logical cables (endpoints + mid-segments)...")
    junctions = find_all_junctions(logical_cables, tolerance_m=junction_tolerance_m)
    
    # Categorize junctions
    junctions_2 = [j for j in junctions if j["cable_count"] == 2]
    junctions_3 = [j for j in junctions if j["cable_count"] == 3]
    junctions_4plus = [j for j in junctions if j["cable_count"] >= 4]
    
    print(f"    Found {len(junctions)} total junctions:")
    print(f"      T-cross (2 cables): {len(junctions_2)}")
    print(f"      Y (3 cables): {len(junctions_3)}")
    print(f"      {len(junctions_4plus)}-way (4+ cables): {len(junctions_4plus)}")
    
    # Step 3: Place FOSCs at ALL junctions
    initial_foscs = []
    
    for junction in junctions:
        initial_foscs.append({
            "position": junction["position"],
            "trigger": junction["trigger"],
            "junction_type": junction.get("junction_type", "unknown"),
            "cable_count": junction["cable_count"],
            "logical_cable_indices": junction["logical_cable_indices"]
        })
    
    print(f"    Placed FOSC at ALL {len(junctions)} junctions")
    
    # Step 4: Place FOSCs every 2km along long cable runs
    print(f"    Finding long cable runs (placing FOSCs every {spacing_m/1000:.1f}km)...")
    long_segments = find_long_segments_on_logical_cables(logical_cables, spacing_m=spacing_m)
    print(f"    Found {len(long_segments)} FOSC positions for long cable runs")
    
    for segment in long_segments:
        initial_foscs.append({
            "position": segment["position"],
            "trigger": segment["trigger"],
            "logical_cable_index": segment["logical_cable_index"],
            "distance_from_start": segment.get("distance_from_start", 0)
        })
    
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
        junction_type = fosc.get("junction_type")
        if junction_type:
            junction_type_counts[junction_type] += 1
    
    summary = {
        "total_foscs": len(foscs),
        "logical_cables": len(logical_cables),
        "total_segments": grouping_stats["total_segments"],
        "junctions_total": len(junctions),
        "junctions_2": len(junctions_2),
        "junctions_3": len(junctions_3),
        "junctions_4plus": len(junctions_4plus),
        "long_segment_foscs": len(long_segments),
        "merged": len(initial_foscs) - len(merged_foscs),
        "trigger_distribution": dict(trigger_counts),
        "junction_type_distribution": dict(junction_type_counts)
    }
    
    print(f"  ✓ Placed {len(foscs)} FOSCs")
    print(f"    Logical cables: {len(logical_cables)}")
    print(f"    Junctions: {len(junctions)} (T-cross: {len(junctions_2)}, Y: {len(junctions_3)}, 4+: {len(junctions_4plus)})")
    print(f"    Long runs (every {spacing_m/1000:.1f}km): {len(long_segments)}")
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
            "placement_method": "topology_based"
        }
        
        if "junction_type" in fosc:
            properties["junction_type"] = fosc["junction_type"]
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
    
    return create_feature_collection(features)

