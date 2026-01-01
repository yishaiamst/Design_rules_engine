#!/usr/bin/env python3
"""
Test Phase 3 Terminal Placement
"""

import json
import os
from utils.geojson_utils import load_geojson, save_geojson
from utils.config_loader import load_config
from phases.phase2_place_foscs import place_foscs_initial
from phases.phase3_place_terminals import place_terminals, generate_terminal_geojson

def main():
    print("=" * 80)
    print("TESTING PHASE 3: TERMINAL PLACEMENT")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Load or create OLTs (Phase 1)
    # For now, use empty list - Phase 3 will handle it
    olts = []
    
    # Run Phase 2 to get FOSCs
    print()
    print("Running Phase 2: FOSC Placement...")
    print()
    foscs, fosc_summary = place_foscs_initial(
        fiber_cable_geojson,
        terminals=None,
        config=config
    )
    
    print()
    print("=" * 80)
    print("RUNNING PHASE 3: TERMINAL PLACEMENT")
    print("=" * 80)
    print()
    
    # Run Phase 3
    terminals, terminal_summary = place_terminals(
        ont_geojson,
        fiber_cable_geojson,
        olts,
        foscs,
        config
    )
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    print("Terminal Placement Summary:")
    print(f"  Total terminals: {terminal_summary.get('total_terminals', len(terminals))}")
    print(f"  At 2-cable junctions: {terminal_summary.get('terminals_at_2cable_junctions', 0)}")
    print(f"  Aerial terminals: {terminal_summary.get('aerial_terminals', 0)}")
    print(f"  MSTs: {terminal_summary.get('msts', 0)}")
    print(f"  ONTs served: {terminal_summary.get('onts_served', 0)}")
    print()
    
    # Save results
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate and save terminal GeoJSON
    terminal_geojson = generate_terminal_geojson(terminals)
    output_path = os.path.join(output_dir, "terminal.geojson")
    save_geojson(terminal_geojson, output_path)
    print(f"✓ Saved terminal GeoJSON to {output_path}")
    
    # Save summary
    summary_path = os.path.join(output_dir, "phase3_terminal_summary.json")
    with open(summary_path, "w") as f:
        json.dump({
            "summary": terminal_summary,
            "terminal_count": len(terminals),
            "fosc_summary": fosc_summary,
            "terminals_sample": terminals[:10]  # First 10 as sample
        }, f, indent=2, default=str)
    print(f"✓ Saved summary to {summary_path}")
    print()
    
    print("=" * 80)
    print("PHASE 3 COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

