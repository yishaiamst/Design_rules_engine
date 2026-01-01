#!/usr/bin/env python3
"""
Test Phase 3b logic on a small area to verify MST placement.
Focus area: Cables 48FOC/F1000410/F1000414, 96FOC/F1000396/F1000402
Terminals: T0000356, T0003830
ONT: O1007818
"""

import json
from utils.geojson_utils import load_geojson, create_feature_collection
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from phases.phase3b_refine_mst_placement import refine_mst_placement

def extract_area_around_reference(
    ont_geojson, 
    fiber_cable_geojson,
    reference_ont_id="O1007818",
    reference_terminal_ids=["T0000356", "T0003830"],
    reference_cable_ids=["48FOC/F1000410/F1000414", "96FOC/F1000396/F1000402"],
    buffer_m=2000.0  # 2km buffer
):
    """Extract a small area around reference points."""
    print("=" * 80)
    print("EXTRACTING SMALL AREA FOR TESTING")
    print("=" * 80)
    print()
    
    # Find reference ONT
    reference_pos = None
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        ont_id = props.get("ID") or props.get("id", "")
        if ont_id == reference_ont_id:
            geometry = feature.get("geometry", {})
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if coords and len(coords) >= 2:
                    reference_pos = (coords[0], coords[1])
                    print(f"✓ Found reference ONT {reference_ont_id} at {reference_pos}")
                    break
    
    if not reference_pos:
        print(f"✗ Reference ONT {reference_ont_id} not found!")
        return None, None
    
    # Extract ONTs within buffer
    extracted_onts = []
    for feature in ont_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                dist = euclidean_distance(
                    reference_pos[0], reference_pos[1],
                    coords[0], coords[1]
                )
                if dist <= buffer_m:
                    extracted_onts.append(feature)
    
    print(f"✓ Extracted {len(extracted_onts)} ONTs within {buffer_m}m")
    
    # Extract cables within buffer
    extracted_cables = []
    for feature in fiber_cable_geojson.get("features", []):
        props = feature.get("properties", {})
        cable_id = props.get("ID") or props.get("id", "")
        geometry = feature.get("geometry", {})
        
        # Check if this is a reference cable
        is_reference = any(ref_id in cable_id for ref_id in reference_cable_ids)
        
        coords = []
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        # Check if cable is near reference point
        near_reference = False
        if coords:
            for coord in coords:
                if len(coord) >= 2:
                    dist = euclidean_distance(
                        reference_pos[0], reference_pos[1],
                        coord[0], coord[1]
                    )
                    if dist <= buffer_m:
                        near_reference = True
                        break
        
        if is_reference or near_reference:
            extracted_cables.append(feature)
            if is_reference:
                print(f"  ✓ Found reference cable: {cable_id}")
    
    print(f"✓ Extracted {len(extracted_cables)} cables within {buffer_m}m")
    
    # Create extracted GeoJSONs
    ont_geojson_extracted = {
        "type": "FeatureCollection",
        "crs": ont_geojson.get("crs"),
        "features": extracted_onts
    }
    
    cable_geojson_extracted = {
        "type": "FeatureCollection",
        "crs": fiber_cable_geojson.get("crs"),
        "features": extracted_cables
    }
    
    return ont_geojson_extracted, cable_geojson_extracted

def main():
    print("=" * 80)
    print("SMALL AREA TEST - Phase 3b MST Placement")
    print("=" * 80)
    print()
    
    # Load full data
    print("Loading full dataset...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Extract small area
    print()
    ont_geojson_small, cable_geojson_small = extract_area_around_reference(
        ont_geojson,
        fiber_cable_geojson,
        reference_ont_id="O1007818",
        reference_terminal_ids=["T0000356", "T0003830"],
        reference_cable_ids=["48FOC/F1000410/F1000414", "96FOC/F1000396/F1000402"],
        buffer_m=3000.0  # Increased to include T0000356
    )
    
    if not ont_geojson_small:
        print("✗ Failed to extract area")
        return
    
    # Save extracted area
    with open("test_output/small_area_onts.geojson", "w") as f:
        json.dump(ont_geojson_small, f, indent=2)
    with open("test_output/small_area_cables.geojson", "w") as f:
        json.dump(cable_geojson_small, f, indent=2)
    print()
    print("✓ Saved extracted area to test_output/")
    
    # Run pipeline on small area
    print()
    print("=" * 80)
    print("RUNNING PIPELINE ON SMALL AREA")
    print("=" * 80)
    print()
    
    pockets = create_community_pockets(ont_geojson_small, cable_geojson_small, config)
    olts, _ = place_olts(pockets, cable_geojson_small, ont_geojson_small, config)
    # Phase 3 places FOSCs as well
    terminals, foscs, _ = place_terminals(ont_geojson_small, cable_geojson_small, olts, config)
    
    print()
    print(f"Before Phase 3b:")
    print(f"  Terminals: {len(terminals)}")
    mst_before = [t for t in terminals if t.get("type") == "MST"]
    print(f"  MSTs: {len(mst_before)}")
    
    # Check for reference terminals
    t0000356 = [t for t in terminals if t.get("terminal_id") == "T0000356"]
    t0003830 = [t for t in terminals if t.get("terminal_id") == "T0003830"]
    
    if t0000356:
        t = t0000356[0]
        print(f"  T0000356: {t.get('type')}, {len(t.get('connected_onts', []))} ONTs, pos: {t.get('position')}")
    if t0003830:
        t = t0003830[0]
        print(f"  T0003830: {t.get('type')}, {len(t.get('connected_onts', []))} ONTs, pos: {t.get('position')}")
    
    # Run Phase 3b
    print()
    print("Running Phase 3b...")
    terminals_after, foscs_after, new_msts, summary = refine_mst_placement(
        terminals,
        foscs,
        ont_geojson_small,
        cable_geojson_small,
        config
    )
    
    print()
    print(f"After Phase 3b:")
    print(f"  Terminals: {len(terminals_after)}")
    mst_after = [t for t in terminals_after if t.get("type") == "MST"]
    print(f"  MSTs: {len(mst_after)}")
    print(f"  New MSTs added: {len(new_msts)}")
    print(f"  Summary: {summary}")
    
    # Check if T0000356 was modified
    t0000356_after = [t for t in terminals_after if t.get("terminal_id") == "T0000356"]
    if t0000356_after:
        t = t0000356_after[0]
        print(f"  T0000356 after: {len(t.get('connected_onts', []))} ONTs")
    
    # Check new MSTs
    if new_msts:
        print()
        print("New MSTs created:")
        for mst in new_msts[:10]:  # Show first 10
            print(f"  {mst.get('terminal_id')}: {mst.get('ont_count')} ONTs")
            print(f"    Position: {mst.get('position')}")
            print(f"    FOSC: {mst.get('connected_fosc_id')}")
            print(f"    Replaces: {mst.get('replaces_terminal_id')}")
            print(f"    Savings: {mst.get('savings_m', 0):.1f}m")
    
    # Create visualization of small area
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
                    "marker-size": "medium",
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
    
    with open("test_output/small_area_visualization.geojson", "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    print(f"✓ Saved visualization: test_output/small_area_visualization.geojson")
    print(f"  Total features: {len(features)}")
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
