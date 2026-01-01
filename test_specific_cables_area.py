#!/usr/bin/env python3
"""
Test Phase 3b on area defined by specific cables and terminals.
Cables: 48FOC/F1000410/F1000414, 96FOC/F1000396/F1000402
Terminals: T0000356, T0003830
ONT: O1007818
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase3b_refine_mst_placement import refine_mst_placement

def extract_area_by_cables_and_terminals(
    ont_geojson,
    fiber_cable_geojson,
    terminals_full,
    foscs_full,
    target_cable_ids=["48FOC/F1000410/F1000414", "96FOC/F1000396/F1000402"],
    target_terminal_ids=["T0000356", "T0003830"],
    buffer_m=2000.0
):
    """Extract area based on specific cables and terminals."""
    print("=" * 80)
    print("EXTRACTING AREA BY SPECIFIC CABLES AND TERMINALS")
    print("=" * 80)
    print()
    
    # Find target cables
    target_cables = []
    all_cable_coords = []
    
    for feature in fiber_cable_geojson.get("features", []):
        props = feature.get("properties", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        if any(target_id in cable_id for target_id in target_cable_ids):
            geometry = feature.get("geometry", {})
            coords = []
            if geometry.get("type") == "LineString":
                coords = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiLineString":
                for line in geometry.get("coordinates", []):
                    coords.extend(line)
            
            if coords:
                target_cables.append(feature)
                all_cable_coords.extend([c for c in coords if len(c) >= 2])
                print(f"  ✓ Found cable: {cable_id}")
    
    if not target_cables:
        print("✗ Target cables not found")
        return None, None, None, None
    
    print(f"  Found {len(target_cables)} target cables")
    
    # Find target terminals
    target_terminals = []
    terminal_positions = []
    
    for terminal in terminals_full:
        term_id = terminal.get("terminal_id", "")
        if term_id in target_terminal_ids:
            target_terminals.append(terminal)
            term_pos = terminal.get("position")
            if term_pos:
                terminal_positions.append(term_pos)
                print(f"  ✓ Found terminal: {term_id} at {term_pos}")
    
    if not target_terminals:
        print("✗ Target terminals not found")
        return None, None, None, None
    
    # Create bounding area from cables and terminals
    all_points = all_cable_coords + terminal_positions
    if not all_points:
        print("✗ No points found")
        return None, None, None, None
    
    # Calculate bounding box
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    center = (center_x, center_y)
    
    # Expand by buffer
    radius = max(
        (max_x - min_x) / 2,
        (max_y - min_y) / 2
    ) + buffer_m
    
    print(f"  Area center: {center}")
    print(f"  Extraction radius: {radius:.1f}m")
    
    # Extract ONTs - include those connected to target terminals
    target_ont_ids = set()
    for terminal in target_terminals:
        target_ont_ids.update(terminal.get("connected_onts", []))
    
    extracted_onts = []
    extracted_ont_ids = set()
    
    # First, add ONTs connected to target terminals (CRITICAL)
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        ont_id = props.get("ID") or props.get("id", "")
        if ont_id in target_ont_ids:
            extracted_onts.append(feature)
            extracted_ont_ids.add(ont_id)
    
    # Then add ONTs within geographic radius
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        ont_id = props.get("ID") or props.get("id", "")
        if ont_id in extracted_ont_ids:
            continue  # Already added
        
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                dist = euclidean_distance(center[0], center[1], coords[0], coords[1])
                if dist <= radius:
                    extracted_onts.append(feature)
                    extracted_ont_ids.add(ont_id)
    
    print(f"  ✓ Extracted {len(extracted_onts)} ONTs ({len(target_ont_ids)} from target terminals + {len(extracted_ont_ids) - len(target_ont_ids)} from area)")
    
    # Extract cables (target cables + nearby + near terminals)
    extracted_cables = list(target_cables)  # Always include target cables
    terminal_buffer = 1000.0  # 1km buffer around terminals
    
    for feature in fiber_cable_geojson.get("features", []):
        if feature in target_cables:
            continue  # Already included
        
        geometry = feature.get("geometry", {})
        coords = []
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if not coords:
            continue
        
        # Check if cable is near any target terminal (CRITICAL for T0000356)
        near_terminal = False
        for terminal in target_terminals:
            term_pos = terminal.get("position")
            if not term_pos:
                continue
            term_pos_tuple = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            
            for coord in coords:
                if len(coord) >= 2:
                    dist = euclidean_distance(term_pos_tuple[0], term_pos_tuple[1], coord[0], coord[1])
                    if dist <= terminal_buffer:
                        near_terminal = True
                        break
            if near_terminal:
                break
        
        if near_terminal:
            extracted_cables.append(feature)
            continue
        
        # Also check if cable is near area center
        near_area = False
        for coord in coords:
            if len(coord) >= 2:
                dist = euclidean_distance(center[0], center[1], coord[0], coord[1])
                if dist <= radius:
                    near_area = True
                    break
        
        if near_area:
            extracted_cables.append(feature)
    
    print(f"  ✓ Extracted {len(extracted_cables)} cables ({len(target_cables)} target + {len(extracted_cables) - len(target_cables)} nearby)")
    
    # Extract terminals
    extracted_terminals = list(target_terminals)  # Always include target terminals
    
    for terminal in terminals_full:
        if terminal in target_terminals:
            continue  # Already included
        
        term_pos = terminal.get("position")
        if term_pos:
            dist = euclidean_distance(center[0], center[1], term_pos[0], term_pos[1])
            if dist <= radius:
                extracted_terminals.append(terminal)
    
    print(f"  ✓ Extracted {len(extracted_terminals)} terminals ({len(target_terminal_ids)} target + {len(extracted_terminals) - len(target_terminal_ids)} nearby)")
    
    # Extract FOSCs
    extracted_foscs = []
    for fosc in foscs_full:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            dist = euclidean_distance(center[0], center[1], fosc_pos[0], fosc_pos[1])
            if dist <= radius * 1.5:  # Larger radius for FOSCs
                extracted_foscs.append(fosc)
    
    print(f"  ✓ Extracted {len(extracted_foscs)} FOSCs")
    
    # Check T0000356
    t0000356 = [t for t in extracted_terminals if t.get("terminal_id") == "T0000356"]
    if t0000356:
        t = t0000356[0]
        print(f"  ✓ T0000356: {len(t.get('connected_onts', []))} ONTs")
    
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
    print("TEST: Phase 3b on Specific Cables/Terminals Area")
    print("=" * 80)
    print()
    
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
    
    # Extract area
    print()
    ont_geojson_small, cable_geojson_small, extracted_terminals, extracted_foscs = extract_area_by_cables_and_terminals(
        ont_geojson,
        fiber_cable_geojson,
        terminals_full,
        foscs_full,
        target_cable_ids=["96FOC/F1000402/F1000401", "48FOC/F1000410/F1000414", "48FOC/F1000402/F1000410"],
        target_terminal_ids=["T0000356", "T0003830"],
        buffer_m=2000.0
    )
    
    if not ont_geojson_small:
        print("✗ Failed to extract area")
        return
    
    # Save extracted area
    with open("test_output/specific_area_onts.geojson", "w") as f:
        json.dump(ont_geojson_small, f, indent=2)
    with open("test_output/specific_area_cables.geojson", "w") as f:
        json.dump(cable_geojson_small, f, indent=2)
    print()
    print("✓ Saved extracted area")
    
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
        # Calculate drop lengths
        from utils.spatial_utils import euclidean_distance
        ont_geojson_full = load_geojson("ONT.geojson")
        onts_by_id = {}
        for feature in ont_geojson_full.get("features", []):
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            ont_id = props.get("ID") or props.get("id", "")
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if coords and len(coords) >= 2:
                    onts_by_id[ont_id] = (coords[0], coords[1])
        
        terminal_pos = tuple(t.get("position"))
        drop_lengths = []
        for ont_id in t.get("connected_onts", []):
            if ont_id in onts_by_id:
                ont_pos = onts_by_id[ont_id]
                dist = euclidean_distance(terminal_pos[0], terminal_pos[1], ont_pos[0], ont_pos[1])
                drop_lengths.append(dist)
        
        if drop_lengths:
            avg_drop = sum(drop_lengths) / len(drop_lengths)
            max_drop = max(drop_lengths)
            print(f"    Drop cables: avg {avg_drop:.1f}m, max {max_drop:.1f}m")
    
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
    else:
        print()
        print("⚠️  No new MSTs created")
    
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
    
    with open("test_output/specific_area_visualization.geojson", "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    print(f"✓ Saved visualization: test_output/specific_area_visualization.geojson")
    print(f"  Total features: {len(features)}")
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
