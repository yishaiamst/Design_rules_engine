#!/usr/bin/env python3
"""
Fix FOSC and MST placement issues:
1. Restore FOSCs at cable junctions
2. Convert Aerial Terminals to MSTs when near FOSCs (<1km)
3. Filter ONTs >1km from terminals
4. Ensure MSTs connect to FOSCs via stub cables
"""

import json
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance
from utils.config_loader import load_config
from phases.phase3b_refine_mst_placement import find_nearest_point_on_cable

try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    import math


def latlon_to_utm(lat, lon, zone=17):
    """Convert WGS84 lat/lon to UTM Zone 17N."""
    if PYPROJ_AVAILABLE:
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:32617", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return (easting, northing)
    else:
        import math
        k0 = 0.9996
        a = 6378137.0
        e2 = 0.00669438
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
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
        return (easting, northing)


def find_cable_junctions(cables):
    """
    Find points where multiple cables meet (junctions).
    Uses cable ID patterns to identify junctions (e.g., F1000391 appears in multiple cable IDs).
    """
    from collections import defaultdict
    
    # Method 1: Use cable ID patterns (more reliable)
    # Extract node IDs from cable IDs (e.g., "144FOC/F1000391/F1000392" -> F1000391, F1000392)
    node_to_cables = defaultdict(list)
    cable_id_to_cable = {}
    
    for cable in cables:
        cable_id = cable.get("id", "")
        if not cable_id:
            continue
        
        cable_id_to_cable[cable_id] = cable
        
        # Parse cable ID: {SIZE}FOC/{FROM_ID}/{TO_ID}
        parts = cable_id.split('/')
        if len(parts) >= 3:
            from_id = parts[1]
            to_id = parts[2]
            node_to_cables[from_id].append(cable_id)
            node_to_cables[to_id].append(cable_id)
    
    # Find nodes where 2+ cables meet (junctions)
    junctions = []
    for node_id, cable_list in node_to_cables.items():
        if len(cable_list) >= 2:
            # Get position from first cable's endpoint
            first_cable = cable_id_to_cable.get(cable_list[0])
            if first_cable:
                coords = first_cable.get("coordinates", [])
                if len(coords) >= 2:
                    # Try to find the endpoint that matches this node
                    # For now, use the start point
                    junction_pos = coords[0]
                    
                    junctions.append({
                        "position": tuple(junction_pos),
                        "cables": cable_list,
                        "cable_count": len(cable_list),
                        "node_id": node_id
                    })
    
    # Method 2: Also check geometric endpoints (fallback)
    endpoint_to_cables = defaultdict(list)
    
    for cable in cables:
        cable_id = cable.get("id", "")
        coords = cable.get("coordinates", [])
        if len(coords) >= 2:
            start = tuple(coords[0])
            end = tuple(coords[-1])
            
            # Round to nearest 10m for matching (more tolerant)
            start_rounded = (round(start[0]/10)*10, round(start[1]/10)*10)
            end_rounded = (round(end[0]/10)*10, round(end[1]/10)*10)
            
            endpoint_to_cables[start_rounded].append(cable_id)
            endpoint_to_cables[end_rounded].append(cable_id)
    
    # Add geometric junctions not found by ID pattern
    for point, cable_list in endpoint_to_cables.items():
        unique_cables = list(set(cable_list))
        if len(unique_cables) >= 2:
            # Check if we already have this junction
            already_found = False
            for existing in junctions:
                dist = euclidean_distance(point[0], point[1], existing["position"][0], existing["position"][1])
                if dist < 50.0:  # Within 50m
                    already_found = True
                    break
            
            if not already_found:
                junctions.append({
                    "position": point,
                    "cables": unique_cables,
                    "cable_count": len(unique_cables),
                    "node_id": None
                })
    
    return junctions


