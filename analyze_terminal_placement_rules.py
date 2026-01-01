#!/usr/bin/env python3
"""
analyze_terminal_placement_rules.py
-------------------------------------------------------------------------------
Analyze terminal placement rules to verify and refine:
1. Aerial terminals placed on infrastructure cables (288/144/96/72/48)
2. MSTs connect to FOSCs
3. MSTs used for communities 200m+ away from infrastructure cable
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple
import math
import statistics
from collections import defaultdict

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def point_to_line_distance(point: Tuple[float, float], 
                          line_start: Tuple[float, float], 
                          line_end: Tuple[float, float]) -> float:
    """Calculate minimum distance from point to line segment (in meters)."""
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        return haversine_distance(px, py, x1, y1) * 1000  # Convert to meters
    
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return haversine_distance(px, py, closest_x, closest_y) * 1000  # Convert to meters

def utm_to_latlon(easting: float, northing: float, zone: int = 17) -> Tuple[float, float]:
    """Convert UTM coordinates to lat/lon (approximate, for EPSG:32617)."""
    lat = (northing / 111320.0) - 45.0
    lon = ((easting - 500000.0) / (111320.0 * math.cos(math.radians(lat)))) - 79.0
    return lat, lon

def extract_fiber_count(size_str: str) -> int:
    """Extract fiber count from size string."""
    import re
    match = re.search(r'(\d+)', str(size_str))
    return int(match.group(1)) if match else 0

def load_terminals(filepath: str = "Terminal.geojson") -> List[Dict[str, Any]]:
    """Load terminal data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    terminals = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        terminal_id = props.get("ID") or props.get("id")
        terminal_type = props.get("Type") or props.get("type") or ""
        
        coords = geom.get("coordinates", [])
        if geom.get("type") == "Point" and len(coords) >= 2:
            if coords[0] > 1000:  # UTM
                lat, lon = utm_to_latlon(coords[0], coords[1])
            else:
                lon, lat = coords[0], coords[1]
            
            terminals.append({
                "id": terminal_id,
                "type": terminal_type,
                "coordinates": (lat, lon),
                "utm": (coords[0], coords[1]) if coords[0] > 1000 else None,
                "properties": props
            })
    
    print(f"  ✓ Loaded {len(terminals)} terminals")
    return terminals

def load_fiber_cables(filepath: str = "fiber cable.geojson") -> List[Dict[str, Any]]:
    """Load fiber cable data, focusing on infrastructure cables (≥48F)."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    cables = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        # Extract fiber count
        fiber_count = 0
        if props.get("FiberCount"):
            try:
                fiber_count = int(props.get("FiberCount"))
            except (ValueError, TypeError):
                pass
        
        if fiber_count == 0:
            size_str = props.get("Size", "")
            fiber_count = extract_fiber_count(size_str)
        
        # Focus on infrastructure cables (≥48F: 288, 144, 96, 72, 48)
        if fiber_count < 48:
            continue
        
        coords = geom.get("coordinates", [])
        geom_type = geom.get("type", "")
        
        if geom_type in ["LineString", "MultiLineString"]:
            converted_coords = []
            
            if geom_type == "MultiLineString":
                for line in coords:
                    for coord in line:
                        if len(coord) >= 2:
                            if coord[0] > 1000:  # UTM
                                lat, lon = utm_to_latlon(coord[0], coord[1])
                            else:
                                lon, lat = coord[0], coord[1]
                            converted_coords.append((lat, lon))
            else:  # LineString
                for coord in coords:
                    if len(coord) >= 2:
                        if coord[0] > 1000:  # UTM
                            lat, lon = utm_to_latlon(coord[0], coord[1])
                        else:
                            lon, lat = coord[0], coord[1]
                        converted_coords.append((lat, lon))
            
            if converted_coords:
                cables.append({
                    "id": props.get("ID") or props.get("id"),
                    "fiber_count": fiber_count,
                    "size": props.get("Size", ""),
                    "coordinates": converted_coords
                })
    
    print(f"  ✓ Loaded {len(cables)} infrastructure cables (≥48F)")
    return cables

def load_foscs(filepath: str = "splice closure.geojson") -> List[Dict[str, Any]]:
    """Load FOSC data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    foscs = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        fosc_id = props.get("ID") or props.get("id")
        
        coords = geom.get("coordinates", [])
        if geom.get("type") == "Point" and len(coords) >= 2:
            if coords[0] > 1000:  # UTM
                lat, lon = utm_to_latlon(coords[0], coords[1])
            else:
                lon, lat = coords[0], coords[1]
            
            foscs.append({
                "id": fosc_id,
                "coordinates": (lat, lon),
                "utm": (coords[0], coords[1]) if coords[0] > 1000 else None
            })
    
    print(f"  ✓ Loaded {len(foscs)} FOSCs")
    return foscs

