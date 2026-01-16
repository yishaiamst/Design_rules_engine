#!/usr/bin/env python3
"""
phase5_drop_cables.py
-------------------------------------------------------------------------------
Phase 5: Create Drop and Stub Cables

Strategy:
1. Drop Cables: Terminal → ONT (1F, configurable)
2. Stub Cables: MST → FOSC (size matches MST type)
-------------------------------------------------------------------------------
"""

import json
import math
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from utils.spatial_utils import euclidean_distance
from utils.geojson_utils import create_feature, create_feature_collection


def _point_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return euclidean_distance(a[0], a[1], b[0], b[1])


def _flatten_lines(geometry: Dict[str, Any]) -> List[List[List[float]]]:
    if geometry.get("type") == "LineString":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiLineString":
        return geometry.get("coordinates", [])
    return []


def _is_wgs84_coords(sample: Tuple[float, float]) -> bool:
    x, y = sample
    return -180.0 <= x <= 180.0 and -90.0 <= y <= 90.0


def _nearest_point_on_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> Tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return (x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return (x1 + t * dx, y1 + t * dy)


def _add_node(
    point: Tuple[float, float],
    nodes: List[Tuple[float, float]],
    snap_tol: float,
) -> int:
    for idx, p in enumerate(nodes):
        if _point_distance(point, p) <= snap_tol:
            return idx
    nodes.append(point)
    return len(nodes) - 1


def _build_road_graph(
    road_polylines: List[List[Tuple[float, float]]],
    snap_tol: float,
) -> Tuple[List[Tuple[float, float]], Dict[int, List[Tuple[int, float]]], List[Dict[str, Any]]]:
    nodes: List[Tuple[float, float]] = []
    adjacency: Dict[int, List[Tuple[int, float]]] = {}
    segments: List[Dict[str, Any]] = []

    for poly in road_polylines:
        for i in range(len(poly) - 1):
            a = poly[i]
            b = poly[i + 1]
            n1 = _add_node(a, nodes, snap_tol)
            n2 = _add_node(b, nodes, snap_tol)
            d = _point_distance(a, b)
            adjacency.setdefault(n1, []).append((n2, d))
            adjacency.setdefault(n2, []).append((n1, d))
            segments.append({"a": a, "b": b, "n1": n1, "n2": n2})
    return nodes, adjacency, segments


def _insert_projection_node(
    point: Tuple[float, float],
    nodes: List[Tuple[float, float]],
    adjacency: Dict[int, List[Tuple[int, float]]],
    segments: List[Dict[str, Any]],
    snap_tol: float,
    max_snap_m: float,
) -> Optional[Tuple[int, Tuple[float, float], float]]:
    best = None
    for i, seg in enumerate(segments):
        a = seg["a"]
        b = seg["b"]
        proj = _nearest_point_on_segment(point[0], point[1], a[0], a[1], b[0], b[1])
        d = _point_distance(point, proj)
        if best is None or d < best[2]:
            best = (proj, i, d)
    if best is None or best[2] > max_snap_m:
        return None

    proj, seg_index, dist = best
    node_id = _add_node(proj, nodes, snap_tol)
    seg = segments[seg_index]
    n1 = seg["n1"]
    n2 = seg["n2"]
    adjacency.setdefault(node_id, [])
    adjacency[node_id].append((n1, _point_distance(proj, seg["a"])))
    adjacency[node_id].append((n2, _point_distance(proj, seg["b"])))
    adjacency.setdefault(n1, []).append((node_id, _point_distance(proj, seg["a"])))
    adjacency.setdefault(n2, []).append((node_id, _point_distance(proj, seg["b"])))
    return node_id, proj, dist


def _dijkstra(
    adjacency: Dict[int, List[Tuple[int, float]]],
    start: int,
    goal: int,
) -> Optional[List[int]]:
    import heapq

    dist = {start: 0.0}
    prev: Dict[int, int] = {}
    heap = [(0.0, start)]
    visited = set()

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == goal:
            break
        for v, w in adjacency.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    if goal not in dist:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def _path_length(coords: List[Tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        total += _point_distance(coords[i], coords[i + 1])
    return total


def _normalize_roads(roads_geojson: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
    polylines: List[List[Tuple[float, float]]] = []
    sample_coord = None
    for feature in roads_geojson.get("features", [])[:1]:
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if coords:
            if isinstance(coords[0], list) and len(coords[0]) >= 2:
                sample_coord = coords[0]
            elif len(coords) >= 2:
                sample_coord = coords[0]
            break

    needs_conversion = False
    if sample_coord:
        needs_conversion = _is_wgs84_coords((float(sample_coord[0]), float(sample_coord[1])))

    for feature in roads_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        for part in _flatten_lines(geometry):
            if len(part) < 2:
                continue
            coords = []
            for p in part:
                x, y = float(p[0]), float(p[1])
                if needs_conversion:
                    from phases.phase3e_connect_isolated_cables import convert_wgs84_to_utm_coords
                    x, y = convert_wgs84_to_utm_coords(x, y, utm_zone=17)
                coords.append((x, y))
            if len(coords) >= 2:
                polylines.append(coords)
    return polylines

def get_terminal_port_capacity(terminal: Dict[str, Any], config: Dict[str, Any]) -> int:
    """Get port capacity for a terminal based on its type and model."""
    terminal_type = terminal.get("type", "")
    terminal_model = terminal.get("model", "")
    
    if terminal_type == "MST":
        mst_config = config.get("equipment", {}).get("mst", {})
        ports = mst_config.get(terminal_model, {}).get("ports", 12)
        return ports
    elif terminal_type == "Aerial Terminal":
        aerial_config = config.get("equipment", {}).get("aerial_terminal", {})
        ports = aerial_config.get(terminal_model, {}).get("ports", 12)
        return ports
    
    return 12  # Default

def create_drop_cables(
    terminals: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Create drop cables from terminals to ONTs.
    
    Args:
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        config: Configuration dictionary
    
    Returns:
        (drop_cables_list, summary_stats)
    """
    print("  Creating drop cables (Terminal → ONT)...")
    
    # Get configuration
    drop_cable_config = config.get("cables", {}).get("drop_cable", {})
    default_drop_size = drop_cable_config.get("default_size", 1)
    
    # Load ONTs
    onts = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            onts[ont_id] = {
                "id": ont_id,
                "position": (coords[0], coords[1])
            }
    
    print(f"    Loaded {len(onts)} ONTs")
    
    # Create drop cables for each terminal
    drop_cables = []
    drop_cable_id_counter = 1
    summary = {
        "total_drop_cables": 0,
        "total_length_m": 0.0,
        "by_terminal_type": defaultdict(int),
        "terminals_at_capacity": 0,
        "onts_not_connected": 0,
        "length_stats": {
            "min": float('inf'),
            "max": 0.0,
            "total": 0.0,
            "count": 0
        }
    }
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id")
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        connected_ont_ids = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_ont_ids:
            continue
        
        # Get terminal port capacity from model
        port_capacity = get_terminal_port_capacity(terminal, config)
        
        # IMPORTANT: Respect terminal port limit
        # Only create drop cables up to the port capacity
        original_ont_count = len(connected_ont_ids)
        ont_ids_to_connect = connected_ont_ids[:port_capacity]
        
        if original_ont_count > port_capacity:
            summary["terminals_at_capacity"] += 1
            summary["onts_not_connected"] += original_ont_count - port_capacity
            print(f"    ⚠️  Terminal {terminal_id} ({terminal_type} {terminal.get('model', '')}) has {original_ont_count} ONTs but only {port_capacity} ports. Limiting to {port_capacity} drop cables.")
        
        # Create drop cable for each ONT (up to port capacity)
        for ont_id in ont_ids_to_connect:
            if ont_id not in onts:
                continue
            
            ont_pos = onts[ont_id]["position"]
            
            # Calculate drop cable length
            length = euclidean_distance(
                terminal_pos[0], terminal_pos[1],
                ont_pos[0], ont_pos[1]
            )
            
            # Create drop cable feature
            drop_cable_id = f"DC{drop_cable_id_counter:07d}"
            drop_cable = {
                "cable_id": drop_cable_id,
                "from_id": terminal_id,
                "to_id": ont_id,
                "from_type": "terminal",
                "to_type": "ont",
                "size": default_drop_size,
                "length_m": length,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [terminal_pos[0], terminal_pos[1]],
                        [ont_pos[0], ont_pos[1]]
                    ]
                }
            }
            
            drop_cables.append(drop_cable)
            drop_cable_id_counter += 1
            summary["total_drop_cables"] += 1
            summary["total_length_m"] += length
            summary["by_terminal_type"][terminal_type] += 1
            
            # Update length stats
            if length < summary["length_stats"]["min"]:
                summary["length_stats"]["min"] = length
            if length > summary["length_stats"]["max"]:
                summary["length_stats"]["max"] = length
            summary["length_stats"]["total"] += length
            summary["length_stats"]["count"] += 1
    
    # Calculate average length
    if summary["length_stats"]["count"] > 0:
        summary["length_stats"]["average"] = summary["length_stats"]["total"] / summary["length_stats"]["count"]
        sorted_lengths = sorted([dc["length_m"] for dc in drop_cables])
        summary["length_stats"]["median"] = sorted_lengths[len(sorted_lengths) // 2] if sorted_lengths else 0.0
    else:
        summary["length_stats"]["average"] = 0.0
        summary["length_stats"]["median"] = 0.0
        summary["length_stats"]["min"] = 0.0
    
    print(f"  ✓ Created {summary['total_drop_cables']} drop cables")
    print(f"    Total length: {summary['total_length_m']:.1f}m")
    print(f"    Average length: {summary['length_stats']['average']:.1f}m")
    print(f"    Median length: {summary['length_stats']['median']:.1f}m")
    print(f"    By type: {dict(summary['by_terminal_type'])}")
    
    return (drop_cables, summary)

def create_stub_cables(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    config: Dict[str, Any],
    fiber_cables: List[Dict[str, Any]] = None,
    roads_geojson: Dict[str, Any] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Create stub cables from MST terminals to FOSCs.
    IMPORTANT: Stub cable size matches MST port count (MST12 → 12F, MST6 → 6F, etc.)
    
    Args:
        terminals: List of terminal dictionaries (only MSTs will be used)
        foscs: List of FOSC dictionaries
        config: Configuration dictionary
    
    Returns:
        (stub_cables_list, summary_stats)
    """
    print("  Creating stub cables (MST → FOSC)...")
    
    # Get MST configuration
    mst_config = config.get("equipment", {}).get("mst", {})
    
    # Build FOSC position map
    fosc_positions = {}
    fosc_meta = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id")
        fosc_pos = fosc.get("position")
        if fosc_id and fosc_pos:
            fosc_positions[fosc_id] = fosc_pos
            fosc_meta[fosc_id] = {
                "cable_count": fosc.get("cable_count", 0)
            }
    
    print(f"    Loaded {len(fosc_positions)} FOSCs")
    
    # Prepare road graph (optional)
    road_nodes = None
    road_adjacency = None
    road_segments = None
    if roads_geojson and roads_geojson.get("features"):
        road_polylines = _normalize_roads(roads_geojson)
        if road_polylines:
            road_nodes, road_adjacency, road_segments = _build_road_graph(
                road_polylines,
                snap_tol=float(config.get("routing", {}).get("road_node_snap_m", 0.5))
            )
        else:
            print("    ⚠️  No road polylines found; stub routing will use fiber only")
    else:
        print("    ⚠️  No road layer provided; stub routing will use fiber only")

    # Create stub cables for MST terminals
    stub_cables = []
    stub_cable_id_counter = 1
    summary = {
        "total_stub_cables": 0,
        "total_length_m": 0.0,
        "by_mst_type": defaultdict(int),
        "skipped_no_route": 0,
        "routed_along_roads": 0,
        "routed_along_fiber": 0,
        "length_stats": {
            "min": float('inf'),
            "max": 0.0,
            "total": 0.0,
            "count": 0
        }
    }
    
    routing_config = config.get("routing", {})
    max_road_snap_m = float(routing_config.get("max_road_snap_m", 50.0))
    max_fosc_candidates = int(routing_config.get("max_fosc_candidates", 8))
    road_path_tolerance_m = float(routing_config.get("road_path_tolerance_m", 25.0))
    for terminal in terminals:
        terminal_type = terminal.get("type", "")
        if terminal_type != "MST":
            continue
        
        terminal_id = terminal.get("terminal_id")
        terminal_pos = terminal.get("position")
        terminal_model = terminal.get("model", "MST12")
        nearest_fosc_id = terminal.get("nearest_fosc_id")
        distance_to_fosc = terminal.get("distance_to_fosc_m")
        
        if not terminal_pos:
            continue
        
        # Find FOSC for this MST
        # CRITICAL: Use same logic as Rule 20 - prioritize FOSCs that can route along fiber
        # First, check if terminal already has a connected_fosc_id (from Rule 20)
        target_fosc_id = terminal.get("connected_fosc_id")
        target_fosc_pos = None
        
        if target_fosc_id and target_fosc_id in fosc_positions:
            # Use the FOSC assigned by Rule 20 (which validates routing)
            target_fosc_pos = fosc_positions[target_fosc_id]
        elif nearest_fosc_id and nearest_fosc_id in fosc_positions:
            # Fallback to nearest_fosc_id if Rule 20 didn't assign one
            target_fosc_id = nearest_fosc_id
            target_fosc_pos = fosc_positions[nearest_fosc_id]
        else:
            # Find nearest FOSC
            min_dist = float('inf')
            for fosc_id, fosc_pos in fosc_positions.items():
                dist = euclidean_distance(
                    terminal_pos[0], terminal_pos[1],
                    fosc_pos[0], fosc_pos[1]
                )
                if dist < min_dist:
                    min_dist = dist
                    target_fosc_id = fosc_id
                    target_fosc_pos = fosc_pos
        
        # Road-based routing: choose shortest road path to a FOSC when roads are provided
        road_path_coords = None
        road_path_length = 0.0
        if road_nodes and road_adjacency and road_segments:
            # Build candidate list from nearest FOSCs
            fosc_candidates = []
            for fosc_id, fosc_pos in fosc_positions.items():
                dist = _point_distance(terminal_pos, fosc_pos)
                fosc_candidates.append((dist, fosc_id, fosc_pos, fosc_meta.get(fosc_id, {}).get("cable_count", 0)))
            fosc_candidates.sort(key=lambda x: x[0])
            fosc_candidates = fosc_candidates[:max_fosc_candidates]
            # Ensure connected_fosc_id is included if available
            if target_fosc_id and target_fosc_pos:
                if all(fid != target_fosc_id for _, fid, _, _ in fosc_candidates):
                    fosc_candidates.insert(0, (_point_distance(terminal_pos, target_fosc_pos), target_fosc_id, target_fosc_pos, fosc_meta.get(target_fosc_id, {}).get("cable_count", 0)))

            best = None
            for _, fosc_id, fosc_pos, cable_count in fosc_candidates:
                start = _insert_projection_node(
                    terminal_pos, road_nodes, road_adjacency, road_segments,
                    snap_tol=float(routing_config.get("road_node_snap_m", 0.5)),
                    max_snap_m=max_road_snap_m
                )
                end = _insert_projection_node(
                    fosc_pos, road_nodes, road_adjacency, road_segments,
                    snap_tol=float(routing_config.get("road_node_snap_m", 0.5)),
                    max_snap_m=max_road_snap_m
                )
                if not start or not end:
                    continue
                path = _dijkstra(road_adjacency, start[0], end[0])
                if not path or len(path) < 2:
                    continue
                coords = [road_nodes[n] for n in path]
                # Add terminal and fosc endpoints if off-road
                if _point_distance(terminal_pos, coords[0]) > 1.0:
                    coords = [terminal_pos] + coords
                if _point_distance(fosc_pos, coords[-1]) > 1.0:
                    coords = coords + [fosc_pos]
                length = _path_length(coords)
                if best is None:
                    best = (length, fosc_id, fosc_pos, coords, cable_count)
                else:
                    if length < best[0] - road_path_tolerance_m:
                        best = (length, fosc_id, fosc_pos, coords, cable_count)
                    elif abs(length - best[0]) <= road_path_tolerance_m and cable_count > best[4]:
                        best = (length, fosc_id, fosc_pos, coords, cable_count)
            if best:
                road_path_length, target_fosc_id, target_fosc_pos, road_path_coords, _ = best

        # CRITICAL: If road routing not available, fall back to fiber routing
        if not road_path_coords and fiber_cables and len(fiber_cables) > 0 and target_fosc_id:
            try:
                from utils.cable_routing import route_stub_cable_along_fiber
                terminal_cable_id = terminal.get("connected_cable_id")
                fosc = next((f for f in foscs if f.get("fosc_id") == target_fosc_id), None)
                fosc_connected_cables = fosc.get("connected_cables", []) if fosc else []
                
                # Try routing to current FOSC
                test_result = route_stub_cable_along_fiber(
                    terminal_pos,
                    target_fosc_pos,
                    fiber_cables,
                    terminal_cable_id=terminal_cable_id,
                    preferred_cable_id=terminal_cable_id,
                    fosc_connected_cables=fosc_connected_cables
                )
                
                # If routing fails, find alternative FOSC that can route
                if not test_result or len(test_result) != 3 or not test_result[2]:
                    # Try all FOSCs to find one that can route
                    best_fosc_id = None
                    best_fosc_pos = None
                    best_dist = float('inf')
                    
                    for alt_fosc_id, alt_fosc_pos in fosc_positions.items():
                        if alt_fosc_id == target_fosc_id:
                            continue
                        alt_fosc = next((f for f in foscs if f.get("fosc_id") == alt_fosc_id), None)
                        if alt_fosc:
                            alt_fosc_connected_cables = alt_fosc.get("connected_cables", [])
                            alt_result = route_stub_cable_along_fiber(
                                terminal_pos,
                                alt_fosc_pos,
                                fiber_cables,
                                terminal_cable_id=terminal_cable_id,
                                preferred_cable_id=terminal_cable_id,
                                fosc_connected_cables=alt_fosc_connected_cables
                            )
                            if alt_result and len(alt_result) == 3 and alt_result[2]:
                                # This FOSC can route - check distance
                                alt_dist = euclidean_distance(
                                    terminal_pos[0], terminal_pos[1],
                                    alt_fosc_pos[0], alt_fosc_pos[1]
                                )
                                if alt_dist < best_dist and alt_dist <= 1000.0:  # Within 1km
                                    best_fosc_id = alt_fosc_id
                                    best_fosc_pos = alt_fosc_pos
                                    best_dist = alt_dist
                    
                    # Use best alternative if found
                    if best_fosc_id:
                        target_fosc_id = best_fosc_id
                        target_fosc_pos = best_fosc_pos
            except Exception:
                # If validation fails, continue with original FOSC
                pass
        
        if not target_fosc_id or not target_fosc_pos:
            continue
        
        # Get stub cable size from MST model
        # CRITICAL: Stub cable size MUST match MST port count
        # MST4=4F, MST6=6F, MST8=8F, MST12=12F
        # This is the key relationship: stub cable size = MST port count
        stub_size = mst_config.get(terminal_model, {}).get("ports", 12)
        
        # CRITICAL: Route stub cable along roads when available, otherwise along fiber
        # Use fiber_cables parameter if provided, otherwise try to get from config
        if not fiber_cables:
            fiber_cables = config.get("fiber_cables", [])
        
        path_coords = None
        length = 0.0
        routed_along_cable = False
        routed_along_roads = False

        if road_path_coords:
            path_coords = [[p[0], p[1]] for p in road_path_coords]
            length = road_path_length
            routed_along_roads = True
        
        if not routed_along_roads and fiber_cables and len(fiber_cables) > 0:
            try:
                from utils.cable_routing import route_stub_cable_along_fiber
                terminal_cable_id = terminal.get("connected_cable_id")
                fosc = next((f for f in foscs if f.get("fosc_id") == target_fosc_id), None)
                # CRITICAL: Pass fosc_connected_cables like Rule 20 does
                fosc_connected_cables = fosc.get("connected_cables", []) if fosc else []
                
                result = route_stub_cable_along_fiber(
                    terminal_pos,
                    target_fosc_pos,
                    fiber_cables,
                    terminal_cable_id=terminal_cable_id,
                    preferred_cable_id=terminal_cable_id,
                    fosc_connected_cables=fosc_connected_cables  # This is the key parameter!
                )
                
                if result and len(result) == 3:
                    path_coords, length, routed_along_cable = result
                else:
                    # Function returned None or wrong format
                    path_coords = None
            except Exception as e:
                # Silently fall back to straight line if routing fails
                path_coords = None
        
        # If routing failed, try to find ANY nearby cable and route along it
        # This is a fallback to ensure stub cables always route along fiber when possible
        if not routed_along_roads and (not path_coords or len(path_coords) < 2):
            if fiber_cables and len(fiber_cables) > 0:
                try:
                    from phases.phase3b_refine_mst_placement import find_nearest_point_on_cable
                    from utils.cable_routing import route_along_single_cable, calculate_path_length
                    
                    # Find nearest cable to terminal
                    nearest_cable = None
                    min_dist = float('inf')
                    nearest_term_on_cable = None
                    nearest_fosc_on_cable = None
                    
                    for cable in fiber_cables:
                        term_point, term_dist = find_nearest_point_on_cable(terminal_pos, cable)
                        fosc_point, fosc_dist = find_nearest_point_on_cable(target_fosc_pos, cable)
                        combined_dist = term_dist + fosc_dist
                        if combined_dist < min_dist:
                            min_dist = combined_dist
                            nearest_cable = cable
                            nearest_term_on_cable = term_point
                            nearest_fosc_on_cable = fosc_point
                    
                    # If we found a cable, route along it (even if points are far)
                    # This ensures stub cables follow infrastructure
                    if nearest_cable:
                        path_along_cable = route_along_single_cable(
                            nearest_term_on_cable,
                            nearest_fosc_on_cable,
                            nearest_cable
                        )
                        if path_along_cable and len(path_along_cable) > 2:
                            # Build full path: terminal -> cable -> FOSC
                            path_coords = []
                            # Add terminal if off-cable
                            term_to_cable_dist = euclidean_distance(
                                terminal_pos[0], terminal_pos[1],
                                nearest_term_on_cable[0], nearest_term_on_cable[1]
                            )
                            if term_to_cable_dist > 1.0:
                                path_coords.append([terminal_pos[0], terminal_pos[1]])
                            # Add path along cable
                            path_coords.extend([[p[0], p[1]] for p in path_along_cable])
                            # Update FOSC endpoint if off-cable
                            fosc_to_cable_dist = euclidean_distance(
                                target_fosc_pos[0], target_fosc_pos[1],
                                nearest_fosc_on_cable[0], nearest_fosc_on_cable[1]
                            )
                            if fosc_to_cable_dist > 1.0:
                                path_coords[-1] = [target_fosc_pos[0], target_fosc_pos[1]]
                            length = calculate_path_length(path_coords)
                            routed_along_cable = True
                except Exception as e:
                    # If fallback also fails, continue to straight line
                    pass
            
        # Final rule: stub cables must follow roads (preferred) or fiber if no roads
        if not path_coords or len(path_coords) < 2 or (not routed_along_roads and not routed_along_cable):
            summary["skipped_no_route"] += 1
            print(f"    ⚠️  Skipping stub cable for {terminal_id} → {target_fosc_id} (no valid road or fiber path)")
            continue
        
        # Create stub cable feature
        stub_cable_id = f"SC{stub_cable_id_counter:07d}"
        stub_cable = {
            "cable_id": stub_cable_id,
            "from_id": terminal_id,
            "to_id": target_fosc_id,
            "from_type": "terminal",
            "to_type": "fosc",
            "size": stub_size,
            "length_m": length,
            "routed_along_cable": routed_along_cable,
            "routed_along_roads": routed_along_roads,
            "geometry": {
                "type": "LineString",
                "coordinates": path_coords
            }
        }
        
        stub_cables.append(stub_cable)
        stub_cable_id_counter += 1
        summary["total_stub_cables"] += 1
        summary["total_length_m"] += length
        summary["by_mst_type"][terminal_model] += 1
        if routed_along_roads:
            summary["routed_along_roads"] += 1
        elif routed_along_cable:
            summary["routed_along_fiber"] += 1
        
        # Update length stats
        if length < summary["length_stats"]["min"]:
            summary["length_stats"]["min"] = length
        if length > summary["length_stats"]["max"]:
            summary["length_stats"]["max"] = length
        summary["length_stats"]["total"] += length
        summary["length_stats"]["count"] += 1
    
    # Calculate average length
    if summary["length_stats"]["count"] > 0:
        summary["length_stats"]["average"] = summary["length_stats"]["total"] / summary["length_stats"]["count"]
        sorted_lengths = sorted([sc["length_m"] for sc in stub_cables])
        summary["length_stats"]["median"] = sorted_lengths[len(sorted_lengths) // 2] if sorted_lengths else 0.0
    else:
        summary["length_stats"]["average"] = 0.0
        summary["length_stats"]["median"] = 0.0
        summary["length_stats"]["min"] = 0.0
    
    print(f"  ✓ Created {summary['total_stub_cables']} stub cables")
    print(f"    Total length: {summary['total_length_m']:.1f}m")
    print(f"    Average length: {summary['length_stats']['average']:.1f}m")
    print(f"    Median length: {summary['length_stats']['median']:.1f}m")
    print(f"    By MST type: {dict(summary['by_mst_type'])}")
    print(f"    Routed via roads: {summary['routed_along_roads']}, fiber: {summary['routed_along_fiber']}")
    if summary["skipped_no_route"] > 0:
        print(f"    ⚠️  Skipped {summary['skipped_no_route']} stub cables (no fiber path)")
    
    return (stub_cables, summary)

def generate_drop_cable_geojson(drop_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for drop cables."""
    features = []
    
    for cable in drop_cables:
        properties = {
            "ID": cable["cable_id"],
            "From": cable["from_id"],
            "To": cable["to_id"],
            "Size": f"{cable['size']}F",
            "Length_m": round(cable["length_m"], 2)
        }
        
        geometry = cable["geometry"]
        feature = create_feature(geometry, properties)
        features.append(feature)
    
    return create_feature_collection(features, crs="EPSG:32617")

def generate_stub_cable_geojson(stub_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for stub cables."""
    features = []
    
    for cable in stub_cables:
        properties = {
            "ID": cable["cable_id"],
            "From": cable["from_id"],
            "To": cable["to_id"],
            "Size": f"{cable['size']}F",
            "Length_m": round(cable["length_m"], 2)
        }
        
        geometry = cable["geometry"]
        feature = create_feature(geometry, properties)
        features.append(feature)
    
    return create_feature_collection(features, crs="EPSG:32617")

