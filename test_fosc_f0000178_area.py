#!/usr/bin/env python3
"""
Test Phase 3b on area around FOSC F0000178 (4km radius).
This should capture T0000356 and the ONT cluster that needs an MST.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase3b_refine_mst_placement import refine_mst_placement

def extract_area_around_fosc(
    ont_geojson,
    fiber_cable_geojson,
    terminals_full,
    foscs_full,
        fosc_id="F0000178",
        buffer_m=15000.0  # 15km radius to include T0000356 and surrounding area
):
    """Extract area around FOSC."""
    print("=" * 80)
    print(f"EXTRACTING AREA AROUND FOSC {fosc_id} ({buffer_m/1000:.1f}km radius)")
    print("=" * 80)
    print()
    
    # Note: buffer_m parameter is used, not hardcoded
    
    # Find FOSC - try to get position from cable if FOSC position seems wrong
    fosc = None
    fosc_pos = None
    
    # First, try to find FOSC position from cable endpoints
    # Look for cable connecting F0000178 to T0000356
    fosc_pos_from_cable = None
    if fosc_id == "F0000178":
        # Try to find F0000178 position from cable
        for feature in fiber_cable_geojson.get("features", []):
            props = feature.get("properties", {})
            cable_id = props.get("ID") or props.get("id", "")
            if "F0000178" in cable_id and "T0000356" in cable_id:
                geometry = feature.get("geometry", {})
                coords = []
                if geometry.get("type") == "LineString":
                    coords = geometry.get("coordinates", [])
                elif geometry.get("type") == "MultiLineString":
                    for line in geometry.get("coordinates", []):
                        coords.extend(line)
                
                if coords and len(coords) >= 2:
                    # F0000178 should be at the end that's NOT T0000356
                    # T0000356 is at (410000.99785385263, 5073774.324154561)
                    t0000356_pos = (410000.99785385263, 5073774.324154561)
                    start = coords[0]
                    end = coords[-1]
                    
                    dist_to_start = euclidean_distance(t0000356_pos[0], t0000356_pos[1], start[0], start[1])
                    dist_to_end = euclidean_distance(t0000356_pos[0], t0000356_pos[1], end[0], end[1])
                    
                    # F0000178 is at the end farther from T0000356
                    if dist_to_start > dist_to_end:
                        fosc_pos_from_cable = start
                    else:
                        fosc_pos_from_cable = end
                    print(f"  Found F0000178 position from cable: {fosc_pos_from_cable}")
                break
    
    # Find FOSC in list
    for f in foscs_full:
        if f.get("fosc_id") == fosc_id:
            fosc = f
            fosc_pos = f.get("position")
            break
    
    # Use position from cable if available (more accurate)
    if fosc_pos_from_cable:
        fosc_pos = fosc_pos_from_cable
        if fosc:
            fosc["position"] = fosc_pos  # Update FOSC position
        print(f"  Using FOSC position from cable endpoint")
    
    if not fosc_pos:
        print(f"✗ FOSC {fosc_id} not found")
        return None, None, None, None
    
    fosc_pos_tuple = tuple(fosc_pos) if isinstance(fosc_pos, list) else fosc_pos
    print(f"✓ Using FOSC {fosc_id} at {fosc_pos_tuple}")
    
    # Extract ONTs
    extracted_onts = []
    for feature in ont_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                dist = euclidean_distance(
                    fosc_pos_tuple[0], fosc_pos_tuple[1],
                    coords[0], coords[1]
                )
                if dist <= buffer_m:
                    extracted_onts.append(feature)
    
    print(f"✓ Extracted {len(extracted_onts)} ONTs")
    
    # Extract cables
    extracted_cables = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        coords = []
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        near_fosc = False
        if coords:
            for coord in coords:
                if len(coord) >= 2:
                    dist = euclidean_distance(
                        fosc_pos_tuple[0], fosc_pos_tuple[1],
                        coord[0], coord[1]
                    )
                    if dist <= buffer_m:
                        near_fosc = True
                        break
        
        if near_fosc:
            extracted_cables.append(feature)
    
    print(f"✓ Extracted {len(extracted_cables)} cables")
    
    # Extract terminals
    extracted_terminals = []
    for terminal in terminals_full:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_tuple = tuple(term_pos) if isinstance(term_pos, list) else term_pos
            dist = euclidean_distance(
                fosc_pos_tuple[0], fosc_pos_tuple[1],
                term_pos_tuple[0], term_pos_tuple[1]
            )
            if dist <= buffer_m:
                extracted_terminals.append(terminal)
    
    print(f"✓ Extracted {len(extracted_terminals)} terminals")
    
    # Extract FOSCs
    extracted_foscs = []
    for f in foscs_full:
        f_pos = f.get("position")
        if f_pos:
            f_pos_tuple = tuple(f_pos) if isinstance(f_pos, list) else f_pos
            dist = euclidean_distance(
                fosc_pos_tuple[0], fosc_pos_tuple[1],
                f_pos_tuple[0], f_pos_tuple[1]
            )
            if dist <= buffer_m:
                extracted_foscs.append(f)
    
    print(f"✓ Extracted {len(extracted_foscs)} FOSCs")
    
    # Check for T0000356
    t0000356 = [t for t in extracted_terminals if t.get("terminal_id") == "T0000356"]
    if t0000356:
        t = t0000356[0]
        t_pos = t.get("position")
        dist_to_fosc = euclidean_distance(fosc_pos_tuple[0], fosc_pos_tuple[1], t_pos[0], t_pos[1])
        print(f"  ✓ T0000356 is in area: {len(t.get('connected_onts', []))} ONTs, {dist_to_fosc:.1f}m from FOSC")
    else:
        print(f"  ✗ T0000356 is NOT in {buffer_m/1000:.1f}km radius")
        # Check actual distance
        for t in terminals_full:
            if t.get("terminal_id") == "T0000356":
                t_pos = t.get("position")
                if t_pos:
                    dist = euclidean_distance(fosc_pos_tuple[0], fosc_pos_tuple[1], t_pos[0], t_pos[1])
                    print(f"    Actual distance: {dist:.1f}m ({dist/1000:.2f}km)")
                    break
    
    # Create GeoJSONs
    ont_geojson_small = {
        "type": "FeatureCollection",
        "crs": ont_geojson.get("crs"),
        "features": extracted_onts
    }
    
    cable_geojson_small = {
        "type": "FeatureCollection",
        "crs": fiber_cable_geojson.get("crs"),
        "features": extracted_cables
    }
    
    return ont_geojson_small, cable_geojson_small, extracted_terminals, extracted_foscs

def main():
    print("=" * 80)
    print("TEST: Phase 3b on FOSC F0000178 Area (4km radius)")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Load terminals and FOSCs from full dataset
    print("Loading terminals and FOSCs from full dataset...")
    with open("test_output/terminal_placement_summary.json") as f:
        terminal_data = json.load(f)
    terminals_full = terminal_data.get("terminals", [])
    
    with open("test_output/fosc_placement_summary.json") as f:
        fosc_data = json.load(f)
    foscs_full = fosc_data.get("foscs", [])
    
    print(f"  Loaded {len(terminals_full)} terminals, {len(foscs_full)} FOSCs")
    
    # Extract area around F0000178
    print()
    ont_geojson_small, cable_geojson_small, extracted_terminals, extracted_foscs = extract_area_around_fosc(
        ont_geojson,
        fiber_cable_geojson,
        terminals_full,
        foscs_full,
        fosc_id="F0000178",
        buffer_m=4000.0
    )
    
    if not ont_geojson_small:
        print("✗ Failed to extract area")
        return
    
    # Save extracted area
    with open("test_output/f0000178_area_onts.geojson", "w") as f:
        json.dump(ont_geojson_small, f, indent=2)
    with open("test_output/f0000178_area_cables.geojson", "w") as f:
        json.dump(cable_geojson_small, f, indent=2)
    print()
    print("✓ Saved extracted area to test_output/")
    
    # Run Phase 3b
    print()
    print("=" * 80)
    print("RUNNING PHASE 3B")
    print("=" * 80)
    print()
    
    print(f"Before Phase 3b:")
    print(f"  Terminals: {len(extracted_terminals)}")
    mst_before = [t for t in extracted_terminals if t.get("type") == "MST"]
    print(f"  MSTs: {len(mst_before)}")
    
    t0000356 = [t for t in extracted_terminals if t.get("terminal_id") == "T0000356"]
    if t0000356:
        t = t0000356[0]
        print(f"  T0000356: {t.get('type')}, {len(t.get('connected_onts', []))} ONTs")
    
    terminals_after, foscs_after, new_msts, summary = refine_mst_placement(
        extracted_terminals,
        extracted_foscs,
        ont_geojson_small,
        cable_geojson_small,
        config
    )
    
    print()
    print(f"After Phase 3b:")
    print(f"  Terminals: {len(terminals_after)}")
    mst_after = [t for t in terminals_after if t.get("type") == "MST"]
    print(f"  MSTs: {len(mst_after)}")
    print(f"  New MSTs: {len(new_msts)}")
    print(f"  Summary: {summary}")
    
    # Check T0000356
    t0000356_after = [t for t in terminals_after if t.get("terminal_id") == "T0000356"]
    if t0000356_after:
        t = t0000356_after[0]
        print(f"  T0000356 after: {len(t.get('connected_onts', []))} ONTs")
        if len(t.get('connected_onts', [])) < len(t0000356[0].get('connected_onts', [])):
            print("  ✓ ONTs were reassigned to new MST(s)")
    
    # Show new MSTs
    if new_msts:
        print()
        print("New MSTs created:")
        for mst in new_msts:
            print(f"  {mst.get('terminal_id')}: {mst.get('ont_count')} ONTs")
            print(f"    Position: {mst.get('position')}")
            print(f"    FOSC: {mst.get('connected_fosc_id')}")
            print(f"    Replaces: {mst.get('replaces_terminal_id')}")
            print(f"    Savings: {mst.get('savings_m', 0):.1f}m")
    
    # Create visualization
    print()
    print("Creating visualization...")
    features = []
    
    # Add cables
    for feature in cable_geojson_small.get("features", []):
        features.append(feature)
    
    # Add FOSCs
    for fosc in foscs_after:
        pos = fosc.get("position")
        if pos:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [pos[0], pos[1]]},
                "properties": {
                    "layer": "fosc",
                    "fosc_id": fosc.get("fosc_id"),
                    "marker-color": "#FF0000",
                    "marker-size": "large",
                    "marker-symbol": "circle"
                }
            })
    
    # Add terminals
    for terminal in terminals_after:
        pos = terminal.get("position")
        term_id = terminal.get("terminal_id")
        term_type = terminal.get("type", "")
        
        if pos:
            if term_type == "MST":
                color = "#800080"
                symbol = "triangle"
            else:
                color = "#0000FF"
                symbol = "square"
            
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [pos[0], pos[1]]},
                "properties": {
                    "layer": "terminal",
                    "terminal_id": term_id,
                    "terminal_type": term_type,
                    "marker-color": color,
                    "marker-size": "medium",
                    "marker-symbol": symbol,
                    "ont_count": len(terminal.get("connected_onts", []))
                }
            })
    
    # Add ONTs
    for feature in ont_geojson_small.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                **props,
                "layer": "ont",
                "marker-color": "#FFFF00",
                "marker-size": "small",
                "marker-symbol": "dot"
            }
        })
    
    vis_geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:EPSG::32617"}
        },
        "features": features
    }
    
    with open("test_output/f0000178_area_visualization.geojson", "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    print(f"✓ Saved visualization: test_output/f0000178_area_visualization.geojson")
    print(f"  Total features: {len(features)}")
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
