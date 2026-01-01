#!/usr/bin/env python3
"""
phase0_community_pockets.py
-------------------------------------------------------------------------------
Phase 0: Create Community Pockets
Cluster ONTs into community pockets for OLT placement decisions.
-------------------------------------------------------------------------------
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Any, Tuple, Optional
from utils.geojson_utils import extract_points
from utils.spatial_utils import (
    euclidean_distance, 
    calculate_centroid, 
    calculate_diameter,
    simple_cluster,
    point_to_linestring_distance
)
from utils.config_loader import get_placement_config

def create_community_pockets(ont_geojson: Dict[str, Any],
                            fiber_cable_geojson: Dict[str, Any],
                            config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create community pockets by clustering ONTs.
    
    Args:
        ont_geojson: ONT GeoJSON data
        fiber_cable_geojson: Fiber cable GeoJSON data
        config: Configuration dictionary
        
    Returns:
        List of community pockets with metadata
    """
    print("  Creating community pockets...")
    
    # Get placement configuration
    placement_config = get_placement_config(config)
    olt_config = placement_config.get("olt", {})
    
    # Clustering parameters
    initial_radius_km = 2.0  # 2km initial clustering radius
    merge_distance_km = olt_config.get("pocket_merge_distance_km", 15.0)
    max_diameter_km = olt_config.get("pocket_max_diameter_km", 15.0)
    diameter_enforcement = olt_config.get("pocket_diameter_enforcement", "strict")
    
    # Extract ONT points
    ont_points = extract_points(ont_geojson)
    print(f"    Extracted {len(ont_points)} ONT points")
    
    if not ont_points:
        return []
    
    # Extract fiber cable linestrings
    from utils.geojson_utils import extract_linestrings
    cable_linestrings = extract_linestrings(fiber_cable_geojson)
    print(f"    Found {len(cable_linestrings)} fiber cable segments")
    
    # Step 1: Initial clustering (2km radius)
    print(f"    Clustering ONTs with {initial_radius_km}km radius...")
    initial_radius_m = initial_radius_km * 1000  # Convert to meters
    clusters = simple_cluster(ont_points, initial_radius_m)
    print(f"    Created {len(clusters)} initial clusters")
    
    # Step 2: Create initial pockets
    initial_pockets = []
    for i, cluster_indices in enumerate(clusters):
        cluster_points = [ont_points[idx] for idx in cluster_indices]
        cluster_coords = [(p[0], p[1]) for p in cluster_points]
        
        # Calculate centroid
        centroid = calculate_centroid(cluster_coords)
        
        # Calculate diameter
        diameter = calculate_diameter(cluster_coords)
        diameter_km = diameter / 1000  # Convert to km
        
        # Find nearest infrastructure cable
        nearest_cable, cable_distance = find_nearest_infrastructure_cable(
            centroid, cable_linestrings
        )
        
        # Get ONT IDs
        ont_ids = [p[2].get("ID") or p[2].get("id") for p in cluster_points]
        
        pocket = {
            "pocket_id": f"POCKET_{i+1:04d}",
            "ont_count": len(cluster_points),
            "ont_ids": ont_ids,
            "ont_points": cluster_points,
            "centroid": centroid,
            "diameter_km": diameter_km,
            "nearest_cable": nearest_cable,
            "distance_to_cable_m": cable_distance,
            "merged": False
        }
        
        initial_pockets.append(pocket)
    
    # Step 3: Merge pockets if <15km apart
    print(f"    Merging pockets within {merge_distance_km}km...")
    merged_pockets = merge_pockets(initial_pockets, merge_distance_km, max_diameter_km)
    print(f"    After merging: {len(merged_pockets)} pockets")
    
    # Step 4: Split oversized pockets (if enabled)
    if diameter_enforcement == "disabled":
        print(f"    Diameter validation: DISABLED (keeping all {len(merged_pockets)} pockets)")
        final_pockets = merged_pockets
    elif diameter_enforcement == "warning":
        print(f"    Validating pocket diameters (max {max_diameter_km}km) - WARNING MODE...")
        oversized = [p for p in merged_pockets if p.get("diameter_km", 0) > max_diameter_km]
        if oversized:
            print(f"    ⚠️  WARNING: {len(oversized)} pockets exceed {max_diameter_km}km diameter:")
            for p in oversized:
                print(f"      {p['pocket_id']}: {p.get('diameter_km', 0):.2f}km ({p['ont_count']} ONTs)")
        final_pockets = merged_pockets
    else:  # strict
        print(f"    Validating pocket diameters (max {max_diameter_km}km)...")
        final_pockets = split_oversized_pockets(merged_pockets, max_diameter_km, initial_radius_m)
        print(f"    Final pockets: {len(final_pockets)}")
    
    # Print summary
    print(f"    Pocket size distribution:")
    size_dist = {}
    for pocket in final_pockets:
        size_range = get_size_range(pocket["ont_count"])
        size_dist[size_range] = size_dist.get(size_range, 0) + 1
    
    for size_range, count in sorted(size_dist.items()):
        print(f"      {size_range}: {count} pockets")
    
    return final_pockets

