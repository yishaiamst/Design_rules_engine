#!/usr/bin/env python3
"""
Apply all optimization rules to the unified coordinate area.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase3c_optimization_rules import apply_all_optimization_rules

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


def main():
    print("=" * 80)
    print("APPLY ALL OPTIMIZATION RULES")
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
    
    # Use fixed FOSCs if available, otherwise use original
    try:
        with open("test_output/fixed_foscs.json") as f:
            foscs = json.load(f)
        print("  Using fixed FOSCs")
    except FileNotFoundError:
        with open("test_output/fosc_placement_summary.json") as f:
            fosc_data = json.load(f)
        foscs = fosc_data.get("foscs", [])
        print("  Using original FOSCs")
    
    # Extract area
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
    
    # Also include restored FOSCs from fix_fosc_mst_placement if available
    try:
        from fix_fosc_mst_placement import restore_foscs_at_junctions
        # This will add FOSCs at cable junctions
        new_foscs = restore_foscs_at_junctions(cables_list, extracted_foscs, extracted_terminals)
        extracted_foscs.extend(new_foscs)
        print(f"  Added {len(new_foscs)} restored FOSCs at junctions")
    except:
        pass
    
    print(f"  Extracted {len(extracted_cables)} cables, {len(extracted_terminals)} terminals, {len(extracted_foscs)} FOSCs")
    print()
    
    # Apply all optimization rules
    optimized_terminals, optimized_foscs, summary = apply_all_optimization_rules(
        extracted_terminals,
        extracted_foscs,
        cables_list,
        ont_geojson,
        config
    )
    
    # Save results
    with open("test_output/rules_optimized_terminals.json", "w") as f:
        json.dump(optimized_terminals, f, indent=2)
    with open("test_output/rules_optimized_foscs.json", "w") as f:
        json.dump(optimized_foscs, f, indent=2)
    with open("test_output/rules_optimization_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print("✓ Saved optimized terminals and FOSCs")
    print()
    
    # Create visualization
    print("Creating visualization...")
    # Use the existing visualization script
    import subprocess
    subprocess.run(["python3", "create_complete_visualization.py"], check=False)
    
    print()
    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print()
    print()
    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print()
    print(f"Terminals: {len(optimized_terminals)}")
    print(f"  - MSTs: {len([t for t in optimized_terminals if t.get('type') == 'MST'])}")
    print(f"  - Aerial: {len([t for t in optimized_terminals if t.get('type') == 'Aerial Terminal'])}")
    print(f"FOSCs: {len(optimized_foscs)}")
    print()


if __name__ == "__main__":
    main()
