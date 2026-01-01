#!/usr/bin/env python3
"""
Analyze drop cable and terminal patterns from actual design.
"""

import json
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any
from utils.geojson_utils import load_geojson

def analyze_drop_cables():
    """Analyze drop cable patterns."""
    print("=" * 80)
    print("DROP CABLE ANALYSIS")
    print("=" * 80)
    print()
    
    print("Loading drop cables...")
    drop_cables = load_geojson("drop cable.geojson")
    
    drop_cable_count = len(drop_cables.get("features", []))
    print(f"  Loaded {drop_cable_count} drop cables")
    
    # Analyze drop cable properties
    sizes = Counter()
    lengths = []
    
    for feat in drop_cables.get("features", []):
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # Extract size
        size = props.get("Size") or props.get("FiberCount") or props.get("size")
        if size:
            if isinstance(size, str):
                size = int(size.replace("F", "")) if size.replace("F", "").isdigit() else None
            sizes[size] += 1
        
        # Calculate length
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            # Handle both LineString and MultiLineString
            coord_list = coords
            if geometry.get("type") == "MultiLineString":
                coord_list = []
                for line in coords:
                    coord_list.extend(line)
            
            # Simple length calculation (Euclidean)
            total_length = 0
            for i in range(len(coord_list) - 1):
                p1 = coord_list[i]
                p2 = coord_list[i+1]
                # Handle nested coordinates
                if isinstance(p1, list) and len(p1) >= 2:
                    x1, y1 = p1[0], p1[1]
                else:
                    continue
                if isinstance(p2, list) and len(p2) >= 2:
                    x2, y2 = p2[0], p2[1]
                else:
                    continue
                length = ((x2-x1)**2 + (y2-y1)**2)**0.5
                total_length += length
            if total_length > 0:
                lengths.append(total_length)
    
    print("\nDrop Cable Size Distribution:")
    for size in sorted(sizes.keys()):
        print(f"  {size}F: {sizes[size]} cables")
    
    if lengths:
        print(f"\nDrop Cable Length Statistics:")
        print(f"  Count: {len(lengths)}")
        print(f"  Min: {min(lengths):.1f}m")
        print(f"  Max: {max(lengths):.1f}m")
        print(f"  Average: {sum(lengths)/len(lengths):.1f}m")
        print(f"  Median: {sorted(lengths)[len(lengths)//2]:.1f}m")
    
    return {
        "count": drop_cable_count,
        "sizes": dict(sizes),
        "lengths": lengths
    }

def analyze_terminals():
    """Analyze terminal patterns."""
    print("\n" + "=" * 80)
    print("TERMINAL ANALYSIS")
    print("=" * 80)
    print()
    
    print("Loading terminals...")
    terminals = load_geojson("terminal.geojson")
    
    terminal_count = len(terminals.get("features", []))
    print(f"  Loaded {terminal_count} terminals")
    
    # Analyze terminal types
    types = Counter()
    ports = Counter()
    
    for feat in terminals.get("features", []):
        props = feat.get("properties", {})
        
        # Extract type
        terminal_type = props.get("Type") or props.get("type") or props.get("TerminalType")
        if terminal_type:
            types[terminal_type] += 1
        
        # Extract ports
        port_count = props.get("Ports") or props.get("ports") or props.get("PortCount")
        if port_count:
            ports[port_count] += 1
    
    print("\nTerminal Type Distribution:")
    for ttype in sorted(types.keys()):
        print(f"  {ttype}: {types[ttype]} terminals")
    
    print("\nTerminal Port Distribution:")
    for port in sorted(ports.keys()):
        print(f"  {port} ports: {ports[port]} terminals")
    
    return {
        "count": terminal_count,
        "types": dict(types),
        "ports": dict(ports)
    }

def analyze_ont_terminal_connections():
    """Analyze how ONTs connect to terminals via drop cables."""
    print("\n" + "=" * 80)
    print("ONT-TERMINAL CONNECTION ANALYSIS")
    print("=" * 80)
    print()
    
    # Load ONTs
    print("Loading ONTs...")
    onts = load_geojson("ONT.geojson")
    ont_count = len(onts.get("features", []))
    print(f"  Loaded {ont_count} ONTs")
    
    # Load terminals
    terminals = load_geojson("terminal.geojson")
    terminal_features = terminals.get("features", [])
    
    # Build terminal position map
    terminal_positions = {}
    for feat in terminal_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        terminal_id = props.get("ID") or props.get("id", "")
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            terminal_positions[terminal_id] = (coords[0], coords[1])
    
    # Load drop cables
    drop_cables = load_geojson("drop cable.geojson")
    drop_features = drop_cables.get("features", [])
    
    # Analyze connections
    ont_to_terminal = {}
    terminal_to_onts = defaultdict(list)
    
    for feat in drop_features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # Try to extract FROM and TO from properties or ID
        from_id = props.get("From") or props.get("from_id") or props.get("FromID")
        to_id = props.get("To") or props.get("to_id") or props.get("ToID")
        
        # Or try to extract from ID field
        cable_id = props.get("ID") or props.get("id", "")
        if not from_id or not to_id:
            # Try parsing ID (might be in format like "DROP/ONT123/TERM456")
            if "/" in cable_id:
                parts = cable_id.split("/")
                if len(parts) >= 3:
                    from_id = parts[1]
                    to_id = parts[2]
        
        coords = geometry.get("coordinates", [])
        if coords and len(coords) >= 2:
            start = coords[0]
            end = coords[-1]
            
            # Match to terminal (closest endpoint to terminal)
            if from_id or to_id:
                # Simple heuristic: assume one end is terminal, one is ONT
                # We'll need to match by proximity
                pass
    
    print(f"  Analyzed {len(drop_features)} drop cables")
    print(f"  Found {len(terminal_to_onts)} terminals with ONT connections")
    
    # Count ONTs per terminal
    ont_counts = [len(onts) for onts in terminal_to_onts.values()]
    if ont_counts:
        print(f"\nONTs per Terminal Statistics:")
        print(f"  Min: {min(ont_counts)}")
        print(f"  Max: {max(ont_counts)}")
        print(f"  Average: {sum(ont_counts)/len(ont_counts):.1f}")
        print(f"  Median: {sorted(ont_counts)[len(ont_counts)//2]}")
    
    return {
        "ont_to_terminal": ont_to_terminal,
        "terminal_to_onts": dict(terminal_to_onts)
    }

def main():
    """Main analysis."""
    drop_analysis = analyze_drop_cables()
    terminal_analysis = analyze_terminals()
    connection_analysis = analyze_ont_terminal_connections()
    
    # Save results
    results = {
        "drop_cables": drop_analysis,
        "terminals": terminal_analysis,
        "connections": connection_analysis
    }
    
    with open("drop_cable_terminal_analysis.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n" + "=" * 80)
    print("RESULTS SAVED")
    print("=" * 80)
    print("  ✓ Saved drop_cable_terminal_analysis.json")
    print()

if __name__ == "__main__":
    main()

