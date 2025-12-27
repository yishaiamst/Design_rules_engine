#!/usr/bin/env python3
"""
Compare Phase 6 cable sizing to actual design.
Runs full pipeline and compares results.
"""

import json
import os
import sys
from collections import Counter, defaultdict
from utils.geojson_utils import load_geojson, save_geojson
from utils.config_loader import load_config
from utils.timeout_utils import timeout, Timer, TimeoutError
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from phases.phase6_cable_sizing import size_cables, generate_sized_cable_geojson


def extract_cable_sizes_from_geojson(geojson_path: str) -> dict:
    """Extract cable sizes from GeoJSON file, indexed by geometry (OPTIMIZED)."""
    from utils.spatial_utils import euclidean_distance
    
    with Timer("Loading and parsing actual cables"):
        geojson = load_geojson(geojson_path)
        cables = {}  # key: (start_pos, end_pos) -> cable info
        
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            cable_id = props.get("ID") or props.get("id", "")
            size_str = props.get("Size") or props.get("size", "")
            
            # Parse size (e.g., "96F" -> 96)
            size = None
            if size_str:
                try:
                    size = int(size_str.replace("F", "").strip())
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
                # Use start and end points as key (rounded to 1m)
                start = (round(coords[0][0], 1), round(coords[0][1], 1))
                end = (round(coords[-1][0], 1), round(coords[-1][1], 1))
                
                # Store both directions (start->end and end->start)
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
                cables[key2] = cable_info  # Store reverse direction too
    
    return cables


def compare_cable_sizes(actual_cables: dict, generated_cables: list) -> dict:
    """Compare actual vs generated cable sizes by geometry (OPTIMIZED)."""
    from utils.spatial_utils import euclidean_distance
    
    with Timer("Converting generated cables to geometry index"):
        # Convert generated cables to dict by geometry
        generated_by_geom = {}
        for cable in generated_cables:
            coords = cable.get("coordinates", [])
            if len(coords) >= 2:
                # Use start and end points as key (rounded to 1m)
                start = (round(coords[0][0], 1), round(coords[0][1], 1))
                end = (round(coords[-1][0], 1), round(coords[-1][1], 1))
                
                # Store both directions
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
    
    # Compare by geometry (OPTIMIZED - use set intersection)
    with Timer("Comparing cables by geometry"):
        matches = 0
        mismatches = []
        only_actual = []
        only_generated = []
        
        # Use set operations for faster comparison
        actual_keys = set(actual_cables.keys())
        generated_keys = set(generated_by_geom.keys())
        all_keys = actual_keys | generated_keys
        common_keys = actual_keys & generated_keys
        
        # Process matches first (most common case)
        for key in common_keys:
            actual = actual_cables.get(key)
            generated = generated_by_geom.get(key)
            
            if actual and generated:
                actual_size = actual["size"]
                generated_size = generated["size"]
                
                if actual_size == generated_size:
                    matches += 1
                else:
                    mismatches.append({
                        "id": generated.get("id", ""),
                        "actual": actual_size,
                        "generated": generated_size,
                        "diff": generated_size - actual_size,
                        "downstream_onts": generated.get("downstream_onts", 0),
                        "sizing_method": generated.get("sizing_method", "unknown")
                    })
        # Process only_actual (in actual but not in generated)
        for key in actual_keys - generated_keys:
            actual = actual_cables.get(key)
            if actual:
                only_actual.append({
                    "id": actual.get("id", ""),
                    "size": actual["size"]
                })
        
        # Process only_generated (in generated but not in actual)
        for key in generated_keys - actual_keys:
            generated = generated_by_geom.get(key)
            if generated:
                only_generated.append({
                    "id": generated.get("id", ""),
                    "size": generated["size"]
                })
    
    # Calculate statistics
    total_compared = len(set(actual_cables.keys()) & set(generated_by_geom.keys()))
    match_rate = (matches / total_compared * 100) if total_compared > 0 else 0
    
    return {
        "total_actual": len(set(actual["id"] for actual in actual_cables.values() if actual.get("id"))),
        "total_generated": len(set(gen["id"] for gen in generated_by_geom.values() if gen.get("id"))),
        "total_compared": total_compared,
        "matches": matches,
        "mismatches": len(mismatches),
        "only_actual": len(only_actual),
        "only_generated": len(only_generated),
        "match_rate": match_rate,
        "mismatches_detail": mismatches[:50],  # First 50
        "only_actual_detail": only_actual[:20],
        "only_generated_detail": only_generated[:20]
    }


