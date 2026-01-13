#!/usr/bin/env python3
"""
Update fiber cable IDs based on FOSC and terminal positions at endpoints.

Format: <size>FOC/From/To
Example: 144FOC/T123456/F67890

Where:
- size: Fiber count (extracted from current cable ID or properties)
- From: Terminal ID (T...) or FOSC ID (F...) at start point
- To: Terminal ID (T...) or FOSC ID (F...) at end point
"""

import json
import sys
import os
from typing import List, Dict, Any, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.spatial_utils import euclidean_distance
from utils.geojson_utils import load_geojson


def find_nearest_element_at_point(
    point: Tuple[float, float],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    tolerance: float = 50.0,
    prefer_fosc: bool = True
) -> Tuple[Optional[str], Optional[str], float]:
    """
    Find the nearest FOSC or Terminal at a point.
    
    Rule: Fiber cables should connect to FOSCs, not MSTs.
    If both FOSC and MST are at the same location, prefer FOSC.
    
    Args:
        point: Point coordinates (x, y)
        foscs: List of FOSC dictionaries
        terminals: List of terminal dictionaries
        tolerance: Distance tolerance for matching (default 50m)
        prefer_fosc: If True, prefer FOSC over Terminal when both are at same location
    
    Returns:
        (element_id, element_type, distance)
        element_type: 'FOSC' or 'Terminal'
    """
    min_dist_fosc = float('inf')
    nearest_fosc_id = None
    
    min_dist_terminal = float('inf')
    nearest_terminal_id = None
    nearest_terminal_type = None
    
    # Check FOSCs
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            dist = euclidean_distance(point[0], point[1], fosc_pos_utm[0], fosc_pos_utm[1])
            if dist < min_dist_fosc and dist < tolerance:
                min_dist_fosc = dist
                nearest_fosc_id = fosc.get("fosc_id", "")
    
    # Check Terminals (only Aerial Terminals, not MSTs - MSTs don't connect to fiber cables)
    for terminal in terminals:
        term_type = terminal.get("type", "").upper()
        # Skip MSTs - fiber cables should connect to FOSCs, not MSTs
        if term_type == "MST":
            continue
        
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            dist = euclidean_distance(point[0], point[1], term_pos_utm[0], term_pos_utm[1])
            if dist < min_dist_terminal and dist < tolerance:
                min_dist_terminal = dist
                nearest_terminal_id = terminal.get("terminal_id", "")
                nearest_terminal_type = "Terminal"
    
    # Prefer FOSC if both are found and prefer_fosc is True
    if prefer_fosc and nearest_fosc_id and nearest_terminal_id:
        # If FOSC is closer or within 1m of terminal, use FOSC
        if min_dist_fosc <= min_dist_terminal + 1.0:
            return nearest_fosc_id, "FOSC", min_dist_fosc
        else:
            return nearest_terminal_id, nearest_terminal_type, min_dist_terminal
    
    # Return whichever is found (or closest if both found)
    if nearest_fosc_id and nearest_terminal_id:
        if min_dist_fosc < min_dist_terminal:
            return nearest_fosc_id, "FOSC", min_dist_fosc
        else:
            return nearest_terminal_id, nearest_terminal_type, min_dist_terminal
    elif nearest_fosc_id:
        return nearest_fosc_id, "FOSC", min_dist_fosc
    elif nearest_terminal_id:
        return nearest_terminal_id, nearest_terminal_type, min_dist_terminal
    else:
        return None, None, float('inf')


def extract_fiber_size_from_cable_id(cable_id: str) -> Optional[str]:
    """
    Extract fiber size from cable ID.
    
    Examples:
        '144FOC/F1000391/F1000392' -> '144FOC'
        '48FOC/F1000406/F1000394' -> '48FOC'
        '96FOC/F1000391/F1000397' -> '96FOC'
    """
    if not cable_id:
        return None
    
    # Look for pattern like "144FOC", "48FOC", etc.
    parts = cable_id.split('/')
    if parts and 'FOC' in parts[0].upper():
        return parts[0].upper()
    
    # Try to extract from other parts
    for part in parts:
        if 'FOC' in part.upper():
            # Extract number before FOC
            import re
            match = re.search(r'(\d+)FOC', part.upper())
            if match:
                return match.group(0)
    
    return None


