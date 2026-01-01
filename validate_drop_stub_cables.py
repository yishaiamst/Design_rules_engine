#!/usr/bin/env python3
"""
Validate drop and stub cables against actual design.
"""

import json
from collections import defaultdict, Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

def validate_drop_cables():
    """Compare generated drop cables against actual design."""
    print("=" * 80)
    print("DROP CABLE VALIDATION")
    print("=" * 80)
    print()
    
    # Load actual drop cables
    print("Loading actual drop cables...")
    actual_drop = load_geojson("drop cable.geojson")
    actual_features = actual_drop.get("features", [])
    print(f"  Actual drop cables: {len(actual_features)}")
    
    # Load generated drop cables
    print("Loading generated drop cables...")
    try:
        generated_drop = load_geojson("test_output/drop cable.geojson")
        generated_features = generated_drop.get("features", [])
        print(f"  Generated drop cables: {len(generated_features)}")
    except:
        print("  ❌ No generated drop cables found")
        return None
    
    # Extract cable data
    actual_cables = []
    for feat in actual_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            # Handle LineString and MultiLineString
            if geom.get("type") == "MultiLineString":
                all_coords = []
                for line in coords:
                    all_coords.extend(line)
                coords = all_coords
            
            # Get start and end points
            start = coords[0] if isinstance(coords[0], list) else coords[0]
            end = coords[-1] if isinstance(coords[-1], list) else coords[-1]
            
            if len(start) >= 2 and len(end) >= 2:
                actual_cables.append({
                    "from": (start[0], start[1]),
                    "to": (end[0], end[1]),
                    "size": props.get("Size") or props.get("size", "1F")
                })
    
    generated_cables = []
    for feat in generated_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            start = coords[0]
            end = coords[-1]
            if len(start) >= 2 and len(end) >= 2:
                generated_cables.append({
                    "from": (start[0], start[1]),
                    "to": (end[0], end[1]),
                    "size": props.get("Size") or props.get("size", "1F")
                })
    
    # Compare counts
    print()
    print("Drop Cable Statistics:")
    print(f"  Actual: {len(actual_cables)}")
    print(f"  Generated: {len(generated_cables)}")
    print(f"  Difference: {len(generated_cables) - len(actual_cables)} ({((len(generated_cables) - len(actual_cables)) / len(actual_cables) * 100) if actual_cables else 0:.1f}%)")
    
    # Analyze sizes
    actual_sizes = Counter(str(c["size"]) for c in actual_cables)
    generated_sizes = Counter(str(c["size"]) for c in generated_cables)
    
    print()
    print("Size Distribution:")
    print(f"  {'Size':<10} {'Actual':<12} {'Generated':<12} {'Match %':<10}")
    print("  " + "-" * 44)
    for size in set(list(actual_sizes.keys()) + list(generated_sizes.keys())):
        actual_count = actual_sizes.get(size, 0)
        generated_count = generated_sizes.get(size, 0)
        match_pct = (generated_count / actual_count * 100) if actual_count > 0 else 0
        print(f"  {size:<10} {actual_count:<12} {generated_count:<12} {match_pct:>6.1f}%")
    
    return {
        "actual_count": len(actual_cables),
        "generated_count": len(generated_cables),
        "actual_sizes": dict(actual_sizes),
        "generated_sizes": dict(generated_sizes)
    }

def validate_stub_cables():
    """Compare generated stub cables against actual design."""
    print()
    print("=" * 80)
    print("STUB CABLE VALIDATION")
    print("=" * 80)
    print()
    
    # Load actual stub cables
    print("Loading actual stub cables...")
    try:
        actual_stub = load_geojson("stub cable.geojson")
        actual_features = actual_stub.get("features", [])
        print(f"  Actual stub cables: {len(actual_features)}")
    except:
        print("  ⚠️  No actual stub cable file found")
        return None
    
    # Load generated stub cables
    print("Loading generated stub cables...")
    try:
        generated_stub = load_geojson("test_output/stub cable.geojson")
        generated_features = generated_stub.get("features", [])
        print(f"  Generated stub cables: {len(generated_features)}")
    except:
        print("  ❌ No generated stub cables found")
        return None
    
    # Extract cable data
    actual_cables = []
    for feat in actual_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            # Handle LineString and MultiLineString
            if geom.get("type") == "MultiLineString":
                all_coords = []
                for line in coords:
                    all_coords.extend(line)
                coords = all_coords
            
            start = coords[0] if isinstance(coords[0], list) else coords[0]
            end = coords[-1] if isinstance(coords[-1], list) else coords[-1]
            
            if len(start) >= 2 and len(end) >= 2:
                actual_cables.append({
                    "from": (start[0], start[1]),
                    "to": (end[0], end[1]),
                    "size": props.get("Size") or props.get("size", "12F")
                })
    
    generated_cables = []
    for feat in generated_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if coords and len(coords) >= 2:
            start = coords[0]
            end = coords[-1]
            if len(start) >= 2 and len(end) >= 2:
                generated_cables.append({
                    "from": (start[0], start[1]),
                    "to": (end[0], end[1]),
                    "size": props.get("Size") or props.get("size", "12F")
                })
    
    # Compare counts
    print()
    print("Stub Cable Statistics:")
    print(f"  Actual: {len(actual_cables)}")
    print(f"  Generated: {len(generated_cables)}")
    print(f"  Difference: {len(generated_cables) - len(actual_cables)} ({((len(generated_cables) - len(actual_cables)) / len(actual_cables) * 100) if actual_cables else 0:.1f}%)")
    
    # Analyze sizes
    actual_sizes = Counter(str(c["size"]) for c in actual_cables)
    generated_sizes = Counter(str(c["size"]) for c in generated_cables)
    
    print()
    print("Size Distribution:")
    print(f"  {'Size':<10} {'Actual':<12} {'Generated':<12} {'Match %':<10}")
    print("  " + "-" * 44)
    for size in set(list(actual_sizes.keys()) + list(generated_sizes.keys())):
        actual_count = actual_sizes.get(size, 0)
        generated_count = generated_sizes.get(size, 0)
        match_pct = (generated_count / actual_count * 100) if actual_count > 0 else 0
        print(f"  {size:<10} {actual_count:<12} {generated_count:<12} {match_pct:>6.1f}%")
    
    return {
        "actual_count": len(actual_cables),
        "generated_count": len(generated_cables),
        "actual_sizes": dict(actual_sizes),
        "generated_sizes": dict(generated_sizes)
    }

def main():
    """Run all validations."""
    drop_stats = validate_drop_cables()
    stub_stats = validate_stub_cables()
    
    # Save results
    results = {
        "drop_cables": drop_stats,
        "stub_cables": stub_stats
    }
    
    with open("test_output/cable_validation.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print()
    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print("  ✓ Results saved to test_output/cable_validation.json")
    print()

if __name__ == "__main__":
    main()

