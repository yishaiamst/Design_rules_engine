#!/usr/bin/env python3
"""
Phase 3b: Refine MST Placement and Fix Design Issues

Fixes based on user feedback:
1. MSTs must ALWAYS be placed ON the fiber cable (not standalone)
2. Detect terminal overload (>12 ONTs) and split into multiple MSTs from FOSC
3. Detect long drop cables and place MSTs near ONT clusters connected to FOSCs
4. If MST can't be placed on cable, use Aerial Terminal instead

COORDINATE SYSTEM: All calculations use UTM Zone 17N (EPSG:32617).
Coordinates are loaded as-is from GeoJSON files (already in UTM).
No coordinate transformation during calculations - only at visualization time.
"""

from typing import Dict, List, Any, Tuple
from collections import defaultdict
from utils.spatial_utils import euclidean_distance, point_to_line_distance, calculate_centroid
from utils.geojson_utils import create_feature, create_feature_collection


def find_nearest_point_on_cable(point: Tuple[float, float], cable: Dict[str, Any]) -> Tuple[Tuple[float, float], float]:
    """
    Find nearest point on cable to given point.
    Returns: (nearest_point, distance)
    """
    coords = cable.get("coordinates", [])
    if not coords or len(coords) < 2:
        return point, float('inf')
    
    min_dist = float('inf')
    nearest_point = coords[0]
    
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i + 1]
        
        # Project point onto line segment
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        px, py = point[0], point[1]
        
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            t = 0
        else:
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        proj_point = (proj_x, proj_y)
        
        dist = euclidean_distance(px, py, proj_x, proj_y)
        if dist < min_dist:
            min_dist = dist
            nearest_point = proj_point
    
    return nearest_point, min_dist

def find_point_on_cable_closest_to_target(cable: Dict[str, Any], target_point: Tuple[float, float]) -> Tuple[Tuple[float, float], float]:
    """
    Find the point on the cable that is closest to the target point.
    This is the same as find_nearest_point_on_cable but with a clearer name.
    """
    return find_nearest_point_on_cable(target_point, cable)


def validate_utm_coordinates(coords, name="coordinate"):
    """
    Validate that coordinates are in UTM Zone 17N (EPSG:32617).
    UTM Zone 17N range: easting ~300000-800000, northing ~4000000-6000000
    """
    if not coords or len(coords) < 2:
        return False
    
    x, y = coords[0], coords[1]
    # UTM Zone 17N bounds
    is_utm = (300000 <= x <= 800000) and (4000000 <= y <= 6000000)
    
    if not is_utm:
        print(f"  ⚠️  WARNING: {name} appears to NOT be in UTM Zone 17N: ({x:.2f}, {y:.2f})")
        print(f"     Expected range: X=300000-800000, Y=4000000-6000000")
    
    return is_utm


