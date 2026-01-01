#!/usr/bin/env python3
"""
Test script to extract area based on unified coordinates.
Uses a specific lat/lon point (WGS84) and converts to UTM for all operations.
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
    print("⚠️  WARNING: pyproj not available. Using manual conversion (less accurate).")
    print("   Install with: pip install pyproj")


def latlon_to_utm(lat, lon, zone=17):
    """
    Convert WGS84 lat/lon to UTM Zone 17N (EPSG:32617).
    """
    if PYPROJ_AVAILABLE:
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:32617", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return (easting, northing)
    else:
        # Manual approximation (less accurate)
        # UTM Zone 17N: central meridian = -81°
        import math
        k0 = 0.9996
        a = 6378137.0
        e2 = 0.00669438
        
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        central_meridian = math.radians(-81.0)  # Zone 17
        
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
    radius_m=4000.0
):
    """
    Extract area based on center coordinates (WGS84) and radius.
    All coordinates are converted to UTM for consistency.
    """
    print("=" * 80)
    print("EXTRACTING AREA BY UNIFIED COORDINATES")
    print("=" * 80)
    print()
    
    # Convert center point to UTM
    center_utm = latlon_to_utm(center_lat, center_lon)
    print(f"Center point (WGS84): ({center_lat:.6f}, {center_lon:.6f})")
    print(f"Center point (UTM Zone 17N): ({center_utm[0]:.2f}, {center_utm[1]:.2f})")
    print(f"Extraction radius: {radius_m/1000:.1f}km ({radius_m:.0f}m)")
    print()
    print("Extracting all features within radius (ignoring specific IDs)...")
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
            # Coordinates should already be in UTM
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
        
        # Check if any point on cable is within radius
        near_center = False
        for coord in coords_list:
            if len(coord) >= 2:
                # Coordinates should already be in UTM
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
            if dist <= radius_m * 1.5:  # Larger radius for FOSCs
                extracted_foscs.append(fosc)
    
    print(f"  ✓ Extracted {len(extracted_foscs)} FOSCs")
    
    # Create GeoJSON for extracted area
    ont_geojson_small = create_feature_collection(extracted_onts)
    cable_geojson_small = create_feature_collection(extracted_cables)
    
    return ont_geojson_small, cable_geojson_small, extracted_terminals, extracted_foscs, center_utm


def main():
    print("=" * 80)
    print("TEST: Unified Coordinate System Extraction")
    print("=" * 80)
    print()
    
    # Center point from user (WGS84)
    center_lat = 45.731437
    center_lon = -82.401057
    radius_m = 5000.0  # 5km
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Load terminals and FOSCs
    print("Loading terminals and FOSCs...")
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
    
    if not ont_geojson_small:
        print("✗ Failed to extract area")
        return
    
    # Save extracted area
    with open("test_output/unified_area_onts.geojson", "w") as f:
        json.dump(ont_geojson_small, f, indent=2)
    with open("test_output/unified_area_cables.geojson", "w") as f:
        json.dump(cable_geojson_small, f, indent=2)
    print()
    print("✓ Saved extracted area")
    
    # Run Phase 3b
    print()
    print("=" * 80)
    print("RUNNING PHASE 3B")
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
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Before Phase 3b:")
    print(f"  Terminals: {len(extracted_terminals)}")
    print(f"  FOSCs: {len(extracted_foscs)}")
    print()
    print(f"After Phase 3b:")
    print(f"  Terminals: {len(terminals_after)}")
    print(f"  FOSCs: {len(foscs_after)}")
    print(f"  New MSTs: {len(new_msts)}")
    print()
    
    # Create simple visualization
    print("Creating visualization...")
    
    vis_features = []
    
    # Add center point marker
    center_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [center_utm[0], center_utm[1]]
        },
        "properties": {
            "name": "Center Point (45.731437, -82.401057)",
            "marker-color": "#FF0000",
            "marker-size": "large",
            "marker-symbol": "star"
        }
    }
    vis_features.append(center_feature)
    
    # Add radius circle (approximate)
    import math
    circle_points = []
    for angle in range(0, 360, 10):
        angle_rad = math.radians(angle)
        x = center_utm[0] + radius_m * math.cos(angle_rad)
        y = center_utm[1] + radius_m * math.sin(angle_rad)
        circle_points.append([x, y])
    circle_points.append(circle_points[0])  # Close the circle
    
    radius_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": circle_points
        },
        "properties": {
            "name": f"5km Radius",
            "stroke": "#FF0000",
            "stroke-width": 2,
            "stroke-opacity": 0.5
        }
    }
    vis_features.append(radius_feature)
    
    # Add extracted cables
    vis_features.extend(cable_geojson_small.get("features", []))
    
    # Add extracted ONTs
    vis_features.extend(ont_geojson_small.get("features", []))
    
    # Add terminals
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
    
    # Add FOSCs
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
    
    with open("test_output/unified_area_visualization.geojson", "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    print(f"✓ Saved visualization: test_output/unified_area_visualization.geojson")
    print(f"  Total features: {len(vis_features)}")
    print(f"  Coordinate system: UTM Zone 17N (EPSG:32617)")
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print(f"Center point (UTM): {center_utm}")
    print(f"All coordinates are in UTM Zone 17N (EPSG:32617)")


if __name__ == "__main__":
    main()
