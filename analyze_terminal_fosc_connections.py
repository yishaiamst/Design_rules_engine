#!/usr/bin/env python3
"""
Analyze actual terminal-FOSC connections to understand MST vs Aerial Terminal patterns.
"""

import json
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

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

def analyze_terminal_fosc_connections():
    """Analyze how terminals connect to FOSCs in actual design."""
    print("=" * 80)
    print("TERMINAL-FOSC CONNECTION ANALYSIS")
    print("=" * 80)
    print()
    
    # Load terminals
    print("Loading terminals...")
    terminals = load_geojson("terminal.geojson")
    terminal_features = terminals.get("features", [])
    print(f"  Loaded {len(terminal_features)} terminals")
    
    # Load FOSCs
    print("Loading FOSCs...")
    foscs = load_geojson("splice closure.geojson")
    fosc_features = foscs.get("features", [])
    print(f"  Loaded {len(fosc_features)} FOSCs")
    
    # Load stub cables (MST → FOSC connections)
    print("Loading stub cables...")
    try:
        stub_cables = load_geojson("stub cable.geojson")
        stub_features = stub_cables.get("features", [])
        print(f"  Loaded {len(stub_features)} stub cables")
    except:
        stub_features = []
        print("  No stub cable file found")
    
    # Load drop cables to count ONTs per terminal
    print("Loading drop cables...")
    drop_cables = load_geojson("drop cable.geojson")
    drop_features = drop_cables.get("features", [])
    print(f"  Loaded {len(drop_features)} drop cables")
    
    # Build terminal data
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
                "ont_count": 0,
                "connected_to_fosc": False,
                "fosc_id": None,
                "distance_to_fosc": None,
                "has_stub_cable": False
            }
    
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
    
    # Analyze stub cables to find MST-FOSC connections
    print("\nAnalyzing stub cables...")
    terminal_to_fosc = {}
    for feat in stub_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # Try to extract terminal and FOSC IDs from stub cable
        from_id = props.get("From") or props.get("from_id") or props.get("FromID")
        to_id = props.get("To") or props.get("to_id") or props.get("ToID")
        
        # Or extract from ID field
        cable_id = props.get("ID") or props.get("id", "")
        if "/" in cable_id:
            parts = cable_id.split("/")
            if len(parts) >= 3:
                from_id = parts[1] if not from_id else from_id
                to_id = parts[2] if not to_id else to_id
        
        # Match by geometry (stub cable connects terminal to FOSC)
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            # Handle nested coordinates (LineString or MultiLineString)
            start = coords[0]
            end = coords[-1]
            
            # Flatten if needed
            while isinstance(start, list) and len(start) > 0 and isinstance(start[0], list):
                start = start[0]
            while isinstance(end, list) and len(end) > 0 and isinstance(end[0], list):
                end = end[-1]
            
            if isinstance(start, list) and len(start) >= 2:
                start_x, start_y = float(start[0]), float(start[1])
            else:
                continue
            if isinstance(end, list) and len(end) >= 2:
                end_x, end_y = float(end[0]), float(end[1])
            else:
                continue
            
            # Find terminal at start
            for term_id, term in terminals_data.items():
                term_pos = term["position"]
                if isinstance(term_pos, (list, tuple)) and len(term_pos) >= 2:
                    term_x, term_y = term_pos[0], term_pos[1]
                    if euclidean_distance(start_x, start_y, term_x, term_y) < 50:
                        # Find FOSC at end
                        for fosc_id, fosc in foscs_data.items():
                            fosc_pos = fosc["position"]
                            if isinstance(fosc_pos, (list, tuple)) and len(fosc_pos) >= 2:
                                fosc_x, fosc_y = fosc_pos[0], fosc_pos[1]
                                if euclidean_distance(end_x, end_y, fosc_x, fosc_y) < 50:
                                    terminal_to_fosc[term_id] = fosc_id
                                    terminals_data[term_id]["connected_to_fosc"] = True
                                    terminals_data[term_id]["fosc_id"] = fosc_id
                                    terminals_data[term_id]["has_stub_cable"] = True
                                    dist = euclidean_distance(term_x, term_y, fosc_x, fosc_y)
                                    terminals_data[term_id]["distance_to_fosc"] = dist
                                    break
                        break
    
    # Also check by proximity (terminal near FOSC)
    print("Analyzing terminal-FOSC proximity...")
    for term_id, term in terminals_data.items():
        if term["connected_to_fosc"]:
            continue  # Already connected via stub cable
        
        term_pos = term["position"]
        if not isinstance(term_pos, (list, tuple)) or len(term_pos) < 2:
            continue
        
        term_x, term_y = term_pos[0], term_pos[1]
        min_dist = float('inf')
        nearest_fosc_id = None
        
        for fosc_id, fosc in foscs_data.items():
            fosc_pos = fosc["position"]
            if not isinstance(fosc_pos, (list, tuple)) or len(fosc_pos) < 2:
                continue
            fosc_x, fosc_y = fosc_pos[0], fosc_pos[1]
            dist = euclidean_distance(term_x, term_y, fosc_x, fosc_y)
            if dist < min_dist:
                min_dist = dist
                nearest_fosc_id = fosc_id
        
        # Consider connected if within 500m (stub cable range)
        if min_dist < 500:
            term["connected_to_fosc"] = True
            term["fosc_id"] = nearest_fosc_id
            term["distance_to_fosc"] = min_dist
    
    # Count ONTs per terminal from drop cables
    print("Counting ONTs per terminal from drop cables...")
    terminal_ont_counts = defaultdict(int)
    for feat in drop_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # Try to extract terminal ID
        to_id = props.get("To") or props.get("to_id") or props.get("ToID")
        cable_id = props.get("ID") or props.get("id", "")
        
        # Match by geometry (drop cable ends at terminal)
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            # Handle nested coordinates (LineString or MultiLineString)
            end = coords[-1]
            # Flatten if needed
            while isinstance(end, list) and len(end) > 0 and isinstance(end[0], list):
                end = end[-1]
            if isinstance(end, list) and len(end) >= 2:
                end_x, end_y = float(end[0]), float(end[1])
            else:
                continue
            
            # Find terminal at end
            for term_id, term in terminals_data.items():
                term_pos = term["position"]
                if isinstance(term_pos, (list, tuple)) and len(term_pos) >= 2:
                    term_x, term_y = term_pos[0], term_pos[1]
                    if euclidean_distance(end_x, end_y, term_x, term_y) < 50:
                        terminal_ont_counts[term_id] += 1
                        break
    
    # Update terminal ONT counts
    for term_id, count in terminal_ont_counts.items():
        if term_id in terminals_data:
            terminals_data[term_id]["ont_count"] = count
    
    # Analyze by terminal type
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    
    aerial_stats = {
        "total": 0,
        "connected_to_fosc": 0,
        "not_connected_to_fosc": 0,
        "ont_counts": [],
        "distances_to_fosc": []
    }
    
    mst_stats = {
        "total": 0,
        "connected_to_fosc": 0,
        "not_connected_to_fosc": 0,
        "has_stub_cable": 0,
        "ont_counts": [],
        "distances_to_fosc": []
    }
    
    for term_id, term in terminals_data.items():
        term_type = term["type"]
        
        if term_type == "Aerial Terminal":
            aerial_stats["total"] += 1
            if term["connected_to_fosc"]:
                aerial_stats["connected_to_fosc"] += 1
                if term["distance_to_fosc"]:
                    aerial_stats["distances_to_fosc"].append(term["distance_to_fosc"])
            else:
                aerial_stats["not_connected_to_fosc"] += 1
            if term["ont_count"] > 0:
                aerial_stats["ont_counts"].append(term["ont_count"])
        
        elif term_type == "MST":
            mst_stats["total"] += 1
            if term["connected_to_fosc"]:
                mst_stats["connected_to_fosc"] += 1
                if term["distance_to_fosc"]:
                    mst_stats["distances_to_fosc"].append(term["distance_to_fosc"])
            else:
                mst_stats["not_connected_to_fosc"] += 1
            if term["has_stub_cable"]:
                mst_stats["has_stub_cable"] += 1
            if term["ont_count"] > 0:
                mst_stats["ont_counts"].append(term["ont_count"])
    
    print("\nAERIAL TERMINAL STATISTICS:")
    print(f"  Total: {aerial_stats['total']}")
    print(f"  Connected to FOSC: {aerial_stats['connected_to_fosc']} ({aerial_stats['connected_to_fosc']/aerial_stats['total']*100:.1f}%)")
    print(f"  NOT connected to FOSC: {aerial_stats['not_connected_to_fosc']} ({aerial_stats['not_connected_to_fosc']/aerial_stats['total']*100:.1f}%)")
    if aerial_stats["ont_counts"]:
        print(f"  ONT count - Min: {min(aerial_stats['ont_counts'])}, Max: {max(aerial_stats['ont_counts'])}, Mean: {sum(aerial_stats['ont_counts'])/len(aerial_stats['ont_counts']):.1f}, Median: {sorted(aerial_stats['ont_counts'])[len(aerial_stats['ont_counts'])//2]}")
    if aerial_stats["distances_to_fosc"]:
        print(f"  Distance to FOSC (when connected) - Min: {min(aerial_stats['distances_to_fosc']):.1f}m, Max: {max(aerial_stats['distances_to_fosc']):.1f}m, Mean: {sum(aerial_stats['distances_to_fosc'])/len(aerial_stats['distances_to_fosc']):.1f}m")
    
    print("\nMST STATISTICS:")
    print(f"  Total: {mst_stats['total']}")
    print(f"  Connected to FOSC: {mst_stats['connected_to_fosc']} ({mst_stats['connected_to_fosc']/mst_stats['total']*100:.1f}%)")
    print(f"  NOT connected to FOSC: {mst_stats['not_connected_to_fosc']} ({mst_stats['not_connected_to_fosc']/mst_stats['total']*100:.1f}%)")
    print(f"  Has stub cable: {mst_stats['has_stub_cable']} ({mst_stats['has_stub_cable']/mst_stats['total']*100:.1f}%)")
    if mst_stats["ont_counts"]:
        print(f"  ONT count - Min: {min(mst_stats['ont_counts'])}, Max: {max(mst_stats['ont_counts'])}, Mean: {sum(mst_stats['ont_counts'])/len(mst_stats['ont_counts']):.1f}, Median: {sorted(mst_stats['ont_counts'])[len(mst_stats['ont_counts'])//2]}")
    if mst_stats["distances_to_fosc"]:
        print(f"  Distance to FOSC (when connected) - Min: {min(mst_stats['distances_to_fosc']):.1f}m, Max: {max(mst_stats['distances_to_fosc']):.1f}m, Mean: {sum(mst_stats['distances_to_fosc'])/len(mst_stats['distances_to_fosc']):.1f}m")
    
    # Save results
    results = {
        "aerial_terminal": {
            "total": aerial_stats["total"],
            "connected_to_fosc": aerial_stats["connected_to_fosc"],
            "not_connected_to_fosc": aerial_stats["not_connected_to_fosc"],
            "connection_rate": aerial_stats["connected_to_fosc"]/aerial_stats["total"]*100 if aerial_stats["total"] > 0 else 0,
            "ont_count_stats": {
                "min": min(aerial_stats["ont_counts"]) if aerial_stats["ont_counts"] else 0,
                "max": max(aerial_stats["ont_counts"]) if aerial_stats["ont_counts"] else 0,
                "mean": sum(aerial_stats["ont_counts"])/len(aerial_stats["ont_counts"]) if aerial_stats["ont_counts"] else 0,
                "median": sorted(aerial_stats["ont_counts"])[len(aerial_stats["ont_counts"])//2] if aerial_stats["ont_counts"] else 0
            },
            "distance_to_fosc_stats": {
                "min": min(aerial_stats["distances_to_fosc"]) if aerial_stats["distances_to_fosc"] else 0,
                "max": max(aerial_stats["distances_to_fosc"]) if aerial_stats["distances_to_fosc"] else 0,
                "mean": sum(aerial_stats["distances_to_fosc"])/len(aerial_stats["distances_to_fosc"]) if aerial_stats["distances_to_fosc"] else 0
            }
        },
        "mst": {
            "total": mst_stats["total"],
            "connected_to_fosc": mst_stats["connected_to_fosc"],
            "not_connected_to_fosc": mst_stats["not_connected_to_fosc"],
            "has_stub_cable": mst_stats["has_stub_cable"],
            "connection_rate": mst_stats["connected_to_fosc"]/mst_stats["total"]*100 if mst_stats["total"] > 0 else 0,
            "ont_count_stats": {
                "min": min(mst_stats["ont_counts"]) if mst_stats["ont_counts"] else 0,
                "max": max(mst_stats["ont_counts"]) if mst_stats["ont_counts"] else 0,
                "mean": sum(mst_stats["ont_counts"])/len(mst_stats["ont_counts"]) if mst_stats["ont_counts"] else 0,
                "median": sorted(mst_stats["ont_counts"])[len(mst_stats["ont_counts"])//2] if mst_stats["ont_counts"] else 0
            },
            "distance_to_fosc_stats": {
                "min": min(mst_stats["distances_to_fosc"]) if mst_stats["distances_to_fosc"] else 0,
                "max": max(mst_stats["distances_to_fosc"]) if mst_stats["distances_to_fosc"] else 0,
                "mean": sum(mst_stats["distances_to_fosc"])/len(mst_stats["distances_to_fosc"]) if mst_stats["distances_to_fosc"] else 0
            }
        }
    }
    
    with open("terminal_fosc_connection_analysis.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 80)
    print("RESULTS SAVED")
    print("=" * 80)
    print("  ✓ Saved terminal_fosc_connection_analysis.json")
    print()
    
    return results

if __name__ == "__main__":
    analyze_terminal_fosc_connections()

