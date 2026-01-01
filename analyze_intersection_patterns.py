#!/usr/bin/env python3
"""
Analyze intersection patterns from actual design to learn sizing rules.
"""

import json
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any
from utils.geojson_utils import load_geojson

def extract_fiber_count(value):
    """Extract fiber count from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.search(r'(\d+)', str(value))
        if match:
            return int(match.group(1))
    return None

def load_actual_cables():
    """Load actual design cables with sizes and coordinates."""
    print("Loading actual design cables...")
    actual = load_geojson("fiber cable.geojson")
    
    cables = []
    for feat in actual.get("features", []):
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        # Extract size
        size = None
        for field in ["FiberCount", "Size", "size", "fiber_count"]:
            val = props.get(field)
            if val:
                size = extract_fiber_count(val)
                if size:
                    break
        if not size and cable_id:
            size = extract_fiber_count(cable_id)
        
        # Extract coordinates
        coords = []
        geom_type = geometry.get("type", "")
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if size and len(coords) >= 2:
            cables.append({
                "id": cable_id,
                "size": size,
                "coordinates": coords,
                "start": tuple(coords[0][:2]) if coords else None,
                "end": tuple(coords[-1][:2]) if coords else None
            })
    
    print(f"  Loaded {len(cables)} cables with sizes")
    return cables

def find_intersections(cables: List[Dict[str, Any]], tolerance_m: float = 10.0) -> Dict[Tuple[float, float], List[Dict[str, Any]]]:
    """
    Find cable intersections based on endpoint proximity.
    Returns: intersection_position -> [cables meeting there]
    """
    print(f"Finding intersections (tolerance: {tolerance_m}m)...")
    
    # Build spatial index for endpoints
    endpoint_to_cables = defaultdict(list)
    grid_size = tolerance_m
    
    for cable in cables:
        if not cable.get("start") or not cable.get("end"):
            continue
        
        start = cable["start"]
        end = cable["end"]
        
        # Round to grid
        start_key = (int(start[0] / grid_size) * grid_size, int(start[1] / grid_size) * grid_size)
        end_key = (int(end[0] / grid_size) * grid_size, int(end[1] / grid_size) * grid_size)
        
        endpoint_to_cables[start_key].append(cable)
        endpoint_to_cables[end_key].append(cable)
    
    # Filter to intersections (≥2 cables)
    intersections = {pos: cable_list for pos, cable_list in endpoint_to_cables.items() if len(cable_list) >= 2}
    
    print(f"  Found {len(intersections)} intersections")
    return intersections

def analyze_intersection_patterns(intersections: Dict[Tuple[float, float], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Analyze patterns at intersections:
    - How many cables of each size meet
    - What size the upstream cable should be
    - Common patterns (e.g., 3x 48F → 144F)
    """
    print("\nAnalyzing intersection patterns...")
    
    patterns = defaultdict(list)  # pattern_key -> [examples]
    size_transitions = defaultdict(int)  # (downstream_sizes_tuple, upstream_size) -> count
    
    for intersection_pos, cables in intersections.items():
        if len(cables) < 2:
            continue
        
        # Get sizes of all cables at intersection
        sizes = [c["size"] for c in cables if c.get("size")]
        if not sizes or len(sizes) < 2:
            continue
        
        # Count size distribution
        size_counts = Counter(sizes)
        
        # For now, we can't easily determine upstream/downstream from geometry alone
        # But we can analyze common size combinations
        sizes_sorted = tuple(sorted(sizes))
        pattern_key = f"{len(sizes)} cables: {dict(size_counts)}"
        
        patterns[pattern_key].append({
            "position": intersection_pos,
            "cables": [{"id": c["id"], "size": c["size"]} for c in cables],
            "size_distribution": dict(size_counts)
        })
    
    # Analyze most common patterns
    print("\nMost common intersection patterns:")
    pattern_counts = {k: len(v) for k, v in patterns.items()}
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"  {pattern}: {count} intersections")
    
    # Analyze size combinations
    print("\nAnalyzing size combinations at intersections...")
    size_combinations = defaultdict(int)
    for pattern_key, examples in patterns.items():
        for example in examples:
            sizes = sorted(example["size_distribution"].keys())
            if len(sizes) >= 2:
                combo_key = tuple(sizes)
                size_combinations[combo_key] += 1
    
    print("\nMost common size combinations:")
    for combo, count in sorted(size_combinations.items(), key=lambda x: x[1], reverse=True)[:15]:
        sizes_str = ", ".join(f"{s}F" for s in combo)
        print(f"  [{sizes_str}]: {count} intersections")
    
    return {
        "patterns": dict(patterns),
        "pattern_counts": dict(pattern_counts),
        "size_combinations": dict(size_combinations)
    }

