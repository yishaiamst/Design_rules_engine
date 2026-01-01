#!/usr/bin/env python3
"""
analyze_olt_fiber_proximity.py
-------------------------------------------------------------------------------
Analyze OLT placement relative to main fiber infrastructure (288F/144F/96F).
Determine optimal placement strategy: OLT near fiber routes, ONTs within range.
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple
import math
import statistics

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
    """Calculate minimum distance from point to line segment."""
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    # Vector from line_start to line_end
    dx = x2 - x1
    dy = y2 - y1
    
    # If line is a point, return distance to that point
    if dx == 0 and dy == 0:
        return haversine_distance(px, py, x1, y1)
    
    # Vector from line_start to point
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    
    # Closest point on line segment
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return haversine_distance(px, py, closest_x, closest_y)

def utm_to_latlon(easting: float, northing: float, zone: int = 17) -> Tuple[float, float]:
    """Convert UTM coordinates to lat/lon (approximate, for EPSG:32617)."""
    lat = (northing / 111320.0) - 45.0
    lon = ((easting - 500000.0) / (111320.0 * math.cos(math.radians(lat)))) - 79.0
    return lat, lon

def extract_fiber_count(size_str: str) -> int:
    """Extract fiber count from size string (e.g., '288F' -> 288)."""
    import re
    match = re.search(r'(\d+)', str(size_str))
    return int(match.group(1)) if match else 0

def load_olts(filepath: str = "OLT.geojson") -> Dict[str, Dict[str, Any]]:
    """Load OLT data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    olts = {}
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        olt_id = props.get("ID") or props.get("id")
        if not olt_id:
            continue
        
        coords = geom.get("coordinates", [])
        if geom.get("type") == "MultiPoint" and coords:
            coords = coords[0]
        
        if len(coords) >= 2:
            if coords[0] > 1000:  # UTM
                lat, lon = utm_to_latlon(coords[0], coords[1])
            else:
                lon, lat = coords[0], coords[1]
            
            olts[olt_id] = {
                "id": olt_id,
                "name": props.get("Name", ""),
                "coordinates": (lat, lon),
                "utm": (coords[0], coords[1]) if coords[0] > 1000 else None
            }
    
    print(f"  ✓ Loaded {len(olts)} OLTs")
    return olts

def load_fiber_cables(filepath: str = "fiber cable.geojson") -> List[Dict[str, Any]]:
    """Load fiber cable data, focusing on main infrastructure (288F/144F/96F)."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    cables = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        # Extract fiber count - check multiple possible field names
        # Try FiberCount first (it's a string like "96")
        fiber_count = 0
        size_str = props.get("Size", "")
        
        if props.get("FiberCount"):
            try:
                fiber_count = int(props.get("FiberCount"))
            except (ValueError, TypeError):
                pass
        
        # If not found, try Size field (e.g., "96F")
        if fiber_count == 0:
            fiber_count = extract_fiber_count(size_str)
        
        # If still not found, try to extract from ID field (e.g., "288FOC/..." -> 288)
        if fiber_count == 0:
            id_str = props.get("ID", "")
            fiber_count = extract_fiber_count(id_str)
        
        # Focus on main infrastructure cables (288F, 144F, 96F)
        if fiber_count < 96:
            continue
        
        coords = geom.get("coordinates", [])
        geom_type = geom.get("type", "")
        
        # Handle both LineString and MultiLineString
        if geom_type in ["LineString", "MultiLineString"]:
            # Convert coordinates
            converted_coords = []
            
            # MultiLineString has nested arrays
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
                    "size": size_str,
                    "coordinates": converted_coords,
                    "length": props.get("calclength") or 0
                })
    
    print(f"  ✓ Loaded {len(cables)} main infrastructure cables (≥96F)")
    
    # Count by size
    size_counts = {}
    for cable in cables:
        size = cable["fiber_count"]
        size_counts[size] = size_counts.get(size, 0) + 1
    
    print(f"  Size distribution: {size_counts}")
    return cables

def find_nearest_fiber_cable(olt_coords: Tuple[float, float], 
                            cables: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float, Tuple[float, float]]:
    """Find nearest main infrastructure cable to OLT."""
    min_distance = float('inf')
    nearest_cable = None
    nearest_point = None
    
    for cable in cables:
        coords = cable["coordinates"]
        
        # Check distance to each segment
        for i in range(len(coords) - 1):
            dist = point_to_line_distance(olt_coords, coords[i], coords[i + 1])
            if dist < min_distance:
                min_distance = dist
                nearest_cable = cable
                # Calculate nearest point on segment
                px, py = olt_coords
                x1, y1 = coords[i]
                x2, y2 = coords[i + 1]
                dx = x2 - x1
                dy = y2 - y1
                if dx == 0 and dy == 0:
                    nearest_point = coords[i]
                else:
                    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
                    nearest_point = (x1 + t * dx, y1 + t * dy)
    
    return nearest_cable, min_distance, nearest_point

def analyze_olt_fiber_proximity(olts: Dict[str, Dict[str, Any]], 
                                cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze OLT placement relative to fiber infrastructure."""
    print("\nAnalyzing OLT proximity to fiber infrastructure...")
    
    results = {}
    
    for olt_id, olt_data in olts.items():
        olt_coords = olt_data["coordinates"]
        
        # Find nearest main infrastructure cable
        nearest_cable, distance, nearest_point = find_nearest_fiber_cable(olt_coords, cables)
        
        results[olt_id] = {
            "olt_id": olt_id,
            "olt_name": olt_data.get("name", ""),
            "olt_coordinates": {"lat": olt_coords[0], "lon": olt_coords[1]},
            "nearest_fiber_cable": {
                "id": nearest_cable["id"] if nearest_cable else None,
                "fiber_count": nearest_cable["fiber_count"] if nearest_cable else None,
                "size": nearest_cable["size"] if nearest_cable else None,
                "distance_km": round(distance, 2) if nearest_cable else None,
                "nearest_point": {"lat": nearest_point[0], "lon": nearest_point[1]} if nearest_point else None
            } if nearest_cable else None
        }
    
    return results

