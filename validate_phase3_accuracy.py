#!/usr/bin/env python3
"""
Validate Phase 3 accuracy against actual design.
Compares FOSCs and terminals placement.
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


def match_by_position(actual_items: list, generated_items: list, tolerance_m: float = 10.0) -> dict:
    """
    Match items by position within tolerance.
    
    Returns:
        {
            "matches": count,
            "only_actual": count,
            "only_generated": count,
            "match_rate": percentage
        }
    """
    # Build spatial index for generated items
    generated_by_pos = {}
    for item in generated_items:
        pos = item.get("position")
        if pos:
            rounded_pos = (
                round(pos[0] / tolerance_m) * tolerance_m,
                round(pos[1] / tolerance_m) * tolerance_m
            )
            generated_by_pos[rounded_pos] = item
    
    # Match actual items
    matches = 0
    only_actual = []
    only_generated = []
    
    actual_positions = set()
    for item in actual_items:
        pos = item.get("position")
        if pos:
            rounded_pos = (
                round(pos[0] / tolerance_m) * tolerance_m,
                round(pos[1] / tolerance_m) * tolerance_m
            )
            actual_positions.add(rounded_pos)
            
            if rounded_pos in generated_by_pos:
                matches += 1
            else:
                only_actual.append(item)
    
    # Find only_generated
    for rounded_pos, item in generated_by_pos.items():
        if rounded_pos not in actual_positions:
            only_generated.append(item)
    
    match_rate = (matches / len(actual_items) * 100) if actual_items else 0
    
    return {
        "matches": matches,
        "only_actual": len(only_actual),
        "only_generated": len(only_generated),
        "match_rate": match_rate,
        "total_actual": len(actual_items),
        "total_generated": len(generated_items)
    }


def validate_phase3():
    """Validate Phase 3 FOSC and terminal placement against actual design."""
    try:
        with timeout(600):  # 10 minutes
            print("=" * 80)
            print("VALIDATING PHASE 3 ACCURACY")
            print("=" * 80)
            print()
            
            # Load actual design
            with Timer("Loading actual design"):
                actual_foscs_geojson = load_geojson("splice closure.geojson")
                actual_terminals_geojson = load_geojson("terminal.geojson")
                
                # Extract actual FOSCs
                actual_foscs = []
                for feature in actual_foscs_geojson.get("features", []):
                    geometry = feature.get("geometry", {})
                    props = feature.get("properties", {})
                    coords = geometry.get("coordinates", [])
                    if geometry.get("type") == "Point" and len(coords) >= 2:
                        actual_foscs.append({
                            "id": props.get("ID") or props.get("id", ""),
                            "position": (coords[0], coords[1]),
                            "properties": props
                        })
                
                # Extract actual terminals
                actual_terminals = []
                for feature in actual_terminals_geojson.get("features", []):
                    geometry = feature.get("geometry", {})
                    props = feature.get("properties", {})
                    coords = geometry.get("coordinates", [])
                    if geometry.get("type") == "Point" and len(coords) >= 2:
                        actual_terminals.append({
                            "id": props.get("ID") or props.get("id", ""),
                            "position": (coords[0], coords[1]),
                            "type": props.get("Type") or props.get("type", ""),
                            "properties": props
                        })
                
                print(f"  ✓ Loaded {len(actual_foscs)} actual FOSCs")
                print(f"  ✓ Loaded {len(actual_terminals)} actual terminals")
                print()
            
            # Run Phase 3
            with Timer("Running Phase 3"):
                ont_geojson = load_geojson("ONT.geojson")
                fiber_cable_geojson = load_geojson("fiber cable.geojson")
                config = load_config("design_config.json")
                
                # Run pipeline to get inputs
                pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
                olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
                
                # Run Phase 3
                terminals, foscs, phase3_summary = place_terminals(
                    ont_geojson,
                    fiber_cable_geojson,
                    olts,
                    config
                )
                
                print(f"  ✓ Phase 3 placed {len(foscs)} FOSCs")
                print(f"  ✓ Phase 3 placed {len(terminals)} terminals")
                print()
            
            # Validate FOSCs
            print("=" * 80)
            print("FOSC VALIDATION")
            print("=" * 80)
            print()
            
            fosc_results = match_by_position(actual_foscs, foscs, tolerance_m=10.0)
            
            print(f"Actual FOSCs: {fosc_results['total_actual']:,}")
            print(f"Generated FOSCs: {fosc_results['total_generated']:,}")
            print(f"Matches: {fosc_results['matches']:,}")
            print(f"Only in actual: {fosc_results['only_actual']:,}")
            print(f"Only in generated: {fosc_results['only_generated']:,}")
            print(f"Match Rate: {fosc_results['match_rate']:.2f}%")
            print()
            
            # Validate Terminals
            print("=" * 80)
            print("TERMINAL VALIDATION")
            print("=" * 80)
            print()
            
            terminal_results = match_by_position(actual_terminals, terminals, tolerance_m=10.0)
            
            print(f"Actual Terminals: {terminal_results['total_actual']:,}")
            print(f"Generated Terminals: {terminal_results['total_generated']:,}")
            print(f"Matches: {terminal_results['matches']:,}")
            print(f"Only in actual: {terminal_results['only_actual']:,}")
            print(f"Only in generated: {terminal_results['only_generated']:,}")
            print(f"Match Rate: {terminal_results['match_rate']:.2f}%")
            print()
            
            # Analyze by type
            print("=" * 80)
            print("TERMINAL TYPE ANALYSIS")
            print("=" * 80)
            print()
            
            actual_types = Counter(t.get("type", "Unknown") for t in actual_terminals)
            generated_types = Counter(t.get("type", "Unknown") for t in terminals)
            
            print("Actual Terminal Types:")
            for term_type, count in sorted(actual_types.items()):
                print(f"  {term_type}: {count:,}")
            print()
            
            print("Generated Terminal Types:")
            for term_type, count in sorted(generated_types.items()):
                print(f"  {term_type}: {count:,}")
            print()
            
            # Save results
            results = {
                "fosc_validation": fosc_results,
                "terminal_validation": terminal_results,
                "phase3_summary": phase3_summary,
                "actual_types": dict(actual_types),
                "generated_types": dict(generated_types)
            }
            
            os.makedirs("test_output", exist_ok=True)
            results_path = os.path.join("test_output", "phase3_accuracy_validation.json")
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"✓ Saved validation results to {results_path}")
            print()
            
            # Summary
            print("=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print()
            print(f"FOSC Match Rate: {fosc_results['match_rate']:.2f}%")
            print(f"Terminal Match Rate: {terminal_results['match_rate']:.2f}%")
            print()
            
            if fosc_results['match_rate'] >= 99.0 and terminal_results['match_rate'] >= 99.0:
                print("✅ EXCELLENT: Phase 3 matches design with >99% accuracy")
            elif fosc_results['match_rate'] >= 95.0 and terminal_results['match_rate'] >= 95.0:
                print("✅ GOOD: Phase 3 matches design with >95% accuracy")
            elif fosc_results['match_rate'] >= 90.0 and terminal_results['match_rate'] >= 90.0:
                print("⚠️  ACCEPTABLE: Phase 3 matches design with >90% accuracy")
            else:
                print("⚠️  NEEDS IMPROVEMENT: Phase 3 match rate is <90%")
            print()
    
    except TimeoutError:
        print()
        print("=" * 80)
        print("TIMEOUT: Validation exceeded 10 minute limit")
        print("=" * 80)
        print()
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        sys.exit(1)


if __name__ == "__main__":
    import sys
    validate_phase3()
