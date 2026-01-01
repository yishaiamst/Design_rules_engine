#!/usr/bin/env python3
"""
Show detailed cable sizing comparison: Generated vs Actual Design
"""

import json
import os
from collections import Counter, defaultdict
from utils.geojson_utils import load_geojson

def main():
    print("=" * 80)
    print("CABLE SIZING COMPARISON: GENERATED VS ACTUAL DESIGN")
    print("=" * 80)
    print()
    
    # Load comparison results if available
    results_path = "test_output/phase6_comparison_results.json"
    if os.path.exists(results_path):
        with open(results_path, "r") as f:
            results = json.load(f)
        
        comparison = results.get("comparison", {})
        size_analysis = results.get("size_analysis", {})
        
        print("OVERALL SUMMARY")
        print("-" * 80)
        print(f"Match Rate: {comparison.get('match_rate', 0):.2f}%")
        print(f"Total Compared: {comparison.get('total_compared', 0):,} cables")
        print(f"Matches: {comparison.get('matches', 0):,}")
        print(f"Mismatches: {comparison.get('mismatches', 0):,}")
        print()
        
        # Size distribution
        print("=" * 80)
        print("SIZE DISTRIBUTION COMPARISON")
        print("=" * 80)
        print()
        print(f"{'Size':<10} {'Actual':<12} {'Generated':<12} {'Difference':<12} {'Diff %':<10}")
        print("-" * 60)
        
        for comp in size_analysis.get("comparison", []):
            size = comp["size"]
            actual = comp["actual"]
            generated = comp["generated"]
            diff = comp["difference"]
            diff_pct = comp["difference_pct"]
            print(f"{size}F{'':<6} {actual:<12,} {generated:<12,} {diff:+d}{'':<9} {diff_pct:>6.1f}%")
        print()
        
        # Mismatch examples
        mismatches = comparison.get("mismatches_detail", [])
        if mismatches:
            print("=" * 80)
            print("MISMATCH EXAMPLES (First 30)")
            print("=" * 80)
            print()
            print(f"{'Cable ID':<40} {'Actual':<10} {'Generated':<12} {'Diff':<10} {'ONTs':<10} {'Method':<20}")
            print("-" * 100)
            
            for m in mismatches[:30]:
                print(f"{m['id']:<40} {m['actual']}F{'':<7} {m['generated']}F{'':<9} {m['diff']:+d}{'':<7} {m['downstream_onts']:<10} {m['sizing_method']:<20}")
            print()
            
            # Group mismatches by pattern
            print("=" * 80)
            print("MISMATCH PATTERNS")
            print("=" * 80)
            print()
            
            pattern_counts = defaultdict(int)
            for m in mismatches:
                pattern = f"{m['actual']}F → {m['generated']}F"
                pattern_counts[pattern] += 1
            
            print("Most Common Mismatch Patterns:")
            for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {pattern}: {count:,} cables")
            print()
        
        # Load actual and generated GeoJSON for detailed analysis
        print("=" * 80)
        print("LOADING ACTUAL AND GENERATED CABLES")
        print("=" * 80)
        print()
        
        actual_geojson = load_geojson("fiber cable.geojson")
        generated_geojson = load_geojson("test_output/fiber cable.geojson")
        
        # Extract sizes
        actual_sizes = Counter()
        generated_sizes = Counter()
        
        for feature in actual_geojson.get("features", []):
            props = feature.get("properties", {})
            size_str = props.get("Size") or props.get("size", "")
            if size_str:
                try:
                    size = int(str(size_str).replace("F", "").strip())
                    actual_sizes[size] += 1
                except:
                    pass
        
        for feature in generated_geojson.get("features", []):
            props = feature.get("properties", {})
            size = props.get("FiberCount", 0)
            if size > 0:
                generated_sizes[size] += 1
        
        print("ACTUAL DESIGN SIZE DISTRIBUTION:")
        for size, count in sorted(actual_sizes.items()):
            print(f"  {size}F: {count:,} cables")
        print()
        
        print("GENERATED DESIGN SIZE DISTRIBUTION:")
        for size, count in sorted(generated_sizes.items()):
            print(f"  {size}F: {count:,} cables")
        print()
        
    else:
        print("⚠️  Comparison results not found. Run compare_phase6_to_design.py first.")
        print()

if __name__ == "__main__":
    main()