def generate_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary statistics."""
    distances = []
    size_distribution = {}
    
    for olt_id, stats in analysis.items():
        nearest = stats.get("nearest_fiber_cable")
        if nearest and nearest.get("distance_km") is not None:
            distances.append(nearest["distance_km"])
            size = nearest.get("fiber_count")
            if size:
                size_distribution[size] = size_distribution.get(size, 0) + 1
    
    summary = {
        "total_olts_analyzed": len(analysis),
        "olts_with_nearby_fiber": len(distances),
        "distance_to_fiber_statistics": {
            "mean_km": round(statistics.mean(distances), 2) if distances else None,
            "median_km": round(statistics.median(distances), 2) if distances else None,
            "min_km": round(min(distances), 2) if distances else None,
            "max_km": round(max(distances), 2) if distances else None
        },
        "nearest_fiber_size_distribution": size_distribution,
        "recommendations": []
    }
    
    # Generate recommendations
    if distances:
        avg_dist = statistics.mean(distances)
        if avg_dist < 1.0:
            summary["recommendations"].append(
                "OLTs are very close to fiber infrastructure (<1km). Current placement strategy is optimal."
            )
        elif avg_dist < 3.0:
            summary["recommendations"].append(
                f"OLTs are reasonably close to fiber infrastructure (avg {avg_dist:.2f}km). Placement near fiber routes is appropriate."
            )
        else:
            summary["recommendations"].append(
                f"Some OLTs are far from fiber infrastructure (avg {avg_dist:.2f}km). Consider placing OLTs closer to main fiber routes."
            )
    
    return summary

def main():
    """Main execution."""
    print("=" * 80)
    print("OLT-FIBER INFRASTRUCTURE PROXIMITY ANALYSIS")
    print("=" * 80)
    
    # Load data
    olts = load_olts()
    cables = load_fiber_cables()
    
    if not cables:
        print("\n⚠️  No main infrastructure cables (≥96F) found. Cannot analyze proximity.")
        return
    
    # Analyze
    analysis = analyze_olt_fiber_proximity(olts, cables)
    
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
    
    with open("olt_fiber_proximity_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("  ✓ Saved olt_fiber_proximity_analysis.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal OLTs Analyzed: {summary['total_olts_analyzed']}")
    print(f"OLTs with Nearby Fiber Infrastructure: {summary['olts_with_nearby_fiber']}")
    
    if summary["distance_to_fiber_statistics"]["mean_km"]:
        print(f"\nDistance to Nearest Fiber Infrastructure:")
        dist_stats = summary["distance_to_fiber_statistics"]
        print(f"  Mean: {dist_stats['mean_km']} km")
        print(f"  Median: {dist_stats['median_km']} km")
        print(f"  Min: {dist_stats['min_km']} km")
        print(f"  Max: {dist_stats['max_km']} km")
    
    print(f"\nNearest Fiber Size Distribution:")
    for size, count in sorted(summary["nearest_fiber_size_distribution"].items(), reverse=True):
        print(f"  {size}F: {count} OLTs")
    
    print(f"\nRecommendations:")
    for rec in summary["recommendations"]:
        print(f"  • {rec}")
    
    # Print examples
    print(f"\n" + "=" * 80)
    print("TOP EXAMPLES")
    print("=" * 80)
    
    # Sort by distance to fiber
    sorted_olts = sorted(
        [(olt_id, stats) for olt_id, stats in analysis.items()],
        key=lambda x: x[1].get("nearest_fiber_cable", {}).get("distance_km", 999) or 999
    )
    
    print("\nOLTs Closest to Fiber Infrastructure:")
    for olt_id, stats in sorted_olts[:5]:
        nearest = stats.get("nearest_fiber_cable")
        if nearest and nearest.get("distance_km") is not None:
            print(f"  OLT {olt_id} ({stats.get('olt_name', '')}): {nearest['distance_km']:.2f}km from {nearest['fiber_count']}F cable")
    
    print("\nOLTs Farthest from Fiber Infrastructure:")
    for olt_id, stats in sorted_olts[-5:]:
        nearest = stats.get("nearest_fiber_cable")
        if nearest and nearest.get("distance_km") is not None:
            print(f"  OLT {olt_id} ({stats.get('olt_name', '')}): {nearest['distance_km']:.2f}km from {nearest['fiber_count']}F cable")
    
    print(f"\n✅ Analysis complete. See olt_fiber_proximity_analysis.json for details.")


if __name__ == "__main__":
    main()

