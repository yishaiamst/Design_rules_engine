#!/usr/bin/env python3
"""
Analyze Generated vs Actual Cable Sizing
Detailed comparison with examples and patterns
"""

import json
import os
from collections import Counter, defaultdict
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.spatial_utils import euclidean_distance
from utils.timeout_utils import timeout, Timer, TimeoutError
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from phases.phase6_cable_sizing import size_cables, generate_sized_cable_geojson


def extract_cable_sizes(geojson_path: str) -> dict:
    """Extract cable sizes from GeoJSON, indexed by geometry."""
    geojson = load_geojson(geojson_path)
    cables = {}  # key: (start_pos, end_pos) -> cable info
    
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        # Parse size
        size = None
        size_str = props.get("Size") or props.get("size", "")
        if size_str:
            try:
                size = int(str(size_str).replace("F", "").strip())
            except (ValueError, AttributeError):
                pass
        
        # Extract coordinates
        coords = []
        geom_type = geometry.get("type", "")
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2 and size:
            start = (round(coords[0][0], 1), round(coords[0][1], 1))
            end = (round(coords[-1][0], 1), round(coords[-1][1], 1))
            
            key1 = (start, end)
            key2 = (end, start)
            
            cable_info = {
                "id": cable_id,
                "size": size,
                "start": start,
                "end": end,
                "coordinates": coords,
                "properties": props
            }
            
            cables[key1] = cable_info
            cables[key2] = cable_info
    
    return cables