def refine_mst_placement(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    fiber_cable_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Refine terminal/MST placement to fix design issues:
    1. Ensure MSTs are ON the fiber cable
    2. Split overloaded terminals into multiple MSTs
    3. Add MSTs for long drop cables
    4. Replace standalone MSTs with Aerial Terminals
    
    Returns: (refined_terminals, new_msts, summary)
    """
    print("=" * 80)
    print("PHASE 3B: REFINING MST PLACEMENT")
    print("=" * 80)
    print()
    print("COORDINATE SYSTEM: UTM Zone 17N (EPSG:32617) - NO TRANSFORMATION")
    print()
    
    # Load cables
    cables = []
    cable_by_id = {}
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cable = {
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples
                }
                cables.append(cable)
                if cable["id"]:
                    cable_by_id[cable["id"]] = cable
    
    print(f"  Loaded {len(cables)} cables")
    
    # Load ONTs
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        # Handle different geometry types
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list and len(coords_list) > 0:
                coords = coords_list[0]  # Take first point
            else:
                coords = None
        
        if ont_id and coords and len(coords) >= 2:
            # Store as tuple for consistency, but ensure UTM
            ont_pos_utm = (float(coords[0]), float(coords[1]))
            # Validate first few ONTs
            if len(onts_by_id) < 5:
                validate_utm_coordinates(ont_pos_utm, f"ONT {ont_id}")
            onts_by_id[ont_id] = {
                "id": ont_id,
                "position": ont_pos_utm
            }
    
    print(f"  Loaded {len(onts_by_id)} ONTs (all in UTM Zone 17N)")
    
    # DEBUG: Check if T0000356's ONTs are loaded
    t0000356_onts = ['O1005647', 'O1005772', 'O1005971', 'O1005972', 'O1006044']
    found_onts = [ont_id for ont_id in t0000356_onts if ont_id in onts_by_id]
    if len(found_onts) < len(t0000356_onts):
        print(f"  ⚠️  Warning: Only {len(found_onts)}/{len(t0000356_onts)} T0000356 ONTs loaded")
        print(f"    Missing: {set(t0000356_onts) - set(found_onts)}")
    
    # Build FOSC position map
    # CRITICAL: Use FOSC positions as-is (UTM), no transformation
    fosc_by_id = {}
    fosc_positions = {}
    fosc_validation_errors = 0
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id") or fosc.get("id", "")
        fosc_pos = fosc.get("position")
        if fosc_id and fosc_pos:
            # Ensure position is a list/tuple with 2 elements
            if isinstance(fosc_pos, list) and len(fosc_pos) >= 2:
                fosc_pos_utm = [float(fosc_pos[0]), float(fosc_pos[1])]
            elif isinstance(fosc_pos, tuple) and len(fosc_pos) >= 2:
                fosc_pos_utm = [float(fosc_pos[0]), float(fosc_pos[1])]
            else:
                fosc_validation_errors += 1
                continue
            
            # Validate UTM coordinates
            if not validate_utm_coordinates(fosc_pos_utm, f"FOSC {fosc_id}"):
                fosc_validation_errors += 1
            
            fosc_by_id[fosc_id] = fosc
            fosc_positions[fosc_id] = fosc_pos_utm
    
    print(f"  Loaded {len(foscs)} FOSCs")
    if fosc_validation_errors > 0:
        print(f"  ⚠️  WARNING: {fosc_validation_errors} FOSCs had coordinate validation issues")
    
    # Get config
    mst_config = config.get("equipment", {}).get("mst", {})
    aerial_config = config.get("equipment", {}).get("aerial_terminal", {})
    max_onts_per_terminal = 12  # Standard port limit
    
    refined_terminals = []
    new_msts = []
    summary = {
        "msts_moved_to_cable": 0,
        "standalone_msts_replaced": 0,
        "overloaded_terminals_split": 0,
        "new_msts_added": 0,
        "long_drop_cables_fixed": 0,
        "foscs_moved_to_cable": 0
    }
    
    # Fix 0: Ensure FOSCs are ON the fiber cable
    print()
    print("  Fix 0: Ensuring FOSCs are placed ON the fiber cable...")
    foscs_fixed = []
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            foscs_fixed.append(fosc)
            continue
        
        # Find nearest point on any cable
        min_dist = float('inf')
        nearest_cable = None
        best_pos = fosc_pos
        
        for cable in cables:
            coords = cable.get("coordinates", [])
            if not coords:
                continue
            
            nearest_point, dist = find_nearest_point_on_cable(fosc_pos, cable)
            if dist < min_dist:
                min_dist = dist
                nearest_cable = cable
                best_pos = nearest_point
        
        # Move FOSC to nearest point on cable if not already on cable
        if min_dist > 1.0:  # Not on cable (more than 1m away)
            fosc["position"] = best_pos
            fosc["distance_to_cable_m"] = min_dist
            summary["foscs_moved_to_cable"] += 1
        
        foscs_fixed.append(fosc)
    
    foscs = foscs_fixed
    print(f"    Moved {summary['foscs_moved_to_cable']} FOSCs to cable")
    
    # Fix 1: Ensure MSTs are ON the fiber cable
    print()
    print("  Fix 1: Ensuring MSTs are placed ON the fiber cable...")
    for terminal in terminals:
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        connected_cable_id = terminal.get("connected_cable_id") or terminal.get("nearest_cable_id")
        
        if terminal_type == "MST" and terminal_pos:
            # Check if MST is on cable
            is_on_cable = False
            nearest_cable = None
            min_dist = float('inf')
            
            # Find nearest cable
            for cable in cables:
                coords = cable.get("coordinates", [])
                if not coords:
                    continue
                
                nearest_point, dist = find_nearest_point_on_cable(terminal_pos, cable)
                if dist < min_dist:
                    min_dist = dist
                    nearest_cable = cable
                    if dist < 1.0:  # Within 1m = on cable
                        is_on_cable = True
            
            if not is_on_cable:
                # CRITICAL: Both MSTs and Aerial Terminals MUST be on cable
                # Move to nearest point on cable (no exceptions)
                if nearest_cable:
                    new_pos, _ = find_nearest_point_on_cable(terminal_pos, nearest_cable)
                    terminal["position"] = new_pos
                    terminal["connected_cable_id"] = nearest_cable.get("id", "")
                    terminal["distance_to_cable_m"] = 0.0
                    summary["msts_moved_to_cable"] += 1
                else:
                    # No cable found - this is a serious error, but try to find any cable
                    print(f"    ⚠️  Warning: Terminal {terminal.get('terminal_id')} has no nearby cable, searching all cables...")
                    # Search all cables (slower but necessary)
                    for cable in cables:
                        coords = cable.get("coordinates", [])
                        if not coords:
                            continue
                        nearest_point, dist = find_nearest_point_on_cable(terminal_pos, cable)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_cable = cable
                    
                    if nearest_cable:
                        new_pos, _ = find_nearest_point_on_cable(terminal_pos, nearest_cable)
                        terminal["position"] = new_pos
                        terminal["connected_cable_id"] = nearest_cable.get("id", "")
                        terminal["distance_to_cable_m"] = 0.0
                        summary["msts_moved_to_cable"] += 1
                    else:
                        print(f"    ❌ ERROR: Cannot place terminal {terminal.get('terminal_id')} on any cable!")
        
        refined_terminals.append(terminal)
    
    print(f"    Moved {summary['msts_moved_to_cable']} MSTs to cable")
    print(f"    Replaced {summary['standalone_msts_replaced']} standalone MSTs with Aerial Terminals")
    
    # Fix 2: Detect terminal overload and split into multiple MSTs from FOSC
    print()
    print("  Fix 2: Detecting terminal overload and splitting into multiple MSTs...")
    
    # Get max terminal ID
    max_terminal_id = 0
    for terminal in refined_terminals:
        term_id = terminal.get("terminal_id", "")
        if term_id and term_id.startswith("T"):
            try:
                term_num = int(term_id.replace("T", ""))
                max_terminal_id = max(max_terminal_id, term_num)
            except:
                pass
    
    terminal_id_counter = max_terminal_id + 1
    
    terminals_to_remove = []
    for terminal in refined_terminals:
        ont_count = len(terminal.get("connected_onts", []))
        terminal_type = terminal.get("type", "")
        connected_fosc_id = terminal.get("connected_fosc_id") or terminal.get("nearest_fosc_id")
        
        # Check if terminal is overloaded (>12 ONTs)
        # Also check port_limit to be safe
        port_limit = terminal.get("port_limit", max_onts_per_terminal)
        if ont_count > port_limit:
            # Check if there's a nearby FOSC
            if connected_fosc_id and connected_fosc_id in fosc_positions:
                fosc_pos = fosc_positions[connected_fosc_id]
                terminal_pos = terminal.get("position")
                
                # Split ONTs into groups of 12
                connected_ont_ids = terminal.get("connected_onts", [])
                num_msts_needed = (ont_count + max_onts_per_terminal - 1) // max_onts_per_terminal
                
                print(f"    Terminal {terminal.get('terminal_id')} has {ont_count} ONTs, splitting into {num_msts_needed} MSTs")
                
                # Group ONTs by proximity to create MST clusters
                ont_groups = []
                remaining_onts = connected_ont_ids.copy()
                
                while remaining_onts and len(ont_groups) < num_msts_needed:
                    # Start new group with first remaining ONT
                    group = [remaining_onts.pop(0)]
                    group_positions = [onts_by_id.get(ont_id, {}).get("position") for ont_id in group if ont_id in onts_by_id]
                    
                    # Add nearby ONTs to group (up to 12)
                    for ont_id in remaining_onts[:]:
                        if len(group) >= max_onts_per_terminal:
                            break
                        
                        ont_pos = onts_by_id.get(ont_id, {}).get("position")
                        if not ont_pos:
                            continue
                        
                        # Check distance to group centroid
                        if group_positions:
                            centroid = calculate_centroid(group_positions)
                            dist = euclidean_distance(ont_pos[0], ont_pos[1], centroid[0], centroid[1])
                            if dist < 200.0:  # Within 200m of group
                                group.append(ont_id)
                                remaining_onts.remove(ont_id)
                                group_positions.append(ont_pos)
                    
                    ont_groups.append(group)
                
                # Create MST for each group
                for i, ont_group in enumerate(ont_groups):
                    if not ont_group:
                        continue
                    
                    # Calculate group centroid
                    group_positions = [onts_by_id.get(ont_id, {}).get("position") for ont_id in ont_group if ont_id in onts_by_id]
                    if not group_positions:
                        continue
                    
                    group_centroid = calculate_centroid(group_positions)
                    
                    # Find nearest cable to place MST ON
                    nearest_cable = None
                    min_cable_dist = float('inf')
                    for cable in cables:
                        nearest_point, dist = find_nearest_point_on_cable(group_centroid, cable)
                        if dist < min_cable_dist:
                            min_cable_dist = dist
                            nearest_cable = cable
                    
                    if nearest_cable and min_cable_dist < 200.0:
                        # Place MST ON the cable
                        mst_pos, _ = find_nearest_point_on_cable(group_centroid, nearest_cable)
                        
                        mst_id = f"T{terminal_id_counter:07d}"
                        mst = {
                            "terminal_id": mst_id,
                            "type": "MST",
                            "model": "MST12",
                            "position": mst_pos,
                            "ont_count": len(ont_group),
                            "port_limit": 12,
                            "connected_onts": ont_group,
                            "connected_cable_id": nearest_cable.get("id", ""),
                            "connected_fosc_id": connected_fosc_id,
                            "nearest_fosc_id": connected_fosc_id,
                            "distance_to_cable_m": 0.0,
                            "distance_to_fosc_m": euclidean_distance(mst_pos[0], mst_pos[1], fosc_pos[0], fosc_pos[1]) if fosc_pos else None,
                            "created_from_split": True,
                            "original_terminal_id": terminal.get("terminal_id")
                        }
                        
                        new_msts.append(mst)
                        terminal_id_counter += 1
                        summary["overloaded_terminals_split"] += 1
                
                # Mark original terminal for removal
                terminals_to_remove.append(terminal)
    
    # Remove overloaded terminals that were split
    refined_terminals = [t for t in refined_terminals if t not in terminals_to_remove]
    refined_terminals.extend(new_msts)
    
    print(f"    Split {summary['overloaded_terminals_split']} overloaded terminals into multiple MSTs")
    
    # Fix 3: Detect terminals with long drop cables and place MSTs closer to ONT clusters
    print()
    print("  Fix 3: Detecting terminals with long drop cables and placing optimal MSTs...")
    
    # Step 1: Analyze all terminals for long drop cables
    terminals_with_long_drops = []
    
    for terminal in refined_terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos_raw = terminal.get("position")
        connected_ont_ids = terminal.get("connected_onts", [])
        
        # DEBUG: Check T0000356
        is_t0000356_check = (terminal_id == "T0000356")
        
        if not terminal_pos_raw or not connected_ont_ids:
            if is_t0000356_check:
                print(f"    DEBUG T0000356: Skipped - no position or no ONTs (pos: {terminal_pos_raw}, onts: {len(connected_ont_ids)})")
            continue
        
        # Ensure terminal position is in UTM format (list or tuple)
        if isinstance(terminal_pos_raw, list) and len(terminal_pos_raw) >= 2:
            terminal_pos = (float(terminal_pos_raw[0]), float(terminal_pos_raw[1]))
        elif isinstance(terminal_pos_raw, tuple) and len(terminal_pos_raw) >= 2:
            terminal_pos = (float(terminal_pos_raw[0]), float(terminal_pos_raw[1]))
        else:
            if is_t0000356_check:
                print(f"    DEBUG T0000356: Invalid position format: {terminal_pos_raw}")
            continue
        
        # Validate UTM coordinates for T0000356
        if is_t0000356_check:
            validate_utm_coordinates(terminal_pos, f"Terminal {terminal_id}")
        
        # Calculate drop cable lengths
        drop_lengths = []
        ont_positions = []
        
        for ont_id in connected_ont_ids:
            ont = onts_by_id.get(ont_id)
            if not ont:
                continue
            
            ont_pos = ont.get("position")
            if not ont_pos:
                continue
            
            drop_length = euclidean_distance(
                terminal_pos[0], terminal_pos[1],
                ont_pos[0], ont_pos[1]
            )
            drop_lengths.append(drop_length)
            ont_positions.append(ont_pos)
        
        if not drop_lengths:
            continue
        
        avg_drop = sum(drop_lengths) / len(drop_lengths)
        max_drop = max(drop_lengths)
        total_drop = sum(drop_lengths)
        
        # Check if terminal has long drop cables
        # Criteria: avg > 100m OR max > 150m
        is_t0000356_check = terminal_id == "T0000356"
        
        if avg_drop > 100.0 or max_drop > 150.0:
            cluster_centroid = calculate_centroid(ont_positions) if ont_positions else terminal_pos
            
            if is_t0000356_check:
                print(f"    DEBUG T0000356: Detected as long drop terminal (avg: {avg_drop:.1f}m, max: {max_drop:.1f}m)")
            
            terminals_with_long_drops.append({
                "terminal": terminal,
                "terminal_id": terminal_id,
                "terminal_pos": terminal_pos,
                "ont_ids": connected_ont_ids,
                "ont_positions": ont_positions,
                "drop_lengths": drop_lengths,
                "avg_drop": avg_drop,
                "max_drop": max_drop,
                "total_drop": total_drop,
                "cluster_centroid": cluster_centroid,
                "ont_count": len(connected_ont_ids)
            })
        elif is_t0000356_check:
            print(f"    DEBUG T0000356: NOT detected as long drop (avg: {avg_drop:.1f}m, max: {max_drop:.1f}m) - criteria: avg>100 OR max>150")
    
    print(f"    Found {len(terminals_with_long_drops)} terminals with long drop cables")
    
    # Step 2: For each terminal with long drops, evaluate MST placement
    def find_optimal_mst_position(ont_positions, candidate_positions):
        """
        Find MST position that minimizes total drop cable length.
        Returns: (best_position, total_drop_length)
        """
        best_pos = None
        min_total_length = float('inf')
        
        for candidate_pos in candidate_positions:
            total_length = 0.0
            for ont_pos in ont_positions:
                dist = euclidean_distance(
                    candidate_pos[0], candidate_pos[1],
                    ont_pos[0], ont_pos[1]
                )
                total_length += dist
            
            if total_length < min_total_length:
                min_total_length = total_length
                best_pos = candidate_pos
        
        return best_pos, min_total_length
    
    candidates_for_mst_placement = []
    
    for term_info in terminals_with_long_drops:
        terminal = term_info["terminal"]
        terminal_id = term_info["terminal_id"]
        terminal_pos = term_info["terminal_pos"]
        ont_positions = term_info["ont_positions"]
        ont_ids = term_info["ont_ids"]
        cluster_centroid = term_info["cluster_centroid"]
        total_drop = term_info["total_drop"]
        
        # DEBUG: Check T0000356 specifically
        is_t0000356 = terminal_id == "T0000356"
        
        if is_t0000356:
            print(f"    DEBUG T0000356: Processing terminal")
            print(f"    DEBUG T0000356: Terminal position: {terminal_pos}")
            print(f"    DEBUG T0000356: Cluster centroid: {cluster_centroid}")
            print(f"    DEBUG T0000356: ONT positions: {ont_positions[:3]}...")
        
        # Check if ONTs form a cluster (within 200m of centroid)
        cluster_radius = 200.0
        clustered_onts = []
        clustered_positions = []
        clustered_ids = []
        
        for i, ont_pos in enumerate(ont_positions):
            dist_to_centroid = euclidean_distance(
                cluster_centroid[0], cluster_centroid[1],
                ont_pos[0], ont_pos[1]
            )
            if dist_to_centroid <= cluster_radius:
                clustered_onts.append(ont_ids[i])
                clustered_positions.append(ont_pos)
                clustered_ids.append(ont_ids[i])
        
        # Need at least 3 ONTs in cluster to justify MST
        if len(clustered_onts) < 3:
            if is_t0000356:
                print(f"    DEBUG T0000356: Only {len(clustered_onts)} ONTs in cluster (need 3+)")
            continue
        
        # Find nearby FOSCs
        # First, check if user-specified FOSC (F0000178) is available and on a cable near cluster
        nearest_fosc = None
        min_fosc_dist = float('inf')
        user_specified_fosc = None
        
        for fosc in foscs:
            fosc_id = fosc.get("fosc_id", "")
            fosc_pos_raw = fosc.get("position")
            if not fosc_pos_raw:
                continue
            
            # CRITICAL: Use FOSC position from fosc_positions map (validated UTM)
            # This ensures we use the correct UTM coordinates, not transformed ones
            if fosc_id in fosc_positions:
                fosc_pos_utm = fosc_positions[fosc_id]
                fosc_pos_tuple = (float(fosc_pos_utm[0]), float(fosc_pos_utm[1]))
            else:
                # Fallback: use position from fosc dict (but validate)
                if isinstance(fosc_pos_raw, list) and len(fosc_pos_raw) >= 2:
                    fosc_pos_tuple = (float(fosc_pos_raw[0]), float(fosc_pos_raw[1]))
                elif isinstance(fosc_pos_raw, tuple) and len(fosc_pos_raw) >= 2:
                    fosc_pos_tuple = (float(fosc_pos_raw[0]), float(fosc_pos_raw[1]))
                else:
                    continue
                
                # Validate UTM
                if is_t0000356 and fosc_id == "F0000090":
                    validate_utm_coordinates(fosc_pos_tuple, f"FOSC {fosc_id} (fallback)")
            
            # Check if this is the user-specified FOSC
            if fosc_id == "F0000178":
                user_specified_fosc = fosc
                # Check if it's on a cable near the cluster
                fosc_on_cable_near_cluster = False
                for cable in cables:
                    nearest_point, dist = find_nearest_point_on_cable(fosc_pos_tuple, cable)
                    if dist < 10.0:  # FOSC is on cable
                        cluster_nearest, cluster_dist = find_nearest_point_on_cable(cluster_centroid, cable)
                        if cluster_dist < 500.0:  # Cable is near cluster
                            fosc_on_cable_near_cluster = True
                            dist_to_cluster = euclidean_distance(
                                cluster_centroid[0], cluster_centroid[1],
                                fosc_pos_tuple[0], fosc_pos_tuple[1]
                            )
                            if dist_to_cluster < min_fosc_dist:
                                min_fosc_dist = dist_to_cluster
                                nearest_fosc = fosc
                            break
                if is_t0000356:
                    print(f"    DEBUG T0000356: F0000178 found, on cable near cluster: {fosc_on_cable_near_cluster}, dist: {min_fosc_dist:.1f}m")
            
            # Also check distance-based (within 2km)
            # CRITICAL: All coordinates are UTM, so distance is in meters
            dist = euclidean_distance(
                cluster_centroid[0], cluster_centroid[1],
                fosc_pos_tuple[0], fosc_pos_tuple[1]
            )
            # Update if this FOSC is closer (within 2km)
            if dist < 2000.0 and dist < min_fosc_dist:  # Within 2km and closer than current best
                min_fosc_dist = dist
                nearest_fosc = fosc
                if is_t0000356 and dist < 500.0:
                    print(f"    DEBUG T0000356: Found nearby FOSC {fosc_id} at {dist:.1f}m (UTM distance)")
                    print(f"      FOSC position (UTM): {fosc_pos_tuple}")
                    print(f"      Cluster centroid (UTM): {cluster_centroid}")
        
        if not nearest_fosc:
            if is_t0000356:
                print(f"    DEBUG T0000356: No FOSC within 2km of cluster")
                print(f"    DEBUG T0000356: Total FOSCs checked: {len(foscs)}")
                print(f"    DEBUG T0000356: Cluster centroid: {cluster_centroid}, type: {type(cluster_centroid)}")
                # Check distances to all FOSCs
                fosc_distances = []
                foscs_with_pos = 0
                foscs_checked = 0
                for f in foscs:
                    f_pos = f.get("position")
                    if f_pos:
                        foscs_with_pos += 1
                        # Handle list or tuple
                        if isinstance(f_pos, list) and len(f_pos) >= 2:
                            f_pos_tuple = (f_pos[0], f_pos[1])
                        elif isinstance(f_pos, tuple) and len(f_pos) >= 2:
                            f_pos_tuple = f_pos
                        else:
                            continue
                        
                        foscs_checked += 1
                        # Ensure cluster_centroid is a tuple
                        if isinstance(cluster_centroid, list):
                            cluster_tuple = (cluster_centroid[0], cluster_centroid[1])
                        else:
                            cluster_tuple = cluster_centroid
                        
                        # Test with F0000090 specifically
                        fosc_id = f.get("fosc_id", "")
                        if fosc_id == "F0000090":
                            print(f"    DEBUG T0000356: Checking F0000090")
                            print(f"      FOSC position: {f_pos_tuple}, type: {type(f_pos_tuple)}")
                            print(f"      Cluster: {cluster_tuple}, type: {type(cluster_tuple)}")
                        
                        d = euclidean_distance(cluster_tuple[0], cluster_tuple[1], f_pos_tuple[0], f_pos_tuple[1])
                        
                        if fosc_id == "F0000090":
                            print(f"      Distance: {d:.1f}m")
                        
                        if d < 2000.0:
                            fosc_distances.append((fosc_id, d))
                fosc_distances.sort(key=lambda x: x[1])
                print(f"    DEBUG T0000356: FOSCs with position: {foscs_with_pos}/{len(foscs)}")
                print(f"    DEBUG T0000356: FOSCs within 2km: {len(fosc_distances)}")
                for fosc_id, dist in fosc_distances[:5]:
                    print(f"      {fosc_id}: {dist:.1f}m")
            continue
        
        if is_t0000356:
            print(f"    DEBUG T0000356: Using FOSC {nearest_fosc.get('fosc_id')} at {min_fosc_dist:.1f}m")
        
        # Find nearby cables for MST placement
        # CRITICAL: Search ALL cables within 500m, not just the nearest
        # This ensures we find the best cable that passes through or near the cluster
        nearby_cables = []
        for cable in cables:
            nearest_point, dist = find_nearest_point_on_cable(cluster_centroid, cable)
            if dist < 500.0:  # Within 500m
                nearby_cables.append((cable, nearest_point, dist))
        
        if not nearby_cables:
            if is_t0000356:
                print(f"    DEBUG T0000356: No cables within 500m of cluster")
                print(f"    DEBUG T0000356: Cluster centroid: {cluster_centroid}, type: {type(cluster_centroid)}")
                # Check distance to first few cables
                for i, cable in enumerate(cables[:5]):
                    nearest_point, dist = find_nearest_point_on_cable(cluster_centroid, cable)
                    print(f"      Cable {i+1} ({cable.get('id', 'unknown')}): {dist:.1f}m")
            continue
        
        # Sort by distance to cluster (closest first)
        nearby_cables.sort(key=lambda x: x[2])
        
        if is_t0000356:
            print(f"    DEBUG T0000356: Found {len(nearby_cables)} cables within 500m")
            for i, (cable, point, dist) in enumerate(nearby_cables[:3]):
                # Check if this point is the same as terminal
                terminal_pos_tuple = tuple(terminal_pos) if isinstance(terminal_pos, list) else terminal_pos
                point_tuple = tuple(point) if isinstance(point, list) else point
                dist_to_terminal = euclidean_distance(
                    point_tuple[0], point_tuple[1],
                    terminal_pos_tuple[0], terminal_pos_tuple[1]
                )
                same_as_terminal = " (SAME AS TERMINAL)" if dist_to_terminal < 5.0 else ""
                print(f"      Cable {i+1}: {cable.get('id', 'unknown')} at {dist:.1f}m, point: {point}{same_as_terminal}")
        
        # Generate candidate positions on cables
        # CRITICAL: For each nearby cable, find the point closest to cluster centroid
        # This ensures we place MST as close as possible to ONT cluster
        candidate_positions = []
        
        # For each nearby cable, find point closest to cluster centroid
        for cable, nearest_point, dist in nearby_cables:
            # Find point on THIS cable closest to cluster centroid
            centroid_on_this_cable, _ = find_nearest_point_on_cable(cluster_centroid, cable)
            candidate_positions.append(centroid_on_this_cable)
            
            if is_t0000356 and dist < 100.0:
                print(f"    DEBUG T0000356: Cable {cable.get('id', 'unknown')} at {dist:.1f}m, point on cable: {centroid_on_this_cable}")
            
            # Also try points along cable segments very close to cluster
            coords = cable.get("coordinates", [])
            if len(coords) >= 2:
                for i in range(len(coords) - 1):
                    p1 = coords[i]
                    p2 = coords[i + 1]
                    seg_centroid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                    seg_dist = euclidean_distance(
                        cluster_centroid[0], cluster_centroid[1],
                        seg_centroid[0], seg_centroid[1]
                    )
                    if seg_dist < 100.0:  # Segment is very close to cluster
                        candidate_positions.append(seg_centroid)
        
        # Find optimal MST position
        optimal_pos, new_total_drop = find_optimal_mst_position(clustered_positions, candidate_positions)
        
        if not optimal_pos:
            if is_t0000356:
                print(f"    DEBUG T0000356: No optimal position found")
            continue
        
        # CRITICAL: Always use cluster centroid projected onto nearest cable
        # This ensures MST is placed as close as possible to ONT cluster
        best_cable_for_centroid = None
        min_dist_to_cable = float('inf')
        centroid_on_cable = None
        
        for cable in cables:
            nearest_point, dist = find_nearest_point_on_cable(cluster_centroid, cable)
            if dist < min_dist_to_cable:
                min_dist_to_cable = dist
                best_cable_for_centroid = cable
                if dist < 100.0:  # Cluster is reasonably close to cable
                    centroid_on_cable = nearest_point
        
        # ALWAYS use cluster centroid projected onto nearest cable if available (within 100m)
        # This ensures we place MST closer to ONTs than the current terminal
        if centroid_on_cable and min_dist_to_cable < 100.0:
            # Recalculate drop from cluster centroid position
            drop_from_centroid = sum(
                euclidean_distance(centroid_on_cable[0], centroid_on_cable[1], ont_pos[0], ont_pos[1])
                for ont_pos in clustered_positions
            )
            
            # Check if centroid position is actually different from terminal
            terminal_pos_tuple = tuple(terminal_pos) if isinstance(terminal_pos, list) else terminal_pos
            centroid_tuple = tuple(centroid_on_cable) if isinstance(centroid_on_cable, list) else centroid_on_cable
            dist_centroid_to_terminal = euclidean_distance(
                centroid_tuple[0], centroid_tuple[1],
                terminal_pos_tuple[0], terminal_pos_tuple[1]
            )
            
            # Only use centroid if it's significantly different (>10m) and gives better drop cables
            if dist_centroid_to_terminal > 10.0 and drop_from_centroid < new_total_drop:
                optimal_pos = centroid_on_cable
                new_total_drop = drop_from_centroid
                
                if is_t0000356:
                    print(f"    DEBUG T0000356: Using cluster centroid on cable (dist to cable: {min_dist_to_cable:.1f}m)")
                    print(f"    DEBUG T0000356: Centroid position: {centroid_on_cable}")
                    print(f"    DEBUG T0000356: Terminal position: {terminal_pos}")
                    print(f"    DEBUG T0000356: Distance between them: {dist_centroid_to_terminal:.1f}m")
                    print(f"    DEBUG T0000356: Drop from centroid: {drop_from_centroid:.1f}m vs from terminal: {total_drop:.1f}m")
            elif is_t0000356:
                print(f"    DEBUG T0000356: Centroid on cable is same as terminal (dist: {dist_centroid_to_terminal:.1f}m) or not better")
        
        # Check distance to terminal
        terminal_pos_tuple = tuple(terminal_pos) if isinstance(terminal_pos, list) else terminal_pos
        optimal_pos_tuple = tuple(optimal_pos) if isinstance(optimal_pos, list) else optimal_pos
        
        dist_to_terminal = euclidean_distance(
            optimal_pos_tuple[0], optimal_pos_tuple[1],
            terminal_pos_tuple[0], terminal_pos_tuple[1]
        )
        
        if is_t0000356:
            print(f"    DEBUG T0000356: Optimal position: {optimal_pos}, Terminal: {terminal_pos}, Distance: {dist_to_terminal:.1f}m")
        
        # Calculate savings: (old total drop) - (new total drop + stub cable)
        stub_cable_length = min_fosc_dist
        savings = total_drop - (new_total_drop + stub_cable_length)
        
        # Only place MST if savings are significant
        # For terminals with very long drop cables (max > 150m), use lower threshold
        # This ensures we fix problematic terminals even if savings are marginal
        max_drop = max(term_info["drop_lengths"]) if "drop_lengths" in term_info else 0
        savings_threshold = 50.0 if max_drop > 150.0 else 100.0
        
        if is_t0000356:
            print(f"    DEBUG T0000356: Savings calculation: {savings:.1f}m (old: {total_drop:.1f}m, new: {new_total_drop:.1f}m, stub: {stub_cable_length:.1f}m)")
            print(f"    DEBUG T0000356: Max drop: {max_drop:.1f}m, threshold: {savings_threshold:.1f}m")
            print(f"    DEBUG T0000356: Optimal position: {optimal_pos}, Terminal position: {terminal_pos}")
        
        # For terminals with very long drop cables (max > 150m), create MST even with negative savings
        # if the terminal is an Aerial Terminal (can be converted to MST)
        terminal_type = term_info.get("terminal", {}).get("type", "")
        force_mst = (max_drop > 150.0 and terminal_type == "Aerial Terminal" and savings > -500.0)
        
        if is_t0000356:
            print(f"    DEBUG T0000356: Terminal type: {terminal_type}, force_mst: {force_mst}")
        
        if savings > savings_threshold or force_mst:
            # Determine which cable the optimal position is on
            best_cable = None
            min_cable_dist = float('inf')
            for cable in cables:
                nearest_point, dist = find_nearest_point_on_cable(optimal_pos, cable)
                if dist < min_cable_dist:
                    min_cable_dist = dist
                    best_cable = cable
                    if dist < 1.0:  # On cable
                        optimal_pos = nearest_point
                        break
            
            if best_cable:
                candidates_for_mst_placement.append({
                    "terminal": terminal,
                    "terminal_id": term_info["terminal_id"],
                    "ont_ids": clustered_ids,
                    "ont_positions": clustered_positions,
                    "optimal_mst_pos": optimal_pos,
                    "best_cable": best_cable,
                    "nearest_fosc": nearest_fosc,
                    "stub_cable_length": stub_cable_length,
                    "old_total_drop": total_drop,
                    "new_total_drop": new_total_drop,
                    "savings": savings,
                    "ont_count": len(clustered_ids)
                })
    
    print(f"    Identified {len(candidates_for_mst_placement)} candidates for MST placement")
    
    # Step 3: Place MSTs for terminals with long drop cables
    for candidate in candidates_for_mst_placement:
        # Split ONTs into groups (max 12 per MST)
        ont_ids = candidate["ont_ids"]
        ont_positions = candidate["ont_positions"]
        num_msts = (len(ont_ids) + max_onts_per_terminal - 1) // max_onts_per_terminal
        
        # Split into groups
        ont_groups = []
        for i in range(0, len(ont_ids), max_onts_per_terminal):
            group_ids = ont_ids[i:i + max_onts_per_terminal]
            group_positions = ont_positions[i:i + max_onts_per_terminal]
            ont_groups.append((group_ids, group_positions))
        
        # Place MST for each group
        for group_ids, group_positions in ont_groups:
            optimal_pos = candidate["optimal_mst_pos"]
            best_cable = candidate["best_cable"]
            nearest_fosc = candidate["nearest_fosc"]
            stub_cable_length = candidate["stub_cable_length"]
            
            # Recalculate drop lengths for this specific group
            new_total_drop = 0.0
            for ont_pos in group_positions:
                dist = euclidean_distance(
                    optimal_pos[0], optimal_pos[1],
                    ont_pos[0], ont_pos[1]
                )
                new_total_drop += dist
            
            # Create MST
            mst_id = f"T{terminal_id_counter:07d}"
            
            mst = {
                "terminal_id": mst_id,
                "type": "MST",
                "model": "MST12",
                "position": optimal_pos,
                "ont_count": len(group_ids),
                "port_limit": 12,
                "connected_onts": group_ids,
                "connected_cable_id": best_cable.get("id", ""),
                "connected_fosc_id": nearest_fosc.get("fosc_id", ""),
                "nearest_fosc_id": nearest_fosc.get("fosc_id", ""),
                "distance_to_cable_m": 0.0,  # ON cable
                "distance_to_fosc_m": stub_cable_length,
                "created_from_long_drop_fix": True,
                "replaces_terminal_id": candidate["terminal_id"],
                "avg_drop_length_m": new_total_drop / len(group_positions) if group_positions else 0.0,
                "old_avg_drop_length_m": candidate["old_total_drop"] / len(candidate["ont_positions"]) if candidate["ont_positions"] else 0.0,
                "savings_m": candidate["savings"],
                "needs_stub_cable": True
            }
            
            # Remove these ONTs from original terminal
            original_terminal = candidate["terminal"]
            original_terminal["connected_onts"] = [oid for oid in original_terminal.get("connected_onts", []) if oid not in group_ids]
            original_terminal["ont_count"] = len(original_terminal["connected_onts"])
            
            new_msts.append(mst)
            terminal_id_counter += 1
            summary["new_msts_added"] += 1
            summary["long_drop_cables_fixed"] += len(group_ids)
    
    refined_terminals.extend(new_msts)
    
    print(f"    Added {summary['new_msts_added']} new MSTs for ONT clusters")
    print(f"    Fixed {summary['long_drop_cables_fixed']} drop cables by placing MSTs in clusters")
    
    # Summary
    print()
    print("=" * 80)
    print("PHASE 3B SUMMARY")
    print("=" * 80)
    print(f"  MSTs moved to cable: {summary['msts_moved_to_cable']}")
    print(f"  Standalone MSTs replaced: {summary['standalone_msts_replaced']}")
    print(f"  Overloaded terminals split: {summary['overloaded_terminals_split']}")
    print(f"  New MSTs added: {summary['new_msts_added']}")
    print(f"  Long drop cables fixed: {summary['long_drop_cables_fixed']}")
    print(f"  Total terminals after refinement: {len(refined_terminals)}")
    print(f"  Total FOSCs after refinement: {len(foscs)}")
    print()
    
    return refined_terminals, foscs, new_msts, summary
