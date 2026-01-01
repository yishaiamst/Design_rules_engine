#!/usr/bin/env python3
"""
Learn terminal port limits and cable patterns from actual design.
"""

import json
from collections import defaultdict, Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

def learn_terminal_cable_patterns():
    """Learn terminal port limits and cable patterns from actual design."""
    print("=" * 80)
    print("LEARNING TERMINAL CABLE PATTERNS FROM ACTUAL DESIGN")
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
        print("  ⚠️  No stub cable file found")
    
    # Build terminal data
    terminals_data = {}
    for feat in terminal_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        terminal_id = props.get("ID") or props.get("id", "")
        terminal_type = props.get("Type") or props.get("type", "")
        terminal_model = props.get("Model") or props.get("model", "")
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            terminals_data[terminal_id] = {
                "id": terminal_id,
                "type": terminal_type,
                "model": terminal_model,
                "position": (coords[0], coords[1]),
                "drop_cable_count": 0,
                "stub_cable_size": None
            }
    
    # Count drop cables per terminal
    print("\nAnalyzing drop cables per terminal...")
    terminal_drop_counts = defaultdict(int)
    matched_count = 0
    
    for feat in drop_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # Try to extract terminal ID from drop cable properties first
        from_id = props.get("From") or props.get("from_id") or props.get("FromID") or props.get("from")
        to_id = props.get("To") or props.get("to_id") or props.get("ToID") or props.get("to")
        
        matched = False
        
        # Try ID-based matching first
        if to_id and to_id in terminals_data:
            terminal_drop_counts[to_id] += 1
            terminals_data[to_id]["drop_cable_count"] += 1
            matched = True
            matched_count += 1
        elif from_id and from_id in terminals_data:
            # Sometimes terminal is at "from" instead of "to"
            terminal_drop_counts[from_id] += 1
            terminals_data[from_id]["drop_cable_count"] += 1
            matched = True
            matched_count += 1
        
        # If ID matching failed, try geometry matching
        if not matched:
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                # Handle nested coordinates (LineString vs MultiLineString)
                if geometry.get("type") == "MultiLineString":
                    # Get last point of last line
                    end = coords[-1][-1] if isinstance(coords[-1], list) and len(coords[-1]) > 0 else coords[-1]
                else:
                    end = coords[-1]
                
                # Flatten nested lists
                while isinstance(end, list) and len(end) > 0:
                    if isinstance(end[0], (int, float)):
                        break
                    end = end[-1] if isinstance(end[-1], list) else end[0]
                
                if isinstance(end, list) and len(end) >= 2:
                    end_x, end_y = float(end[0]), float(end[1])
                    
                    # Find terminal at end point (use larger tolerance)
                    min_dist = float('inf')
                    closest_term_id = None
                    
                    for term_id, term in terminals_data.items():
                        term_pos = term["position"]
                        if isinstance(term_pos, (list, tuple)) and len(term_pos) >= 2:
                            term_x, term_y = term_pos[0], term_pos[1]
                            dist = euclidean_distance(end_x, end_y, term_x, term_y)
                            if dist < min_dist:
                                min_dist = dist
                                closest_term_id = term_id
                    
                    if min_dist < 100:  # 100m tolerance
                        terminal_drop_counts[closest_term_id] += 1
                        terminals_data[closest_term_id]["drop_cable_count"] += 1
                        matched_count += 1
    
    print(f"  Matched {matched_count}/{len(drop_features)} drop cables to terminals")
    
    # Analyze stub cables per MST
    print("Analyzing stub cables per MST...")
    terminal_stub_sizes = {}
    stub_matched_count = 0
    
    for feat in stub_features:
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
        
        # Try to extract terminal ID from properties first
        from_id = props.get("From") or props.get("from_id") or props.get("FromID") or props.get("from")
        to_id = props.get("To") or props.get("to_id") or props.get("ToID") or props.get("to")
        
        matched = False
        
        # Try ID-based matching first
        if from_id and from_id in terminals_data and terminals_data[from_id]["type"] == "MST":
            if size:
                terminal_stub_sizes[from_id] = size
                terminals_data[from_id]["stub_cable_size"] = size
                matched = True
                stub_matched_count += 1
        
        # If ID matching failed, try geometry matching
        if not matched:
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                # Handle nested coordinates
                if geometry.get("type") == "MultiLineString":
                    start = coords[0][0] if isinstance(coords[0], list) and len(coords[0]) > 0 else coords[0]
                else:
                    start = coords[0]
                
                # Flatten nested lists
                while isinstance(start, list) and len(start) > 0:
                    if isinstance(start[0], (int, float)):
                        break
                    start = start[0] if isinstance(start[0], list) else start[-1]
                
                if isinstance(start, list) and len(start) >= 2:
                    start_x, start_y = float(start[0]), float(start[1])
                    
                    # Find MST terminal at start point
                    min_dist = float('inf')
                    closest_term_id = None
                    
                    for term_id, term in terminals_data.items():
                        if term["type"] != "MST":
                            continue
                        term_pos = term["position"]
                        if isinstance(term_pos, (list, tuple)) and len(term_pos) >= 2:
                            term_x, term_y = term_pos[0], term_pos[1]
                            dist = euclidean_distance(start_x, start_y, term_x, term_y)
                            if dist < min_dist:
                                min_dist = dist
                                closest_term_id = term_id
                    
                    if min_dist < 100 and size:  # 100m tolerance
                        terminal_stub_sizes[closest_term_id] = size
                        terminals_data[closest_term_id]["stub_cable_size"] = size
                        stub_matched_count += 1
    
    print(f"  Matched {stub_matched_count}/{len(stub_features)} stub cables to MST terminals")
    
    # Analyze by terminal type and model
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    
    # Drop cable analysis by terminal type/model
    drop_by_type = defaultdict(list)
    drop_by_model = defaultdict(list)
    
    for term_id, term in terminals_data.items():
        drop_count = term["drop_cable_count"]
        if drop_count > 0:
            drop_by_type[term["type"]].append(drop_count)
            if term["model"]:
                drop_by_model[term["model"]].append(drop_count)
    
    print("\nDrop Cable Count per Terminal:")
    print(f"  {'Terminal Type/Model':<25} {'Count':<10} {'Min':<10} {'Max':<10} {'Mean':<10} {'Median':<10}")
    print("  " + "-" * 75)
    
    for term_type in sorted(drop_by_type.keys()):
        counts = drop_by_type[term_type]
        print(f"  {term_type:<25} {len(counts):<10} {min(counts):<10} {max(counts):<10} {sum(counts)/len(counts):<10.1f} {sorted(counts)[len(counts)//2]:<10}")
    
    for model in sorted(drop_by_model.keys()):
        counts = drop_by_model[model]
        print(f"  {model:<25} {len(counts):<10} {min(counts):<10} {max(counts):<10} {sum(counts)/len(counts):<10.1f} {sorted(counts)[len(counts)//2]:<10}")
    
    # Stub cable analysis by MST model
    stub_by_model = defaultdict(list)
    for term_id, term in terminals_data.items():
        if term["type"] == "MST" and term["stub_cable_size"]:
            stub_by_model[term["model"]].append(term["stub_cable_size"])
    
    print("\nStub Cable Size per MST Model:")
    print(f"  {'MST Model':<15} {'Count':<10} {'Stub Sizes':<30} {'Most Common':<15}")
    print("  " + "-" * 70)
    
    for model in sorted(stub_by_model.keys()):
        sizes = stub_by_model[model]
        size_counts = Counter(sizes)
        most_common = size_counts.most_common(1)[0] if size_counts else (None, 0)
        print(f"  {model:<15} {len(sizes):<10} {str(dict(size_counts)):<30} {str(most_common[0])+'F' if most_common[0] else 'N/A':<15}")
    
    # Port limit analysis (infer from max drop cables)
    print("\nInferred Port Limits (from max drop cables):")
    port_limits = {}
    for model in sorted(drop_by_model.keys()):
        max_drops = max(drop_by_model[model])
        port_limits[model] = max_drops
        print(f"  {model}: {max_drops} ports (max {max_drops} drop cables observed)")
    
    # Save learned patterns
    learned_patterns = {
        "drop_cable_limits": {
            "by_type": {k: {
                "min": min(v),
                "max": max(v),
                "mean": sum(v)/len(v),
                "median": sorted(v)[len(v)//2],
                "count": len(v)
            } for k, v in drop_by_type.items()},
            "by_model": {k: {
                "min": min(v),
                "max": max(v),
                "mean": sum(v)/len(v),
                "median": sorted(v)[len(v)//2],
                "count": len(v)
            } for k, v in drop_by_model.items()}
        },
        "stub_cable_sizes": {
            "by_model": {k: {
                "sizes": dict(Counter(v)),
                "most_common": Counter(v).most_common(1)[0][0] if v else None,
                "count": len(v)
            } for k, v in stub_by_model.items()}
        },
        "inferred_port_limits": port_limits
    }
    
    with open("terminal_cable_patterns.json", "w") as f:
        json.dump(learned_patterns, f, indent=2)
    
    print("\n" + "=" * 80)
    print("LEARNING COMPLETE")
    print("=" * 80)
    print("  ✓ Saved learned patterns to terminal_cable_patterns.json")
    print()
    
    return learned_patterns

if __name__ == "__main__":
    learn_terminal_cable_patterns()

