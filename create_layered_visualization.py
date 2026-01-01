#!/usr/bin/env python3
"""
Create separate GeoJSON layers for each network component:
- FOSC
- Aerial Terminal
- MST
- ONT
- Fiber Cables
- Drop Cables
- Stub Cables
- FDH
- Vaults
"""

import json
import math
import os
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False


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


def create_geojson_layer(features, layer_name, crs="EPSG:32617"):
    """Create a GeoJSON FeatureCollection for a layer."""
    if crs == "EPSG:32617":
        crs_name = "urn:ogc:def:crs:EPSG::32617"
    elif crs == "EPSG:4326":
        crs_name = "urn:ogc:def:crs:EPSG::4326"
    else:
        crs_name = f"urn:ogc:def:crs:{crs}"
    
    return {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": crs_name
            }
        },
        "features": features
    }


def main():
    print("=" * 80)
    print("CREATING LAYERED VISUALIZATION")
    print("=" * 80)
    print()
    
    # Center point and radius
    center_lat = 45.731437
    center_lon = -82.401057
    radius_m = 5000.0
    center_utm = latlon_to_utm(center_lat, center_lon)
    
    # Create output directory
    output_dir = "test_output/layers"
    os.makedirs(output_dir, exist_ok=True)
    
    # Load optimized data
    print("Loading optimized data...")
    with open("test_output/rules_optimized_terminals.json") as f:
        terminals = json.load(f)
    
    with open("test_output/rules_optimized_foscs.json") as f:
        foscs = json.load(f)
    
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    
    # Try to load FDH and Vault data
    fdh_geojson = None
    vault_geojson = None
    try:
        fdh_geojson = load_geojson("fdh.geojson")
        print("  Loaded FDH data")
    except Exception as e:
        print(f"  Warning: Could not load FDH data: {e}")
    
    try:
        vault_geojson = load_geojson("Vault.geojson")
        print("  Loaded Vault data")
    except Exception as e:
        print(f"  Warning: Could not load Vault data: {e}")
    
    # Extract area (5km radius)
    print(f"Extracting area around ({center_lat}, {center_lon}) with {radius_m/1000}km radius...")
    
    # Extract ONTs
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
    
    # Extract fiber cables
    extracted_cables = []
    for feature in fiber_cable_geojson.get("features", []):
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
                cable_pos_utm = (float(coord[0]), float(coord[1]))
                dist = euclidean_distance(center_utm[0], center_utm[1], cable_pos_utm[0], cable_pos_utm[1])
                if dist <= radius_m:
                    near_center = True
                    break
        
        if near_center:
            extracted_cables.append(feature)
    
    # Extract FDHs (if available)
    extracted_fdhs = []
    if fdh_geojson:
        for feature in fdh_geojson.get("features", []):
            geometry = feature.get("geometry", {})
            coords = None
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiPoint":
                coords_list = geometry.get("coordinates", [])
                if coords_list:
                    coords = coords_list[0]
            
            if coords and len(coords) >= 2:
                fdh_pos_utm = (float(coords[0]), float(coords[1]))
                dist = euclidean_distance(center_utm[0], center_utm[1], fdh_pos_utm[0], fdh_pos_utm[1])
                if dist <= radius_m:
                    extracted_fdhs.append(feature)
    
    # Extract Vaults (if available)
    extracted_vaults = []
    if vault_geojson:
        for feature in vault_geojson.get("features", []):
            geometry = feature.get("geometry", {})
            coords = None
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiPoint":
                coords_list = geometry.get("coordinates", [])
                if coords_list:
                    coords = coords_list[0]
            
            if coords and len(coords) >= 2:
                vault_pos_utm = (float(coords[0]), float(coords[1]))
                dist = euclidean_distance(center_utm[0], center_utm[1], vault_pos_utm[0], vault_pos_utm[1])
                if dist <= radius_m:
                    extracted_vaults.append(feature)
    
    print(f"  Extracted: {len(extracted_onts)} ONTs, {len(extracted_cables)} cables")
    if extracted_fdhs:
        print(f"  Extracted: {len(extracted_fdhs)} FDHs")
    if extracted_vaults:
        print(f"  Extracted: {len(extracted_vaults)} Vaults")
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in extracted_onts:
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
    
    # Build cables list for routing (use ALL cables for routing)
    all_cable_geojson = load_geojson("fiber cable.geojson")
    cables_list = []
    for feature in all_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        if len(coords_list) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords_list if len(c) >= 2]
            if coord_tuples:
                cables_list.append({
                    "id": cable_id,
                    "coordinates": coord_tuples
                })
    
    # ==========================================
    # LAYER 1: FOSC
    # ==========================================
    print("Creating FOSC layer...")
    fosc_features = []
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [fosc_pos_utm[0], fosc_pos_utm[1]]
                },
                "properties": {
                    "id": fosc.get("fosc_id", ""),
                    "type": "FOSC",
                    "merged": fosc.get("merged", False),
                    "connected_cables": fosc.get("connected_cables", []),
                    "marker-color": "#0000FF",
                    "marker-size": "medium",
                    "marker-symbol": "circle"
                }
            }
            fosc_features.append(fosc_feature)
    
    fosc_layer = create_geojson_layer(fosc_features, "FOSC")
    with open(f"{output_dir}/fosc.geojson", "w") as f:
        json.dump(fosc_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/fosc.geojson ({len(fosc_features)} features)")
    
    # ==========================================
    # LAYER 2: Aerial Terminal
    # ==========================================
    print("Creating Aerial Terminal layer...")
    aerial_features = []
    for terminal in terminals:
        term_type = terminal.get("type", "").upper()
        if term_type == "AERIAL" or term_type == "AERIAL TERMINAL":
            term_pos = terminal.get("position")
            if term_pos:
                term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
                aerial_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [term_pos_utm[0], term_pos_utm[1]]
                    },
                    "properties": {
                        "id": terminal.get("terminal_id", ""),
                        "type": "Aerial Terminal",
                        "connected_onts": len(terminal.get("connected_onts", [])),
                        "connected_cable_id": terminal.get("connected_cable_id", ""),
                        "marker-color": "#FF00FF",
                        "marker-size": "medium",
                        "marker-symbol": "circle"
                    }
                }
                aerial_features.append(aerial_feature)
    
    aerial_layer = create_geojson_layer(aerial_features, "Aerial Terminal")
    with open(f"{output_dir}/aerial_terminal.geojson", "w") as f:
        json.dump(aerial_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/aerial_terminal.geojson ({len(aerial_features)} features)")
    
    # ==========================================
    # LAYER 3: MST
    # ==========================================
    print("Creating MST layer...")
    # Build stub cable ID map first
    stub_cable_id_map = {}
    # We'll populate this when creating stub cables
    
    mst_features = []
    for terminal in terminals:
        term_type = terminal.get("type", "").upper()
        if term_type == "MST":
            term_pos = terminal.get("position")
            if term_pos:
                term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
                terminal_id = terminal.get("terminal_id", "")
                connected_fosc_id = terminal.get("connected_fosc_id", "")
                connected_aerial_id = terminal.get("connected_aerial_terminal_id", "")
                
                # Generate stub cable ID (will be set when we create stub cables)
                stub_cable_id = None
                if connected_fosc_id:
                    stub_cable_id = f"stub_{terminal_id}_{connected_fosc_id}"
                elif connected_aerial_id:
                    stub_cable_id = f"stub_{terminal_id}_{connected_aerial_id}"
                
                mst_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [term_pos_utm[0], term_pos_utm[1]]
                    },
                    "properties": {
                        "id": terminal_id,
                        "type": "MST",
                        "connected_onts": len(terminal.get("connected_onts", [])),
                        "connected_cable_id": terminal.get("connected_cable_id", ""),
                        "connected_fosc_id": connected_fosc_id,
                        "connected_aerial_terminal_id": connected_aerial_id,
                        "stub_cable_id": stub_cable_id,
                        "stub_cable_length": terminal.get("stub_cable_length"),
                        "marker-color": "#800080",
                        "marker-size": "medium",
                        "marker-symbol": "triangle"
                    }
                }
                mst_features.append(mst_feature)
    
    mst_layer = create_geojson_layer(mst_features, "MST")
    with open(f"{output_dir}/mst.geojson", "w") as f:
        json.dump(mst_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/mst.geojson ({len(mst_features)} features)")
    
    # ==========================================
    # LAYER 4: ONT
    # ==========================================
    print("Creating ONT layer...")
    ont_layer = create_geojson_layer(extracted_onts, "ONT")
    with open(f"{output_dir}/ont.geojson", "w") as f:
        json.dump(ont_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/ont.geojson ({len(extracted_onts)} features)")
    
    # ==========================================
    # LAYER 5: Fiber Cables (with offset for overlapping paths)
    # ==========================================
    print("Creating Fiber Cables layer...")
    
    def offset_line_perpendicular(coords, offset_distance):
        """Offset a LineString perpendicular to its direction."""
        if len(coords) < 2:
            return coords
        
        offset_coords = []
        for i in range(len(coords)):
            x, y = coords[i][0], coords[i][1]
            
            if i == 0:
                # First point: use direction to next point
                if len(coords) > 1:
                    dx = coords[1][0] - x
                    dy = coords[1][1] - y
                    length = math.sqrt(dx*dx + dy*dy)
                    if length > 0:
                        # Perpendicular vector (rotate 90 degrees)
                        perp_x = -dy / length
                        perp_y = dx / length
                        offset_coords.append([x + perp_x * offset_distance, y + perp_y * offset_distance])
                    else:
                        offset_coords.append([x, y])
            elif i == len(coords) - 1:
                # Last point: use direction from previous point
                dx = x - coords[i-1][0]
                dy = y - coords[i-1][1]
                length = math.sqrt(dx*dx + dy*dy)
                if length > 0:
                    perp_x = -dy / length
                    perp_y = dx / length
                    offset_coords.append([x + perp_x * offset_distance, y + perp_y * offset_distance])
                else:
                    offset_coords.append([x, y])
            else:
                # Middle point: average direction from previous and next
                dx1 = coords[i][0] - coords[i-1][0]
                dy1 = coords[i][1] - coords[i-1][1]
                dx2 = coords[i+1][0] - coords[i][0]
                dy2 = coords[i+1][1] - coords[i][1]
                
                # Average direction
                avg_dx = (dx1 + dx2) / 2
                avg_dy = (dy1 + dy2) / 2
                length = math.sqrt(avg_dx*avg_dx + avg_dy*avg_dy)
                if length > 0:
                    perp_x = -avg_dy / length
                    perp_y = avg_dx / length
                    offset_coords.append([x + perp_x * offset_distance, y + perp_y * offset_distance])
                else:
                    offset_coords.append([x, y])
        
        return offset_coords
    
    def are_cables_overlapping(cable1_coords, cable2_coords, tolerance=10.0):
        """Check if two cables are overlapping (within tolerance distance)."""
        if len(cable1_coords) < 2 or len(cable2_coords) < 2:
            return False
        
        # Sample points along both cables (more efficient: check endpoints and midpoints)
        sample_points1 = []
        sample_points2 = []
        
        # Sample cable1: endpoints + every 100m along the path
        for i in range(len(cable1_coords) - 1):
            x1, y1 = cable1_coords[i][0], cable1_coords[i][1]
            x2, y2 = cable1_coords[i+1][0], cable1_coords[i+1][1]
            segment_length = euclidean_distance(x1, y1, x2, y2)
            num_samples = max(2, int(segment_length / 100.0) + 1)  # Sample every 100m
            for j in range(num_samples):
                t = j / max(1, num_samples - 1)
                sample_points1.append((x1 + t*(x2-x1), y1 + t*(y2-y1)))
        
        # Sample cable2 similarly
        for i in range(len(cable2_coords) - 1):
            x1, y1 = cable2_coords[i][0], cable2_coords[i][1]
            x2, y2 = cable2_coords[i+1][0], cable2_coords[i+1][1]
            segment_length = euclidean_distance(x1, y1, x2, y2)
            num_samples = max(2, int(segment_length / 100.0) + 1)
            for j in range(num_samples):
                t = j / max(1, num_samples - 1)
                sample_points2.append((x1 + t*(x2-x1), y1 + t*(y2-y1)))
        
        # Check if any points are close (within tolerance)
        for p1 in sample_points1:
            for p2 in sample_points2:
                dist = euclidean_distance(p1[0], p1[1], p2[0], p2[1])
                if dist < tolerance:
                    return True
        return False
    
    # Group cables by overlapping paths
    offset_cables = []
    offset_distance = 5.0  # 5 meters offset
    
    for i, feature in enumerate(extracted_cables):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = [geometry.get("coordinates", [])]
        elif geometry.get("type") == "MultiLineString":
            coords_list = geometry.get("coordinates", [])
        
        offset_feature = feature.copy()
        
        # Check if this cable overlaps with any previous cable
        overlaps = False
        overlap_index = 0
        for j in range(i):
            prev_feature = extracted_cables[j]
            prev_geometry = prev_feature.get("geometry", {})
            prev_coords_list = []
            if prev_geometry.get("type") == "LineString":
                prev_coords_list = [prev_geometry.get("coordinates", [])]
            elif prev_geometry.get("type") == "MultiLineString":
                prev_coords_list = prev_geometry.get("coordinates", [])
            
            # Check each line segment
            for cable_coords in coords_list:
                for prev_coords in prev_coords_list:
                    if are_cables_overlapping(cable_coords, prev_coords, tolerance=5.0):
                        overlaps = True
                        overlap_index = j
                        break
                if overlaps:
                    break
            if overlaps:
                break
        
        # Apply offset if overlapping
        if overlaps:
            offset_multiplier = (i - overlap_index) * 0.5  # Stagger offsets
            actual_offset = offset_distance * offset_multiplier
            
            if geometry.get("type") == "LineString":
                coords = geometry.get("coordinates", [])
                offset_coords = offset_line_perpendicular(coords, actual_offset)
                offset_feature["geometry"]["coordinates"] = offset_coords
            elif geometry.get("type") == "MultiLineString":
                offset_lines = []
                for line in geometry.get("coordinates", []):
                    offset_line = offset_line_perpendicular(line, actual_offset)
                    offset_lines.append(offset_line)
                offset_feature["geometry"]["coordinates"] = offset_lines
            
            # Add offset info to properties
            offset_feature["properties"]["offset_applied"] = True
            offset_feature["properties"]["offset_distance_m"] = actual_offset
        
        offset_cables.append(offset_feature)
    
    fiber_cable_layer = create_geojson_layer(offset_cables, "Fiber Cable")
    with open(f"{output_dir}/fiber_cable.geojson", "w") as f:
        json.dump(fiber_cable_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/fiber_cable.geojson ({len(offset_cables)} features)")
    
    # ==========================================
    # LAYER 6: Drop Cables
    # ==========================================
    print("Creating Drop Cables layer...")
    drop_cable_features = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_onts = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_onts:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        for ont_id in connected_onts:
            if ont_id in onts_by_id:
                ont_pos = onts_by_id[ont_id]
                
                # Drop cables are direct connections (not routed along fiber cables)
                length = euclidean_distance(
                    ont_pos[0], ont_pos[1],
                    term_pos_utm[0], term_pos_utm[1]
                )
                
                drop_cable = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [ont_pos[0], ont_pos[1]],
                            [term_pos_utm[0], term_pos_utm[1]]
                        ]
                    },
                    "properties": {
                        "id": f"drop_{ont_id}_{terminal_id}",
                        "ont_id": ont_id,
                        "terminal_id": terminal_id,
                        "terminal_type": terminal.get("type", ""),
                        "length_m": length,
                        "stroke": "#FFA500",
                        "stroke-width": 2,
                        "stroke-opacity": 0.7
                    }
                }
                drop_cable_features.append(drop_cable)
    
    drop_cable_layer = create_geojson_layer(drop_cable_features, "Drop Cable")
    with open(f"{output_dir}/drop_cable.geojson", "w") as f:
        json.dump(drop_cable_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/drop_cable.geojson ({len(drop_cable_features)} features)")
    
    # ==========================================
    # LAYER 7: Stub Cables
    # ==========================================
    print("Creating Stub Cables layer...")
    from utils.cable_routing import route_stub_cable_along_fiber
    
    stub_cable_features = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        connected_fosc_id = terminal.get("connected_fosc_id")
        connected_aerial_id = terminal.get("connected_aerial_terminal_id")  # New field for Aerial Terminal connections
        connected_cable_id = terminal.get("connected_cable_id")
        
        # MST can connect to FOSC or Aerial Terminal
        target_id = connected_fosc_id or connected_aerial_id
        target_type = "FOSC" if connected_fosc_id else "Aerial Terminal"
        
        if terminal_type == "MST" and target_id and terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            
            # Get target (FOSC or Aerial Terminal)
            target_pos = None
            target_connected_cables = []
            
            if connected_fosc_id:
                target = next((f for f in foscs if f.get("fosc_id") == connected_fosc_id), None)
                if target:
                    target_pos = target.get("position")
                    target_connected_cables = target.get("connected_cables", [])
            elif connected_aerial_id:
                # Find Aerial Terminal
                target = next((t for t in terminals if t.get("terminal_id") == connected_aerial_id), None)
                if target:
                    target_pos = target.get("position")
                    # Aerial Terminal is on a cable, use that cable for routing
                    aerial_cable_id = target.get("connected_cable_id", "")
                    if aerial_cable_id:
                        target_connected_cables = [aerial_cable_id]
            
            if target_pos:
                target_pos_utm = (target_pos[0], target_pos[1]) if isinstance(target_pos, list) else target_pos
                
                # Route stub cable along fiber cable
                preferred_cable_id = None
                if terminal_id in ["T0004288", "T0004601"] and connected_fosc_id == "F0000962":
                    preferred_cable_id = "48FOC/F1000398/T1001731"
                elif connected_cable_id == "48FOC/F1000398/T1001731" and connected_fosc_id == "F0000962":
                    preferred_cable_id = "48FOC/F1000398/T1001731"
                
                path, length, routed = route_stub_cable_along_fiber(
                    term_pos_utm,
                    target_pos_utm,
                    cables_list,
                    terminal_cable_id=connected_cable_id,
                    preferred_cable_id=preferred_cable_id,
                    fosc_connected_cables=target_connected_cables if target_connected_cables else None
                )
                
                if path is None:
                    # Stub cable cannot be routed along fiber - this is an error
                    print(f"  ⚠ WARNING: Stub cable {terminal_id} -> {target_id} ({target_type}) cannot be routed along fiber cables!")
                    print(f"    Terminal cable: {connected_cable_id}")
                    print(f"    Target cables: {target_connected_cables}")
                    # Still create the stub cable but mark it as invalid
                    path = [term_pos_utm, target_pos_utm]
                    length = euclidean_distance(term_pos_utm[0], term_pos_utm[1], target_pos_utm[0], target_pos_utm[1])
                    routed = False
                
                stub_id = f"stub_{terminal_id}_{target_id}"
                stub_cable = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[p[0], p[1]] for p in path]
                    },
                    "properties": {
                        "id": stub_id,
                        "terminal_id": terminal_id,
                        "target_type": target_type,
                        "fosc_id": connected_fosc_id if connected_fosc_id else None,
                        "aerial_terminal_id": connected_aerial_id if connected_aerial_id else None,
                        "length_m": length,
                        "routed_along_cable": routed and len(path) > 2,
                        "valid": routed,  # Mark if valid (routed along fiber)
                        "stroke": "#00FF00" if routed else "#FF0000",  # Red if invalid
                        "stroke-width": 3,
                        "stroke-opacity": 0.8
                    }
                }
                stub_cable_features.append(stub_cable)
    
    stub_cable_layer = create_geojson_layer(stub_cable_features, "Stub Cable")
    with open(f"{output_dir}/stub_cable.geojson", "w") as f:
        json.dump(stub_cable_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/stub_cable.geojson ({len(stub_cable_features)} features)")
    
    # ==========================================
    # LAYER 8: FDH
    # ==========================================
    print("Creating FDH layer...")
    if extracted_fdhs:
        fdh_layer = create_geojson_layer(extracted_fdhs, "FDH")
        with open(f"{output_dir}/fdh.geojson", "w") as f:
            json.dump(fdh_layer, f, indent=2)
        print(f"  ✓ Saved: {output_dir}/fdh.geojson ({len(extracted_fdhs)} features)")
    else:
        # Create empty layer
        fdh_layer = create_geojson_layer([], "FDH")
        with open(f"{output_dir}/fdh.geojson", "w") as f:
            json.dump(fdh_layer, f, indent=2)
        print(f"  ✓ Saved: {output_dir}/fdh.geojson (0 features - no FDH data in area)")
    
    # ==========================================
    # LAYER 9: Vaults
    # ==========================================
    print("Creating Vaults layer...")
    if extracted_vaults:
        vault_layer = create_geojson_layer(extracted_vaults, "Vault")
        with open(f"{output_dir}/vault.geojson", "w") as f:
            json.dump(vault_layer, f, indent=2)
        print(f"  ✓ Saved: {output_dir}/vault.geojson ({len(extracted_vaults)} features)")
    else:
        # Create empty layer
        vault_layer = create_geojson_layer([], "Vault")
        with open(f"{output_dir}/vault.geojson", "w") as f:
            json.dump(vault_layer, f, indent=2)
        print(f"  ✓ Saved: {output_dir}/vault.geojson (0 features - no Vault data in area)")
    
    print()
    print("=" * 80)
    print("LAYER SUMMARY")
    print("=" * 80)
    print(f"  FOSC:              {len(fosc_features)} features")
    print(f"  Aerial Terminal:   {len(aerial_features)} features")
    print(f"  MST:               {len(mst_features)} features")
    print(f"  ONT:               {len(extracted_onts)} features")
    print(f"  Fiber Cables:      {len(extracted_cables)} features")
    print(f"  Drop Cables:       {len(drop_cable_features)} features")
    print(f"  Stub Cables:       {len(stub_cable_features)} features")
    print(f"  FDH:               {len(extracted_fdhs)} features")
    print(f"  Vaults:            {len(extracted_vaults)} features")
    print()
    print(f"All layers saved to: {output_dir}/")
    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
