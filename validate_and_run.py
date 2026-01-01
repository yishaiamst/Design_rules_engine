#!/usr/bin/env python3
"""
Validation and test runner for build_fiber_graph.py
Checks for required files and runs the graph builder.
"""

import os
import json
import glob

REQUIRED_FILES = [
    "ONT.geojson",
    "terminal.geojson",
    "stub cable.geojson",
    "splice closure.geojson",
    "fdh.geojson",
    "OLT.geojson",
    "fiber cable.geojson",
    "drop cable.geojson"
]

def check_files():
    """Check if all required files exist."""
    print("Checking for required GeoJSON files...")
    missing = []
    found = []
    
    for filename in REQUIRED_FILES:
        # Try exact match first
        if os.path.exists(filename):
            found.append(filename)
            print(f"  ✓ Found: {filename}")
        else:
            # Try case-insensitive search
            matches = glob.glob(filename.lower()) + glob.glob(filename.upper())
            if matches:
                found.append(matches[0])
                print(f"  ✓ Found: {matches[0]} (case variation)")
            else:
                missing.append(filename)
                print(f"  ✗ Missing: {filename}")
    
    print(f"\nStatus: {len(found)}/{len(REQUIRED_FILES)} files found")
    
    if missing:
        print(f"\n⚠ Missing files: {', '.join(missing)}")
        return False
    
    return True

def validate_outputs():
    """Validate the output JSON files."""
    print("\n" + "="*60)
    print("Validating output files...")
    print("="*60)
    
    outputs = [
        "logical_fiber_graph.json",
        "olt_ont_paths.json",
        "summary_metrics.json"
    ]
    
    for filename in outputs:
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if filename == "logical_fiber_graph.json":
                    nodes = len(data.get("nodes", []))
                    links = len(data.get("links", []))
                    print(f"✓ {filename}: {nodes} nodes, {links} links")
                
                elif filename == "olt_ont_paths.json":
                    paths = len(data) if isinstance(data, list) else 0
                    print(f"✓ {filename}: {paths} ONT paths")
                
                elif filename == "summary_metrics.json":
                    avg = data.get("average_total_cable_length_per_ont_m", 0)
                    max_len = data.get("max_chain_length_m", 0)
                    print(f"✓ {filename}: avg={avg}m, max={max_len}m")
                    print(f"  FOSC per OLT: {len(data.get('fosc_count_per_olt', {}))} OLTs")
                    print(f"  FOSC per FDH: {len(data.get('fosc_count_per_fdh', {}))} FDHs")
                
            except json.JSONDecodeError as e:
                print(f"✗ {filename}: Invalid JSON - {e}")
            except Exception as e:
                print(f"✗ {filename}: Error - {e}")
        else:
            print(f"✗ {filename}: Not found")

if __name__ == "__main__":
    if check_files():
        print("\n" + "="*60)
        print("Running build_fiber_graph.py...")
        print("="*60 + "\n")
        
        import build_fiber_graph
        
        print("\n" + "="*60)
        validate_outputs()
        print("="*60)
    else:
        print("\n⚠ Please ensure all required files are in the current directory.")
        print("Current directory:", os.getcwd())







