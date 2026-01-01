#!/usr/bin/env python3
"""
analyze_olt_placement_comparison.py
-------------------------------------------------------------------------------
Compare generated OLT placements with actual design OLT placements.
Analyze differences and understand the logic used in the actual design.
-------------------------------------------------------------------------------
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, List, Any, Tuple, Optional
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance, calculate_centroid
from collections import defaultdict

def load_actual_olts(filepath: str = "OLT.geojson") -> Dict[str, Dict[str, Any]]:
    """Load actual OLT positions from design."""
    print(f"Loading actual OLTs from {filepath}...")
    olt_geojson = load_geojson(filepath)
    
    olts = {}
    for feature in olt_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        olt_id = str(props.get("ID") or props.get("id", ""))
        if not olt_id:
            continue
        
        # Extract position
        coords = None
        geom_type = geometry.get("type", "")
        
        if geom_type == "Point":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if coords and len(coords) >= 2:
            olts[olt_id] = {
                "olt_id": olt_id,
                "position": (coords[0], coords[1]),
                "name": props.get("Name", ""),
                "subscribers": props.get("NoOfAddr", ""),
                "properties": props
            }
    
    print(f"  ✓ Loaded {len(olts)} actual OLTs")
    return olts

def load_generated_olts(filepath: str = "test_output/OLT.geojson") -> Dict[str, Dict[str, Any]]:
    """Load generated OLT positions."""
    print(f"Loading generated OLTs from {filepath}...")
    olt_geojson = load_geojson(filepath)
    
    olts = {}
    for feature in olt_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        olt_id = str(props.get("ID", ""))
        if not olt_id:
            continue
        
        coords = geometry.get("coordinates", [])
        if len(coords) >= 2:
            olts[olt_id] = {
                "olt_id": olt_id,
                "position": (coords[0], coords[1]),
                "pocket_id": props.get("pocket_id", ""),
                "ont_count": props.get("ont_count", 0),
                "placement_method": props.get("placement_method", ""),
                "max_distance_km": props.get("max_distance_km", 0),
                "violation_count": props.get("violation_count", 0),
                "nearest_cable_id": props.get("nearest_cable_id", ""),
                "nearest_cable_fiber_count": props.get("nearest_cable_fiber_count", 0),
                "distance_to_cable_km": props.get("distance_to_cable_km", 0)
            }
    
    print(f"  ✓ Loaded {len(olts)} generated OLTs")
    return olts

def load_olt_ont_assignments(filepath: str = "olt_ont_paths.json") -> Dict[str, List[str]]:
    """Load actual OLT-ONT assignments."""
    print(f"Loading OLT-ONT assignments from {filepath}...")
    with open(filepath, 'r') as f:
        paths = json.load(f)
    
    olt_ont_map = defaultdict(list)
    for path in paths:
        olt_id = str(path.get('olt_id', ''))
        ont_id = str(path.get('ont_id', ''))
        if olt_id and ont_id:
            olt_ont_map[olt_id].append(ont_id)
    
    print(f"  ✓ Loaded assignments for {len(olt_ont_map)} OLTs")
    return dict(olt_ont_map)

def load_ont_positions(filepath: str = "ONT.geojson") -> Dict[str, Tuple[float, float]]:
    """Load ONT positions."""
    print(f"Loading ONT positions from {filepath}...")
    ont_geojson = load_geojson(filepath)
    
    ont_positions = {}
    for feature in ont_geojson.get("features", []):
        ont_id = str(feature.get("properties", {}).get("ID") or 
                    feature.get("properties", {}).get("id", ""))
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                ont_positions[ont_id] = (coords[0], coords[1])
    
    print(f"  ✓ Loaded {len(ont_positions)} ONT positions")
    return ont_positions

def find_nearest_olt(generated_olt: Dict[str, Any], actual_olts: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], float]:
    """Find nearest actual OLT to generated OLT."""
    gen_pos = generated_olt["position"]
    min_distance = float('inf')
    nearest_olt_id = None
    
    for olt_id, actual_olt in actual_olts.items():
        actual_pos = actual_olt["position"]
        distance = euclidean_distance(
            gen_pos[0], gen_pos[1],
            actual_pos[0], actual_pos[1]
        ) / 1000.0  # Convert to km
        
        if distance < min_distance:
            min_distance = distance
            nearest_olt_id = olt_id
    
    return (nearest_olt_id, min_distance)

def calculate_ont_centroid_for_olt(olt_id: str, olt_ont_map: Dict[str, List[str]], ont_positions: Dict[str, Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Calculate centroid of ONTs assigned to an OLT."""
    ont_ids = olt_ont_map.get(olt_id, [])
    if not ont_ids:
        return None
    
    positions = []
    for ont_id in ont_ids:
        if ont_id in ont_positions:
            positions.append(ont_positions[ont_id])
    
    if not positions:
        return None
    
    return calculate_centroid(positions)

