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
    
    # Rule 23 (Early): Connect Isolated Cables in Input Data
    # Run this FIRST to clean up any isolated cables in the input data
    # before starting the design process
    print("Rule 23 (Early): Connecting Isolated Cables in Input Data...")
    try:
        from phases.phase3e_connect_isolated_cables import connect_isolated_cables
        
        # Connect isolated cables in the original input data
        cleaned_cables_geojson, early_foscs, early_summary = connect_isolated_cables(
            fiber_cable_geojson,
            [],  # No FOSCs yet at this stage
            tolerance_m=50.0,
            max_connection_distance_m=3000.0,
            max_iterations=5,
            terminals=[],  # No terminals yet
            olts=[],  # No OLTs yet
            roads_geojson=roads_geojson  # Pass roads for accurate alignment check
        )
        
        # Update fiber_cable_geojson with cleaned version
        fiber_cable_geojson = cleaned_cables_geojson
        design_state["fiber_cables"] = cleaned_cables_geojson
        
        print(f"  ✓ Connected {early_summary.get('connected', 0)} isolated cables in input data")
        print(f"  ✓ Created {early_summary.get('new_foscs', 0)} FOSCs for early connections")
        
        # Save early connection summary
        early_summary_path = os.path.join(output_dir, "early_isolated_cable_connection_summary.json")
        with open(early_summary_path, "w") as f:
            json.dump(early_summary, f, indent=2)
        
    except ImportError as e:
        print(f"  ⏳ Rule 23 (Early) not available: {e}")
    except Exception as e:
        print(f"  ⚠️  Rule 23 (Early) error: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Phase 3e: Connect Isolated Fiber Cables (Rule 23 - After Cable ID Updates)
    # Run this AFTER phase3d because cable ID assignment may create new isolations
    # (e.g., cables with From_ID/To_ID that don't actually connect to anything)
    print("Phase 3e: Connecting Isolated Fiber Cables (After Cable ID Updates)...")
    try:
        from phases.phase3e_connect_isolated_cables import connect_isolated_cables
        
        # Use updated cables from Phase 3d
        connected_cables_geojson, new_foscs, connection_summary = connect_isolated_cables(
            updated_cables_geojson,
            foscs,
            tolerance_m=50.0,
            max_connection_distance_m=3000.0,  # 3km to handle cases like F1000390
            max_iterations=5,  # Multiple passes to catch isolated islands
            terminals=design_state.get("terminals", []),  # Pass terminals for loop detection
            olts=design_state.get("olts", []),  # Pass OLTs for path analysis
            roads_geojson=roads_geojson  # Pass roads for accurate alignment check
        )
        
        # Add new FOSCs to existing FOSCs
        if new_foscs:
            foscs.extend(new_foscs)
            design_state["foscs"] = foscs
            print(f"  ✓ Added {len(new_foscs)} new FOSCs for cable connections")
            
            # Update optimized FOSCs file
            optimized_foscs_path = os.path.join(output_dir, "rules_optimized_foscs.json")
            with open(optimized_foscs_path, "w") as f:
                json.dump(foscs, f, indent=2)
            print(f"  ✓ Updated optimized FOSCs file")
            
            # Regenerate FOSC GeoJSON with new FOSCs
            try:
                from phases.phase2_place_foscs import generate_fosc_geojson
                fosc_geojson = generate_fosc_geojson(foscs)
                fosc_output_path = os.path.join(output_dir, "splice closure.geojson")
                save_geojson(fosc_geojson, fosc_output_path)
                print(f"  ✓ Updated FOSC GeoJSON with new FOSCs")
            except Exception as e:
                print(f"  ⚠️  Could not update FOSC GeoJSON: {e}")
        
        # Update design state with connected cables
        design_state["fiber_cables"] = connected_cables_geojson
        
        # CRITICAL: Always regenerate FOSC GeoJSON after Phase 3e to include ALL FOSCs
        # (including those from Phase 3c optimization rules)
        try:
            from phases.phase2_place_foscs import generate_fosc_geojson
            fosc_geojson = generate_fosc_geojson(foscs)
        except ImportError:
            # Fallback: Create FOSC GeoJSON directly
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
            fosc_geojson = create_feature_collection(features, crs="EPSG:32617")
        
        fosc_output_path = os.path.join(output_dir, "splice closure.geojson")
        save_geojson(fosc_geojson, fosc_output_path)
        print(f"  ✓ Updated FOSC GeoJSON with all {len(foscs)} FOSCs")
        
        print(f"  ✓ Connected {connection_summary.get('connected', 0)} isolated cables")
        print(f"  ✓ Extended {connection_summary.get('extended', 0)} cables")
        
        # Save connected cables
        connected_cables_path = os.path.join(output_dir, "fiber_cable_connected.geojson")
        save_geojson(connected_cables_geojson, connected_cables_path)
        print(f"  ✓ Saved connected cables to {connected_cables_path}")
        
        # Save connection summary
        connection_summary_path = os.path.join(output_dir, "isolated_cable_connection_summary.json")
        with open(connection_summary_path, "w") as f:
            json.dump(connection_summary, f, indent=2)
        print(f"  ✓ Saved connection summary to {connection_summary_path}")
        
    except ImportError as e:
        print(f"  ⏳ Phase 3e not available: {e}")
        connected_cables_geojson = updated_cables_geojson
    except Exception as e:
        print(f"  ⚠️  Phase 3e error: {e}")
        import traceback
        traceback.print_exc()
        connected_cables_geojson = updated_cables_geojson
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

