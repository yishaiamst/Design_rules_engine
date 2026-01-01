#!/usr/bin/env python3
"""
Junction Detection Utilities
Detect junctions between logical cables (topology-based)
Includes both endpoint and mid-segment intersections
"""

from typing import Dict, List, Any, Tuple, Set
from collections import defaultdict
from utils.spatial_utils import euclidean_distance


def find_line_segment_intersection(
    line1_start: Tuple[float, float],
    line1_end: Tuple[float, float],
    line2_start: Tuple[float, float],
    line2_end: Tuple[float, float],
    tolerance_m: float = 10.0
) -> Tuple[bool, Tuple[float, float]]:
    """
    Find intersection point of two line segments.
    Returns (intersects, intersection_point)
    """
    x1, y1 = line1_start
    x2, y2 = line1_end
    x3, y3 = line2_start
    x4, y4 = line2_end
    
    # Calculate line segment vectors
    dx1 = x2 - x1
    dy1 = y2 - y1
    dx2 = x4 - x3
    dy2 = y4 - y3
    
    # Check if lines are parallel
    denominator = dx1 * dy2 - dy1 * dx2
    if abs(denominator) < 1e-10:
        # Lines are parallel - check if they overlap
        return (False, (0, 0))
    
    # Calculate intersection parameters
    t1 = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / denominator
    t2 = ((x3 - x1) * dy1 - (y3 - y1) * dx1) / denominator
    
    # Check if intersection is within both line segments (with tolerance)
    if -tolerance_m <= t1 <= 1 + tolerance_m and -tolerance_m <= t2 <= 1 + tolerance_m:
        # Intersection point
        ix = x1 + t1 * dx1
        iy = y1 + t1 * dy1
        return (True, (ix, iy))
    
    return (False, (0, 0))


