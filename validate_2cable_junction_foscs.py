#!/usr/bin/env python3
"""
Validate 2-Cable Junction (T-cross) FOSC Placement
Compare generated FOSCs at 2-cable junctions with actual design.
"""

import json
import statistics
from collections import defaultdict
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance
from utils.intersection_utils import find_cable_junctions_geometric


def validate_2cable_junction_foscs():
    """
    Validate that FOSCs placed at 2-cable junctions match actual design.
    """
    print("=" * 80)
    print("VALIDATING 2-CABLE JUNCTION (T-CROSS) FOSC PLACEMENT")
    print("=" * 80)
    print()
    
    # Load actual design FOSCs
    print("Loading actual design FOSCs...")
    try:
        actual_foscs_geojson = load_geojson("splice closure.geojson")
        actual_features = actual_foscs_geojson.get("features", [])
        print(f"  ✓ Loaded {len(actual_features)} actual FOSCs")
    except FileNotFoundError:
        print("  ❌ Error: splice closure.geojson not found")
        return
    
    # Extract actual FOSC positions
    actual_positions = []
    for feat in actual_features:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if geom.get("type") == "Point" and len(coords) >= 2:
            actual_positions.append({
                "position": (coords[0], coords[1]),
                "id": feat.get("properties", {}).get("ID") or feat.get("properties", {}).get("id", ""),
                "properties": feat.get("properties", {})
            })
    
    print()
    
    # Load cable segments and detect junctions
    print("Detecting 2-cable junctions...")
    print()
    
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    
    # Extract segments
    cables = []
    for feature in fiber_cable_geojson.get("features", []):
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
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    print(f"    Loaded {len(cables)} cable segments")
    
    # Detect all junctions
    junctions = find_cable_junctions_geometric(cables, tolerance_m=10.0, max_junctions=5000)
    print(f"    Found {len(junctions)} total junctions")
    
    # Filter to 2-cable junctions (T-cross)
    junctions_2 = [j for j in junctions if j["cable_count"] == 2]
    print(f"    Found {len(junctions_2)} 2-cable junctions (T-cross)")
    print()
    
    print("=" * 80)
    print("ANALYSIS: 2-CABLE JUNCTION FOSCs")
    print("=" * 80)
    print()
    
    # Create generated FOSCs from 2-cable junctions
    generated_2cable_foscs = []
    for i, junction in enumerate(junctions_2, 1):
        generated_2cable_foscs.append({
            "fosc_id": f"F{i:07d}",
            "position": junction["position"],
            "trigger": "junction",
            "cable_count": 2,
            "junction_type": "T-cross",
            "cable_indices": junction["cable_indices"]
        })
    
    print(f"Generated FOSCs at 2-cable junctions: {len(generated_2cable_foscs)}")
    print()
    
    # Match generated 2-cable FOSCs with actual FOSCs
    tolerance_m = 50.0
    matched_actual = set()
    matched_generated = set()
    match_distances = []
    match_details = []
    
    for i, gen_fosc in enumerate(generated_2cable_foscs):
        gen_pos = gen_fosc["position"]
        min_dist = float('inf')
        closest_actual_idx = None
        
        for j, actual in enumerate(actual_positions):
            if j in matched_actual:
                continue
            
            actual_pos = actual["position"]
            dist = euclidean_distance(
                gen_pos[0], gen_pos[1],
                actual_pos[0], actual_pos[1]
            )
            
            if dist < min_dist:
                min_dist = dist
                closest_actual_idx = j
        
        if min_dist <= tolerance_m and closest_actual_idx is not None:
            matched_actual.add(closest_actual_idx)
            matched_generated.add(i)
            match_distances.append(min_dist)
            match_details.append({
                "generated": gen_fosc,
                "actual": actual_positions[closest_actual_idx],
                "distance": min_dist
            })
    
    matched_count = len(matched_generated)
    unmatched_generated = len(generated_2cable_foscs) - matched_count
    
    match_rate = (matched_count / len(generated_2cable_foscs) * 100) if generated_2cable_foscs else 0
    
    print("=" * 80)
    print("MATCHING RESULTS")
    print("=" * 80)
    print()
    
    print(f"Match tolerance: {tolerance_m}m")
    print(f"Generated 2-cable junction FOSCs: {len(generated_2cable_foscs)}")
    print(f"Matched: {matched_count} ({match_rate:.1f}%)")
    print(f"Unmatched generated: {unmatched_generated}")
    print()
    
    if match_distances:
        print(f"Match distance statistics:")
        print(f"  Mean: {statistics.mean(match_distances):.2f}m")
        print(f"  Median: {statistics.median(match_distances):.2f}m")
        print(f"  Min: {min(match_distances):.2f}m")
        print(f"  Max: {max(match_distances):.2f}m")
        print()
    
    # Analyze unmatched generated FOSCs
    if unmatched_generated > 0:
        print("=" * 80)
        print("UNMATCHED GENERATED 2-CABLE JUNCTION FOSCs")
        print("=" * 80)
        print()
        
        unmatched_details = []
        for i, gen_fosc in enumerate(generated_2cable_foscs):
            if i not in matched_generated:
                # Find nearest actual FOSC
                gen_pos = gen_fosc["position"]
                min_dist_to_any = float('inf')
                nearest_actual = None
                
                for actual in actual_positions:
                    dist = euclidean_distance(
                        gen_pos[0], gen_pos[1],
                        actual["position"][0], actual["position"][1]
                    )
                    if dist < min_dist_to_any:
                        min_dist_to_any = dist
                        nearest_actual = actual
                
                unmatched_details.append({
                    "fosc": gen_fosc,
                    "nearest_actual": nearest_actual,
                    "distance": min_dist_to_any
                })
        
        # Sort by distance
        unmatched_details.sort(key=lambda x: x["distance"])
        
        print(f"Found {len(unmatched_details)} unmatched generated FOSCs")
        print()
        print("Distance distribution of unmatched FOSCs:")
        distance_ranges = {
            "50-100m": 0,
            "100-200m": 0,
            "200-500m": 0,
            "500m+": 0
        }
        
        for detail in unmatched_details:
            dist = detail["distance"]
            if 50 <= dist < 100:
                distance_ranges["50-100m"] += 1
            elif 100 <= dist < 200:
                distance_ranges["100-200m"] += 1
            elif 200 <= dist < 500:
                distance_ranges["200-500m"] += 1
            else:
                distance_ranges["500m+"] += 1
        
        for range_name, count in distance_ranges.items():
            if count > 0:
                print(f"  {range_name}: {count}")
        print()
        
        print("Top 10 closest to actual FOSCs:")
        for i, detail in enumerate(unmatched_details[:10], 1):
            print(f"  {i}. Distance to nearest actual: {detail['distance']:.2f}m")
        print()
    
    # Check if unmatched might be aerial terminals
    print("=" * 80)
    print("CHECKING IF UNMATCHED FOSCs ARE AERIAL TERMINALS")
    print("=" * 80)
    print()
    
    try:
        terminal_geojson = load_geojson("terminal.geojson")
        terminal_features = terminal_geojson.get("features", [])
        
        terminal_positions = []
        for feat in terminal_features:
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            props = feat.get("properties", {})
            if geom.get("type") == "Point" and len(coords) >= 2:
                terminal_type = props.get("Type") or props.get("type", "")
                if "Aerial" in terminal_type or "AER" in terminal_type:
                    terminal_positions.append({
                        "position": (coords[0], coords[1]),
                        "id": props.get("ID") or props.get("id", ""),
                        "type": terminal_type
                    })
        
        print(f"  Loaded {len(terminal_positions)} aerial terminals")
        
        # Check unmatched FOSCs against aerial terminals
        unmatched_matching_terminals = 0
        terminal_match_distances = []
        
        for i, gen_fosc in enumerate(generated_2cable_foscs):
            if i not in matched_generated:
                gen_pos = gen_fosc["position"]
                min_terminal_dist = float('inf')
                
                for terminal in terminal_positions:
                    dist = euclidean_distance(
                        gen_pos[0], gen_pos[1],
                        terminal["position"][0], terminal["position"][1]
                    )
                    if dist < min_terminal_dist:
                        min_terminal_dist = dist
                
                if min_terminal_dist <= tolerance_m:
                    unmatched_matching_terminals += 1
                    terminal_match_distances.append(min_terminal_dist)
        
        print(f"  Unmatched FOSCs matching aerial terminals (within {tolerance_m}m): {unmatched_matching_terminals}")
        if terminal_match_distances:
            print(f"    Mean distance: {statistics.mean(terminal_match_distances):.2f}m")
            print(f"    Median distance: {statistics.median(terminal_match_distances):.2f}m")
        print()
        
        # Calculate adjusted match rate (FOSCs + terminals)
        total_placed = matched_count + unmatched_matching_terminals
        adjusted_match_rate = (total_placed / len(generated_2cable_foscs) * 100) if generated_2cable_foscs else 0
        print(f"  Adjusted match rate (FOSCs + Aerial Terminals): {adjusted_match_rate:.1f}%")
        print()
        
    except FileNotFoundError:
        print("  ⚠️  terminal.geojson not found, skipping aerial terminal check")
        print()
    
    # Summary and recommendation
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print()
    
    if match_rate >= 95:
        status = "✅ EXCELLENT"
        recommendation = "2-cable junction FOSC placement is highly accurate. Proceed to next step."
    elif match_rate >= 80:
        status = "✅ GOOD"
        recommendation = "2-cable junction FOSC placement is good. Review unmatched cases but can proceed."
    elif match_rate >= 60:
        status = "⚠️  MODERATE"
        recommendation = "2-cable junction FOSC placement needs review. Many unmatched cases."
    else:
        status = "❌ NEEDS WORK"
        recommendation = "2-cable junction FOSC placement has significant issues. Debug before proceeding."
    
    print(f"Match Rate (FOSCs only): {match_rate:.1f}%")
    if 'adjusted_match_rate' in locals():
        print(f"Adjusted Match Rate (FOSCs + Terminals): {adjusted_match_rate:.1f}%")
    print(f"Status: {status}")
    print(f"Recommendation: {recommendation}")
    print()
    
    # Save results
    results = {
        "validation_type": "2_cable_junction_foscs",
        "generated_count": len(generated_2cable_foscs),
        "matched_count": matched_count,
        "match_rate": match_rate,
        "unmatched_generated": unmatched_generated,
        "tolerance_m": tolerance_m,
        "status": status,
        "recommendation": recommendation,
        "match_distance_stats": {
            "mean": statistics.mean(match_distances) if match_distances else 0,
            "median": statistics.median(match_distances) if match_distances else 0,
            "min": min(match_distances) if match_distances else 0,
            "max": max(match_distances) if match_distances else 0
        } if match_distances else {},
        "unmatched_matching_terminals": unmatched_matching_terminals if 'unmatched_matching_terminals' in locals() else 0,
        "adjusted_match_rate": adjusted_match_rate if 'adjusted_match_rate' in locals() else None
    }
    
    output_file = "test_output/validate_2cable_junction_foscs.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    return results


if __name__ == "__main__":
    validate_2cable_junction_foscs()

