#!/usr/bin/env python3
"""
Run complete MST placement algorithm on unified coordinate area.
Includes drop cable creation and visualization.
"""

import json
from utils.geojson_utils import load_geojson, create_feature_collection
from utils.spatial_utils import euclidean_distance
from utils.config_loader import load_config
from phases.phase3b_refine_mst_placement import refine_mst_placement

try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    import math


def latlon_to_utm(lat, lon, zone=17):
    """Convert WGS84 lat/lon to UTM Zone 17N (EPSG:32617)."""
    if PYPROJ_AVAILABLE:
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:32617", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return (easting, northing)
    else:
        # Manual approximation
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


def extract_area_by_coordinates(
    ont_geojson,
    fiber_cable_geojson,
    terminals_full,
    foscs_full,
    center_lat,
    center_lon,
    radius_m=5000.0
):
    """Extract area based on center coordinates (WGS84) and radius."""
    print("=" * 80)
    print("EXTRACTING AREA BY UNIFIED COORDINATES")
    print("=" * 80)
    print()
    
    center_utm = latlon_to_utm(center_lat, center_lon)
    print(f"Center point (WGS84): ({center_lat:.6f}, {center_lon:.6f})")
    print(f"Center point (UTM Zone 17N): ({center_utm[0]:.2f}, {center_utm[1]:.2f})")
    print(f"Extraction radius: {radius_m/1000:.1f}km ({radius_m:.0f}m)")
    print()
    
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
    
    print(f"  ✓ Extracted {len(extracted_onts)} ONTs")
    
    # Extract cables
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
    
    print(f"  ✓ Extracted {len(extracted_cables)} cables")
    
    # Extract terminals
    extracted_terminals = []
    for terminal in terminals_full:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            dist = euclidean_distance(center_utm[0], center_utm[1], term_pos_utm[0], term_pos_utm[1])
            if dist <= radius_m:
                extracted_terminals.append(terminal)
    
    print(f"  ✓ Extracted {len(extracted_terminals)} terminals")
    
    # Extract FOSCs
    extracted_foscs = []
    for fosc in foscs_full:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            dist = euclidean_distance(center_utm[0], center_utm[1], fosc_pos_utm[0], fosc_pos_utm[1])
            if dist <= radius_m:
                extracted_foscs.append(fosc)
    
    print(f"  ✓ Extracted {len(extracted_foscs)} FOSCs")
    
    ont_geojson_small = create_feature_collection(extracted_onts)
    cable_geojson_small = create_feature_collection(extracted_cables)
    
    return ont_geojson_small, cable_geojson_small, extracted_terminals, extracted_foscs, center_utm


def create_drop_cables(terminals, ont_geojson):
    """Create drop cables from ONTs to their connected terminals."""
    drop_cables = []
    onts_by_id = {}
    
    # Build ONT position map
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
    
    # Create drop cables
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
                        "stroke": "#FFA500",
                        "stroke-width": 2,
                        "stroke-opacity": 0.7
                    }
                }
                drop_cables.append(drop_cable)
    
    return drop_cables


def analyze_fosc_redundancy(foscs, terminals, cables):
    """
    Analyze FOSC redundancy:
    1. FOSCs very close to terminals (<50m) - likely redundant
    2. FOSCs on single cable with same size on both sides - likely redundant
    """
    print()
    print("=" * 80)
    print("ANALYZING FOSC REDUNDANCY")
    print("=" * 80)
    print()
    
    from phases.phase3b_refine_mst_placement import find_nearest_point_on_cable
    
    redundant_foscs = []
    
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            continue
        
        fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
        
        # Check 1: Very close to terminal (<50m)
        nearby_terminals = []
        for terminal in terminals:
            term_pos = terminal.get("position")
            if not term_pos:
                continue
            
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            dist = euclidean_distance(fosc_pos_utm[0], fosc_pos_utm[1], term_pos_utm[0], term_pos_utm[1])
            
            if dist < 50.0:  # Within 50m
                nearby_terminals.append((terminal.get("terminal_id", ""), dist, terminal.get("type", "")))
        
        # Check 2: On single cable with same size on both sides
        fosc_on_single_cable = False
        cable_sizes = []
        
        for cable in cables:
            nearest_point, dist = find_nearest_point_on_cable(fosc_pos_utm, cable)
            if dist < 10.0:  # FOSC is on this cable
                # Check cable size (if available in properties)
                cable_id = cable.get("id", "")
                # For now, we'll check if FOSC is on only one cable
                cable_sizes.append(cable_id)
        
        if len(cable_sizes) == 1:
            fosc_on_single_cable = True
        
        # Determine if redundant
        is_redundant = False
        reason = []
        
        if nearby_terminals:
            is_redundant = True
            reason.append(f"Very close to terminal(s): {', '.join([f'{t[0]} ({t[1]:.1f}m)' for t in nearby_terminals])}")
        
        if fosc_on_single_cable:
            is_redundant = True
            reason.append("On single fiber cable")
        
        if is_redundant:
            redundant_foscs.append({
                "fosc_id": fosc_id,
                "fosc_pos": fosc_pos_utm,
                "reasons": reason,
                "nearby_terminals": nearby_terminals
            })
    
    if redundant_foscs:
        print("Redundant FOSCs identified:")
        for fosc_info in redundant_foscs:
            print(f"  {fosc_info['fosc_id']} at {fosc_info['fosc_pos']}")
            for reason in fosc_info['reasons']:
                print(f"    - {reason}")
        print()
        print(f"Total redundant FOSCs: {len(redundant_foscs)}")
        print()
    else:
        print("No redundant FOSCs found.")
        print()
    
    return redundant_foscs


