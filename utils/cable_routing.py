#!/usr/bin/env python3
"""
Cable routing utilities for routing cables along fiber infrastructure.
"""

from typing import List, Tuple, Dict, Any, Optional
from utils.spatial_utils import euclidean_distance, point_to_line_distance
from phases.phase3b_refine_mst_placement import find_nearest_point_on_cable


def find_path_along_fiber_cable(
    start_point: Tuple[float, float],
    end_point: Tuple[float, float],
    cables: List[Dict[str, Any]],
    max_search_distance: float = 1000.0
) -> Optional[List[Tuple[float, float]]]:
    """
    Find a path along fiber cables from start_point to end_point.
    
    This routes the stub cable along the fiber cable infrastructure.
    
    Args:
        start_point: Starting point (MST position)
        end_point: Ending point (FOSC position)
        cables: List of fiber cable dictionaries with 'coordinates' field
        max_search_distance: Maximum distance to search for nearby cables
    
    Returns:
        List of coordinates following the fiber cable path, or None if no path found
    """
    # Find cables near start and end points
    start_cables = []
    end_cables = []
    
    for cable in cables:
        coords = cable.get("coordinates", [])
        if not coords or len(coords) < 2:
            continue
        
        # Check if start point is near this cable
        nearest_start, dist_start = find_nearest_point_on_cable(start_point, cable)
        if dist_start < max_search_distance:
            start_cables.append((cable, nearest_start, dist_start))
        
        # Check if end point is near this cable
        nearest_end, dist_end = find_nearest_point_on_cable(end_point, cable)
        if dist_end < max_search_distance:
            end_cables.append((cable, nearest_end, dist_end))
    
    if not start_cables or not end_cables:
        return None
    
    # Find the best cable that connects start and end
    best_path = None
    min_total_length = float('inf')
    
    for start_cable, start_nearest, start_dist in start_cables:
        for end_cable, end_nearest, end_dist in end_cables:
            # If same cable, route along it
            if start_cable == end_cable:
                path = route_along_single_cable(
                    start_nearest, end_nearest, start_cable
                )
                if path:
                    total_length = calculate_path_length(path)
                    if total_length < min_total_length:
                        min_total_length = total_length
                        best_path = path
    
    # If no single cable connects them, try to find a path through multiple cables
    if not best_path:
        # For now, return None - could implement multi-cable routing later
        return None
    
    return best_path


def route_along_single_cable(
    start_point: Tuple[float, float],
    end_point: Tuple[float, float],
    cable: Dict[str, Any]
) -> Optional[List[Tuple[float, float]]]:
    """
    Route along a single cable from start_point to end_point.
    
    Args:
        start_point: Starting point on cable
        end_point: Ending point on cable
        cable: Cable dictionary with 'coordinates' field
    
    Returns:
        List of coordinates along the cable path
    """
    coords = cable.get("coordinates", [])
    if not coords or len(coords) < 2:
        return None
    
    # Find indices of start and end points on cable
    start_idx = find_closest_segment_index(start_point, coords)
    end_idx = find_closest_segment_index(end_point, coords)
    
    if start_idx is None or end_idx is None:
        return None
    
    # Build path along cable
    path = []
    
    # If start and end are the same (or very close), return minimal path
    if euclidean_distance(start_point[0], start_point[1], end_point[0], end_point[1]) < 1.0:
        return [start_point, end_point]
    
    # Add start point
    path.append(start_point)
    
    # Add intermediate points along cable
    if start_idx < end_idx:
        # Forward direction
        for i in range(start_idx + 1, end_idx + 1):
            path.append(coords[i])
    elif start_idx > end_idx:
        # Reverse direction
        for i in range(start_idx - 1, end_idx - 1, -1):
            path.append(coords[i])
    else:
        # Same segment - add the segment's end point if different from start
        if start_idx + 1 < len(coords):
            segment_end = coords[start_idx + 1]
            if euclidean_distance(start_point[0], start_point[1], segment_end[0], segment_end[1]) > 1.0:
                path.append(segment_end)
    
    # Add end point (if different from last point)
    if not path or euclidean_distance(path[-1][0], path[-1][1], end_point[0], end_point[1]) > 1.0:
        path.append(end_point)
    
    return path