def find_nearest_infrastructure_cable(centroid: Tuple[float, float],
                                     cable_linestrings: List[Tuple[List[Tuple[float, float]], Dict[str, Any]]]) -> Tuple[Optional[Dict[str, Any]], float]:
    """
    Find nearest infrastructure cable to centroid.
    
    Args:
        centroid: Centroid coordinates (x, y)
        cable_linestrings: List of cable linestrings with properties
        
    Returns:
        Tuple of (nearest_cable_properties, distance_in_meters)
    """
    if not cable_linestrings:
        return (None, float('inf'))
    
    min_distance = float('inf')
    nearest_cable = None
    
    for linestring_coords, props in cable_linestrings:
        distance, _ = point_to_linestring_distance(centroid, linestring_coords)
        
        if distance < min_distance:
            min_distance = distance
            nearest_cable = props
    
    return (nearest_cable, min_distance)

def merge_pockets(pockets: List[Dict[str, Any]], 
                 merge_distance_km: float,
                 max_diameter_km: float) -> List[Dict[str, Any]]:
    """
    Merge pockets that are within merge_distance_km of each other.
    
    Args:
        pockets: List of pocket dictionaries
        merge_distance_km: Distance threshold for merging
        max_diameter_km: Maximum allowed diameter after merging
        
    Returns:
        List of merged pockets
    """
    if not pockets:
        return []
    
    merge_distance_m = merge_distance_km * 1000
    
    # Create a copy to work with
    remaining_pockets = pockets.copy()
    merged_pockets = []
    
    while remaining_pockets:
        current_pocket = remaining_pockets.pop(0)
        merged_with = [current_pocket]
        
        # Find pockets to merge
        i = 0
        while i < len(remaining_pockets):
            other_pocket = remaining_pockets[i]
            
            # Calculate distance between centroids
            dist = euclidean_distance(
                current_pocket["centroid"][0], current_pocket["centroid"][1],
                other_pocket["centroid"][0], other_pocket["centroid"][1]
            )
            
            if dist <= merge_distance_m:
                # Merge this pocket
                merged_with.append(remaining_pockets.pop(i))
            else:
                i += 1
        
        # Create merged pocket
        if len(merged_with) > 1:
            merged_pocket = merge_pocket_list(merged_with, max_diameter_km)
            merged_pockets.append(merged_pocket)
        else:
            merged_pockets.append(current_pocket)
    
    return merged_pockets

def merge_pocket_list(pockets: List[Dict[str, Any]], 
                     max_diameter_km: float) -> Dict[str, Any]:
    """
    Merge a list of pockets into a single pocket.
    
    Args:
        pockets: List of pockets to merge
        max_diameter_km: Maximum allowed diameter
        
    Returns:
        Merged pocket dictionary
    """
    # Combine all ONT points
    all_ont_points = []
    all_ont_ids = []
    
    for pocket in pockets:
        all_ont_points.extend(pocket["ont_points"])
        all_ont_ids.extend(pocket["ont_ids"])
    
    # Calculate new centroid
    all_coords = [(p[0], p[1]) for p in all_ont_points]
    new_centroid = calculate_centroid(all_coords)
    
    # Calculate new diameter
    new_diameter = calculate_diameter(all_coords)
    new_diameter_km = new_diameter / 1000
    
    # Find nearest cable (use first pocket's for now, could improve)
    nearest_cable = pockets[0].get("nearest_cable")
    distance_to_cable = pockets[0].get("distance_to_cable_m", float('inf'))
    
    # Use smallest pocket ID as base
    base_pocket_id = min([p["pocket_id"] for p in pockets])
    
    merged_pocket = {
        "pocket_id": base_pocket_id + "_MERGED",
        "ont_count": len(all_ont_points),
        "ont_ids": all_ont_ids,
        "ont_points": all_ont_points,
        "centroid": new_centroid,
        "diameter_km": new_diameter_km,
        "nearest_cable": nearest_cable,
        "distance_to_cable_m": distance_to_cable,
        "merged": True,
        "merged_from": [p["pocket_id"] for p in pockets]
    }
    
    return merged_pocket