def restore_foscs_at_junctions(cables, existing_foscs, terminals):
    """Restore FOSCs at cable junctions where they were removed."""
    print()
    print("=" * 80)
    print("RESTORING FOSCs AT CABLE JUNCTIONS")
    print("=" * 80)
    print()
    
    junctions = find_cable_junctions(cables)
    print(f"Found {len(junctions)} cable junctions")
    
    # Get existing FOSC positions
    existing_fosc_positions = set()
    for fosc in existing_foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (round(fosc_pos[0]), round(fosc_pos[1])) if isinstance(fosc_pos, list) else (round(fosc_pos[0]), round(fosc_pos[1]))
            existing_fosc_positions.add(fosc_pos_utm)
    
    # Get terminal positions that might have replaced FOSCs
    terminal_positions = {}
    for terminal in terminals:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            terminal_positions[terminal.get("terminal_id", "")] = term_pos_utm
    
    new_foscs = []
    fosc_id_counter = 1
    
    for junction in junctions:
        junction_pos = junction["position"]
        junction_rounded = (round(junction_pos[0]), round(junction_pos[1]))
        
        # Check if FOSC already exists at this location
        if junction_rounded in existing_fosc_positions:
            continue
        
        # Check if there's a terminal very close (might have replaced FOSC)
        has_nearby_terminal = False
        nearby_terminal_id = None
        for term_id, term_pos in terminal_positions.items():
            dist = euclidean_distance(junction_pos[0], junction_pos[1], term_pos[0], term_pos[1])
            if dist < 50.0:  # Within 50m
                has_nearby_terminal = True
                nearby_terminal_id = term_id
                break
        
        # Create FOSC at junction
        fosc_id = f"F{len(existing_foscs) + len(new_foscs) + fosc_id_counter:07d}"
        fosc_id_counter += 1
        
        # Find nearest point on cable (snap to cable)
        nearest_cable = None
        min_dist = float('inf')
        for cable in cables:
            nearest_point, dist = find_nearest_point_on_cable(junction_pos, cable)
            if dist < min_dist:
                min_dist = dist
                nearest_cable = cable
                junction_pos = nearest_point
        
        new_fosc = {
            "fosc_id": fosc_id,
            "position": [junction_pos[0], junction_pos[1]],
            "connected_cables": junction["cables"],
            "junction_cable_count": junction["cable_count"],
            "restored": True,
            "nearby_terminal": nearby_terminal_id if has_nearby_terminal else None
        }
        
        new_foscs.append(new_fosc)
        
        if has_nearby_terminal:
            print(f"  ✓ Restored FOSC {fosc_id} at junction (near {nearby_terminal_id})")
            print(f"    Cables: {', '.join(junction['cables'][:3])}...")
        else:
            print(f"  ✓ Restored FOSC {fosc_id} at junction")
            print(f"    Cables: {', '.join(junction['cables'][:3])}...")
    
    print()
    print(f"Restored {len(new_foscs)} FOSCs at cable junctions")
    print()
    
    return new_foscs


def convert_aerial_to_mst_near_foscs(terminals, foscs, max_distance=1000.0):
    """Convert Aerial Terminals to MSTs when they're near FOSCs (<1km)."""
    print()
    print("=" * 80)
    print("CONVERTING AERIAL TERMINALS TO MSTs AND CONNECTING MSTs TO FOSCs")
    print("=" * 80)
    print()
    
    converted = []
    
    converted = []
    connected = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        
        if not terminal_pos:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Find nearest FOSC
        nearest_fosc = None
        min_fosc_dist = float('inf')
        
        for fosc in foscs:
            fosc_pos = fosc.get("position")
            if not fosc_pos:
                continue
            
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos_utm[0], fosc_pos_utm[1])
            
            if dist < min_fosc_dist and dist <= max_distance:
                min_fosc_dist = dist
                nearest_fosc = fosc
        
        if nearest_fosc and min_fosc_dist <= max_distance:
            if terminal_type == "Aerial Terminal":
                # Convert to MST
                terminal["type"] = "MST"
                terminal["connected_fosc_id"] = nearest_fosc.get("fosc_id", "")
                terminal["stub_cable_length"] = min_fosc_dist
                
                converted.append({
                    "terminal_id": terminal_id,
                    "fosc_id": nearest_fosc.get("fosc_id", ""),
                    "distance": min_fosc_dist
                })
                
                print(f"  ✓ Converted {terminal_id} to MST (FOSC: {nearest_fosc.get('fosc_id')}, {min_fosc_dist:.1f}m)")
            elif terminal_type == "MST" and not terminal.get("connected_fosc_id"):
                # Connect existing MST to FOSC
                terminal["connected_fosc_id"] = nearest_fosc.get("fosc_id", "")
                terminal["stub_cable_length"] = min_fosc_dist
                
                connected.append({
                    "terminal_id": terminal_id,
                    "fosc_id": nearest_fosc.get("fosc_id", ""),
                    "distance": min_fosc_dist
                })
                
                print(f"  ✓ Connected {terminal_id} (MST) to FOSC {nearest_fosc.get('fosc_id')} ({min_fosc_dist:.1f}m)")
    
    print()
    print(f"Converted {len(converted)} Aerial Terminals to MSTs")
    print(f"Connected {len(connected)} existing MSTs to FOSCs")
    print()
    
    return converted + connected


def filter_distant_onts(terminals, ont_geojson, max_drop_distance=1000.0):
    """Remove ONTs that are >1km from their terminal."""
    print()
    print("=" * 80)
    print("FILTERING DISTANT ONTs (>1km)")
    print("=" * 80)
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    filtered_count = 0
    filtered_onts = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_onts = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_onts:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Filter ONTs by distance
        valid_onts = []
        removed_onts = []
        
        for ont_id in connected_onts:
            if ont_id not in onts_by_id:
                continue
            
            ont_pos = onts_by_id[ont_id]
            dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], ont_pos[0], ont_pos[1])
            
            if dist <= max_drop_distance:
                valid_onts.append(ont_id)
            else:
                removed_onts.append((ont_id, dist))
                filtered_onts.append(ont_id)
                filtered_count += 1
        
        if removed_onts:
            print(f"  {terminal_id}: Removed {len(removed_onts)} distant ONTs")
            for ont_id, dist in removed_onts:
                print(f"    - {ont_id}: {dist:.1f}m ({dist/1000:.2f}km)")
        
        terminal["connected_onts"] = valid_onts
        terminal["removed_distant_onts"] = [ont_id for ont_id, _ in removed_onts]
    
    print()
    print(f"Filtered {filtered_count} ONTs >{max_drop_distance/1000:.1f}km from terminals")
    print()
    
    return filtered_onts