def find_closest_segment_index(
    point: Tuple[float, float],
    coords: List[Tuple[float, float]]
) -> Optional[int]:
    """
    Find the index of the segment closest to the point.
    
    Returns the index of the start of the closest segment.
    """
    if len(coords) < 2:
        return None
    
    min_dist = float('inf')
    closest_idx = 0
    
    for i in range(len(coords) - 1):
        dist = point_to_line_distance(point, coords[i], coords[i + 1])
        if dist < min_dist:
            min_dist = dist
            closest_idx = i
    
    return closest_idx


def calculate_path_length(path: List[Tuple[float, float]]) -> float:
    """Calculate total length of a path."""
    if len(path) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(path) - 1):
        total += euclidean_distance(
            path[i][0], path[i][1],
            path[i + 1][0], path[i + 1][1]
        )
    
    return total


def route_drop_cable_along_fiber(
    ont_pos: Tuple[float, float],
    terminal_pos: Tuple[float, float],
    cables: List[Dict[str, Any]],
    terminal_cable_id: Optional[str] = None,
    max_search_distance: float = 500.0
) -> Tuple[List[Tuple[float, float]], float, bool]:
    """
    Route a drop cable from ONT to terminal along fiber cable infrastructure.
    
    Drop cables MUST run along fiber cables, just like stub cables.
    
    Args:
        ont_pos: ONT position
        terminal_pos: Terminal (MST or Aerial) position
        cables: List of fiber cable dictionaries
        terminal_cable_id: Optional cable ID that terminal is connected to
        max_search_distance: Maximum distance to consider ONT/terminal "on cable" (default 500m)
    
    Returns:
        (path_coordinates, total_length, routed_along_cable)
        routed_along_cable is True if path follows a cable, False if straight line
    """
    # First, try using the terminal's connected cable if provided
    # This is the most reliable since terminal should be on this cable
    if terminal_cable_id:
        terminal_cable = next((c for c in cables if c.get("id") == terminal_cable_id), None)
        if terminal_cable:
            # Check distances to cable
            nearest_ont, ont_dist = find_nearest_point_on_cable(ont_pos, terminal_cable)
            nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
            
            # If terminal is on cable (within 50m), always route through this cable
            if term_dist < 50.0:
                path_along_cable = route_along_single_cable(nearest_ont, nearest_term, terminal_cable)
                if path_along_cable:
                    # Build full path
                    full_path = []
                    if ont_dist > 1.0:
                        full_path.append(ont_pos)
                    full_path.extend(path_along_cable)
                    if term_dist > 1.0:
                        if full_path:
                            full_path[-1] = terminal_pos
                        else:
                            full_path.append(terminal_pos)
                    
                    length = calculate_path_length(full_path)
                    return full_path, length, True
            
            # If both are near this cable (within max_search_distance), route along it
            elif ont_dist < max_search_distance and term_dist < max_search_distance:
                path = route_along_single_cable(nearest_ont, nearest_term, terminal_cable)
                if path:
                    # Build full path including connections from ONT/terminal if off-cable
                    full_path = []
                    if ont_dist > 1.0:
                        full_path.append(ont_pos)
                    full_path.extend(path)
                    if term_dist > 1.0:
                        if full_path:
                            full_path[-1] = terminal_pos
                        else:
                            full_path.append(terminal_pos)
                    
                    length = calculate_path_length(full_path)
                    return full_path, length, True
    
    # Try finding any cable that both points are near
    best_cable = None
    best_path = None
    min_total_dist = float('inf')
    
    for cable in cables:
        nearest_ont, ont_dist = find_nearest_point_on_cable(ont_pos, cable)
        nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
        
        # If both are near the same cable, route along it
        if ont_dist < max_search_distance and term_dist < max_search_distance:
            path = route_along_single_cable(nearest_ont, nearest_term, cable)
            if path:
                # Build full path
                full_path = []
                if ont_dist > 1.0:
                    full_path.append(ont_pos)
                full_path.extend(path)
                if term_dist > 1.0:
                    if full_path:
                        full_path[-1] = terminal_pos
                    else:
                        full_path.append(terminal_pos)
                
                # Prefer cable where both points are closer
                total_dist = ont_dist + term_dist
                if total_dist < min_total_dist:
                    min_total_dist = total_dist
                    best_cable = cable
                    best_path = full_path
    
    if best_path:
        length = calculate_path_length(best_path)
        return best_path, length, True
    
    # Try finding cable where terminal is on it, and route from terminal to nearest point on cable to ONT
    # This handles case where ONT is off-cable but terminal is on-cable
    if terminal_cable_id:
        terminal_cable = next((c for c in cables if c.get("id") == terminal_cable_id), None)
        if terminal_cable:
            nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
            if term_dist < 50.0:  # Terminal is on cable
                # Find nearest point on cable to ONT
                nearest_ont_on_cable, ont_dist = find_nearest_point_on_cable(ont_pos, terminal_cable)
                if ont_dist < max_search_distance:
                    # Route along cable from nearest_ont_on_cable to nearest_term
                    path_along_cable = route_along_single_cable(nearest_ont_on_cable, nearest_term, terminal_cable)
                    if path_along_cable:
                        # Full path: ONT -> nearest point on cable -> ... -> terminal
                        path = []
                        if ont_dist > 1.0:
                            path.append(ont_pos)
                        path.extend(path_along_cable)
                        if term_dist > 1.0:
                            if path:
                                path[-1] = terminal_pos
                            else:
                                path.append(terminal_pos)
                        length = calculate_path_length(path)
                        return path, length, True
    
    # Try finding cable where ONT is on it, and route from ONT to nearest point on cable to terminal
    # This handles case where terminal is off-cable but ONT is on-cable
    for cable in cables:
        nearest_ont, ont_dist = find_nearest_point_on_cable(ont_pos, cable)
        if ont_dist < 50.0:  # ONT is on cable
            nearest_term_on_cable, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
            if term_dist < max_search_distance:
                # Route along cable from nearest_ont to nearest_term_on_cable
                path_along_cable = route_along_single_cable(nearest_ont, nearest_term_on_cable, cable)
                if path_along_cable:
                    # Full path: ONT -> ... -> nearest point on cable -> terminal
                    path = []
                    if ont_dist > 1.0:
                        path.append(ont_pos)
                    path.extend(path_along_cable)
                    if term_dist > 1.0:
                        if path:
                            path[-1] = terminal_pos
                        else:
                            path.append(terminal_pos)
                    length = calculate_path_length(path)
                    return path, length, True
    
    # Final attempt: Find nearest cable to either ONT or terminal and route through it
    # This handles cases where both are off-cable but we can route through a nearby cable
    best_cable = None
    best_path = None
    min_total_dist = float('inf')
    
    for cable in cables:
        nearest_ont, ont_dist = find_nearest_point_on_cable(ont_pos, cable)
        nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
        
        # If either is near the cable (within max_search_distance), try routing through it
        if ont_dist < max_search_distance or term_dist < max_search_distance:
            # Route along cable between the two nearest points
            path_along_cable = route_along_single_cable(nearest_ont, nearest_term, cable)
            if path_along_cable:
                # Build full path: ONT -> nearest point on cable -> ... -> nearest point on cable -> terminal
                path = []
                
                # Start with ONT if it's off-cable
                if ont_dist > 10.0:
                    path.append(ont_pos)
                
                # Add path along cable (skip first point if ONT was added, as it's the same as nearest_ont)
                if path:
                    path.extend(path_along_cable[1:])  # Skip first point (nearest_ont) since we have ont_pos
                else:
                    path.extend(path_along_cable)
                
                # End with terminal if it's off-cable
                if term_dist > 10.0:
                    # Remove last point from path_along_cable (nearest_term) and add terminal_pos
                    if path and len(path) > 0:
                        path[-1] = terminal_pos
                    else:
                        path.append(terminal_pos)
                
                if len(path) > 1:
                    total_dist = ont_dist + term_dist
                    if total_dist < min_total_dist:
                        min_total_dist = total_dist
                        best_cable = cable
                        best_path = path
    
    if best_path:
        length = calculate_path_length(best_path)
        return best_path, length, True
    
    # Final attempt: Find nearest cable to either ONT or terminal and route through it
    # This ensures we always route through a cable
    best_cable_final = None
    best_path_final = None
    min_combined_dist = float('inf')
    
    for cable in cables:
        nearest_ont, ont_dist = find_nearest_point_on_cable(ont_pos, cable)
        nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
        
        # Use cable if either point is reasonably near it
        if ont_dist < max_search_distance or term_dist < max_search_distance:
            path_along_cable = route_along_single_cable(nearest_ont, nearest_term, cable)
            if path_along_cable:
                # Build full path
                path = []
                if ont_dist > 1.0:
                    path.append(ont_pos)
                path.extend(path_along_cable)
                if term_dist > 1.0:
                    if path:
                        path[-1] = terminal_pos
                    else:
                        path.append(terminal_pos)
                
                combined_dist = ont_dist + term_dist
                if combined_dist < min_combined_dist:
                    min_combined_dist = combined_dist
                    best_cable_final = cable
                    best_path_final = path
    
    if best_path_final:
        length = calculate_path_length(best_path_final)
        return best_path_final, length, True
    
    # Final fallback: Find the absolute nearest cable and route through it
    # This ensures we ALWAYS route through a cable, even if both points are far
    nearest_cable_any = None
    min_any_dist = float('inf')
    best_ont_point = None
    best_term_point = None
    
    for cable in cables:
        nearest_ont, ont_dist = find_nearest_point_on_cable(ont_pos, cable)
        nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
        
        # Use the cable with minimum combined distance
        combined_dist = ont_dist + term_dist
        if combined_dist < min_any_dist:
            min_any_dist = combined_dist
            nearest_cable_any = cable
            best_ont_point = nearest_ont
            best_term_point = nearest_term
    
    if nearest_cable_any:
        # Route along cable between the two nearest points
        path_along_cable = route_along_single_cable(best_ont_point, best_term_point, nearest_cable_any)
        if path_along_cable:
            # Build path: ONT -> nearest point on cable -> ... -> nearest point on cable -> terminal
            path = [ont_pos]  # Start with ONT
            path.extend(path_along_cable[1:])  # Add cable path (skip first point, it's best_ont_point)
            path[-1] = terminal_pos  # End with terminal
            
            length = calculate_path_length(path)
            return path, length, True
    
    # Absolute final fallback: straight line (should never happen)
    straight_path = [ont_pos, terminal_pos]
    length = euclidean_distance(ont_pos[0], ont_pos[1], terminal_pos[0], terminal_pos[1])
    return straight_path, length, False