def split_oversized_pockets(pockets: List[Dict[str, Any]], 
                           max_diameter_km: float,
                           cluster_radius_m: float) -> List[Dict[str, Any]]:
    """
    Split pockets that exceed max_diameter_km.
    
    Args:
        pockets: List of pocket dictionaries
        max_diameter_km: Maximum allowed diameter
        cluster_radius_m: Clustering radius for splitting
        
    Returns:
        List of pockets (some may be split)
    """
    max_diameter_m = max_diameter_km * 1000
    final_pockets = []
    
    for pocket in pockets:
        if pocket["diameter_km"] <= max_diameter_km:
            # Pocket is within limits
            final_pockets.append(pocket)
        else:
            # Split oversized pocket
            print(f"      Splitting oversized pocket {pocket['pocket_id']} (diameter: {pocket['diameter_km']:.2f}km)")
            split_pockets = split_pocket(pocket, cluster_radius_m, max_diameter_km)
            final_pockets.extend(split_pockets)
            print(f"        Split into {len(split_pockets)} pockets")
    
    return final_pockets

def split_pocket(pocket: Dict[str, Any],
                cluster_radius_m: float,
                max_diameter_km: float) -> List[Dict[str, Any]]:
    """
    Split an oversized pocket into smaller pockets.
    
    Args:
        pocket: Pocket dictionary to split
        cluster_radius_m: Clustering radius
        max_diameter_km: Maximum diameter for split pockets
        
    Returns:
        List of split pockets
    """
    # Re-cluster the ONT points with smaller radius
    ont_points = pocket["ont_points"]
    clusters = simple_cluster(ont_points, cluster_radius_m)
    
    split_pockets = []
    base_id = pocket["pocket_id"]
    
    for i, cluster_indices in enumerate(clusters):
        cluster_points = [ont_points[idx] for idx in cluster_indices]
        cluster_coords = [(p[0], p[1]) for p in cluster_points]
        
        centroid = calculate_centroid(cluster_coords)
        diameter = calculate_diameter(cluster_coords)
        diameter_km = diameter / 1000
        
        ont_ids = [p[2].get("ID") or p[2].get("id") for p in cluster_points]
        
        split_pocket_dict = {
            "pocket_id": f"{base_id}_SPLIT_{i+1}",
            "ont_count": len(cluster_points),
            "ont_ids": ont_ids,
            "ont_points": cluster_points,
            "centroid": centroid,
            "diameter_km": diameter_km,
            "nearest_cable": pocket.get("nearest_cable"),
            "distance_to_cable_m": pocket.get("distance_to_cable_m", float('inf')),
            "merged": False,
            "split_from": pocket["pocket_id"]
        }
        
        # Recursively split if still too large
        if diameter_km > max_diameter_km:
            # Use smaller radius for recursive split
            smaller_radius = cluster_radius_m * 0.5
            further_split = split_pocket(split_pocket_dict, smaller_radius, max_diameter_km)
            split_pockets.extend(further_split)
        else:
            split_pockets.append(split_pocket_dict)
    
    return split_pockets

def get_size_range(ont_count: int) -> str:
    """Get size range string for pocket."""
    if ont_count < 100:
        return "<100"
    elif ont_count < 500:
        return "100-499"
    elif ont_count < 2000:
        return "500-1999"
    else:
        return "≥2000"

def point_to_linestring_distance(point: Tuple[float, float],
                                 linestring: List[Tuple[float, float]]) -> Tuple[float, Tuple[float, float]]:
    """
    Calculate shortest distance from point to LineString.
    
    Args:
        point: Point coordinates (x, y)
        linestring: List of line segment coordinates
        
    Returns:
        Tuple of (distance, nearest_point_on_line)
    """
    from utils.spatial_utils import point_to_line_distance
    
    if len(linestring) < 2:
        return (float('inf'), point)
    
    min_distance = float('inf')
    nearest_point = point
    
    for i in range(len(linestring) - 1):
        segment_start = linestring[i]
        segment_end = linestring[i + 1]
        
        distance = point_to_line_distance(point, segment_start, segment_end)
        
        if distance < min_distance:
            min_distance = distance
            # Calculate nearest point on segment
            px, py = point
            x1, y1 = segment_start
            x2, y2 = segment_end
            
            dx = x2 - x1
            dy = y2 - y1
            
            if dx == 0 and dy == 0:
                nearest_point = segment_start
            else:
                t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
                nearest_point = (x1 + t * dx, y1 + t * dy)
    
    return (min_distance, nearest_point)

