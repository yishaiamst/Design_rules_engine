#!/usr/bin/env python3
"""
Analyze what factors determine Aerial vs MST in actual design.
"""

import json
from collections import Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import point_to_line_distance, euclidean_distance

def analyze_decision_factors():
    """Analyze what distinguishes Aerial from MST in actual design."""
    print("=" * 80)
    print("TERMINAL DECISION FACTOR ANALYSIS")
    print("=" * 80)
    print()
    
    # Load terminals
    terminals = load_geojson("terminal.geojson")
    terminal_features = terminals.get("features", [])
    
    # Load cables
    cables = load_geojson("fiber cable.geojson")
    cable_features = cables.get("features", [])
    
    # Load FOSCs
    foscs = load_geojson("splice closure.geojson")
    fosc_features = foscs.get("features", [])
    
    # Load drop cables
    drop_cables = load_geojson("drop cable.geojson")
    drop_features = drop_cables.get("features", [])
    
    # Build data structures
    terminals_data = {}
    for feat in terminal_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        terminal_id = props.get("ID") or props.get("id", "")
        terminal_type = props.get("Type") or props.get("type", "")
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            terminals_data[terminal_id] = {
                "id": terminal_id,
                "type": terminal_type,
                "position": (coords[0], coords[1]),
                "ont_count": 0
            }
    
    # Count ONTs per terminal
    for feat in drop_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            # Handle nested coordinates
            end = coords[-1]
            while isinstance(end, list) and len(end) > 0 and isinstance(end[0], list):
                end = end[-1]
            if isinstance(end, list) and len(end) >= 2:
                end_x, end_y = float(end[0]), float(end[1])
                for term_id, term in terminals_data.items():
                    term_pos = term["position"]
                    if isinstance(term_pos, (list, tuple)) and len(term_pos) >= 2:
                        term_x, term_y = term_pos[0], term_pos[1]
                        if euclidean_distance(end_x, end_y, term_x, term_y) < 50:
                            terminals_data[term_id]["ont_count"] += 1
                            break
    
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
    
    # Build FOSC data
    foscs_data = []
    for feat in fosc_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            foscs_data.append({"position": (coords[0], coords[1])})
    
    # Analyze distances
    print("Analyzing terminal distances...")
    aerial_data = []
    mst_data = []
    
    for term_id, term in terminals_data.items():
        term_pos = term["position"]
        if not isinstance(term_pos, (list, tuple)) or len(term_pos) < 2:
            continue
        
        term_x, term_y = term_pos[0], term_pos[1]
        
        # Distance to cable
        min_cable_dist = float('inf')
        for cable in cables_data:
            cable_coords = cable["coordinates"]
            for i in range(min(100, len(cable_coords) - 1)):  # Limit for performance
                p1 = cable_coords[i]
                p2 = cable_coords[i + 1]
                if isinstance(p1, list) and len(p1) >= 2 and isinstance(p2, list) and len(p2) >= 2:
                    dist = point_to_line_distance(term_pos, p1, p2)
                    if dist < min_cable_dist:
                        min_cable_dist = dist
        
        # Distance to FOSC
        min_fosc_dist = float('inf')
        for fosc in foscs_data:
            fosc_pos = fosc["position"]
            if isinstance(fosc_pos, (list, tuple)) and len(fosc_pos) >= 2:
                dist = euclidean_distance(term_x, term_y, fosc_pos[0], fosc_pos[1])
                if dist < min_fosc_dist:
                    min_fosc_dist = dist
        
        data_point = {
            "distance_to_cable": min_cable_dist,
            "distance_to_fosc": min_fosc_dist,
            "ont_count": term["ont_count"]
        }
        
        if term["type"] == "Aerial Terminal":
            aerial_data.append(data_point)
        elif term["type"] == "MST":
            mst_data.append(data_point)
    
    # Analyze by distance ranges
    print("\n" + "=" * 80)
    print("DISTRIBUTION BY DISTANCE RANGES")
    print("=" * 80)
    
    ranges = [
        (0, 1, "0-1m"),
        (1, 5, "1-5m"),
        (5, 10, "5-10m"),
        (10, 25, "10-25m"),
        (25, 50, "25-50m"),
        (50, 100, "50-100m"),
        (100, 200, "100-200m"),
        (200, float('inf'), "200m+")
    ]
    
    print(f"\n{'Range':<12} {'Aerial':<10} {'MST':<10} {'Aerial %':<12} {'MST %':<12}")
    print("-" * 60)
    
    for min_dist, max_dist, label in ranges:
        aerial_in_range = sum(1 for d in aerial_data if min_dist <= d["distance_to_cable"] < max_dist)
        mst_in_range = sum(1 for d in mst_data if min_dist <= d["distance_to_cable"] < max_dist)
        total_in_range = aerial_in_range + mst_in_range
        
        aerial_pct = (aerial_in_range / len(aerial_data) * 100) if aerial_data else 0
        mst_pct = (mst_in_range / len(mst_data) * 100) if mst_data else 0
        
        print(f"{label:<12} {aerial_in_range:<10} {mst_in_range:<10} {aerial_pct:>10.1f}% {mst_pct:>10.1f}%")
    
    # Find optimal threshold using probability
    print("\n" + "=" * 80)
    print("OPTIMAL THRESHOLD (PROBABILITY-BASED)")
    print("=" * 80)
    
    # Calculate probability of being Aerial given distance
    print(f"\n{'Threshold':<12} {'Aerial <Thresh':<15} {'MST <Thresh':<15} {'Aerial Prob':<15} {'Expected Aerial':<15}")
    print("-" * 75)
    
    best_threshold = 10
    best_match = float('inf')
    target_aerial = 3775
    
    for threshold in [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100]:
        aerial_below = sum(1 for d in aerial_data if d["distance_to_cable"] < threshold)
        mst_below = sum(1 for d in mst_data if d["distance_to_cable"] < threshold)
        total_below = aerial_below + mst_below
        
        if total_below > 0:
            aerial_prob = aerial_below / total_below
            # Estimate how many would be classified as Aerial with this threshold
            # We'd classify all terminals < threshold as Aerial with probability = aerial_prob
            # But we need to know total terminals to estimate
            # For now, just show the probability
            print(f"{threshold:<12} {aerial_below:<15} {mst_below:<15} {aerial_prob:>14.2%}")
            
            # Calculate expected Aerial count if we use this threshold
            # This is approximate - we'd need to know total terminals
            if abs(aerial_below - target_aerial) < best_match:
                best_match = abs(aerial_below - target_aerial)
                best_threshold = threshold
    
    print(f"\nBest threshold for matching Aerial count: {best_threshold}m")
    
    # Analyze by ONT count
    print("\n" + "=" * 80)
    print("DISTRIBUTION BY ONT COUNT")
    print("=" * 80)
    
    ont_ranges = [(1, 1), (2, 3), (4, 6), (7, 12), (13, float('inf'))]
    print(f"\n{'ONT Range':<12} {'Aerial':<10} {'MST':<10} {'Aerial %':<12} {'MST %':<12}")
    print("-" * 60)
    
    for min_ont, max_ont in ont_ranges:
        label = f"{min_ont}-{int(max_ont) if max_ont != float('inf') else '∞'}"
        aerial_in_range = sum(1 for d in aerial_data if min_ont <= d["ont_count"] <= max_ont)
        mst_in_range = sum(1 for d in mst_data if min_ont <= d["ont_count"] <= max_ont)
        
        aerial_pct = (aerial_in_range / len(aerial_data) * 100) if aerial_data else 0
        mst_pct = (mst_in_range / len(mst_data) * 100) if mst_data else 0
        
        print(f"{label:<12} {aerial_in_range:<10} {mst_in_range:<10} {aerial_pct:>10.1f}% {mst_pct:>10.1f}%")
    
    # Analyze by FOSC distance for terminals <1m from cable
    print("\n" + "=" * 80)
    print("FOSC DISTANCE ANALYSIS (for terminals <1m from cable)")
    print("=" * 80)
    
    aerial_close = [d for d in aerial_data if d["distance_to_cable"] < 1.0]
    mst_close = [d for d in mst_data if d["distance_to_cable"] < 1.0]
    
    print(f"\nAerial terminals <1m from cable: {len(aerial_close)}")
    print(f"MST terminals <1m from cable: {len(mst_close)}")
    
    if aerial_close and mst_close:
        aerial_fosc_distances = [d["distance_to_fosc"] for d in aerial_close]
        mst_fosc_distances = [d["distance_to_fosc"] for d in mst_close]
        
        print(f"\nFOSC distance stats for terminals <1m from cable:")
        print(f"  Aerial - Mean: {sum(aerial_fosc_distances)/len(aerial_fosc_distances):.1f}m, Median: {sorted(aerial_fosc_distances)[len(aerial_fosc_distances)//2]:.1f}m")
        print(f"  MST - Mean: {sum(mst_fosc_distances)/len(mst_fosc_distances):.1f}m, Median: {sorted(mst_fosc_distances)[len(mst_fosc_distances)//2]:.1f}m")
        
        # Check if FOSC distance can distinguish them
        fosc_thresholds = [100, 200, 300, 400, 500, 1000]
        print(f"\n{'FOSC Threshold':<15} {'Aerial <Thresh':<15} {'MST <Thresh':<15} {'Aerial Prob':<15}")
        print("-" * 65)
        
        for threshold in fosc_thresholds:
            aerial_below = sum(1 for d in aerial_close if d["distance_to_fosc"] < threshold)
            mst_below = sum(1 for d in mst_close if d["distance_to_fosc"] < threshold)
            total_below = aerial_below + mst_below
            
            if total_below > 0:
                aerial_prob = aerial_below / total_below
                print(f"{threshold:<15} {aerial_below:<15} {mst_below:<15} {aerial_prob:>14.2%}")
    
    return {
        "best_threshold": best_threshold,
        "aerial_data": len(aerial_data),
        "mst_data": len(mst_data)
    }

if __name__ == "__main__":
    analyze_decision_factors()