def find_nearest_infrastructure_cable(terminal_coords: Tuple[float, float], 
                                     cables: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
    """Find nearest infrastructure cable to terminal."""
    min_distance = float('inf')
    nearest_cable = None
    
    for cable in cables:
        coords = cable["coordinates"]
        
        for i in range(len(coords) - 1):
            dist = point_to_line_distance(terminal_coords, coords[i], coords[i + 1])
            if dist < min_distance:
                min_distance = dist
                nearest_cable = cable
    
    return nearest_cable, min_distance

def find_nearest_fosc(terminal_coords: Tuple[float, float], 
                     foscs: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
    """Find nearest FOSC to terminal."""
    min_distance = float('inf')
    nearest_fosc = None
    
    for fosc in foscs:
        fosc_coords = fosc["coordinates"]
        dist = haversine_distance(terminal_coords[0], terminal_coords[1],
                                 fosc_coords[0], fosc_coords[1]) * 1000  # Convert to meters
        
        if dist < min_distance:
            min_distance = dist
            nearest_fosc = fosc
    
    return nearest_fosc, min_distance

def analyze_terminal_placement(terminals: List[Dict[str, Any]],
                              cables: List[Dict[str, Any]],
                              foscs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze terminal placement patterns."""
    print("\nAnalyzing terminal placement patterns...")
    
    results = {
        "aerial_terminals": [],
        "mst_terminals": [],
        "unknown_terminals": []
    }
    
    for terminal in terminals:
        terminal_coords = terminal["coordinates"]
        terminal_type = terminal.get("type", "").upper()
        
        # Find nearest infrastructure cable
        nearest_cable, cable_distance = find_nearest_infrastructure_cable(terminal_coords, cables)
        
        # Find nearest FOSC
        nearest_fosc, fosc_distance = find_nearest_fosc(terminal_coords, foscs)
        
        analysis = {
            "terminal_id": terminal["id"],
            "type": terminal_type,
            "distance_to_infrastructure_cable_m": round(cable_distance, 2) if nearest_cable else None,
            "nearest_cable_size": nearest_cable["fiber_count"] if nearest_cable else None,
            "distance_to_fosc_m": round(fosc_distance, 2) if nearest_fosc else None,
            "nearest_fosc_id": nearest_fosc["id"] if nearest_fosc else None
        }
        
        # Classify terminal
        if "MST" in terminal_type or "mst" in terminal_type.lower():
            results["mst_terminals"].append(analysis)
        elif "AERIAL" in terminal_type or "aerial" in terminal_type.lower() or terminal_type == "":
            results["aerial_terminals"].append(analysis)
        else:
            results["unknown_terminals"].append(analysis)
    
    return results

def generate_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary statistics."""
    summary = {
        "aerial_terminal_stats": {},
        "mst_terminal_stats": {},
        "rule_validation": {}
    }
    
    # Aerial Terminal Statistics
    aerial = analysis["aerial_terminals"]
    if aerial:
        cable_distances = [t["distance_to_infrastructure_cable_m"] 
                          for t in aerial if t["distance_to_infrastructure_cable_m"] is not None]
        fosc_distances = [t["distance_to_fosc_m"] 
                         for t in aerial if t["distance_to_fosc_m"] is not None]
        cable_sizes = [t["nearest_cable_size"] 
                      for t in aerial if t["nearest_cable_size"] is not None]
        
        summary["aerial_terminal_stats"] = {
            "total_count": len(aerial),
            "on_infrastructure_cable": len([d for d in cable_distances if d < 50]),  # Within 50m
            "distance_to_cable": {
                "mean_m": round(statistics.mean(cable_distances), 2) if cable_distances else None,
                "median_m": round(statistics.median(cable_distances), 2) if cable_distances else None,
                "min_m": round(min(cable_distances), 2) if cable_distances else None,
                "max_m": round(max(cable_distances), 2) if cable_distances else None
            },
            "cable_size_distribution": {
                size: cable_sizes.count(size) 
                for size in set(cable_sizes)
            }
        }
    
    # MST Terminal Statistics
    mst = analysis["mst_terminals"]
    if mst:
        cable_distances = [t["distance_to_infrastructure_cable_m"] 
                          for t in mst if t["distance_to_infrastructure_cable_m"] is not None]
        fosc_distances = [t["distance_to_fosc_m"] 
                         for t in mst if t["distance_to_fosc_m"] is not None]
        
        summary["mst_terminal_stats"] = {
            "total_count": len(mst),
            "connected_to_fosc": len([d for d in fosc_distances if d < 500]),  # Within 500m
            "distance_to_cable": {
                "mean_m": round(statistics.mean(cable_distances), 2) if cable_distances else None,
                "median_m": round(statistics.median(cable_distances), 2) if cable_distances else None,
                "min_m": round(min(cable_distances), 2) if cable_distances else None,
                "max_m": round(max(cable_distances), 2) if cable_distances else None
            },
            "distance_to_fosc": {
                "mean_m": round(statistics.mean(fosc_distances), 2) if fosc_distances else None,
                "median_m": round(statistics.median(fosc_distances), 2) if fosc_distances else None,
                "min_m": round(min(fosc_distances), 2) if fosc_distances else None,
                "max_m": round(max(fosc_distances), 2) if fosc_distances else None
            },
            "far_from_cable_200m": len([d for d in cable_distances if d >= 200])  # 200m or more
        }
    
    # Rule Validation
    summary["rule_validation"] = {
        "rule1_aerial_on_infrastructure": {
            "description": "Aerial terminals placed on infrastructure cables (288/144/96/72/48)",
            "valid": summary["aerial_terminal_stats"].get("on_infrastructure_cable", 0) > 0,
            "percentage": round((summary["aerial_terminal_stats"].get("on_infrastructure_cable", 0) / 
                               summary["aerial_terminal_stats"].get("total_count", 1)) * 100, 1) 
                        if summary["aerial_terminal_stats"].get("total_count", 0) > 0 else 0
        },
        "rule2_mst_connects_fosc": {
            "description": "MSTs connect to FOSCs",
            "valid": summary["mst_terminal_stats"].get("connected_to_fosc", 0) > 0,
            "percentage": round((summary["mst_terminal_stats"].get("connected_to_fosc", 0) / 
                               summary["mst_terminal_stats"].get("total_count", 1)) * 100, 1)
                        if summary["mst_terminal_stats"].get("total_count", 0) > 0 else 0
        },
        "rule3_mst_far_from_cable": {
            "description": "MSTs used for communities 200m+ away from infrastructure cable",
            "valid": summary["mst_terminal_stats"].get("far_from_cable_200m", 0) > 0,
            "percentage": round((summary["mst_terminal_stats"].get("far_from_cable_200m", 0) / 
                               summary["mst_terminal_stats"].get("total_count", 1)) * 100, 1)
                        if summary["mst_terminal_stats"].get("total_count", 0) > 0 else 0
        }
    }
    
    return summary

def main():
    """Main execution."""
    print("=" * 80)
    print("TERMINAL PLACEMENT RULES ANALYSIS")
    print("=" * 80)
    
    # Load data
    terminals = load_terminals()
    cables = load_fiber_cables()
    foscs = load_foscs()
    
    if not terminals:
        print("\n⚠️  No terminals found. Cannot analyze.")
        return
    
    if not cables:
        print("\n⚠️  No infrastructure cables found. Cannot analyze distance to cables.")
        return
    
    # Analyze
    analysis = analyze_terminal_placement(terminals, cables, foscs)
    
    # Generate summary
    summary = generate_summary(analysis)
    
    # Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    
    output = {
        "summary": summary,
        "detailed_analysis": analysis
    }
    
    with open("terminal_placement_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("  ✓ Saved terminal_placement_analysis.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nAerial Terminals: {summary['aerial_terminal_stats'].get('total_count', 0)}")
    if summary["aerial_terminal_stats"].get("total_count", 0) > 0:
        stats = summary["aerial_terminal_stats"]
        print(f"  On Infrastructure Cable (<50m): {stats.get('on_infrastructure_cable', 0)} "
              f"({stats.get('on_infrastructure_cable', 0) / stats.get('total_count', 1) * 100:.1f}%)")
        if stats.get("distance_to_cable", {}).get("mean_m"):
            dist = stats["distance_to_cable"]
            print(f"  Distance to Cable: mean={dist['mean_m']}m, median={dist['median_m']}m")
        if stats.get("cable_size_distribution"):
            print(f"  Cable Size Distribution: {stats['cable_size_distribution']}")
    
    print(f"\nMST Terminals: {summary['mst_terminal_stats'].get('total_count', 0)}")
    if summary["mst_terminal_stats"].get("total_count", 0) > 0:
        stats = summary["mst_terminal_stats"]
        print(f"  Connected to FOSC (<500m): {stats.get('connected_to_fosc', 0)} "
              f"({stats.get('connected_to_fosc', 0) / stats.get('total_count', 1) * 100:.1f}%)")
        print(f"  Far from Cable (≥200m): {stats.get('far_from_cable_200m', 0)} "
              f"({stats.get('far_from_cable_200m', 0) / stats.get('total_count', 1) * 100:.1f}%)")
        if stats.get("distance_to_cable", {}).get("mean_m"):
            dist = stats["distance_to_cable"]
            print(f"  Distance to Cable: mean={dist['mean_m']}m, median={dist['median_m']}m")
        if stats.get("distance_to_fosc", {}).get("mean_m"):
            dist = stats["distance_to_fosc"]
            print(f"  Distance to FOSC: mean={dist['mean_m']}m, median={dist['median_m']}m")
    
    print(f"\n" + "=" * 80)
    print("RULE VALIDATION")
    print("=" * 80)
    
    for rule_name, rule_data in summary["rule_validation"].items():
        status = "✅ VALID" if rule_data["valid"] else "❌ INVALID"
        print(f"\n{rule_name}: {status}")
        print(f"  {rule_data['description']}")
        print(f"  Percentage: {rule_data['percentage']}%")
    
    print(f"\n✅ Analysis complete. See terminal_placement_analysis.json for details.")


if __name__ == "__main__":
    main()

