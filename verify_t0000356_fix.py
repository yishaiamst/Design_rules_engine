#!/usr/bin/env python3
"""
Verify that T0000356 is handled by Fix 3 logic.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance, calculate_centroid
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase2_place_foscs import place_foscs_initial
from phases.phase3_place_terminals import place_terminals
from phases.phase3b_refine_mst_placement import refine_mst_placement

def main():
    print("=" * 80)
    print("VERIFYING T0000356 FIX")
    print("=" * 80)
    print()
    
    # Load data
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Run pipeline
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
    foscs, _ = place_foscs_initial(fiber_cable_geojson, None, config)
    terminals, _, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, config)
    
    # Find T0000356
    t0000356 = None
    for terminal in terminals:
        if terminal.get("terminal_id") == "T0000356":
            t0000356 = terminal
            break
    
    if not t0000356:
        print("❌ T0000356 not found in terminals")
        return
    
    print("Found T0000356:")
    print(f"  Position: {t0000356.get('position')}")
    print(f"  Type: {t0000356.get('type')}")
    print(f"  ONT Count: {len(t0000356.get('connected_onts', []))}")
    
    # Load ONTs
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2 and ont_id:
                onts_by_id[ont_id] = {
                    "id": ont_id,
                    "position": (coords[0], coords[1])
                }
    
    # Calculate drop cable lengths
    terminal_pos = t0000356.get("position")
    connected_ont_ids = t0000356.get("connected_onts", [])
    
    drop_lengths = []
    ont_positions = []
    
    for ont_id in connected_ont_ids:
        ont = onts_by_id.get(ont_id)
        if not ont:
            continue
        
        ont_pos = ont.get("position")
        if not ont_pos:
            continue
        
        drop_length = euclidean_distance(
            terminal_pos[0], terminal_pos[1],
            ont_pos[0], ont_pos[1]
        )
        drop_lengths.append(drop_length)
        ont_positions.append(ont_pos)
    
    if drop_lengths:
        avg_drop = sum(drop_lengths) / len(drop_lengths)
        max_drop = max(drop_lengths)
        total_drop = sum(drop_lengths)
        
        print()
        print("Drop Cable Analysis:")
        print(f"  Average: {avg_drop:.1f}m")
        print(f"  Max: {max_drop:.1f}m")
        print(f"  Total: {total_drop:.1f}m")
        print(f"  Count: {len(drop_lengths)}")
        
        # Check if it meets long drop criteria
        is_long_drop = avg_drop > 100.0 or max_drop > 150.0
        print()
        print(f"  Meets long drop criteria (avg>100m OR max>150m): {is_long_drop}")
        
        if is_long_drop:
            # Check clustering
            cluster_centroid = calculate_centroid(ont_positions) if ont_positions else None
            print(f"  Cluster centroid: {cluster_centroid}")
            
            # Check if ONTs form cluster
            cluster_radius = 200.0
            clustered_count = 0
            for ont_pos in ont_positions:
                dist = euclidean_distance(
                    cluster_centroid[0], cluster_centroid[1],
                    ont_pos[0], ont_pos[1]
                )
                if dist <= cluster_radius:
                    clustered_count += 1
            
            print(f"  ONTs in cluster (within 200m): {clustered_count}/{len(ont_positions)}")
            
            if clustered_count >= 3:
                # Find nearby FOSCs
                print()
                print("  Nearby FOSCs:")
                for fosc in foscs:
                    fosc_pos = fosc.get("position")
                    fosc_id = fosc.get("fosc_id", "")
                    if fosc_pos and cluster_centroid:
                        dist = euclidean_distance(
                            cluster_centroid[0], cluster_centroid[1],
                            fosc_pos[0], fosc_pos[1]
                        )
                        if dist < 1000.0:
                            print(f"    {fosc_id}: {dist:.1f}m away")
                            if fosc_id == "F0000178":
                                print(f"      ✓ F0000178 found!")
    
    # Run Phase 3b
    print()
    print("Running Phase 3b...")
    refined_terminals, refined_foscs, new_msts, summary = refine_mst_placement(
        terminals,
        foscs,
        ont_geojson,
        fiber_cable_geojson,
        config
    )
    
    # Check if T0000356 was modified
    t0000356_after = None
    for terminal in refined_terminals:
        if terminal.get("terminal_id") == "T0000356":
            t0000356_after = terminal
            break
    
    print()
    print("After Phase 3b:")
    if t0000356_after:
        print(f"  T0000356 still exists")
        print(f"  ONT Count: {len(t0000356_after.get('connected_onts', []))}")
        print(f"  Original ONT Count: {len(t0000356.get('connected_onts', []))}")
        
        if len(t0000356_after.get('connected_onts', [])) < len(t0000356.get('connected_onts', [])):
            print("  ✓ ONTs were reassigned to new MST(s)")
    else:
        print("  T0000356 removed (all ONTs reassigned)")
    
    # Check if new MSTs were created for T0000356
    msts_for_t0000356 = [mst for mst in new_msts if mst.get("replaces_terminal_id") == "T0000356"]
    if msts_for_t0000356:
        print()
        print(f"  ✓ {len(msts_for_t0000356)} new MST(s) created for T0000356:")
        for mst in msts_for_t0000356:
            print(f"    {mst.get('terminal_id')}: {mst.get('ont_count')} ONTs")
            print(f"      Position: {mst.get('position')}")
            print(f"      FOSC: {mst.get('connected_fosc_id')}")
            print(f"      Savings: {mst.get('savings_m', 0):.1f}m")
    else:
        print()
        print("  ⚠️  No MSTs created for T0000356")
        print("  Possible reasons:")
        print("    - ONTs don't form cluster (within 200m)")
        print("    - No nearby FOSC (within 1km)")
        print("    - No nearby cable (within 200m)")
        print("    - Savings not significant (<100m)")

if __name__ == "__main__":
    main()
