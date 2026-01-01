#!/usr/bin/env python3
"""
Topology-based junction detection for cable networks.
Detects junctions between logical cables, including mid-segment intersections.
"""

from typing import Dict, List, Any, Tuple, Set
from collections import defaultdict
from utils.spatial_utils import euclidean_distance
from utils.intersection_utils import find_line_intersection


def detect_junctions_topology(
    logical_cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0,
    detect_mid_segment: bool = True
) -> List[Dict[str, Any]]:
    """
    Detect junctions between logical cables using topology.
    
    Detects:
    1. Endpoint intersections (cables meeting at endpoints)
    2. Mid-segment intersections (cables crossing in the middle)
    
    Categorizes as:
    - T-cross: 2 cables
    - Y: 3 cables
    - 4+ way: 4 or more cables
    
    Args:
        logical_cables: List of logical cable dicts with 'coordinates', 'start', 'end'
        tolerance_m: Distance tolerance for considering points as the same
        detect_mid_segment: Whether to detect mid-segment intersections
        
    Returns:
        List of junction dicts with position, cable_count, junction_type
    """
    import time
    start_time = time.time()
    
    junctions = []
    junction_positions = set()
    grid_size = tolerance_m
    
    # Step 1: Detect endpoint intersections
    print(f"      Detecting endpoint intersections...")
    endpoint_junctions = detect_endpoint_junctions(logical_cables, tolerance_m)
    print(f"      Found {len(endpoint_junctions)} endpoint junctions")
    
    # Step 2: Detect mid-segment intersections (if enabled)
    mid_segment_junctions = []
    if detect_mid_segment:
        print(f"      Detecting mid-segment intersections...")
        mid_segment_junctions = detect_mid_segment_intersections(logical_cables, tolerance_m)
        print(f"      Found {len(mid_segment_junctions)} mid-segment intersections")
    
    # Step 3: Combine and deduplicate
    all_junctions = endpoint_junctions + mid_segment_junctions
    
    # Group by position (within tolerance)
    junction_groups = defaultdict(list)
    for junction in all_junctions:
        pos = junction["position"]
        rounded_pos = (
            round(pos[0] / grid_size) * grid_size,
            round(pos[1] / grid_size) * grid_size
        )
        junction_groups[rounded_pos].append(junction)
    
    # Merge junctions at same location
    for rounded_pos, junction_list in junction_groups.items():
        if rounded_pos in junction_positions:
            continue
        
        # Combine all cables from junctions at this location
        all_cable_indices = set()
        all_positions = []
        
        for junction in junction_list:
            all_cable_indices.update(junction.get("cable_indices", []))
            all_positions.append(junction["position"])
        
        if len(all_cable_indices) >= 2:
            junction_positions.add(rounded_pos)
            
            # Calculate average position
            avg_x = sum(p[0] for p in all_positions) / len(all_positions)
            avg_y = sum(p[1] for p in all_positions) / len(all_positions)
            
            # Categorize junction type
            cable_count = len(all_cable_indices)
            if cable_count == 2:
                junction_type = "T-cross"
            elif cable_count == 3:
                junction_type = "Y"
            else:
                junction_type = f"{cable_count}+-way"
            
            junctions.append({
                "position": (avg_x, avg_y),
                "cable_indices": list(all_cable_indices),
                "cable_count": cable_count,
                "junction_type": junction_type,
                "trigger": "junction",
                "detection_method": "topology"
            })
    
    elapsed = time.time() - start_time
    print(f"      Total junctions: {len(junctions)} ({elapsed:.1f}s)")
    
    # Count by type
    type_counts = defaultdict(int)
    for j in junctions:
        type_counts[j["junction_type"]] += 1
    
    print(f"      Junction breakdown:")
    for jtype, count in sorted(type_counts.items()):
        print(f"        {jtype}: {count}")
    
    return junctions


