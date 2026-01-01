#!/usr/bin/env python3
"""
analyze_olt_cable_size_preference.py
-------------------------------------------------------------------------------
Analyze which cable sizes actual OLTs are placed on and their relationship
to ONT count. This will help understand if larger cables are preferred.
-------------------------------------------------------------------------------
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, List, Any, Tuple, Optional
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance
from collections import defaultdict

def extract_fiber_count(props: Dict[str, Any]) -> int:
    """Extract fiber count from cable properties."""
    if props.get("FiberCount"):
        try:
            return int(props.get("FiberCount"))
        except (ValueError, TypeError):
            pass
    
    size_str = props.get("Size", "")
    if size_str:
        import re
        match = re.search(r'(\d+)', str(size_str))
        if match:
            return int(match.group(1))
    
    id_str = props.get("ID", "")
    if id_str:
        import re
        match = re.search(r'(\d+)F', str(id_str))
        if match:
            return int(match.group(1))
    
    return 0

def find_main_infrastructure_cables(fiber_cable_geojson: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find main infrastructure cables (288F, 144F, 96F)."""
    main_cables = []
    
    for feature in fiber_cable_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        fiber_count = extract_fiber_count(props)
        
        if fiber_count >= 96:  # 288F, 144F, or 96F
            coords = []
            geom_type = geometry.get("type", "")
            
            if geom_type == "LineString":
                coords = geometry.get("coordinates", [])
            elif geom_type == "MultiLineString":
                for line in geometry.get("coordinates", []):
                    coords.extend(line)
            
            if len(coords) >= 2:
                coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
                if coord_tuples:
                    main_cables.append({
                        "id": props.get("ID", ""),
                        "fiber_count": fiber_count,
                        "coordinates": coord_tuples,
                        "properties": props
                    })
    
    return main_cables

def find_nearest_cables_with_size(
    point: Tuple[float, float],
    main_cables: List[Dict[str, Any]],
    max_distance_km: float = 1.0
) -> List[Tuple[Dict[str, Any], float, Tuple[float, float]]]:
    """
    Find all infrastructure cables within max_distance_km, sorted by distance.
    
    Returns list of (cable, distance_km, nearest_point) tuples.
    """
    from phases.phase1_place_olts import find_nearest_infrastructure_cable
    
    candidates = []
    
    for cable in main_cables:
        _, distance_m, nearest_point = find_nearest_infrastructure_cable(point, [cable])
        distance_km = distance_m / 1000.0
        
        if distance_km <= max_distance_km:
            candidates.append((cable, distance_km, nearest_point))
    
    # Sort by distance, then by fiber count (larger first)
    candidates.sort(key=lambda x: (x[1], -x[0]["fiber_count"]))
    
    return candidates