def extract_fiber_size_from_properties(props: Dict[str, Any]) -> Optional[str]:
    """
    Extract fiber size from cable properties.
    """
    # Check common property names
    fiber_count = props.get("FiberCount") or props.get("fiber_count") or props.get("Size") or props.get("size")
    
    if fiber_count:
        # Convert to string format
        if isinstance(fiber_count, (int, float)):
            return f"{int(fiber_count)}FOC"
        elif isinstance(fiber_count, str):
            if 'FOC' in fiber_count.upper():
                return fiber_count.upper()
            else:
                # Try to extract number
                import re
                match = re.search(r'(\d+)', fiber_count)
                if match:
                    return f"{match.group(1)}FOC"
    
    return None


def update_cable_ids(
    cables_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    tolerance: float = 50.0
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Update cable IDs based on FOSC and terminal positions at endpoints.
    
    Format: <size>FOC/From/To
    
    Args:
        cables_geojson: GeoJSON with cable features
        foscs: List of FOSC dictionaries
        terminals: List of terminal dictionaries
        tolerance: Distance tolerance for matching endpoints (default 50m)
    
    Returns:
        (updated_cables_geojson, summary)
    """
    print()
    print("=" * 80)
    print("UPDATING CABLE IDs BASED ON FOSC AND TERMINAL POSITIONS")
    print("=" * 80)
    print()
    
    updated_features = []
    updates = []
    unchanged = []
    
    for feature in cables_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        old_cable_id = props.get("ID") or props.get("id", "")
        
        # Extract coordinates
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        if not coords_list or len(coords_list) < 2:
            updated_features.append(feature)
            continue
        
        start_point = (coords_list[0][0], coords_list[0][1])
        end_point = (coords_list[-1][0], coords_list[-1][1])
        
        # Find elements at endpoints
        from_id, from_type, from_dist = find_nearest_element_at_point(start_point, foscs, terminals, tolerance)
        to_id, to_type, to_dist = find_nearest_element_at_point(end_point, foscs, terminals, tolerance)
        
        # Extract fiber size
        fiber_size = extract_fiber_size_from_cable_id(old_cable_id)
        if not fiber_size:
            fiber_size = extract_fiber_size_from_properties(props)
        if not fiber_size:
            fiber_size = "UNKNOWN"  # Fallback
        
        # Build new cable ID
        new_cable_id = None
        if from_id and to_id:
            # Format: <size>FOC/From/To
            new_cable_id = f"{fiber_size}/{from_id}/{to_id}"
        elif from_id:
            # Only start point has element
            new_cable_id = f"{fiber_size}/{from_id}/UNKNOWN"
        elif to_id:
            # Only end point has element
            new_cable_id = f"{fiber_size}/UNKNOWN/{to_id}"
        else:
            # No elements at endpoints - keep original or use UNKNOWN
            new_cable_id = old_cable_id if old_cable_id else f"{fiber_size}/UNKNOWN/UNKNOWN"
        
        # Update feature
        updated_feature = feature.copy()
        updated_props = updated_feature.get("properties", {})
        updated_props["ID"] = new_cable_id
        updated_props["id"] = new_cable_id
        updated_props["original_id"] = old_cable_id  # Keep original for reference
        updated_props["from_id"] = from_id
        updated_props["from_type"] = from_type
        updated_props["to_id"] = to_id
        updated_props["to_type"] = to_type
        updated_feature["properties"] = updated_props
        
        updated_features.append(updated_feature)
        
        if new_cable_id != old_cable_id:
            updates.append({
                "old_id": old_cable_id,
                "new_id": new_cable_id,
                "from": from_id,
                "to": to_id,
                "fiber_size": fiber_size
            })
            print(f"  ✓ {old_cable_id}")
            print(f"    → {new_cable_id}")
            if from_id:
                print(f"    From: {from_id} ({from_type}, {from_dist:.1f}m)")
            if to_id:
                print(f"    To: {to_id} ({to_type}, {to_dist:.1f}m)")
            print()
        else:
            unchanged.append(old_cable_id)
    
    updated_geojson = cables_geojson.copy()
    updated_geojson["features"] = updated_features
    
    # Ensure CRS is included for map visualization
    if "crs" not in updated_geojson:
        updated_geojson["crs"] = {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:EPSG::32617"
            }
        }
    
    print(f"Updated {len(updates)} cable IDs")
    print(f"Unchanged: {len(unchanged)} cable IDs")
    print()
    
    return updated_geojson, {
        "updated": len(updates),
        "unchanged": len(unchanged),
        "updates": updates
    }


def update_cable_ids_for_area(
    cables_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    center_point: Tuple[float, float] = None,
    radius_m: float = None,
    tolerance: float = 50.0
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Update cable IDs for cables in a specific area (if center_point and radius provided).
    Otherwise updates all cables.
    """
    if center_point and radius_m:
        # Filter cables in area
        filtered_features = []
        for feature in cables_geojson.get("features", []):
            geometry = feature.get("geometry", {})
            coords_list = []
            if geometry.get("type") == "LineString":
                coords_list = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiLineString":
                for line in geometry.get("coordinates", []):
                    coords_list.extend(line)
            
            near_center = False
            for coord in coords_list:
                if len(coord) >= 2:
                    dist = euclidean_distance(center_point[0], center_point[1], coord[0], coord[1])
                    if dist <= radius_m:
                        near_center = True
                        break
            
            if near_center:
                filtered_features.append(feature)
        
        filtered_geojson = cables_geojson.copy()
        filtered_geojson["features"] = filtered_features
        return update_cable_ids(filtered_geojson, foscs, terminals, tolerance)
    else:
        return update_cable_ids(cables_geojson, foscs, terminals, tolerance)


def main():
    print("=" * 80)
    print("UPDATING CABLE IDs")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    cables_geojson = load_geojson("fiber cable.geojson")
    
    with open("test_output/rules_optimized_foscs.json") as f:
        foscs = json.load(f)
    
    with open("test_output/rules_optimized_terminals.json") as f:
        terminals = json.load(f)
    
    print(f"  Loaded {len(cables_geojson.get('features', []))} cables")
    print(f"  Loaded {len(foscs)} FOSCs")
    print(f"  Loaded {len(terminals)} terminals")
    print()
    
    # Update cable IDs for extracted area (5km radius around center)
    center_lat = 45.731437
    center_lon = -82.401057
    radius_m = 5000.0
    
    # Convert center to UTM
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32617", always_xy=True)
        center_utm = transformer.transform(center_lon, center_lat)
    except:
        # Manual approximation
        import math
        k0 = 0.9996
        a = 6378137.0
        e2 = 0.00669438
        lat_rad = math.radians(center_lat)
        lon_rad = math.radians(center_lon)
        central_meridian = math.radians(-81.0)
        N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
        T = math.tan(lat_rad)**2
        C = e2 * math.cos(lat_rad)**2 / (1 - e2)
        A = math.cos(lat_rad) * (lon_rad - central_meridian)
        M = a * ((1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_rad
                 - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_rad)
                 + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_rad)
                 - (35*e2**3/3072) * math.sin(6*lat_rad))
        easting = k0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58)*A**5/120) + 500000.0
        northing = k0 * (M + N*math.tan(lat_rad)*(A**2/2 + (5-T+9*C+4*C**2)*A**4/24 + (61-58*T+T**2+600*C-330)*A**6/720))
        center_utm = (easting, northing)
    
    # Update cable IDs
    updated_cables, summary = update_cable_ids_for_area(
        cables_geojson, foscs, terminals,
        center_point=center_utm,
        radius_m=radius_m,
        tolerance=50.0
    )
    
    # Save updated cables
    output_file = "test_output/updated_cables.geojson"
    with open(output_file, "w") as f:
        json.dump(updated_cables, f, indent=2)
    
    print(f"✓ Saved updated cables: {output_file}")
    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
