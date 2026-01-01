#!/usr/bin/env python3
"""
Simple test for Phase 6: Cable Sizing
Tests with minimal setup
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from phases.phase6_cable_sizing import size_cables, generate_sized_cable_geojson

def main():
    print("=" * 80)
    print("TESTING PHASE 6: CABLE SIZING (Simple)")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # For testing, use empty lists for phases we haven't run
    # In real usage, these would come from previous phases
    olts = []  # Will be empty for this test
    foscs = []  # Will be empty for this test
    terminals = []  # Will be empty for this test
    
    print()
    print("=" * 80)
    print("PHASE 6: CABLE SIZING")
    print("=" * 80)
    print()
    
    # Test 1: Default size override
    print("Test 1: Default size override (96F)...")
    config_test = config.copy()
    config_test["cables"]["infrastructure_cable"]["default_size_override"] = 96
    
    sized_cables, sizing_summary = size_cables(
        fiber_cable_geojson,
        foscs,
        terminals,
        olts,
        ont_geojson,
        config_test
    )
    
    print()
    print(f"  Result: {len(sized_cables)} cables sized")
    print(f"  Size distribution: {sizing_summary.get('size_distribution', {})}")
    print(f"  Method: {sizing_summary.get('sizing_method', 'unknown')}")
    print()
    
    # Test 2: Formula-based (no override)
    print("Test 2: Formula-based sizing (no override)...")
    config_test2 = config.copy()
    config_test2["cables"]["infrastructure_cable"]["default_size_override"] = None
    
    sized_cables2, sizing_summary2 = size_cables(
        fiber_cable_geojson,
        foscs,
        terminals,
        olts,
        ont_geojson,
        config_test2
    )
    
    print()
    print(f"  Result: {len(sized_cables2)} cables sized")
    print(f"  Size distribution: {sizing_summary2.get('size_distribution', {})}")
    print(f"  FOSC aggregations: {sizing_summary2.get('fosc_aggregations', 0)}")
    print()
    
    print("=" * 80)
    print("PHASE 6 TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