def analyze_sizing_comparison():
    """Analyze generated vs actual cable sizing in detail."""
    try:
        with timeout(600):  # 10 minutes
            print("=" * 80)
            print("CABLE SIZING COMPARISON: GENERATED VS ACTUAL DESIGN")
            print("=" * 80)
            print()
            
            # Load actual design
            with Timer("Loading actual design"):
                actual_cables = extract_cable_sizes("fiber cable.geojson")
                print(f"  ✓ Loaded {len(set(c.get('id') for c in actual_cables.values() if c.get('id')))} actual cables")
                print()
            
            # Run pipeline to get generated sizing
            with Timer("Running pipeline (Phases 0-3 → Phase 6)"):
                ont_geojson = load_geojson("ONT.geojson")
                fiber_cable_geojson = load_geojson("fiber cable.geojson")
                config = load_config("design_config.json")
                
                # Run pipeline
                pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
                olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
                terminals, foscs, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, config)
                sized_cables, sizing_summary = size_cables(
                    fiber_cable_geojson, foscs, terminals, olts, ont_geojson, config
                )
                print()
            
            # Convert generated to geometry index
            with Timer("Indexing generated cables"):
                generated_by_geom = {}
                for cable in sized_cables:
                    coords = cable.get("coordinates", [])
                    if len(coords) >= 2:
                        start = (round(coords[0][0], 1), round(coords[0][1], 1))
                        end = (round(coords[-1][0], 1), round(coords[-1][1], 1))
                        
                        key1 = (start, end)
                        key2 = (end, start)
                        
                        cable_info = {
                            "id": cable.get("cable_id") or cable.get("original_id", ""),
                            "size": cable.get("fiber_count", 0),
                            "required_fibers": cable.get("required_fibers", 0),
                            "downstream_onts": cable.get("downstream_onts", 0),
                            "sizing_method": cable.get("sizing_method", "unknown"),
                            "start": start,
                            "end": end
                        }
                        
                        generated_by_geom[key1] = cable_info
                        generated_by_geom[key2] = cable_info
            
            # Compare
            print("=" * 80)
            print("DETAILED SIZE COMPARISON")
            print("=" * 80)
            print()
            
            # Size distribution
            actual_sizes = Counter()
            generated_sizes = Counter()
            matches_by_size = defaultdict(int)
            mismatches_by_size = defaultdict(list)
            
            actual_keys = set(actual_cables.keys())
            generated_keys = set(generated_by_geom.keys())
            common_keys = actual_keys & generated_keys
            
            for key in common_keys:
                actual = actual_cables.get(key)
                generated = generated_by_geom.get(key)
                
                if actual and generated:
                    actual_size = actual["size"]
                    generated_size = generated["size"]
                    
                    # Deduplicate by ID
                    cable_id = actual.get("id", "")
                    if cable_id:
                        actual_sizes[actual_size] += 1
                        generated_sizes[generated_size] += 1
                        
                        if actual_size == generated_size:
                            matches_by_size[actual_size] += 1
                        else:
                            mismatches_by_size[actual_size].append({
                                "id": cable_id,
                                "actual": actual_size,
                                "generated": generated_size,
                                "diff": generated_size - actual_size,
                                "downstream_onts": generated.get("downstream_onts", 0),
                                "sizing_method": generated.get("sizing_method", "unknown")
                            })
            
            # Print size distribution comparison
            print("SIZE DISTRIBUTION COMPARISON")
            print("-" * 80)
            print(f"{'Size':<10} {'Actual':<12} {'Generated':<12} {'Matches':<12} {'Match %':<10} {'Mismatches':<12}")
            print("-" * 80)
            
            all_sizes = set(actual_sizes.keys()) | set(generated_sizes.keys())
            total_matches = 0
            total_mismatches = 0
            
            for size in sorted(all_sizes):
                actual_count = actual_sizes.get(size, 0)
                generated_count = generated_sizes.get(size, 0)
                matches = matches_by_size.get(size, 0)
                mismatches = len(mismatches_by_size.get(size, []))
                
                match_pct = (matches / actual_count * 100) if actual_count > 0 else 0
                
                print(f"{size}F{'':<6} {actual_count:<12,} {generated_count:<12,} {matches:<12,} {match_pct:>6.1f}%{'':<3} {mismatches:<12,}")
                
                total_matches += matches
                total_mismatches += mismatches
            
            print("-" * 80)
            total_compared = sum(actual_sizes.values())
            overall_match_rate = (total_matches / total_compared * 100) if total_compared > 0 else 0
            print(f"{'TOTAL':<10} {total_compared:<12,} {sum(generated_sizes.values()):<12,} {total_matches:<12,} {overall_match_rate:>6.1f}%{'':<3} {total_mismatches:<12,}")
            print()
            
            # Analyze mismatch patterns
            print("=" * 80)
            print("MISMATCH PATTERNS BY SIZE")
            print("=" * 80)
            print()
            
            for size in sorted(mismatches_by_size.keys()):
                mismatches = mismatches_by_size[size]
                if not mismatches:
                    continue
                
                print(f"{size}F Actual → Generated:")
                print(f"  Total mismatches: {len(mismatches)}")
                
                # Group by generated size
                by_generated = defaultdict(list)
                for m in mismatches:
                    by_generated[m["generated"]].append(m)
                
                for gen_size in sorted(by_generated.keys()):
                    count = len(by_generated[gen_size])
                    examples = by_generated[gen_size][:3]  # First 3 examples
                    print(f"    → {gen_size}F: {count} cables")
                    for ex in examples:
                        print(f"      - {ex['id']}: {ex['actual']}F → {ex['generated']}F (diff: {ex['diff']:+d}, ONTs: {ex['downstream_onts']}, method: {ex['sizing_method']})")
                print()
            
            # Analyze sizing methods
            print("=" * 80)
            print("SIZING METHOD ANALYSIS")
            print("=" * 80)
            print()
            
            method_stats = defaultdict(lambda: {"count": 0, "matches": 0, "mismatches": 0})
            
            for key in common_keys:
                actual = actual_cables.get(key)
                generated = generated_by_geom.get(key)
                
                if actual and generated:
                    method = generated.get("sizing_method", "unknown")
                    method_stats[method]["count"] += 1
                    
                    if actual["size"] == generated["size"]:
                        method_stats[method]["matches"] += 1
                    else:
                        method_stats[method]["mismatches"] += 1
            
            print(f"{'Method':<25} {'Total':<12} {'Matches':<12} {'Mismatches':<12} {'Match %':<10}")
            print("-" * 80)
            for method, stats in sorted(method_stats.items()):
                match_pct = (stats["matches"] / stats["count"] * 100) if stats["count"] > 0 else 0
                print(f"{method:<25} {stats['count']:<12,} {stats['matches']:<12,} {stats['mismatches']:<12,} {match_pct:>6.1f}%")
            print()
            
            # Save detailed results
            results = {
                "size_distribution": {
                    "actual": dict(actual_sizes),
                    "generated": dict(generated_sizes),
                    "matches": dict(matches_by_size)
                },
                "mismatch_analysis": {
                    size: mismatches[:20]  # First 20 per size
                    for size, mismatches in mismatches_by_size.items()
                },
                "sizing_method_stats": dict(method_stats),
                "overall_match_rate": overall_match_rate,
                "total_compared": total_compared,
                "total_matches": total_matches,
                "total_mismatches": total_mismatches
            }
            
            os.makedirs("test_output", exist_ok=True)
            results_path = os.path.join("test_output", "cable_sizing_detailed_comparison.json")
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"✓ Saved detailed comparison to {results_path}")
            print()
            
            # Summary
            print("=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print()
            print(f"Overall Match Rate: {overall_match_rate:.2f}%")
            print(f"Total Compared: {total_compared:,} cables")
            print(f"Matches: {total_matches:,}")
            print(f"Mismatches: {total_mismatches:,}")
            print()
            
            # Key findings
            print("KEY FINDINGS:")
            print()
            
            # Most common actual sizes
            top_actual = actual_sizes.most_common(5)
            print("Most Common Actual Sizes:")
            for size, count in top_actual:
                gen_count = generated_sizes.get(size, 0)
                matches = matches_by_size.get(size, 0)
                match_pct = (matches / count * 100) if count > 0 else 0
                print(f"  {size}F: {count:,} actual, {gen_count:,} generated, {matches:,} matches ({match_pct:.1f}%)")
            print()
            
            # Most common generated sizes
            top_generated = generated_sizes.most_common(5)
            print("Most Common Generated Sizes:")
            for size, count in top_generated:
                actual_count = actual_sizes.get(size, 0)
                matches = matches_by_size.get(size, 0)
                match_pct = (matches / actual_count * 100) if actual_count > 0 else 0
                print(f"  {size}F: {count:,} generated, {actual_count:,} actual, {matches:,} matches ({match_pct:.1f}%)")
            print()
    
    except TimeoutError:
        print()
        print("=" * 80)
        print("TIMEOUT: Analysis exceeded 10 minute limit")
        print("=" * 80)
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    import sys
    analyze_sizing_comparison()
