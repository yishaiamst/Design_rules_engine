#!/usr/bin/env python3
"""
Test Phase 6: Cable Sizing
"""

import json
import os
from utils.geojson_utils import load_geojson, save_geojson
from utils.config_loader import load_config
from phases.phase1_place_olts import place_olts
from phases.phase0_community_pockets import create_community_pockets
from phases.phase2_place_foscs import place_foscs_initial
from phases.phase3_place_terminals import place_terminals
from phases.phase6_cable_sizing import size_cables, generate_sized_cable_geojson

def main():
    print("=" * 80)
    print("TESTING PHASE 6: CABLE SIZING")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    print()
    
    # Run previous phases to get required inputs
    print("Running previous phases...")
    print()
    
    # Phase 0: Community Pockets
    print("Phase 0: Community Pockets...")
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    print(f"  ✓ Created {len(pockets)} pockets")
    print()
    
    # Phase 1: OLT Placement
    print("Phase 1: OLT Placement...")
    olts, olt_summary = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
    print(f"  ✓ Placed {len(olts)} OLTs")
    print()
    
    # Phase 3: Terminal and FOSC Placement (Independent - no Phase 2)
    print("Phase 3: Terminal and FOSC Placement...")
    terminals, foscs, phase3_summary = place_terminals(
        ont_geojson,
        fiber_cable_geojson,
        olts,
        config
    )
    print(f"  ✓ Placed {len(terminals)} terminals")
    print()
    
    # Phase 6: Cable Sizing
    print("=" * 80)
    print("PHASE 6: CABLE SIZING")
    print("=" * 80)
    print()
    
    sized_cables, sizing_summary = size_cables(
        fiber_cable_geojson,
        foscs,
        terminals,
        olts,
        ont_geojson,
        config
    )
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    print("Cable Sizing Summary:")
    print(f"  Total cables: {sizing_summary.get('total_cables', len(sized_cables))}")
    print(f"  Size distribution: {sizing_summary.get('size_distribution', {})}")
    print(f"  FOSC aggregations: {sizing_summary.get('fosc_aggregations', 0)}")
    print(f"  Max size limit: {sizing_summary.get('max_size', 288)}F")
    print(f"  Default override: {sizing_summary.get('default_size_override', 'None')}")
    print()
    
    # Save results
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate and save sized cable GeoJSON
    sized_cable_geojson = generate_sized_cable_geojson(sized_cables)
    output_path = os.path.join(output_dir, "fiber cable.geojson")
    save_geojson(sized_cable_geojson, output_path)
    print(f"✓ Saved sized cable GeoJSON to {output_path}")
    
    # Save summary
    summary_path = os.path.join(output_dir, "phase6_sizing_summary.json")
    with open(summary_path, "w") as f:
        json.dump({
            "summary": sizing_summary,
            "cable_count": len(sized_cables),
            "cables_sample": sized_cables[:10]  # First 10 as sample
        }, f, indent=2, default=str)
    print(f"✓ Saved summary to {summary_path}")
    print()
    
    print("=" * 80)
    print("PHASE 6 COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()