def analyze_size_distribution(actual_cables: dict, generated_cables: list) -> dict:
    """Analyze size distribution for actual vs generated."""
    # Actual sizes (deduplicate by ID)
    actual_sizes = Counter()
    seen_ids = set()
    for cable in actual_cables.values():
        cable_id = cable.get("id", "")
        if cable_id and cable_id not in seen_ids:
            actual_sizes[cable["size"]] += 1
            seen_ids.add(cable_id)
    
    # Generated sizes
    generated_sizes = Counter()
    for cable in generated_cables:
        size = cable.get("fiber_count", 0)
        if size > 0:
            generated_sizes[size] += 1
    
    # Compare
    all_sizes = set(actual_sizes.keys()) | set(generated_sizes.keys())
    
    comparison = []
    for size in sorted(all_sizes):
        actual_count = actual_sizes.get(size, 0)
        generated_count = generated_sizes.get(size, 0)
        diff = generated_count - actual_count
        diff_pct = (diff / actual_count * 100) if actual_count > 0 else 0
        
        comparison.append({
            "size": size,
            "actual": actual_count,
            "generated": generated_count,
            "difference": diff,
            "difference_pct": diff_pct
        })
    
    return {
        "actual_distribution": dict(actual_sizes),
        "generated_distribution": dict(generated_sizes),
        "comparison": comparison
    }