def analyze_olt_cable_preferences():
    """Analyze which cable sizes actual OLTs are placed on."""
    print("=" * 80)
    print("OLT CABLE SIZE PREFERENCE ANALYSIS")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    actual_olts = {}
    olt_geojson = load_geojson("OLT.geojson")
    for feature in olt_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        olt_id = str(props.get("ID") or props.get("id", ""))
        if not olt_id:
            continue
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if coords and len(coords) >= 2:
            actual_olts[olt_id] = {
                "olt_id": olt_id,
                "position": (coords[0], coords[1]),
                "name": props.get("Name", ""),
                "subscribers": props.get("NoOfAddr", "")
            }
    
    # Load OLT-ONT assignments
    with open("olt_ont_paths.json", "r") as f:
        paths = json.load(f)
    
    olt_ont_map = defaultdict(list)
    for path in paths:
        olt_id = str(path.get("olt_id", ""))
        ont_id = str(path.get("ont_id", ""))
        if olt_id and ont_id:
            olt_ont_map[olt_id].append(ont_id)
    
    # Load fiber cables
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    main_cables = find_main_infrastructure_cables(fiber_cable_geojson)
    
    print(f"  ✓ Loaded {len(actual_olts)} OLTs")
    print(f"  ✓ Loaded {len(main_cables)} main infrastructure cables")
    print()
    
    # Analyze each OLT
    print("=" * 80)
    print("OLT CABLE SIZE ANALYSIS")
    print("=" * 80)
    print()
    
    print(f"{'OLT ID':<10} {'ONT Count':<12} {'Nearest Cable':<30} {'Size':<8} {'Distance':<10} {'Other Cables Nearby':<30}")
    print("-" * 120)
    
    olt_cable_data = []
    
    for olt_id in sorted(actual_olts.keys()):
        olt = actual_olts[olt_id]
        ont_count = len(olt_ont_map.get(olt_id, []))
        
        # Find nearest cables (within 1km)
        nearby_cables = find_nearest_cables_with_size(
            olt["position"], main_cables, max_distance_km=1.0
        )
        
        if nearby_cables:
            nearest_cable, distance, _ = nearby_cables[0]
            nearest_size = nearest_cable["fiber_count"]
            nearest_id = nearest_cable["id"]
            
            # Get other nearby cables
            other_cables = []
            for cable, dist, _ in nearby_cables[1:5]:  # Show up to 4 more
                other_cables.append(f"{cable['fiber_count']}F({dist:.2f}km)")
            
            other_str = ", ".join(other_cables) if other_cables else "None"
            
            print(f"{olt_id:<10} {ont_count:<12} {nearest_id[:28]:<30} {nearest_size:<8} {distance:<10.3f} {other_str:<30}")
            
            olt_cable_data.append({
                "olt_id": olt_id,
                "ont_count": ont_count,
                "cable_size": nearest_size,
                "cable_id": nearest_id,
                "distance_km": distance,
                "other_cables": [{"size": c[0]["fiber_count"], "distance": c[1]} for c in nearby_cables[1:]]
            })
        else:
            print(f"{olt_id:<10} {ont_count:<12} {'No cable within 1km':<30}")
    
    # Analyze patterns
    print()
    print("=" * 80)
    print("CABLE SIZE PREFERENCE ANALYSIS")
    print("=" * 80)
    print()
    
    # Group by cable size
    size_distribution = defaultdict(list)
    for data in olt_cable_data:
        size_distribution[data["cable_size"]].append(data)
    
    print("Cable size distribution:")
    for size in sorted(size_distribution.keys(), reverse=True):
        olts = size_distribution[size]
        ont_counts = [o["ont_count"] for o in olts]
        import statistics
        print(f"  {size}F: {len(olts)} OLTs")
        print(f"    ONT count range: {min(ont_counts)} - {max(ont_counts)}")
        print(f"    Mean ONT count: {statistics.mean(ont_counts):.0f}")
        print(f"    Median ONT count: {statistics.median(ont_counts):.0f}")
    
    # Check if larger cables are preferred when multiple options exist
    print()
    print("Preference analysis (OLTs with multiple cable options):")
    multi_cable_olts = [d for d in olt_cable_data if len(d["other_cables"]) > 0]
    
    if multi_cable_olts:
        print(f"  {len(multi_cable_olts)} OLTs have multiple cable options nearby")
        
        chose_larger = 0
        chose_smaller = 0
        same_size = 0
        
        for olt_data in multi_cable_olts:
            chosen_size = olt_data["cable_size"]
            other_sizes = [c["size"] for c in olt_data["other_cables"]]
            
            if other_sizes:
                max_other = max(other_sizes)
                if chosen_size > max_other:
                    chose_larger += 1
                elif chosen_size < max_other:
                    chose_smaller += 1
                else:
                    same_size += 1
        
        print(f"  Chose larger cable: {chose_larger}")
        print(f"  Chose smaller cable: {chose_smaller}")
        print(f"  Same size (or only option): {same_size}")
    else:
        print("  No OLTs have multiple cable options within 1km")
    
    # Analyze relationship between ONT count and cable size
    print()
    print("=" * 80)
    print("ONT COUNT vs CABLE SIZE RELATIONSHIP")
    print("=" * 80)
    print()
    
    print(f"{'ONT Count Range':<20} {'288F':<8} {'144F':<8} {'96F':<8} {'Total':<8}")
    print("-" * 60)
    
    ranges = [
        (0, 500, "<500"),
        (500, 1000, "500-1000"),
        (1000, 1500, "1000-1500"),
        (1500, 2000, "1500-2000"),
        (2000, 10000, "≥2000")
    ]
    
    for min_ont, max_ont, label in ranges:
        olts_in_range = [d for d in olt_cable_data if min_ont <= d["ont_count"] < max_ont]
        if olts_in_range:
            count_288 = sum(1 for o in olts_in_range if o["cable_size"] == 288)
            count_144 = sum(1 for o in olts_in_range if o["cable_size"] == 144)
            count_96 = sum(1 for o in olts_in_range if o["cable_size"] == 96)
            total = len(olts_in_range)
            
            print(f"{label:<20} {count_288:<8} {count_144:<8} {count_96:<8} {total:<8}")
    
    # Save results
    output_data = {
        "olt_cable_assignments": olt_cable_data,
        "size_distribution": {
            size: {
                "count": len(olts),
                "ont_count_stats": {
                    "min": min(o["ont_count"] for o in olts),
                    "max": max(o["ont_count"] for o in olts),
                    "mean": statistics.mean([o["ont_count"] for o in olts]),
                    "median": statistics.median([o["ont_count"] for o in olts])
                }
            }
            for size, olts in size_distribution.items()
        },
        "preference_analysis": {
            "multi_cable_olts": len(multi_cable_olts),
            "chose_larger": chose_larger if multi_cable_olts else 0,
            "chose_smaller": chose_smaller if multi_cable_olts else 0
        }
    }
    
    output_path = "olt_cable_size_analysis.json"
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print()
    print(f"✓ Saved analysis to {output_path}")
    
    return output_data

if __name__ == "__main__":
    analyze_olt_cable_preferences()


