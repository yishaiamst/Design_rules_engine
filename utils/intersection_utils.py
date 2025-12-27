#!/usr/bin/env python3
"""
Intersection utilities for cable junction detection.
"""

from typing import Dict, List, Any, Tuple
from collections import defaultdict


def find_cable_junctions_geometric(
    cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0,
    max_junctions: int = 5000
) -> List[Dict[str, Any]]:
    """
    Find junctions where cables meet at endpoints (geometric detection).
    
    This is the same logic used in Phase 3 which matches actual design 99.9%.
    Uses endpoint-based detection: cables meet where their start/end points are within tolerance.
    
    Args:
        cables: List of cable dictionaries with coordinates
        tolerance_m: Distance tolerance for considering endpoints as the same point
        max_junctions: Maximum number of junctions to find (performance limit)
        
    Returns:
        List of junction dictionaries with position, cable_count, and cable_indices
    """
    # Build endpoint map: rounded position -> set of cable indices meeting there
    endpoint_map = defaultdict(set)  # (rounded_x, rounded_y) -> set of cable indices
    grid_size = tolerance_m  # Use tolerance as grid size for grouping
    
    for i, cable in enumerate(cables):
        coords = cable.get("coordinates", [])
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
    
    # Find junctions: points where 2+ cables meet
    junctions = []
    for pos, cable_indices in endpoint_map.items():
        if len(junctions) >= max_junctions:
            break
        
        unique_cables = list(cable_indices)
        if len(unique_cables) >= 2:
            # Determine junction type
            cable_count = len(unique_cables)
            if cable_count == 2:
                junction_type = "T-cross"
            elif cable_count == 3:
                junction_type = "Y"
            else:
                junction_type = "4+ way"
            
            junctions.append({
                "position": pos,
                "cable_indices": unique_cables,
                "cable_count": cable_count,
                "junction_type": junction_type,
                "trigger": "junction"
            })
    
    return junctions
