#!/usr/bin/env python3
"""
analyze_olt_placement_patterns.py
-------------------------------------------------------------------------------
Analyze actual OLT placement patterns in existing design.
Compare OLT locations to ONT clusters to understand placement strategy.
-------------------------------------------------------------------------------
"""

import json
from collections import defaultdict
from typing import Dict, List, Any, Tuple
import statistics
import math
import re

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula."""
    R = 6371  # Earth radius in km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def utm_to_latlon(easting: float, northing: float, zone: int = 17) -> Tuple[float, float]:
    """Convert UTM coordinates to lat/lon (approximate, for EPSG:32617)."""
    # This is a simplified conversion - for production, use pyproj
    # EPSG:32617 is UTM Zone 17N
    # Approximate conversion (not precise, but good enough for analysis)
    lat = (northing / 111320.0) - 45.0  # Rough approximation
    lon = ((easting - 500000.0) / (111320.0 * math.cos(math.radians(lat)))) - 79.0
    return lat, lon

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
        
        # Extract coordinates
            coords = geom.get("coordinates", [])
        if geom.get("type") == "MultiPoint" and coords:
            coords = coords[0]  # Take first point
        
            if len(coords) >= 2:
            # Check if UTM (large numbers) or lat/lon
            if coords[0] > 1000:  # Likely UTM
                easting, northing = coords[0], coords[1]
                lat, lon = utm_to_latlon(easting, northing)
            else:
                lon, lat = coords[0], coords[1]
            
            # Parse subscriber count (handle complex formats)
            subscriber_count = 0
            no_of_addr = props.get("NoOfAddr", "")
            if no_of_addr:
                # Extract first number from string (e.g., "1608(...)" -> 1608)
                match = re.search(r'(\d+)', str(no_of_addr))
                if match:
                    subscriber_count = int(match.group(1))
            
            olts[olt_id] = {
                "id": olt_id,
                "name": props.get("Name", ""),
                "coordinates": (lat, lon),
                "utm": (coords[0], coords[1]) if coords[0] > 1000 else None,
                "subscriber_count": subscriber_count,
                "properties": props
            }
    
    print(f"  ✓ Loaded {len(olts)} OLTs")
    return olts

def load_onts(filepath: str = "ONT.geojson") -> List[Dict[str, Any]]:
    """Load ONT data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    onts = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        ont_id = props.get("ID") or props.get("id") or props.get("ONT_ID")
        olt_id = props.get("OLT_ID") or props.get("olt_id")
        
            coords = geom.get("coordinates", [])
        if geom.get("type") == "Point" and len(coords) >= 2:
            # Check if UTM or lat/lon
            if coords[0] > 1000:  # Likely UTM
                easting, northing = coords[0], coords[1]
                lat, lon = utm_to_latlon(easting, northing)
            else:
                lon, lat = coords[0], coords[1]
            
            onts.append({
                "id": ont_id,
                "olt_id": olt_id,
                "coordinates": (lat, lon),
                "utm": (coords[0], coords[1]) if coords[0] > 1000 else None
            })
    
    print(f"  ✓ Loaded {len(onts)} ONTs")
    return onts

