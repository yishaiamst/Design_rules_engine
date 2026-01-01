#!/usr/bin/env python3
"""
Analyze distance distribution to find the optimal threshold for Aerial vs MST.
"""

import json
from collections import Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import point_to_line_distance, euclidean_distance

def analyze_distance_distribution():
    """Analyze distance to cable distribution for Aerial vs MST."""
    print("=" * 80)
    print("TERMINAL DISTANCE DISTRIBUTION ANALYSIS")
    print("=" * 80)
    print()
    
    # Load terminals
    terminals = load_geojson("terminal.geojson")
    terminal_features = terminals.get("features", [])
    
    # Load cables
    cables = load_geojson("fiber cable.geojson")
    cable_features = cables.get("features", [])
    
    # Build cable data
    cables_data = []
    for feat in cable_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        coords = []
        geom_type = geometry.get("type", "")
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        if coords and len(coords) >= 2:
            cables_data.append({"coordinates": coords})
    
    # Analyze distances
    aerial_distances = []
    mst_distances = []
    
    for feat in terminal_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        terminal_type = props.get("Type") or props.get("type", "")
        
        coords = geometry.get("coordinates", [])
        if not coords or len(coords) < 2:
            continue
        
        term_pos = (coords[0], coords[1])
        
        # Find nearest cable
        min_dist = float('inf')
        for cable in cables_data:
            cable_coords = cable["coordinates"]
            for i in range(len(cable_coords) - 1):
                dist = point_to_line_distance(term_pos, cable_coords[i], cable_coords[i + 1])
                if dist < min_dist:
                    min_dist = dist
        
        if terminal_type == "Aerial Terminal":
            aerial_distances.append(min_dist)
        elif terminal_type == "MST":
            mst_distances.append(min_dist)
    
    # Analyze distributions
    print("AERIAL TERMINAL DISTANCES:")
    if aerial_distances:
        sorted_aerial = sorted(aerial_distances)
        print(f"  Count: {len(aerial_distances)}")
        print(f"  Min: {min(aerial_distances):.2f}m")
        print(f"  Max: {max(aerial_distances):.2f}m")
        print(f"  Mean: {sum(aerial_distances)/len(aerial_distances):.2f}m")
        print(f"  Median: {sorted_aerial[len(sorted_aerial)//2]:.2f}m")
        print(f"  P75: {sorted_aerial[3*len(sorted_aerial)//4]:.2f}m")
        print(f"  P90: {sorted_aerial[9*len(sorted_aerial)//10]:.2f}m")
        print(f"  P95: {sorted_aerial[19*len(sorted_aerial)//20]:.2f}m")
    
    print("\nMST DISTANCES:")
    if mst_distances:
        sorted_mst = sorted(mst_distances)
        print(f"  Count: {len(mst_distances)}")
        print(f"  Min: {min(mst_distances):.2f}m")
        print(f"  Max: {max(mst_distances):.2f}m")
        print(f"  Mean: {sum(mst_distances)/len(mst_distances):.2f}m")
        print(f"  Median: {sorted_mst[len(sorted_mst)//2]:.2f}m")
        print(f"  P25: {sorted_mst[len(sorted_mst)//4]:.2f}m")
        print(f"  P10: {sorted_mst[len(sorted_mst)//10]:.2f}m")
        print(f"  P5: {sorted_mst[len(sorted_mst)//20]:.2f}m")
    
    # Find optimal threshold (where distributions overlap least)
    print("\n" + "=" * 80)
    print("OPTIMAL THRESHOLD ANALYSIS")
    print("=" * 80)
    
    # Test different thresholds
    thresholds = [10, 25, 50, 75, 100, 150, 200, 250, 300]
    print(f"\n{'Threshold':<12} {'Aerial <Thresh':<15} {'MST <Thresh':<15} {'Accuracy':<10}")
    print("-" * 60)
    
    best_threshold = 50
    best_accuracy = 0
    
    for threshold in thresholds:
        aerial_below = sum(1 for d in aerial_distances if d < threshold)
        mst_below = sum(1 for d in mst_distances if d < threshold)
        
        # Accuracy: how well threshold separates the two types
        # Aerial should be below threshold, MST should be above
        aerial_correct = aerial_below
        mst_correct = len(mst_distances) - mst_below
        total_correct = aerial_correct + mst_correct
        accuracy = total_correct / (len(aerial_distances) + len(mst_distances)) * 100
        
        print(f"{threshold:<12} {aerial_below:<15} {mst_below:<15} {accuracy:.1f}%")
        
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = threshold
    
    print(f"\nBest threshold: {best_threshold}m (accuracy: {best_accuracy:.1f}%)")
    
    return best_threshold

if __name__ == "__main__":
    analyze_distance_distribution()

