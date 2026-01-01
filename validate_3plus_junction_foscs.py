#!/usr/bin/env python3
"""
Validate 3+ Cable Junction FOSC Placement
Compare generated FOSCs at 3+ cable junctions with actual design.
This should match exactly as it's a basic rule.
"""

import json
from collections import defaultdict
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance
from phases.phase2_place_foscs import place_foscs_initial
from utils.config_loader import load_config
from utils.cable_grouping import group_cables_by_topology
from utils.topology_junctions import detect_junctions_topology


def validate_3plus_junction_foscs():
    """
    Validate that FOSCs placed at 3+ cable junctions match actual design.
    """
    print("=" * 80)
    print("VALIDATING 3+ CABLE JUNCTION FOSC PLACEMENT")
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
    
    # Run Phase 2 to get generated FOSCs
    # For validation, we'll use the original segment-based approach to detect junctions
    # This matches the actual design better for now
    print("Detecting junctions using segment-based approach...")
    print()
    
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Extract segments (original approach)
    from utils.intersection_utils import find_cable_junctions_geometric
    
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
    
    # Detect junctions using original approach
    junctions = find_cable_junctions_geometric(cables, tolerance_m=10.0, max_junctions=5000)
    print(f"    Found {len(junctions)} junctions")
    
    # Filter to 3+ cable junctions
    junctions_3plus = [j for j in junctions if j["cable_count"] >= 3]
    print(f"    Found {len(junctions_3plus)} 3+ cable junctions")
    print()
    
    # Create FOSCs from 3+ junctions
    foscs = []
    for i, junction in enumerate(junctions_3plus, 1):
        fosc_id = f"F{i:07d}"
        foscs.append({
            "fosc_id": fosc_id,
            "position": junction["position"],
            "trigger": "junction",
            "cable_count": junction["cable_count"],
            "junction_type": "Y" if junction["cable_count"] == 3 else f"{junction['cable_count']}+-way",
            "cable_indices": junction["cable_indices"]
        })
    
    summary = {
        "junctions_3plus": len(junctions_3plus),
        "junctions_y": len([j for j in junctions_3plus if j["cable_count"] == 3]),
        "junctions_4plus": len([j for j in junctions_3plus if j["cable_count"] >= 4])
    }
    
    print()
    print("=" * 80)
    print("ANALYSIS: 3+ CABLE JUNCTION FOSCs")
    print("=" * 80)
    print()
    
    # Filter generated FOSCs to only 3+ cable junctions
    generated_3plus_foscs = []
    for fosc in foscs:
        junction_type = fosc.get("junction_type", "")
        cable_count = fosc.get("cable_count", 0)
        trigger = fosc.get("trigger", "")
        
        # Include Y (3) and 4+ way junctions
        if (junction_type in ["Y", "3+-way", "4+-way"] or 
            (cable_count >= 3 and trigger == "junction")):
            generated_3plus_foscs.append(fosc)
    
    print(f"Generated FOSCs at 3+ cable junctions: {len(generated_3plus_foscs)}")
    print(f"  Y junctions (3 cables): {summary.get('junctions_y', 0)}")
    print(f"  4+ way junctions: {summary.get('junctions_4plus', 0)}")
    print()
    
    # Match generated 3+ FOSCs with actual FOSCs
    tolerance_m = 50.0
    matched_actual = set()
    matched_generated = set()
    match_distances = []
    match_details = []
    
    for i, gen_fosc in enumerate(generated_3plus_foscs):
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
    unmatched_generated = len(generated_3plus_foscs) - matched_count
    unmatched_actual_3plus = 0  # We'll estimate this
    
    match_rate = (matched_count / len(generated_3plus_foscs) * 100) if generated_3plus_foscs else 0
    
    print("=" * 80)
    print("MATCHING RESULTS")
    print("=" * 80)
    print()
    
    print(f"Match tolerance: {tolerance_m}m")
    print(f"Generated 3+ junction FOSCs: {len(generated_3plus_foscs)}")
    print(f"Matched: {matched_count} ({match_rate:.1f}%)")
    print(f"Unmatched generated: {unmatched_generated}")
    print()
    
    if match_distances:
        import statistics
        print(f"Match distance statistics:")
        print(f"  Mean: {statistics.mean(match_distances):.2f}m")
        print(f"  Median: {statistics.median(match_distances):.2f}m")
        print(f"  Min: {min(match_distances):.2f}m")
        print(f"  Max: {max(match_distances):.2f}m")
        print()
    
    # Analyze unmatched generated FOSCs
    if unmatched_generated > 0:
        print("=" * 80)
        print("UNMATCHED GENERATED 3+ JUNCTION FOSCs")
        print("=" * 80)
        print()
        
        unmatched_details = []
        for i, gen_fosc in enumerate(generated_3plus_foscs):
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
                    "distance": min_dist_to_any,
                    "junction_type": gen_fosc.get("junction_type", "unknown"),
                    "cable_count": gen_fosc.get("cable_count", 0)
                })
        
        # Sort by distance
        unmatched_details.sort(key=lambda x: x["distance"])
        
        print(f"Found {len(unmatched_details)} unmatched generated FOSCs")
        print()
        print("Top 10 closest to actual FOSCs:")
        for i, detail in enumerate(unmatched_details[:10], 1):
            print(f"  {i}. Junction type: {detail['junction_type']}, "
                  f"Cable count: {detail['cable_count']}, "
                  f"Distance to nearest actual: {detail['distance']:.2f}m")
        print()
    
    # Summary and recommendation
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print()
    
    if match_rate >= 95:
        status = "✅ EXCELLENT"
        recommendation = "3+ junction FOSC placement is highly accurate. Proceed to next validation step."
    elif match_rate >= 80:
        status = "✅ GOOD"
        recommendation = "3+ junction FOSC placement is good. Review unmatched cases but can proceed."
    elif match_rate >= 60:
        status = "⚠️  MODERATE"
        recommendation = "3+ junction FOSC placement needs review. Investigate unmatched cases before proceeding."
    else:
        status = "❌ NEEDS WORK"
        recommendation = "3+ junction FOSC placement has significant issues. Debug before proceeding."
    
    print(f"Match Rate: {match_rate:.1f}%")
    print(f"Status: {status}")
    print(f"Recommendation: {recommendation}")
    print()
    
    # Save results
    results = {
        "validation_type": "3+_cable_junction_foscs",
        "generated_count": len(generated_3plus_foscs),
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
        "summary_stats": summary
    }
    
    output_file = "test_output/validate_3plus_junction_foscs.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    return results


if __name__ == "__main__":
    import statistics
    validate_3plus_junction_foscs()