def load_ont_paths(filepath: str = "olt_ont_paths.json") -> Dict[str, List[Dict[str, Any]]]:
    """Load ONT paths grouped by OLT."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if isinstance(data, list):
        paths = data
    else:
        paths = data.get("paths", [])
    
    # Group by OLT
    olt_paths = defaultdict(list)
    for path in paths:
        olt_id = path.get("olt_id")
        if olt_id:
            olt_paths[olt_id].append(path)
    
    print(f"  ✓ Loaded {len(paths)} paths for {len(olt_paths)} OLTs")
    return dict(olt_paths)

def calculate_ont_cluster_centroid(onts: List[Dict[str, Any]]) -> Tuple[float, float]:
    """Calculate geometric centroid of ONT cluster."""
    if not onts:
        return None, None
    
    lats = [ont["coordinates"][0] for ont in onts if ont.get("coordinates")]
    lons = [ont["coordinates"][1] for ont in onts if ont.get("coordinates")]
    
    if not lats or not lons:
        return None, None
    
    return statistics.mean(lats), statistics.mean(lons)

def analyze_olt_placement(olts: Dict[str, Dict[str, Any]], 
                         onts: List[Dict[str, Any]],
                         olt_paths: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Analyze OLT placement patterns."""
    print("\nAnalyzing OLT placement patterns...")
    
    # Group ONTs by OLT
    olt_ont_groups = defaultdict(list)
    for ont in onts:
        olt_id = ont.get("olt_id")
        if olt_id and olt_id in olts:
            olt_ont_groups[olt_id].append(ont)
    
    # Also use paths to get ONT-OLT relationships
    for olt_id, paths in olt_paths.items():
        if olt_id not in olt_ont_groups:
            # Try to find ONTs from paths
    for path in paths:
        ont_id = path.get("ont_id")
                # We'll use path data for distance analysis
    
    results = {}
    
    for olt_id, olt_data in olts.items():
        olt_lat, olt_lon = olt_data["coordinates"]
        ont_list = olt_ont_groups.get(olt_id, [])
        paths = olt_paths.get(olt_id, [])
        
        # Calculate cluster centroid from ONTs
        if ont_list:
            cluster_lat, cluster_lon = calculate_ont_cluster_centroid(ont_list)
        else:
            cluster_lat, cluster_lon = None, None
        
        # Calculate distances
        distances_to_centroid = []
        distances_to_olt = []
        ont_coords_list = []
        
        for ont in ont_list:
            ont_lat, ont_lon = ont["coordinates"]
            ont_coords_list.append((ont_lat, ont_lon))
            
            # Distance from ONT to OLT
            dist_to_olt = haversine_distance(ont_lat, ont_lon, olt_lat, olt_lon)
            distances_to_olt.append(dist_to_olt)
            
            # Distance from ONT to cluster centroid
            if cluster_lat and cluster_lon:
                dist_to_centroid = haversine_distance(ont_lat, ont_lon, cluster_lat, cluster_lon)
                distances_to_centroid.append(dist_to_centroid)
        
        # Distance from OLT to cluster centroid
        olt_to_centroid_dist = None
        if cluster_lat and cluster_lon:
            olt_to_centroid_dist = haversine_distance(olt_lat, olt_lon, cluster_lat, cluster_lon)
        
        # Calculate statistics
        stats = {
            "olt_id": olt_id,
            "olt_name": olt_data.get("name", ""),
            "olt_coordinates": {"lat": olt_lat, "lon": olt_lon},
            "subscriber_count": olt_data.get("subscriber_count", len(ont_list)),
            "ont_count": len(ont_list),
            "cluster_centroid": {"lat": cluster_lat, "lon": cluster_lon} if cluster_lat else None,
            "olt_to_centroid_distance_km": round(olt_to_centroid_dist, 2) if olt_to_centroid_dist else None,
            "distance_statistics": {}
        }
        
        if distances_to_olt:
            stats["distance_statistics"] = {
                "ont_to_olt": {
                    "mean_km": round(statistics.mean(distances_to_olt), 2),
                    "median_km": round(statistics.median(distances_to_olt), 2),
                    "min_km": round(min(distances_to_olt), 2),
                    "max_km": round(max(distances_to_olt), 2),
                    "p95_km": round(statistics.quantiles(distances_to_olt, n=20)[18], 2) if len(distances_to_olt) >= 20 else None
                }
            }
        
        if distances_to_centroid:
            stats["distance_statistics"]["ont_to_centroid"] = {
                "mean_km": round(statistics.mean(distances_to_centroid), 2),
                "median_km": round(statistics.median(distances_to_centroid), 2),
                "min_km": round(min(distances_to_centroid), 2),
                "max_km": round(max(distances_to_centroid), 2)
            }
        
        # Analysis
        if olt_to_centroid_dist is not None:
            if olt_to_centroid_dist < 1.0:
                stats["placement_type"] = "at_centroid"
                stats["placement_description"] = "OLT placed at or very near cluster centroid (<1km)"
            elif olt_to_centroid_dist < 5.0:
                stats["placement_type"] = "near_centroid"
                stats["placement_description"] = "OLT placed near cluster centroid (1-5km)"
            else:
                stats["placement_type"] = "offset_from_centroid"
                stats["placement_description"] = f"OLT placed offset from centroid ({olt_to_centroid_dist:.2f}km)"
        else:
            stats["placement_type"] = "unknown"
            stats["placement_description"] = "Cannot determine (no ONT coordinates)"
        
        results[olt_id] = stats
    
    return results

