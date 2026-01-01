#!/usr/bin/env python3
"""
Check what FOSCs and terminals Phase 6 is receiving
"""

from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals

def main():
    print("=" * 80)
    print("CHECKING PHASE 6 INPUTS (FOSCs and Terminals)")
    print("=" * 80)
    print()
    
    # Load data
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Run pipeline
    print("Running pipeline...")
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
    
    # Phase 2: FOSC Placement
    print("\n" + "=" * 80)
    print("PHASE 2: FOSC PLACEMENT")
    print("=" * 80)
    foscs, fosc_summary = place_foscs_initial(
        fiber_cable_geojson,
        terminals=None,
        config=config
    )
    print(f"\nPhase 2 Output:")
    print(f"  - FOSCs placed: {len(foscs)}")
    print(f"  - FOSC summary: {fosc_summary}")
    print()
    
    # Phase 3: Terminal Placement
    print("=" * 80)
    print("PHASE 3: TERMINAL PLACEMENT")
    print("=" * 80)
    terminals, terminal_summary = place_terminals(
        ont_geojson,
        fiber_cable_geojson,
        olts,
        foscs,  # Uses FOSCs from Phase 2
        config
    )
    print(f"\nPhase 3 Output:")
    print(f"  - Terminals placed: {len(terminals)}")
    print(f"  - Terminal summary: {terminal_summary}")
    print()
    
    # Check what Phase 6 receives
    print("=" * 80)
    print("WHAT PHASE 6 RECEIVES")
    print("=" * 80)
    print()
    print("Phase 6 receives:")
    print(f"  - FOSCs: {len(foscs)} (from Phase 2)")
    print(f"  - Terminals: {len(terminals)} (from Phase 3)")
    print()
    
    # Check FOSC sources
    print("FOSC Breakdown:")
    fosc_sources = {}
    for fosc in foscs:
        trigger = fosc.get("trigger", "unknown")
        fosc_sources[trigger] = fosc_sources.get(trigger, 0) + 1
    
    for source, count in fosc_sources.items():
        print(f"  - {source}: {count}")
    print()
    
    # Check if Phase 3 modifies FOSCs
    print("Phase 3 Analysis:")
    print("  - Phase 3 receives FOSCs from Phase 2")
    print("  - Phase 3 returns ONLY terminals (not FOSCs)")
    print("  - Phase 3 found 2,993 2-cable junctions (using geometric detection)")
    print("  - Phase 2 found 0 junctions (using topology-based detection)")
    print()
    
    print("=" * 80)
    print("ISSUE IDENTIFIED")
    print("=" * 80)
    print()
    print("Problem:")
    print("  - Phase 2 uses topology-based detection → finds 0 junctions")
    print("  - Phase 3 uses geometric detection → finds 2,993 junctions")
    print("  - Phase 6 uses FOSCs from Phase 2 (0 junction FOSCs)")
    print("  - Phase 6 should use FOSCs at junctions for aggregation")
    print()
    print("Solution:")
    print("  - Phase 2 should use the same geometric detection as Phase 3")
    print("  - OR Phase 6 should use junction information from Phase 3")
    print()

if __name__ == "__main__":
    main()

