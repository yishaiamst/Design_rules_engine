#!/usr/bin/env python3
"""
phase3e_connect_isolated_cables.py
-------------------------------------------------------------------------------
Phase 3e: Connect Isolated Fiber Cables

Detects isolated fiber cables (not connected to other cables) and connects
them to the nearest cable or FOSC by extending the isolated cable.

Rule: All fiber cables must be part of a connected network so OLTs can serve
all ONTs. Isolated cables are extended to connect to the nearest cable/FOSC,
and a FOSC is placed at the new intersection point.
-------------------------------------------------------------------------------

"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from utils.spatial_utils import euclidean_distance, point_to_linestring_distance
from utils.geojson_utils import load_geojson


def find_nearest_point_on_line(point: Tuple[float, float], line_coords: List[Tuple[float, float]]) -> Tuple[Tuple[float, float], float]:
    """
    Find the nearest point on a line to a given point.
    
    Returns:
        (nearest_point, distance)
    """
    if not line_coords or len(line_coords) < 2:
        return point, float('inf')
    
    min_dist = float('inf')
    nearest_point = point
    
    for i in range(len(line_coords) - 1):
        p1 = line_coords[i]
        p2 = line_coords[i + 1]
        
        # Vector from p1 to p2
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        line_length_sq = dx*dx + dy*dy
        
        if line_length_sq == 0:
            # Degenerate segment
            dist = euclidean_distance(point[0], point[1], p1[0], p1[1])
            if dist < min_dist:
                min_dist = dist
                nearest_point = p1
            continue
        
        # Vector from p1 to point
        px = point[0] - p1[0]
        py = point[1] - p1[1]
        
        # Project point onto line segment
        t = max(0, min(1, (px*dx + py*dy) / line_length_sq))
        
        # Nearest point on segment
        nearest_x = p1[0] + t * dx
        nearest_y = p1[1] + t * dy
        nearest_on_segment = (nearest_x, nearest_y)
        
        dist = euclidean_distance(point[0], point[1], nearest_x, nearest_y)
        if dist < min_dist:
            min_dist = dist
            nearest_point = nearest_on_segment
    
    return nearest_point, min_dist


def detect_isolated_cables(
    cables_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    tolerance_m: float = 50.0
) -> List[Dict[str, Any]]:
    """
    Detect isolated cables that are not connected to other cables.
    
    A cable is isolated if:
    - Its endpoints don't connect to any FOSC (within tolerance)
    - Its endpoints don't connect to any other cable endpoint (within tolerance)
    - It's not part of a connected component
    
    Returns:
        List of isolated cable features with metadata
    """
    print("  Detecting isolated cables...")
    
    # Build FOSC position map
    fosc_positions = {}
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_id = fosc.get("fosc_id", "")
            fosc_positions[fosc_id] = fosc_pos_utm
    
    # Build cable endpoint map
    cable_endpoints = defaultdict(list)  # (rounded_x, rounded_y) -> [cable_features]
    grid_size = tolerance_m
    
    isolated_cables = []
    
    for feature in cables_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        if len(coords_list) < 2:
            continue
        
        start_point = (float(coords_list[0][0]), float(coords_list[0][1]))
        end_point = (float(coords_list[-1][0]), float(coords_list[-1][1]))
        
        # Check if endpoints connect to FOSCs
        start_connected = False
        end_connected = False
        
        for fosc_id, fosc_pos in fosc_positions.items():
            dist_start = euclidean_distance(start_point[0], start_point[1], fosc_pos[0], fosc_pos[1])
            dist_end = euclidean_distance(end_point[0], end_point[1], fosc_pos[0], fosc_pos[1])
            
            if dist_start < tolerance_m:
                start_connected = True
            if dist_end < tolerance_m:
                end_connected = True
        
        # Add this cable to endpoint map (before checking, so we can see if others share)
        start_rounded = (
            round(start_point[0] / grid_size) * grid_size,
            round(start_point[1] / grid_size) * grid_size
        )
        end_rounded = (
            round(end_point[0] / grid_size) * grid_size,
            round(end_point[1] / grid_size) * grid_size
        )
        
        cable_endpoints[start_rounded].append(feature)
        cable_endpoints[end_rounded].append(feature)
    
    # Second pass: Check which cables are truly isolated
    for feature in cables_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        if len(coords_list) < 2:
            continue
        
        start_point = (float(coords_list[0][0]), float(coords_list[0][1]))
        end_point = (float(coords_list[-1][0]), float(coords_list[-1][1]))
        
        # Check if endpoints connect to FOSCs
        start_connected_to_fosc = False
        end_connected_to_fosc = False
        
        for fosc_id, fosc_pos in fosc_positions.items():
            dist_start = euclidean_distance(start_point[0], start_point[1], fosc_pos[0], fosc_pos[1])
            dist_end = euclidean_distance(end_point[0], end_point[1], fosc_pos[0], fosc_pos[1])
            
            if dist_start < tolerance_m:
                start_connected_to_fosc = True
            if dist_end < tolerance_m:
                end_connected_to_fosc = True
        
        # Check if endpoints are shared with other cables
        start_rounded = (
            round(start_point[0] / grid_size) * grid_size,
            round(start_point[1] / grid_size) * grid_size
        )
        end_rounded = (
            round(end_point[0] / grid_size) * grid_size,
            round(end_point[1] / grid_size) * grid_size
        )
        
        # Count how many OTHER cables share these endpoints
        cables_at_start = [c for c in cable_endpoints.get(start_rounded, []) if c != feature]
        cables_at_end = [c for c in cable_endpoints.get(end_rounded, []) if c != feature]
        
        start_shared_with_other = len(cables_at_start) > 0
        end_shared_with_other = len(cables_at_end) > 0
        
        # Also check if cable has UNKNOWN endpoints (indicates isolation)
        from_id = props.get("from_id", "")
        to_id = props.get("to_id", "")
        has_unknown = "UNKNOWN" in cable_id or from_id == "UNKNOWN" or to_id == "UNKNOWN"
        
        # Cable is isolated if:
        # 1. Neither endpoint connects to FOSC AND neither endpoint is shared with other cables
        # OR
        # 2. Has UNKNOWN endpoint(s) - one end may connect but other doesn't
        # OR
        # 3. Has From_ID/To_ID but those FOSCs don't exist or aren't at endpoints (phase3d issue)
        has_unknown_endpoint = (
            from_id == "UNKNOWN" or to_id == "UNKNOWN" or 
            "UNKNOWN" in cable_id
        )
        
        # Check if cable has From_ID/To_ID but endpoints aren't actually connected
        # This catches phase3d issues where IDs are assigned but FOSCs don't exist
        has_from_to_ids = props.get("From_ID") or props.get("To_ID") or from_id or to_id
        from_to_but_not_connected = False
        if has_from_to_ids and not has_unknown_endpoint:
            # Has IDs but neither endpoint connects to FOSC or other cables
            if not start_connected_to_fosc and not start_shared_with_other and \
               not end_connected_to_fosc and not end_shared_with_other:
                from_to_but_not_connected = True
        
        # Check if UNKNOWN endpoint is actually isolated
        if has_unknown_endpoint:
            # If FROM is UNKNOWN, check if start point is isolated
            if from_id == "UNKNOWN" or (cable_id.split("/")[1] if "/" in cable_id else "") == "UNKNOWN":
                start_is_isolated = not start_connected_to_fosc and not start_shared_with_other
            else:
                start_is_isolated = False
            
            # If TO is UNKNOWN, check if end point is isolated
            if to_id == "UNKNOWN" or (cable_id.split("/")[2] if len(cable_id.split("/")) >= 3 else "") == "UNKNOWN":
                end_is_isolated = not end_connected_to_fosc and not end_shared_with_other
            else:
                end_is_isolated = False
            
            # Cable with UNKNOWN is isolated if the UNKNOWN endpoint is isolated
            is_isolated = start_is_isolated or end_is_isolated
        else:
            # No UNKNOWN - check if both endpoints are isolated
            # Also check if cable has From_ID/To_ID but those FOSCs don't exist at endpoints
            # This catches phase3d issues where IDs are assigned but FOSCs aren't actually there
            has_from_to_ids = props.get("From_ID") or props.get("To_ID")
            if has_from_to_ids:
                # Has From_ID/To_ID - check if endpoints actually connect
                # If neither endpoint connects to FOSC or other cables, it's isolated
                # (even though it has IDs, those IDs may not correspond to actual FOSCs)
                is_isolated = (
                    not start_connected_to_fosc and 
                    not end_connected_to_fosc and
                    not start_shared_with_other and
                    not end_shared_with_other
                )
            else:
                # No From_ID/To_ID - standard isolation check
                is_isolated = (
                    not start_connected_to_fosc and 
                    not end_connected_to_fosc and
                    not start_shared_with_other and
                    not end_shared_with_other
                )
        
        if is_isolated:
            isolated_cables.append({
                "feature": feature,
                "cable_id": cable_id,
                "start_point": start_point,
                "end_point": end_point,
                "coordinates": coords_list,
                "has_unknown": has_unknown
            })
    
    print(f"    Found {len(isolated_cables)} isolated cables")
    for iso in isolated_cables:
        print(f"      - {iso['cable_id']}")
    
    return isolated_cables


def extract_fosc_positions_from_cable_ids(
    cables_geojson: Dict[str, Any]
) -> Dict[str, Tuple[float, float]]:
    """
    Extract FOSC positions from cable IDs.
    
    If a cable has ID like "48FOC/F1000390/F1000502", F1000390 is a FOSC ID
    and its position is at the start point of that cable.
    
    Returns:
        Dictionary mapping FOSC ID to position
    """
    fosc_positions = {}
    
    for feature in cables_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        if not cable_id or "/" not in cable_id:
            continue
        
        parts = cable_id.split("/")
        if len(parts) >= 3:
            from_id = parts[1]
            to_id = parts[2]
            
            # Extract coordinates
            coords_list = []
            if geometry.get("type") == "LineString":
                coords_list = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiLineString":
                lines = geometry.get("coordinates", [])
                if lines and len(lines) > 0:
                    first_line = lines[0]
                    if first_line and len(first_line) > 0:
                        coords_list = first_line
            
            if len(coords_list) >= 2:
                # Handle nested coordinates (MultiLineString can have nested lists)
                start_coord = coords_list[0]
                end_coord = coords_list[-1]
                
                # Unwrap if nested
                if isinstance(start_coord[0], list):
                    start_coord = start_coord[0]
                if isinstance(end_coord[0], list):
                    end_coord = end_coord[0]
                
                start_point = (float(start_coord[0]), float(start_coord[1]))
                end_point = (float(end_coord[0]), float(end_coord[1]))
                
                # If FROM is a FOSC ID (starts with F), use start point
                if from_id.startswith("F") and from_id != "UNKNOWN":
                    fosc_positions[from_id] = start_point
                
                # If TO is a FOSC ID (starts with F), use end point
                if to_id.startswith("F") and to_id != "UNKNOWN":
                    fosc_positions[to_id] = end_point
    
    return fosc_positions


def extract_cable_size(cable_id: str) -> Optional[int]:
    """
    Extract cable size (fiber count) from cable ID.
    
    Examples:
        "48FOC/F1000390/F1000502" -> 48
        "144FOC/UNKNOWN/T0000003" -> 144
        "12FOC/F1000397/T1001719" -> 12
    
    Returns:
        Fiber count as integer, or None if not found
    """
    if not cable_id or "/" not in cable_id:
        return None
    
    parts = cable_id.split("/")
    if len(parts) >= 1:
        size_part = parts[0]  # e.g., "48FOC" or "144FOC"
        # Extract number before "FOC"
        if "FOC" in size_part:
            try:
                size_str = size_part.split("FOC")[0]
                return int(size_str)
            except (ValueError, IndexError):
                pass
    
    return None


def detect_loop_enhanced(
    cables_geojson: Dict[str, Any],
    isolated_cable_id: str,
    connection_point: Tuple[float, float],
    target_cable_id: str,
    tolerance_m: float = 50.0
) -> bool:
    """
    Detect if connecting the isolated cable would create a loop/square.
    
    A loop is detected if connecting would create a closed path through cables.
    This happens when:
    - Multiple cables form a closed polygon
    - The isolated cable would complete a square/rectangle
    - Example: 96FOC/UNKNOWN/T0000005 + 48FOC/T0000005/UNKNOWN + 48FOC/F1000406/F1000394 = loop
    
    Returns:
        True if connection would create a loop, False otherwise
    """
    from utils.spatial_utils import euclidean_distance
    
    # Build endpoint map for all cables (including isolated cable for full network check)
    endpoint_to_cables = defaultdict(list)
    cable_endpoints = {}  # cable_id -> (start, end)
    
    for feature in cables_geojson.get("features", []):
        props = feature.get("properties", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        geometry = feature.get("geometry", {})
        coords = []
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                if line and len(line) > 0:
                    coords.extend(line)
        
        if len(coords) < 2:
            continue
        
        # Handle nested coordinates
        start = coords[0]
        end = coords[-1]
        if isinstance(start, list) and len(start) > 0:
            if isinstance(start[0], list):
                start = start[0]
        if isinstance(end, list) and len(end) > 0:
            if isinstance(end[0], list):
                end = end[0]
        
        start = tuple(start[:2]) if isinstance(start, list) else tuple(start[:2])
        end = tuple(end[:2]) if isinstance(end, list) else tuple(end[:2])
        
        # Round to tolerance precision for matching
        start_key = (round(start[0] / tolerance_m) * tolerance_m, round(start[1] / tolerance_m) * tolerance_m)
        end_key = (round(end[0] / tolerance_m) * tolerance_m, round(end[1] / tolerance_m) * tolerance_m)
        
        endpoint_to_cables[start_key].append(cable_id)
        endpoint_to_cables[end_key].append(cable_id)
        cable_endpoints[cable_id] = (start_key, end_key)
    
    # Get isolated cable endpoints
    isolated_feature = next((f for f in cables_geojson.get("features", []) 
                            if (f.get("properties", {}).get("ID") or f.get("properties", {}).get("id", "")) == isolated_cable_id), None)
    if not isolated_feature:
        return False
    
    geom = isolated_feature.get("geometry", {})
    iso_coords = []
    if geom.get("type") == "LineString":
        iso_coords = geom.get("coordinates", [])
    elif geom.get("type") == "MultiLineString":
        for line in geom.get("coordinates", []):
            if line and len(line) > 0:
                iso_coords.extend(line)
    
    if len(iso_coords) < 2:
        return False
    
    # Handle nested coordinates
    iso_start = iso_coords[0]
    iso_end = iso_coords[-1]
    if isinstance(iso_start, list) and len(iso_start) > 0:
        if isinstance(iso_start[0], list):
            iso_start = iso_start[0]
    if isinstance(iso_end, list) and len(iso_end) > 0:
        if isinstance(iso_end[0], list):
            iso_end = iso_end[0]
    
    iso_start = tuple(iso_start[:2]) if isinstance(iso_start, list) else tuple(iso_start[:2])
    iso_end = tuple(iso_end[:2]) if isinstance(iso_end, list) else tuple(iso_end[:2])
    iso_start_key = (round(iso_start[0] / tolerance_m) * tolerance_m, round(iso_start[1] / tolerance_m) * tolerance_m)
    iso_end_key = (round(iso_end[0] / tolerance_m) * tolerance_m, round(iso_end[1] / tolerance_m) * tolerance_m)
    
    conn_key = (round(connection_point[0] / tolerance_m) * tolerance_m, round(connection_point[1] / tolerance_m) * tolerance_m)
    
    # Check if connection point is near isolated cable endpoint
    iso_conn_endpoint = None
    if euclidean_distance(conn_key[0], conn_key[1], iso_start_key[0], iso_start_key[1]) < tolerance_m:
        iso_conn_endpoint = iso_start_key
    elif euclidean_distance(conn_key[0], conn_key[1], iso_end_key[0], iso_end_key[1]) < tolerance_m:
        iso_conn_endpoint = iso_end_key
    
    # Check if connection point is near target cable endpoint
    if target_cable_id in cable_endpoints:
        target_start, target_end = cable_endpoints[target_cable_id]
        target_conn_endpoint = None
        if euclidean_distance(conn_key[0], conn_key[1], target_start[0], target_start[1]) < tolerance_m:
            target_conn_endpoint = target_start
        elif euclidean_distance(conn_key[0], conn_key[1], target_end[0], target_end[1]) < tolerance_m:
            target_conn_endpoint = target_end
        
        # If both isolated and target cables connect at the same point, check for loop
        if iso_conn_endpoint and target_conn_endpoint and iso_conn_endpoint == target_conn_endpoint:
            # Both cables share an endpoint at connection point - check if this creates a loop
            # A loop exists if we can trace a path from the other endpoint of isolated cable
            # to the other endpoint of target cable through existing cables
            other_iso_endpoint = iso_end_key if iso_conn_endpoint == iso_start_key else iso_start_key
            other_target_endpoint = target_end if target_conn_endpoint == target_start else target_start
            
            # Check if there's a path from other_iso_endpoint to other_target_endpoint
            # through existing cables (BFS traversal)
            visited = set()
            queue = [other_iso_endpoint]
            visited.add(other_iso_endpoint)
            
            while queue:
                current = queue.pop(0)
                if current == other_target_endpoint:
                    # Found a path - this would create a loop
                    return True
                
                # Check all cables at this endpoint (except the ones we're connecting)
                for cable_id_at_endpoint in endpoint_to_cables.get(current, []):
                    if cable_id_at_endpoint == target_cable_id or cable_id_at_endpoint == isolated_cable_id:
                        continue
                    if cable_id_at_endpoint in cable_endpoints:
                        t_start, t_end = cable_endpoints[cable_id_at_endpoint]
                        next_endpoint = t_end if current == t_start else t_start
                        if next_endpoint not in visited:
                            visited.add(next_endpoint)
                            queue.append(next_endpoint)
    
    return False


def convert_wgs84_to_utm_coords(lon: float, lat: float, utm_zone: int = 17) -> Tuple[float, float]:
    """
    Convert WGS84 (lon, lat) to UTM Zone 17N coordinates.
    
    Args:
        lon: Longitude in degrees
        lat: Latitude in degrees
        utm_zone: UTM zone (default 17)
    
    Returns:
        (easting, northing) in UTM meters
    """
    try:
        import pyproj
        wgs84 = pyproj.Proj(proj='latlong', ellps='WGS84')
        utm = pyproj.Proj(proj='utm', zone=utm_zone, ellps='WGS84')
        easting, northing = pyproj.transform(wgs84, utm, lon, lat)
        return easting, northing
    except ImportError:
        # Fallback: approximate conversion (less accurate)
        # This is a rough approximation - should use pyproj for accuracy
        import math
        # Approximate conversion for Zone 17N (Ontario)
        # Center: ~45.7°N, -82°W
        # 1 degree lat ≈ 111,000m
        # 1 degree lon ≈ 78,000m at 45.7°N
        center_lat = 45.7
        center_lon = -82.0
        
        # Rough conversion
        northing = 5000000 + (lat - center_lat) * 111000.0
        easting = 500000 + (lon - center_lon) * (111000.0 * math.cos(math.radians(center_lat)))
        
        return easting, northing


def check_near_infrastructure(
    connection_point: Tuple[float, float],
    isolated_endpoint: Tuple[float, float],
    cables_geojson: Dict[str, Any],
    max_distance_m: float = 50.0,  # Stricter: 50m instead of 100m
    path_alignment_threshold: float = 0.8  # 80% of path must be near infrastructure
) -> Tuple[bool, float, float]:
    """
    Check if connection path follows existing infrastructure cables (roads for mounting).
    
    The ENTIRE connection path should follow existing infrastructure cables so the cable
    can be mounted on poles/structures along the road. This prevents cross-country routing.
    
    Args:
        connection_point: Where to connect
        isolated_endpoint: Isolated cable endpoint
        cables_geojson: All infrastructure cables (representing roads/paths)
        max_distance_m: Maximum distance from infrastructure (default 50m - stricter)
        path_alignment_threshold: Minimum fraction of path that must be near infrastructure (default 0.8 = 80%)
    
    Returns:
        (is_near_infrastructure, min_distance_to_infrastructure, path_alignment_ratio)
        - is_near_infrastructure: True if path follows infrastructure
        - min_distance_to_infrastructure: Minimum distance to nearest infrastructure
        - path_alignment_ratio: Fraction of path that is near infrastructure (0.0 to 1.0)
    """
    import math
    from utils.spatial_utils import euclidean_distance, point_to_linestring_distance, point_to_line_distance
    
    # Calculate connection path length
    path_length = euclidean_distance(
        isolated_endpoint[0], isolated_endpoint[1],
        connection_point[0], connection_point[1]
    )
    
    if path_length < 10.0:  # Very short paths are always OK
        return True, 0.0, 1.0
    
    # Sample points along the connection path to check alignment
    # Sample every 50m along the path
    sample_interval_m = 50.0
    num_samples = max(3, int(path_length / sample_interval_m) + 1)  # At least 3 samples
    
    samples_near_infrastructure = 0
    min_dist_to_infrastructure = float('inf')
    total_alignment_distance = 0.0
    
    # Build infrastructure cable list once
    # Check if roads are in WGS84 (lat/lon) and need conversion to UTM
    roads_crs = cables_geojson.get("crs", {})
    roads_crs_name = ""
    if isinstance(roads_crs, dict):
        roads_crs_name = roads_crs.get("properties", {}).get("name", "")
    elif isinstance(roads_crs, str):
        roads_crs_name = roads_crs
    
    is_wgs84 = "4326" in roads_crs_name or "WGS84" in roads_crs_name.upper() or "latlong" in roads_crs_name.lower() or "EPSG:4326" in roads_crs_name
    is_utm = "32617" in roads_crs_name or "UTM" in roads_crs_name.upper() or "EPSG:32617" in roads_crs_name
    
    # If roads are in WGS84, we need to convert them to UTM for comparison
    # Connection point and isolated_endpoint are in UTM, so we need to convert roads
    needs_conversion = is_wgs84 and not is_utm
    
    # Find roads that the connection path should follow
    # The path from isolated_endpoint to connection_point should follow a road
    # Prioritize roads that are along the path, not just nearby
    
    infrastructure_cables = []
    for feature in cables_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        coords = []
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                if line and len(line) > 0:
                    coords.extend(line)
        
        if len(coords) < 2:
            continue
        
        # Convert to tuples, handling coordinate conversion if needed
        cable_coords_tuples = []
        for c in coords:
            if isinstance(c, list) and len(c) >= 2:
                if isinstance(c[0], list):
                    x, y = float(c[0][0]), float(c[0][1])
                else:
                    x, y = float(c[0]), float(c[1])
            else:
                continue
            
            # Convert from WGS84 (lat/lon) to UTM Zone 17N if needed
            if needs_conversion:
                # OSM/GeoJSON WGS84 coordinates are (lon, lat)
                # Check if values look like lat/lon (reasonable ranges)
                if -180 <= x <= 180 and -90 <= y <= 90:
                    # Looks like (lon, lat) - swap if needed
                    # Actually, GeoJSON spec says [lon, lat] for coordinates
                    lon, lat = x, y
                elif -90 <= x <= 90 and -180 <= y <= 180:
                    # Looks like (lat, lon) - swap
                    lat, lon = x, y
                else:
                    # Can't determine - assume already UTM
                    cable_coords_tuples.append((x, y))
                    continue
                
                # Convert to UTM
                x_utm, y_utm = convert_wgs84_to_utm_coords(lon, lat, utm_zone=17)
                cable_coords_tuples.append((x_utm, y_utm))
            else:
                # Already in UTM
                cable_coords_tuples.append((x, y))
        
        if len(cable_coords_tuples) >= 2:
            infrastructure_cables.append(cable_coords_tuples)
    
    # Calculate connection path direction vector
    path_dx = connection_point[0] - isolated_endpoint[0]
    path_dy = connection_point[1] - isolated_endpoint[1]
    path_length_vec = math.sqrt(path_dx**2 + path_dy**2)
    if path_length_vec > 0:
        path_dir_normalized = (path_dx / path_length_vec, path_dy / path_length_vec)
    else:
        path_dir_normalized = (0.0, 0.0)
    
    # Sample points along the connection path
    for i in range(num_samples):
        # Interpolate point along path
        t = i / (num_samples - 1) if num_samples > 1 else 0.0
        sample_x = isolated_endpoint[0] + t * (connection_point[0] - isolated_endpoint[0])
        sample_y = isolated_endpoint[1] + t * (connection_point[1] - isolated_endpoint[1])
        sample_point = (sample_x, sample_y)
        
        # Find minimum distance to any infrastructure cable AND check direction alignment
        sample_min_dist = float('inf')
        best_alignment = 0.0  # Dot product of direction vectors (1.0 = parallel, 0.0 = perpendicular)
        
        for cable_coords in infrastructure_cables:
            dist_to_line, nearest_point_on_cable = point_to_linestring_distance(sample_point, cable_coords)
            
            if dist_to_line < sample_min_dist:
                sample_min_dist = dist_to_line
                
                # Check if path direction aligns with cable direction
                # Find the cable segment nearest to sample point
                if len(cable_coords) >= 2:
                    # Find nearest segment
                    nearest_seg_idx = 0
                    min_seg_dist = float('inf')
                    for seg_idx in range(len(cable_coords) - 1):
                        seg_start = cable_coords[seg_idx]
                        seg_end = cable_coords[seg_idx + 1]
                        seg_dist = point_to_line_distance(sample_point, seg_start, seg_end)
                        if seg_dist < min_seg_dist:
                            min_seg_dist = seg_dist
                            nearest_seg_idx = seg_idx
                    
                    # Calculate cable segment direction
                    seg_start = cable_coords[nearest_seg_idx]
                    seg_end = cable_coords[nearest_seg_idx + 1]
                    cable_dx = seg_end[0] - seg_start[0]
                    cable_dy = seg_end[1] - seg_start[1]
                    cable_length = math.sqrt(cable_dx**2 + cable_dy**2)
                    
                    if cable_length > 0:
                        cable_dir_normalized = (cable_dx / cable_length, cable_dy / cable_length)
                        # Dot product: 1.0 = parallel, 0.0 = perpendicular, -1.0 = opposite
                        alignment = abs(path_dir_normalized[0] * cable_dir_normalized[0] + 
                                      path_dir_normalized[1] * cable_dir_normalized[1])
                        if alignment > best_alignment:
                            best_alignment = alignment
        
        # Update global minimum
        if sample_min_dist < min_dist_to_infrastructure:
            min_dist_to_infrastructure = sample_min_dist
        
        # Check if this sample is near infrastructure AND direction aligns
        # Require both: close distance AND similar direction (alignment > 0.5 = within 60 degrees)
        # CRITICAL: Also check if the road segment is actually along the path (not just nearby)
        # This ensures we follow roads like Grimsthorpe Road, not just any nearby road
        is_along_path = False
        if sample_min_dist <= max_distance_m and best_alignment > 0.5:
            # Check if the nearest road segment is actually along the connection path
            # by checking if the road segment overlaps with the path
            path_vec = (connection_point[0] - isolated_endpoint[0], 
                       connection_point[1] - isolated_endpoint[1])
            path_len = math.sqrt(path_vec[0]**2 + path_vec[1]**2)
            if path_len > 0:
                path_unit = (path_vec[0] / path_len, path_vec[1] / path_len)
                
                # Check if sample point is along the path
                to_sample = (sample_point[0] - isolated_endpoint[0],
                            sample_point[1] - isolated_endpoint[1])
                projection = to_sample[0] * path_unit[0] + to_sample[1] * path_unit[1]
                
                # Sample should be along the path (not beyond endpoints)
                if 0 <= projection <= path_len:
                    # Check if road segment itself overlaps with path
                    # Project road segment endpoints onto path
                    if len(best_road_segment) >= 2:
                        road_start = best_road_segment[0]
                        road_end = best_road_segment[-1]
                        
                        # Project road endpoints onto path direction
                        to_road_start = (road_start[0] - isolated_endpoint[0],
                                       road_start[1] - isolated_endpoint[1])
                        to_road_end = (road_end[0] - isolated_endpoint[0],
                                     road_end[1] - isolated_endpoint[1])
                        
                        proj_start = to_road_start[0] * path_unit[0] + to_road_start[1] * path_unit[1]
                        proj_end = to_road_end[0] * path_unit[0] + to_road_end[1] * path_unit[1]
                        
                        # Road should overlap with path segment
                        # Check if road segment intersects the path (not just nearby)
                        road_proj_min = min(proj_start, proj_end)
                        road_proj_max = max(proj_start, proj_end)
                        
                        # Road overlaps path if projections intersect
                        if not (road_proj_max < 0 or road_proj_min > path_len):
                            is_along_path = True
        
        # Count sample as following roads if: close, aligned, and along path
        if sample_min_dist <= max_distance_m and best_alignment > 0.5 and is_along_path:
            samples_near_infrastructure += 1
            # Accumulate aligned distance (approximate)
            total_alignment_distance += path_length / num_samples
    
    # Calculate alignment ratio
    path_alignment_ratio = samples_near_infrastructure / num_samples if num_samples > 0 else 0.0
    
    # Path is "near infrastructure" if:
    # 1. At least path_alignment_threshold (80%) of samples are near infrastructure
    # 2. AND the minimum distance is reasonable
    is_near = (path_alignment_ratio >= path_alignment_threshold) and (min_dist_to_infrastructure <= max_distance_m * 2)
    
    return is_near, min_dist_to_infrastructure, path_alignment_ratio


def calculate_path_metrics_from_olt(
    isolated_cable_id: str,
    connection_point: Tuple[float, float],
    target_cable_id: str,
    cables_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]] = None,
    olts: List[Dict[str, Any]] = None,
    isolated_endpoint: Tuple[float, float] = None,
    roads_geojson: Dict[str, Any] = None  # NEW: Optional road layer
) -> Dict[str, Any]:
    """
    Calculate path metrics from OLT to the connection point.
    
    Returns metrics including:
    - Distance along fiber cable path from nearest OLT
    - Number of FOSCs crossed
    - Number of terminals crossed
    - Whether connection path is near infrastructure (for mounting)
    
    Returns:
        Dictionary with metrics: {distance_m, fosc_count, terminal_count, path_length, near_infrastructure}
    """
    from utils.spatial_utils import euclidean_distance
    
    # Find nearest OLT
    nearest_olt = None
    min_olt_dist = float('inf')
    
    if olts and len(olts) > 0:
        for olt in olts:
            olt_pos = olt.get("position")
            if olt_pos:
                # Handle both tuple and list formats
                if isinstance(olt_pos, tuple):
                    olt_pos_utm = olt_pos
                elif isinstance(olt_pos, list):
                    if len(olt_pos) >= 2:
                        olt_pos_utm = (float(olt_pos[0]), float(olt_pos[1]))
                    else:
                        continue
                else:
                    continue
                
                dist = euclidean_distance(
                    connection_point[0], connection_point[1],
                    olt_pos_utm[0], olt_pos_utm[1]
                )
                if dist < min_olt_dist:
                    min_olt_dist = dist
                    nearest_olt = olt
    
    # Count FOSCs and terminals near the connection point (within 50m)
    fosc_count = 0
    terminal_count = 0
    
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            dist = euclidean_distance(
                connection_point[0], connection_point[1],
                fosc_pos_utm[0], fosc_pos_utm[1]
            )
            if dist < 50.0:
                fosc_count += 1
    
    if terminals:
        for terminal in terminals:
            term_pos = terminal.get("position")
            if term_pos:
                term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
                dist = euclidean_distance(
                    connection_point[0], connection_point[1],
                    term_pos_utm[0], term_pos_utm[1]
                )
                if dist < 50.0:
                    terminal_count += 1
    
    # Check if connection path is near infrastructure (for mounting)
    # Use roads if available, otherwise fall back to cables as proxy
    near_infrastructure = True  # Default to True if we can't check
    infrastructure_distance = 0.0
    path_alignment_ratio = 1.0
    if isolated_endpoint:
        # Prefer roads over cables for infrastructure check
        # roads_geojson is passed as parameter, may be None
        infrastructure_source = roads_geojson if roads_geojson is not None else cables_geojson
        if infrastructure_source:
            near_infrastructure, infrastructure_distance, path_alignment_ratio = check_near_infrastructure(
                connection_point, isolated_endpoint, infrastructure_source, max_distance_m=50.0, path_alignment_threshold=0.8
            )
    
    # Estimate path length along cables (simplified - use straight line distance from OLT)
    path_length = min_olt_dist if nearest_olt else float('inf')
    
    return {
        "distance_from_olt_m": min_olt_dist if nearest_olt else None,
        "fosc_count": fosc_count,
        "terminal_count": terminal_count,
        "path_length_m": path_length,
        "total_crossings": fosc_count + terminal_count,
        "near_infrastructure": near_infrastructure,
        "infrastructure_distance_m": infrastructure_distance,
        "path_alignment_ratio": path_alignment_ratio  # Fraction of path following infrastructure (0.0 to 1.0)
    }


def find_nearest_connection_point(
    isolated_cable: Dict[str, Any],
    all_cables: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables_geojson: Dict[str, Any] = None,
    tolerance_m: float = 1000.0,
    terminals: List[Dict[str, Any]] = None,
    olts: List[Dict[str, Any]] = None,
    roads_geojson: Dict[str, Any] = None  # NEW: Optional road layer
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[float, float]], str, Tuple[float, float]]:
    """
    Find the nearest cable or FOSC to connect the isolated cable to.
    
    Also checks cable IDs for FOSC references (e.g., F1000390 in cable ID).
    
    If cable has UNKNOWN endpoint, prioritize connecting from that endpoint.
    
    Returns:
        (target_element, connection_point, element_type, iso_endpoint_to_use)
        element_type: 'cable', 'fosc', or 'fosc_from_cable_id'
    """
    iso_start = isolated_cable["start_point"]
    iso_end = isolated_cable["end_point"]
    iso_coords = isolated_cable["coordinates"]
    cable_id = isolated_cable["cable_id"]
    has_unknown = isolated_cable.get("has_unknown", False)
    
    # Determine which endpoint to prioritize
    # If cable has UNKNOWN, prefer connecting from the UNKNOWN endpoint
    props = isolated_cable["feature"].get("properties", {})
    from_id = props.get("from_id", "")
    to_id = props.get("to_id", "")
    
    # Parse cable ID to find UNKNOWN
    iso_points = []
    if "UNKNOWN" in cable_id:
        parts = cable_id.split("/")
        if len(parts) >= 3:
            if parts[1] == "UNKNOWN":
                # UNKNOWN is at start - prioritize start point
                iso_points = [iso_start, iso_end]  # Try start first
            elif parts[2] == "UNKNOWN":
                # UNKNOWN is at end - prioritize end point
                iso_points = [iso_end, iso_start]  # Try end first
            else:
                iso_points = [iso_start, iso_end]
        else:
            iso_points = [iso_start, iso_end]
    else:
        # No UNKNOWN - try both endpoints
        iso_points = [iso_start, iso_end]
    
    min_dist = float('inf')
    best_target = None
    best_connection_point = None
    best_type = None
    best_iso_point = None
    
    # Extract FOSC positions from cable IDs (e.g., F1000390 from cable IDs)
    fosc_positions_from_cables = {}
    if cables_geojson:
        fosc_positions_from_cables = extract_fosc_positions_from_cable_ids(cables_geojson)
    
    # Get FOSC IDs that are already at the isolated cable endpoints (don't connect to these)
    excluded_fosc_ids = set()
    if from_id and from_id.startswith("F"):
        excluded_fosc_ids.add(from_id)
    if to_id and to_id.startswith("F"):
        excluded_fosc_ids.add(to_id)
    # Also check cable ID parts
    if "/" in cable_id:
        parts = cable_id.split("/")
        if len(parts) >= 3:
            if parts[1].startswith("F") and parts[1] != "UNKNOWN":
                excluded_fosc_ids.add(parts[1])
            if parts[2].startswith("F") and parts[2] != "UNKNOWN":
                excluded_fosc_ids.add(parts[2])
    
    # Check FOSCs from FOSC list first (prefer FOSC over cable)
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_id = fosc.get("fosc_id", "")
            
            # Skip if this FOSC is already at an endpoint of the isolated cable
            if fosc_id in excluded_fosc_ids:
                continue
            
            for iso_point in iso_points:
                dist = euclidean_distance(iso_point[0], iso_point[1], fosc_pos_utm[0], fosc_pos_utm[1])
                if dist < min_dist and dist < tolerance_m:
                    min_dist = dist
                    best_target = {"fosc_id": fosc_id, "position": fosc_pos_utm}
                    best_connection_point = fosc_pos_utm
                    best_type = "fosc"
                    best_iso_point = iso_point
    
    # Check FOSCs extracted from cable IDs (e.g., F1000390)
    # Store all FOSC candidates for evaluation (not just the nearest)
    fosc_candidates = []
    
    for fosc_id, fosc_pos in fosc_positions_from_cables.items():
        # Skip if this FOSC is already at an endpoint of the isolated cable
        if fosc_id in excluded_fosc_ids:
            continue
        
        for iso_point in iso_points:
            dist = euclidean_distance(iso_point[0], iso_point[1], fosc_pos[0], fosc_pos[1])
            if dist < tolerance_m:
                # Check if this FOSC connection would create a loop
                # Find the cable that defines this FOSC position
                fosc_cable_id = None
                for feat in (cables_geojson.get("features", []) if cables_geojson else []):
                    feat_props = feat.get("properties", {})
                    feat_id = feat_props.get("ID") or feat_props.get("id", "")
                    if fosc_id in feat_id:
                        fosc_cable_id = feat_id
                        break
                
                would_loop = False
                if cables_geojson and fosc_cable_id:
                    would_loop = detect_loop_enhanced(cables_geojson, cable_id, fosc_pos, fosc_cable_id, tolerance_m)
                
                if not would_loop:
                    # Calculate path metrics
                    metrics = calculate_path_metrics_from_olt(
                        cable_id, fosc_pos, fosc_cable_id or "",
                        cables_geojson or {"features": all_cables},
                        foscs, terminals, olts,
                        isolated_endpoint=iso_point,
                        roads_geojson=roads_geojson  # Pass roads for accurate alignment check
                    )
                    
                    fosc_candidates.append({
                        "fosc_id": fosc_id,
                        "position": fosc_pos,
                        "iso_point": iso_point,
                        "distance": dist,
                        "metrics": metrics,
                        "from_cable_id": True,
                        "target_cable_id": fosc_cable_id
                    })
    
    # Find best FOSC from candidates
    best_fosc_from_id = None
    best_fosc_dist = float('inf')
    best_fosc_point = None
    if fosc_candidates:
        # Sort by: 1) path length from OLT, 2) total crossings, 3) distance
        fosc_candidates.sort(key=lambda x: (
            x["metrics"]["path_length_m"] if x["metrics"]["path_length_m"] != float('inf') else 999999,
            x["metrics"]["total_crossings"],
            x["distance"]
        ))
        best_fosc_candidate = fosc_candidates[0]
        best_fosc_from_id = {"fosc_id": best_fosc_candidate["fosc_id"], "position": best_fosc_candidate["position"], "from_cable_id": True}
        best_fosc_dist = best_fosc_candidate["distance"]
        best_fosc_point = best_fosc_candidate["iso_point"]
    
    # Extract isolated cable size for size-based filtering
    isolated_cable_size = extract_cable_size(cable_id)
    
    # Check other cables - only consider cables with size >= isolated cable size
    # Also evaluate path metrics to avoid loops and minimize path length
    best_cable_dist = float('inf')
    best_cable_target = None
    best_cable_point = None
    best_cable_connection = None
    best_cable_metrics = None
    candidate_connections = []  # Store all valid candidates for evaluation
    
    for cable_feat in all_cables:
        if cable_feat == isolated_cable["feature"]:
            continue
        
        # Check cable size constraint: target cable must be >= isolated cable size
        target_cable_id = cable_feat.get("properties", {}).get("ID") or cable_feat.get("properties", {}).get("id", "")
        if isolated_cable_size is not None and target_cable_id:
            target_cable_size = extract_cable_size(target_cable_id)
            if target_cable_size is not None:
                # Only consider cables where target_size >= isolated_size
                # This ensures we don't connect larger cables to smaller infrastructure cables
                if target_cable_size < isolated_cable_size:
                    continue  # Skip this cable - it's smaller than isolated cable (size constraint)
        
        geometry = cable_feat.get("geometry", {})
        cable_coords = []
        if geometry.get("type") == "LineString":
            cable_coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                if line and len(line) > 0:
                    # MultiLineString: line is a list of coordinate pairs
                    cable_coords.extend(line)
        
        if len(cable_coords) < 2:
            continue
        
        # Convert to tuples for distance calculation
        # Handle various coordinate formats: [x, y], [[x, y]], etc.
        cable_coords_tuples = []
        for c in cable_coords:
            if isinstance(c, list):
                if len(c) >= 2:
                    # Check if nested: [[x, y]]
                    if isinstance(c[0], list):
                        if len(c[0]) >= 2:
                            cable_coords_tuples.append((float(c[0][0]), float(c[0][1])))
                    else:
                        # [x, y]
                        cable_coords_tuples.append((float(c[0]), float(c[1])))
            elif isinstance(c, tuple) and len(c) >= 2:
                cable_coords_tuples.append(c)
        
        if len(cable_coords_tuples) < 2:
            continue  # Skip if we couldn't extract enough valid coordinates
        
        for iso_point in iso_points:
            nearest_point, dist = find_nearest_point_on_line(iso_point, cable_coords_tuples)
            if dist < tolerance_m:
                # Calculate path metrics from OLT (we'll filter loops later when evaluating)
                metrics = calculate_path_metrics_from_olt(
                    cable_id, nearest_point, target_cable_id,
                    cables_geojson or {"features": all_cables},
                    foscs, terminals, olts,
                    isolated_endpoint=iso_point,
                    roads_geojson=roads_geojson  # Pass roads for accurate alignment check
                )
                
                candidate_connections.append({
                    "cable_feat": cable_feat,
                    "connection_point": nearest_point,
                    "iso_point": iso_point,
                    "distance": dist,
                    "metrics": metrics,
                    "target_cable_id": target_cable_id
                })
    
    # Evaluate candidates: prefer shorter path from OLT, fewer FOSCs/terminals, avoid loops
    if candidate_connections:
        # Filter out candidates that would create loops
        valid_candidates = []
        for candidate in candidate_connections:
            if cables_geojson:
                would_loop = detect_loop_enhanced(
                    cables_geojson, cable_id, candidate["connection_point"],
                    candidate["target_cable_id"], tolerance_m
                )
                if would_loop:
                    continue  # Skip this candidate - it would create a loop
            valid_candidates.append(candidate)
        
        if not valid_candidates:
            # All candidates would create loops - use the one with best metrics anyway
            # (better than not connecting at all)
            valid_candidates = candidate_connections
        
        # Sort by: 1) path length from OLT, 2) total crossings (FOSCs + terminals), 3) distance
        valid_candidates.sort(key=lambda x: (
            x["metrics"]["path_length_m"] if x["metrics"]["path_length_m"] != float('inf') else 999999,
            x["metrics"]["total_crossings"],
            x["distance"]
        ))
        
        if valid_candidates:
            best_candidate = valid_candidates[0]
            best_cable_target = best_candidate["cable_feat"]
            best_cable_connection = best_candidate["connection_point"]
            best_cable_point = best_candidate["iso_point"]
            best_cable_dist = best_candidate["distance"]
            best_cable_metrics = best_candidate["metrics"]
    
    # Evaluate all candidates (FOSCs and cables) together based on path metrics
    all_candidates = []
    
    # Add FOSC candidates
    for fosc_cand in fosc_candidates:
        all_candidates.append({
            "type": "fosc_from_cable_id",
            "target": {"fosc_id": fosc_cand["fosc_id"], "position": fosc_cand["position"], "from_cable_id": True},
            "connection_point": fosc_cand["position"],
            "iso_point": fosc_cand["iso_point"],
            "distance": fosc_cand["distance"],
            "metrics": fosc_cand["metrics"]
        })
    
    # Add cable candidates (already filtered for loops and size)
    for cable_cand in valid_candidates if valid_candidates else []:
        all_candidates.append({
            "type": "cable",
            "target": cable_cand["cable_feat"],
            "connection_point": cable_cand["connection_point"],
            "iso_point": cable_cand["iso_point"],
            "distance": cable_cand["distance"],
            "metrics": cable_cand["metrics"]
        })
    
    # Select best candidate: minimize path from OLT, minimize crossings, avoid loops
    if all_candidates:
        # Debug: Show all candidates for isolated cable
        if len(all_candidates) > 1:
            print(f"    Evaluating {len(all_candidates)} connection candidates:")
            for i, cand in enumerate(all_candidates[:5]):  # Show top 5
                target_id = ""
                if cand["type"] == "cable":
                    target_id = cand["target"].get("properties", {}).get("ID") or cand["target"].get("properties", {}).get("id", "")
                elif cand["type"] == "fosc_from_cable_id":
                    target_id = cand["target"].get("fosc_id", "")
                
                path_str = f"{cand['metrics']['path_length_m']:.0f}m" if cand['metrics']['path_length_m'] != float('inf') else "inf"
                print(f"      {i+1}. {cand['type']}: {target_id} ({cand['distance']:.1f}m, path: {path_str}, crossings: {cand['metrics']['total_crossings']})")
        
        # Check if any candidate would create a loop - prioritize non-loop candidates
        non_loop_candidates = []
        loop_candidates = []
        
        for cand in all_candidates:
            would_loop = False
            if cables_geojson:
                target_id_for_loop = ""
                if cand["type"] == "cable":
                    target_id_for_loop = cand["target"].get("properties", {}).get("ID") or cand["target"].get("properties", {}).get("id", "")
                elif cand["type"] == "fosc_from_cable_id":
                    # Get the cable ID that defines this FOSC
                    target_id_for_loop = cand.get("target_cable_id", "")
                
                if target_id_for_loop:
                    would_loop = detect_loop_enhanced(
                        cables_geojson, cable_id, cand["connection_point"],
                        target_id_for_loop, tolerance_m
                    )
            
            if would_loop:
                loop_candidates.append(cand)
            else:
                non_loop_candidates.append(cand)
        
        # Prefer non-loop candidates, but if all create loops, use the best one anyway
        candidates_to_use = non_loop_candidates if non_loop_candidates else loop_candidates
        
        # Sort by: 1) avoid loops, 2) near infrastructure (for mounting), 3) path alignment (how much follows roads), 4) distance (closest first), 5) path length from OLT, 6) total crossings
        # CRITICAL: Prioritize connections that follow roads - reject cross-country paths
        # Priority: Closest cable that doesn't create a loop and follows roads
        # This ensures we connect to the nearest acceptable cable on a road path
        candidates_to_use.sort(key=lambda x: (
            0 if x in non_loop_candidates else 1,  # Non-loops first (avoid squares)
            0 if x["metrics"].get("near_infrastructure", True) else 1,  # Near infrastructure (roads) - CRITICAL
            1.0 - x["metrics"].get("path_alignment_ratio", 1.0),  # Higher alignment ratio first (more of path follows roads) - CRITICAL
            x["distance"],  # Closest first (but only if follows roads)
            x["metrics"]["path_length_m"] if x["metrics"]["path_length_m"] != float('inf') else 999999,  # Shorter path from OLT
            x["metrics"]["total_crossings"]  # Fewer FOSCs/terminals crossed
        ))
        
        # Filter out candidates not near infrastructure (unless all are far)
        # Require at least 80% of path to follow infrastructure
        # CRITICAL: Only accept connections that follow actual roads
        # This prevents cross-country paths like diagonal cuts across fields
        infrastructure_candidates = [c for c in candidates_to_use 
                                   if c["metrics"].get("near_infrastructure", True) and 
                                   c["metrics"].get("path_alignment_ratio", 1.0) >= 0.8]
        if infrastructure_candidates:
            candidates_to_use = infrastructure_candidates  # Only consider connections that follow roads
            print(f"    ✓ Filtered to {len(candidates_to_use)} candidates that follow roads (80%+ alignment)")
        else:
            # If no candidates follow roads, this is a problem
            # The connection would cut across fields - reject it or find alternative
            print(f"    ⚠️  CRITICAL: No candidates follow roads (80%+ alignment)")
            print(f"    ⚠️  All connections would cut across fields - not mountable")
            print(f"    ⚠️  Trying to find road-aligned alternative...")
            
            # Try to find a connection that at least partially follows roads
            # Lower threshold to 50% if no perfect solution
            partial_road_candidates = [c for c in candidates_to_use 
                                      if c["metrics"].get("near_infrastructure", True) and 
                                      c["metrics"].get("path_alignment_ratio", 1.0) >= 0.5]
            if partial_road_candidates:
                print(f"    ⚠️  Found {len(partial_road_candidates)} candidates with 50%+ road alignment")
                print(f"    ⚠️  Using best partial alignment, but may still cross fields")
                candidates_to_use = partial_road_candidates
            else:
                # No road-aligned options - this connection may not be feasible
                print(f"    ⚠️  No road-aligned options found - connection may not be mountable")
                # Still proceed but mark as problematic
        
        best_candidate = candidates_to_use[0]
        
        # Debug: Log selection
        target_id = ""
        if best_candidate["type"] == "cable":
            target_id = best_candidate["target"].get("properties", {}).get("ID") or best_candidate["target"].get("properties", {}).get("id", "")
        elif best_candidate["type"] == "fosc_from_cable_id":
            target_id = best_candidate["target"].get("fosc_id", "")
        
        path_str = f"{best_candidate['metrics']['path_length_m']:.0f}m" if best_candidate['metrics']['path_length_m'] != float('inf') else "inf"
        creates_loop = best_candidate in loop_candidates
        loop_str = " (creates loop)" if creates_loop else ""
        is_closest = best_candidate == min(candidates_to_use, key=lambda x: x["distance"]) if candidates_to_use else False
        closest_str = " [closest]" if is_closest and not creates_loop else ""
        near_infra = best_candidate["metrics"].get("near_infrastructure", True)
        alignment_ratio = best_candidate["metrics"].get("path_alignment_ratio", 1.0)
        infra_str = "" if near_infra else " [NOT following roads]"
        alignment_str = f" ({alignment_ratio*100:.0f}% on roads)" if near_infra else ""
        print(f"    Selected: {best_candidate['type']} ({best_candidate['distance']:.1f}m, path: {path_str}, crossings: {best_candidate['metrics']['total_crossings']}){loop_str}{closest_str}{infra_str}{alignment_str}")
        if target_id:
            print(f"      Target: {target_id}")
        if not near_infra or alignment_ratio < 0.8:
            infra_dist = best_candidate["metrics"].get("infrastructure_distance_m", 0)
            print(f"      ⚠️  Connection path is {infra_dist:.1f}m from nearest infrastructure, {alignment_ratio*100:.0f}% aligned (may not be mountable)")
        
        return (
            best_candidate["target"],
            best_candidate["connection_point"],
            best_candidate["type"],
            best_candidate["iso_point"]
        )
    
    # Fallback to original logic if no candidates
    if best_fosc_from_id and best_fosc_dist < tolerance_m:
        return best_fosc_from_id, best_fosc_from_id["position"], "fosc_from_cable_id", best_fosc_point
    
    # Use cable if no good FOSC found, or if FOSC is too far
    if best_cable_target:
        return best_cable_target, best_cable_connection, "cable", best_cable_point
    
    # Fallback to FOSC from list if available
    if best_target:
        return best_target, best_connection_point, best_type, best_iso_point
    
    return None, None, None, None


def find_road_path_between_points(
    start_point: Tuple[float, float],
    end_point: Tuple[float, float],
    roads_geojson: Dict[str, Any],
    max_deviation_m: float = 100.0
) -> List[Tuple[float, float]]:
    """
    Find a road path between two points.
    
    Instead of a straight line, finds roads that connect the points,
    creating a path that follows actual roads (like Grimsthorpe Road).
    
    Args:
        start_point: Starting point (UTM coordinates)
        end_point: Ending point (UTM coordinates)
        roads_geojson: Road GeoJSON (may be WGS84 or UTM)
        max_deviation_m: Maximum deviation from direct path (default 100m)
    
    Returns:
        List of (x, y) coordinates following roads, or straight line if no road path found
    """
    if not roads_geojson or not roads_geojson.get("features"):
        # No roads - return straight line
        return [list(start_point), list(end_point)]
    
    import math
    from utils.spatial_utils import euclidean_distance, point_to_linestring_distance
    
    # Check if roads need coordinate conversion
    roads_crs = roads_geojson.get("crs", {})
    roads_crs_name = ""
    if isinstance(roads_crs, dict):
        roads_crs_name = roads_crs.get("properties", {}).get("name", "")
    elif isinstance(roads_crs, str):
        roads_crs_name = roads_crs
    
    is_wgs84 = "4326" in roads_crs_name or "WGS84" in roads_crs_name.upper()
    is_utm = "32617" in roads_crs_name or "UTM" in roads_crs_name.upper()
    needs_conversion = is_wgs84 and not is_utm
    
    # Find roads near the path
    path_mid_x = (start_point[0] + end_point[0]) / 2
    path_mid_y = (start_point[1] + end_point[1]) / 2
    path_length = euclidean_distance(start_point[0], start_point[1], end_point[0], end_point[1])
    
    # Helper function to calculate perpendicular distance from point to line segment
    def point_to_line_distance(pt, line_start, line_end):
        """Calculate perpendicular distance from point to line segment."""
        x0, y0 = pt
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Vector from line_start to line_end
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            # Line segment is a point
            return math.sqrt((x0 - x1)**2 + (y0 - y1)**2)
        
        # Parameter t for closest point on line
        t = max(0, min(1, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
        
        # Closest point on line segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Distance from point to closest point
        return math.sqrt((x0 - closest_x)**2 + (y0 - closest_y)**2)
    
    # Find roads that are along the path (not just nearby)
    candidate_roads = []
    for feature in roads_geojson.get("features", []):
            geometry = feature.get("geometry", {})
            coords = []
            if geometry.get("type") == "LineString":
                coords = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiLineString":
                for line in geometry.get("coordinates", []):
                    if line and len(line) > 0:
                        coords.extend(line)
            
            if len(coords) < 2:
                continue
            
            # Convert coordinates to UTM if needed
            road_coords_utm = []
            for c in coords:
                if isinstance(c, list) and len(c) >= 2:
                    if isinstance(c[0], list):
                        x, y = float(c[0][0]), float(c[0][1])
                    else:
                        x, y = float(c[0]), float(c[1])
                else:
                    continue
                
                if needs_conversion:
                    if -180 <= x <= 180 and -90 <= y <= 90:
                        lon, lat = x, y
                        x_utm, y_utm = convert_wgs84_to_utm_coords(lon, lat, utm_zone=17)
                        road_coords_utm.append((x_utm, y_utm))
                else:
                    road_coords_utm.append((x, y))
            
            if len(road_coords_utm) < 2:
                continue
            
            # Check if this road is along the path
            # Calculate distance from path to road
            min_dist_to_path = float('inf')
            for i in range(len(road_coords_utm) - 1):
                road_seg_start = road_coords_utm[i]
                road_seg_end = road_coords_utm[i + 1]
                
                # Check distance from path midpoint to road segment
                dist_to_seg = point_to_line_distance(
                    (path_mid_x, path_mid_y),
                    road_seg_start,
                    road_seg_end
                )
                if dist_to_seg < min_dist_to_path:
                    min_dist_to_path = dist_to_seg
            
            # Road is candidate if it's near the path
            if min_dist_to_path < max_deviation_m:
                candidate_roads.append({
                    "coords": road_coords_utm,
                    "distance": min_dist_to_path,
                    "name": feature.get("properties", {}).get("name", "")
                })
    
    if not candidate_roads:
        # No roads found - return straight line
        return [list(start_point), list(end_point)]
    
    # Sort by distance (closest roads first)
    candidate_roads.sort(key=lambda x: x["distance"])
    
    # Try to build a path using the closest roads
    # For now, return the road that's closest to the path
    # In future, could do pathfinding through road network
    best_road = candidate_roads[0]
    
    # Check if road endpoints are near start/end points
    road_start = best_road["coords"][0]
    road_end = best_road["coords"][-1]
    
    dist_to_start = euclidean_distance(start_point[0], start_point[1], road_start[0], road_start[1])
    dist_to_end = euclidean_distance(end_point[0], end_point[1], road_end[0], road_end[1])
    
    # If road is close to both endpoints, use the road path
    if dist_to_start < 200.0 and dist_to_end < 200.0:
        # Road connects the points - use it
        path_coords = [list(start_point)]
        # Add road coordinates
        for coord in best_road["coords"]:
            path_coords.append(list(coord))
        path_coords.append(list(end_point))
        return path_coords
    elif dist_to_start < 200.0:
        # Road starts near start point - use road then straight line to end
        path_coords = [list(start_point)]
        for coord in best_road["coords"]:
            path_coords.append(list(coord))
        path_coords.append(list(end_point))
        return path_coords
    elif dist_to_end < 200.0:
        # Road ends near end point - straight line to road then road
        path_coords = [list(start_point)]
        for coord in best_road["coords"]:
            path_coords.append(list(coord))
        path_coords.append(list(end_point))
        return path_coords
    else:
        # Road is nearby but doesn't connect - use straight line
        return [list(start_point), list(end_point)]


def extend_cable_to_connection(
    isolated_cable: Dict[str, Any],
    connection_point: Tuple[float, float],
    iso_endpoint: Tuple[float, float],
    roads_geojson: Dict[str, Any] = None  # NEW: Optional roads for path following
) -> List[List[float]]:
    """
    Extend isolated cable to connection point, following roads if available.
    
    Instead of a straight line, finds roads that connect the points,
    creating a path that follows actual roads (like Grimsthorpe Road).
    
    Args:
        isolated_cable: Isolated cable dictionary
        connection_point: Where to connect (UTM coordinates)
        iso_endpoint: Isolated cable endpoint (UTM coordinates)
        roads_geojson: Optional road GeoJSON for path following
    
    Returns:
        List of coordinate pairs suitable for LineString geometry, following roads if possible.
    """
    coords = isolated_cable["coordinates"]
    
    # Flatten coordinates if it's from a MultiLineString
    # isolated_cable["coordinates"] is already flattened in detect_isolated_cables
    # But handle both cases for safety
    flat_coords = []
    if len(coords) > 0:
        # Check if first element is a list of lists (MultiLineString structure)
        if isinstance(coords[0], list) and len(coords[0]) > 0 and isinstance(coords[0][0], list):
            # MultiLineString: flatten all lines
            for line in coords:
                for coord in line:
                    if len(coord) >= 2:
                        flat_coords.append([float(coord[0]), float(coord[1])])
        else:
            # Already flat (LineString or already processed)
            for coord in coords:
                if len(coord) >= 2:
                    flat_coords.append([float(coord[0]), float(coord[1])])
    
    if len(flat_coords) < 2:
        # Fallback: use iso_endpoint as reference
        flat_coords = [[float(iso_endpoint[0]), float(iso_endpoint[1])]]
    
    # Determine which endpoint is closer to connection point
    start_point = (flat_coords[0][0], flat_coords[0][1])
    end_point = (flat_coords[-1][0], flat_coords[-1][1])
    
    dist_to_start = euclidean_distance(
        connection_point[0], connection_point[1],
        start_point[0], start_point[1]
    )
    dist_to_end = euclidean_distance(
        connection_point[0], connection_point[1],
        end_point[0], end_point[1]
    )
    
    # CRITICAL: If roads are available, find road path instead of straight line
    # This ensures generated cables follow roads (like Grimsthorpe Road)
    if roads_geojson:
        # Determine which endpoint to extend from
        extend_from = start_point if dist_to_start < dist_to_end else end_point
        
        # Find road path from extend_from to connection_point
        road_path = find_road_path_between_points(
            extend_from,
            connection_point,
            roads_geojson,
            max_deviation_m=100.0
        )
        
        # Combine cable coordinates with road path
        if dist_to_start < dist_to_end:
            # Extend from start - prepend road path (reverse order)
            # Road path goes from start to connection, so reverse it
            road_path_reversed = list(reversed(road_path))
            # Remove duplicate at connection point
            if len(road_path_reversed) > 1 and road_path_reversed[0] == flat_coords[0]:
                road_path_reversed = road_path_reversed[1:]
            extended_coords = road_path_reversed + flat_coords
        else:
            # Extend from end - append road path
            # Remove duplicate at connection point
            if len(road_path) > 1 and road_path[0] == flat_coords[-1]:
                road_path = road_path[1:]
            extended_coords = flat_coords + road_path
        
        return extended_coords
    
    # No roads available - use straight line (original behavior)
    # Add connection point to the appropriate end
    if dist_to_start < dist_to_end:
        # Extend from start
        flat_coords.insert(0, [float(connection_point[0]), float(connection_point[1])])
    else:
        # Extend from end
        flat_coords.append([float(connection_point[0]), float(connection_point[1])])
    
    return flat_coords


def connect_isolated_cables(
    cables_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    tolerance_m: float = 50.0,
    max_connection_distance_m: float = 3000.0,  # Increased default to 3km to handle cases like F1000390
    max_iterations: int = 5,  # Run multiple passes to catch isolated islands
    terminals: List[Dict[str, Any]] = None,
    olts: List[Dict[str, Any]] = None,
    roads_geojson: Dict[str, Any] = None  # NEW: Optional road/street layer for accurate road alignment
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Connect isolated fiber cables to the network.
    
    Runs multiple passes to catch isolated islands (groups of cables that connect
    to each other but not to the main network).
    
    Args:
        cables_geojson: Fiber cable GeoJSON
        foscs: List of FOSC dictionaries
        tolerance_m: Tolerance for detecting connections
        max_connection_distance_m: Maximum distance to extend isolated cable
        max_iterations: Maximum number of passes to run
        terminals: List of terminal dictionaries (for path metrics)
        olts: List of OLT dictionaries (for path metrics)
        roads_geojson: Optional road/street GeoJSON (for accurate road alignment check)
    
    Returns:
        (updated_cables_geojson, new_foscs, summary)
    """
    print("=" * 80)
    print("CONNECTING ISOLATED FIBER CABLES")
    print("=" * 80)
    
    current_cables = cables_geojson
    current_foscs = foscs.copy()
    all_new_foscs = []
    all_connections = []
    total_connected = 0
    iteration = 0
    
    # Run multiple passes to catch isolated islands
    while iteration < max_iterations:
        iteration += 1
        print(f"\n  Pass {iteration}:")
        
        # Detect isolated cables (including newly created ones)
        isolated_cables = detect_isolated_cables(current_cables, current_foscs, tolerance_m)
        
        if len(isolated_cables) == 0:
            print(f"    ✓ No isolated cables found - network is fully connected")
            break
        
        print(f"    Found {len(isolated_cables)} isolated cables")
        
        # Build list of all cables for distance calculations
        all_cables = []
        for feature in current_cables.get("features", []):
            all_cables.append(feature)
        
        updated_features = []
        processed_cable_ids = set()
        new_foscs_this_pass = []
        connections_this_pass = []
        target_connections_this_pass = set()  # Track which targets are being connected to (prevent loops)
        
        for isolated in isolated_cables:
            cable_id = isolated["cable_id"]
            print(f"\n  Processing isolated cable: {cable_id}")
            
            # Find nearest connection point (pass current_cables to extract FOSC positions from cable IDs)
            target, connection_point, target_type, iso_endpoint = find_nearest_connection_point(
                isolated,
                all_cables,
                current_foscs,
                current_cables,  # Pass to extract FOSC positions from cable IDs
                max_connection_distance_m,
                terminals,  # Pass terminals for path analysis
                olts,  # Pass OLTs for path analysis
                roads_geojson=roads_geojson  # Pass roads for accurate alignment check
            )
            
            # Get target ID to check for duplicate connections (would create loop)
            target_id_for_check = None
            if target_type == "cable":
                target_id_for_check = target.get("properties", {}).get("ID") or target.get("properties", {}).get("id", "")
            elif target_type == "fosc_from_cable_id":
                # Find the cable that defines this FOSC
                fosc_id = target.get("fosc_id", "")
                for feat in current_cables.get("features", []):
                    feat_props = feat.get("properties", {})
                    feat_id = feat_props.get("ID") or feat_props.get("id", "")
                    if fosc_id in feat_id:
                        target_id_for_check = feat_id
                        break
            
            # Check if another isolated cable is already connecting to this target (would create loop)
            if target_id_for_check:
                connection_key = (cable_id, target_id_for_check)
                if target_id_for_check in target_connections_this_pass:
                    print(f"    ⚠️  Skipping - another isolated cable already connecting to {target_id_for_check} (would create loop)")
                    # Keep the cable as-is (don't update)
                    for feat in current_cables.get("features", []):
                        props = feat.get("properties", {})
                        if (props.get("ID") or props.get("id", "")) == cable_id:
                            updated_features.append(feat)
                            processed_cable_ids.add(cable_id)
                            break
                    continue
                target_connections_this_pass.add(target_id_for_check)
        
            if not target or not connection_point:
                print(f"    ⚠️  No connection point found within {max_connection_distance_m}m")
                # If cable has UNKNOWN endpoint, try increasing search distance more aggressively
                if isolated.get("has_unknown", False):
                    print(f"    ⚠️  Cable has UNKNOWN endpoint - trying extended search (up to 5km)...")
                    # Try progressively larger distances
                    for multiplier in [2, 3, 5]:
                        extended_distance = max_connection_distance_m * multiplier
                        target, connection_point, target_type, iso_endpoint = find_nearest_connection_point(
                            isolated,
                            all_cables,
                            current_foscs,
                            current_cables,  # Pass to extract FOSC positions from cable IDs
                            extended_distance,
                            terminals=terminals,
                            olts=olts,
                            roads_geojson=roads_geojson  # Pass roads for accurate alignment check
                        )
                        if target and connection_point:
                            print(f"    ✓ Found connection at {extended_distance:.0f}m distance")
                            break
                    
                    if not target or not connection_point:
                        print(f"    ⚠️  No connection found even at extended distance - keeping cable as-is")
                        updated_features.append(isolated["feature"])
                        continue
                else:
                    # Keep cable as-is
                    updated_features.append(isolated["feature"])
                    continue
            
            distance = euclidean_distance(
                iso_endpoint[0], iso_endpoint[1],
                connection_point[0], connection_point[1]
            )
            
            print(f"    ✓ Found connection point: {target_type} ({distance:.1f}m away)")
            
            # Extend cable to connection point, following roads if available
            extended_coords = extend_cable_to_connection(
                isolated, 
                connection_point, 
                iso_endpoint,
                roads_geojson=roads_geojson  # Pass roads to follow road paths
            )
            
            # Update cable feature
            updated_feature = isolated["feature"].copy()
            updated_geometry = updated_feature.get("geometry", {}).copy()
            original_type = updated_geometry.get("type", "LineString")
            
            # Ensure coordinates are properly formatted
            # If original was MultiLineString, we need to convert to LineString
            # (since extended_coords is a flat list of coordinate pairs)
            if original_type == "MultiLineString":
                # Convert to LineString with proper coordinate structure
                updated_geometry["type"] = "LineString"
                # extended_coords is already a list of [x, y] pairs, which is correct for LineString
                updated_geometry["coordinates"] = extended_coords
            else:
                # LineString - extended_coords is already correct format
                updated_geometry["coordinates"] = extended_coords
            
            updated_feature["geometry"] = updated_geometry
            
            # Update properties
            updated_props = updated_feature.get("properties", {}).copy()
            updated_props["extended"] = True
            updated_props["extension_distance_m"] = distance
            updated_props["connected_to"] = target_type
            updated_feature["properties"] = updated_props
            
            updated_features.append(updated_feature)
            processed_cable_ids.add(cable_id)
            
            # Create FOSC at connection point
            # Check if target is a FOSC from cable ID (e.g., F1000390)
            if target_type == "fosc_from_cable_id":
                # Use the FOSC ID from the cable (e.g., F1000390)
                target_fosc_id = target.get("fosc_id", "")
                if target_fosc_id:
                    # Check if this FOSC already exists in the FOSC list
                    existing_fosc = next((f for f in current_foscs if f.get("fosc_id") == target_fosc_id), None)
                    if existing_fosc:
                        # Add cable to existing FOSC
                        if cable_id not in existing_fosc.get("connected_cables", []):
                            existing_fosc["connected_cables"].append(cable_id)
                        print(f"    ✓ Added cable to existing FOSC {target_fosc_id} (from cable ID)")
                        connections_this_pass.append({
                            "cable_id": cable_id,
                            "fosc_id": target_fosc_id,
                            "connection_point": connection_point,
                            "distance_m": distance,
                            "target_type": "fosc_from_cable_id",
                            "iteration": iteration
                        })
                        continue
                    else:
                        # Create new FOSC with the ID from cable
                        fosc_id = target_fosc_id
                        new_fosc = {
                            "fosc_id": fosc_id,
                            "position": connection_point,
                            "connected_cables": [cable_id],
                            "created_for": "isolated_cable_connection",
                            "connected_isolated_cable": cable_id,
                            "connection_distance_m": distance,
                            "extracted_from_cable_id": True
                        }
                        new_foscs_this_pass.append(new_fosc)
                        current_foscs.append(new_fosc)  # Add to current FOSCs for next iteration
                        connections_this_pass.append({
                            "cable_id": cable_id,
                            "fosc_id": fosc_id,
                            "connection_point": connection_point,
                            "distance_m": distance,
                            "target_type": "fosc_from_cable_id",
                            "iteration": iteration
                        })
                        print(f"    ✓ Created FOSC {fosc_id} at connection point (extracted from cable ID)")
                        continue
            
            # Generate new FOSC ID
            fosc_counter = len(current_foscs) + len(new_foscs_this_pass) + 1
            fosc_id = f"F{fosc_counter:07d}"
            
            new_fosc = {
                "fosc_id": fosc_id,
                "position": connection_point,
                "connected_cables": [cable_id],
                "created_for": "isolated_cable_connection",
                "connected_isolated_cable": cable_id,
                "connection_distance_m": distance
            }
            
            # If connecting to another cable, add that cable to connected_cables
            if target_type == "cable":
                target_cable_id = target.get("properties", {}).get("ID") or target.get("properties", {}).get("id", "")
                if target_cable_id:
                    new_fosc["connected_cables"].append(target_cable_id)
            elif target_type == "fosc":
                target_fosc_id = target.get("fosc_id", "")
                if target_fosc_id:
                    # Merge with existing FOSC instead of creating new one
                    existing_fosc = next((f for f in current_foscs if f.get("fosc_id") == target_fosc_id), None)
                    if existing_fosc:
                        if cable_id not in existing_fosc.get("connected_cables", []):
                            existing_fosc["connected_cables"].append(cable_id)
                        print(f"    ✓ Added cable to existing FOSC {target_fosc_id}")
                        connections_this_pass.append({
                            "cable_id": cable_id,
                            "fosc_id": target_fosc_id,
                            "connection_point": connection_point,
                            "distance_m": distance,
                            "target_type": target_type,
                            "iteration": iteration
                        })
                        continue
            
            new_foscs_this_pass.append(new_fosc)
            current_foscs.append(new_fosc)  # Add to current FOSCs for next iteration
            connections_this_pass.append({
                "cable_id": cable_id,
                "fosc_id": fosc_id,
                "connection_point": connection_point,
                "distance_m": distance,
                "target_type": target_type,
                "iteration": iteration
            })
            print(f"    ✓ Created FOSC {fosc_id} at connection point")
        
        # Update all non-isolated cables
        for feature in current_cables.get("features", []):
            props = feature.get("properties", {})
            cable_id = props.get("ID") or props.get("id", "")
            
            # Skip if this was an isolated cable (already processed)
            if cable_id in processed_cable_ids:
                continue
            
            updated_features.append(feature)
        
            # Build updated GeoJSON for this pass (with CRS for map visualization)
            current_cables = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": "urn:ogc:def:crs:EPSG::32617"
                    }
                },
                "features": updated_features
            }
        
        # Accumulate results
        all_new_foscs.extend(new_foscs_this_pass)
        all_connections.extend(connections_this_pass)
        total_connected += len(connections_this_pass)
        
        print(f"    ✓ Connected {len(connections_this_pass)} cables in this pass")
        print(f"    ✓ Created {len(new_foscs_this_pass)} new FOSCs in this pass")
    
    print(f"\n  ✓ Total: Connected {total_connected} isolated cables over {iteration} pass(es)")
    print(f"  ✓ Total: Created {len(all_new_foscs)} new FOSCs")
    
    return current_cables, all_new_foscs, {
        "isolated_found": "multiple_passes" if iteration > 1 else len(isolated_cables) if iteration == 1 else 0,
        "connected": total_connected,
        "extended": total_connected,
        "new_foscs": len(all_new_foscs),
        "iterations": iteration,
        "connections": all_connections
    }


def main():
    """Test function."""
    print("=" * 80)
    print("CONNECTING ISOLATED CABLES - TEST")
    print("=" * 80)
    print()
    
    # Load data
    cables_geojson = load_geojson("test_output/small_area_design/fiber_cable_updated_ids.geojson")
    
    # Load FOSCs
    try:
        with open("test_output/small_area_design/rules_optimized_foscs.json") as f:
            import json
            foscs = json.load(f)
    except:
        foscs = []
    
    # Connect isolated cables
    updated_cables, new_foscs, summary = connect_isolated_cables(
        cables_geojson,
        foscs,
        tolerance_m=50.0,
        max_connection_distance_m=1000.0
    )
    
    # Save results
    output_path = "test_output/small_area_design/fiber_cable_connected.geojson"
    with open(output_path, "w") as f:
        import json
        json.dump(updated_cables, f, indent=2)
    
    print(f"✓ Saved connected cables to {output_path}")
    print(f"✓ Summary: {summary}")


if __name__ == "__main__":
    main()