def detect_endpoint_junctions(
    logical_cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Detect junctions where logical cables meet at endpoints.
    """
    grid_size = tolerance_m
    endpoint_map = defaultdict(set)
    
    for i, cable in enumerate(logical_cables):
        start = cable.get("start")
        end = cable.get("end")
        
        if not start or not end:
            continue
        
        start_rounded = (
            round(start[0] / grid_size) * grid_size,
            round(start[1] / grid_size) * grid_size
        )
        end_rounded = (
            round(end[0] / grid_size) * grid_size,
            round(end[1] / grid_size) * grid_size
        )
        
        endpoint_map[start_rounded].add(i)
        endpoint_map[end_rounded].add(i)
    
    junctions = []
    for pos, cable_indices in endpoint_map.items():
        if len(cable_indices) >= 2:
            # Get actual positions
            positions = []
            for cable_idx in cable_indices:
                cable = logical_cables[cable_idx]
                if pos == (round(cable["start"][0] / grid_size) * grid_size,
                          round(cable["start"][1] / grid_size) * grid_size):
                    positions.append(cable["start"])
                else:
                    positions.append(cable["end"])
            
            avg_x = sum(p[0] for p in positions) / len(positions)
            avg_y = sum(p[1] for p in positions) / len(positions)
            
            cable_count = len(cable_indices)
            if cable_count == 2:
                junction_type = "T-cross"
            elif cable_count == 3:
                junction_type = "Y"
            else:
                junction_type = f"{cable_count}+-way"
            
            junctions.append({
                "position": (avg_x, avg_y),
                "cable_indices": list(cable_indices),
                "cable_count": cable_count,
                "junction_type": junction_type,
                "detection_method": "endpoint"
            })
    
    return junctions


def detect_mid_segment_intersections(
    logical_cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Detect intersections where cables cross in the middle (not at endpoints).
    """
    intersections = []
    
    # Check all pairs of logical cables
    for i in range(len(logical_cables)):
        cable1 = logical_cables[i]
        coords1 = cable1.get("coordinates", [])
        if len(coords1) < 2:
            continue
        
        for j in range(i + 1, len(logical_cables)):
            cable2 = logical_cables[j]
            coords2 = cable2.get("coordinates", [])
            if len(coords2) < 2:
                continue
            
            # Check each segment of cable1 against each segment of cable2
            for k in range(len(coords1) - 1):
                seg1_start = coords1[k]
                seg1_end = coords1[k + 1]
                
                for m in range(len(coords2) - 1):
                    seg2_start = coords2[m]
                    seg2_end = coords2[m + 1]
                    
                    # Check if segments intersect
                    intersects, intersection_point = find_line_intersection(
                        seg1_start, seg1_end,
                        seg2_start, seg2_end,
                        tolerance=tolerance_m
                    )
                    
                    if intersects:
                        # Check if intersection is not at endpoints (mid-segment)
                        dist_to_seg1_start = euclidean_distance(
                            intersection_point[0], intersection_point[1],
                            seg1_start[0], seg1_start[1]
                        )
                        dist_to_seg1_end = euclidean_distance(
                            intersection_point[0], intersection_point[1],
                            seg1_end[0], seg1_end[1]
                        )
                        dist_to_seg2_start = euclidean_distance(
                            intersection_point[0], intersection_point[1],
                            seg2_start[0], seg2_start[1]
                        )
                        dist_to_seg2_end = euclidean_distance(
                            intersection_point[0], intersection_point[1],
                            seg2_end[0], seg2_end[1]
                        )
                        
                        # If intersection is far from all endpoints (>tolerance), it's mid-segment
                        min_dist_to_endpoint = min(
                            dist_to_seg1_start, dist_to_seg1_end,
                            dist_to_seg2_start, dist_to_seg2_end
                        )
                        
                        if min_dist_to_endpoint > tolerance_m:
                            intersections.append({
                                "position": intersection_point,
                                "cable_indices": [i, j],
                                "cable_count": 2,
                                "junction_type": "T-cross",
                                "detection_method": "mid-segment"
                            })
    
    return intersections