def find_nearest_infrastructure_cable_to_olt(
    olt_position: Tuple[float, float],
    fiber_cable_geojson: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], float, Optional[Tuple[float, float]]]:
    """Find nearest main infrastructure cable to OLT position."""
    from phases.phase1_place_olts import find_main_infrastructure_cables, find_nearest_infrastructure_cable
    
    main_cables = find_main_infrastructure_cables(fiber_cable_geojson)
    if not main_cables:
        return (None, float('inf'), None)
    
    cable, distance_m, nearest_point = find_nearest_infrastructure_cable(olt_position, main_cables)
    return (cable, distance_m / 1000.0, nearest_point)  # Convert to km

def analyze_placement_differences():
    """Main analysis function."""
    print("=" * 80)
    print("OLT PLACEMENT COMPARISON ANALYSIS")
    print("=" * 80)
    print()
    
    # Load data
    actual_olts = load_actual_olts()
    generated_olts = load_generated_olts()
    olt_ont_map = load_olt_ont_assignments()
    ont_positions = load_ont_positions()
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    
    print()
    print("=" * 80)
    print("MATCHING GENERATED OLTS TO ACTUAL OLTS")
    print("=" * 80)
    print()
    
    # Match generated OLTs to actual OLTs
    matches = []
    unmatched_generated = []
    unmatched_actual = set(actual_olts.keys())
    
    for gen_olt_id, gen_olt in generated_olts.items():
        nearest_actual_id, distance_km = find_nearest_olt(gen_olt, actual_olts)
        
        if nearest_actual_id and distance_km < 50.0:  # Within 50km
            actual_olt = actual_olts[nearest_actual_id]
            matches.append({
                "generated_olt_id": gen_olt_id,
                "actual_olt_id": nearest_actual_id,
                "distance_km": distance_km,
                "generated": gen_olt,
                "actual": actual_olt
            })
            unmatched_actual.discard(nearest_actual_id)
        else:
            unmatched_generated.append(gen_olt_id)
    
    print(f"Matched: {len(matches)} pairs")
    print(f"Unmatched generated: {len(unmatched_generated)}")
    print(f"Unmatched actual: {len(unmatched_actual)}")
    print()
    
    # Analyze matches
    print("=" * 80)
    print("PLACEMENT ANALYSIS")
    print("=" * 80)
    print()
    
    print(f"{'Generated OLT':<30} {'Actual OLT':<15} {'Distance':<12} {'Gen Method':<20} {'Gen→Cable':<12} {'Actual→Cable':<12} {'Gen→Centroid':<15} {'Actual→Centroid':<15}")
    print("-" * 150)
    
    distances = []
    placement_methods = defaultdict(int)
    
    for match in matches:
        gen = match["generated"]
        actual = match["actual"]
        distance = match["distance_km"]
        distances.append(distance)
        
        placement_methods[gen["placement_method"]] += 1
        
        # Calculate distance from actual OLT to nearest infrastructure
        gen_cable_dist = gen.get("distance_to_cable_km", 0)
        actual_cable, actual_cable_dist, _ = find_nearest_infrastructure_cable_to_olt(
            actual["position"], fiber_cable_geojson
        )
        actual_cable_fiber_count = actual_cable.get("fiber_count") if actual_cable else None
        
        # Calculate distances to ONT centroid
        actual_ont_centroid = calculate_ont_centroid_for_olt(
            actual['olt_id'], olt_ont_map, ont_positions
        )
        gen_to_centroid = "N/A"
        actual_to_centroid = "N/A"
        
        if actual_ont_centroid:
            gen_to_centroid = euclidean_distance(
                gen['position'][0], gen['position'][1],
                actual_ont_centroid[0], actual_ont_centroid[1]
            ) / 1000.0
            
            actual_to_centroid = euclidean_distance(
                actual['position'][0], actual['position'][1],
                actual_ont_centroid[0], actual_ont_centroid[1]
            ) / 1000.0
        
        print(f"{gen['olt_id']:<30} {actual['olt_id']:<15} {distance:<12.2f} "
              f"{gen['placement_method']:<20} {gen_cable_dist:<12.2f} {actual_cable_dist:<12.2f} "
              f"{gen_to_centroid:<15.2f} {actual_to_centroid:<15.2f}")
    
    print()
    print(f"Distance statistics:")
    import statistics
    if distances:
        print(f"  Mean: {statistics.mean(distances):.2f} km")
        print(f"  Median: {statistics.median(distances):.2f} km")
        print(f"  Min: {min(distances):.2f} km")
        print(f"  Max: {max(distances):.2f} km")
    
    print()
    print(f"Placement method distribution:")
    for method, count in placement_methods.items():
        print(f"  {method}: {count}")
    
    # Detailed analysis for each match
    print()
    print("=" * 80)
    print("DETAILED ANALYSIS")
    print("=" * 80)
    print()
    
    for match in matches[:5]:  # Show first 5
        gen = match["generated"]
        actual = match["actual"]
        distance = match["distance_km"]
        
        print(f"Match: {gen['olt_id']} ↔ {actual['olt_id']} (distance: {distance:.2f} km)")
        print(f"  Generated position: {gen['position']}")
        print(f"  Actual position: {actual['position']}")
        print(f"  Generated method: {gen['placement_method']}")
        print(f"  Generated ONT count: {gen.get('ont_count', 0)}")
        print(f"  Actual subscribers: {actual.get('subscribers', 'N/A')}")
        
        # Calculate centroid of ONTs assigned to actual OLT
        actual_ont_centroid = calculate_ont_centroid_for_olt(
            actual['olt_id'], olt_ont_map, ont_positions
        )
        
        if actual_ont_centroid:
            dist_to_centroid = euclidean_distance(
                actual['position'][0], actual['position'][1],
                actual_ont_centroid[0], actual_ont_centroid[1]
            ) / 1000.0
            
            dist_gen_to_centroid = euclidean_distance(
                gen['position'][0], gen['position'][1],
                actual_ont_centroid[0], actual_ont_centroid[1]
            ) / 1000.0
            
            print(f"  ONT centroid: {actual_ont_centroid}")
            print(f"  Actual OLT → centroid: {dist_to_centroid:.2f} km")
            print(f"  Generated OLT → centroid: {dist_gen_to_centroid:.2f} km")
        
        if gen.get("nearest_cable_id"):
            print(f"  Generated nearest cable: {gen['nearest_cable_id']} ({gen.get('nearest_cable_fiber_count', 0)}F)")
            print(f"  Generated distance to cable: {gen.get('distance_to_cable_km', 0):.2f} km")
        
        print()
    
    # Save detailed comparison
    comparison_data = {
        "matches": [
            {
                "generated_olt_id": m["generated_olt_id"],
                "actual_olt_id": m["actual_olt_id"],
                "distance_km": m["distance_km"],
                "generated_position": m["generated"]["position"],
                "actual_position": m["actual"]["position"],
                "generated_method": m["generated"]["placement_method"],
                "generated_ont_count": m["generated"].get("ont_count", 0),
                "generated_cable_distance_km": m["generated"].get("distance_to_cable_km", 0)
            }
            for m in matches
        ],
        "unmatched_generated": unmatched_generated,
        "unmatched_actual": list(unmatched_actual),
        "statistics": {
            "total_matches": len(matches),
            "mean_distance_km": statistics.mean(distances) if distances else 0,
            "median_distance_km": statistics.median(distances) if distances else 0,
            "min_distance_km": min(distances) if distances else 0,
            "max_distance_km": max(distances) if distances else 0
        }
    }
    
    output_path = "olt_placement_comparison.json"
    with open(output_path, "w") as f:
        json.dump(comparison_data, f, indent=2)
    
    print(f"✓ Saved detailed comparison to {output_path}")
    
    return comparison_data

if __name__ == "__main__":
    analyze_placement_differences()