def main():
    print("=" * 80)
    print("FIX FOSC AND MST PLACEMENT")
    print("=" * 80)
    print()
    
    # Center point
    center_lat = 45.731437
    center_lon = -82.401057
    radius_m = 5000.0
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    with open("test_output/terminal_placement_summary.json") as f:
        terminal_data = json.load(f)
    terminals = terminal_data.get("terminals", [])
    
    with open("test_output/fosc_placement_summary.json") as f:
        fosc_data = json.load(f)
    foscs = fosc_data.get("foscs", [])
    
    # Extract area (same as before)
    center_utm = latlon_to_utm(center_lat, center_lon)
    
    # Extract cables
    extracted_cables = []
    cables_list = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        near_center = False
        for coord in coords_list:
            if len(coord) >= 2:
                cable_pos_utm = (float(coord[0]), float(coord[1]))
                dist = euclidean_distance(center_utm[0], center_utm[1], cable_pos_utm[0], cable_pos_utm[1])
                if dist <= radius_m:
                    near_center = True
                    break
        
        if near_center:
            extracted_cables.append(feature)
            coord_tuples = [(c[0], c[1]) for c in coords_list if len(c) >= 2]
            if coord_tuples:
                cables_list.append({
                    "id": cable_id,
                    "coordinates": coord_tuples
                })
    
    # Extract terminals and FOSCs
    extracted_terminals = []
    for terminal in terminals:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            dist = euclidean_distance(center_utm[0], center_utm[1], term_pos_utm[0], term_pos_utm[1])
            if dist <= radius_m:
                extracted_terminals.append(terminal)
    
    extracted_foscs = []
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            dist = euclidean_distance(center_utm[0], center_utm[1], fosc_pos_utm[0], fosc_pos_utm[1])
            if dist <= radius_m:
                extracted_foscs.append(fosc)
    
    print(f"  Extracted {len(extracted_cables)} cables, {len(extracted_terminals)} terminals, {len(extracted_foscs)} FOSCs")
    print()
    
    # Step 1: Restore FOSCs at cable junctions
    new_foscs = restore_foscs_at_junctions(cables_list, extracted_foscs, extracted_terminals)
    all_foscs = extracted_foscs + new_foscs
    
    # Step 2: Convert Aerial Terminals to MSTs and connect MSTs to FOSCs
    converted = convert_aerial_to_mst_near_foscs(extracted_terminals, all_foscs, max_distance=1000.0)
    
    # Step 3: Filter distant ONTs
    filtered_onts = filter_distant_onts(extracted_terminals, ont_geojson, max_drop_distance=1000.0)
    
    # Step 4: Run Phase 3b again with fixed FOSCs
    print("=" * 80)
    print("RUNNING PHASE 3B WITH FIXED FOSCs")
    print("=" * 80)
    print()
    
    from phases.phase3b_refine_mst_placement import refine_mst_placement
    
    # Extract ONTs within radius
    extracted_onts = []
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            ont_pos_utm = (float(coords[0]), float(coords[1]))
            dist = euclidean_distance(center_utm[0], center_utm[1], ont_pos_utm[0], ont_pos_utm[1])
            if dist <= radius_m:
                extracted_onts.append(feature)
    
    ont_geojson_small = {
        "type": "FeatureCollection",
        "features": extracted_onts
    }
    
    cable_geojson_small = {
        "type": "FeatureCollection",
        "features": extracted_cables
    }
    
    terminals_after, foscs_after, new_msts, summary = refine_mst_placement(
        extracted_terminals,
        all_foscs,
        ont_geojson_small,
        cable_geojson_small,
        config
    )
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"FOSCs restored: {len(new_foscs)}")
    print(f"Terminals converted to MST: {len(converted)}")
    print(f"ONTs filtered (>1km): {len(filtered_onts)}")
    print(f"Final terminals: {len(terminals_after)}")
    print(f"Final FOSCs: {len(foscs_after)}")
    print()
    
    # Save results
    with open("test_output/fixed_terminals.json", "w") as f:
        json.dump(terminals_after, f, indent=2)
    with open("test_output/fixed_foscs.json", "w") as f:
        json.dump(foscs_after, f, indent=2)
    
    print("✓ Saved fixed terminals and FOSCs")
    print()


if __name__ == "__main__":
    main()