def main():
    print("=" * 80)
    print("COMPLETE MST PLACEMENT ALGORITHM - UNIFIED COORDINATES")
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
    terminals_full = terminal_data.get("terminals", [])
    
    with open("test_output/fosc_placement_summary.json") as f:
        fosc_data = json.load(f)
    foscs_full = fosc_data.get("foscs", [])
    
    print(f"  Loaded {len(terminals_full)} terminals, {len(foscs_full)} FOSCs")
    print()
    
    # Extract area
    ont_geojson_small, cable_geojson_small, extracted_terminals, extracted_foscs, center_utm = extract_area_by_coordinates(
        ont_geojson,
        fiber_cable_geojson,
        terminals_full,
        foscs_full,
        center_lat,
        center_lon,
        radius_m
    )
    
    # Analyze FOSC redundancy
    # Build cables list for analysis
    cables_list = []
    for feature in cable_geojson_small.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        coords_list = []
        
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        if coords_list:
            coord_tuples = [(c[0], c[1]) for c in coords_list if len(c) >= 2]
            if coord_tuples:
                cables_list.append({
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples
                })
    
    redundant_foscs = analyze_fosc_redundancy(extracted_foscs, extracted_terminals, cables_list)
    
    # Remove redundant FOSCs
    if redundant_foscs:
        redundant_ids = {f["fosc_id"] for f in redundant_foscs}
        extracted_foscs = [f for f in extracted_foscs if f.get("fosc_id") not in redundant_ids]
        print(f"Removed {len(redundant_ids)} redundant FOSCs")
        print()
    
    # Run Phase 3b
    print("=" * 80)
    print("RUNNING PHASE 3B: MST PLACEMENT")
    print("=" * 80)
    print()
    
    terminals_after, foscs_after, new_msts, summary = refine_mst_placement(
        extracted_terminals,
        extracted_foscs,
        ont_geojson_small,
        cable_geojson_small,
        config
    )
    
    print()
    print("=" * 80)
    print("CREATING DROP CABLES")
    print("=" * 80)
    print()
    
    # Create drop cables
    drop_cables = create_drop_cables(terminals_after, ont_geojson_small)
    print(f"  ✓ Created {len(drop_cables)} drop cables")
    
    # Create visualization
    print()
    print("Creating visualization...")
    
    vis_features = []
    
    # Center point
    center_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [center_utm[0], center_utm[1]]
        },
        "properties": {
            "name": "Center Point",
            "marker-color": "#FF0000",
            "marker-size": "large",
            "marker-symbol": "star"
        }
    }
    vis_features.append(center_feature)
    
    # Radius circle
    import math
    circle_points = []
    for angle in range(0, 360, 10):
        angle_rad = math.radians(angle)
        x = center_utm[0] + radius_m * math.cos(angle_rad)
        y = center_utm[1] + radius_m * math.sin(angle_rad)
        circle_points.append([x, y])
    circle_points.append(circle_points[0])
    
    radius_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": circle_points
        },
        "properties": {
            "name": "5km Radius",
            "stroke": "#FF0000",
            "stroke-width": 2,
            "stroke-opacity": 0.3
        }
    }
    vis_features.append(radius_feature)
    
    # Cables
    vis_features.extend(cable_geojson_small.get("features", []))
    
    # Drop cables
    vis_features.extend(drop_cables)
    
    # ONTs
    vis_features.extend(ont_geojson_small.get("features", []))
    
    # Terminals
    for terminal in terminals_after:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            term_type = terminal.get("type", "Terminal")
            color = "#800080" if term_type == "MST" else "#FF00FF"
            
            term_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [term_pos_utm[0], term_pos_utm[1]]
                },
                "properties": {
                    "id": terminal.get("terminal_id", ""),
                    "type": term_type,
                    "marker-color": color,
                    "marker-size": "medium",
                    "marker-symbol": "triangle" if term_type == "MST" else "circle"
                }
            }
            vis_features.append(term_feature)
    
    # FOSCs
    for fosc in foscs_after:
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
                    "marker-color": "#0000FF",
                    "marker-size": "medium",
                    "marker-symbol": "circle"
                }
            }
            vis_features.append(fosc_feature)
    
    vis_geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:EPSG::32617"
            }
        },
        "features": vis_features
    }
    
    with open("test_output/unified_area_complete.geojson", "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    print(f"✓ Saved visualization: test_output/unified_area_complete.geojson")
    print(f"  Total features: {len(vis_features)}")
    print(f"  - {len(drop_cables)} drop cables")
    print(f"  - {len(ont_geojson_small.get('features', []))} ONTs")
    print(f"  - {len(terminals_after)} terminals")
    print(f"  - {len(foscs_after)} FOSCs")
    print(f"  - {len(cable_geojson_small.get('features', []))} cables")
    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
