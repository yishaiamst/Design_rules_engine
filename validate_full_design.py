#!/usr/bin/env python3
"""
Comprehensive validation of generated design against actual design.
"""

import json
from collections import Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

def validate_all():
    """Run all validations and generate comprehensive report."""
    print("=" * 80)
    print("COMPREHENSIVE DESIGN VALIDATION")
    print("=" * 80)
    print()
    
    results = {}
    
    # 1. FOSC Validation
    print("1. FOSC PLACEMENT VALIDATION")
    print("-" * 80)
    actual_foscs = load_geojson("splice closure.geojson")
    generated_foscs = load_geojson("test_output/splice closure.geojson")
    
    actual_count = len(actual_foscs.get("features", []))
    generated_count = len(generated_foscs.get("features", []))
    
    # Match FOSCs (within 50m)
    actual_positions = []
    for feat in actual_foscs.get("features", []):
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            actual_positions.append((coords[0], coords[1]))
    
    generated_positions = []
    for feat in generated_foscs.get("features", []):
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            generated_positions.append((coords[0], coords[1]))
    
    matched = 0
    used_generated = set()
    for actual_pos in actual_positions:
        min_dist = float('inf')
        closest_idx = None
        for i, gen_pos in enumerate(generated_positions):
            if i in used_generated:
                continue
            dist = euclidean_distance(actual_pos[0], actual_pos[1], gen_pos[0], gen_pos[1])
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        if min_dist <= 50.0 and closest_idx is not None:
            matched += 1
            used_generated.add(closest_idx)
    
    fosc_match_rate = (matched / actual_count * 100) if actual_count > 0 else 0
    print(f"  Actual FOSCs: {actual_count}")
    print(f"  Generated FOSCs: {generated_count}")
    print(f"  Matched (within 50m): {matched} ({fosc_match_rate:.1f}%)")
    print(f"  Difference: {generated_count - actual_count} ({((generated_count - actual_count) / actual_count * 100) if actual_count > 0 else 0:.1f}%)")
    print()
    
    results["fosc"] = {
        "actual": actual_count,
        "generated": generated_count,
        "matched": matched,
        "match_rate": fosc_match_rate,
        "difference": generated_count - actual_count
    }
    
    # 2. Terminal Validation
    print("2. TERMINAL PLACEMENT VALIDATION")
    print("-" * 80)
    actual_terminals = load_geojson("terminal.geojson")
    generated_terminals = load_geojson("test_output/terminal.geojson")
    
    actual_features = actual_terminals.get("features", [])
    generated_features = generated_terminals.get("features", [])
    
    # Count by type
    actual_by_type = Counter()
    generated_by_type = Counter()
    
    for feat in actual_features:
        props = feat.get("properties", {})
        term_type = props.get("Type") or props.get("type", "")
        actual_by_type[term_type] += 1
    
    for feat in generated_features:
        props = feat.get("properties", {})
        term_type = props.get("Type") or props.get("type", "")
        generated_by_type[term_type] += 1
    
    print(f"  Actual terminals: {len(actual_features)}")
    print(f"  Generated terminals: {len(generated_features)}")
    print(f"  Difference: {len(generated_features) - len(actual_features)} ({((len(generated_features) - len(actual_features)) / len(actual_features) * 100) if actual_features else 0:.1f}%)")
    print()
    print(f"  Type Distribution:")
    print(f"    {'Type':<20} {'Actual':<12} {'Generated':<12} {'Match %':<10}")
    print(f"    {'-' * 54}")
    for term_type in set(list(actual_by_type.keys()) + list(generated_by_type.keys())):
        actual_count = actual_by_type.get(term_type, 0)
        generated_count = generated_by_type.get(term_type, 0)
        match_pct = (generated_count / actual_count * 100) if actual_count > 0 else 0
        print(f"    {term_type:<20} {actual_count:<12} {generated_count:<12} {match_pct:>6.1f}%")
    print()
    
    results["terminals"] = {
        "actual": len(actual_features),
        "generated": len(generated_features),
        "actual_by_type": dict(actual_by_type),
        "generated_by_type": dict(generated_by_type)
    }
    
    # 3. Drop Cable Validation
    print("3. DROP CABLE VALIDATION")
    print("-" * 80)
    actual_drop = load_geojson("drop cable.geojson")
    generated_drop = load_geojson("test_output/drop cable.geojson")
    
    actual_drop_count = len(actual_drop.get("features", []))
    generated_drop_count = len(generated_drop.get("features", []))
    
    # Count by size
    actual_drop_sizes = Counter()
    generated_drop_sizes = Counter()
    
    for feat in actual_drop.get("features", []):
        props = feat.get("properties", {})
        size = props.get("Size") or props.get("size", "1F")
        actual_drop_sizes[str(size)] += 1
    
    for feat in generated_drop.get("features", []):
        props = feat.get("properties", {})
        size = props.get("Size") or props.get("size", "1F")
        generated_drop_sizes[str(size)] += 1
    
    print(f"  Actual drop cables: {actual_drop_count}")
    print(f"  Generated drop cables: {generated_drop_count}")
    print(f"  Difference: {generated_drop_count - actual_drop_count} ({((generated_drop_count - actual_drop_count) / actual_drop_count * 100) if actual_drop_count > 0 else 0:.1f}%)")
    print()
    print(f"  Size Distribution:")
    print(f"    {'Size':<10} {'Actual':<12} {'Generated':<12} {'Match %':<10}")
    print(f"    {'-' * 44}")
    for size in set(list(actual_drop_sizes.keys()) + list(generated_drop_sizes.keys())):
        actual_count = actual_drop_sizes.get(size, 0)
        generated_count = generated_drop_sizes.get(size, 0)
        match_pct = (generated_count / actual_count * 100) if actual_count > 0 else 0
        print(f"    {size:<10} {actual_count:<12} {generated_count:<12} {match_pct:>6.1f}%")
    print()
    
    results["drop_cables"] = {
        "actual": actual_drop_count,
        "generated": generated_drop_count,
        "actual_sizes": dict(actual_drop_sizes),
        "generated_sizes": dict(generated_drop_sizes)
    }
    
    # 4. Stub Cable Validation
    print("4. STUB CABLE VALIDATION")
    print("-" * 80)
    try:
        actual_stub = load_geojson("stub cable.geojson")
        generated_stub = load_geojson("test_output/stub cable.geojson")
        
        actual_stub_count = len(actual_stub.get("features", []))
        generated_stub_count = len(generated_stub.get("features", []))
        
        # Count by size
        actual_stub_sizes = Counter()
        generated_stub_sizes = Counter()
        
        for feat in actual_stub.get("features", []):
            props = feat.get("properties", {})
            size = props.get("Size") or props.get("size", "")
            actual_stub_sizes[str(size)] += 1
        
        for feat in generated_stub.get("features", []):
            props = feat.get("properties", {})
            size = props.get("Size") or props.get("size", "")
            generated_stub_sizes[str(size)] += 1
        
        print(f"  Actual stub cables: {actual_stub_count}")
        print(f"  Generated stub cables: {generated_stub_count}")
        print(f"  Difference: {generated_stub_count - actual_stub_count} ({((generated_stub_count - actual_stub_count) / actual_stub_count * 100) if actual_stub_count > 0 else 0:.1f}%)")
        print()
        print(f"  Size Distribution:")
        print(f"    {'Size':<10} {'Actual':<12} {'Generated':<12} {'Match %':<10}")
        print(f"    {'-' * 44}")
        for size in set(list(actual_stub_sizes.keys()) + list(generated_stub_sizes.keys())):
            actual_count = actual_stub_sizes.get(size, 0)
            generated_count = generated_stub_sizes.get(size, 0)
            match_pct = (generated_count / actual_count * 100) if actual_count > 0 else 0
            print(f"    {size:<10} {actual_count:<12} {generated_count:<12} {match_pct:>6.1f}%")
        print()
        
        results["stub_cables"] = {
            "actual": actual_stub_count,
            "generated": generated_stub_count,
            "actual_sizes": dict(actual_stub_sizes),
            "generated_sizes": dict(generated_stub_sizes)
        }
    except Exception as e:
        print(f"  ⚠️  Error loading stub cables: {e}")
        results["stub_cables"] = {"error": str(e)}
    
    # 5. Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print()
    
    print(f"FOSCs:")
    print(f"  Match rate: {fosc_match_rate:.1f}%")
    print(f"  Count difference: {generated_count - actual_count} ({((generated_count - actual_count) / actual_count * 100) if actual_count > 0 else 0:.1f}%)")
    print()
    
    print(f"Terminals:")
    actual_aerial = actual_by_type.get("Aerial Terminal", 0)
    generated_aerial = generated_by_type.get("Aerial Terminal", 0)
    actual_mst = actual_by_type.get("MST", 0)
    generated_mst = generated_by_type.get("MST", 0)
    print(f"  Total: {len(generated_features)}/{len(actual_features)} ({len(generated_features)/len(actual_features)*100 if actual_features else 0:.1f}%)")
    print(f"  Aerial: {generated_aerial}/{actual_aerial} ({generated_aerial/actual_aerial*100 if actual_aerial > 0 else 0:.1f}%)")
    print(f"  MST: {generated_mst}/{actual_mst} ({generated_mst/actual_mst*100 if actual_mst > 0 else 0:.1f}%)")
    print()
    
    print(f"Drop Cables:")
    print(f"  Count: {generated_drop_count}/{actual_drop_count} ({generated_drop_count/actual_drop_count*100 if actual_drop_count > 0 else 0:.1f}%)")
    print()
    
    if "stub_cables" in results and "actual" in results["stub_cables"]:
        print(f"Stub Cables:")
        print(f"  Count: {results['stub_cables']['generated']}/{results['stub_cables']['actual']} ({results['stub_cables']['generated']/results['stub_cables']['actual']*100 if results['stub_cables']['actual'] > 0 else 0:.1f}%)")
        print()
    
    # Save results
    with open("test_output/full_validation_report.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print("  ✓ Results saved to test_output/full_validation_report.json")
    print()
    
    return results

if __name__ == "__main__":
    validate_all()

