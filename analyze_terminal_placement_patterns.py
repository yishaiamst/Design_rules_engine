#!/usr/bin/env python3
"""
Analyze terminal placement patterns from actual design to learn statistics.
"""

import json
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance, point_to_line_distance

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

def analyze_terminal_placement():
    """Analyze terminal placement patterns from actual design."""
    print("=" * 80)
    print("TERMINAL PLACEMENT PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    # Load terminals
    print("Loading terminals...")
    terminals = load_geojson("terminal.geojson")
    terminal_features = terminals.get("features", [])
    print(f"  Loaded {len(terminal_features)} terminals")
    
    # Load infrastructure cables
    print("Loading infrastructure cables...")
    cables = load_geojson("fiber cable.geojson")
    cable_features = cables.get("features", [])
    print(f"  Loaded {len(cable_features)} infrastructure cables")
    
    # Load FOSCs
    print("Loading FOSCs...")
    foscs = load_geojson("splice closure.geojson")
    fosc_features = foscs.get("features", [])
    print(f"  Loaded {len(fosc_features)} FOSCs")
    
    # Load drop cables to count ONTs per terminal
    print("Loading drop cables...")
    drop_cables = load_geojson("drop cable.geojson")
    drop_features = drop_cables.get("features", [])
    print(f"  Loaded {len(drop_features)} drop cables")
    
    # Build terminal position map
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
                "ont_count": 0  # Will be calculated from drop cables
            }
    
    # Count ONTs per terminal (from drop cables)
    print("\nCounting ONTs per terminal from drop cables...")
    terminal_ont_counts = defaultdict(int)
    for feat in drop_features:
        props = feat.get("properties", {})
        # Try to extract terminal ID from drop cable
        # Drop cables typically connect to terminals
        # We'll match by proximity later if needed
        pass
    
    # Build cable data structure
    cables_data = []
    for feat in cable_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        # Extract size
        size = extract_fiber_count(props.get("Size") or props.get("FiberCount") or cable_id)
        
        coords = []
        geom_type = geometry.get("type", "")
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if coords and len(coords) >= 2:
            cables_data.append({
                "id": cable_id,
                "size": size,
                "coordinates": coords
            })
    
    # Build FOSC position map
    foscs_data = {}
    for feat in fosc_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        fosc_id = props.get("ID") or props.get("id", "")
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            foscs_data[fosc_id] = {
                "id": fosc_id,
                "position": (coords[0], coords[1])
            }
    
    # Analyze terminal placement
    print("\nAnalyzing terminal placement...")
    aerial_stats = {
        "count": 0,
        "distances_to_cable": [],
        "distances_to_fosc": [],
        "ont_counts": [],
        "cable_sizes": Counter()
    }
    
    mst_stats = {
        "count": 0,
        "distances_to_cable": [],
        "distances_to_fosc": [],
        "ont_counts": [],
        "cable_sizes": Counter()
    }
    
    for terminal_id, terminal in terminals_data.items():
        term_pos = terminal["position"]
        term_type = terminal["type"]
        
        # Find nearest infrastructure cable
        min_cable_dist = float('inf')
        nearest_cable = None
        for cable in cables_data:
            coords = cable["coordinates"]
            for i in range(len(coords) - 1):
                dist = point_to_line_distance(term_pos, coords[i], coords[i+1])
                if dist < min_cable_dist:
                    min_cable_dist = dist
                    nearest_cable = cable
        
        # Find nearest FOSC
        min_fosc_dist = float('inf')
        nearest_fosc = None
        for fosc_id, fosc in foscs_data.items():
            dist = euclidean_distance(term_pos[0], term_pos[1], fosc["position"][0], fosc["position"][1])
            if dist < min_fosc_dist:
                min_fosc_dist = dist
                nearest_fosc = fosc
        
        # Update statistics
        if term_type == "Aerial Terminal":
            aerial_stats["count"] += 1
            aerial_stats["distances_to_cable"].append(min_cable_dist)
            aerial_stats["distances_to_fosc"].append(min_fosc_dist)
            if nearest_cable:
                aerial_stats["cable_sizes"][nearest_cable.get("size", 0)] += 1
        elif term_type == "MST":
            mst_stats["count"] += 1
            mst_stats["distances_to_cable"].append(min_cable_dist)
            mst_stats["distances_to_fosc"].append(min_fosc_dist)
            if nearest_cable:
                mst_stats["cable_sizes"][nearest_cable.get("size", 0)] += 1
    
    # Calculate statistics
    def calc_stats(values):
        if not values:
            return {}
        sorted_vals = sorted(values)
        return {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "median": sorted_vals[len(sorted_vals) // 2],
            "p25": sorted_vals[len(sorted_vals) // 4],
            "p75": sorted_vals[3 * len(sorted_vals) // 4]
        }
    
    print("\n" + "=" * 80)
    print("AERIAL TERMINAL STATISTICS")
    print("=" * 80)
    print(f"Count: {aerial_stats['count']}")
    print(f"\nDistance to Infrastructure Cable:")
    cable_dist_stats = calc_stats(aerial_stats["distances_to_cable"])
    for key, val in cable_dist_stats.items():
        print(f"  {key}: {val:.2f}m")
    print(f"\nDistance to Nearest FOSC:")
    fosc_dist_stats = calc_stats(aerial_stats["distances_to_fosc"])
    for key, val in fosc_dist_stats.items():
        print(f"  {key}: {val:.2f}m")
    print(f"\nInfrastructure Cable Sizes:")
    for size in sorted(aerial_stats["cable_sizes"].keys()):
        print(f"  {size}F: {aerial_stats['cable_sizes'][size]} terminals")
    
    print("\n" + "=" * 80)
    print("MST STATISTICS")
    print("=" * 80)
    print(f"Count: {mst_stats['count']}")
    print(f"\nDistance to Infrastructure Cable:")
    cable_dist_stats = calc_stats(mst_stats["distances_to_cable"])
    for key, val in cable_dist_stats.items():
        print(f"  {key}: {val:.2f}m")
    print(f"\nDistance to Nearest FOSC:")
    fosc_dist_stats = calc_stats(mst_stats["distances_to_fosc"])
    for key, val in fosc_dist_stats.items():
        print(f"  {key}: {val:.2f}m")
    print(f"\nInfrastructure Cable Sizes:")
    for size in sorted(mst_stats["cable_sizes"].keys()):
        print(f"  {size}F: {mst_stats['cable_sizes'][size]} terminals")
    
    # Save results
    results = {
        "aerial_terminal": {
            "count": aerial_stats["count"],
            "distance_to_cable": calc_stats(aerial_stats["distances_to_cable"]),
            "distance_to_fosc": calc_stats(aerial_stats["distances_to_fosc"]),
            "cable_sizes": dict(aerial_stats["cable_sizes"])
        },
        "mst": {
            "count": mst_stats["count"],
            "distance_to_cable": calc_stats(mst_stats["distances_to_cable"]),
            "distance_to_fosc": calc_stats(mst_stats["distances_to_fosc"]),
            "cable_sizes": dict(mst_stats["cable_sizes"])
        }
    }
    
    with open("terminal_placement_statistics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 80)
    print("RESULTS SAVED")
    print("=" * 80)
    print("  ✓ Saved terminal_placement_statistics.json")
    print()
    
    return results

if __name__ == "__main__":
    analyze_terminal_placement()

