#!/usr/bin/env python3
"""
generate_design.py
-------------------------------------------------------------------------------
Main design generation engine that applies all rules to create network design.

Input:
  - ONT.geojson (Point features)
  - fiber cable.geojson (MultiLineString, NO SIZE specified)

Output:
  - All design layers (GeoJSON with sizes)
  - BOM (JSON + text)
  - Design validation report
-------------------------------------------------------------------------------
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add utils to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_loader import load_config
from utils.geojson_utils import load_geojson, save_geojson, create_feature_collection, extract_points, extract_linestrings

def generate_design(ont_geojson_path: str,
                   fiber_cable_geojson_path: str,
                   config_path: str = "design_config.json",
                   output_dir: str = "output") -> Dict[str, Any]:
    """
    Main entry point for design generation.
    
    Args:
        ont_geojson_path: Path to ONT GeoJSON file
        fiber_cable_geojson_path: Path to fiber cable GeoJSON file
        config_path: Path to configuration file
        output_dir: Output directory for generated files
        
    Returns:
        Dictionary with design results and metadata
    """
    print("=" * 80)
    print("FIBER NETWORK DESIGN ENGINE")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    # Load configuration
    print("Loading configuration...")
    config = load_config(config_path)
    print(f"  ✓ Configuration loaded from {config_path}")
    print()
    
    # Load input data
    print("Loading input data...")
    ont_geojson = load_geojson(ont_geojson_path)
    fiber_cable_geojson = load_geojson(fiber_cable_geojson_path)
    
    ont_count = len(ont_geojson.get("features", []))
    cable_count = len(fiber_cable_geojson.get("features", []))
    
    print(f"  ✓ Loaded {ont_count} ONTs from {ont_geojson_path}")
    print(f"  ✓ Loaded {cable_count} fiber cable segments from {fiber_cable_geojson_path}")
    print()
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize design state
    design_state = {
        "config": config,
        "onts": ont_geojson,
        "fiber_cables": fiber_cable_geojson,
        "community_pockets": [],
        "olts": [],
        "fdhs": [],
        "foscs": [],
        "terminals": [],
        "drop_cables": [],
        "stub_cables": [],
        "sized_cables": None,
        "bom": None
    }
    
    # Phase 0: Create Community Pockets
    print("Phase 0: Create Community Pockets...")
    try:
        from phases.phase0_community_pockets import create_community_pockets
        community_pockets = create_community_pockets(
            ont_geojson,
            fiber_cable_geojson,
            config
        )
        design_state["community_pockets"] = community_pockets
        print(f"  ✓ Created {len(community_pockets)} community pockets")
    except ImportError as e:
        print(f"  ⏳ Phase 0 not yet implemented: {e}")
        community_pockets = []
    except Exception as e:
        print(f"  ❌ Error in Phase 0: {e}")
        import traceback
        traceback.print_exc()
        community_pockets = []
    print()
    
    # Phase 1: Place OLTs
    print("Phase 1: Place OLTs...")
    try:
        from phases.phase1_place_olts import place_olts, generate_olt_geojson
        
        if not community_pockets:
            print("  ⚠️  No community pockets available, skipping OLT placement")
            olts = []
            olt_summary = {}
        else:
            olts, olt_summary = place_olts(
                community_pockets,
                fiber_cable_geojson,
                ont_geojson,
                config
            )
            design_state["olts"] = olts
            
            # Generate OLT GeoJSON
            olt_geojson = generate_olt_geojson(olts)
            olt_output_path = os.path.join(output_dir, "OLT.geojson")
            save_geojson(olt_geojson, olt_output_path)
            print(f"  ✓ Saved OLT GeoJSON to {olt_output_path}")
            
            # Save OLT summary
            olt_summary_path = os.path.join(output_dir, "olt_placement_summary.json")
            with open(olt_summary_path, "w") as f:
                json.dump({
                    "summary": olt_summary,
                    "olts": olts
                }, f, indent=2)
            print(f"  ✓ Saved OLT summary to {olt_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 1 not yet implemented: {e}")
        olts = []
        olt_summary = {}
    except Exception as e:
        print(f"  ❌ Error in Phase 1: {e}")
        import traceback
        traceback.print_exc()
        olts = []
        olt_summary = {}
    print()
    
    # Initialize FOSCs as empty list (will be populated in Phase 2 after terminals)
    foscs = []
    
    # Initialize terminals as empty list
    terminals = []
    
    # Phase 3: Place Terminals and FOSCs (Independent - no Phase 2)
    print("Phase 3: Place Terminals and FOSCs...")
    try:
        from phases.phase3_place_terminals import place_terminals, generate_terminal_geojson
        
        terminals, foscs, phase3_summary = place_terminals(
            ont_geojson,
            fiber_cable_geojson,
            olts,
            config
        )
        
        # Phase 3b: Refine MST placement (fix design issues)
        try:
            from phases.phase3b_refine_mst_placement import refine_mst_placement
            print("Phase 3b: Refining MST placement...")
            refined_terminals, refined_foscs, new_msts, phase3b_summary = refine_mst_placement(
                terminals,
                foscs,
                ont_geojson,
                fiber_cable_geojson,
                config
            )
            terminals = refined_terminals
            foscs = refined_foscs
            print(f"  ✓ Refined {len(terminals)} terminals and {len(foscs)} FOSCs")
        except ImportError as e:
            print(f"  ⏳ Phase 3b not available: {e}")
        except Exception as e:
            print(f"  ⚠️  Phase 3b error: {e}")
            import traceback
            traceback.print_exc()
        
        design_state["terminals"] = terminals
        
        # Generate Terminal GeoJSON
        terminal_geojson = generate_terminal_geojson(terminals)
        terminal_output_path = os.path.join(output_dir, "terminal.geojson")
        save_geojson(terminal_geojson, terminal_output_path)
        print(f"  ✓ Saved Terminal GeoJSON to {terminal_output_path}")
        
        # Save terminal summary
        terminal_summary_path = os.path.join(output_dir, "terminal_placement_summary.json")
        with open(terminal_summary_path, "w") as f:
            json.dump({
                "summary": terminal_summary,
                "terminals": terminals
            }, f, indent=2)
        print(f"  ✓ Saved terminal summary to {terminal_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 3 not yet implemented: {e}")
        terminals = []
        terminal_summary = {}
    except Exception as e:
        print(f"  ❌ Error in Phase 3: {e}")
        import traceback
        traceback.print_exc()
        terminals = []
        terminal_summary = {}
    print()
    
    # Phase 2: Place FOSCs (Refined - Geometry + Terminal-Based) - MOVED AFTER TERMINALS
    print("Phase 2: Place FOSCs (Refined - Geometry + Terminal-Based)...")
    try:
        from phases.phase2_place_foscs import place_foscs_initial, generate_fosc_geojson
        
        # FOSCs now placed after terminals, using terminal locations for refinement
        # Use terminals from design_state if available, otherwise use local variable
        terminals_for_fosc = design_state.get("terminals", terminals) if "terminals" in design_state else terminals
        foscs, fosc_summary = place_foscs_initial(
            design_state["fiber_cables"],
            terminals_for_fosc,  # Pass terminals for refined placement (from Phase 3)
            config
        )
        design_state["foscs"] = foscs
        
        # Generate FOSC GeoJSON
        fosc_geojson = generate_fosc_geojson(foscs)
        fosc_output_path = os.path.join(output_dir, "splice closure.geojson")
        save_geojson(fosc_geojson, fosc_output_path)
        print(f"  ✓ Saved FOSC GeoJSON to {fosc_output_path}")
        
        # Save FOSC summary
        fosc_summary_path = os.path.join(output_dir, "fosc_placement_summary.json")
        with open(fosc_summary_path, "w") as f:
            json.dump({
                "summary": fosc_summary,
                "foscs": foscs
            }, f, indent=2)
        print(f"  ✓ Saved FOSC summary to {fosc_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 2 not yet implemented: {e}")
        foscs = []
        fosc_summary = {}
    except Exception as e:
        print(f"  ❌ Error in Phase 2: {e}")
        import traceback
        traceback.print_exc()
        foscs = []
        fosc_summary = {}
    print()
    
    # Phase 5: Create Cable Extensions (Drop & Stub)
    print("Phase 5: Create Drop and Stub Cables...")
    try:
        from phases.phase5_drop_cables import (
            create_drop_cables, create_stub_cables,
            generate_drop_cable_geojson, generate_stub_cable_geojson
        )
        
        # Create drop cables (Terminal → ONT)
        drop_cables, drop_summary = create_drop_cables(
            design_state.get("terminals", []),
            ont_geojson,
            config
        )
        design_state["drop_cables"] = drop_cables
        
        # Create stub cables (MST → FOSC)
        stub_cables, stub_summary = create_stub_cables(
            design_state.get("terminals", []),
            design_state.get("foscs", []),
            config
        )
        design_state["stub_cables"] = stub_cables
        
        # Generate GeoJSON
        drop_cable_geojson = generate_drop_cable_geojson(drop_cables)
        drop_output_path = os.path.join(output_dir, "drop cable.geojson")
        save_geojson(drop_cable_geojson, drop_output_path)
        print(f"  ✓ Saved drop cable GeoJSON to {drop_output_path}")
        
        stub_cable_geojson = generate_stub_cable_geojson(stub_cables)
        stub_output_path = os.path.join(output_dir, "stub cable.geojson")
        save_geojson(stub_cable_geojson, stub_output_path)
        print(f"  ✓ Saved stub cable GeoJSON to {stub_output_path}")
        
        # Save summary
        cable_summary_path = os.path.join(output_dir, "cable_extensions_summary.json")
        with open(cable_summary_path, "w") as f:
            json.dump({
                "drop_cables": drop_summary,
                "stub_cables": stub_summary
            }, f, indent=2)
        print(f"  ✓ Saved cable extensions summary to {cable_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 5 not yet implemented: {e}")
        drop_cables = []
        stub_cables = []
    except Exception as e:
        print(f"  ❌ Error in Phase 5: {e}")
        import traceback
        traceback.print_exc()
        drop_cables = []
        stub_cables = []
    print()
    
    # Phase 6: Cable Sizing & ID Allocation
    print("Phase 6: Cable Sizing & ID Allocation...")
    try:
        from phases.phase6_cable_sizing import size_cables, generate_sized_cable_geojson
        
        # Get FOSCs and terminals from design_state (placed in Phase 3)
        # Phase 3 returns: (terminals, foscs, summary)
        # Phase 6 uses both for aggregation and cable ID assignment
        foscs_for_sizing = design_state.get("foscs", foscs) if "foscs" in design_state else foscs
        terminals_for_sizing = design_state.get("terminals", terminals) if "terminals" in design_state else terminals
        
        sized_cables, sizing_summary = size_cables(
            fiber_cable_geojson,
            foscs_for_sizing,  # FOSCs from Phase 3 (675 at 3+ cable junctions)
            terminals_for_sizing,  # Terminals from Phase 3 (8,108 total)
            olts,
            ont_geojson,
            config
        )
        design_state["sized_cables"] = sized_cables
        
        # Generate sized cable GeoJSON
        sized_cable_geojson = generate_sized_cable_geojson(sized_cables)
        cable_output_path = os.path.join(output_dir, "fiber cable.geojson")
        save_geojson(sized_cable_geojson, cable_output_path)
        print(f"  ✓ Saved sized cable GeoJSON to {cable_output_path}")
        
        # Save sizing summary
        sizing_summary_path = os.path.join(output_dir, "cable_sizing_summary.json")
        with open(sizing_summary_path, "w") as f:
            json.dump({
                "summary": sizing_summary,
                "sized_cables": sized_cables
            }, f, indent=2)
        print(f"  ✓ Saved cable sizing summary to {sizing_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 6 not yet implemented: {e}")
        sized_cables = []
        sizing_summary = {}
    except Exception as e:
        print(f"  ❌ Error in Phase 6: {e}")
        import traceback
        traceback.print_exc()
        sized_cables = []
        sizing_summary = {}
    print()
    
    # Phase 7: BOM Generation
    print("Phase 7: BOM Generation...")
    # TODO: Implement phase7_bom_generation
    print("  ⏳ Phase 7 not yet implemented")
    print()
    
    # Advanced: Infrastructure Cable Extensions (Placeholder)
    # TODO: Future optimization - extend infrastructure cables to improve service
    
    # Export results
    print("Exporting results...")
    # TODO: Export all layers
    print("  ⏳ Export not yet implemented")
    print()
    
    print("=" * 80)
    print("DESIGN GENERATION COMPLETE")
    print("=" * 80)
    print(f"Finished: {datetime.now().isoformat()}")
    print(f"Output directory: {output_dir}")
    
    return {
        "status": "success",
        "design_state": design_state,
        "output_dir": output_dir
    }

def main():
    """Main entry point for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate fiber network design")
    parser.add_argument("--onts", required=True, help="Path to ONT GeoJSON file")
    parser.add_argument("--cables", required=True, help="Path to fiber cable GeoJSON file")
    parser.add_argument("--config", default="design_config.json", help="Path to configuration file")
    parser.add_argument("--output", default="output", help="Output directory")
    
    args = parser.parse_args()
    
    try:
        result = generate_design(
            ont_geojson_path=args.onts,
            fiber_cable_geojson_path=args.cables,
            config_path=args.config,
            output_dir=args.output
        )
        print(f"\n✅ Design generation completed successfully!")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

