#!/usr/bin/env python3
"""
Test graph-based cable sizing approach
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.timeout_utils import timeout, Timer, TimeoutError
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from phases.phase6_cable_sizing import size_cables

def main():
    try:
        with timeout(600):  # 10 minutes
            print("=" * 80)
            print("TESTING GRAPH-BASED CABLE SIZING")
            print("=" * 80)
            print()
            
            # Load data
            with Timer("Loading data"):
                ont_geojson = load_geojson("ONT.geojson")
                fiber_cable_geojson = load_geojson("fiber cable.geojson")
                config = load_config("design_config.json")
            
            # Run pipeline
            with Timer("Phase 0: Community Pockets"):
                pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
            
            with Timer("Phase 1: Place OLTs"):
                olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
            
            with Timer("Phase 3: Place Terminals and FOSCs"):
                terminals, foscs, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, config)
            
            with Timer("Phase 6: Size Cables (Graph-Based)"):
                sized_cables, sizing_summary = size_cables(
                    fiber_cable_geojson,
                    foscs,
                    terminals,
                    olts,
                    ont_geojson,
                    config
                )
            
            # Print summary
            print()
            print("=" * 80)
            print("RESULTS")
            print("=" * 80)
            print()
            print(f"Total cables sized: {len(sized_cables)}")
            print(f"Sizing summary: {json.dumps(sizing_summary, indent=2, default=str)}")
            print()
            
            # Size distribution
            from collections import Counter
            size_dist = Counter(c.get("fiber_count", 0) for c in sized_cables)
            print("Size Distribution:")
            for size, count in sorted(size_dist.items()):
                print(f"  {size}F: {count:,} cables")
            print()
            
            # Cables with paths
            cables_with_paths = sum(1 for c in sized_cables if c.get("downstream_onts", 0) > 0)
            print(f"Cables with ONT paths: {cables_with_paths:,} / {len(sized_cables):,}")
            print()
    
    except TimeoutError:
        print()
        print("=" * 80)
        print("TIMEOUT: Test exceeded 10 minute limit")
        print("=" * 80)
    except Exception as e:
        print()
        print("=" * 80)
        print(f"ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
