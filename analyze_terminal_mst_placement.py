#!/usr/bin/env python3
"""
analyze_terminal_mst_placement.py
-------------------------------------------------------------------------------
Analyze Terminal and MST placement patterns to verify refined rules:
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
    """Calculate minimum distance from point to line segment (in km)."""
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        return haversine_distance(px, py, x1, y1)
    
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return haversine_distance(px, py, closest_x, closest_y)

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
    """Load Terminal data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    terminals = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        
        terminal_id = props.get("ID") or props.get("id")
        terminal_type = props.get("Type") or props.get("type", "")
        
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

def load_stub_cables(filepath: str = "stub cable.geojson") -> Dict[str, Dict[str, Any]]:
    """Load stub cable data and create terminal-to-FOSC mapping."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    terminal_to_fosc = {}  # terminal_id -> {fosc_id, length_m}
    
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        
        from_id = props.get("From_ID") or props.get("from_id")
        to_id = props.get("To_ID") or props.get("to_id")
        
        # Stub cables connect FOSC (From_ID) to Terminal (To_ID)
        if from_id and to_id:
            # Check if from_id is FOSC (starts with F) and to_id is Terminal (starts with T)
            if (from_id.startswith("F") and to_id.startswith("T")):
                length = props.get("MeasLength") or props.get("CalcLength") or 0
                try:
                    length = float(length) if length else 0
                except (ValueError, TypeError):
                    length = 0
                
                terminal_to_fosc[to_id] = {
                    "fosc_id": from_id,
                    "stub_length_m": length
                }
    
    print(f"  ✓ Loaded {len(terminal_to_fosc)} terminal-to-FOSC stub cable connections")
    return terminal_to_fosc

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
    
    # Count by size
    size_counts = {}
    for cable in cables:
        size = cable["fiber_count"]
        size_counts[size] = size_counts.get(size, 0) + 1
    
    print(f"  Size distribution: {size_counts}")
    return cables

def find_nearest_fiber_cable(terminal_coords: Tuple[float, float], 
                            cables: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float, Tuple[float, float]]:
    """Find nearest infrastructure cable to terminal."""
    min_distance = float('inf')
    nearest_cable = None
    nearest_point = None
    
    for cable in cables:
        coords = cable["coordinates"]
        
        for i in range(len(coords) - 1):
            dist = point_to_line_distance(terminal_coords, coords[i], coords[i + 1])
            if dist < min_distance:
                min_distance = dist
                nearest_cable = cable
                # Calculate nearest point on segment
                px, py = terminal_coords
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

def find_nearest_fosc(terminal_coords: Tuple[float, float], 
                     foscs: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], float]:
    """Find nearest FOSC to terminal."""
    min_distance = float('inf')
    nearest_fosc = None
    
    for fosc in foscs:
        fosc_coords = fosc["coordinates"]
        dist = haversine_distance(terminal_coords[0], terminal_coords[1],
                                 fosc_coords[0], fosc_coords[1])
        if dist < min_distance:
            min_distance = dist
            nearest_fosc = fosc
    
    return nearest_fosc, min_distance

def analyze_terminal_placement(terminals: List[Dict[str, Any]], 
                              cables: List[Dict[str, Any]],
                              foscs: List[Dict[str, Any]],
                              stub_cables: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze terminal placement patterns."""
    print("\nAnalyzing terminal placement patterns...")
    
    results = {
        "aerial_terminals": [],
        "msts": [],
        "summary": {}
    }
    
    for terminal in terminals:
        terminal_coords = terminal["coordinates"]
        terminal_type = terminal.get("type", "").lower()
        
        # Find nearest infrastructure cable
        nearest_cable, cable_distance, nearest_point = find_nearest_fiber_cable(
            terminal_coords, cables
        )
        
        # Find nearest FOSC
        nearest_fosc, fosc_distance = find_nearest_fosc(terminal_coords, foscs)
        
        # Check if terminal has stub cable connection (definitive MST indicator)
        stub_connection = stub_cables.get(terminal_id)
        
        # Classify as Aerial Terminal or MST
        # MST if: has stub cable connection OR type indicates MST
        is_mst = stub_connection is not None or "mst" in terminal_type or "stub" in terminal_type.lower()
        
        terminal_data = {
            "terminal_id": terminal["id"],
            "type": terminal_type,
            "is_mst": is_mst,
            "coordinates": {"lat": terminal_coords[0], "lon": terminal_coords[1]},
            "nearest_infrastructure_cable": {
                "id": nearest_cable["id"] if nearest_cable else None,
                "fiber_count": nearest_cable["fiber_count"] if nearest_cable else None,
                "size": nearest_cable["size"] if nearest_cable else None,
                "distance_m": round(cable_distance * 1000, 2) if nearest_cable else None
            } if nearest_cable else None,
            "nearest_fosc": {
                "id": nearest_fosc["id"] if nearest_fosc else None,
                "distance_m": round(fosc_distance * 1000, 2) if nearest_fosc else None
            } if nearest_fosc else None,
            "stub_cable_connection": {
                "fosc_id": stub_connection["fosc_id"] if stub_connection else None,
                "stub_length_m": stub_connection["stub_length_m"] if stub_connection else None
            } if stub_connection else None
        }
        
        if is_mst:
            results["msts"].append(terminal_data)
        else:
            results["aerial_terminals"].append(terminal_data)
    
    return results

