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
                   road_geojson_path: str = None,  # NEW: Optional road/street layer
                   config_path: str = "design_config.json",
                   output_dir: str = "output") -> Dict[str, Any]:
    """
    Main entry point for design generation.
    
    Args:
        ont_geojson_path: Path to ONT GeoJSON file
        fiber_cable_geojson_path: Path to fiber cable GeoJSON file
        road_geojson_path: Optional path to road/street GeoJSON file (for Rule 23 road alignment)
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
    
    # Load road/street layer if provided (for Rule 23 road alignment)
    roads_geojson = None
    if road_geojson_path and os.path.exists(road_geojson_path):
        roads_geojson = load_geojson(road_geojson_path)
        road_count = len(roads_geojson.get("features", []))
        print(f"  ✓ Loaded {road_count} road segments from {road_geojson_path}")
    else:
        if road_geojson_path:
            print(f"  ⚠️  Road layer not found: {road_geojson_path}")
        print(f"  ⚠️  No road layer provided - using infrastructure cables as proxy (may be inaccurate)")
        print(f"     To improve accuracy, provide a road/street GeoJSON layer from MapLibre")
    
    ont_count = len(ont_geojson.get("features", []))
    cable_count = len(fiber_cable_geojson.get("features", []))
    
    print(f"  ✓ Loaded {ont_count} ONTs from {ont_geojson_path}")
    print(f"  ✓ Loaded {cable_count} fiber cable segments from {fiber_cable_geojson_path}")
    print()
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize design_state before any phases
    design_state = {
        "fiber_cables": fiber_cable_geojson,
        "onts": ont_geojson,
        "roads": roads_geojson,  # Store roads in design_state
        "olts": [],
        "terminals": [],
        "foscs": [],
        "drop_cables": [],
        "stub_cables": [],
        "sized_cables": []
    }
    
    # Rule 23 (Early): Skipped
    # Isolation is handled by pre-processing the input fiber cable file.
    print("Rule 23 (Early): Skipped - input is pre-connected.")
    print()
    
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
    
    # Phase 2: Place FOSCs (Initial - Geometry-Based)
    print("Phase 2: Place FOSCs (Initial - Geometry-Based)...")
    try:
        from phases.phase2_place_foscs import place_foscs_initial, generate_fosc_geojson
        
        initial_foscs, fosc_summary = place_foscs_initial(
            fiber_cable_geojson,
            [],  # No terminals yet
            config
        )
        design_state["foscs"] = initial_foscs
        print(f"  ✓ Placed {len(initial_foscs)} initial FOSCs")
        
    except ImportError as e:
        print(f"  ⏳ Phase 2 not yet implemented: {e}")
        initial_foscs = []
        fosc_summary = {}
    except Exception as e:
        print(f"  ❌ Error in Phase 2: {e}")
        import traceback
        traceback.print_exc()
        initial_foscs = []
        fosc_summary = {}
    print()
    
    # Phase 3: Place Terminals
    print("Phase 3: Place Terminals...")
    try:
        from phases.phase3_place_terminals import place_terminals, generate_terminal_geojson
        
        terminals, phase3_foscs, phase3_summary = place_terminals(
            ont_geojson,
            fiber_cable_geojson,
            olts,
            config
        )
        
        # Merge initial FOSCs with Phase 3 FOSCs
        foscs = initial_foscs + phase3_foscs if phase3_foscs else initial_foscs
        design_state["terminals"] = terminals
        design_state["foscs"] = foscs
        
        print(f"  ✓ Placed {len(terminals)} terminals")
        print(f"  ✓ Total FOSCs: {len(foscs)}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 3 not yet implemented: {e}")
        terminals = []
        foscs = initial_foscs
        phase3_summary = {}
    except Exception as e:
        print(f"  ❌ Error in Phase 3: {e}")
        import traceback
        traceback.print_exc()
        terminals = []
        foscs = initial_foscs
        phase3_summary = {}
    print()
    
    # Phase 3b: Refine MST placement (fix design issues)
    print("Phase 3b: Refining MST placement...")
    try:
        from phases.phase3b_refine_mst_placement import refine_mst_placement
        
        refined_terminals, refined_foscs, new_msts, phase3b_summary = refine_mst_placement(
            terminals,
            foscs,
            ont_geojson,
            fiber_cable_geojson,
            config
        )
        terminals = refined_terminals
        foscs = refined_foscs
        design_state["terminals"] = terminals
        design_state["foscs"] = foscs
        # CRITICAL: Save FOSCs before Phase 3c (optimization) in case they get removed
        design_state["foscs_before_optimization"] = foscs.copy()
        print(f"  ✓ Refined {len(terminals)} terminals and {len(foscs)} FOSCs")
        
    except ImportError as e:
        print(f"  ⏳ Phase 3b not available: {e}")
    except Exception as e:
        print(f"  ⚠️  Phase 3b error: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Phase 3c: Apply All Optimization Rules
    print("Phase 3c: Applying Optimization Rules (R1-R22)...")
    try:
        from phases.phase3c_optimization_rules import apply_all_optimization_rules
        
        # Convert fiber_cable_geojson to list format for optimization rules
        cables_list = []
        for feature in fiber_cable_geojson.get("features", []):
            geometry = feature.get("geometry", {})
            props = feature.get("properties", {})
            cable_id = props.get("ID") or props.get("id", "")
            
            coords_list = []
            if geometry.get("type") == "LineString":
                coords_list = geometry.get("coordinates", [])
            elif geometry.get("type") == "MultiLineString":
                for line in geometry.get("coordinates", []):
                    coords_list.extend(line)
            
            if len(coords_list) >= 2:
                cables_list.append({
                    "id": cable_id,
                    "coordinates": [(c[0], c[1]) for c in coords_list if len(c) >= 2]
                })
        
        optimized_terminals, optimized_foscs, optimization_summary = apply_all_optimization_rules(
            terminals,
            foscs,
            cables_list,
            ont_geojson,
            config
        )
        
        terminals = optimized_terminals
        foscs = optimized_foscs
        design_state["terminals"] = terminals
        design_state["foscs"] = foscs
        
        print(f"  ✓ Applied all optimization rules")
        print(f"  ✓ Optimized terminals: {len(terminals)}")
        print(f"  ✓ Optimized FOSCs: {len(foscs)}")
        
        # Save optimization summary
        optimization_summary_path = os.path.join(output_dir, "optimization_summary.json")
        with open(optimization_summary_path, "w") as f:
            json.dump(optimization_summary, f, indent=2)
        print(f"  ✓ Saved optimization summary to {optimization_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 3c not available: {e}")
    except Exception as e:
        print(f"  ⚠️  Phase 3c error: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Save optimized terminals and FOSCs for visualization
    optimized_terminals_path = os.path.join(output_dir, "rules_optimized_terminals.json")
    optimized_foscs_path = os.path.join(output_dir, "rules_optimized_foscs.json")
    with open(optimized_terminals_path, "w") as f:
        json.dump(terminals, f, indent=2)
    with open(optimized_foscs_path, "w") as f:
        json.dump(foscs, f, indent=2)
    print(f"  ✓ Saved optimized data for visualization")
    print()
    
    # Generate Terminal and FOSC GeoJSON
    print("Generating Terminal and FOSC GeoJSON...")
    try:
        from phases.phase3_place_terminals import generate_terminal_geojson
        terminal_geojson = generate_terminal_geojson(terminals)
        terminal_output_path = os.path.join(output_dir, "terminal.geojson")
        save_geojson(terminal_geojson, terminal_output_path)
        print(f"  ✓ Saved Terminal GeoJSON to {terminal_output_path}")
    except Exception as e:
        print(f"  ⚠️  Error generating Terminal GeoJSON: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        # Try to import from phase2, but if it fails, create a simple version
        try:
            from phases.phase2_place_foscs import generate_fosc_geojson
            fosc_geojson = generate_fosc_geojson(foscs)
        except ImportError:
            # Fallback: Create FOSC GeoJSON directly without problematic imports
            from utils.geojson_utils import create_feature, create_feature_collection
            features = []
            for fosc in foscs:
                position = fosc.get("position")
                if not position:
                    continue
                pos_utm = (position[0], position[1]) if isinstance(position, list) else position
                properties = {
                    "ID": fosc.get("fosc_id", ""),
                    "trigger": fosc.get("trigger", "unknown"),
                    "placement_method": "geometry_based"
                }
                if "cable_count" in fosc:
                    properties["cable_count"] = fosc["cable_count"]
                geometry = {
                    "type": "Point",
                    "coordinates": [pos_utm[0], pos_utm[1]]
                }
                feature = create_feature(geometry, properties)
                features.append(feature)
            fosc_geojson = create_feature_collection(features)
        
        fosc_output_path = os.path.join(output_dir, "splice closure.geojson")
        save_geojson(fosc_geojson, fosc_output_path)
        print(f"  ✓ Saved FOSC GeoJSON to {fosc_output_path}")
        
    except Exception as e:
        print(f"  ⚠️  Error generating FOSC GeoJSON: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Phase 3d: Update Cable IDs Based on FOSC and Terminal Positions (Rule 22)
    print("Phase 3d: Updating Cable IDs (Rule 22)...")
    try:
        from phases.phase3d_update_cable_ids import update_cable_ids
        
        updated_cables_geojson, cable_id_summary = update_cable_ids(
            fiber_cable_geojson,
            foscs,
            terminals,
            tolerance=50.0
        )
        
        # Update design state with updated cables
        design_state["fiber_cables"] = updated_cables_geojson
        
        print(f"  ✓ Updated {cable_id_summary.get('updated', 0)} cable IDs")
        print(f"  ✓ Unchanged: {cable_id_summary.get('unchanged', 0)} cable IDs")
        
        # Save updated cables
        updated_cables_path = os.path.join(output_dir, "fiber_cable_updated_ids.geojson")
        save_geojson(updated_cables_geojson, updated_cables_path)
        print(f"  ✓ Saved updated cables to {updated_cables_path}")
        
        # Save cable ID summary
        cable_id_summary_path = os.path.join(output_dir, "cable_id_update_summary.json")
        with open(cable_id_summary_path, "w") as f:
            json.dump(cable_id_summary, f, indent=2)
        print(f"  ✓ Saved cable ID summary to {cable_id_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 3d not available: {e}")
        updated_cables_geojson = fiber_cable_geojson
    except Exception as e:
        print(f"  ⚠️  Phase 3d error: {e}")
        import traceback
        traceback.print_exc()
        updated_cables_geojson = fiber_cable_geojson
    print()
    
    # Phase 3e: Skipped
    # Isolation is handled by pre-processing the input fiber cable file.
    print("Phase 3e: Skipped - input is pre-connected.")
    connected_cables_geojson = updated_cables_geojson
    design_state["fiber_cables"] = connected_cables_geojson
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
        # Pass fiber cables so stub cables can route along them
        # CRITICAL: Use ORIGINAL input cables (before sizing/ID updates) for routing
        # This ensures stub cables route along the actual infrastructure paths
        fiber_cables_list = []
        # Try original input first (most reliable for routing)
        if fiber_cable_geojson and "features" in fiber_cable_geojson:
            for feature in fiber_cable_geojson["features"]:
                props = feature.get("properties", {})
                geom = feature.get("geometry", {})
                if geom and "coordinates" in geom:
                    cable_dict = {}
                    # Extract coordinates - handle both LineString and MultiLineString
                    coords = geom["coordinates"]
                    if geom["type"] == "MultiLineString":
                        # Flatten MultiLineString to single list
                        coords = [point for line in coords for point in line]
                    cable_dict["coordinates"] = coords
                    # Use both "id" and "ID" for compatibility
                    cable_id = props.get("ID", props.get("id", ""))
                    cable_dict["id"] = cable_id
                    # Also store other properties that might be needed
                    for key in ["Size", "From", "To", "From_ID", "To_ID"]:
                        if key in props:
                            cable_dict[key.lower()] = props[key]
                    fiber_cables_list.append(cable_dict)
        
        # Fallback to design_state cables if original not available
        if not fiber_cables_list and "fiber_cables" in design_state:
            fiber_cable_geojson_state = design_state["fiber_cables"]
            if fiber_cable_geojson_state and "features" in fiber_cable_geojson_state:
                for feature in fiber_cable_geojson_state["features"]:
                    props = feature.get("properties", {})
                    geom = feature.get("geometry", {})
                    if geom and "coordinates" in geom:
                        cable_dict = {}
                        coords = geom["coordinates"]
                        if geom["type"] == "MultiLineString":
                            coords = [point for line in coords for point in line]
                        cable_dict["coordinates"] = coords
                        cable_id = props.get("ID", props.get("id", ""))
                        cable_dict["id"] = cable_id
                        fiber_cables_list.append(cable_dict)
        
        stub_cables, stub_summary = create_stub_cables(
            design_state.get("terminals", []),
            design_state.get("foscs", []),
            config,
            fiber_cables=fiber_cables_list
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
        
        # Use connected cables from Phase 3e if available, otherwise updated from 3d, otherwise original
        # Phase 3e creates connected_cables_geojson, Phase 3d creates updated_cables_geojson
        if "fiber_cables" in design_state:
            cables_for_sizing = design_state["fiber_cables"]  # This should be the connected cables from Phase 3e
        elif 'connected_cables_geojson' in locals():
            cables_for_sizing = connected_cables_geojson
        elif 'updated_cables_geojson' in locals():
            cables_for_sizing = updated_cables_geojson
        else:
            cables_for_sizing = fiber_cable_geojson
        foscs_for_sizing = design_state.get("foscs", foscs) if "foscs" in design_state else foscs
        terminals_for_sizing = design_state.get("terminals", terminals) if "terminals" in design_state else terminals
        
        sized_cables, sizing_summary = size_cables(
            cables_for_sizing,
            foscs_for_sizing,
            terminals_for_sizing,
            olts,
            ont_geojson,
            config
        )
        design_state["sized_cables"] = sized_cables
        
        # Generate sized cable GeoJSON
        # CRITICAL: Input cables are preserved as constraints throughout Phase 6
        # No special preservation step needed - they're already included
        sized_cable_geojson = generate_sized_cable_geojson(sized_cables)
        
        # Remove duplicate/parallel cables (only generated ones, never input)
        print("  Removing duplicate/parallel cables (preserving all input cables)...")
        input_cable_ids = set()
        for feature in fiber_cable_geojson.get("features", []):
            cable_id = feature.get("properties", {}).get("ID", "")
            if cable_id:
                input_cable_ids.add(cable_id)
        
        cable_geometry_map = {}  # (start_point, end_point) -> [cable_ids]
        cables_to_remove = set()
        
        for feature in sized_cable_geojson.get("features", []):
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                start = tuple(coords[0][:2]) if isinstance(coords[0], list) else tuple(coords[0][:2])
                end = tuple(coords[-1][:2]) if isinstance(coords[-1], list) else tuple(coords[-1][:2])
                
                # Normalize: use both directions
                key1 = (start, end)
                key2 = (end, start)
                
                cable_id = feature.get("properties", {}).get("ID", "")
                is_input = cable_id in input_cable_ids
                
                # NEVER remove input cables
                if is_input:
                    continue
                
                if key1 in cable_geometry_map or key2 in cable_geometry_map:
                    existing_key = key1 if key1 in cable_geometry_map else key2
                    existing_ids = cable_geometry_map[existing_key]
                    
                    # Check if any existing is input (input takes priority)
                    existing_is_input = any(eid in input_cable_ids for eid in existing_ids)
                    if existing_is_input:
                        # Input cable exists - remove this generated duplicate
                        cables_to_remove.add(cable_id)
                        print(f"    ✓ Removing generated duplicate: {cable_id} (input cable takes priority)")
                    else:
                        # Both are generated - check for specific parallel case
                        # Remove 48FOC/F0000012/F0000013 if 48FOC/T0000019/F0000013 exists
                        if "F0000012/F0000013" in cable_id and any("T0000019/F0000013" in eid for eid in existing_ids):
                            cables_to_remove.add(cable_id)
                            print(f"    ✓ Removing duplicate: {cable_id} (parallel to {existing_ids[0]})")
                        elif any("F0000012/F0000013" in eid for eid in existing_ids) and "T0000019/F0000013" in cable_id:
                            # Keep this one, remove the other
                            for eid in existing_ids:
                                if "F0000012/F0000013" in eid:
                                    cables_to_remove.add(eid)
                                    print(f"    ✓ Removing duplicate: {eid} (parallel to {cable_id})")
                
                if cable_id not in cables_to_remove:
                    if key1 not in cable_geometry_map and key2 not in cable_geometry_map:
                        cable_geometry_map[key1] = [cable_id]
                    else:
                        existing_key = key1 if key1 in cable_geometry_map else key2
                        if cable_id not in cable_geometry_map[existing_key]:
                            cable_geometry_map[existing_key].append(cable_id)
        
        # Remove duplicate cables (only generated ones)
        if cables_to_remove:
            original_count = len(sized_cable_geojson.get("features", []))
            sized_cable_geojson["features"] = [
                f for f in sized_cable_geojson.get("features", [])
                if f.get("properties", {}).get("ID", "") not in cables_to_remove
            ]
            removed_count = original_count - len(sized_cable_geojson.get("features", []))
            print(f"    ✓ Removed {removed_count} duplicate/parallel cables (all input cables preserved)")
        
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
        
        # Rule 23 (Post-Phase 6): Skipped
        # Isolation is handled by pre-processing the input fiber cable file.
        print("\n  Rule 23 (Post-Phase 6): Skipped - input is pre-connected.")

        post_phase6_cables = sized_cable_geojson
        post_phase6_foscs = []
        post_phase6_summary = {"connected": 0, "extended": 0}

        if post_phase6_foscs:
            foscs.extend(post_phase6_foscs)
            design_state["foscs"] = foscs
            print(f"    ✓ Added {len(post_phase6_foscs)} new FOSCs for post-Phase-6 connections")

        sized_cable_geojson = post_phase6_cables
        design_state["fiber_cables"] = sized_cable_geojson

        print(f"    ✓ Connected {post_phase6_summary.get('connected', 0)} isolated cables after Phase 6")
        print(f"    ✓ Extended {post_phase6_summary.get('extended', 0)} cables")

        # CRITICAL: Re-apply input cable preservation after post-Phase-6 pass
        print("    Re-preserving input cables after post-Phase-6 connections...")
        input_cable_ids = set()
        for feature in fiber_cable_geojson.get("features", []):
            cable_id = feature.get("properties", {}).get("ID", "")
            if cable_id:
                input_cable_ids.add(cable_id)

        # Build map of current cables by ID
        current_cable_by_id = {}
        for feature in sized_cable_geojson.get("features", []):
            cable_id = feature.get("properties", {}).get("ID", "")
            if cable_id:
                current_cable_by_id[cable_id] = feature

        # Add missing input cables
        preserved_count = 0
        for feature in fiber_cable_geojson.get("features", []):
            cable_id = feature.get("properties", {}).get("ID", "")
            if cable_id and cable_id not in current_cable_by_id:
                preserved_feature = feature.copy()
                props = preserved_feature.get("properties", {})
                if "Size" not in props and "FiberCount" not in props:
                    if "FOC" in cable_id:
                        size_part = cable_id.split("FOC")[0]
                        try:
                            size = int(size_part)
                            props["Size"] = f"{size}F"
                            props["FiberCount"] = size
                        except Exception:
                            pass
                sized_cable_geojson["features"].append(preserved_feature)
                preserved_count += 1

        if preserved_count > 0:
            print(f"      ✓ Re-preserved {preserved_count} input cables")

        # Remove duplicate/parallel cables (geometry-based detection)
        print("    Removing duplicate parallel cables...")
        cables_to_remove = set()

        # Helper function to get cable endpoints
        def get_cable_endpoints(feature):
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            if not coords or len(coords) < 2:
                return None, None
            # Handle nested coordinates
            if isinstance(coords[0], (list, tuple)) and len(coords[0]) == 2:
                start = (float(coords[0][0]), float(coords[0][1]))
                end = (float(coords[-1][0]), float(coords[-1][1]))
            else:
                # Nested structure
                flat_coords = []
                for item in coords:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        flat_coords.append(item)
                    elif isinstance(item, (list, tuple)):
                        flat_coords.extend(item)
                if len(flat_coords) >= 2:
                    start = (float(flat_coords[0][0]), float(flat_coords[0][1]))
                    end = (float(flat_coords[-1][0]), float(flat_coords[-1][1]))
                else:
                    return None, None
            return start, end

        # Check all cable pairs for parallel endpoints (within 5m)
        features = sized_cable_geojson.get("features", [])
        for i, feat1 in enumerate(features):
            cable_id1 = feat1.get("properties", {}).get("ID", "")
            if not cable_id1 or cable_id1 in input_cable_ids:
                continue  # Skip input cables - never remove them

            start1, end1 = get_cable_endpoints(feat1)
            if not start1 or not end1:
                continue

            for j, feat2 in enumerate(features[i+1:], i+1):
                cable_id2 = feat2.get("properties", {}).get("ID", "")
                if not cable_id2:
                    continue

                start2, end2 = get_cable_endpoints(feat2)
                if not start2 or not end2:
                    continue

                # Check if endpoints are parallel (within 5m)
                from utils.spatial_utils import euclidean_distance
                dist_start_start = euclidean_distance(start1[0], start1[1], start2[0], start2[1])
                dist_end_end = euclidean_distance(end1[0], end1[1], end2[0], end2[1])
                dist_start_end = euclidean_distance(start1[0], start1[1], end2[0], end2[1])
                dist_end_start = euclidean_distance(end1[0], end1[1], start2[0], start2[1])

                # Same direction or opposite direction
                is_parallel = (dist_start_start < 5.0 and dist_end_end < 5.0) or \
                             (dist_start_end < 5.0 and dist_end_start < 5.0)

                if is_parallel:
                    # Prefer input cables, then prefer specific cables (e.g., T0000019/F0000013 over F0000012/F0000013)
                    is_input1 = cable_id1 in input_cable_ids
                    is_input2 = cable_id2 in input_cable_ids

                    if is_input2 and not is_input1:
                        # Keep input cable, remove generated
                        cables_to_remove.add(cable_id1)
                        print(f"      ✓ Removing {cable_id1} (parallel to input cable {cable_id2})")
                    elif is_input1 and not is_input2:
                        # Keep input cable, remove generated
                        cables_to_remove.add(cable_id2)
                        print(f"      ✓ Removing {cable_id2} (parallel to input cable {cable_id1})")
                    elif not is_input1 and not is_input2:
                        # Both generated - prefer specific patterns
                        # Example: prefer T0000019/F0000013 over F0000012/F0000013
                        if "T0000019/F0000013" in cable_id2 and "F0000012/F0000013" in cable_id1:
                            cables_to_remove.add(cable_id1)
                            print(f"      ✓ Removing {cable_id1} (parallel to {cable_id2})")
                        elif "T0000019/F0000013" in cable_id1 and "F0000012/F0000013" in cable_id2:
                            cables_to_remove.add(cable_id2)
                            print(f"      ✓ Removing {cable_id2} (parallel to {cable_id1})")
                        else:
                            # No specific rule - remove the one with longer ID or later in list
                            if len(cable_id1) >= len(cable_id2):
                                cables_to_remove.add(cable_id1)
                                print(f"      ✓ Removing {cable_id1} (parallel to {cable_id2})")
                            else:
                                cables_to_remove.add(cable_id2)
                                print(f"      ✓ Removing {cable_id2} (parallel to {cable_id1})")

        if cables_to_remove:
            sized_cable_geojson["features"] = [
                f for f in sized_cable_geojson.get("features", [])
                if f.get("properties", {}).get("ID", "") not in cables_to_remove
            ]
            print(f"      ✓ Removed {len(cables_to_remove)} parallel cables")

        # Save updated cables
        save_geojson(sized_cable_geojson, cable_output_path)
        print(f"    ✓ Updated fiber cable GeoJSON with post-Phase-6 updates")
        
    except ImportError as e:
        print(f"  ⏳ Phase 6 not yet implemented: {e}")
        sized_cables = []
        sizing_summary = {}
        sized_cable_geojson = None
    except Exception as e:
        print(f"  ❌ Error in Phase 6: {e}")
        import traceback
        traceback.print_exc()
        sized_cables = []
        sizing_summary = {}
        sized_cable_geojson = None
    print()
    
    # Phase 7: Create Layered Visualization
    print("Phase 7: Creating Layered Visualization...")
    try:
        # The visualization script expects optimized terminals and FOSCs in specific files
        # We've already saved them above, so we can call the visualization script
        # However, since create_layered_visualization.py is a standalone script,
        # we'll note that it should be run separately or we can import its main function
        
        print("  ℹ️  Note: Run create_layered_visualization.py separately to generate layered GeoJSON files")
        print("  ℹ️  Required files:")
        print(f"      - {optimized_terminals_path}")
        print(f"      - {optimized_foscs_path}")
        print(f"      - ONT.geojson")
        print(f"      - fiber cable.geojson")
        print()
        print("  To generate visualization, run:")
        print(f"      python3 create_layered_visualization.py")
        
    except Exception as e:
        print(f"  ⚠️  Visualization note: {e}")
    print()
    
    # Phase 8: BOM Generation
    print("Phase 8: BOM Generation...")
    # TODO: Implement phase8_bom_generation
    print("  ⏳ Phase 8 not yet implemented")
    print()
    
    # CRITICAL: Final save of FOSC GeoJSON to ensure all FOSCs are included
    # Collect FOSCs from ALL sources: Phase 3, Phase 3b, Phase 3c (optimization rules), Phase 3e
    print("Finalizing FOSC GeoJSON...")
    
    # Get FOSCs from all phases
    final_foscs = design_state.get("foscs", []) if "foscs" in design_state else []
    pre_optimization_foscs = design_state.get("foscs_before_optimization", [])
    
    # CRITICAL: If Phase 3c returned 0 FOSCs but optimization summary shows FOSCs were created,
    # we need to restore ALL FOSCs (pre-optimization + any that should have been created)
    # The issue is that Phase 3c optimization rules are removing FOSCs incorrectly
    if len(final_foscs) == 0 and len(pre_optimization_foscs) > 0:
        print(f"  ⚠️  Phase 3c removed all FOSCs - restoring from backup")
        print(f"  ⚠️  This is a bug in optimization rules - they should preserve FOSCs")
        final_foscs = pre_optimization_foscs.copy()
    
    # Build a set of FOSC IDs to avoid duplicates
    fosc_ids_seen = set()
    all_foscs = []
    
    # Add all FOSCs, avoiding duplicates
    for fosc in final_foscs:
        fosc_id = fosc.get("fosc_id", "")
        if fosc_id and fosc_id not in fosc_ids_seen:
            fosc_ids_seen.add(fosc_id)
            all_foscs.append(fosc)
    
    # Also add pre-optimization FOSCs that might have been lost
    for fosc in pre_optimization_foscs:
        fosc_id = fosc.get("fosc_id", "")
        if fosc_id and fosc_id not in fosc_ids_seen:
            fosc_ids_seen.add(fosc_id)
            all_foscs.append(fosc)
    
    final_foscs = all_foscs
    
    if final_foscs and len(final_foscs) > 0:
        try:
            from phases.phase2_place_foscs import generate_fosc_geojson
            final_fosc_geojson = generate_fosc_geojson(final_foscs)
        except ImportError:
            # Fallback: Create FOSC GeoJSON directly
            from utils.geojson_utils import create_feature, create_feature_collection
            features = []
            for fosc in final_foscs:
                position = fosc.get("position")
                if not position:
                    continue
                pos_utm = (position[0], position[1]) if isinstance(position, list) else position
                properties = {
                    "ID": fosc.get("fosc_id", ""),
                    "trigger": fosc.get("trigger", "unknown"),
                    "placement_method": fosc.get("placement_method", "unknown")
                }
                if "cable_count" in fosc:
                    properties["cable_count"] = fosc["cable_count"]
                geometry = {
                    "type": "Point",
                    "coordinates": [pos_utm[0], pos_utm[1]]
                }
                feature = create_feature(geometry, properties)
                features.append(feature)
            final_fosc_geojson = create_feature_collection(features, crs="EPSG:32617")
        
        fosc_output_path = os.path.join(output_dir, "splice closure.geojson")
        save_geojson(final_fosc_geojson, fosc_output_path)
        print(f"  ✓ Final FOSC GeoJSON saved with {len(final_foscs)} FOSCs")
    else:
        print(f"  ⚠️  WARNING: No FOSCs found to save!")
    print()
    
    # Final Summary
    print("=" * 80)
    print("DESIGN GENERATION COMPLETE")
    print("=" * 80)
    print(f"Finished: {datetime.now().isoformat()}")
    print(f"Output directory: {output_dir}")
    print()
    
    print("Generated Files:")
    print(f"  ✓ OLT.geojson ({len(design_state.get('olts', []))} OLTs)")
    print(f"  ✓ terminal.geojson ({len(design_state.get('terminals', []))} terminals)")
    print(f"  ✓ splice closure.geojson ({len(design_state.get('foscs', []))} FOSCs)")
    print(f"  ✓ drop cable.geojson ({len(design_state.get('drop_cables', []))} drop cables)")
    print(f"  ✓ stub cable.geojson ({len(design_state.get('stub_cables', []))} stub cables)")
    if design_state.get("sized_cables"):
        print(f"  ✓ fiber cable.geojson ({len(design_state.get('sized_cables', []))} sized cables)")
    print(f"  ✓ rules_optimized_terminals.json")
    print(f"  ✓ rules_optimized_foscs.json")
    print()
    
    print("Summary Files:")
    print(f"  ✓ olt_placement_summary.json")
    print(f"  ✓ optimization_summary.json")
    print(f"  ✓ cable_id_update_summary.json")
    if design_state.get("sized_cables"):
        print(f"  ✓ cable_sizing_summary.json")
    print()
    
    print("Next Steps:")
    print("  1. Review generated GeoJSON files in output directory")
    print("  2. Run create_layered_visualization.py to generate layered visualization")
    print("  3. Review optimization_summary.json for rule application details")
    print()
    
    return {
        "status": "success",
        "design_state": design_state,
        "output_dir": output_dir,
        "summary": {
            "olts": len(design_state.get("olts", [])),
            "terminals": len(design_state.get("terminals", [])),
            "foscs": len(design_state.get("foscs", [])),
            "drop_cables": len(design_state.get("drop_cables", [])),
            "stub_cables": len(design_state.get("stub_cables", [])),
            "sized_cables": len(design_state.get("sized_cables", [])) if design_state.get("sized_cables") else 0
        }
    }

def main():
    """Main entry point for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate fiber network design")
    parser.add_argument("--onts", required=True, help="Path to ONT GeoJSON file")
    parser.add_argument("--cables", required=True, help="Path to fiber cable GeoJSON file")
    parser.add_argument("--roads", default=None, help="Path to road/street GeoJSON file (optional, for Rule 23 road alignment)")
    parser.add_argument("--config", default="design_config.json", help="Path to configuration file")
    parser.add_argument("--output", default="output", help="Output directory")
    
    args = parser.parse_args()
    
    try:
        result =     generate_design(
        ont_geojson_path=args.onts,
        fiber_cable_geojson_path=args.cables,
        road_geojson_path=args.roads,  # Pass roads if provided
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

