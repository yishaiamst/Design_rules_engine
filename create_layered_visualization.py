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
    
    # Extract fiber cables (will be updated with new IDs later)
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
    # First pass: collect all FOSC positions
    fosc_positions = {}
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_id = fosc.get("fosc_id", "")
            fosc_positions[fosc_id] = fosc_pos_utm
    
    # Second pass: create features with overlap detection
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_id = fosc.get("fosc_id", "")
            
            # Check for overlapping FOSCs (within 1m) - prioritize F0000962 visibility
            offset_x, offset_y = 0.0, 0.0
            overlapping_foscs = []
            for existing_id, existing_pos in fosc_positions.items():
                if existing_id == fosc_id:
                    continue
                dist = euclidean_distance(fosc_pos_utm[0], fosc_pos_utm[1], existing_pos[0], existing_pos[1])
                if dist < 1.0:  # Within 1 meter
                    overlapping_foscs.append(existing_id)
            
            # Apply offset: F0000962 gets priority (no offset), others get offset
            if overlapping_foscs and fosc_id == "F0000962":
                print(f"  ⚠️  F0000962 overlaps with {overlapping_foscs} - keeping F0000962 at original location")
            elif overlapping_foscs and "F0000962" in overlapping_foscs:
                # Offset this FOSC away from F0000962
                offset_x = -2.0
                offset_y = -2.0
                print(f"  ⚠️  {fosc_id} overlaps with F0000962 - applying 2m offset to {fosc_id}")
            elif overlapping_foscs:
                # Multiple overlaps - offset this one
                offset_x = 2.0
                offset_y = 2.0
                print(f"  ⚠️  {fosc_id} overlaps with {overlapping_foscs} - applying 2m offset")
            
            fosc_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [fosc_pos_utm[0] + offset_x, fosc_pos_utm[1] + offset_y]
                },
                "properties": {
                    "id": fosc_id,
                    "type": "FOSC",
                    "merged": fosc.get("merged", False),
                    "connected_cables": fosc.get("connected_cables", []),
                    "marker-color": "#FF0000" if fosc_id == "F0000962" else "#0000FF",  # Red for F0000962
                    "marker-size": "large" if fosc_id == "F0000962" else "medium",  # Larger for F0000962
                    "marker-symbol": "circle",
                    "offset_applied": offset_x != 0.0 or offset_y != 0.0,
                    "offset_distance_m": ((offset_x**2 + offset_y**2)**0.5) if (offset_x != 0.0 or offset_y != 0.0) else 0.0,
                    "overlaps_with": overlapping_foscs if overlapping_foscs else None
                }
            }
            fosc_features.append(fosc_feature)
    
    fosc_layer = create_geojson_layer(fosc_features, "FOSC")
    with open(f"{output_dir}/fosc.geojson", "w") as f:
        json.dump(fosc_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/fosc.geojson ({len(fosc_features)} features)")
    
    # ==========================================
    # LAYER 2: Aerial Terminal (with offset for FOSC overlaps)
    # ==========================================
    print("Creating Aerial Terminal layer...")
    # Build FOSC position map for overlap detection (use final positions after FOSC offsets)
    fosc_final_positions_aerial = {}
    for feature in fosc_features:
        fosc_id = feature.get("properties", {}).get("id", "")
        coords = feature.get("geometry", {}).get("coordinates", [])
        if fosc_id and len(coords) >= 2:
            fosc_final_positions_aerial[fosc_id] = (coords[0], coords[1])
    
    aerial_features = []
    aerial_positions = {}  # Track Aerial Terminal positions for overlap detection
    
    for terminal in terminals:
        term_type = terminal.get("type", "").upper()
        if term_type == "AERIAL" or term_type == "AERIAL TERMINAL":
            term_pos = terminal.get("position")
            if term_pos:
                term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
                terminal_id = terminal.get("terminal_id", "")
                
                # Check for overlaps with FOSCs
                offset_x, offset_y = 0.0, 0.0
                overlapping_fosc = None
                min_fosc_dist = float('inf')
                
                for fosc_id, fosc_pos in fosc_final_positions_aerial.items():
                    dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos[0], fosc_pos[1])
                    if dist < 1.0:  # Within 1 meter
                        if dist < min_fosc_dist:
                            min_fosc_dist = dist
                            overlapping_fosc = fosc_id
                
                # Apply offset if overlapping with FOSC
                if overlapping_fosc:
                    fosc_pos = fosc_final_positions_aerial[overlapping_fosc]
                    dx = term_pos_utm[0] - fosc_pos[0]
                    dy = term_pos_utm[1] - fosc_pos[1]
                    dist = math.sqrt(dx*dx + dy*dy) if (dx != 0 or dy != 0) else 1.0
                    
                    offset_distance = 3.0
                    if dist > 0:
                        offset_x = (dx / dist) * offset_distance
                        offset_y = (dy / dist) * offset_distance
                    else:
                        offset_x = 3.0
                        offset_y = 3.0
                    
                    print(f"  ⚠️  Aerial Terminal {terminal_id} overlaps with FOSC {overlapping_fosc} ({min_fosc_dist:.2f}m) - applying {offset_distance}m offset")
                
                # Store final position
                aerial_positions[terminal_id] = (term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y)
                
                # Store offset for drop cable adjustment (so drop cables connect to offset position)
                terminal["visualization_offset"] = (offset_x, offset_y)
                terminal["visualization_position"] = (term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y)
                
                aerial_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y]
                    },
                    "properties": {
                        "id": terminal_id,
                        "type": "Aerial Terminal",
                        "connected_onts": len(terminal.get("connected_onts", [])),
                        "connected_cable_id": terminal.get("connected_cable_id", ""),
                        "marker-color": "#FF00FF",
                        "marker-size": "medium",
                        "marker-symbol": "circle",
                        "offset_applied": offset_x != 0.0 or offset_y != 0.0,
                        "offset_distance_m": ((offset_x**2 + offset_y**2)**0.5) if (offset_x != 0.0 or offset_y != 0.0) else 0.0,
                        "overlaps_with_fosc": overlapping_fosc if overlapping_fosc else None
                    }
                }
                aerial_features.append(aerial_feature)
    
    aerial_layer = create_geojson_layer(aerial_features, "Aerial Terminal")
    with open(f"{output_dir}/aerial_terminal.geojson", "w") as f:
        json.dump(aerial_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/aerial_terminal.geojson ({len(aerial_features)} features)")
    
    # ==========================================
    # LAYER 3: MST (with offset for FOSC overlaps)
    # ==========================================
    print("Creating MST layer...")
    # Build stub cable ID map first
    stub_cable_id_map = {}
    # We'll populate this when creating stub cables
    
    # Build FOSC position map for overlap detection (use final positions after FOSC offsets)
    fosc_final_positions = {}
    for feature in fosc_features:
        fosc_id = feature.get("properties", {}).get("id", "")
        coords = feature.get("geometry", {}).get("coordinates", [])
        if fosc_id and len(coords) >= 2:
            fosc_final_positions[fosc_id] = (coords[0], coords[1])
    
    mst_features = []
    mst_positions = {}  # Track MST positions for MST-to-MST overlap detection
    
    for terminal in terminals:
        term_type = terminal.get("type", "").upper()
        if term_type == "MST":
            term_pos = terminal.get("position")
            if term_pos:
                term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
                terminal_id = terminal.get("terminal_id", "")
                connected_fosc_id = terminal.get("connected_fosc_id", "")
                connected_aerial_id = terminal.get("connected_aerial_terminal_id", "")
                
                # Check for overlaps with FOSCs
                offset_x, offset_y = 0.0, 0.0
                overlapping_fosc = None
                min_fosc_dist = float('inf')
                
                for fosc_id, fosc_pos in fosc_final_positions.items():
                    dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos[0], fosc_pos[1])
                    if dist < 1.0:  # Within 1 meter
                        if dist < min_fosc_dist:
                            min_fosc_dist = dist
                            overlapping_fosc = fosc_id
                
                # Apply offset if overlapping with FOSC
                # Offset MST away from FOSC (FOSC stays at original location)
                if overlapping_fosc:
                    # Calculate offset direction (away from FOSC)
                    fosc_pos = fosc_final_positions[overlapping_fosc]
                    dx = term_pos_utm[0] - fosc_pos[0]
                    dy = term_pos_utm[1] - fosc_pos[1]
                    dist = math.sqrt(dx*dx + dy*dy) if (dx != 0 or dy != 0) else 1.0
                    
                    # Normalize and apply 3m offset away from FOSC
                    offset_distance = 3.0
                    if dist > 0:
                        offset_x = (dx / dist) * offset_distance
                        offset_y = (dy / dist) * offset_distance
                    else:
                        # Same exact location - offset in a default direction
                        offset_x = 3.0
                        offset_y = 3.0
                    
                    print(f"  ⚠️  MST {terminal_id} overlaps with FOSC {overlapping_fosc} ({min_fosc_dist:.2f}m) - applying {offset_distance}m offset")
                
                # Check for overlaps with other MSTs (after FOSC offset)
                final_mst_pos = (term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y)
                overlapping_msts = []
                for existing_mst_id, existing_mst_pos in mst_positions.items():
                    dist = euclidean_distance(final_mst_pos[0], final_mst_pos[1], existing_mst_pos[0], existing_mst_pos[1])
                    if dist < 1.0:
                        overlapping_msts.append(existing_mst_id)
                
                # Apply additional offset if overlapping with other MSTs
                if overlapping_msts:
                    # Stagger MSTs: alternate offset direction
                    mst_offset_multiplier = len(overlapping_msts) % 2 * 2 - 1  # -1 or 1
                    additional_offset = 2.0 * mst_offset_multiplier
                    offset_x += additional_offset
                    offset_y += additional_offset
                    print(f"  ⚠️  MST {terminal_id} also overlaps with MSTs {overlapping_msts} - applying additional offset")
                
                # Store final position for future overlap checks
                mst_positions[terminal_id] = (term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y)
                
                # Store offset for drop cable adjustment (so drop cables connect to offset position)
                terminal["visualization_offset"] = (offset_x, offset_y)
                terminal["visualization_position"] = (term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y)
                
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
                        "coordinates": [term_pos_utm[0] + offset_x, term_pos_utm[1] + offset_y]
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
                        "marker-symbol": "triangle",
                        "offset_applied": offset_x != 0.0 or offset_y != 0.0,
                        "offset_distance_m": ((offset_x**2 + offset_y**2)**0.5) if (offset_x != 0.0 or offset_y != 0.0) else 0.0,
                        "overlaps_with_fosc": overlapping_fosc if overlapping_fosc else None,
                        "overlaps_with_msts": overlapping_msts if overlapping_msts else None
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
    
    # Update cable IDs based on FOSC and terminal positions
    from phases.phase3d_update_cable_ids import update_cable_ids_for_area
    
    # Convert center to UTM
    center_utm = latlon_to_utm(center_lat, center_lon)
    
    # Update cable IDs for the extracted area
    updated_cables_geojson, cable_id_summary = update_cable_ids_for_area(
        fiber_cable_geojson,
        foscs,
        terminals,
        center_point=center_utm,
        radius_m=radius_m,
        tolerance=50.0
    )
    
    # Use updated cables for extraction
    updated_extracted_cables = []
    for feature in updated_cables_geojson.get("features", []):
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
            updated_extracted_cables.append(feature)
    
    print(f"  Updated {cable_id_summary.get('updated', 0)} cable IDs based on FOSC/terminal positions")
    print()
    
    # Load exact offset positions of FOSCs and Aerial Terminals from saved GeoJSON files
    # This ensures fiber cable endpoints connect to the exact visual positions
    fosc_positions_map_fiber = {}  # fosc_id -> (x, y) offset position
    aerial_positions_map_fiber = {}  # terminal_id -> (x, y) offset position
    
    # Load FOSC positions from saved file
    try:
        with open(f"{output_dir}/fosc.geojson", "r") as f:
            fosc_geojson = json.load(f)
            for feature in fosc_geojson.get("features", []):
                fosc_id = feature.get("properties", {}).get("id", "")
                coords = feature.get("geometry", {}).get("coordinates", [])
                if fosc_id and len(coords) >= 2:
                    fosc_positions_map_fiber[fosc_id] = (float(coords[0]), float(coords[1]))
    except Exception as e:
        print(f"  ⚠️  Could not load FOSC positions for fiber cable endpoints: {e}")
        # Fall back to fosc_features if available
        for feature in fosc_features:
            fosc_id = feature.get("properties", {}).get("id", "")
            coords = feature.get("geometry", {}).get("coordinates", [])
            if fosc_id and len(coords) >= 2:
                fosc_positions_map_fiber[fosc_id] = (float(coords[0]), float(coords[1]))
    
    # Load Aerial Terminal positions from saved file
    try:
        with open(f"{output_dir}/aerial_terminal.geojson", "r") as f:
            aerial_geojson = json.load(f)
            for feature in aerial_geojson.get("features", []):
                terminal_id = feature.get("properties", {}).get("id", "")
                coords = feature.get("geometry", {}).get("coordinates", [])
                if terminal_id and len(coords) >= 2:
                    aerial_positions_map_fiber[terminal_id] = (float(coords[0]), float(coords[1]))
    except Exception as e:
        print(f"  ⚠️  Could not load Aerial Terminal positions for fiber cable endpoints: {e}")
        # Fall back to aerial_features if available
        for feature in aerial_features:
            terminal_id = feature.get("properties", {}).get("id", "")
            coords = feature.get("geometry", {}).get("coordinates", [])
            if terminal_id and len(coords) >= 2:
                aerial_positions_map_fiber[terminal_id] = (float(coords[0]), float(coords[1]))
    
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
    
    # Use updated extracted cables (with new IDs) for offsetting
    cables_to_offset = updated_extracted_cables if 'updated_extracted_cables' in locals() else extracted_cables
    
    # STEP 1: Snap cable endpoints to exact FOSC/Terminal positions BEFORE offsetting
    # This ensures the base geometry connects precisely to point features
    print("  Snapping fiber cable endpoints to FOSC/Terminal positions...")
    snapped_cables = []
    for feature in cables_to_offset:
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        # Extract from_id and to_id
        from_id = props.get("from_id")
        to_id = props.get("to_id")
        
        # If not in properties, try to parse from cable ID (format: <size>FOC/From/To)
        if not from_id or not to_id:
            cable_id = props.get("ID") or props.get("id", "")
            if cable_id and '/' in cable_id:
                parts = cable_id.split('/')
                if len(parts) >= 3:
                    if not from_id:
                        from_id = parts[1] if parts[1] != "UNKNOWN" else None
                    if not to_id:
                        to_id = parts[2] if parts[2] != "UNKNOWN" else None
        
        snapped_feature = feature.copy()
        snapped_geometry = snapped_feature.get("geometry", {}).copy()
        
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                # Snap first point (from_id)
                if from_id:
                    target_pos = None
                    if from_id.startswith('F') and from_id in fosc_positions_map_fiber:
                        target_pos = fosc_positions_map_fiber[from_id]
                    elif from_id.startswith('T') and from_id in aerial_positions_map_fiber:
                        target_pos = aerial_positions_map_fiber[from_id]
                    
                    if target_pos:
                        # Replace first point with exact target position
                        coords[0] = [float(target_pos[0]), float(target_pos[1])]
                
                # Snap last point (to_id)
                if to_id:
                    target_pos = None
                    if to_id.startswith('F') and to_id in fosc_positions_map_fiber:
                        target_pos = fosc_positions_map_fiber[to_id]
                    elif to_id.startswith('T') and to_id in aerial_positions_map_fiber:
                        target_pos = aerial_positions_map_fiber[to_id]
                    
                    if target_pos:
                        # Replace last point with exact target position
                        coords[-1] = [float(target_pos[0]), float(target_pos[1])]
                
                snapped_geometry["coordinates"] = coords
        elif geometry.get("type") == "MultiLineString":
            lines = geometry.get("coordinates", [])
            if lines:
                # Snap first point of first line (from_id)
                if from_id:
                    target_pos = None
                    if from_id.startswith('F') and from_id in fosc_positions_map_fiber:
                        target_pos = fosc_positions_map_fiber[from_id]
                    elif from_id.startswith('T') and from_id in aerial_positions_map_fiber:
                        target_pos = aerial_positions_map_fiber[from_id]
                    
                    if target_pos and len(lines[0]) > 0:
                        lines[0][0] = [float(target_pos[0]), float(target_pos[1])]
                
                # Snap last point of last line (to_id)
                if to_id:
                    target_pos = None
                    if to_id.startswith('F') and to_id in fosc_positions_map_fiber:
                        target_pos = fosc_positions_map_fiber[to_id]
                    elif to_id.startswith('T') and to_id in aerial_positions_map_fiber:
                        target_pos = aerial_positions_map_fiber[to_id]
                    
                    if target_pos and len(lines) > 0 and len(lines[-1]) > 0:
                        lines[-1][-1] = [float(target_pos[0]), float(target_pos[1])]
                
                snapped_geometry["coordinates"] = lines
        
        snapped_feature["geometry"] = snapped_geometry
        snapped_cables.append(snapped_feature)
    
    print(f"  ✓ Snapped {len(snapped_cables)} fiber cables to exact endpoint positions")
    
    # Group cables by overlapping paths
    offset_cables = []
    offset_distance = 5.0  # 5 meters offset
    
    for i, feature in enumerate(snapped_cables):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords_list = []
        if geometry.get("type") == "LineString":
            coords_list = [geometry.get("coordinates", [])]
        elif geometry.get("type") == "MultiLineString":
            coords_list = geometry.get("coordinates", [])
        
        offset_feature = feature.copy()
        
        # Check if this cable overlaps with any previous cable (use snapped cables for comparison)
        overlaps = False
        overlap_index = 0
        for j in range(i):
            prev_feature = snapped_cables[j]
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
                
                # CRITICAL: Restore endpoints to exact offset positions of connected FOSCs/Aerial Terminals
                # Extract from_id and to_id from cable properties or cable ID
                from_id = props.get("from_id")
                to_id = props.get("to_id")
                
                # If not in properties, try to parse from cable ID (format: <size>FOC/From/To)
                if not from_id or not to_id:
                    cable_id = props.get("ID") or props.get("id", "")
                    if cable_id and '/' in cable_id:
                        parts = cable_id.split('/')
                        if len(parts) >= 3:
                            if not from_id:
                                from_id = parts[1] if parts[1] != "UNKNOWN" else None
                            if not to_id:
                                to_id = parts[2] if parts[2] != "UNKNOWN" else None
                
                # Restore first point (from_id) to exact offset position
                if from_id:
                    if from_id.startswith('F') and from_id in fosc_positions_map_fiber:
                        # FOSC - use exact offset position
                        offset_coords[0] = [float(fosc_positions_map_fiber[from_id][0]), 
                                           float(fosc_positions_map_fiber[from_id][1])]
                    elif from_id.startswith('T') and from_id in aerial_positions_map_fiber:
                        # Aerial Terminal - use exact offset position
                        offset_coords[0] = [float(aerial_positions_map_fiber[from_id][0]), 
                                           float(aerial_positions_map_fiber[from_id][1])]
                
                # Restore last point (to_id) to exact offset position
                if to_id:
                    if to_id.startswith('F') and to_id in fosc_positions_map_fiber:
                        # FOSC - use exact offset position
                        offset_coords[-1] = [float(fosc_positions_map_fiber[to_id][0]), 
                                            float(fosc_positions_map_fiber[to_id][1])]
                    elif to_id.startswith('T') and to_id in aerial_positions_map_fiber:
                        # Aerial Terminal - use exact offset position
                        offset_coords[-1] = [float(aerial_positions_map_fiber[to_id][0]), 
                                            float(aerial_positions_map_fiber[to_id][1])]
                
                offset_feature["geometry"]["coordinates"] = offset_coords
            elif geometry.get("type") == "MultiLineString":
                offset_lines = []
                for line_idx, line in enumerate(geometry.get("coordinates", [])):
                    offset_line = offset_line_perpendicular(line, actual_offset)
                    
                    # CRITICAL: Restore endpoints for each line segment
                    # For MultiLineString, we need to handle first line's first point and last line's last point
                    from_id = props.get("from_id")
                    to_id = props.get("to_id")
                    
                    # If not in properties, try to parse from cable ID
                    if not from_id or not to_id:
                        cable_id = props.get("ID") or props.get("id", "")
                        if cable_id and '/' in cable_id:
                            parts = cable_id.split('/')
                            if len(parts) >= 3:
                                if not from_id:
                                    from_id = parts[1] if parts[1] != "UNKNOWN" else None
                                if not to_id:
                                    to_id = parts[2] if parts[2] != "UNKNOWN" else None
                    
                    # First line's first point connects to from_id
                    if line_idx == 0 and from_id:
                        if from_id.startswith('F') and from_id in fosc_positions_map_fiber:
                            offset_line[0] = [float(fosc_positions_map_fiber[from_id][0]), 
                                             float(fosc_positions_map_fiber[from_id][1])]
                        elif from_id.startswith('T') and from_id in aerial_positions_map_fiber:
                            offset_line[0] = [float(aerial_positions_map_fiber[from_id][0]), 
                                             float(aerial_positions_map_fiber[from_id][1])]
                    
                    # Last line's last point connects to to_id
                    if line_idx == len(geometry.get("coordinates", [])) - 1 and to_id:
                        if to_id.startswith('F') and to_id in fosc_positions_map_fiber:
                            offset_line[-1] = [float(fosc_positions_map_fiber[to_id][0]), 
                                              float(fosc_positions_map_fiber[to_id][1])]
                        elif to_id.startswith('T') and to_id in aerial_positions_map_fiber:
                            offset_line[-1] = [float(aerial_positions_map_fiber[to_id][0]), 
                                              float(aerial_positions_map_fiber[to_id][1])]
                    
                    offset_lines.append(offset_line)
                offset_feature["geometry"]["coordinates"] = offset_lines
            
            # Add offset info to properties
            offset_feature["properties"]["offset_applied"] = True
            offset_feature["properties"]["offset_distance_m"] = actual_offset
        else:
            # Even if not overlapping, ensure endpoints connect to exact offset positions
            # This handles cases where cables weren't offset but still need endpoint correction
            from_id = props.get("from_id")
            to_id = props.get("to_id")
            
            # If not in properties, try to parse from cable ID
            if not from_id or not to_id:
                cable_id = props.get("ID") or props.get("id", "")
                if cable_id and '/' in cable_id:
                    parts = cable_id.split('/')
                    if len(parts) >= 3:
                        if not from_id:
                            from_id = parts[1] if parts[1] != "UNKNOWN" else None
                        if not to_id:
                            to_id = parts[2] if parts[2] != "UNKNOWN" else None
            
            if geometry.get("type") == "LineString":
                coords = geometry.get("coordinates", [])
                if len(coords) >= 2:
                    # Restore first point
                    if from_id:
                        if from_id.startswith('F') and from_id in fosc_positions_map_fiber:
                            coords[0] = [float(fosc_positions_map_fiber[from_id][0]), 
                                        float(fosc_positions_map_fiber[from_id][1])]
                        elif from_id.startswith('T') and from_id in aerial_positions_map_fiber:
                            coords[0] = [float(aerial_positions_map_fiber[from_id][0]), 
                                        float(aerial_positions_map_fiber[from_id][1])]
                    
                    # Restore last point
                    if to_id:
                        if to_id.startswith('F') and to_id in fosc_positions_map_fiber:
                            coords[-1] = [float(fosc_positions_map_fiber[to_id][0]), 
                                         float(fosc_positions_map_fiber[to_id][1])]
                        elif to_id.startswith('T') and to_id in aerial_positions_map_fiber:
                            coords[-1] = [float(aerial_positions_map_fiber[to_id][0]), 
                                         float(aerial_positions_map_fiber[to_id][1])]
                    
                    offset_feature["geometry"]["coordinates"] = coords
            elif geometry.get("type") == "MultiLineString":
                lines = geometry.get("coordinates", [])
                if lines:
                    # Restore first point of first line
                    if from_id:
                        if from_id.startswith('F') and from_id in fosc_positions_map_fiber:
                            if len(lines[0]) > 0:
                                lines[0][0] = [float(fosc_positions_map_fiber[from_id][0]), 
                                             float(fosc_positions_map_fiber[from_id][1])]
                        elif from_id.startswith('T') and from_id in aerial_positions_map_fiber:
                            if len(lines[0]) > 0:
                                lines[0][0] = [float(aerial_positions_map_fiber[from_id][0]), 
                                             float(aerial_positions_map_fiber[from_id][1])]
                    
                    # Restore last point of last line
                    if to_id:
                        if to_id.startswith('F') and to_id in fosc_positions_map_fiber:
                            if len(lines[-1]) > 0:
                                lines[-1][-1] = [float(fosc_positions_map_fiber[to_id][0]), 
                                                float(fosc_positions_map_fiber[to_id][1])]
                        elif to_id.startswith('T') and to_id in aerial_positions_map_fiber:
                            if len(lines[-1]) > 0:
                                lines[-1][-1] = [float(aerial_positions_map_fiber[to_id][0]), 
                                                float(aerial_positions_map_fiber[to_id][1])]
                    
                    offset_feature["geometry"]["coordinates"] = lines
        
        offset_cables.append(offset_feature)
    
    fiber_cable_layer = create_geojson_layer(offset_cables, "Fiber Cable")
    with open(f"{output_dir}/fiber_cable.geojson", "w") as f:
        json.dump(fiber_cable_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/fiber_cable.geojson ({len(offset_cables)} features)")
    
    # ==========================================
    # LAYER 6: Drop Cables (with offset for MST/Aerial Terminal visualization)
    # ==========================================
    print("Creating Drop Cables layer...")
    drop_cable_features = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_onts = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_onts:
            continue
        
        # Use visualization position if offset was applied, otherwise use original position
        if "visualization_position" in terminal:
            term_pos_utm = terminal["visualization_position"]
            offset_applied = terminal.get("visualization_offset", (0.0, 0.0)) != (0.0, 0.0)
            offset_dist = ((terminal.get("visualization_offset", (0.0, 0.0))[0]**2 + terminal.get("visualization_offset", (0.0, 0.0))[1]**2)**0.5) if offset_applied else 0.0
        else:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            offset_applied = False
            offset_dist = 0.0
        
        for ont_id in connected_onts:
            if ont_id in onts_by_id:
                ont_pos = onts_by_id[ont_id]
                
                # Drop cables are direct connections (not routed along fiber cables)
                # Use offset terminal position so drop cable connects to visible MST/Aerial Terminal
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
                        "stroke-opacity": 0.7,
                        "terminal_offset_applied": offset_applied,
                        "terminal_offset_distance_m": offset_dist
                    }
                }
                drop_cable_features.append(drop_cable)
    
    drop_cable_layer = create_geojson_layer(drop_cable_features, "Drop Cable")
    with open(f"{output_dir}/drop_cable.geojson", "w") as f:
        json.dump(drop_cable_layer, f, indent=2)
    print(f"  ✓ Saved: {output_dir}/drop_cable.geojson ({len(drop_cable_features)} features)")
    
    # ==========================================
    # LAYER 7: Stub Cables (with offset for overlapping paths)
    # ==========================================
    print("Creating Stub Cables layer...")
    from utils.cable_routing import route_stub_cable_along_fiber
    
    # Reload MST and FOSC positions from saved GeoJSON files to ensure we have exact offset positions
    # This ensures stub cables connect to the exact visual positions
    mst_positions_map = {}  # terminal_id -> (x, y) offset position
    fosc_positions_map = {}  # fosc_id -> (x, y) offset position
    
    # Load MST positions from saved file
    try:
        with open(f"{output_dir}/mst.geojson", "r") as f:
            mst_geojson = json.load(f)
            for feature in mst_geojson.get("features", []):
                terminal_id = feature.get("properties", {}).get("id", "")
                coords = feature.get("geometry", {}).get("coordinates", [])
                if terminal_id and len(coords) >= 2:
                    mst_positions_map[terminal_id] = (float(coords[0]), float(coords[1]))
    except Exception as e:
        print(f"  ⚠️  Could not load MST positions: {e}")
        # Fall back to mst_features if available
        for feature in mst_features:
            terminal_id = feature.get("properties", {}).get("id", "")
            coords = feature.get("geometry", {}).get("coordinates", [])
            if terminal_id and len(coords) >= 2:
                mst_positions_map[terminal_id] = (float(coords[0]), float(coords[1]))
    
    # Load FOSC positions from saved file
    try:
        with open(f"{output_dir}/fosc.geojson", "r") as f:
            fosc_geojson = json.load(f)
            for feature in fosc_geojson.get("features", []):
                fosc_id = feature.get("properties", {}).get("id", "")
                coords = feature.get("geometry", {}).get("coordinates", [])
                if fosc_id and len(coords) >= 2:
                    fosc_positions_map[fosc_id] = (float(coords[0]), float(coords[1]))
    except Exception as e:
        print(f"  ⚠️  Could not load FOSC positions: {e}")
        # Fall back to fosc_features if available
        for feature in fosc_features:
            fosc_id = feature.get("properties", {}).get("id", "")
            coords = feature.get("geometry", {}).get("coordinates", [])
            if fosc_id and len(coords) >= 2:
                fosc_positions_map[fosc_id] = (float(coords[0]), float(coords[1]))
    
    stub_cable_features = []
    stub_cable_coords_map = {}  # Map stub_id -> coordinates for overlap detection
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
            # Use visualization position if offset was applied (so stub cable connects to visible MST)
            # Look up MST position from saved positions map (exact offset position from GeoJSON file)
            term_pos_utm = None
            if terminal_id in mst_positions_map:
                # Use exact offset position from saved MST GeoJSON file
                term_pos_utm = mst_positions_map[terminal_id]
                # Debug for problematic cables
                if terminal_id in ["T0000034", "T0004300"]:
                    print(f"  DEBUG {terminal_id}: Found in mst_positions_map: {term_pos_utm}")
            else:
                # Fallback: try mst_features
                try:
                    mst_feature = next((f for f in mst_features if f.get("properties", {}).get("id") == terminal_id), None)
                    if mst_feature:
                        mst_coords = mst_feature.get("geometry", {}).get("coordinates", [])
                        if len(mst_coords) >= 2:
                            term_pos_utm = (float(mst_coords[0]), float(mst_coords[1]))
                            if terminal_id in ["T0000034", "T0004300"]:
                                print(f"  DEBUG {terminal_id}: Found in mst_features: {term_pos_utm}")
                except (NameError, TypeError):
                    pass
            
            # Final fallback to visualization_position or original position
            if term_pos_utm is None:
                if "visualization_position" in terminal and terminal["visualization_position"]:
                    term_pos_utm = terminal["visualization_position"]
                    if isinstance(term_pos_utm, list):
                        term_pos_utm = (term_pos_utm[0], term_pos_utm[1])
                    if terminal_id in ["T0000034", "T0004300"]:
                        print(f"  DEBUG {terminal_id}: Using visualization_position: {term_pos_utm}")
                else:
                    term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
                    if terminal_id in ["T0000034", "T0004300"]:
                        print(f"  DEBUG {terminal_id}: Using original position: {term_pos_utm}")
            
            # Get target (FOSC or Aerial Terminal)
            # Use visualization position if FOSC was offset
            target_pos = None
            target_connected_cables = []
            
            if connected_fosc_id:
                target = next((f for f in foscs if f.get("fosc_id") == connected_fosc_id), None)
                if target:
                    # Look up FOSC position from saved positions map (exact offset position from GeoJSON file)
                    if connected_fosc_id in fosc_positions_map:
                        # Use exact offset position from saved FOSC GeoJSON file
                        target_pos = fosc_positions_map[connected_fosc_id]
                    else:
                        # Fallback: try fosc_features
                        fosc_feature = next((f for f in fosc_features if f.get("properties", {}).get("id") == connected_fosc_id), None)
                        if fosc_feature:
                            # Use offset FOSC position from GeoJSON feature
                            fosc_coords = fosc_feature.get("geometry", {}).get("coordinates", [])
                            if len(fosc_coords) >= 2:
                                target_pos = (float(fosc_coords[0]), float(fosc_coords[1]))
                            else:
                                target_pos = target.get("position")
                                if isinstance(target_pos, list):
                                    target_pos = (target_pos[0], target_pos[1])
                        else:
                            target_pos = target.get("position")
                            if isinstance(target_pos, list):
                                target_pos = (target_pos[0], target_pos[1])
                    target_connected_cables = target.get("connected_cables", [])
            elif connected_aerial_id:
                # Find Aerial Terminal
                target = next((t for t in terminals if t.get("terminal_id") == connected_aerial_id), None)
                if target:
                    # Use visualization position if Aerial Terminal was offset
                    if "visualization_position" in target:
                        target_pos = target["visualization_position"]
                    else:
                        target_pos = target.get("position")
                    # Aerial Terminal is on a cable, use that cable for routing
                    aerial_cable_id = target.get("connected_cable_id", "")
                    if aerial_cable_id:
                        target_connected_cables = [aerial_cable_id]
            
            if target_pos:
                target_pos_utm = (target_pos[0], target_pos[1]) if isinstance(target_pos, list) else target_pos
                
                # Route stub cable along fiber cable (using original positions for routing logic)
                # But the path will be adjusted to connect to offset positions
                preferred_cable_id = None
                if terminal_id in ["T0004288", "T0004601"] and connected_fosc_id == "F0000962":
                    preferred_cable_id = "48FOC/F1000398/T1001731"
                elif connected_cable_id == "48FOC/F1000398/T1001731" and connected_fosc_id == "F0000962":
                    preferred_cable_id = "48FOC/F1000398/T1001731"
                
                # Route using original positions for pathfinding
                original_term_pos = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
                original_target_pos = None
                if connected_fosc_id:
                    original_target = next((f for f in foscs if f.get("fosc_id") == connected_fosc_id), None)
                    if original_target:
                        original_target_pos = original_target.get("position")
                        if isinstance(original_target_pos, list):
                            original_target_pos = (original_target_pos[0], original_target_pos[1])
                elif connected_aerial_id:
                    original_target = next((t for t in terminals if t.get("terminal_id") == connected_aerial_id), None)
                    if original_target:
                        original_target_pos = original_target.get("position")
                        if isinstance(original_target_pos, list):
                            original_target_pos = (original_target_pos[0], original_target_pos[1])
                
                # Initialize path_for_geojson variable
                path_for_geojson = None
                path = None
                length = 0.0
                routed = False
                
                if original_target_pos:
                    # Route using original positions for pathfinding (along fiber cables)
                    path, length, routed = route_stub_cable_along_fiber(
                        original_term_pos,
                        original_target_pos,
                        cables_list,
                        terminal_cable_id=connected_cable_id,
                        preferred_cable_id=preferred_cable_id,
                        fosc_connected_cables=target_connected_cables if target_connected_cables else None
                    )
                    
                    # Adjust path endpoints to connect to offset positions
                    # This ensures stub cable visually connects to offset MST and FOSC
                    if path and len(path) >= 2:
                        # Make a mutable copy of the path
                        path_list = []
                        for p in path:
                            if isinstance(p, (list, tuple)) and len(p) >= 2:
                                path_list.append([float(p[0]), float(p[1])])
                            else:
                                path_list.append([float(p[0]), float(p[1])])
                        
                        # Debug before modification
                        if terminal_id in ["T0000034", "T0004300"]:
                            print(f"  DEBUG {stub_id} BEFORE modification:")
                            print(f"    path_list[0] (original): {path_list[0]}")
                            print(f"    path_list[-1] (original): {path_list[-1]}")
                            print(f"    term_pos_utm (should use): {term_pos_utm}")
                            print(f"    target_pos_utm (should use): {target_pos_utm}")
                        
                        # CRITICAL: Update first point (MST end) to EXACT offset position
                        # This ensures stub cable visually connects to offset MST
                        # Force exact match - overwrite whatever was in path_list[0]
                        path_list[0] = [float(term_pos_utm[0]), float(term_pos_utm[1])]
                        # CRITICAL: Update last point (FOSC/Terminal end) to EXACT offset position
                        # This ensures stub cable visually connects to offset FOSC
                        # Force exact match - overwrite whatever was in path_list[-1]
                        path_list[-1] = [float(target_pos_utm[0]), float(target_pos_utm[1])]
                        
                        # Store for GeoJSON (use modified path_list with offset endpoints)
                        path_for_geojson = path_list.copy()  # Make explicit copy
                        
                        # Final verification: Force endpoints to exact offset positions
                        # This is a safety check to ensure endpoints match exactly
                        # CRITICAL: These MUST be the exact offset positions from mst_positions_map and fosc_positions_map
                        path_for_geojson[0] = [float(term_pos_utm[0]), float(term_pos_utm[1])]
                        path_for_geojson[-1] = [float(target_pos_utm[0]), float(target_pos_utm[1])]
                        
                        # Debug: Verify endpoints are correct (for specific problematic cables)
                        if terminal_id in ["T0000034", "T0004300"]:
                            print(f"  DEBUG {stub_id} AFTER modification:")
                            print(f"    path_list[0]: {path_list[0]}")
                            print(f"    path_list[-1]: {path_list[-1]}")
                            print(f"    path_for_geojson[0]: {path_for_geojson[0]}")
                            print(f"    path_for_geojson[-1]: {path_for_geojson[-1]}")
                        
                        # Recalculate length with offset endpoints
                        total_length = 0.0
                        for i in range(len(path_list) - 1):
                            x1, y1 = path_list[i][0], path_list[i][1]
                            x2, y2 = path_list[i+1][0], path_list[i+1][1]
                            total_length += euclidean_distance(x1, y1, x2, y2)
                        length = total_length
                    else:
                        # No path found - use direct connection with offset positions
                        if terminal_id in ["T0000034", "T0004300"]:
                            print(f"  DEBUG {stub_id}: No path found, using direct connection")
                            print(f"    term_pos_utm: {term_pos_utm}")
                            print(f"    target_pos_utm: {target_pos_utm}")
                        path_for_geojson = [[float(term_pos_utm[0]), float(term_pos_utm[1])], 
                                           [float(target_pos_utm[0]), float(target_pos_utm[1])]]
                        length = euclidean_distance(term_pos_utm[0], term_pos_utm[1], target_pos_utm[0], target_pos_utm[1])
                        routed = False
                else:
                    # Fallback: direct connection with offset positions
                    path_for_geojson = [[float(term_pos_utm[0]), float(term_pos_utm[1])], 
                                       [float(target_pos_utm[0]), float(target_pos_utm[1])]]
                    length = euclidean_distance(term_pos_utm[0], term_pos_utm[1], target_pos_utm[0], target_pos_utm[1])
                    routed = False
                
                if path is None or not path_for_geojson:
                    # Stub cable cannot be routed along fiber - this is an error
                    print(f"  ⚠ WARNING: Stub cable {terminal_id} -> {target_id} ({target_type}) cannot be routed along fiber cables!")
                    print(f"    Terminal cable: {connected_cable_id}")
                    print(f"    Target cables: {target_connected_cables}")
                    # Still create the stub cable but mark it as invalid
                    path_for_geojson = [[float(term_pos_utm[0]), float(term_pos_utm[1])], 
                                       [float(target_pos_utm[0]), float(target_pos_utm[1])]]
                    length = euclidean_distance(term_pos_utm[0], term_pos_utm[1], target_pos_utm[0], target_pos_utm[1])
                    routed = False
                
                stub_id = f"stub_{terminal_id}_{target_id}"
                
                # CRITICAL: Create a NEW list for path_coords with exact offset endpoints
                # This ensures we're not modifying a shared reference
                if path_for_geojson and len(path_for_geojson) >= 2:
                    # Create new list with offset endpoints
                    path_coords = []
                    # First point: exact offset MST position
                    path_coords.append([float(term_pos_utm[0]), float(term_pos_utm[1])])
                    # Middle points: copy from path_for_geojson (if any)
                    if len(path_for_geojson) > 2:
                        for i in range(1, len(path_for_geojson) - 1):
                            path_coords.append([float(path_for_geojson[i][0]), float(path_for_geojson[i][1])])
                    # Last point: exact offset FOSC position
                    path_coords.append([float(target_pos_utm[0]), float(target_pos_utm[1])])
                else:
                    # Fallback: direct connection with offset positions
                    path_coords = [[float(term_pos_utm[0]), float(term_pos_utm[1])], 
                                  [float(target_pos_utm[0]), float(target_pos_utm[1])]]
                
                # Debug: Verify final coordinates (for problematic cables)
                if terminal_id in ["T0000034", "T0004300"]:
                    print(f"  DEBUG {stub_id} FINAL coordinates:")
                    print(f"    path_coords[0]: {path_coords[0]}")
                    print(f"    path_coords[-1]: {path_coords[-1]}")
                    print(f"    term_pos_utm: {term_pos_utm}")
                    print(f"    target_pos_utm: {target_pos_utm}")
                
                stub_cable = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": path_coords
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
    
    # Apply offsets to overlapping stub cables
    print("  Applying offsets to overlapping stub cables...")
    offset_stub_cables = []
    stub_offset_distance = 3.0  # 3 meters offset for stub cables (smaller than fiber cables)
    
    for i, feature in enumerate(stub_cable_features):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        stub_id = props.get("id", "")
        coords = geometry.get("coordinates", [])
        
        if len(coords) < 2:
            offset_stub_cables.append(feature)
            continue
        
        # Check if this stub cable overlaps with any previous stub cable
        overlaps = False
        overlap_count = 0
        for j in range(i):
            prev_feature = stub_cable_features[j]
            prev_props = prev_feature.get("properties", {})
            prev_stub_id = prev_props.get("id", "")
            prev_coords = prev_feature.get("geometry", {}).get("coordinates", [])
            
            if prev_stub_id in stub_cable_coords_map:
                prev_coords = stub_cable_coords_map[prev_stub_id]
            
            if len(prev_coords) >= 2:
                # Check if overlapping (within 5m tolerance for stub cables)
                if are_cables_overlapping(coords, prev_coords, tolerance=5.0):
                    overlaps = True
                    overlap_count += 1
        
        # Apply offset if overlapping
        offset_feature = feature.copy()
        offset_geometry = offset_feature.get("geometry", {})
        offset_props = offset_feature.get("properties", {})
        
        if overlaps:
            # Calculate offset: stagger based on overlap count
            # First overlap: offset one direction, second: opposite, etc.
            offset_multiplier = (overlap_count % 2) * 2 - 1  # -1 or 1
            actual_offset = stub_offset_distance * offset_multiplier * (overlap_count + 1) / 2
            
            # Apply perpendicular offset to middle points, but preserve endpoints
            # Endpoints must remain at exact offset MST and FOSC positions
            offset_coords = offset_line_perpendicular(coords, actual_offset)
            
            # CRITICAL: Restore endpoints to exact offset positions
            # Get terminal and FOSC IDs from stub_id
            stub_parts = stub_id.split('_')
            if len(stub_parts) >= 3:
                terminal_id = stub_parts[1]
                target_id = stub_parts[2]
                
                # Get exact offset positions from maps
                if terminal_id in mst_positions_map:
                    # Restore first point to exact offset MST position
                    offset_coords[0] = [float(mst_positions_map[terminal_id][0]), 
                                       float(mst_positions_map[terminal_id][1])]
                
                # Get FOSC or Aerial Terminal position
                if target_id.startswith('F') and target_id in fosc_positions_map:
                    # Restore last point to exact offset FOSC position
                    offset_coords[-1] = [float(fosc_positions_map[target_id][0]), 
                                        float(fosc_positions_map[target_id][1])]
                elif target_id.startswith('T'):
                    # Aerial Terminal - get from saved positions or original
                    # Try to find in mst_positions_map (if it's an MST) or use original
                    if target_id in mst_positions_map:
                        offset_coords[-1] = [float(mst_positions_map[target_id][0]), 
                                            float(mst_positions_map[target_id][1])]
            
            offset_geometry["coordinates"] = offset_coords
            offset_props["offset_applied"] = True
            offset_props["offset_distance_m"] = abs(actual_offset)
            offset_props["overlap_count"] = overlap_count
            
            # Update stored coordinates for future overlap checks
            stub_cable_coords_map[stub_id] = offset_coords
        else:
            offset_props["offset_applied"] = False
            offset_props["offset_distance_m"] = 0.0
        
        offset_feature["geometry"] = offset_geometry
        offset_feature["properties"] = offset_props
        offset_stub_cables.append(offset_feature)
    
    if len(offset_stub_cables) != len(stub_cable_features):
        print(f"  ⚠️  Warning: Stub cable count mismatch after offsetting")
    
    stub_cable_layer = create_geojson_layer(offset_stub_cables, "Stub Cable")
    with open(f"{output_dir}/stub_cable.geojson", "w") as f:
        json.dump(stub_cable_layer, f, indent=2)
    
    offset_count = sum(1 for f in offset_stub_cables if f.get("properties", {}).get("offset_applied", False))
    print(f"  ✓ Saved: {output_dir}/stub_cable.geojson ({len(offset_stub_cables)} features, {offset_count} with offsets)")
    
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
