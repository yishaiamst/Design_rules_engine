#!/usr/bin/env python3
"""
Debug Phase 6 FOSC Aggregation
Check why FOSC aggregation isn't working
"""

import json
import signal
import sys
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase2_place_foscs import place_foscs_initial
from phases.phase3_place_terminals import place_terminals
from phases.phase6_cable_sizing import size_cables

# Timeout handling (using signal on Unix, skip on Windows/Mac)
try:
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(TimeoutError("Operation timed out")))
    USE_TIMEOUT = True
except (AttributeError, ValueError):
    USE_TIMEOUT = False
    print("  Note: Timeout not available on this platform, will run without timeout")


def debug_fosc_aggregation():
    if USE_TIMEOUT:
        signal.alarm(300)  # 5 minutes
    
    try:
        print("=" * 80)
        print("DEBUGGING PHASE 6 FOSC AGGREGATION")
        print("=" * 80)
        print()
        
        # Load data
        print("Loading data...")
        ont_geojson = load_geojson("ONT.geojson")
        fiber_cable_geojson = load_geojson("fiber cable.geojson")
        config = load_config("design_config.json")
        print("  ✓ Data loaded")
        print()
        
        # Run pipeline (skip if we have cached results)
        print("Running pipeline (Phases 0-3)...")
        print("  Phase 0: Community Pockets...")
        pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
        print(f"    ✓ {len(pockets)} pockets")
        
        print("  Phase 1: OLT Placement...")
        olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
        print(f"    ✓ {len(olts)} OLTs")
        
        print("  Phase 2: FOSC Placement...")
        foscs, _ = place_foscs_initial(fiber_cable_geojson, terminals=None, config=config)
        print(f"    ✓ {len(foscs)} FOSCs")
        
        print("  Phase 3: Terminal Placement...")
        terminals, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, foscs, config)
        print(f"    ✓ {len(terminals)} terminals")
        print()
    
    print(f"  FOSCs placed: {len(foscs)}")
    print(f"  Terminals placed: {len(terminals)}")
    print()
    
    # Extract cables
    cables = []
    for i, feature in enumerate(fiber_cable_geojson.get("features", [])):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cables.append({
                    "index": i,
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    print(f"  Cables loaded: {len(cables)}")
    print()
    
    # Check FOSC positions and nearby cables (OPTIMIZED)
    print("=" * 80)
    print("FOSC POSITION ANALYSIS")
    print("=" * 80)
    print()
    
    tolerance_m = 10.0
    fosc_cable_counts = []
    
    # Build spatial index for cables (endpoints only)
    print("  Building spatial index for cables...")
    cable_endpoints = []  # List of (cable_idx, endpoint_type, position)
    for i, cable in enumerate(cables):
        coords = cable.get("coordinates", [])
        if len(coords) >= 2:
            start = coords[0]
            end = coords[-1]
            cable_endpoints.append((i, "start", start))
            cable_endpoints.append((i, "end", end))
    
    print(f"  Indexed {len(cable_endpoints)} cable endpoints")
    print()
    
    # Check FOSCs (limit to first 100 for debugging)
    max_foscs_to_check = min(100, len(foscs))
    print(f"  Checking first {max_foscs_to_check} FOSCs...")
    
    for fosc_idx, fosc in enumerate(foscs[:max_foscs_to_check]):
        if fosc_idx % 10 == 0:
            print(f"    Processing FOSC {fosc_idx}/{max_foscs_to_check}...")
        
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            continue
        
        # Find cables at this FOSC (using spatial index)
        connected_cables = []
        seen_cable_indices = set()
        
        for cable_idx, endpoint_type, endpoint_pos in cable_endpoints:
            if cable_idx in seen_cable_indices:
                continue
            
            dist = euclidean_distance(fosc_pos[0], fosc_pos[1], endpoint_pos[0], endpoint_pos[1])
            
            if dist <= tolerance_m:
                cable = cables[cable_idx]
                coords = cable.get("coordinates", [])
                if len(coords) >= 2:
                    start = coords[0]
                    end = coords[-1]
                    
                    dist_to_start = euclidean_distance(fosc_pos[0], fosc_pos[1], start[0], start[1])
                    dist_to_end = euclidean_distance(fosc_pos[0], fosc_pos[1], end[0], end[1])
                    
                    connected_cables.append({
                        "index": cable_idx,
                        "id": cable.get("id", ""),
                        "dist_to_start": dist_to_start,
                        "dist_to_end": dist_to_end,
                        "start": start,
                        "end": end
                    })
                    seen_cable_indices.add(cable_idx)
        
        fosc_cable_counts.append({
            "fosc_idx": fosc_idx,
            "fosc_pos": fosc_pos,
            "fosc_id": fosc.get("fosc_id", ""),
            "connected_cables": len(connected_cables),
            "cables": connected_cables[:3]  # First 3 only
        })
        
        if len(connected_cables) >= 2 and fosc_idx < 10:  # Only print first 10
            print(f"FOSC {fosc_idx} ({fosc.get('fosc_id', 'N/A')}):")
            print(f"  Position: ({fosc_pos[0]:.2f}, {fosc_pos[1]:.2f})")
            print(f"  Connected cables: {len(connected_cables)}")
            for cab in connected_cables[:3]:
                print(f"    - Cable {cab['index']}: dist_start={cab['dist_to_start']:.2f}m, dist_end={cab['dist_to_end']:.2f}m")
            print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    foscs_with_2plus = sum(1 for f in fosc_cable_counts if f["connected_cables"] >= 2)
    foscs_with_1 = sum(1 for f in fosc_cable_counts if f["connected_cables"] == 1)
    foscs_with_0 = sum(1 for f in fosc_cable_counts if f["connected_cables"] == 0)
    
    print(f"Total FOSCs: {len(foscs)}")
    print(f"  FOSCs with 2+ cables: {foscs_with_2plus}")
    print(f"  FOSCs with 1 cable: {foscs_with_1}")
    print(f"  FOSCs with 0 cables: {foscs_with_0}")
    print()
    
    # Now run Phase 6 and check what happens
    print("=" * 80)
    print("RUNNING PHASE 6")
    print("=" * 80)
    print()
    
    sized_cables, sizing_summary = size_cables(
        fiber_cable_geojson,
        foscs,
        terminals,
        olts,
        ont_geojson,
        config
    )
    
    print()
    print("=" * 80)
    print("PHASE 6 RESULTS")
    print("=" * 80)
    print()
    print(f"FOSC aggregations applied: {sizing_summary.get('fosc_aggregations', 0)}")
    print(f"Size distribution: {sizing_summary.get('size_distribution', {})}")
    print()
    
    # Check if FOSC aggregation should have worked
    if foscs_with_2plus > 0 and sizing_summary.get('fosc_aggregations', 0) == 0:
        print("⚠️  ISSUE DETECTED:")
        print(f"  - {foscs_with_2plus} FOSCs have 2+ cables")
        print(f"  - But 0 aggregations were applied")
        print()
        print("Possible causes:")
        print("  1. FOSC positions don't match cable endpoints (tolerance issue)")
        print("  2. Direction detection (incoming vs outgoing) failing")
        print("  3. Cables already sized before aggregation check")
        print()
    
    # Save debug info
    debug_info = {
        "fosc_count": len(foscs),
        "foscs_with_2plus_cables": foscs_with_2plus,
        "foscs_with_1_cable": foscs_with_1,
        "foscs_with_0_cables": foscs_with_0,
        "fosc_cable_details": fosc_cable_counts,
        "phase6_aggregations": sizing_summary.get('fosc_aggregations', 0),
        "phase6_size_distribution": sizing_summary.get('size_distribution', {})
    }
    
    with open("test_output/fosc_aggregation_debug.json", "w") as f:
        json.dump(debug_info, f, indent=2, default=str)
    
        print("✓ Saved debug info to test_output/fosc_aggregation_debug.json")
        
    except Exception as e:
        if "timed out" in str(e).lower() or isinstance(e, TimeoutError):
            print()
            print("=" * 80)
            print("TIMEOUT: Operation took longer than 5 minutes")
            print("=" * 80)
            print()
            print("The debug script was optimized but still timed out.")
            print("This suggests the cable-FOSC matching is too slow.")
            print()
            print("Recommendations:")
            print("  1. Use spatial indexing (grid-based)")
            print("  2. Limit FOSC checking to subset")
            print("  3. Check actual FOSC positions vs cable endpoints")
            sys.exit(1)
        else:
            raise
        print()
        print("=" * 80)
        print("TIMEOUT: Operation took longer than 5 minutes")
        print("=" * 80)
        print()
        print("The debug script was optimized but still timed out.")
        print("This suggests the cable-FOSC matching is too slow.")
        print()
        print("Recommendations:")
        print("  1. Use spatial indexing (grid-based)")
        print("  2. Limit FOSC checking to subset")
        print("  3. Check actual FOSC positions vs cable endpoints")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        sys.exit(1)
    finally:
        if USE_TIMEOUT:
            signal.alarm(0)  # Cancel timeout


if __name__ == "__main__":
    debug_fosc_aggregation()