def analyze_size_transitions(cables: List[Dict[str, Any]], intersections: Dict) -> Dict[str, Any]:
    """
    Analyze size transitions: when multiple cables of one size meet,
    what size does the upstream cable typically have?
    """
    print("\nAnalyzing size transitions at intersections...")
    
    # This is a simplified analysis - in reality we'd need to determine
    # which cable is upstream based on network topology
    # For now, we'll look for patterns where multiple cables of same size meet
    
    transition_patterns = defaultdict(list)  # (input_sizes) -> [output_sizes]
    
    for intersection_pos, cables_at_intersection in intersections.items():
        if len(cables_at_intersection) < 2:
            continue
        
        sizes = [c["size"] for c in cables_at_intersection if c.get("size")]
        if len(sizes) < 2:
            continue
        
        size_counts = Counter(sizes)
        
        # Look for patterns like "3x 48F cables"
        for size, count in size_counts.items():
            if count >= 2:
                # Multiple cables of same size
                other_sizes = [s for s in sizes if s != size]
                if other_sizes:
                    # There's at least one cable of different size
                    # This might be the upstream cable
                    for other_size in set(other_sizes):
                        pattern = f"{count}x {size}F → {other_size}F"
                        transition_patterns[pattern].append({
                            "position": intersection_pos,
                            "cables": [{"id": c["id"], "size": c["size"]} for c in cables_at_intersection]
                        })
    
    print("\nSize transition patterns:")
    for pattern, examples in sorted(transition_patterns.items(), key=lambda x: len(x[1]), reverse=True)[:15]:
        print(f"  {pattern}: {len(examples)} occurrences")
        # Show first example
        if examples:
            example = examples[0]
            cable_ids = [c["id"][:30] for c in example["cables"][:4]]
            print(f"    Example: {', '.join(cable_ids)}...")
    
    return {
        "transition_patterns": {k: len(v) for k, v in transition_patterns.items()},
        "transition_examples": {k: v[:3] for k, v in transition_patterns.items()}  # Keep first 3 examples
    }

def main():
    """Main analysis."""
    print("=" * 80)
    print("INTERSECTION PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    # Load cables
    cables = load_actual_cables()
    
    # Find intersections
    intersections = find_intersections(cables, tolerance_m=10.0)
    
    # Analyze patterns
    pattern_analysis = analyze_intersection_patterns(intersections)
    
    # Analyze size transitions
    transition_analysis = analyze_size_transitions(cables, intersections)
    
    # Save results
    results = {
        "intersection_count": len(intersections),
        "pattern_analysis": pattern_analysis,
        "transition_analysis": transition_analysis
    }
    
    with open("intersection_patterns.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n" + "=" * 80)
    print("RESULTS SAVED")
    print("=" * 80)
    print("  ✓ Saved intersection_patterns.json")
    print()
    
    # Summary
    print("SUMMARY:")
    print(f"  - Analyzed {len(intersections)} intersections")
    print(f"  - Found {len(pattern_analysis['patterns'])} unique patterns")
    print(f"  - Identified {len(transition_analysis['transition_patterns'])} transition patterns")
    print()

if __name__ == "__main__":
    main()

