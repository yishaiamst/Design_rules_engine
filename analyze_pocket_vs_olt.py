#!/usr/bin/env python3
"""
analyze_pocket_vs_olt.py
-------------------------------------------------------------------------------
Compare community pockets with actual OLT positions to understand:
1. Are pocket centroids similar to OLT positions?
2. What happens with different diameter limits?
3. Why are pockets so large (97km)?
-------------------------------------------------------------------------------
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, List, Any, Tuple
from utils.geojson_utils import load_geojson, extract_points
from utils.spatial_utils import euclidean_distance, calculate_centroid, calculate_diameter
from phases.phase0_community_pockets import create_community_pockets, merge_pockets
from utils.config_loader import load_config

def load_olts() -> List[Tuple[float, float, Dict[str, Any]]]:
    """Load OLT positions."""
    olt_geojson = load_geojson("OLT.geojson")
    olt_points = []
    
    for feature in olt_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                olt_points.append((coords[0], coords[1], props))
        elif geometry.get("type") == "MultiPoint":
            for coords in geometry.get("coordinates", []):
                if len(coords) >= 2:
                    olt_points.append((coords[0], coords[1], props))
    
    return olt_points

def compare_pockets_to_olts(pockets: List[Dict[str, Any]], 
                            olt_points: List[Tuple[float, float, Dict[str, Any]]],
                            diameter_limit: float = 15.0) -> Dict[str, Any]:
    """Compare pocket centroids to OLT positions."""
    print(f"\n{'='*80}")
    print(f"COMPARING POCKETS TO OLTs (Diameter Limit: {diameter_limit}km)")
    print(f"{'='*80}\n")
    
    # Filter pockets by diameter if needed
    if diameter_limit:
        filtered_pockets = [p for p in pockets if p.get("diameter_km", 0) <= diameter_limit]
        print(f"Pockets within {diameter_limit}km diameter: {len(filtered_pockets)}")
    else:
        filtered_pockets = pockets
        print(f"All pockets: {len(filtered_pockets)}")
    
    print(f"OLTs in design: {len(olt_points)}\n")
    
    # Match pockets to nearest OLT
    matches = []
    unmatched_pockets = []
    unmatched_olts = list(range(len(olt_points)))
    
    for pocket in filtered_pockets:
        pocket_centroid = pocket["centroid"]
        min_distance = float('inf')
        nearest_olt_idx = None
        
        for i, (olt_x, olt_y, olt_props) in enumerate(olt_points):
            distance = euclidean_distance(
                pocket_centroid[0], pocket_centroid[1],
                olt_x, olt_y
            ) / 1000  # Convert to km
        
            if distance < min_distance:
                min_distance = distance
                nearest_olt_idx = i
        
        if nearest_olt_idx is not None:
            olt_x, olt_y, olt_props = olt_points[nearest_olt_idx]
            matches.append({
                "pocket_id": pocket["pocket_id"],
                "pocket_centroid": pocket_centroid,
                "pocket_ont_count": pocket["ont_count"],
                "pocket_diameter_km": pocket.get("diameter_km", 0),
                "olt_id": olt_props.get("ID") or olt_props.get("id"),
                "olt_position": (olt_x, olt_y),
                "distance_km": min_distance
            })
            
            if nearest_olt_idx in unmatched_olts:
                unmatched_olts.remove(nearest_olt_idx)
        else:
            unmatched_pockets.append(pocket)
    
    # Print matches
    print("Pocket to OLT Matches:")
    print(f"{'Pocket ID':<30} {'ONT Count':<12} {'Diameter':<12} {'OLT ID':<10} {'Distance':<12}")
    print("-" * 80)
    
    for match in sorted(matches, key=lambda x: x["distance_km"]):
        print(f"{match['pocket_id']:<30} {match['pocket_ont_count']:<12} "
              f"{match['pocket_diameter_km']:.2f}km{'':<7} {match['olt_id']:<10} "
              f"{match['distance_km']:.2f}km")
    
    print(f"\nMatched: {len(matches)} pockets")
    print(f"Unmatched pockets: {len(unmatched_pockets)}")
    print(f"Unmatched OLTs: {len(unmatched_olts)}")
    
    if unmatched_olts:
        print(f"\nUnmatched OLT IDs:")
        for idx in unmatched_olts:
            olt_id = olt_points[idx][2].get("ID") or olt_points[idx][2].get("id")
            print(f"  {olt_id}")
    
    # Statistics
    if matches:
        distances = [m["distance_km"] for m in matches]
        import statistics
        print(f"\nDistance Statistics:")
        print(f"  Mean distance: {statistics.mean(distances):.2f} km")
        print(f"  Median distance: {statistics.median(distances):.2f} km")
        print(f"  Max distance: {max(distances):.2f} km")
        print(f"  Min distance: {min(distances):.2f} km")
    
    return {
        "matches": matches,
        "unmatched_pockets": unmatched_pockets,
        "unmatched_olts": unmatched_olts,
        "pocket_count": len(filtered_pockets),
        "olt_count": len(olt_points)
    }

def test_diameter_limits(pockets: List[Dict[str, Any]], 
                        diameter_limits: List[float]) -> Dict[float, int]:
    """Test how many pockets remain with different diameter limits."""
    print(f"\n{'='*80}")
    print("TESTING DIFFERENT DIAMETER LIMITS")
    print(f"{'='*80}\n")
    
    results = {}
    
    for limit in diameter_limits:
        valid_pockets = [p for p in pockets if p.get("diameter_km", 0) <= limit]
        oversized = [p for p in pockets if p.get("diameter_km", 0) > limit]
        
        results[limit] = {
            "valid_count": len(valid_pockets),
            "oversized_count": len(oversized),
            "oversized_details": [
                {
                    "pocket_id": p["pocket_id"],
                    "ont_count": p["ont_count"],
                    "diameter_km": p.get("diameter_km", 0)
                }
                for p in oversized
            ]
        }
        
        print(f"Diameter Limit: {limit}km")
        print(f"  Valid pockets: {len(valid_pockets)}")
        print(f"  Oversized pockets: {len(oversized)}")
        if oversized:
            print(f"  Oversized details:")
            for p in oversized[:5]:  # Show first 5
                print(f"    {p['pocket_id']}: {p['ont_count']} ONTs, {p.get('diameter_km', 0):.2f}km")
            if len(oversized) > 5:
                print(f"    ... and {len(oversized) - 5} more")
        print()
    
    return results

def analyze_large_pocket(pocket: Dict[str, Any], olt_points: List[Tuple[float, float, Dict[str, Any]]]):
    """Analyze why a pocket is so large."""
    print(f"\n{'='*80}")
    print(f"ANALYZING LARGE POCKET: {pocket['pocket_id']}")
    print(f"{'='*80}\n")
    
    print(f"ONT Count: {pocket['ont_count']}")
    print(f"Diameter: {pocket.get('diameter_km', 0):.2f} km")
    print(f"Centroid: {pocket['centroid']}")
    
    # Find nearest OLT
    min_distance = float('inf')
    nearest_olt = None
    
    for olt_x, olt_y, olt_props in olt_points:
        distance = euclidean_distance(
            pocket["centroid"][0], pocket["centroid"][1],
            olt_x, olt_y
        ) / 1000
        
        if distance < min_distance:
            min_distance = distance
            nearest_olt = (olt_x, olt_y, olt_props, distance)
    
    if nearest_olt:
        olt_x, olt_y, olt_props, distance = nearest_olt
        print(f"\nNearest OLT:")
        print(f"  OLT ID: {olt_props.get('ID') or olt_props.get('id')}")
        print(f"  OLT Position: ({olt_x:.2f}, {olt_y:.2f})")
        print(f"  Distance from pocket centroid: {distance:.2f} km")
        print(f"  OLT Name: {olt_props.get('Name', 'N/A')}")
        print(f"  OLT Subscribers: {olt_props.get('NoOfAddr', 'N/A')}")
    
    # Check if any ONTs in pocket are far from centroid
    ont_points = pocket.get("ont_points", [])
    if ont_points:
        distances_from_centroid = []
        for ont_x, ont_y, ont_props in ont_points:
            dist = euclidean_distance(
                pocket["centroid"][0], pocket["centroid"][1],
                ont_x, ont_y
            ) / 1000
            distances_from_centroid.append(dist)
        
        import statistics
        print(f"\nONT Distance from Centroid:")
        print(f"  Mean: {statistics.mean(distances_from_centroid):.2f} km")
        print(f"  Median: {statistics.median(distances_from_centroid):.2f} km")
        print(f"  Max: {max(distances_from_centroid):.2f} km")
        print(f"  Min: {min(distances_from_centroid):.2f} km")
        
        # Check how many ONTs are >20km from centroid
        far_onts = [d for d in distances_from_centroid if d > 20]
        print(f"  ONTs >20km from centroid: {len(far_onts)} ({len(far_onts)/len(distances_from_centroid)*100:.1f}%)")

def main():
    """Main analysis."""
    print("=" * 80)
    print("POCKET vs OLT ANALYSIS")
    print("=" * 80)
    
    # Load data
    print("\nLoading data...")
    config = load_config()
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    olt_points = load_olts()
    
    print(f"  Loaded {len(extract_points(ont_geojson))} ONTs")
    print(f"  Loaded {len(olt_points)} OLTs")
    
    # Create pockets (without splitting)
    print("\nCreating pockets (without diameter splitting)...")
    from phases.phase0_community_pockets import create_community_pockets
    
    # Temporarily disable splitting by setting very high diameter limit
    original_config = config.copy()
    config["placement"]["olt"]["pocket_max_diameter_km"] = 999.0  # Disable splitting
    
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    
    # Restore config
    config = original_config
    
    print(f"\nCreated {len(pockets)} pockets (after merging, before splitting)")
    
    # 1. Compare pockets to OLTs
    comparison_15km = compare_pockets_to_olts(pockets, olt_points, diameter_limit=15.0)
    comparison_20km = compare_pockets_to_olts(pockets, olt_points, diameter_limit=20.0)
    comparison_22km = compare_pockets_to_olts(pockets, olt_points, diameter_limit=22.0)
    comparison_none = compare_pockets_to_olts(pockets, olt_points, diameter_limit=None)
    
    # 2. Test different diameter limits
    print("\n" + "=" * 80)
    diameter_results = test_diameter_limits(pockets, [15.0, 20.0, 22.0, 25.0, 30.0, 50.0, 100.0, 999.0])
    
    # 3. Analyze largest pocket
    largest_pocket = max(pockets, key=lambda p: p.get("diameter_km", 0))
    analyze_large_pocket(largest_pocket, olt_points)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal pockets (after merging): {len(pockets)}")
    print(f"Total OLTs: {len(olt_points)}")
    print(f"\nPockets matching OLT count: {len(pockets) == len(olt_points)}")
    print(f"\nDiameter limit results:")
    for limit, result in sorted(diameter_results.items()):
        print(f"  {limit}km: {result['valid_count']} valid, {result['oversized_count']} oversized")

if __name__ == "__main__":
    main()


