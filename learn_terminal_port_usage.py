#!/usr/bin/env python3
"""
Learn terminal port usage and stub cable sizing from actual design.
"""

import json
from collections import defaultdict, Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

def learn_terminal_port_usage():
    """Learn how many drop cables connect to each terminal type."""
    print("=" * 80)
    print("LEARNING TERMINAL PORT USAGE")
    print("=" * 80)
    print()
    
    # Load terminals
    print("Loading terminals...")
    terminals = load_geojson("terminal.geojson")
    terminal_features = terminals.get("features", [])
    print(f"  Loaded {len(terminal_features)} terminals")
    
    # Load drop cables
    print("Loading drop cables...")
    drop_cables = load_geojson("drop cable.geojson")
    drop_features = drop_cables.get("features", [])
    print(f"  Loaded {len(drop_features)} drop cables")
    
    # Load stub cables
    print("Loading stub cables...")
    try:
        stub_cables = load_geojson("stub cable.geojson")
        stub_features = stub_cables.get("features", [])
        print(f"  Loaded {len(stub_features)} stub cables")
    except:
        stub_features = []
        print("  No stub cable file found")
    
    # Build terminal position map
    terminal_data = {}
    for feat in terminal_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        terminal_id = props.get("ID") or props.get("id", "")
        terminal_type = props.get("Type") or props.get("type", "")
        terminal_model = props.get("Model") or props.get("model", "")
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            terminal_data[terminal_id] = {
                "id": terminal_id,
                "type": terminal_type,
                "model": terminal_model,
                "position": (coords[0], coords[1]),
                "drop_cable_count": 0,
                "stub_cable_size": None
            }
    
    # Count drop cables per terminal
    print("\nAnalyzing drop cable connections...")
    matched_count = 0
    unmatched_count = 0
    
    for idx, feat in enumerate(drop_features):
        props = feat.get("properties", {})
        
        # Find terminal - drop cables go FROM terminal TO ONT
        # So terminal ID is in From_ID field
        terminal_id = props.get("From_ID")
        
        if not terminal_id:
            continue
        
        # Convert to string for matching
        terminal_id = str(terminal_id)
        
        # Try exact match
        if terminal_id in terminal_data:
            terminal_data[terminal_id]["drop_cable_count"] += 1
            matched_count += 1
        else:
            unmatched_count += 1
            # Debug first few unmatched (only if it looks like a terminal ID)
            if unmatched_count <= 10 and terminal_id.startswith("T"):
                # Check if similar IDs exist
                similar = [tid for tid in list(terminal_data.keys())[:20] if terminal_id[:6] in str(tid) or str(tid)[:6] in terminal_id]
                if similar:
                    print(f"    Unmatched terminal ID: {terminal_id}, similar: {similar[:2]}")
    
    print(f"  Matched {matched_count} drop cables to terminals")
    print(f"  Unmatched {unmatched_count} drop cables")
    
    # Analyze stub cables for MSTs
    print("Analyzing stub cable connections...")
    stub_matched = 0
    stub_unmatched = 0
    for idx, feat in enumerate(stub_features):
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # Extract stub cable size
        size_str = props.get("Size") or props.get("size", "")
        size = None
        if size_str:
            if isinstance(size_str, str):
                size = int(size_str.replace("F", "")) if size_str.replace("F", "").isdigit() else None
            elif isinstance(size_str, (int, float)):
                size = int(size_str)
        
        # Find terminal - stub cables go FROM FOSC TO Terminal
        # So terminal ID is in To_ID field (opposite of drop cables)
        terminal_id = props.get("To_ID")
        
        if not terminal_id:
            if idx < 5:
                print(f"    Sample stub cable {idx}: No To_ID found, From_ID={props.get('From_ID')}")
            stub_unmatched += 1
            continue
        
        # Convert to string for matching
        terminal_id = str(terminal_id)
        
        # Try exact match (MST only)
        if terminal_id in terminal_data:
            if terminal_data[terminal_id]["type"] == "MST":
                if size:
                    terminal_data[terminal_id]["stub_cable_size"] = size
                    stub_matched += 1
            else:
                # Not an MST - this is expected for some terminals
                if idx < 5:
                    print(f"    Stub cable {idx}: Terminal {terminal_id} is {terminal_data[terminal_id]['type']}, not MST")
        else:
            stub_unmatched += 1
            # Debug first few
            if stub_unmatched <= 5 and terminal_id.startswith("T"):
                print(f"    Unmatched stub terminal ID: {terminal_id}")
    
    print(f"  Matched {stub_matched} stub cables to MST terminals")
    print(f"  Unmatched {stub_unmatched} stub cables")
    
    # Analyze by terminal type and model
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    
    by_type_model = defaultdict(lambda: {"count": 0, "drop_counts": [], "stub_sizes": []})
    
    for term_id, term in terminal_data.items():
        key = f"{term['type']}_{term['model']}"
        by_type_model[key]["count"] += 1
        by_type_model[key]["drop_counts"].append(term["drop_cable_count"])
        if term["stub_cable_size"]:
            by_type_model[key]["stub_sizes"].append(term["stub_cable_size"])
    
    print("\nTerminal Port Usage (Drop Cables per Terminal):")
    print(f"{'Type':<20} {'Model':<15} {'Count':<10} {'Min':<8} {'Max':<8} {'Mean':<8} {'Median':<8} {'Mode':<8}")
    print("-" * 95)
    
    for key in sorted(by_type_model.keys()):
        data = by_type_model[key]
        type_model = key.split("_", 1)
        term_type = type_model[0] if len(type_model) > 0 else ""
        term_model = type_model[1] if len(type_model) > 1 else ""
        
        drop_counts = data["drop_counts"]
        if drop_counts:
            min_drops = min(drop_counts)
            max_drops = max(drop_counts)
            mean_drops = sum(drop_counts) / len(drop_counts)
            sorted_drops = sorted(drop_counts)
            median_drops = sorted_drops[len(sorted_drops) // 2]
            mode_drops = Counter(drop_counts).most_common(1)[0][0]
            
            print(f"{term_type:<20} {term_model:<15} {data['count']:<10} {min_drops:<8} {max_drops:<8} {mean_drops:<8.1f} {median_drops:<8} {mode_drops:<8}")
    
    print("\nStub Cable Sizing (MST only):")
    print(f"{'MST Model':<15} {'Count':<10} {'Stub Sizes':<30} {'Most Common':<15}")
    print("-" * 70)
    
    for key in sorted(by_type_model.keys()):
        if not key.startswith("MST_"):
            continue
        data = by_type_model[key]
        term_model = key.replace("MST_", "")
        
        stub_sizes = data["stub_sizes"]
        if stub_sizes:
            size_counter = Counter(stub_sizes)
            most_common = size_counter.most_common(1)[0] if size_counter else (None, 0)
            size_dist = ", ".join([f"{size}F: {count}" for size, count in size_counter.most_common(5)])
            
            print(f"{term_model:<15} {data['count']:<10} {size_dist:<30} {f'{most_common[0]}F ({most_common[1]})':<15}")
    
    # Save learned patterns
    patterns = {}
    for key, data in by_type_model.items():
        type_model = key.split("_", 1)
        term_type = type_model[0] if len(type_model) > 0 else ""
        term_model = type_model[1] if len(type_model) > 1 else ""
        
        drop_counts = data["drop_counts"]
        if drop_counts:
            patterns[key] = {
                "type": term_type,
                "model": term_model,
                "count": data["count"],
                "drop_cable_stats": {
                    "min": min(drop_counts),
                    "max": max(drop_counts),
                    "mean": sum(drop_counts) / len(drop_counts),
                    "median": sorted(drop_counts)[len(drop_counts) // 2],
                    "mode": Counter(drop_counts).most_common(1)[0][0]
                }
            }
        
        stub_sizes = data["stub_sizes"]
        if stub_sizes:
            size_counter = Counter(stub_sizes)
            most_common_size = size_counter.most_common(1)[0][0] if size_counter else None
            if key not in patterns:
                patterns[key] = {
                    "type": term_type,
                    "model": term_model,
                    "count": data["count"]
                }
            patterns[key]["stub_cable_size"] = most_common_size
            patterns[key]["stub_size_distribution"] = dict(size_counter)
    
    with open("terminal_port_usage_patterns.json", "w") as f:
        json.dump(patterns, f, indent=2)
    
    print("\n" + "=" * 80)
    print("LEARNING COMPLETE")
    print("=" * 80)
    print("  ✓ Saved patterns to terminal_port_usage_patterns.json")
    print()
    
    return patterns

if __name__ == "__main__":
    learn_terminal_port_usage()
