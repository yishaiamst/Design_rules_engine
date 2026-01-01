#!/usr/bin/env python3
"""
Direct test of Phase 3b on T0000356 using real data from full pipeline.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase3b_refine_mst_placement import refine_mst_placement

def main():
    print("=" * 80)
    print("DIRECT TEST: T0000356 Phase 3b Fix")
    print("=" * 80)
    print()
    
    # Load terminal data from summary
    print("Loading terminal data...")
    with open("test_output/terminal_placement_summary.json") as f:
        terminal_data = json.load(f)
    
    terminals_full = terminal_data.get("terminals", [])
    print(f"  Loaded {len(terminals_full)} terminals")
    
    # Find T0000356
    t0000356 = None
    for term in terminals_full:
        if term.get("terminal_id") == "T0000356":
            t0000356 = term
            break
    
    if not t0000356:
        print("✗ T0000356 not found")
        return
    
    print()
    print("T0000356 Details:")
    print(f"  Position: {t0000356.get('position')}")
    print(f"  Type: {t0000356.get('type')}")
    print(f"  ONT count: {t0000356.get('ont_count')}")
    print(f"  Connected ONTs: {t0000356.get('connected_onts')}")
    
    # Calculate drop cable lengths
    ont_geojson = load_geojson("ONT.geojson")
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                onts_by_id[ont_id] = (coords[0], coords[1])
    
    terminal_pos = tuple(t0000356.get("position"))
    drop_lengths = []
    ont_positions = []
    
    for ont_id in t0000356.get("connected_onts", []):
        if ont_id in onts_by_id:
            ont_pos = onts_by_id[ont_id]
            dist = euclidean_distance(terminal_pos[0], terminal_pos[1], ont_pos[0], ont_pos[1])
            drop_lengths.append(dist)
            ont_positions.append(ont_pos)
    
    if drop_lengths:
        avg_drop = sum(drop_lengths) / len(drop_lengths)
        max_drop = max(drop_lengths)
        total_drop = sum(drop_lengths)
        
        print()
        print("Drop Cable Analysis:")
        print(f"  Lengths: {[f'{d:.1f}m' for d in drop_lengths]}")
        print(f"  Average: {avg_drop:.1f}m")
        print(f"  Max: {max_drop:.1f}m")
        print(f"  Total: {total_drop:.1f}m")
        print(f"  Meets long drop criteria (avg>100m OR max>150m): {avg_drop > 100.0 or max_drop > 150.0}")
    
    # Extract area around T0000356
    print()
    print("Extracting area around T0000356...")
    reference_pos = terminal_pos
    buffer_m = 2000.0
    
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
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
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
    
    # Extract terminals
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
    
    print(f"  Extracted: {len(extracted_onts)} ONTs, {len(extracted_cables)} cables, {len(extracted_terminals)} terminals")
    
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
    
    # Load FOSCs from full dataset
    print()
    print("Loading FOSCs...")
    with open("test_output/fosc_placement_summary.json") as f:
        fosc_data = json.load(f)
    
    foscs_full = fosc_data.get("foscs", [])
    print(f"  Loaded {len(foscs_full)} FOSCs from full dataset")
    
    # Extract FOSCs in area
    extracted_foscs = []
    for fosc in foscs_full:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            dist = euclidean_distance(
                reference_pos[0], reference_pos[1],
                fosc_pos[0], fosc_pos[1]
            )
            if dist <= buffer_m * 2:  # Larger buffer for FOSCs (4km)
                extracted_foscs.append(fosc)
    
    print(f"  Extracted {len(extracted_foscs)} FOSCs in area")
    foscs = extracted_foscs
    
    # Run Phase 3b
    print()
    print("=" * 80)
    print("RUNNING PHASE 3B")
    print("=" * 80)
    print()
    
    config = load_config("design_config.json")
    
    print(f"Before Phase 3b:")
    print(f"  Terminals: {len(extracted_terminals)}")
    mst_before = [t for t in extracted_terminals if t.get("type") == "MST"]
    print(f"  MSTs: {len(mst_before)}")
    print(f"  T0000356: {t0000356.get('type')}, {len(t0000356.get('connected_onts', []))} ONTs")
    
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
    print(f"  Summary: {summary}")
    
    # Check T0000356
    t0000356_after = [t for t in terminals_after if t.get("terminal_id") == "T0000356"]
    if t0000356_after:
        t = t0000356_after[0]
        print(f"  T0000356 after: {len(t.get('connected_onts', []))} ONTs")
        if len(t.get('connected_onts', [])) < len(t0000356.get('connected_onts', [])):
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
    else:
        print()
        print("⚠️  No new MSTs created")
        print("  Possible reasons:")
        print("    - T0000356 doesn't meet long drop criteria")
        print("    - ONTs don't form cluster (within 200m)")
        print("    - No nearby FOSC (within 1km)")
        print("    - No nearby cable (within 200m)")
        print("    - Savings not significant (<100m)")

if __name__ == "__main__":
    main()
