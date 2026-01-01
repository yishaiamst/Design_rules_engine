#!/usr/bin/env python3
"""
Cable Grouping Utilities
Group cable segments into logical cables based on topology (endpoint connections)
rather than relying on GeoJSON feature structure.
"""

from typing import Dict, List, Any, Tuple, Set
from collections import defaultdict
from utils.spatial_utils import euclidean_distance


def round_to_grid(point: Tuple[float, float], grid_size: float) -> Tuple[float, float]:
    """Round point to grid for grouping."""
    return (
        round(point[0] / grid_size) * grid_size,
        round(point[1] / grid_size) * grid_size
    )


def extract_coordinates(geometry: Dict[str, Any]) -> List[Tuple[float, float]]:
    """Extract coordinates from LineString or MultiLineString geometry."""
    coords = []
    geom_type = geometry.get("type", "")
    
    if geom_type == "LineString":
        coords_list = geometry.get("coordinates", [])
        coords = [(c[0], c[1]) for c in coords_list if len(c) >= 2]
    elif geom_type == "MultiLineString":
        for line in geometry.get("coordinates", []):
            for c in line:
                if len(c) >= 2:
                    coords.append((c[0], c[1]))
    
    return coords


def find_connected_components(
    segments: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[List[int]]:
    """
    Find groups of segments that are connected end-to-end.
    
    Uses graph traversal (BFS) to find connected components.
    Two segments are connected if they share an endpoint within tolerance.
    
    Args:
        segments: List of segment dicts with 'start', 'end', 'coordinates'
        tolerance_m: Distance tolerance for considering endpoints as the same
        
    Returns:
        List of component lists, where each component contains segment indices
    """
    grid_size = tolerance_m
    
    # Build endpoint map: rounded position -> list of (segment_idx, endpoint_type)
    endpoint_map = defaultdict(list)
    
    for i, segment in enumerate(segments):
        start_rounded = round_to_grid(segment["start"], grid_size)
        end_rounded = round_to_grid(segment["end"], grid_size)
        
        endpoint_map[start_rounded].append((i, 'start'))
        endpoint_map[end_rounded].append((i, 'end'))
    
    # Find connected components using BFS
    visited = set()
    components = []
    
    for i in range(len(segments)):
        if i in visited:
            continue
        
        # BFS to find all segments connected to this one
        component = []
        queue = [i]
        visited.add(i)
        
        while queue:
            seg_idx = queue.pop(0)
            component.append(seg_idx)
            
            # Find segments connected to this segment's endpoints
            segment = segments[seg_idx]
            start_rounded = round_to_grid(segment["start"], grid_size)
            end_rounded = round_to_grid(segment["end"], grid_size)
            
            # Check start endpoint
            for other_idx, endpoint_type in endpoint_map[start_rounded]:
                if other_idx != seg_idx and other_idx not in visited:
                    queue.append(other_idx)
                    visited.add(other_idx)
            
            # Check end endpoint
            for other_idx, endpoint_type in endpoint_map[end_rounded]:
                if other_idx != seg_idx and other_idx not in visited:
                    queue.append(other_idx)
                    visited.add(other_idx)
        
        components.append(component)
    
    return components


def merge_segment_coordinates(
    segments: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> List[Tuple[float, float]]:
    """
    Merge coordinates from multiple segments into one continuous path.
    
    Connects segments end-to-end based on endpoint matching.
    
    Args:
        segments: List of segment dicts with 'start', 'end', 'coordinates'
        tolerance_m: Distance tolerance for endpoint matching
        
    Returns:
        Merged coordinate list
    """
    if not segments:
        return []
    
    if len(segments) == 1:
        return segments[0]["coordinates"]
    
    grid_size = tolerance_m
    
    # Build a path by connecting segments
    # Start with first segment
    path = list(segments[0]["coordinates"])
    used = {0}
    
    # Keep connecting segments until all are used
    while len(used) < len(segments):
        last_point = path[-1]
        last_rounded = round_to_grid(last_point, grid_size)
        
        # Find next segment that connects
        best_match = None
        best_match_idx = None
        should_reverse = False
        
        for i, segment in enumerate(segments):
            if i in used:
                continue
            
            start_rounded = round_to_grid(segment["start"], grid_size)
            end_rounded = round_to_grid(segment["end"], grid_size)
            
            # Check if segment's start connects to path end
            if start_rounded == last_rounded:
                best_match = segment
                best_match_idx = i
                should_reverse = False
                break
            
            # Check if segment's end connects to path end (need to reverse)
            if end_rounded == last_rounded:
                best_match = segment
                best_match_idx = i
                should_reverse = True
                break
        
        if best_match is None:
            # No connection found - start a new path segment
            # For now, just add remaining segments
            break
        
        # Add segment to path
        if should_reverse:
            # Reverse segment coordinates
            segment_coords = list(reversed(best_match["coordinates"]))
        else:
            segment_coords = best_match["coordinates"]
        
        # Skip first point if it matches last point in path
        if round_to_grid(segment_coords[0], grid_size) == last_rounded:
            path.extend(segment_coords[1:])
        else:
            path.extend(segment_coords)
        
        used.add(best_match_idx)
    
    return path


def group_cables_by_topology(
    fiber_cable_geojson: Dict[str, Any],
    tolerance_m: float = 10.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Group cable segments into logical cables based on endpoint connections.
    
    This approach:
    - Does NOT rely on GeoJSON feature structure
    - Does NOT require cable IDs
    - Uses topology (endpoint connections) to group segments
    
    Args:
        fiber_cable_geojson: Input GeoJSON with cable features
        tolerance_m: Distance tolerance for endpoint matching
        
    Returns:
        (logical_cables, statistics)
        - logical_cables: List of logical cable dicts
        - statistics: Summary stats about grouping
    """
    # Step 1: Extract all segments
    segments = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        coords = extract_coordinates(geometry)
        
        if len(coords) >= 2:
            segments.append({
                "id": props.get("ID") or props.get("id", ""),
                "start": coords[0],
                "end": coords[-1],
                "coordinates": coords,
                "properties": props,
                "original_feature_index": len(segments)
            })
    
    print(f"    Extracted {len(segments)} cable segments")
    
    # Step 2: Find connected components
    print(f"    Finding connected components (tolerance: {tolerance_m}m)...")
    components = find_connected_components(segments, tolerance_m)
    print(f"    Found {len(components)} logical cables (connected components)")
    
    # Step 3: Build logical cables
    logical_cables = []
    for comp_idx, component_indices in enumerate(components):
        component_segments = [segments[i] for i in component_indices]
        
        # Merge coordinates (connect segments end-to-end)
        merged_coords = merge_segment_coordinates(component_segments, tolerance_m)
        
        # Get IDs (may have multiple if segments have different IDs)
        cable_ids = [seg["id"] for seg in component_segments if seg["id"]]
        unique_ids = list(set(cable_ids))
        
        logical_cables.append({
            "logical_cable_id": f"LOGICAL_{comp_idx+1:04d}",
            "segment_count": len(component_segments),
            "segment_indices": component_indices,
            "cable_ids": unique_ids,  # All IDs from segments in this component
            "primary_id": unique_ids[0] if unique_ids else None,
            "coordinates": merged_coords,
            "start": merged_coords[0] if merged_coords else None,
            "end": merged_coords[-1] if merged_coords else None,
            "segments": component_segments  # Keep original segments for reference
        })
    
    # Statistics
    stats = {
        "total_segments": len(segments),
        "total_logical_cables": len(logical_cables),
        "single_segment_cables": sum(1 for c in logical_cables if c["segment_count"] == 1),
        "multi_segment_cables": sum(1 for c in logical_cables if c["segment_count"] > 1),
        "max_segments_per_cable": max((c["segment_count"] for c in logical_cables), default=0),
        "avg_segments_per_cable": sum(c["segment_count"] for c in logical_cables) / len(logical_cables) if logical_cables else 0
    }
    
    print(f"    Statistics:")
    print(f"      Single-segment cables: {stats['single_segment_cables']}")
    print(f"      Multi-segment cables: {stats['multi_segment_cables']}")
    print(f"      Max segments per cable: {stats['max_segments_per_cable']}")
    print(f"      Avg segments per cable: {stats['avg_segments_per_cable']:.1f}")
    
    return logical_cables, stats

