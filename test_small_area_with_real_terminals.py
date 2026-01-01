#!/usr/bin/env python3
"""
Test Phase 3b on small area using REAL terminals from full dataset.
This ensures we test with actual T0000356 and see if Phase 3b fixes it.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase3b_refine_mst_placement import refine_mst_placement

def load_full_terminals():
    """Load terminals from full dataset."""
    # Load from the terminal GeoJSON that was generated
    with open("test_output/terminal.geojson") as f:
        terminal_geojson = json.load(f)
    
    terminals = []
    for feature in terminal_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        terminal_id = props.get("ID") or props.get("id", "")
        coords = geometry.get("coordinates", [])
        
        if terminal_id and coords and len(coords) >= 2:
            # Reconstruct terminal dict (simplified)
            terminals.append({
                "terminal_id": terminal_id,
                "type": props.get("type", "Aerial Terminal"),  # May need to infer
                "position": (coords[0], coords[1]),
                "connected_onts": []  # Will need to populate from drop cables
            })
    
    return terminals

def extract_area_with_real_terminals(
    ont_geojson,
    fiber_cable_geojson,
    terminals_full,
    reference_pos,
    buffer_m=3000.0
):
    """Extract area including real terminals."""
    # Extract ONTs
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
        
        if near_reference:
            extracted_cables.append(feature)
    
    # Extract terminals in area
    extracted_terminals = []
    for terminal in terminals_full:
        term_pos = terminal.get("position")
        if term_pos:
            dist = euclidean_distance(
                reference_pos[0], reference_pos[1],
                term_pos[0], term_pos[1]
            )
            if dist <= buffer_m:
                extracted_terminals.append(terminal)
    
    return extracted_onts, extracted_cables, extracted_terminals

def main():
    print("=" * 80)
    print("SMALL AREA TEST WITH REAL TERMINALS")
    print("=" * 80)
    print()
    
    # Find reference ONT position
    ont_geojson = load_geojson("ONT.geojson")
    reference_pos = None
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        if (props.get("ID") or props.get("id")) == "O1007818":
            geometry = feature.get("geometry", {})
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if coords and len(coords) >= 2:
                    reference_pos = (coords[0], coords[1])
                    print(f"✓ Reference ONT O1007818 at {reference_pos}")
                    break
    
    if not reference_pos:
        print("✗ Reference ONT not found")
        return
    
    # Load full terminals
    print("Loading terminals from full dataset...")
    terminals_full = load_full_terminals()
    print(f"  Loaded {len(terminals_full)} terminals")
    
    # Find T0000356
    t0000356 = [t for t in terminals_full if t.get("terminal_id") == "T0000356"]
    if t0000356:
        t = t0000356[0]
        print(f"  ✓ Found T0000356 at {t.get('position')}")
    else:
        print("  ✗ T0000356 not found in full dataset")
    
    # Extract area
    print()
    print("Extracting area...")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    extracted_onts, extracted_cables, extracted_terminals = extract_area_with_real_terminals(
        ont_geojson,
        fiber_cable_geojson,
        terminals_full,
        reference_pos,
        buffer_m=3000.0
    )
    
    print(f"  Extracted: {len(extracted_onts)} ONTs, {len(extracted_cables)} cables, {len(extracted_terminals)} terminals")
    
    # Check if T0000356 is in extracted terminals
    t0000356_extracted = [t for t in extracted_terminals if t.get("terminal_id") == "T0000356"]
    if t0000356_extracted:
        t = t0000356_extracted[0]
        print(f"  ✓ T0000356 is in extracted area")
        print(f"    Position: {t.get('position')}")
        print(f"    Type: {t.get('type')}")
        print(f"    ONTs: {len(t.get('connected_onts', []))}")
    else:
        print("  ✗ T0000356 not in extracted area")
    
    # Create GeoJSONs for extracted area
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
    
    # Load FOSCs from full dataset (simplified - just get ones in area)
    print()
    print("Loading FOSCs...")
    # For now, create empty FOSC list - Phase 3b will work with terminals
    foscs = []
    
    # Run Phase 3b on extracted area
    print()
    print("=" * 80)
    print("RUNNING PHASE 3B ON EXTRACTED AREA")
    print("=" * 80)
    print()
    
    config = load_config("design_config.json")
    
    print(f"Before Phase 3b:")
    print(f"  Terminals: {len(extracted_terminals)}")
    mst_before = [t for t in extracted_terminals if t.get("type") == "MST"]
    print(f"  MSTs: {len(mst_before)}")
    
    if t0000356_extracted:
        t = t0000356_extracted[0]
        print(f"  T0000356: {t.get('type')}, {len(t.get('connected_onts', []))} ONTs")
    
    # Run Phase 3b
    terminals_after, foscs_after, new_msts, summary = refine_mst_placement(
        extracted_terminals,
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
    print(f"  New MSTs: {len(new_msts)}")
    
    # Check T0000356 after
    t0000356_after = [t for t in terminals_after if t.get("terminal_id") == "T0000356"]
    if t0000356_after:
        t = t0000356_after[0]
        print(f"  T0000356 after: {len(t.get('connected_onts', []))} ONTs")
    
    # Show new MSTs
    if new_msts:
        print()
        print("New MSTs created:")
        for mst in new_msts:
            print(f"  {mst.get('terminal_id')}: {mst.get('ont_count')} ONTs")
            print(f"    Position: {mst.get('position')}")
            print(f"    Replaces: {mst.get('replaces_terminal_id')}")
            print(f"    Savings: {mst.get('savings_m', 0):.1f}m")

if __name__ == "__main__":
    main()
