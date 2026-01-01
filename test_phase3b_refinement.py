#!/usr/bin/env python3
"""
Test Phase 3b: MST Placement Refinement
Tests the fixes for the 4 design issues identified by the user.
"""

import json
from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from utils.timeout_utils import timeout, Timer, TimeoutError
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from phases.phase3b_refine_mst_placement import refine_mst_placement


def main():
    try:
        with timeout(600):  # 10 minutes
            print("=" * 80)
            print("TESTING PHASE 3B: MST PLACEMENT REFINEMENT")
            print("=" * 80)
            print()
            
            # Load data
            with Timer("Loading data"):
                ont_geojson = load_geojson("ONT.geojson")
                fiber_cable_geojson = load_geojson("fiber cable.geojson")
                config = load_config("design_config.json")
            
            # Run pipeline up to Phase 3
            with Timer("Phase 0: Community Pockets"):
                pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
            
            with Timer("Phase 1: Place OLTs"):
                olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
            
            with Timer("Phase 3: Place Terminals and FOSCs"):
                terminals, foscs, phase3_summary = place_terminals(
                    ont_geojson, fiber_cable_geojson, olts, config
                )
            
            print()
            print("BEFORE REFINEMENT:")
            print(f"  Total terminals: {len(terminals)}")
            msts_before = [t for t in terminals if t.get("type") == "MST"]
            aerial_before = [t for t in terminals if t.get("type") == "Aerial Terminal"]
            print(f"  MSTs: {len(msts_before)}")
            print(f"  Aerial Terminals: {len(aerial_before)}")
            
            # Check MST placement
            msts_on_cable = 0
            msts_standalone = 0
            for mst in msts_before:
                dist = mst.get("distance_to_cable_m", float('inf'))
                if dist < 1.0:
                    msts_on_cable += 1
                else:
                    msts_standalone += 1
            
            print(f"  MSTs on cable: {msts_on_cable}")
            print(f"  MSTs standalone: {msts_standalone}")
            
            # Check overloaded terminals
            overloaded = [t for t in terminals if len(t.get("connected_onts", [])) > 12]
            print(f"  Overloaded terminals (>12 ONTs): {len(overloaded)}")
            
            # Run Phase 3b
            with Timer("Phase 3b: Refine MST Placement"):
                refined_terminals, refined_foscs, new_msts, phase3b_summary = refine_mst_placement(
                    terminals,
                    foscs,
                    ont_geojson,
                    fiber_cable_geojson,
                    config
                )
            
            print()
            print("AFTER REFINEMENT:")
            print(f"  Total terminals: {len(refined_terminals)}")
            msts_after = [t for t in refined_terminals if t.get("type") == "MST"]
            aerial_after = [t for t in refined_terminals if t.get("type") == "Aerial Terminal"]
            print(f"  MSTs: {len(msts_after)}")
            print(f"  Aerial Terminals: {len(aerial_after)}")
            
            # Check MST placement after
            msts_on_cable_after = 0
            msts_standalone_after = 0
            for mst in msts_after:
                dist = mst.get("distance_to_cable_m", float('inf'))
                if dist < 1.0:
                    msts_on_cable_after += 1
                else:
                    msts_standalone_after += 1
            
            print(f"  MSTs on cable: {msts_on_cable_after}")
            print(f"  MSTs standalone: {msts_standalone_after}")
            
            # Check overloaded terminals after
            overloaded_after = [t for t in refined_terminals if len(t.get("connected_onts", [])) > 12]
            print(f"  Overloaded terminals (>12 ONTs): {len(overloaded_after)}")
            
            print()
            print("REFINEMENT SUMMARY:")
            print(json.dumps(phase3b_summary, indent=2, default=str))
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