def generate_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary statistics."""
    aerial = analysis["aerial_terminals"]
    msts = analysis["msts"]
    
    # Aerial terminal distances to infrastructure
    aerial_distances = [
        t["nearest_infrastructure_cable"]["distance_m"]
        for t in aerial
        if t.get("nearest_infrastructure_cable") and t["nearest_infrastructure_cable"].get("distance_m") is not None
    ]
    
    # MST distances to infrastructure
    mst_distances = [
        t["nearest_infrastructure_cable"]["distance_m"]
        for t in msts
        if t.get("nearest_infrastructure_cable") and t["nearest_infrastructure_cable"].get("distance_m") is not None
    ]
    
    # MST distances to FOSC (geographic)
    mst_fosc_distances = [
        t["nearest_fosc"]["distance_m"]
        for t in msts
        if t.get("nearest_fosc") and t["nearest_fosc"].get("distance_m") is not None
    ]
    
    # MST stub cable connections
    mst_stub_connections = [
        t["stub_cable_connection"]
        for t in msts
        if t.get("stub_cable_connection") and t["stub_cable_connection"].get("fosc_id")
    ]
    
    mst_stub_lengths = [
        conn["stub_length_m"]
        for conn in mst_stub_connections
        if conn.get("stub_length_m") is not None
    ]
    
    # Infrastructure cable sizes for aerial terminals
    aerial_cable_sizes = defaultdict(int)
    for t in aerial:
        if t.get("nearest_infrastructure_cable"):
            size = t["nearest_infrastructure_cable"].get("fiber_count")
            if size:
                aerial_cable_sizes[size] += 1
    
    summary = {
        "total_terminals": len(aerial) + len(msts),
        "aerial_terminals": {
            "count": len(aerial),
            "distance_to_infrastructure": {
                "mean_m": round(statistics.mean(aerial_distances), 2) if aerial_distances else None,
                "median_m": round(statistics.median(aerial_distances), 2) if aerial_distances else None,
                "min_m": round(min(aerial_distances), 2) if aerial_distances else None,
                "max_m": round(max(aerial_distances), 2) if aerial_distances else None,
                "p95_m": round(statistics.quantiles(aerial_distances, n=20)[18], 2) if len(aerial_distances) >= 20 else None
            },
            "infrastructure_cable_sizes": dict(aerial_cable_sizes),
            "on_cable_count": len([d for d in aerial_distances if d < 10]),  # Within 10m
            "near_cable_count": len([d for d in aerial_distances if d < 200])  # Within 200m
        },
        "msts": {
            "count": len(msts),
            "distance_to_infrastructure": {
                "mean_m": round(statistics.mean(mst_distances), 2) if mst_distances else None,
                "median_m": round(statistics.median(mst_distances), 2) if mst_distances else None,
                "min_m": round(min(mst_distances), 2) if mst_distances else None,
                "max_m": round(max(mst_distances), 2) if mst_distances else None
            },
            "distance_to_fosc": {
                "mean_m": round(statistics.mean(mst_fosc_distances), 2) if mst_fosc_distances else None,
                "median_m": round(statistics.median(mst_fosc_distances), 2) if mst_fosc_distances else None,
                "min_m": round(min(mst_fosc_distances), 2) if mst_fosc_distances else None,
                "max_m": round(max(mst_fosc_distances), 2) if mst_fosc_distances else None
            },
            "beyond_200m_count": len([d for d in mst_distances if d >= 200]) if mst_distances else 0
        },
        "rule_validation": {}
    }
    
    # Validate rules
    # Rule 1: Aerial terminals on infrastructure cables
    if aerial_distances:
        on_cable_pct = (summary["aerial_terminals"]["on_cable_count"] / len(aerial_distances)) * 100
        summary["rule_validation"]["aerial_on_infrastructure"] = {
            "validated": on_cable_pct > 80,  # 80% should be on/near cable
            "percentage_on_cable": round(on_cable_pct, 2),
            "threshold_used": "10m"
        }
    
    # Rule 2: Aerial terminals on infrastructure cable sizes (288/144/96/72/48)
    valid_sizes = [288, 144, 96, 72, 48]
    total_aerial_with_cable = sum(aerial_cable_sizes.values())
    valid_size_count = sum(aerial_cable_sizes.get(s, 0) for s in valid_sizes)
    if total_aerial_with_cable > 0:
        valid_size_pct = (valid_size_count / total_aerial_with_cable) * 100
        summary["rule_validation"]["aerial_on_valid_sizes"] = {
            "validated": valid_size_pct > 90,  # 90% should be on valid sizes
            "percentage_valid": round(valid_size_pct, 2),
            "valid_sizes": valid_sizes
        }
    
    # Rule 3: MSTs connect to FOSCs via stub cables
    if mst_stub_connections:
        connection_pct = (len(mst_stub_connections) / len(msts)) * 100 if msts else 0
        summary["rule_validation"]["mst_connects_fosc"] = {
            "validated": connection_pct > 80,  # 80% should have stub cable to FOSC
            "percentage_with_stub_cable": round(connection_pct, 2),
            "total_msts": len(msts),
            "msts_with_stub": len(mst_stub_connections)
        }
    
    # Rule 4: MSTs for communities 200m+ away from infrastructure
    if mst_distances:
        beyond_200m_pct = (summary["msts"]["beyond_200m_count"] / len(mst_distances)) * 100
        summary["rule_validation"]["mst_beyond_200m"] = {
            "validated": beyond_200m_pct > 70,  # 70% should be beyond 200m
            "percentage_beyond_200m": round(beyond_200m_pct, 2),
            "threshold": "200m"
        }
    
    return summary

def main():
    """Main execution."""
    print("=" * 80)
    print("TERMINAL & MST PLACEMENT ANALYSIS")
    print("=" * 80)
    
    # Load data
    terminals = load_terminals()
    cables = load_fiber_cables()
    foscs = load_foscs()
    stub_cables = load_stub_cables()
    
    if not terminals:
        print("\n⚠️  No terminals found. Cannot analyze.")
        return
    
    if not cables:
        print("\n⚠️  No infrastructure cables found. Cannot analyze.")
        return
    
    # Analyze
    analysis = analyze_terminal_placement(terminals, cables, foscs, stub_cables)
    
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
    
    with open("terminal_mst_placement_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("  ✓ Saved terminal_mst_placement_analysis.json")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal Terminals: {summary['total_terminals']}")
    print(f"  Aerial Terminals: {summary['aerial_terminals']['count']}")
    print(f"  MSTs: {summary['msts']['count']}")
    
    print(f"\n{'='*80}")
    print("AERIAL TERMINAL ANALYSIS")
    print(f"{'='*80}")
    if summary["aerial_terminals"]["distance_to_infrastructure"]["mean_m"]:
        dist_stats = summary["aerial_terminals"]["distance_to_infrastructure"]
        print(f"\nDistance to Infrastructure Cable:")
        print(f"  Mean: {dist_stats['mean_m']} m")
        print(f"  Median: {dist_stats['median_m']} m")
        print(f"  Min: {dist_stats['min_m']} m")
        print(f"  Max: {dist_stats['max_m']} m")
        print(f"  On cable (<10m): {summary['aerial_terminals']['on_cable_count']} ({summary['aerial_terminals']['on_cable_count']/len(analysis['aerial_terminals'])*100:.1f}%)")
        print(f"  Near cable (<200m): {summary['aerial_terminals']['near_cable_count']} ({summary['aerial_terminals']['near_cable_count']/len(analysis['aerial_terminals'])*100:.1f}%)")
    
    print(f"\nInfrastructure Cable Sizes:")
    for size, count in sorted(summary["aerial_terminals"]["infrastructure_cable_sizes"].items(), reverse=True):
        print(f"  {size}F: {count}")
    
    print(f"\n{'='*80}")
    print("MST ANALYSIS")
    print(f"{'='*80}")
    if summary["msts"]["distance_to_infrastructure"]["mean_m"]:
        dist_stats = summary["msts"]["distance_to_infrastructure"]
        print(f"\nDistance to Infrastructure Cable:")
        print(f"  Mean: {dist_stats['mean_m']} m")
        print(f"  Median: {dist_stats['median_m']} m")
        print(f"  Min: {dist_stats['min_m']} m")
        print(f"  Max: {dist_stats['max_m']} m")
        print(f"  Beyond 200m: {summary['msts']['beyond_200m_count']} ({summary['msts']['beyond_200m_count']/len(analysis['msts'])*100:.1f}%)")
    
    if summary["msts"]["distance_to_fosc"]["mean_m"]:
        fosc_stats = summary["msts"]["distance_to_fosc"]
        print(f"\nDistance to FOSC (geographic):")
        print(f"  Mean: {fosc_stats['mean_m']} m")
        print(f"  Median: {fosc_stats['median_m']} m")
        print(f"  Min: {fosc_stats['min_m']} m")
        print(f"  Max: {fosc_stats['max_m']} m")
    
    if summary["msts"]["stub_cable_connections"]["count"] > 0:
        stub_stats = summary["msts"]["stub_cable_connections"]
        print(f"\nStub Cable Connections:")
        print(f"  MSTs with stub cable: {stub_stats['count']} ({stub_stats['percentage_with_stub']}%)")
        if stub_stats["stub_lengths"]["mean_m"]:
            length_stats = stub_stats["stub_lengths"]
            print(f"  Stub Length Statistics:")
            print(f"    Mean: {length_stats['mean_m']} m")
            print(f"    Median: {length_stats['median_m']} m")
            print(f"    Min: {length_stats['min_m']} m")
            print(f"    Max: {length_stats['max_m']} m")
    
    print(f"\n{'='*80}")
    print("RULE VALIDATION")
    print(f"{'='*80}")
    for rule_name, validation in summary["rule_validation"].items():
        status = "✅ VALIDATED" if validation.get("validated") else "❌ NOT VALIDATED"
        print(f"\n{rule_name}: {status}")
        for key, value in validation.items():
            if key != "validated":
                print(f"  {key}: {value}")
    
    print(f"\n✅ Analysis complete. See terminal_mst_placement_analysis.json for details.")


if __name__ == "__main__":
    main()