def generate_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary statistics."""
    placement_types = defaultdict(int)
    olt_to_centroid_distances = []
    
    for olt_id, stats in analysis.items():
        placement_type = stats.get("placement_type", "unknown")
        placement_types[placement_type] += 1
        
        dist = stats.get("olt_to_centroid_distance_km")
        if dist is not None:
            olt_to_centroid_distances.append(dist)
    
    summary = {
        "total_olts_analyzed": len(analysis),
        "placement_type_distribution": dict(placement_types),
        "olt_to_centroid_distance": {
            "mean_km": round(statistics.mean(olt_to_centroid_distances), 2) if olt_to_centroid_distances else None,
            "median_km": round(statistics.median(olt_to_centroid_distances), 2) if olt_to_centroid_distances else None,
            "min_km": round(min(olt_to_centroid_distances), 2) if olt_to_centroid_distances else None,
            "max_km": round(max(olt_to_centroid_distances), 2) if olt_to_centroid_distances else None
        },
        "recommendations": []
    }
    
    # Generate recommendations
    at_centroid_count = placement_types.get("at_centroid", 0)
    near_centroid_count = placement_types.get("near_centroid", 0)
    total_with_data = at_centroid_count + near_centroid_count + placement_types.get("offset_from_centroid", 0)
    
    if total_with_data > 0:
        centroid_percentage = ((at_centroid_count + near_centroid_count) / total_with_data) * 100
        
        if centroid_percentage > 80:
            summary["recommendations"].append(
                "Most OLTs are placed at or near cluster centroids. Recommend using centroid placement strategy."
            )
        elif centroid_percentage > 50:
            summary["recommendations"].append(
                "Many OLTs are placed near centroids, but some are offset. Consider centroid as primary with adjustments."
            )
        else:
            summary["recommendations"].append(
                "OLTs show significant offset from centroids. Investigate factors causing offset (infrastructure, routes, etc.)."
            )
    
    if olt_to_centroid_distances:
        avg_dist = statistics.mean(olt_to_centroid_distances)
        if avg_dist < 2.0:
            summary["recommendations"].append(
                f"Average OLT-to-centroid distance is {avg_dist:.2f}km. Centroid placement is appropriate."
            )
    else:
            summary["recommendations"].append(
                f"Average OLT-to-centroid distance is {avg_dist:.2f}km. Consider factors beyond centroid (routes, infrastructure)."
            )
    
    return summary

def main():
    """Main execution."""
    print("=" * 80)
    print("OLT PLACEMENT PATTERN ANALYSIS")
    print("=" * 80)
    
    # Load data
    olts = load_olts()
    onts = load_onts()
    olt_paths = load_ont_paths()
    
    # Analyze
    analysis = analyze_olt_placement(olts, onts, olt_paths)
    
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
    
    with open("olt_placement_patterns.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("  ✓ Saved olt_placement_patterns.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal OLTs Analyzed: {summary['total_olts_analyzed']}")
    print(f"\nPlacement Type Distribution:")
    for ptype, count in summary["placement_type_distribution"].items():
        print(f"  {ptype}: {count}")
    
    if summary["olt_to_centroid_distance"]["mean_km"]:
        print(f"\nOLT-to-Centroid Distance:")
        dist_stats = summary["olt_to_centroid_distance"]
        print(f"  Mean: {dist_stats['mean_km']} km")
        print(f"  Median: {dist_stats['median_km']} km")
        print(f"  Min: {dist_stats['min_km']} km")
        print(f"  Max: {dist_stats['max_km']} km")
    
    print(f"\nRecommendations:")
    for rec in summary["recommendations"]:
        print(f"  • {rec}")
    
    # Print top examples
    print(f"\n" + "=" * 80)
    print("TOP EXAMPLES")
    print("=" * 80)
    
    # Sort by OLT-to-centroid distance
    sorted_olts = sorted(
        [(olt_id, stats) for olt_id, stats in analysis.items()],
        key=lambda x: x[1].get("olt_to_centroid_distance_km", 999) or 999
    )
    
    print("\nOLTs Closest to Centroid:")
    for olt_id, stats in sorted_olts[:5]:
        dist = stats.get("olt_to_centroid_distance_km")
        if dist is not None:
            print(f"  OLT {olt_id} ({stats.get('olt_name', '')}): {dist:.2f}km from centroid, {stats.get('ont_count', 0)} ONTs")
    
    print("\nOLTs Farthest from Centroid:")
    for olt_id, stats in sorted_olts[-5:]:
        dist = stats.get("olt_to_centroid_distance_km")
        if dist is not None:
            print(f"  OLT {olt_id} ({stats.get('olt_name', '')}): {dist:.2f}km from centroid, {stats.get('ont_count', 0)} ONTs")
    
    print(f"\n✅ Analysis complete. See olt_placement_patterns.json for details.")


if __name__ == "__main__":
    main()
