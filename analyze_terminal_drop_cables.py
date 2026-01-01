#!/usr/bin/env python3
"""
Analyze terminal drop cable lengths to identify candidates for MST placement.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance, calculate_centroid
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase2_place_foscs import place_foscs_initial
from phases.phase3_place_terminals import place_terminals

def analyze_terminal_drop_cables(terminals, onts_by_id, target_terminal_id=None):
    """Analyze drop cable lengths for terminals."""
    results = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        if target_terminal_id and terminal_id != target_terminal_id:
            continue
        
        terminal_pos = terminal.get("position")
        if not terminal_pos:
            continue
        
        connected_ont_ids = terminal.get("connected_onts", [])
        if not connected_ont_ids:
            continue
        
        # Calculate drop cable lengths
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
        
        if not drop_lengths:
            continue
        
        avg_drop = sum(drop_lengths) / len(drop_lengths)
        max_drop = max(drop_lengths)
        min_drop = min(drop_lengths)
        total_drop = sum(drop_lengths)
        
        # Calculate cluster centroid
        cluster_centroid = calculate_centroid(ont_positions) if ont_positions else None
        
        results.append({
            "terminal_id": terminal_id,
            "terminal_pos": terminal_pos,
            "ont_count": len(connected_ont_ids),
            "avg_drop_length_m": avg_drop,
            "max_drop_length_m": max_drop,
            "min_drop_length_m": min_drop,
            "total_drop_length_m": total_drop,
            "cluster_centroid": cluster_centroid,
            "drop_lengths": drop_lengths
        })
    
    return results

def main():
    print("=" * 80)
    print("ANALYZING TERMINAL DROP CABLE LENGTHS")
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
    
    # Analyze specific terminal
    print("Analyzing terminal T0000356...")
    results = analyze_terminal_drop_cables(terminals, onts_by_id, "T0000356")
    
    if results:
        r = results[0]
        print(f"Terminal ID: {r['terminal_id']}")
        print(f"Position: {r['terminal_pos']}")
        print(f"ONT Count: {r['ont_count']}")
        print(f"Average Drop Length: {r['avg_drop_length_m']:.1f}m")
        print(f"Max Drop Length: {r['max_drop_length_m']:.1f}m")
        print(f"Min Drop Length: {r['min_drop_length_m']:.1f}m")
        print(f"Total Drop Length: {r['total_drop_length_m']:.1f}m")
        if r['cluster_centroid']:
            print(f"Cluster Centroid: {r['cluster_centroid']}")
        
        # Find nearby FOSCs
        print()
        print("Nearby FOSCs:")
        for fosc in foscs:
            fosc_pos = fosc.get("position")
            fosc_id = fosc.get("fosc_id", "")
            if fosc_pos and r['cluster_centroid']:
                dist = euclidean_distance(
                    r['cluster_centroid'][0], r['cluster_centroid'][1],
                    fosc_pos[0], fosc_pos[1]
                )
                if dist < 1000.0:  # Within 1km
                    print(f"  {fosc_id}: {dist:.1f}m away")
    else:
        print("Terminal T0000356 not found")
    
    # Find terminals with long drop cables
    print()
    print("=" * 80)
    print("TERMINALS WITH LONG DROP CABLES")
    print("=" * 80)
    all_results = analyze_terminal_drop_cables(terminals, onts_by_id)
    
    # Sort by average drop length
    all_results.sort(key=lambda x: x['avg_drop_length_m'], reverse=True)
    
    print(f"\nTop 20 terminals with longest average drop cables:")
    for i, r in enumerate(all_results[:20], 1):
        print(f"{i:2d}. {r['terminal_id']}: {r['avg_drop_length_m']:.1f}m avg, {r['max_drop_length_m']:.1f}m max, {r['ont_count']} ONTs")

if __name__ == "__main__":
    main()