def route_stub_cable_along_fiber(
    terminal_pos: Tuple[float, float],
    fosc_pos: Tuple[float, float],
    cables: List[Dict[str, Any]],
    terminal_cable_id: Optional[str] = None,
    preferred_cable_id: Optional[str] = None,
    fosc_connected_cables: Optional[List[str]] = None
) -> Tuple[List[Tuple[float, float]], float, bool]:
    """
    Route a stub cable from terminal to FOSC along fiber cable infrastructure.
    
    Args:
        terminal_pos: Terminal (MST) position
        fosc_pos: FOSC position
        cables: List of fiber cable dictionaries
        terminal_cable_id: Optional cable ID that terminal is connected to
        preferred_cable_id: Optional preferred cable ID to route along
        fosc_connected_cables: Optional list of cable IDs connected to the FOSC
    
    Returns:
        (path_coordinates, total_length, routed_along_cable)
        routed_along_cable: True if path follows fiber cables, False if straight line
    """
    # First, try using preferred cable if specified
    if preferred_cable_id:
        preferred_cable = next((c for c in cables if c.get("id") == preferred_cable_id), None)
        if preferred_cable:
            nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, preferred_cable)
            nearest_fosc, fosc_dist = find_nearest_point_on_cable(fosc_pos, preferred_cable)
            
            if term_dist < 100.0 and fosc_dist < 100.0:
                path = route_along_single_cable(nearest_term, nearest_fosc, preferred_cable)
                if path and len(path) > 2:
                    length = calculate_path_length(path)
                    return path, length, True
    
    # Try using terminal's connected cable and FOSC's connected cables
    if terminal_cable_id and fosc_connected_cables:
        terminal_cable = next((c for c in cables if c.get("id") == terminal_cable_id), None)
        if terminal_cable:
            # Check if terminal cable is one of FOSC's connected cables
            if terminal_cable_id in fosc_connected_cables:
                nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
                nearest_fosc, fosc_dist = find_nearest_point_on_cable(fosc_pos, terminal_cable)
                if term_dist < 100.0 and fosc_dist < 100.0:
                    path = route_along_single_cable(nearest_term, nearest_fosc, terminal_cable)
                    if path and len(path) > 2:
                        length = calculate_path_length(path)
                        return path, length, True
            
            # Try routing: terminal -> terminal cable endpoint -> FOSC position -> FOSC cable
            # FOSCs are at junctions, so route to FOSC position, then along FOSC cable
            term_coords = terminal_cable.get("coordinates", [])
            if term_coords:
                term_start = term_coords[0]
                term_end = term_coords[-1]
                
                # Find which endpoint is closer to FOSC (likely the junction)
                dist_to_start = euclidean_distance(fosc_pos[0], fosc_pos[1], term_start[0], term_start[1])
                dist_to_end = euclidean_distance(fosc_pos[0], fosc_pos[1], term_end[0], term_end[1])
                
                junction_on_term_cable = term_end if dist_to_end < dist_to_start else term_start
                
                # If FOSC is near an endpoint of terminal cable (within 50m), route through it
                if min(dist_to_start, dist_to_end) < 50.0:
                    # Route along terminal cable to junction, then to FOSC position
                    nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
                    if term_dist < 100.0:
                        path1 = route_along_single_cable(nearest_term, junction_on_term_cable, terminal_cable)
                        if path1:
                            # Now route from FOSC position along one of FOSC's connected cables
                            for fosc_cable_id in fosc_connected_cables:
                                fosc_cable = next((c for c in cables if c.get("id") == fosc_cable_id), None)
                                if fosc_cable:
                                    nearest_fosc_on_cable, fosc_dist = find_nearest_point_on_cable(fosc_pos, fosc_cable)
                                    if fosc_dist < 50.0:  # FOSC is on this cable
                                        # Route from FOSC position along the cable (short segment)
                                        # Since FOSC is at junction, just use FOSC position
                                        combined_path = path1 + [fosc_pos]
                                        if len(combined_path) > 2:
                                            length = calculate_path_length(combined_path)
                                            return combined_path, length, True
            
            # Try to find a path through connected cables
            # Find FOSC cables that might connect to terminal cable via junctions or intermediate cables
            for fosc_cable_id in fosc_connected_cables:
                fosc_cable = next((c for c in cables if c.get("id") == fosc_cable_id), None)
                if fosc_cable:
                    # Check if cables share endpoints (junction)
                    term_coords = terminal_cable.get("coordinates", [])
                    fosc_coords = fosc_cable.get("coordinates", [])
                    
                    if term_coords and fosc_coords:
                        # Check if cables share an endpoint (within 10m)
                        term_start = term_coords[0]
                        term_end = term_coords[-1]
                        fosc_start = fosc_coords[0]
                        fosc_end = fosc_coords[-1]
                        
                        junction_point = None
                        # Check all combinations
                        if euclidean_distance(term_start[0], term_start[1], fosc_start[0], fosc_start[1]) < 10.0:
                            junction_point = term_start
                        elif euclidean_distance(term_start[0], term_start[1], fosc_end[0], fosc_end[1]) < 10.0:
                            junction_point = term_start
                        elif euclidean_distance(term_end[0], term_end[1], fosc_start[0], fosc_start[1]) < 10.0:
                            junction_point = term_end
                        elif euclidean_distance(term_end[0], term_end[1], fosc_end[0], fosc_end[1]) < 10.0:
                            junction_point = term_end
                        
                        if junction_point:
                            # Route: terminal -> junction -> FOSC
                            nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
                            nearest_fosc, fosc_dist = find_nearest_point_on_cable(fosc_pos, fosc_cable)
                            
                            if term_dist < 100.0 and fosc_dist < 100.0:
                                path1 = route_along_single_cable(nearest_term, junction_point, terminal_cable)
                                path2 = route_along_single_cable(junction_point, nearest_fosc, fosc_cable)
                                
                                if path1 and path2:
                                    # Combine paths (remove duplicate junction point)
                                    combined_path = path1[:-1] + path2 if path1 else path2
                                    if len(combined_path) > 2:
                                        length = calculate_path_length(combined_path)
                                        return combined_path, length, True
                        
                        # Try to find intermediate cable that connects terminal cable to FOSC cable
                        # Check if there's a cable that shares endpoints with both
                        for intermediate_cable in cables:
                            if intermediate_cable == terminal_cable or intermediate_cable == fosc_cable:
                                continue
                            
                            inter_coords = intermediate_cable.get("coordinates", [])
                            if not inter_coords:
                                continue
                            
                            inter_start = inter_coords[0]
                            inter_end = inter_coords[-1]
                            
                            # Check if intermediate cable connects terminal cable to FOSC cable
                            connects_to_term = False
                            connects_to_fosc = False
                            term_junction = None
                            fosc_junction = None
                            
                            # Check terminal cable connection
                            if euclidean_distance(term_start[0], term_start[1], inter_start[0], inter_start[1]) < 10.0:
                                connects_to_term = True
                                term_junction = term_start
                            elif euclidean_distance(term_start[0], term_start[1], inter_end[0], inter_end[1]) < 10.0:
                                connects_to_term = True
                                term_junction = term_start
                            elif euclidean_distance(term_end[0], term_end[1], inter_start[0], inter_start[1]) < 10.0:
                                connects_to_term = True
                                term_junction = term_end
                            elif euclidean_distance(term_end[0], term_end[1], inter_end[0], inter_end[1]) < 10.0:
                                connects_to_term = True
                                term_junction = term_end
                            
                            # Check FOSC cable connection
                            if euclidean_distance(fosc_start[0], fosc_start[1], inter_start[0], inter_start[1]) < 10.0:
                                connects_to_fosc = True
                                fosc_junction = fosc_start
                            elif euclidean_distance(fosc_start[0], fosc_start[1], inter_end[0], inter_end[1]) < 10.0:
                                connects_to_fosc = True
                                fosc_junction = fosc_start
                            elif euclidean_distance(fosc_end[0], fosc_end[1], inter_start[0], inter_start[1]) < 10.0:
                                connects_to_fosc = True
                                fosc_junction = fosc_end
                            elif euclidean_distance(fosc_end[0], fosc_end[1], inter_end[0], inter_end[1]) < 10.0:
                                connects_to_fosc = True
                                fosc_junction = fosc_end
                            
                            if connects_to_term and connects_to_fosc and term_junction and fosc_junction:
                                # Found path: terminal -> term_junction -> intermediate -> fosc_junction -> FOSC
                                nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
                                nearest_fosc, fosc_dist = find_nearest_point_on_cable(fosc_pos, fosc_cable)
                                
                                if term_dist < 100.0 and fosc_dist < 100.0:
                                    # Find junction points on intermediate cable
                                    inter_term_junc, _ = find_nearest_point_on_cable(term_junction, intermediate_cable)
                                    inter_fosc_junc, _ = find_nearest_point_on_cable(fosc_junction, intermediate_cable)
                                    
                                    path1 = route_along_single_cable(nearest_term, term_junction, terminal_cable)
                                    path2 = route_along_single_cable(inter_term_junc, inter_fosc_junc, intermediate_cable)
                                    path3 = route_along_single_cable(fosc_junction, nearest_fosc, fosc_cable)
                                    
                                    if path1 and path2 and path3:
                                        # Combine paths
                                        combined_path = path1[:-1] + path2[:-1] + path3
                                        if len(combined_path) > 2:
                                            length = calculate_path_length(combined_path)
                                            return combined_path, length, True
    
    # Try using terminal's connected cable if provided
    if terminal_cable_id:
        terminal_cable = next((c for c in cables if c.get("id") == terminal_cable_id), None)
        if terminal_cable:
            nearest_fosc, fosc_dist = find_nearest_point_on_cable(fosc_pos, terminal_cable)
            if fosc_dist < 50.0:  # FOSC is on same cable
                nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, terminal_cable)
                if term_dist < 50.0:
                    path = route_along_single_cable(nearest_term, nearest_fosc, terminal_cable)
                    if path and len(path) > 2:
                        length = calculate_path_length(path)
                        return path, length, True
    
    # Try to find path along fiber cables (general search)
    path = find_path_along_fiber_cable(terminal_pos, fosc_pos, cables, max_search_distance=1000.0)
    
    if path and len(path) > 2:
        length = calculate_path_length(path)
        return path, length, True
    
    # Try finding any cable that both points are near
    for cable in cables:
        nearest_term, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
        nearest_fosc, fosc_dist = find_nearest_point_on_cable(fosc_pos, cable)
        
        if term_dist < 50.0 and fosc_dist < 50.0:
            path = route_along_single_cable(nearest_term, nearest_fosc, cable)
            if path and len(path) > 2:
                length = calculate_path_length(path)
                return path, length, True
    
    # NO FALLBACK TO STRAIGHT LINE - stub cables MUST route along fiber
    # Return None to indicate failure
    return None, 0.0, False