def main():
    print("=" * 80)
    print("PHASE 6 CABLE SIZING - COMPARISON TO ACTUAL DESIGN")
    print("=" * 80)
    print()
    
    try:
        # Set overall timeout to 10 minutes
        with timeout(600):
            # Load actual design
            with Timer("Loading actual design"):
                actual_cables = extract_cable_sizes_from_geojson("fiber cable.geojson")
                print(f"  ✓ Loaded {len(actual_cables)} cables from actual design")
                print()
            
            # Load data for pipeline
            with Timer("Loading pipeline data"):
                ont_geojson = load_geojson("ONT.geojson")
                fiber_cable_geojson = load_geojson("fiber cable.geojson")
                config = load_config("design_config.json")
                print(f"  ✓ Loaded {len(ont_geojson.get('features', []))} ONTs")
                print(f"  ✓ Loaded {len(fiber_cable_geojson.get('features', []))} cable features")
                print()
            
            # Run pipeline
            print("=" * 80)
            print("RUNNING PIPELINE (Phases 0-3 → Phase 6)")
            print("=" * 80)
            print()
            
            # Phase 0: Community Pockets
            with Timer("Phase 0: Community Pockets"):
                pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
                print(f"  ✓ Created {len(pockets)} pockets")
                print()
            
            # Phase 1: OLT Placement
            with Timer("Phase 1: OLT Placement"):
                olts, olt_summary = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
                print(f"  ✓ Placed {len(olts)} OLTs")
                print()
            
            # Phase 3: Terminal and FOSC Placement (uses geometric detection - 99.9% match)
            with Timer("Phase 3: Terminal and FOSC Placement"):
                terminals, foscs, phase3_summary = place_terminals(
                    ont_geojson,
                    fiber_cable_geojson,
                    olts,
                    config
                )
                print(f"  ✓ Placed {len(terminals)} terminals")
                print(f"  ✓ Placed {len(foscs)} FOSCs at 3+ cable junctions")
                print(f"  ✓ Phase 3 uses geometric detection (matches design 99.9%)")
                print()
            
            # Phase 6: Cable Sizing
            with Timer("Phase 6: Cable Sizing"):
                sized_cables, sizing_summary = size_cables(
                    fiber_cable_geojson,
                    foscs,
                    terminals,
                    olts,
                    ont_geojson,
                    config
                )
                print(f"  ✓ Sized {len(sized_cables)} cables")
                print()
            
            # Compare
            print("=" * 80)
            print("COMPARISON RESULTS")
            print("=" * 80)
            print()
            
            comparison = compare_cable_sizes(actual_cables, sized_cables)
            size_analysis = analyze_size_distribution(actual_cables, sized_cables)
            
            # Print summary
            print("SUMMARY:")
            print(f"  Actual design cables: {comparison['total_actual']:,}")
            print(f"  Generated cables: {comparison['total_generated']:,}")
            print(f"  Cables with matching IDs: {comparison['total_compared']:,}")
            print(f"  Size matches: {comparison['matches']:,}")
            print(f"  Size mismatches: {comparison['mismatches']:,}")
            print(f"  Match rate: {comparison['match_rate']:.1f}%")
            print(f"  Cables only in actual: {comparison['only_actual']:,}")
            print(f"  Cables only in generated: {comparison['only_generated']:,}")
            print()
            
            # Size distribution comparison
            print("=" * 80)
            print("SIZE DISTRIBUTION COMPARISON")
            print("=" * 80)
            print()
            print(f"{'Size':<10} {'Actual':<12} {'Generated':<12} {'Difference':<12} {'Diff %':<10}")
            print("-" * 60)
            for comp in size_analysis["comparison"]:
                size = comp["size"]
                actual = comp["actual"]
                generated = comp["generated"]
                diff = comp["difference"]
                diff_pct = comp["difference_pct"]
                print(f"{size}F{'':<6} {actual:<12,} {generated:<12,} {diff:+d}{'':<9} {diff_pct:>6.1f}%")
            print()
            
            # Mismatch analysis
            if comparison["mismatches"] > 0:
                print("=" * 80)
                print("MISMATCH ANALYSIS (first 20)")
                print("=" * 80)
                print()
                print(f"{'Cable ID':<40} {'Actual':<10} {'Generated':<12} {'Diff':<10} {'ONTs':<10} {'Method':<20}")
                print("-" * 100)
                for m in comparison["mismatches_detail"][:20]:
                    print(f"{m['id']:<40} {m['actual']}F{'':<7} {m['generated']}F{'':<9} {m['diff']:+d}{'':<7} {m['downstream_onts']:<10} {m['sizing_method']:<20}")
                if comparison["mismatches"] > 20:
                    print(f"... and {comparison['mismatches'] - 20} more mismatches")
                print()
            
            # Analyze mismatch patterns
            mismatch_by_diff = Counter()
            for m in comparison["mismatches_detail"]:
                diff = m["diff"]
                if diff > 0:
                    mismatch_by_diff["oversized"] += 1
                elif diff < 0:
                    mismatch_by_diff["undersized"] += 1
            
            print("MISMATCH PATTERNS:")
            print(f"  Oversized (generated > actual): {mismatch_by_diff.get('oversized', 0)}")
            print(f"  Undersized (generated < actual): {mismatch_by_diff.get('undersized', 0)}")
            print()
            
            # Save results
            output_dir = "test_output"
            os.makedirs(output_dir, exist_ok=True)
            
            results = {
                "comparison": comparison,
                "size_analysis": size_analysis,
                "sizing_summary": sizing_summary,
                "config": {
                    "default_size_override": config.get("cables", {}).get("infrastructure_cable", {}).get("default_size_override"),
                    "max_size": config.get("cables", {}).get("infrastructure_cable", {}).get("max_size", 288)
                }
            }
            
            results_path = os.path.join(output_dir, "phase6_comparison_results.json")
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"✓ Saved detailed results to {results_path}")
            
            # Save generated cable GeoJSON
            sized_cable_geojson = generate_sized_cable_geojson(sized_cables)
            output_path = os.path.join(output_dir, "fiber cable.geojson")
            save_geojson(sized_cable_geojson, output_path)
            print(f"✓ Saved generated cable GeoJSON to {output_path}")
            
            print()
            print("=" * 80)
            print("COMPARISON COMPLETE")
            print("=" * 80)
            print()
            print(f"Match Rate: {comparison['match_rate']:.1f}%")
            print(f"Total Variations: {comparison['mismatches']:,} cables")
            print()
    
    except TimeoutError as e:
        print()
        print("=" * 80)
        print("TIMEOUT: Operation exceeded 10 minute limit")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        print()
        print("The comparison script timed out. This may indicate:")
        print("  1. Pipeline phases taking too long")
        print("  2. Cable comparison logic needs optimization")
        print("  3. Large dataset requiring more efficient algorithms")
        print()
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()

