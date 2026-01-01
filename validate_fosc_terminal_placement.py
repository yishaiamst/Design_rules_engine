#!/usr/bin/env python3
"""
Validate FOSC and Terminal placement against actual design.
"""

import json
from collections import defaultdict, Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

def validate_fosc_placement():
    """Compare generated FOSCs against actual design."""
    print("=" * 80)
    print("FOSC PLACEMENT VALIDATION")
    print("=" * 80)
    print()
    
    # Load actual FOSCs
    print("Loading actual FOSCs from design...")
    actual_foscs = load_geojson("splice closure.geojson")
    actual_features = actual_foscs.get("features", [])
    print(f"  Actual FOSCs: {len(actual_features)}")
    
    # Load generated FOSCs
    print("Loading generated FOSCs...")
    try:
        generated_foscs = load_geojson("test_output/splice closure.geojson")
        generated_features = generated_foscs.get("features", [])
        print(f"  Generated FOSCs: {len(generated_features)}")
    except:
        print("  ❌ No generated FOSCs found")
        return
    
    # Extract positions
    actual_positions = []
    for feat in actual_features:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            actual_positions.append((coords[0], coords[1]))
    
    generated_positions = []
    for feat in generated_features:
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            generated_positions.append((coords[0], coords[1]))
    
    # Match FOSCs (within 50m tolerance)
    tolerance_m = 50.0
    matched_count = 0
    unmatched_actual = []
    unmatched_generated = []
    
    used_generated = set()
    for actual_pos in actual_positions:
        min_dist = float('inf')
        closest_generated_idx = None
        
        for i, gen_pos in enumerate(generated_positions):
            if i in used_generated:
                continue
            dist = euclidean_distance(actual_pos[0], actual_pos[1], gen_pos[0], gen_pos[1])
            if dist < min_dist:
                min_dist = dist
                closest_generated_idx = i
        
        if min_dist <= tolerance_m and closest_generated_idx is not None:
            matched_count += 1
            used_generated.add(closest_generated_idx)
        else:
            unmatched_actual.append(actual_pos)
    
    # Find unmatched generated
    for i, gen_pos in enumerate(generated_positions):
        if i not in used_generated:
            unmatched_generated.append(gen_pos)
    
    # Statistics
    match_rate = (matched_count / len(actual_positions) * 100) if actual_positions else 0
    print()
    print("FOSC Placement Statistics:")
    print(f"  Actual FOSCs: {len(actual_positions)}")
    print(f"  Generated FOSCs: {len(generated_positions)}")
    print(f"  Matched (within {tolerance_m}m): {matched_count} ({match_rate:.1f}%)")
    print(f"  Unmatched actual: {len(unmatched_actual)}")
    print(f"  Unmatched generated: {len(unmatched_generated)}")
    print(f"  Difference: {len(generated_positions) - len(actual_positions)} ({((len(generated_positions) - len(actual_positions)) / len(actual_positions) * 100) if actual_positions else 0:.1f}%)")
    
    return {
        "actual_count": len(actual_positions),
        "generated_count": len(generated_positions),
        "matched_count": matched_count,
        "match_rate": match_rate,
        "unmatched_actual": len(unmatched_actual),
        "unmatched_generated": len(unmatched_generated)
    }