def find_endpoint_junctions(
    logical_cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Find junctions where logical cables meet at endpoints.
    
    Args:
        logical_cables: List of logical cable dicts with 'start', 'end', 'coordinates'
        tolerance_m: Distance tolerance for endpoint matching
        
    Returns:
        List of junction dicts
    """
    grid_size = tolerance_m
    endpoint_map = defaultdict(list)  # rounded_pos -> list of (cable_idx, endpoint_type)
    
    # Build endpoint map
    for i, cable in enumerate(logical_cables):
        if not cable.get("start") or not cable.get("end"):
            continue
        
        start_rounded = (
            round(cable["start"][0] / grid_size) * grid_size,
            round(cable["start"][1] / grid_size) * grid_size
        )
        end_rounded = (
            round(cable["end"][0] / grid_size) * grid_size,
            round(cable["end"][1] / grid_size) * grid_size
        )
        
        endpoint_map[start_rounded].append((i, 'start'))
        endpoint_map[end_rounded].append((i, 'end'))
    
    # Find junctions
    junctions = []
    junction_positions = set()
    
    for pos, cable_endpoints in endpoint_map.items():
        unique_cables = set(cable_idx for cable_idx, _ in cable_endpoints)
        
        if len(unique_cables) >= 2:
            # This is a junction
            if pos in junction_positions:
                continue
            
            junction_positions.add(pos)
            
            # Calculate actual position (average of endpoints)
            positions = []
            for cable_idx, endpoint_type in cable_endpoints:
                cable = logical_cables[cable_idx]
                if endpoint_type == 'start':
                    positions.append(cable["start"])
                else:
                    positions.append(cable["end"])
            
            avg_x = sum(p[0] for p in positions) / len(positions)
            avg_y = sum(p[1] for p in positions) / len(positions)
            
            junctions.append({
                "position": (avg_x, avg_y),
                "logical_cable_indices": list(unique_cables),
                "cable_count": len(unique_cables),
                "trigger": "endpoint_junction",
                "junction_type": get_junction_type(len(unique_cables))
            })
    
    return junctions


def find_mid_segment_junctions(
    logical_cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Find junctions where logical cables cross in the middle (not at endpoints).
    
    Args:
        logical_cables: List of logical cable dicts with 'coordinates'
        tolerance_m: Distance tolerance for intersection detection
        
    Returns:
        List of junction dicts
    """
    junctions = []
    junction_positions = set()
    grid_size = tolerance_m
    
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
            
            # Check all segments in cable1 against all segments in cable2
            for k in range(len(coords1) - 1):
                seg1_start = coords1[k]
                seg1_end = coords1[k + 1]
                
                for l in range(len(coords2) - 1):
                    seg2_start = coords2[l]
                    seg2_end = coords2[l + 1]
                    
                    # Check if segments intersect
                    intersects, intersection_point = find_line_segment_intersection(
                        seg1_start, seg1_end,
                        seg2_start, seg2_end,
                        tolerance_m
                    )
                    
                    if intersects:
                        # Round to grid to avoid duplicates
                        rounded_pos = (
                            round(intersection_point[0] / grid_size) * grid_size,
                            round(intersection_point[1] / grid_size) * grid_size
                        )
                        
                        if rounded_pos not in junction_positions:
                            junction_positions.add(rounded_pos)
                            
                            # Check if other cables also intersect at this point
                            intersecting_cables = {i, j}
                            
                            # Check other cables
                            for m in range(len(logical_cables)):
                                if m == i or m == j:
                                    continue
                                
                                cable3 = logical_cables[m]
                                coords3 = cable3.get("coordinates", [])
                                if len(coords3) < 2:
                                    continue
                                
                                # Check if cable3 passes through intersection point
                                for n in range(len(coords3) - 1):
                                    seg3_start = coords3[n]
                                    seg3_end = coords3[n + 1]
                                    
                                    from utils.spatial_utils import point_to_line_distance
                                    dist = point_to_line_distance(
                                        intersection_point,
                                        seg3_start,
                                        seg3_end
                                    )
                                    
                                    if dist <= tolerance_m:
                                        intersecting_cables.add(m)
                                        break
                            
                            if len(intersecting_cables) >= 2:
                                junctions.append({
                                    "position": intersection_point,
                                    "logical_cable_indices": list(intersecting_cables),
                                    "cable_count": len(intersecting_cables),
                                    "trigger": "mid_segment_junction",
                                    "junction_type": get_junction_type(len(intersecting_cables))
                                })
    
    return junctions


def get_junction_type(cable_count: int) -> str:
    """Get junction type name based on cable count."""
    if cable_count == 2:
        return "T-cross"
    elif cable_count == 3:
        return "Y"
    elif cable_count >= 4:
        return f"{cable_count}-way"
    else:
        return "unknown"


def find_all_junctions(
    logical_cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Find all junctions between logical cables (endpoints + mid-segments).
    
    Args:
        logical_cables: List of logical cable dicts
        tolerance_m: Distance tolerance
        
    Returns:
        List of junction dicts (merged and deduplicated)
    """
    # Find endpoint junctions
    endpoint_junctions = find_endpoint_junctions(logical_cables, tolerance_m)
    
    # Find mid-segment junctions
    mid_segment_junctions = find_mid_segment_junctions(logical_cables, tolerance_m)
    
    # Merge and deduplicate
    all_junctions = []
    junction_positions = set()
    grid_size = tolerance_m
    
    for junction in endpoint_junctions + mid_segment_junctions:
        pos = junction["position"]
        rounded_pos = (
            round(pos[0] / grid_size) * grid_size,
            round(pos[1] / grid_size) * grid_size
        )
        
        if rounded_pos not in junction_positions:
            junction_positions.add(rounded_pos)
            all_junctions.append(junction)
        else:
            # Merge with existing junction at this position
            for existing in all_junctions:
                existing_rounded = (
                    round(existing["position"][0] / grid_size) * grid_size,
                    round(existing["position"][1] / grid_size) * grid_size
                )
                
                if existing_rounded == rounded_pos:
                    # Merge cable indices
                    combined_cables = set(existing["logical_cable_indices"])
                    combined_cables.update(junction["logical_cable_indices"])
                    existing["logical_cable_indices"] = list(combined_cables)
                    existing["cable_count"] = len(combined_cables)
                    existing["junction_type"] = get_junction_type(len(combined_cables))
                    # Keep both triggers
                    if existing["trigger"] != junction["trigger"]:
                        existing["trigger"] = "combined"
                    break
    
    return all_junctions