def validate_terminal_placement():
    """Compare generated terminals against actual design."""
    print()
    print("=" * 80)
    print("TERMINAL PLACEMENT VALIDATION")
    print("=" * 80)
    print()
    
    # Load actual terminals
    print("Loading actual terminals from design...")
    actual_terminals = load_geojson("terminal.geojson")
    actual_features = actual_terminals.get("features", [])
    print(f"  Actual terminals: {len(actual_features)}")
    
    # Load generated terminals
    print("Loading generated terminals...")
    try:
        generated_terminals = load_geojson("test_output/terminal.geojson")
        generated_features = generated_terminals.get("features", [])
        print(f"  Generated terminals: {len(generated_features)}")
    except:
        print("  ❌ No generated terminals found")
        return
    
    # Extract terminal data
    actual_data = []
    for feat in actual_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            terminal_type = props.get("Type") or props.get("type", "")
            actual_data.append({
                "position": (coords[0], coords[1]),
                "type": terminal_type
            })
    
    generated_data = []
    for feat in generated_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            terminal_type = props.get("Type") or props.get("type", "")
            generated_data.append({
                "position": (coords[0], coords[1]),
                "type": terminal_type
            })
    
    # Count by type
    actual_by_type = Counter(t["type"] for t in actual_data)
    generated_by_type = Counter(t["type"] for t in generated_data)
    
    print()
    print("Terminal Count by Type:")
    print(f"  {'Type':<20} {'Actual':<12} {'Generated':<12} {'Difference':<12} {'Match %':<10}")
    print("  " + "-" * 66)
    for term_type in set(list(actual_by_type.keys()) + list(generated_by_type.keys())):
        actual_count = actual_by_type.get(term_type, 0)
        generated_count = generated_by_type.get(term_type, 0)
        diff = generated_count - actual_count
        match_pct = (generated_count / actual_count * 100) if actual_count > 0 else 0
        print(f"  {term_type:<20} {actual_count:<12} {generated_count:<12} {diff:<12} {match_pct:>6.1f}%")
    
    # Match terminals (within 100m tolerance - terminals can be placed slightly differently)
    tolerance_m = 100.0
    matched_count = 0
    matched_by_type = defaultdict(int)
    unmatched_actual = []
    unmatched_generated = []
    
    used_generated = set()
    for actual_term in actual_data:
        min_dist = float('inf')
        closest_generated_idx = None
        
        for i, gen_term in enumerate(generated_data):
            if i in used_generated:
                continue
            dist = euclidean_distance(
                actual_term["position"][0], actual_term["position"][1],
                gen_term["position"][0], gen_term["position"][1]
            )
            if dist < min_dist:
                min_dist = dist
                closest_generated_idx = i
        
        if min_dist <= tolerance_m and closest_generated_idx is not None:
            matched_count += 1
            used_generated.add(closest_generated_idx)
            # Check if type matches
            if actual_term["type"] == generated_data[closest_generated_idx]["type"]:
                matched_by_type[actual_term["type"]] += 1
        else:
            unmatched_actual.append(actual_term)
    
    # Find unmatched generated
    for i, gen_term in enumerate(generated_data):
        if i not in used_generated:
            unmatched_generated.append(gen_term)
    
    # Statistics
    match_rate = (matched_count / len(actual_data) * 100) if actual_data else 0
    print()
    print("Terminal Placement Statistics:")
    print(f"  Actual terminals: {len(actual_data)}")
    print(f"  Generated terminals: {len(generated_data)}")
    print(f"  Matched (within {tolerance_m}m): {matched_count} ({match_rate:.1f}%)")
    print(f"  Matched with correct type: {sum(matched_by_type.values())} ({sum(matched_by_type.values()) / len(actual_data) * 100 if actual_data else 0:.1f}%)")
    print(f"  Unmatched actual: {len(unmatched_actual)}")
    print(f"  Unmatched generated: {len(unmatched_generated)}")
    print(f"  Difference: {len(generated_data) - len(actual_data)} ({((len(generated_data) - len(actual_data)) / len(actual_data) * 100) if actual_data else 0:.1f}%)")
    
    print()
    print("Type Match Statistics:")
    for term_type in matched_by_type:
        actual_count = actual_by_type.get(term_type, 0)
        matched = matched_by_type[term_type]
        print(f"  {term_type}: {matched}/{actual_count} matched ({matched/actual_count*100 if actual_count > 0 else 0:.1f}%)")
    
    return {
        "actual_count": len(actual_data),
        "generated_count": len(generated_data),
        "matched_count": matched_count,
        "match_rate": match_rate,
        "type_match_count": sum(matched_by_type.values()),
        "actual_by_type": dict(actual_by_type),
        "generated_by_type": dict(generated_by_type),
        "matched_by_type": dict(matched_by_type)
    }

def main():
    """Run all validations."""
    fosc_stats = validate_fosc_placement()
    terminal_stats = validate_terminal_placement()
    
    # Save results
    results = {
        "fosc_placement": fosc_stats,
        "terminal_placement": terminal_stats
    }
    
    with open("test_output/placement_validation.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print()
    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print("  ✓ Results saved to test_output/placement_validation.json")
    print()

if __name__ == "__main__":
    main()

