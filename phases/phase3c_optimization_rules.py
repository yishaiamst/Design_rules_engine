#!/usr/bin/env python3
"""
Phase 3c: Optimization Rules for FOSC and MST Placement

Rules applied:
1. Merge FOSCs that are close together and serve the same cables
2. Consolidate MSTs within 250m (drop cables are inexpensive)
3. Remove redundant FOSCs (on single cable, very close to terminals)
4. Convert Aerial Terminals to MSTs when near FOSCs (<1km)
5. Filter ONTs >1km from terminals (leave for later)
6. Connect MSTs to nearest FOSC (<1km)

All rules use UTM Zone 17N coordinates (no transformation).
"""

from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from utils.spatial_utils import euclidean_distance
from phases.phase3b_refine_mst_placement import find_nearest_point_on_cable


def merge_nearby_foscs(foscs: List[Dict[str, Any]], cables: List[Dict[str, Any]], max_distance: float = 100.0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 1: Merge FOSCs that are close together and serve the same cables.
    
    Args:
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        max_distance: Maximum distance to consider merging (default 100m)
    
    Returns:
        (merged_foscs, merge_summary)
    """
    print()
    print("=" * 80)
    print("RULE 1: MERGING NEARBY FOSCs")
    print("=" * 80)
    print()
    print(f"Merging FOSCs within {max_distance}m that serve the same cables...")
    print()
    
    # Build FOSC position and cable map
    fosc_positions = {}
    fosc_cables = {}
    
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            continue
        
        fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
        fosc_positions[fosc_id] = fosc_pos_utm
        
        # Get cables connected to this FOSC
        connected_cables = fosc.get("connected_cables", [])
        if not connected_cables:
            # Find cables near this FOSC
            for cable in cables:
                nearest_point, dist = find_nearest_point_on_cable(fosc_pos_utm, cable)
                if dist < 10.0:  # FOSC is on cable
                    cable_id = cable.get("id", "")
                    if cable_id:
                        connected_cables.append(cable_id)
        
        fosc_cables[fosc_id] = set(connected_cables)
    
    # Find FOSCs to merge
    foscs_to_remove = set()
    merges = []
    
    for i, fosc1 in enumerate(foscs):
        fosc1_id = fosc1.get("fosc_id", "")
        if fosc1_id in foscs_to_remove:
            continue
        
        fosc1_pos = fosc_positions.get(fosc1_id)
        if not fosc1_pos:
            continue
        
        fosc1_cables = fosc_cables.get(fosc1_id, set())
        
        # Find nearby FOSCs
        nearby_foscs = []
        for j, fosc2 in enumerate(foscs):
            if i >= j:
                continue
            
            fosc2_id = fosc2.get("fosc_id", "")
            if fosc2_id in foscs_to_remove:
                continue
            
            fosc2_pos = fosc_positions.get(fosc2_id)
            if not fosc2_pos:
                continue
            
            dist = euclidean_distance(fosc1_pos[0], fosc1_pos[1], fosc2_pos[0], fosc2_pos[1])
            
            if dist <= max_distance:
                fosc2_cables = fosc_cables.get(fosc2_id, set())
                # Check if they serve the same or overlapping cables
                common_cables = fosc1_cables & fosc2_cables
                # Merge if they share cables OR are very close (<50m) OR all cables are nearby
                should_merge = common_cables or dist < 50.0
                if not should_merge and dist < max_distance:
                    # Check if all cables are in the same area (all cables nearby)
                    all_cables_nearby = len(fosc1_cables) > 0 and len(fosc2_cables) > 0
                    should_merge = all_cables_nearby and dist < 50.0
                
                if should_merge:
                    nearby_foscs.append((fosc2_id, fosc2, dist, fosc2_cables))
        
        if nearby_foscs:
            # Merge into fosc1
            all_cables = fosc1_cables.copy()
            for fosc2_id, fosc2_obj, dist, fosc2_cables_set in nearby_foscs:
                all_cables.update(fosc2_cables_set)
                foscs_to_remove.add(fosc2_id)
                
                # Calculate common cables for this pair
                common_cables_pair = fosc1_cables & fosc2_cables_set
                merges.append({
                    "kept": fosc1_id,
                    "removed": fosc2_id,
                    "distance": dist,
                    "common_cables": len(common_cables_pair)
                })
            
            # Update fosc1 with merged cables
            fosc1["connected_cables"] = list(all_cables)
            
            # Update position to be between the merged FOSCs (weighted average)
            if nearby_foscs:
                total_weight = 1.0 + len(nearby_foscs)
                new_x = fosc1_pos[0] * (1.0 / total_weight)
                new_y = fosc1_pos[1] * (1.0 / total_weight)
                
                for fosc2_id, fosc2_obj, dist, _ in nearby_foscs:
                    fosc2_pos = fosc_positions.get(fosc2_id)
                    if fosc2_pos:
                        new_x += fosc2_pos[0] * (1.0 / total_weight)
                        new_y += fosc2_pos[1] * (1.0 / total_weight)
                
                fosc1["position"] = [new_x, new_y]
            
            print(f"  ✓ Merged: Kept {fosc1_id}, removed {len(nearby_foscs)} nearby FOSCs")
            for fosc2_id, _, dist, _ in nearby_foscs:
                print(f"    - Removed {fosc2_id} ({dist:.1f}m away)")
    
    # Remove merged FOSCs
    merged_foscs = [f for f in foscs if f.get("fosc_id") not in foscs_to_remove]
    
    print()
    print(f"Merged {len(merges)} FOSC pairs")
    print(f"Removed {len(foscs_to_remove)} redundant FOSCs")
    print(f"Final FOSC count: {len(merged_foscs)}")
    print()
    
    return merged_foscs, merges


def consolidate_nearby_msts(terminals: List[Dict[str, Any]], min_distance: float = 250.0, specific_merges: Optional[List[Tuple[str, str]]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 2: Consolidate nearby terminals (MSTs and Aerial Terminals) within min_distance (250m) of each other.
    Drop cables are inexpensive, so it's better to have one terminal with longer drops.
    
    Args:
        terminals: List of terminal dictionaries
        min_distance: Maximum distance to consider consolidating (default 250m)
    
    Returns:
        (optimized_terminals, consolidation_summary)
    """
    print()
    print("=" * 80)
    print("RULE 2: CONSOLIDATING NEARBY TERMINALS")
    print("=" * 80)
    print()
    print(f"Consolidating terminals within {min_distance}m of each other...")
    print()
    
    # Get all terminals (MSTs and Aerial Terminals)
    all_terminals = [t for t in terminals if t.get("type") in ["MST", "Aerial Terminal"]]
    msts = [t for t in all_terminals if t.get("type") == "MST"]
    aerials = [t for t in all_terminals if t.get("type") == "Aerial Terminal"]
    print(f"Total terminals: {len(all_terminals)} ({len(msts)} MSTs, {len(aerials)} Aerial)")
    
    # Handle specific merges requested by user (e.g., T0004278, T0004280 -> T0004266)
    terminals_to_remove_specific = set()
    specific_consolidations = []
    if specific_merges:
        for keep_id, remove_id in specific_merges:
            keep_term = next((t for t in all_terminals if t.get("terminal_id") == keep_id), None)
            remove_term = next((t for t in all_terminals if t.get("terminal_id") == remove_id), None)
            
            if keep_term and remove_term and remove_id not in terminals_to_remove_specific:
                # Check if merging would exceed 12 ONTs limit
                keep_onts = keep_term.get("connected_onts", [])
                remove_onts = remove_term.get("connected_onts", [])
                total_onts_after = len(keep_onts) + len(remove_onts)
                max_onts_per_terminal = 12
                
                if total_onts_after > max_onts_per_terminal:
                    print(f"  ⚠ Skipping specific merge {remove_id} → {keep_id}: Would exceed {max_onts_per_terminal} ONTs ({total_onts_after} total)")
                    continue
                
                # Merge ONTs
                keep_term["connected_onts"] = keep_onts + remove_onts
                terminals_to_remove_specific.add(remove_id)
                
                specific_consolidations.append({
                    "kept": keep_id,
                    "removed": remove_id,
                    "distance": 0,
                    "onts_moved": len(remove_onts)
                })
                
                print(f"  ✓ Merged {remove_id} into {keep_id} (specific merge)")
                print(f"    {keep_id}: {len(keep_onts)} → {len(keep_term['connected_onts'])} ONTs")
        
        # Remove merged terminals from list
        all_terminals = [t for t in all_terminals if t.get("terminal_id") not in terminals_to_remove_specific]
    
    # Build terminal position map
    terminal_positions = {}
    for terminal in all_terminals:
        term_id = terminal.get("terminal_id", "")
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            terminal_positions[term_id] = term_pos_utm
    
    # Find terminals within min_distance of each other
    terminals_to_remove = set()
    consolidations = []
    
    for i, term1 in enumerate(all_terminals):
        term1_id = term1.get("terminal_id", "")
        if term1_id in terminals_to_remove:
            continue
        
        term1_pos = terminal_positions.get(term1_id)
        if not term1_pos:
            continue
        
        term1_onts = len(term1.get("connected_onts", []))
        term1_type = term1.get("type", "")
        
        # Find nearby terminals
        nearby_terminals = []
        for j, term2 in enumerate(all_terminals):
            if i >= j:
                continue
            
            term2_id = term2.get("terminal_id", "")
            if term2_id in terminals_to_remove:
                continue
            
            term2_pos = terminal_positions.get(term2_id)
            if not term2_pos:
                continue
            
            dist = euclidean_distance(term1_pos[0], term1_pos[1], term2_pos[0], term2_pos[1])
            
            if dist <= min_distance:
                term2_onts = len(term2.get("connected_onts", []))
                term2_type = term2.get("type", "")
                nearby_terminals.append((term2_id, term2, dist, term2_onts, term2_type))
        
        if nearby_terminals:
            # Decide which terminal to keep (prefer MST over Aerial, then more ONTs)
            all_terminals_in_group = [(term1_id, term1, 0.0, term1_onts, term1_type)] + nearby_terminals
            # Sort by: type (MST preferred), then ONT count, then distance
            all_terminals_in_group.sort(key=lambda x: (x[4] != "MST", -x[3], x[2]))
            
            kept_term_id, kept_term, _, _, _ = all_terminals_in_group[0]
            removed_terms = all_terminals_in_group[1:]
            
            # Check if merging would exceed 12 ONTs limit
            kept_term_obj = next((t for t in all_terminals if t.get("terminal_id") == kept_term_id), None)
            if kept_term_obj:
                total_onts_before = len(kept_term_obj.get("connected_onts", []))
                total_onts_after_merge = total_onts_before
                
                # Calculate total ONTs if we merge all nearby terminals
                for removed_id, removed_term_obj, _, _, _ in removed_terms:
                    removed_onts = removed_term_obj.get("connected_onts", [])
                    total_onts_after_merge += len(removed_onts)
                
                # Only merge if total ONTs <= 12
                max_onts_per_terminal = 12
                if total_onts_after_merge > max_onts_per_terminal:
                    print(f"  ⚠ Skipping consolidation of {kept_term_id}: Would exceed {max_onts_per_terminal} ONTs ({total_onts_after_merge} total)")
                    continue
                
                # If keeping an Aerial Terminal but removing an MST, convert to MST
                if kept_term_obj.get("type") == "Aerial Terminal":
                    for removed_id, removed_term_obj, _, _, removed_type in removed_terms:
                        if removed_type == "MST":
                            kept_term_obj["type"] = "MST"
                            print(f"  ✓ Converted {kept_term_id} from Aerial Terminal to MST (consolidating with MST)")
                            break
                
                for removed_id, removed_term_obj, dist_to_kept, _, _ in removed_terms:
                    removed_onts = removed_term_obj.get("connected_onts", [])
                    kept_term_obj["connected_onts"].extend(removed_onts)
                    terminals_to_remove.add(removed_id)
                    
                    consolidations.append({
                        "kept": kept_term_id,
                        "removed": removed_id,
                        "distance": dist_to_kept,
                        "onts_moved": len(removed_onts)
                    })
                
                total_onts_after = len(kept_term_obj.get("connected_onts", []))
                
                print(f"  ✓ Consolidated: Kept {kept_term_id} ({total_onts_before} → {total_onts_after} ONTs)")
                for removed_id, _, dist, _, _ in removed_terms:
                    print(f"    - Removed {removed_id} ({dist:.1f}m away)")
    
    # Remove consolidated terminals
    all_terminals_to_remove = terminals_to_remove_specific | terminals_to_remove
    optimized_terminals = [t for t in terminals if t.get("terminal_id") not in all_terminals_to_remove]
    
    # Combine consolidations
    all_consolidations = specific_consolidations + consolidations
    
    print()
    print(f"Consolidated {len(all_consolidations)} terminal pairs ({len(specific_consolidations)} specific, {len(consolidations)} distance-based)")
    print(f"Removed {len(all_terminals_to_remove)} redundant terminals")
    print(f"Final terminal count: {len([t for t in optimized_terminals if t.get('type') in ['MST', 'Aerial Terminal']])}")
    print()
    
    return optimized_terminals, all_consolidations


def remove_redundant_foscs(foscs: List[Dict[str, Any]], terminals: List[Dict[str, Any]], cables: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 3: Remove redundant FOSCs.
    - FOSCs very close to terminals (<50m) - likely redundant
    - FOSCs on single cable with same size on both sides - likely redundant
    
    Args:
        foscs: List of FOSC dictionaries
        terminals: List of terminal dictionaries
        cables: List of cable dictionaries
    
    Returns:
        (filtered_foscs, removed_foscs)
    """
    print()
    print("=" * 80)
    print("RULE 3: REMOVING REDUNDANT FOSCs")
    print("=" * 80)
    print()
    
    redundant_foscs = []
    terminal_positions = {}
    
    for terminal in terminals:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            terminal_positions[terminal.get("terminal_id", "")] = term_pos_utm
    
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            continue
        
        fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
        
        # Check 1: Very close to terminal (<50m)
        nearby_terminals = []
        for term_id, term_pos in terminal_positions.items():
            dist = euclidean_distance(fosc_pos_utm[0], fosc_pos_utm[1], term_pos[0], term_pos[1])
            if dist < 50.0:
                nearby_terminals.append((term_id, dist))
        
        # Check 2: On single cable (but only if not at junction)
        fosc_on_single_cable = False
        cables_on_fosc = []
        for cable in cables:
            nearest_point, dist = find_nearest_point_on_cable(fosc_pos_utm, cable)
            if dist < 10.0:  # FOSC is on this cable
                cables_on_fosc.append(cable.get("id", ""))
        
        # Check if FOSC is at junction (2+ cables meet here)
        is_at_junction = len(cables_on_fosc) >= 2 or len(fosc.get("connected_cables", [])) >= 2
        
        if len(cables_on_fosc) == 1:
            fosc_on_single_cable = True
        
        # Determine if redundant
        is_redundant = False
        reason = []
        
        # Don't remove FOSCs at junctions (they're needed for cable connections)
        if is_at_junction:
            is_redundant = False
        elif nearby_terminals:
            is_redundant = True
            reason.append(f"Very close to terminal(s): {', '.join([f'{t[0]} ({t[1]:.1f}m)' for t in nearby_terminals])}")
        
        if fosc_on_single_cable and not is_at_junction:
            is_redundant = True
            reason.append("On single fiber cable")
        
        if is_redundant:
            redundant_foscs.append({
                "fosc_id": fosc_id,
                "fosc_pos": fosc_pos_utm,
                "reasons": reason
            })
    
    if redundant_foscs:
        redundant_ids = {f["fosc_id"] for f in redundant_foscs}
        filtered_foscs = [f for f in foscs if f.get("fosc_id") not in redundant_ids]
        
        print(f"Removed {len(redundant_foscs)} redundant FOSCs:")
        for fosc_info in redundant_foscs:
            print(f"  {fosc_info['fosc_id']}: {', '.join(fosc_info['reasons'])}")
        print()
    else:
        filtered_foscs = foscs
        print("No redundant FOSCs found.")
        print()
    
    return filtered_foscs, redundant_foscs


def convert_aerial_to_mst_near_foscs(terminals: List[Dict[str, Any]], foscs: List[Dict[str, Any]], max_distance: float = 1000.0) -> List[Dict[str, Any]]:
    """
    Rule 4: Convert Aerial Terminals to MSTs when near FOSCs (<1km).
    Also connect existing MSTs to FOSCs if they don't have a connection.
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        max_distance: Maximum distance to convert/connect (default 1000m)
    
    Returns:
        List of conversion/connection summaries
    """
    print()
    print("=" * 80)
    print("RULE 4: CONVERTING AERIAL TERMINALS TO MSTs AND CONNECTING MSTs TO FOSCs")
    print("=" * 80)
    print()
    
    converted = []
    connected = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        
        if not terminal_pos:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Find nearest FOSC
        nearest_fosc = None
        min_fosc_dist = float('inf')
        
        for fosc in foscs:
            fosc_pos = fosc.get("position")
            if not fosc_pos:
                continue
            
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos_utm[0], fosc_pos_utm[1])
            
            if dist < min_fosc_dist and dist <= max_distance:
                min_fosc_dist = dist
                nearest_fosc = fosc
        
        if nearest_fosc:
            if terminal_type == "Aerial Terminal":
                # Convert to MST
                terminal["type"] = "MST"
                terminal["connected_fosc_id"] = nearest_fosc.get("fosc_id", "")
                terminal["stub_cable_length"] = min_fosc_dist
                
                converted.append({
                    "terminal_id": terminal_id,
                    "fosc_id": nearest_fosc.get("fosc_id", ""),
                    "distance": min_fosc_dist
                })
                
                print(f"  ✓ Converted {terminal_id} to MST (FOSC: {nearest_fosc.get('fosc_id')}, {min_fosc_dist:.1f}m)")
            elif terminal_type == "MST" and not terminal.get("connected_fosc_id"):
                # Connect existing MST to FOSC
                terminal["connected_fosc_id"] = nearest_fosc.get("fosc_id", "")
                terminal["stub_cable_length"] = min_fosc_dist
                
                connected.append({
                    "terminal_id": terminal_id,
                    "fosc_id": nearest_fosc.get("fosc_id", ""),
                    "distance": min_fosc_dist
                })
                
                print(f"  ✓ Connected {terminal_id} (MST) to FOSC {nearest_fosc.get('fosc_id')} ({min_fosc_dist:.1f}m)")
    
    print()
    print(f"Converted {len(converted)} Aerial Terminals to MSTs")
    print(f"Connected {len(connected)} existing MSTs to FOSCs")
    print()
    
    return converted + connected


def filter_distant_onts(terminals: List[Dict[str, Any]], ont_geojson: Dict[str, Any], max_drop_distance: float = 1000.0) -> List[str]:
    """
    Rule 5: Filter ONTs that are >max_drop_distance from their terminal.
    Leave them unconnected for later deployment.
    
    Args:
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        max_drop_distance: Maximum drop cable distance (default 1000m)
    
    Returns:
        List of filtered ONT IDs
    """
    print()
    print("=" * 80)
    print("RULE 5: FILTERING DISTANT ONTs (>1km)")
    print("=" * 80)
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    filtered_count = 0
    filtered_onts = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_onts = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_onts:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Filter ONTs by distance
        valid_onts = []
        removed_onts = []
        
        for ont_id in connected_onts:
            if ont_id not in onts_by_id:
                continue
            
            ont_pos = onts_by_id[ont_id]
            dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], ont_pos[0], ont_pos[1])
            
            if dist <= max_drop_distance:
                valid_onts.append(ont_id)
            else:
                removed_onts.append((ont_id, dist))
                filtered_onts.append(ont_id)
                filtered_count += 1
        
        if removed_onts:
            print(f"  {terminal_id}: Removed {len(removed_onts)} distant ONTs")
            for ont_id, dist in removed_onts:
                print(f"    - {ont_id}: {dist:.1f}m ({dist/1000:.2f}km)")
        
        terminal["connected_onts"] = valid_onts
        terminal["removed_distant_onts"] = [ont_id for ont_id, _ in removed_onts]
    
    print()
    print(f"Filtered {filtered_count} ONTs >{max_drop_distance/1000:.1f}km from terminals")
    print()
    
    return filtered_onts


def apply_all_optimization_rules(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply all optimization rules in sequence.
    
    Rules applied:
    1. Merge nearby FOSCs (within 100m, same cables)
    2. Consolidate nearby MSTs (within 250m)
    3. Remove redundant FOSCs (single cable, close to terminals)
    4. Convert Aerial Terminals to MSTs near FOSCs (<1km)
    5. Filter distant ONTs (>1km)
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        ont_geojson: ONT GeoJSON
        config: Configuration dictionary (optional)
    
    Returns:
        (optimized_terminals, optimized_foscs, summary)
    """
    print("=" * 80)
    print("APPLYING ALL OPTIMIZATION RULES")
    print("=" * 80)
    print()
    print("COORDINATE SYSTEM: UTM Zone 17N (EPSG:32617) - NO TRANSFORMATION")
    print()
    
    summary = {
        "foscs_merged": 0,
        "msts_consolidated": 0,
        "foscs_removed": 0,
        "aerial_converted": 0,
        "msts_connected": 0,
        "onts_filtered": 0
    }
    
    # Rule 1: Merge nearby FOSCs
    merged_foscs, fosc_merges = merge_nearby_foscs(foscs, cables, max_distance=100.0)
    summary["foscs_merged"] = len(fosc_merges)
    
    # Rule 3: Remove redundant FOSCs
    # BUT: Keep FOSCs that are at cable junctions (connected_cables has 2+ cables)
    filtered_foscs, redundant_foscs = remove_redundant_foscs(merged_foscs, terminals, cables)
    
    # Don't remove FOSCs that are at junctions (they're needed for cable connections)
    junction_foscs = [f for f in filtered_foscs if len(f.get("connected_cables", [])) >= 2]
    redundant_foscs_filtered = [r for r in redundant_foscs if r["fosc_id"] not in [f.get("fosc_id") for f in junction_foscs]]
    
    if redundant_foscs_filtered:
        redundant_ids = {f["fosc_id"] for f in redundant_foscs_filtered}
        filtered_foscs = [f for f in filtered_foscs if f.get("fosc_id") not in redundant_ids]
        summary["foscs_removed"] = len(redundant_foscs_filtered)
    else:
        summary["foscs_removed"] = 0
    
    # Rule 4: Convert Aerial Terminals to MSTs and connect MSTs to FOSCs
    conversions = convert_aerial_to_mst_near_foscs(terminals, filtered_foscs, max_distance=1000.0)
    summary["aerial_converted"] = len([c for c in conversions if "Converted" in str(c)])
    summary["msts_connected"] = len([c for c in conversions if "Connected" in str(c)])
    
    # Rule 2: Consolidate nearby MSTs (after conversion, so we consolidate the new MSTs too)
    # Include specific merges: T0004278, T0004280 -> T0004266, T0004292 -> T0004473
    specific_merges = [("T0004266", "T0004278"), ("T0004266", "T0004280"), ("T0004473", "T0004292")]
    optimized_terminals, mst_consolidations = consolidate_nearby_msts(terminals, min_distance=250.0, specific_merges=specific_merges)
    summary["msts_consolidated"] = len(mst_consolidations)
    
    # After specific merges, ensure merged terminals are properly connected
    # Mark them so Rule 8 doesn't remove them immediately
    for terminal in optimized_terminals:
        if terminal.get("terminal_id") == "T0004266":
            # Ensure T0004266 is marked as properly connected if it has a cable
            if terminal.get("connected_cable_id"):
                terminal["created_by"] = "Rule 2 (specific merge - keep connected)"
    
    # Rule 5: Filter distant ONTs
    filtered_onts = filter_distant_onts(optimized_terminals, ont_geojson, max_drop_distance=1000.0)
    summary["onts_filtered"] = len(filtered_onts)
    
    # Rule 6: Fix ONT-to-FOSC connections (ONTs must connect to terminals, not FOSCs)
    optimized_terminals, fixed_onts = fix_ont_to_fosc_connections(
        optimized_terminals, filtered_foscs, ont_geojson, cables
    )
    summary["onts_fixed_from_fosc"] = len(fixed_onts)
    
    # Rule 7: Place FOSCs at cable junctions
    filtered_foscs, new_junction_foscs = place_foscs_at_cable_junctions(
        cables, filtered_foscs, optimized_terminals
    )
    summary["foscs_added_at_junctions"] = len(new_junction_foscs)
    
    # Rule 8: Fix isolated terminals (not on cables, not connected to FOSCs)
    # BUT: Before removing, check if they can be consolidated with nearby terminals (Rule 2)
    # Re-run Rule 2 to catch any terminals that should be consolidated before removal
    optimized_terminals, additional_consolidations = consolidate_nearby_msts(optimized_terminals, min_distance=250.0, specific_merges=None)
    summary["msts_consolidated"] += len(additional_consolidations)
    
    optimized_terminals, removed_isolated = fix_isolated_terminals(
        optimized_terminals, filtered_foscs, cables, max_cable_distance=50.0, max_fosc_distance=1000.0
    )
    summary["isolated_terminals_removed"] = len(removed_isolated)
    
    # Rule 9: Convert terminals to FOSCs (long non-straight cables)
    optimized_terminals, new_foscs_from_terminals = convert_terminal_to_fosc(
        optimized_terminals, cables, min_cable_length=500.0
    )
    filtered_foscs.extend(new_foscs_from_terminals)
    summary["terminals_converted_to_fosc"] = len(new_foscs_from_terminals)
    
    # Rule 10: Fix incorrect terminal connections
    optimized_terminals = fix_incorrect_terminal_connections(optimized_terminals, max_connection_distance=100.0)
    summary["terminal_connections_fixed"] = 1  # Placeholder
    
    # Rule 12: Split overloaded terminals at cable endpoints
    optimized_terminals, new_endpoint_msts = split_overloaded_terminals_at_cable_ends(
        optimized_terminals, filtered_foscs, cables, ont_geojson,
        max_onts_per_terminal=12, max_distance_to_endpoint=1000.0
    )
    summary["msts_added_at_endpoints"] = len(new_endpoint_msts)
    
    # Rule 13: Place MST near FOSC for specific ONTs
    # F0000962 needs MST for: O1007640, O1007649, O1007644, O1007647, O1007643, O1007650, O1007646, O1007564, O1007651, O1007611
    specific_onts_for_f0962 = ["O1007640", "O1007649", "O1007644", "O1007647", "O1007643", "O1007650", "O1007646", "O1007564", "O1007651", "O1007611"]
    optimized_terminals, new_fosc_mst = place_mst_near_fosc_for_onts(
        "F0000962", specific_onts_for_f0962, filtered_foscs, optimized_terminals, ont_geojson, cables, max_distance_from_fosc=500.0
    )
    if new_fosc_mst:
        summary["msts_added_near_foscs"] = 1
    else:
        summary["msts_added_near_foscs"] = 0
    
    # Rule 15: Convert FOSCs to MSTs when they should serve ONTs directly
    # Specific case: F0004456 should be MST and connect O1007875, O1007873
    optimized_terminals, filtered_foscs, fosc_to_mst_conversions = convert_fosc_to_mst_for_onts(
        filtered_foscs, optimized_terminals, ont_geojson, cables,
        specific_cases=[("F0004456", ["O1007875", "O1007873"])]
    )
    summary["foscs_converted_to_mst"] = len(fosc_to_mst_conversions)
    
    # Rule 14: Enforce MST placement rules - ALL MSTs must be on fiber cables and connected to FOSCs
    # This is a final validation rule that ensures all MSTs follow the placement requirements
    optimized_terminals, mst_fixes = enforce_mst_placement_rules(
        optimized_terminals, filtered_foscs, cables,
        max_cable_distance=50.0,
        max_fosc_distance=1000.0
    )
    summary["msts_fixed_placement"] = mst_fixes.get("fixed_msts", 0)
    
    # Rule 16: Ensure ALL terminals (MST and Aerial) and FOSCs are on fiber cables
    # This is a comprehensive rule that snaps everything to cables
    optimized_terminals, filtered_foscs, placement_fixes = enforce_all_on_cables(
        optimized_terminals, filtered_foscs, cables
    )
    summary["all_on_cables_fixed"] = placement_fixes.get("fixed_count", 0)
    
    # Rule 17: Optimize ONT-to-terminal connections (connect to nearest terminal with capacity)
    optimized_terminals, ont_optimization = optimize_ont_terminal_connections(
        optimized_terminals, ont_geojson, max_onts_per_terminal=12
    )
    summary["onts_reconnected"] = ont_optimization.get("reconnections", 0)
    
    # Rule 18: Merge underutilized MSTs (within 500m, one has 1-2 ONTs)
    optimized_terminals, mst_merges = merge_underutilized_msts(
        optimized_terminals,
        max_distance=500.0,
        max_onts_for_merge=2,
        max_onts_per_terminal=12
    )
    summary["underutilized_msts_merged"] = mst_merges.get("merges", 0)
    
    # Rule 19: Ensure ALL ONTs are connected (final cleanup)
    optimized_terminals, ont_connections = ensure_all_onts_connected(
        optimized_terminals, ont_geojson, cables,
        max_onts_per_terminal=12,
        max_drop_distance=2000.0
    )
    summary["unconnected_onts_found"] = ont_connections.get("unconnected_onts", 0)
    summary["unconnected_onts_connected"] = ont_connections.get("connected", 0)
    
    # Rule 20: Ensure all MSTs are connected to FOSCs via stub cables (routed along fiber)
    optimized_terminals, stub_connections = ensure_all_msts_connected_via_stub_cables(
        optimized_terminals, filtered_foscs, cables
    )
    summary["msts_connected_via_stub"] = stub_connections.get("connected", 0)
    
    print()
    print("=" * 80)
    print("OPTIMIZATION SUMMARY")
    print("=" * 80)
    print()
    print(f"FOSCs merged: {summary['foscs_merged']}")
    print(f"FOSCs removed (redundant): {summary['foscs_removed']}")
    print(f"FOSCs added at junctions: {summary['foscs_added_at_junctions']}")
    print(f"Terminals converted to FOSCs: {summary['terminals_converted_to_fosc']}")
    print(f"Isolated terminals removed: {summary['isolated_terminals_removed']}")
    print(f"Aerial Terminals converted to MST: {summary['aerial_converted']}")
    print(f"MSTs connected to FOSCs: {summary['msts_connected']}")
    print(f"MSTs consolidated: {summary['msts_consolidated']}")
    print(f"ONTs filtered (>1km): {summary['onts_filtered']}")
    print(f"ONTs fixed (was near FOSC): {summary['onts_fixed_from_fosc']}")
    print(f"MSTs added at cable endpoints: {summary['msts_added_at_endpoints']}")
    print(f"MSTs added near FOSCs: {summary.get('msts_added_near_foscs', 0)}")
    print(f"FOSCs converted to MSTs: {summary.get('foscs_converted_to_mst', 0)}")
    print(f"MSTs fixed (placement rules enforced): {summary.get('msts_fixed_placement', 0)}")
    print(f"All elements fixed (on cables): {summary.get('all_on_cables_fixed', 0)}")
    print(f"ONTs reconnected (to nearest): {summary.get('onts_reconnected', 0)}")
    print(f"Underutilized MSTs merged: {summary.get('underutilized_msts_merged', 0)}")
    print(f"Unconnected ONTs found: {summary.get('unconnected_onts_found', 0)}")
    print(f"Unconnected ONTs connected: {summary.get('unconnected_onts_connected', 0)}")
    print(f"MSTs connected via stub cables: {summary.get('msts_connected_via_stub', 0)}")
    print()
    print(f"Final terminals: {len(optimized_terminals)}")
    print(f"Final FOSCs: {len(filtered_foscs)}")
    print()
    
    return optimized_terminals, filtered_foscs, summary


def fix_ont_to_fosc_connections(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    cables: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Rule 6: Ensure ONTs are never directly connected to FOSCs.
    ONTs must connect to terminals (MST or Aerial Terminal), not FOSCs.
    
    If an ONT is found to be connected to a FOSC, find the nearest terminal
    and connect it there instead.
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        ont_geojson: ONT GeoJSON
        cables: List of cable dictionaries
    
    Returns:
        (updated_terminals, fixed_onts)
    """
    print()
    print("=" * 80)
    print("RULE 6: FIXING ONT-TO-FOSC CONNECTIONS")
    print("=" * 80)
    print()
    print("Ensuring ONTs connect to terminals, not FOSCs...")
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    # Build FOSC position map
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_positions[fosc_id] = fosc_pos_utm
    
    # Build terminal position map and connected ONTs
    terminal_positions = {}
    terminal_onts = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
            terminal_onts[terminal_id] = terminal.get("connected_onts", [])
    
    # Find ONTs that might be connected to FOSCs (not in any terminal's connected_onts)
    all_connected_onts = set()
    for terminal in terminals:
        all_connected_onts.update(terminal.get("connected_onts", []))
    
    # Check ONTs near FOSCs that aren't connected to terminals
    fixed_onts = []
    ont_to_fosc_distances = {}
    
    for ont_id, ont_pos in onts_by_id.items():
        if ont_id in all_connected_onts:
            continue  # Already connected to a terminal
        
        # Find nearest FOSC
        nearest_fosc_id = None
        min_fosc_dist = float('inf')
        for fosc_id, fosc_pos in fosc_positions.items():
            dist = euclidean_distance(ont_pos[0], ont_pos[1], fosc_pos[0], fosc_pos[1])
            if dist < min_fosc_dist:
                min_fosc_dist = dist
                nearest_fosc_id = fosc_id
        
        # If ONT is very close to a FOSC (<100m), it might be incorrectly connected
        if nearest_fosc_id and min_fosc_dist < 100.0:
            ont_to_fosc_distances[ont_id] = (nearest_fosc_id, min_fosc_dist)
    
    # Find nearest terminal for each ONT that's near a FOSC
    for ont_id, (fosc_id, fosc_dist) in ont_to_fosc_distances.items():
        ont_pos = onts_by_id.get(ont_id)
        if not ont_pos:
            continue
        
        # Find nearest terminal
        nearest_terminal_id = None
        min_term_dist = float('inf')
        for terminal_id, term_pos in terminal_positions.items():
            dist = euclidean_distance(ont_pos[0], ont_pos[1], term_pos[0], term_pos[1])
            if dist < min_term_dist:
                min_term_dist = dist
                nearest_terminal_id = terminal_id
        
        if nearest_terminal_id:
            # Add ONT to terminal
            terminal = next((t for t in terminals if t.get("terminal_id") == nearest_terminal_id), None)
            if terminal:
                if ont_id not in terminal.get("connected_onts", []):
                    terminal.setdefault("connected_onts", []).append(ont_id)
                    fixed_onts.append({
                        "ont_id": ont_id,
                        "was_near_fosc": fosc_id,
                        "fosc_distance": fosc_dist,
                        "now_connected_to": nearest_terminal_id,
                        "terminal_distance": min_term_dist
                    })
                    print(f"  ✓ Fixed {ont_id}: Was near FOSC {fosc_id} ({fosc_dist:.1f}m), now connected to terminal {nearest_terminal_id} ({min_term_dist:.1f}m)")
    
    print()
    print(f"Fixed {len(fixed_onts)} ONTs that were incorrectly near FOSCs")
    print()
    
    return terminals, [f["ont_id"] for f in fixed_onts]


def place_foscs_at_cable_junctions(
    cables: List[Dict[str, Any]],
    existing_foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 7: Place FOSCs at cable junctions where multiple cables meet.
    
    Detects junctions by finding common cable IDs in cable names.
    Example: "96FOC/F1000391/F1000397", "48FOC/F1000397/F1000398" → junction at F1000397
    
    Args:
        cables: List of cable dictionaries with 'id' field
        existing_foscs: List of existing FOSC dictionaries
        terminals: List of terminal dictionaries
    
    Returns:
        (updated_foscs, new_foscs)
    """
    print()
    print("=" * 80)
    print("RULE 7: PLACING FOSCs AT CABLE JUNCTIONS")
    print("=" * 80)
    print()
    print("Detecting cable junctions and placing FOSCs...")
    print()
    
    # Parse cable IDs to extract segments
    # Format: "SIZEFOC/ID1/ID2" or "SIZEFOC/ID1/TID"
    cable_segments = {}  # cable_id -> [segment1, segment2]
    cable_to_segments = {}  # segment_id -> [cable_ids]
    
    for cable in cables:
        cable_id = cable.get("id", "")
        if not cable_id:
            continue
        
        # Parse cable ID format: "SIZEFOC/ID1/ID2"
        parts = cable_id.split("/")
        if len(parts) >= 3:
            segment1 = parts[1]
            segment2 = parts[2]
            cable_segments[cable_id] = [segment1, segment2]
            
            # Track which cables use each segment
            for segment in [segment1, segment2]:
                if segment not in cable_to_segments:
                    cable_to_segments[segment] = []
                cable_to_segments[segment].append(cable_id)
    
    # Find junctions: segments used by 2+ cables
    junctions = {}
    for segment_id, cable_ids in cable_to_segments.items():
        if len(cable_ids) >= 2:
            junctions[segment_id] = cable_ids
    
    print(f"Found {len(junctions)} potential cable junctions")
    print()
    
    # Build existing FOSC positions
    existing_fosc_positions = {}
    for fosc in existing_foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            existing_fosc_positions[fosc_id] = fosc_pos_utm
    
    # Build terminal positions
    terminal_positions = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
    
    # For each junction, check if FOSC exists nearby
    new_foscs = []
    updated_foscs = existing_foscs.copy()
    
    for segment_id, cable_ids in junctions.items():
        # Find cables that form this junction
        junction_cables = [c for c in cables if c.get("id") in cable_ids]
        
        if len(junction_cables) < 2:
            continue
        
        # Find intersection point of cables
        # Try to find where cables meet (common endpoint or intersection)
        junction_point = None
        
        # Method 1: Find common endpoint
        all_endpoints = []
        for cable in junction_cables:
            coords = cable.get("coordinates", [])
            if coords:
                all_endpoints.append(coords[0])  # Start
                all_endpoints.append(coords[-1])  # End
        
        # Find endpoint used by multiple cables (within 10m)
        for i, ep1 in enumerate(all_endpoints):
            count = 1
            for j, ep2 in enumerate(all_endpoints):
                if i != j:
                    dist = euclidean_distance(ep1[0], ep1[1], ep2[0], ep2[1])
                    if dist < 10.0:
                        count += 1
            if count >= 2:
                junction_point = ep1
                break
        
        # Method 2: If no common endpoint, use centroid of cable endpoints
        if not junction_point and all_endpoints:
            avg_x = sum(ep[0] for ep in all_endpoints) / len(all_endpoints)
            avg_y = sum(ep[1] for ep in all_endpoints) / len(all_endpoints)
            junction_point = (avg_x, avg_y)
        
        if not junction_point:
            continue
        
        # Check if FOSC already exists nearby (<50m)
        fosc_exists = False
        for fosc_pos in existing_fosc_positions.values():
            dist = euclidean_distance(junction_point[0], junction_point[1], fosc_pos[0], fosc_pos[1])
            if dist < 50.0:
                fosc_exists = True
                break
        
        # Check if terminal exists nearby (<50m) - might be serving as junction
        terminal_exists = False
        for term_pos in terminal_positions.values():
            dist = euclidean_distance(junction_point[0], junction_point[1], term_pos[0], term_pos[1])
            if dist < 50.0:
                terminal_exists = True
                break
        
        if not fosc_exists and not terminal_exists:
            # Create new FOSC at junction
            fosc_id = f"F{segment_id}" if not segment_id.startswith("F") else f"F{segment_id[1:]}"
            # Ensure unique ID
            existing_ids = {f.get("fosc_id", "") for f in updated_foscs}
            counter = 1
            original_fosc_id = fosc_id
            while fosc_id in existing_ids:
                fosc_id = f"{original_fosc_id}_{counter}"
                counter += 1
            
            new_fosc = {
                "fosc_id": fosc_id,
                "position": [junction_point[0], junction_point[1]],
                "connected_cables": cable_ids,
                "junction_segment": segment_id,
                "created_by": "Rule 7 (cable junction)"
            }
            
            new_foscs.append(new_fosc)
            updated_foscs.append(new_fosc)
            
            print(f"  ✓ Created FOSC {fosc_id} at junction {segment_id}")
            print(f"    Cables: {', '.join(cable_ids[:3])}{'...' if len(cable_ids) > 3 else ''}")
    
    print()
    print(f"Created {len(new_foscs)} new FOSCs at cable junctions")
    print()
    
    return updated_foscs, new_foscs


def fix_isolated_terminals(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    max_cable_distance: float = 50.0,
    max_fosc_distance: float = 1000.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 8: Fix isolated terminals that are not on cables and not connected to FOSCs.
    
    If a terminal is isolated (not near any cable, not connected to FOSC), move its ONTs
    to the nearest terminal that is properly connected.
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        max_cable_distance: Maximum distance to consider terminal "on cable" (default 50m)
        max_fosc_distance: Maximum distance to consider terminal "near FOSC" (default 1000m)
    
    Returns:
        (updated_terminals, removed_terminals)
    """
    print()
    print("=" * 80)
    print("RULE 8: FIXING ISOLATED TERMINALS")
    print("=" * 80)
    print()
    print("Detecting terminals not on cables and not connected to FOSCs...")
    print()
    
    # Build FOSC positions
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_positions[fosc_id] = fosc_pos_utm
    
    # Build terminal positions
    terminal_positions = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
    
    isolated_terminals = []
    removed_terminals = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_fosc_id = terminal.get("connected_fosc_id")
        
        if not terminal_pos:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Check 1: Is terminal on a cable?
        on_cable = False
        for cable in cables:
            nearest_point, dist = find_nearest_point_on_cable(term_pos_utm, cable)
            if dist < max_cable_distance:
                on_cable = True
                break
        
        # Check 2: Is terminal connected to FOSC?
        connected_to_fosc = bool(connected_fosc_id)
        if not connected_to_fosc:
            # Check if near any FOSC
            for fosc_id, fosc_pos in fosc_positions.items():
                dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos[0], fosc_pos[1])
                if dist < max_fosc_distance:
                    connected_to_fosc = True
                    break
        
        # Terminal is isolated if not on cable and not connected to FOSC
        # BUT: Don't mark terminals that were just created/merged (they might need time to be connected)
        is_newly_merged = terminal.get("created_by") or terminal.get("split_from")
        
        if not on_cable and not connected_to_fosc and not is_newly_merged:
            isolated_terminals.append({
                "terminal_id": terminal_id,
                "terminal": terminal,
                "onts": terminal.get("connected_onts", [])
            })
    
    print(f"Found {len(isolated_terminals)} isolated terminals")
    print()
    
    # For each isolated terminal, move ONTs to nearest properly connected terminal
    for isolated_info in isolated_terminals:
        isolated_id = isolated_info["terminal_id"]
        isolated_term = isolated_info["terminal"]
        isolated_onts = isolated_info["onts"]
        isolated_pos = isolated_term.get("position")
        if isinstance(isolated_pos, list):
            isolated_pos = (isolated_pos[0], isolated_pos[1])
        
        if not isolated_onts:
            # No ONTs to move, just remove terminal
            removed_terminals.append(isolated_id)
            print(f"  ✓ Removed {isolated_id} (no ONTs)")
            continue
        
        # Find nearest properly connected terminal
        nearest_terminal_id = None
        min_dist = float('inf')
        
        for terminal in terminals:
            if terminal.get("terminal_id") == isolated_id:
                continue
            
            term_pos = terminal.get("position")
            if not term_pos:
                continue
            
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            
            # Check if this terminal is properly connected
            is_properly_connected = False
            
            # Check if on cable
            for cable in cables:
                nearest_point, dist = find_nearest_point_on_cable(term_pos_utm, cable)
                if dist < max_cable_distance:
                    is_properly_connected = True
                    break
            
            # Check if connected to FOSC
            if not is_properly_connected:
                if terminal.get("connected_fosc_id"):
                    is_properly_connected = True
            
            if is_properly_connected:
                dist = euclidean_distance(isolated_pos[0], isolated_pos[1], term_pos_utm[0], term_pos_utm[1])
                if dist < min_dist:
                    min_dist = dist
                    nearest_terminal_id = terminal.get("terminal_id")
        
        if nearest_terminal_id:
            # Move ONTs to nearest terminal
            target_terminal = next((t for t in terminals if t.get("terminal_id") == nearest_terminal_id), None)
            if target_terminal:
                target_terminal.setdefault("connected_onts", []).extend(isolated_onts)
                removed_terminals.append(isolated_id)
                print(f"  ✓ Moved {len(isolated_onts)} ONTs from {isolated_id} to {nearest_terminal_id} ({min_dist:.1f}m away)")
        else:
            print(f"  ⚠ Could not find nearby terminal for {isolated_id} ({len(isolated_onts)} ONTs)")
    
    # Remove isolated terminals
    updated_terminals = [t for t in terminals if t.get("terminal_id") not in removed_terminals]
    
    print()
    print(f"Removed {len(removed_terminals)} isolated terminals")
    print()
    
    return updated_terminals, removed_terminals


def convert_terminal_to_fosc(
    terminals: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    min_cable_length: float = 500.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 9: Convert terminals to FOSCs when they're on long, non-straight cables.
    
    Criteria:
    - Terminal is on a cable
    - Cable is long (>min_cable_length)
    - Cable is not straight (has significant curvature)
    
    Args:
        terminals: List of terminal dictionaries
        cables: List of cable dictionaries
        min_cable_length: Minimum cable length to consider (default 500m)
    
    Returns:
        (updated_terminals, new_foscs)
    """
    print()
    print("=" * 80)
    print("RULE 9: CONVERTING TERMINALS TO FOSCs (LONG NON-STRAIGHT CABLES)")
    print("=" * 80)
    print()
    print("Detecting terminals on long, non-straight cables...")
    print()
    
    new_foscs = []
    terminals_to_remove = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_cable_id = terminal.get("connected_cable_id")
        
        if not terminal_pos or not connected_cable_id:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Find the cable
        cable = next((c for c in cables if c.get("id") == connected_cable_id), None)
        if not cable:
            continue
        
        coords = cable.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        # Calculate cable length
        total_length = 0.0
        for i in range(len(coords) - 1):
            dist = euclidean_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
            total_length += dist
        
        # Check if cable is long enough
        if total_length < min_cable_length:
            continue
        
        # Calculate straight-line distance (start to end)
        start_coord = coords[0]
        end_coord = coords[-1]
        straight_distance = euclidean_distance(start_coord[0], start_coord[1], end_coord[0], end_coord[1])
        
        # Calculate curvature ratio (total_length / straight_distance)
        # If ratio > 1.2, cable is significantly curved
        curvature_ratio = total_length / straight_distance if straight_distance > 0 else 1.0
        
        if curvature_ratio > 1.2:
            # Convert terminal to FOSC
            fosc_id = f"F{terminal_id[1:]}" if terminal_id.startswith("T") else f"F{terminal_id}"
            
            new_fosc = {
                "fosc_id": fosc_id,
                "position": [term_pos_utm[0], term_pos_utm[1]],
                "connected_cables": [connected_cable_id],
                "converted_from": terminal_id,
                "created_by": "Rule 9 (long non-straight cable)",
                "cable_length": total_length,
                "curvature_ratio": curvature_ratio
            }
            
            new_foscs.append(new_fosc)
            terminals_to_remove.append(terminal_id)
            
            print(f"  ✓ Converted {terminal_id} to FOSC {fosc_id}")
            print(f"    Cable: {connected_cable_id} ({total_length:.1f}m, curvature: {curvature_ratio:.2f})")
    
    # Remove converted terminals
    updated_terminals = [t for t in terminals if t.get("terminal_id") not in terminals_to_remove]
    
    print()
    print(f"Converted {len(new_foscs)} terminals to FOSCs")
    print()
    
    return updated_terminals, new_foscs


def fix_incorrect_terminal_connections(
    terminals: List[Dict[str, Any]],
    max_connection_distance: float = 100.0
) -> List[Dict[str, Any]]:
    """
    Rule 10: Fix terminals that are incorrectly connected to each other.
    
    Terminals should not be directly connected to each other. They should connect
    to FOSCs or be on cables.
    
    Args:
        terminals: List of terminal dictionaries
        max_connection_distance: Maximum distance to consider terminals "connected" (default 100m)
    
    Returns:
        updated_terminals
    """
    print()
    print("=" * 80)
    print("RULE 10: FIXING INCORRECT TERMINAL CONNECTIONS")
    print("=" * 80)
    print()
    print("Detecting terminals incorrectly connected to each other...")
    print()
    
    # Build terminal positions
    terminal_positions = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
    
    fixed_pairs = []
    
    # Check for terminals that are very close to each other (might be incorrectly connected)
    for i, terminal1 in enumerate(terminals):
        terminal1_id = terminal1.get("terminal_id", "")
        terminal1_pos = terminal_positions.get(terminal1_id)
        
        if not terminal1_pos:
            continue
        
        for j, terminal2 in enumerate(terminals):
            if i >= j:
                continue
            
            terminal2_id = terminal2.get("terminal_id", "")
            terminal2_pos = terminal_positions.get(terminal2_id)
            
            if not terminal2_pos:
                continue
            
            dist = euclidean_distance(terminal1_pos[0], terminal1_pos[1], terminal2_pos[0], terminal2_pos[1])
            
            # If terminals are very close (<max_connection_distance) and both are MSTs or both are Aerial,
            # they might be incorrectly connected
            if dist < max_connection_distance:
                terminal1_type = terminal1.get("type", "")
                terminal2_type = terminal2.get("type", "")
                
                # Check if they have a connection (stub cable, etc.)
                terminal1_fosc = terminal1.get("connected_fosc_id")
                terminal2_fosc = terminal2.get("connected_fosc_id")
                
                # If both are MSTs and very close, they should be consolidated (Rule 2 handles this)
                # But if they're connected to each other somehow, that's wrong
                if terminal1_type == "MST" and terminal2_type == "MST":
                    # Rule 2 (consolidation) should handle this, but check if they're incorrectly linked
                    if terminal1.get("connected_to_terminal") == terminal2_id or terminal2.get("connected_to_terminal") == terminal1_id:
                        # Remove incorrect connection
                        terminal1.pop("connected_to_terminal", None)
                        terminal2.pop("connected_to_terminal", None)
                        fixed_pairs.append((terminal1_id, terminal2_id, dist))
                        print(f"  ✓ Removed incorrect connection between {terminal1_id} and {terminal2_id} ({dist:.1f}m)")
                
                # If terminals share the same FOSC but are very close, one might be redundant
                # This is handled by Rule 2 (consolidation), but we can flag it here
                if terminal1_fosc and terminal2_fosc and terminal1_fosc == terminal2_fosc:
                    if dist < 50.0:  # Very close and same FOSC - likely one should be removed
                        # Rule 2 should handle this, but we can log it
                        pass
    
    print()
    print(f"Fixed {len(fixed_pairs)} incorrect terminal connections")
    print()
    
    return terminals


def split_overloaded_terminals_at_cable_ends(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    max_onts_per_terminal: int = 12,
    max_distance_to_endpoint: float = 1000.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 12: Split overloaded terminals (>12 ONTs) by placing MSTs at unconnected cable endpoints.
    
    When a terminal has more than max_onts_per_terminal ONTs:
    1. Find cable endpoints that are not connected to FOSCs, terminals, or other cables
    2. Place new MSTs at those endpoints
    3. Redistribute ONTs to reduce load on original terminal
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        ont_geojson: ONT GeoJSON
        max_onts_per_terminal: Maximum ONTs per terminal (default 12)
        max_distance_to_endpoint: Maximum distance to consider cable endpoint (default 1000m)
    
    Returns:
        (updated_terminals, new_msts)
    """
    print()
    print("=" * 80)
    print("RULE 12: SPLITTING OVERLOADED TERMINALS AT CABLE ENDPOINTS")
    print("=" * 80)
    print()
    print(f"Splitting terminals with >{max_onts_per_terminal} ONTs by placing MSTs at cable endpoints...")
    print()
    
    # Build position maps
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_positions[fosc_id] = fosc_pos_utm
    
    terminal_positions = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    # Find cable endpoints that are not connected
    def is_endpoint_connected(endpoint: Tuple[float, float], threshold: float = 50.0) -> bool:
        """Check if an endpoint is connected to a FOSC or terminal."""
        # Check FOSCs
        for fosc_pos in fosc_positions.values():
            dist = euclidean_distance(endpoint[0], endpoint[1], fosc_pos[0], fosc_pos[1])
            if dist < threshold:
                return True
        
        # Check terminals
        for term_pos in terminal_positions.values():
            dist = euclidean_distance(endpoint[0], endpoint[1], term_pos[0], term_pos[1])
            if dist < threshold:
                return True
        
        return False
    
    # Find all cable endpoints
    cable_endpoints = []
    for cable in cables:
        coords = cable.get("coordinates", [])
        if len(coords) < 2:
            continue
        
        cable_id = cable.get("id", "")
        
        # Check start point
        start_point = (coords[0][0], coords[0][1])
        if not is_endpoint_connected(start_point):
            cable_endpoints.append({
                "cable_id": cable_id,
                "endpoint": start_point,
                "cable": cable,
                "is_start": True
            })
        
        # Check end point
        end_point = (coords[-1][0], coords[-1][1])
        if not is_endpoint_connected(end_point):
            cable_endpoints.append({
                "cable_id": cable_id,
                "endpoint": end_point,
                "cable": cable,
                "is_start": False
            })
    
    print(f"Found {len(cable_endpoints)} unconnected cable endpoints")
    print()
    
    # Find overloaded terminals
    overloaded_terminals = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        connected_onts = terminal.get("connected_onts", [])
        
        if len(connected_onts) > max_onts_per_terminal:
            terminal_pos = terminal.get("position")
            if terminal_pos:
                term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
                overloaded_terminals.append({
                    "terminal_id": terminal_id,
                    "terminal": terminal,
                    "onts": connected_onts,
                    "position": term_pos_utm,
                    "excess": len(connected_onts) - max_onts_per_terminal
                })
    
    print(f"Found {len(overloaded_terminals)} overloaded terminals")
    print()
    
    new_msts = []
    updated_terminals = terminals.copy()
    
    # For each overloaded terminal, find nearby cable endpoints and place MSTs
    for overload_info in overloaded_terminals:
        terminal_id = overload_info["terminal_id"]
        terminal = overload_info["terminal"]
        terminal_pos = overload_info["position"]
        excess_onts = overload_info["excess"]
        all_onts = overload_info["onts"]
        
        # Find nearby cable endpoints
        nearby_endpoints = []
        for endpoint_info in cable_endpoints:
            endpoint_pos = endpoint_info["endpoint"]
            dist = euclidean_distance(terminal_pos[0], terminal_pos[1], endpoint_pos[0], endpoint_pos[1])
            
            if dist <= max_distance_to_endpoint:
                nearby_endpoints.append((endpoint_info, dist))
        
        # Sort by distance
        nearby_endpoints.sort(key=lambda x: x[1])
        
        # Calculate how many MSTs we need (each MST can handle up to max_onts_per_terminal)
        num_msts_needed = (excess_onts + max_onts_per_terminal - 1) // max_onts_per_terminal
        
        # Place MSTs at nearby endpoints
        msts_placed = 0
        onts_to_redistribute = all_onts.copy()
        
        for endpoint_info, dist in nearby_endpoints[:num_msts_needed]:
            if msts_placed >= num_msts_needed:
                break
            
            endpoint_pos = endpoint_info["endpoint"]
            cable = endpoint_info["cable"]
            cable_id = endpoint_info["cable_id"]
            
            # Create new MST
            mst_id = f"T{len(updated_terminals) + len(new_msts) + 1:07d}"
            new_mst = {
                "terminal_id": mst_id,
                "type": "MST",
                "position": [endpoint_pos[0], endpoint_pos[1]],
                "connected_cable_id": cable_id,
                "connected_onts": [],
                "model": "MST12",
                "created_by": "Rule 12 (overloaded terminal split)",
                "split_from": terminal_id
            }
            
            # Assign ONTs to this MST (up to max_onts_per_terminal)
            onts_for_mst = []
            remaining_onts = []
            
            for ont_id in onts_to_redistribute:
                if len(onts_for_mst) < max_onts_per_terminal:
                    # Check if ONT is closer to new MST than original terminal
                    if ont_id in onts_by_id:
                        ont_pos = onts_by_id[ont_id]
                        dist_to_mst = euclidean_distance(ont_pos[0], ont_pos[1], endpoint_pos[0], endpoint_pos[1])
                        dist_to_terminal = euclidean_distance(ont_pos[0], ont_pos[1], terminal_pos[0], terminal_pos[1])
                        
                        # Assign to MST if closer or if we need to reduce load
                        if dist_to_mst < dist_to_terminal * 1.5 or len(terminal.get("connected_onts", [])) > max_onts_per_terminal:
                            onts_for_mst.append(ont_id)
                        else:
                            remaining_onts.append(ont_id)
                    else:
                        # If we don't have position, assign to reduce load
                        if len(onts_for_mst) < max_onts_per_terminal:
                            onts_for_mst.append(ont_id)
                        else:
                            remaining_onts.append(ont_id)
                else:
                    remaining_onts.append(ont_id)
            
            new_mst["connected_onts"] = onts_for_mst
            onts_to_redistribute = remaining_onts
            new_msts.append(new_mst)
            msts_placed += 1
            
            print(f"  ✓ Created MST {mst_id} at endpoint of {cable_id} ({dist:.1f}m from {terminal_id})")
            print(f"    Assigned {len(onts_for_mst)} ONTs to {mst_id}")
        
        # Update original terminal with remaining ONTs
        terminal["connected_onts"] = onts_to_redistribute
        
        print(f"  ✓ Reduced {terminal_id} from {len(all_onts)} to {len(onts_to_redistribute)} ONTs")
        print(f"    Created {msts_placed} new MSTs at cable endpoints")
    
    # Add new MSTs to terminals list
    updated_terminals.extend(new_msts)
    
    print()
    print(f"Created {len(new_msts)} new MSTs at cable endpoints")
    print(f"Split {len(overloaded_terminals)} overloaded terminals")
    print()
    
    return updated_terminals, new_msts


def place_mst_near_fosc_for_onts(
    fosc_id: str,
    ont_ids: List[str],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    cables: List[Dict[str, Any]],
    max_distance_from_fosc: float = 500.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 13: Place MST near FOSC to connect specific ONTs.
    
    When a FOSC needs to serve specific ONTs, place an MST near the FOSC
    and connect those ONTs to it.
    
    Args:
        fosc_id: FOSC ID to place MST near
        ont_ids: List of ONT IDs to connect
        foscs: List of FOSC dictionaries
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        cables: List of cable dictionaries
        max_distance_from_fosc: Maximum distance to place MST from FOSC (default 500m)
    
    Returns:
        (updated_terminals, new_mst_info)
    """
    print()
    print("=" * 80)
    print(f"RULE 13: PLACING MST NEAR FOSC {fosc_id} FOR SPECIFIC ONTs")
    print("=" * 80)
    print()
    
    # Find FOSC
    fosc = next((f for f in foscs if f.get("fosc_id") == fosc_id), None)
    if not fosc:
        print(f"  ⚠ FOSC {fosc_id} not found")
        return terminals, {}
    
    fosc_pos = fosc.get("position")
    if not fosc_pos:
        print(f"  ⚠ FOSC {fosc_id} has no position")
        return terminals, {}
    
    fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
    
    # Build ONT position map
    onts_by_id = {}
    ont_positions = []
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        if ont_id not in ont_ids:
            continue
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            ont_pos = (float(coords[0]), float(coords[1]))
            onts_by_id[ont_id] = ont_pos
            ont_positions.append(ont_pos)
    
    if not ont_positions:
        print(f"  ⚠ No ONT positions found for specified ONTs")
        return terminals, {}
    
    print(f"Found {len(ont_positions)} ONTs to connect")
    print()
    
    # Calculate centroid of ONTs
    from utils.spatial_utils import calculate_centroid
    ont_centroid = calculate_centroid(ont_positions)
    
    # Find nearest cable to centroid (for MST placement)
    nearest_cable = None
    min_cable_dist = float('inf')
    mst_position = ont_centroid
    
    for cable in cables:
        nearest_point, dist = find_nearest_point_on_cable(ont_centroid, cable)
        if dist < min_cable_dist:
            min_cable_dist = dist
            nearest_cable = cable
            mst_position = nearest_point
    
    # If no cable found nearby, place MST at centroid
    if min_cable_dist > 100.0:
        mst_position = ont_centroid
        nearest_cable_id = None
    else:
        nearest_cable_id = nearest_cable.get("id", "")
    
    # Ensure MST is within max_distance_from_fosc
    dist_to_fosc = euclidean_distance(mst_position[0], mst_position[1], fosc_pos_utm[0], fosc_pos_utm[1])
    if dist_to_fosc > max_distance_from_fosc:
        # Move MST closer to FOSC (on line from FOSC to centroid)
        ratio = max_distance_from_fosc / dist_to_fosc
        mst_position = (
            fosc_pos_utm[0] + (mst_position[0] - fosc_pos_utm[0]) * ratio,
            fosc_pos_utm[1] + (mst_position[1] - fosc_pos_utm[1]) * ratio
        )
    
    # Create new MST
    mst_id = f"T{len(terminals) + 1:07d}"
    new_mst = {
        "terminal_id": mst_id,
        "type": "MST",
        "position": [mst_position[0], mst_position[1]],
        "connected_cable_id": nearest_cable_id,
        "connected_fosc_id": fosc_id,
        "connected_onts": list(onts_by_id.keys()),
        "model": "MST12",
        "stub_cable_length": euclidean_distance(mst_position[0], mst_position[1], fosc_pos_utm[0], fosc_pos_utm[1]),
        "created_by": f"Rule 13 (MST near {fosc_id} for specific ONTs)"
    }
    
    # Remove ONTs from other terminals
    for terminal in terminals:
        connected_onts = terminal.get("connected_onts", [])
        updated_onts = [ont_id for ont_id in connected_onts if ont_id not in ont_ids]
        terminal["connected_onts"] = updated_onts
    
    # Add new MST
    updated_terminals = terminals + [new_mst]
    
    print(f"  ✓ Created MST {mst_id} near FOSC {fosc_id}")
    print(f"    Position: {mst_position}")
    print(f"    Connected {len(ont_ids)} ONTs")
    print(f"    Stub cable length: {new_mst['stub_cable_length']:.1f}m")
    print()
    
    return updated_terminals, {
        "mst_id": mst_id,
        "fosc_id": fosc_id,
        "ont_count": len(ont_ids),
        "position": mst_position
    }


def convert_fosc_to_mst_for_onts(
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    cables: List[Dict[str, Any]],
    specific_cases: List[Tuple[str, List[str]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Rule 15: Convert FOSCs to MSTs when they should serve ONTs directly.
    
    Some FOSCs should actually be MSTs that connect ONTs. This rule handles:
    1. Specific cases where a FOSC should be converted to MST (e.g., F0004456)
    2. Connect specified ONTs to the new MST
    3. Find a FOSC for the new MST to connect to (MSTs must connect to FOSCs)
    
    Args:
        foscs: List of FOSC dictionaries
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        cables: List of cable dictionaries
        specific_cases: List of (fosc_id, [ont_ids]) tuples for specific conversions
    
    Returns:
        (updated_terminals, updated_foscs, conversions)
    """
    print()
    print("=" * 80)
    print("RULE 15: CONVERTING FOSCs TO MSTs FOR ONT CONNECTIONS")
    print("=" * 80)
    print()
    print("Converting FOSCs to MSTs to connect ONTs...")
    print()
    
    if not specific_cases:
        return terminals, foscs, []
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    # Build FOSC position map
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_positions[fosc_id] = fosc_pos_utm
    
    conversions = []
    updated_foscs = []
    updated_terminals = list(terminals)
    
    for fosc_id, ont_ids in specific_cases:
        # Find the FOSC
        fosc = next((f for f in foscs if f.get("fosc_id") == fosc_id), None)
        if not fosc:
            print(f"  ⚠ FOSC {fosc_id} not found")
            continue
        
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            print(f"  ⚠ FOSC {fosc_id} has no position")
            continue
        
        fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
        
        # Check which ONTs exist and are not already connected
        valid_ont_ids = []
        for ont_id in ont_ids:
            if ont_id in onts_by_id:
                # Check if already connected to a terminal
                already_connected = any(ont_id in t.get("connected_onts", []) for t in updated_terminals)
                if not already_connected:
                    valid_ont_ids.append(ont_id)
                else:
                    print(f"  ⚠ {ont_id} is already connected to a terminal")
            else:
                print(f"  ⚠ {ont_id} not found in ONT data")
        
        if not valid_ont_ids:
            print(f"  ⚠ No valid ONTs to connect for FOSC {fosc_id}")
            continue
        
        # Find nearest cable to FOSC position (MST must be on cable)
        nearest_cable = None
        nearest_point = None
        min_cable_dist = float('inf')
        nearest_cable_id = None
        
        for cable in cables:
            nearest_point_candidate, dist = find_nearest_point_on_cable(fosc_pos_utm, cable)
            if dist < min_cable_dist:
                min_cable_dist = dist
                nearest_cable = cable
                nearest_point = nearest_point_candidate
                nearest_cable_id = cable.get("id", "")
        
        # Use FOSC position or snap to cable
        mst_position = fosc_pos_utm
        if nearest_cable and min_cable_dist < 50.0:
            mst_position = nearest_point
        
        # Find nearest FOSC for the new MST to connect to (MSTs must connect to FOSCs)
        nearest_fosc_id = None
        min_fosc_dist = float('inf')
        
        for other_fosc_id, other_fosc_pos in fosc_positions.items():
            if other_fosc_id == fosc_id:
                continue  # Don't connect to itself
            dist = euclidean_distance(mst_position[0], mst_position[1], other_fosc_pos[0], other_fosc_pos[1])
            if dist < min_fosc_dist:
                min_fosc_dist = dist
                nearest_fosc_id = other_fosc_id
        
        # Create new MST
        mst_id = fosc_id.replace("F", "T")  # Convert F0004456 to T0004456
        new_mst = {
            "terminal_id": mst_id,
            "type": "MST",
            "model": "MST12",
            "position": [mst_position[0], mst_position[1]],
            "connected_cable_id": nearest_cable_id,
            "connected_fosc_id": nearest_fosc_id,
            "connected_onts": valid_ont_ids,
            "ont_count": len(valid_ont_ids),
            "port_limit": 12,
            "stub_cable_length": min_fosc_dist if nearest_fosc_id else None,
            "created_by": f"Rule 15 (Converted FOSC {fosc_id} to MST)"
        }
        
        # Remove ONTs from other terminals if they were connected
        for terminal in updated_terminals:
            connected_onts = terminal.get("connected_onts", [])
            updated_onts = [ont_id for ont_id in connected_onts if ont_id not in valid_ont_ids]
            terminal["connected_onts"] = updated_onts
        
        # Remove FOSC from list
        updated_foscs = [f for f in foscs if f.get("fosc_id") != fosc_id]
        
        # Add new MST
        updated_terminals.append(new_mst)
        
        conversions.append({
            "fosc_id": fosc_id,
            "mst_id": mst_id,
            "ont_count": len(valid_ont_ids),
            "connected_to_fosc": nearest_fosc_id,
            "stub_length": min_fosc_dist if nearest_fosc_id else None
        })
        
        print(f"  ✓ Converted FOSC {fosc_id} to MST {mst_id}")
        print(f"    Connected {len(valid_ont_ids)} ONTs: {', '.join(valid_ont_ids)}")
        if nearest_fosc_id:
            print(f"    Connected to FOSC {nearest_fosc_id} (stub: {min_fosc_dist:.1f}m)")
        if nearest_cable_id:
            print(f"    On cable: {nearest_cable_id}")
        print()
    
    return updated_terminals, updated_foscs, conversions


def enforce_mst_placement_rules(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    max_cable_distance: float = 50.0,
    max_fosc_distance: float = 1000.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 14: Enforce MST placement rules - ALL MSTs must be on fiber cables and connected to FOSCs.
    
    This rule ensures:
    1. All MSTs are placed ON fiber cables (within max_cable_distance, snap to cable if needed)
    2. All MSTs are connected to FOSCs via stub cables (find nearest FOSC if not connected)
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        max_cable_distance: Maximum distance to consider MST "on cable" (default 50m)
        max_fosc_distance: Maximum distance to connect MST to FOSC (default 1000m)
    
    Returns:
        (updated_terminals, summary)
    """
    print()
    print("=" * 80)
    print("RULE 14: ENFORCING MST PLACEMENT RULES")
    print("=" * 80)
    print()
    print("Ensuring ALL MSTs are on fiber cables and connected to FOSCs...")
    print()
    
    # Build FOSC position map
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_positions[fosc_id] = fosc_pos_utm
    
    # Process each terminal
    updated_terminals = []
    fixes_applied = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("terminal_type", "").upper()
        terminal_type_alt = terminal.get("type", "").upper()
        
        # Only process MSTs - check both "terminal_type" and "type" fields
        if terminal_type != "MST" and terminal_type_alt != "MST":
            updated_terminals.append(terminal)
            continue
        
        terminal_pos = terminal.get("position")
        
        if not terminal_pos:
            print(f"  ⚠ Skipping {terminal_id}: No position")
            updated_terminals.append(terminal)
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        connected_cable_id = terminal.get("connected_cable_id", "")
        connected_fosc_id = terminal.get("connected_fosc_id", "")
        
        fixes = []
        
        # Fix 1: Ensure MST is on a fiber cable
        nearest_cable = None
        nearest_point = None
        min_cable_dist = float('inf')
        nearest_cable_id = None
        
        # Check if already has a connected cable
        if connected_cable_id:
            connected_cable = next((c for c in cables if c.get("id") == connected_cable_id), None)
            if connected_cable:
                nearest_point, dist = find_nearest_point_on_cable(term_pos_utm, connected_cable)
                if dist < max_cable_distance:
                    nearest_cable = connected_cable
                    min_cable_dist = dist
                    nearest_cable_id = connected_cable_id
        
        # If not on connected cable, find nearest cable
        if min_cable_dist >= max_cable_distance:
            for cable in cables:
                nearest_point_candidate, dist = find_nearest_point_on_cable(term_pos_utm, cable)
                if dist < min_cable_dist:
                    min_cable_dist = dist
                    nearest_cable = cable
                    nearest_point = nearest_point_candidate
                    nearest_cable_id = cable.get("id", "")
        
        # ALWAYS snap MST to nearest cable (even if far) - MSTs MUST be on cables
        if nearest_cable and nearest_point:
            # Always move to cable, regardless of distance
            terminal["position"] = [nearest_point[0], nearest_point[1]]
            if min_cable_dist < 1.0:
                # Already on cable
                pass
            elif min_cable_dist < max_cable_distance:
                fixes.append(f"Snapped to cable {nearest_cable_id} (was {min_cable_dist:.1f}m away)")
            else:
                fixes.append(f"Snapped to cable {nearest_cable_id} (was {min_cable_dist:.1f}m away - moved to cable)")
            
            terminal["connected_cable_id"] = nearest_cable_id
            terminal["distance_to_cable_m"] = 0.0  # Now on cable
        else:
            # No cable found - this is a critical error
            print(f"  ⚠ {terminal_id}: No cable found in network")
            fixes.append(f"ERROR: No cable found in network")
        
        # Fix 2: Ensure MST is connected to a FOSC
        if not connected_fosc_id or connected_fosc_id not in fosc_positions:
            # Find nearest FOSC
            nearest_fosc_id = None
            min_fosc_dist = float('inf')
            
            for fosc_id, fosc_pos in fosc_positions.items():
                dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos[0], fosc_pos[1])
                if dist < min_fosc_dist:
                    min_fosc_dist = dist
                    nearest_fosc_id = fosc_id
            
            # ALWAYS connect to nearest FOSC (even if beyond max_fosc_distance) - MSTs MUST connect to FOSCs
            if nearest_fosc_id:
                terminal["connected_fosc_id"] = nearest_fosc_id
                terminal["stub_cable_length"] = min_fosc_dist
                if min_fosc_dist <= max_fosc_distance:
                    fixes.append(f"Connected to FOSC {nearest_fosc_id} ({min_fosc_dist:.1f}m)")
                else:
                    fixes.append(f"Connected to FOSC {nearest_fosc_id} ({min_fosc_dist:.1f}m - beyond normal range but connected)")
            else:
                print(f"  ⚠ {terminal_id}: No FOSC found in network")
                fixes.append(f"ERROR: No FOSC found in network")
        
        if fixes:
            fixes_applied.append({
                "terminal_id": terminal_id,
                "fixes": fixes
            })
            print(f"  ✓ Fixed {terminal_id}:")
            for fix in fixes:
                print(f"    - {fix}")
        
        updated_terminals.append(terminal)
    
    print()
    print(f"Applied fixes to {len(fixes_applied)} MSTs")
    print()
    
    return updated_terminals, {
        "fixed_msts": len(fixes_applied),
        "fixes": fixes_applied
    }


def enforce_all_on_cables(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    max_distance: float = 50.0
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 16: Ensure ALL terminals (MST and Aerial) and FOSCs are placed ON fiber cables.
    
    This rule ensures that:
    1. ALL MSTs are on fiber cables (snap to nearest cable)
    2. ALL Aerial Terminals are on fiber cables (snap to nearest cable)
    3. ALL FOSCs are on fiber cables (snap to nearest cable)
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        max_distance: Maximum distance to consider "on cable" (default 50m)
    
    Returns:
        (updated_terminals, updated_foscs, summary)
    """
    print()
    print("=" * 80)
    print("RULE 16: ENFORCING ALL TERMINALS AND FOSCs ON FIBER CABLES")
    print("=" * 80)
    print()
    print("Ensuring ALL terminals (MST and Aerial) and FOSCs are on fiber cables...")
    print()
    
    fixes_applied = []
    
    # Process terminals
    updated_terminals = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("type", "").upper()
        terminal_pos = terminal.get("position")
        
        if not terminal_pos:
            updated_terminals.append(terminal)
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        # Find nearest cable
        nearest_cable = None
        nearest_point = None
        min_cable_dist = float('inf')
        nearest_cable_id = None
        
        for cable in cables:
            nearest_point_candidate, dist = find_nearest_point_on_cable(term_pos_utm, cable)
            if dist < min_cable_dist:
                min_cable_dist = dist
                nearest_cable = cable
                nearest_point = nearest_point_candidate
                nearest_cable_id = cable.get("id", "")
        
        # ALWAYS snap to cable (regardless of distance)
        if nearest_cable and nearest_point:
            if min_cable_dist > 1.0:
                terminal["position"] = [nearest_point[0], nearest_point[1]]
                terminal["connected_cable_id"] = nearest_cable_id
                terminal["distance_to_cable_m"] = 0.0
                fixes_applied.append({
                    "type": terminal_type,
                    "id": terminal_id,
                    "action": f"Snapped to cable {nearest_cable_id} (was {min_cable_dist:.1f}m away)"
                })
                print(f"  ✓ {terminal_id} ({terminal_type}): Snapped to cable {nearest_cable_id} (was {min_cable_dist:.1f}m away)")
            else:
                # Already on cable, just ensure connected_cable_id is set
                if not terminal.get("connected_cable_id"):
                    terminal["connected_cable_id"] = nearest_cable_id
                    terminal["distance_to_cable_m"] = 0.0
        
        updated_terminals.append(terminal)
    
    # Process FOSCs
    updated_foscs = []
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        
        if not fosc_pos:
            updated_foscs.append(fosc)
            continue
        
        fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
        
        # Find nearest cable
        nearest_cable = None
        nearest_point = None
        min_cable_dist = float('inf')
        nearest_cable_id = None
        
        for cable in cables:
            nearest_point_candidate, dist = find_nearest_point_on_cable(fosc_pos_utm, cable)
            if dist < min_cable_dist:
                min_cable_dist = dist
                nearest_cable = cable
                nearest_point = nearest_point_candidate
                nearest_cable_id = cable.get("id", "")
        
        # ALWAYS snap to cable (regardless of distance) or ensure connected_cables is set
        if nearest_cable and nearest_point:
            connected_cables = fosc.get("connected_cables", [])
            needs_fix = False
            fix_action = ""
            
            if min_cable_dist > 1.0:
                # Move FOSC to cable
                fosc["position"] = [nearest_point[0], nearest_point[1]]
                needs_fix = True
                fix_action = f"Snapped to cable {nearest_cable_id} (was {min_cable_dist:.1f}m away)"
            
            # Ensure connected_cables includes this cable
            if nearest_cable_id not in connected_cables:
                if not connected_cables:
                    connected_cables = []
                connected_cables.append(nearest_cable_id)
                fosc["connected_cables"] = connected_cables
                if not needs_fix:
                    needs_fix = True
                    fix_action = f"Added cable {nearest_cable_id} to connected_cables"
            
            if needs_fix:
                fixes_applied.append({
                    "type": "FOSC",
                    "id": fosc_id,
                    "action": fix_action
                })
                print(f"  ✓ {fosc_id} (FOSC): {fix_action}")
        
        updated_foscs.append(fosc)
    
    print()
    print(f"Applied fixes to {len(fixes_applied)} elements")
    print()
    
    return updated_terminals, updated_foscs, {
        "fixed_count": len(fixes_applied),
        "fixes": fixes_applied
    }


def optimize_ont_terminal_connections(
    terminals: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    max_onts_per_terminal: int = 12
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 17: Optimize ONT-to-terminal connections based on distance and capacity.
    
    This rule ensures each ONT is connected to the nearest terminal that has capacity (≤12 ONTs).
    If an ONT is connected to a distant terminal but a closer terminal with capacity exists,
    reconnect the ONT to the closer terminal.
    
    Args:
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        max_onts_per_terminal: Maximum ONTs per terminal (default 12)
    
    Returns:
        (updated_terminals, summary)
    """
    print()
    print("=" * 80)
    print("RULE 17: OPTIMIZING ONT-TO-TERMINAL CONNECTIONS")
    print("=" * 80)
    print()
    print("Reconnecting ONTs to nearest terminals with capacity (≤12 ONTs)...")
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    # Build terminal position and ONT map
    terminal_positions = {}
    terminal_onts = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
            terminal_onts[terminal_id] = terminal.get("connected_onts", [])
    
    # Process each ONT
    reconnections = []
    updated_terminals = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal_positions.get(terminal_id)
        if not terminal_pos:
            updated_terminals.append(terminal)
            continue
        
        connected_onts = list(terminal.get("connected_onts", []))
        updated_onts = []
        
        for ont_id in connected_onts:
            ont_pos = onts_by_id.get(ont_id)
            if not ont_pos:
                updated_onts.append(ont_id)  # Keep if ONT position not found
                continue
            
            # Find nearest terminal with capacity
            nearest_terminal_id = None
            min_dist = float('inf')
            
            for other_term_id, other_term_pos in terminal_positions.items():
                # Skip if terminal is at capacity
                other_onts = terminal_onts.get(other_term_id, [])
                if len(other_onts) >= max_onts_per_terminal:
                    continue
                
                # Calculate distance
                dist = euclidean_distance(ont_pos[0], ont_pos[1], other_term_pos[0], other_term_pos[1])
                if dist < min_dist:
                    min_dist = dist
                    nearest_terminal_id = other_term_id
            
            # Check current terminal distance
            current_dist = euclidean_distance(ont_pos[0], ont_pos[1], terminal_pos[0], terminal_pos[1])
            
            # Reconnect if there's a closer terminal with capacity
            if nearest_terminal_id and nearest_terminal_id != terminal_id and min_dist < current_dist:
                # Remove from current terminal
                # (Don't add to updated_onts)
                
                # Add to nearest terminal
                nearest_terminal = next((t for t in terminals if t.get("terminal_id") == nearest_terminal_id), None)
                if nearest_terminal:
                    if ont_id not in nearest_terminal.get("connected_onts", []):
                        nearest_terminal.setdefault("connected_onts", []).append(ont_id)
                        terminal_onts[nearest_terminal_id] = nearest_terminal.get("connected_onts", [])
                        
                        reconnections.append({
                            "ont_id": ont_id,
                            "from_terminal": terminal_id,
                            "to_terminal": nearest_terminal_id,
                            "old_distance": current_dist,
                            "new_distance": min_dist,
                            "savings": current_dist - min_dist
                        })
                        print(f"  ✓ {ont_id}: {terminal_id} ({current_dist:.1f}m) → {nearest_terminal_id} ({min_dist:.1f}m, saved {current_dist - min_dist:.1f}m)")
            else:
                # Keep current connection
                updated_onts.append(ont_id)
        
        # Update terminal's connected ONTs
        terminal["connected_onts"] = updated_onts
        updated_terminals.append(terminal)
    
    print()
    print(f"Reconnected {len(reconnections)} ONTs to closer terminals")
    print()
    
    return updated_terminals, {
        "reconnections": len(reconnections),
        "details": reconnections
    }


def merge_underutilized_msts(
    terminals: List[Dict[str, Any]],
    max_distance: float = 500.0,
    max_onts_for_merge: int = 2,
    max_onts_per_terminal: int = 12
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 18: Merge underutilized MSTs that are nearby.
    
    If two MSTs are within max_distance (default 500m) and one has ≤max_onts_for_merge ONTs (default 2),
    merge them into a single MST (if combined ONTs ≤ 12).
    
    This optimizes deployment by consolidating underutilized MSTs that are close together.
    
    Args:
        terminals: List of terminal dictionaries
        max_distance: Maximum distance to consider merging (default 500m)
        max_onts_for_merge: Maximum ONTs for a terminal to be considered "underutilized" (default 2)
        max_onts_per_terminal: Maximum ONTs per terminal after merge (default 12)
    
    Returns:
        (updated_terminals, summary)
    """
    print()
    print("=" * 80)
    print("RULE 18: MERGING UNDERUTILIZED MSTs")
    print("=" * 80)
    print()
    print(f"Merging MSTs within {max_distance}m where one has ≤{max_onts_for_merge} ONTs...")
    print()
    
    # Get all MSTs
    msts = [t for t in terminals if t.get("type") == "MST"]
    
    # Build position map
    mst_positions = {}
    mst_onts = {}
    for mst in msts:
        mst_id = mst.get("terminal_id", "")
        mst_pos = mst.get("position")
        if mst_pos:
            mst_pos_utm = (mst_pos[0], mst_pos[1]) if isinstance(mst_pos, list) else mst_pos
            mst_positions[mst_id] = mst_pos_utm
            mst_onts[mst_id] = mst.get("connected_onts", [])
    
    # Find underutilized MSTs (1-2 ONTs)
    underutilized_msts = [
        mst for mst in msts 
        if 1 <= len(mst.get("connected_onts", [])) <= max_onts_for_merge
    ]
    
    merges = []
    terminals_to_remove = set()
    
    for small_mst in underutilized_msts:
        small_id = small_mst.get("terminal_id", "")
        if small_id in terminals_to_remove:
            continue
        
        small_pos = mst_positions.get(small_id)
        if not small_pos:
            continue
        
        small_onts = mst_onts.get(small_id, [])
        small_ont_count = len(small_onts)
        
        # Find nearby MSTs within max_distance
        best_merge = None
        min_dist = float('inf')
        
        for other_mst in msts:
            other_id = other_mst.get("terminal_id", "")
            if other_id == small_id or other_id in terminals_to_remove:
                continue
            
            other_pos = mst_positions.get(other_id)
            if not other_pos:
                continue
            
            dist = euclidean_distance(small_pos[0], small_pos[1], other_pos[0], other_pos[1])
            
            if dist <= max_distance:
                other_onts = mst_onts.get(other_id, [])
                other_ont_count = len(other_onts)
                combined_count = small_ont_count + other_ont_count
                
                # Only merge if combined count ≤ 12
                if combined_count <= max_onts_per_terminal:
                    # Prefer closer terminal, or terminal with more ONTs if similar distance
                    if dist < min_dist or (dist < min_dist + 50.0 and other_ont_count > small_ont_count):
                        min_dist = dist
                        best_merge = (other_id, other_mst, dist, other_ont_count, combined_count)
        
        # Perform merge
        if best_merge:
            other_id, other_mst, dist, other_ont_count, combined_count = best_merge
            
            # Merge ONTs from small MST into other MST
            other_mst.setdefault("connected_onts", []).extend(small_onts)
            terminals_to_remove.add(small_id)
            
            merges.append({
                "removed": small_id,
                "kept": other_id,
                "distance": dist,
                "removed_onts": small_ont_count,
                "kept_onts_before": other_ont_count,
                "kept_onts_after": combined_count
            })
            
            print(f"  ✓ Merged {small_id} ({small_ont_count} ONTs) into {other_id} ({other_ont_count} → {combined_count} ONTs, {dist:.1f}m away)")
    
    # Remove merged terminals
    updated_terminals = [t for t in terminals if t.get("terminal_id") not in terminals_to_remove]
    
    print()
    print(f"Merged {len(merges)} underutilized MSTs")
    print()
    
    return updated_terminals, {
        "merges": len(merges),
        "details": merges
    }


def ensure_all_onts_connected(
    terminals: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    cables: List[Dict[str, Any]],
    max_onts_per_terminal: int = 12,
    max_drop_distance: float = 2000.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 19: Ensure ALL ONTs are connected to terminals.
    
    This is a final cleanup rule that runs after all other rules to ensure no ONT is left unconnected.
    For each unconnected ONT, finds the best terminal/MST based on:
    1. Distance (nearest)
    2. Capacity (≤12 ONTs)
    3. Terminal type (prefer MST if available)
    
    Args:
        terminals: List of terminal dictionaries
        ont_geojson: ONT GeoJSON
        cables: List of cable dictionaries (for terminal placement context)
        max_onts_per_terminal: Maximum ONTs per terminal (default 12)
        max_drop_distance: Maximum drop cable distance (default 2000m)
    
    Returns:
        (updated_terminals, summary)
    """
    print()
    print("=" * 80)
    print("RULE 19: ENSURING ALL ONTs ARE CONNECTED")
    print("=" * 80)
    print()
    print("Connecting unconnected ONTs to best terminals...")
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    # Find all connected ONTs
    connected_onts = set()
    for terminal in terminals:
        connected_onts.update(terminal.get("connected_onts", []))
    
    # Find unconnected ONTs
    unconnected_onts = [ont_id for ont_id in onts_by_id.keys() if ont_id not in connected_onts]
    
    if not unconnected_onts:
        print("  ✓ All ONTs are already connected")
        print()
        return terminals, {
            "unconnected_onts": 0,
            "connected": 0
        }
    
    print(f"Found {len(unconnected_onts)} unconnected ONTs")
    print()
    
    # Build terminal position and capacity map
    terminal_positions = {}
    terminal_capacities = {}
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        terminal_type = terminal.get("type", "")
        if terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            terminal_positions[terminal_id] = term_pos_utm
            current_onts = len(terminal.get("connected_onts", []))
            available_capacity = max_onts_per_terminal - current_onts
            terminal_capacities[terminal_id] = {
                "capacity": available_capacity,
                "type": terminal_type,
                "current_onts": current_onts
            }
    
    connections_made = []
    
    for ont_id in unconnected_onts:
        ont_pos = onts_by_id.get(ont_id)
        if not ont_pos:
            continue
        
        # Find best terminal for this ONT
        best_terminal_id = None
        min_dist = float('inf')
        best_score = float('inf')
        
        for terminal_id, term_pos in terminal_positions.items():
            capacity_info = terminal_capacities.get(terminal_id, {})
            available_capacity = capacity_info.get("capacity", 0)
            
            # Skip if terminal is at capacity
            if available_capacity <= 0:
                continue
            
            # Calculate distance
            dist = euclidean_distance(ont_pos[0], ont_pos[1], term_pos[0], term_pos[1])
            
            # Skip if too far
            if dist > max_drop_distance:
                continue
            
            # Score: prefer closer terminals, and MSTs over Aerial Terminals
            terminal_type = capacity_info.get("type", "")
            type_penalty = 0 if terminal_type == "MST" else 100  # Prefer MST
            
            score = dist + type_penalty
            
            if score < best_score:
                best_score = score
                min_dist = dist
                best_terminal_id = terminal_id
        
        # Connect ONT to best terminal
        if best_terminal_id:
            best_terminal = next((t for t in terminals if t.get("terminal_id") == best_terminal_id), None)
            if best_terminal:
                best_terminal.setdefault("connected_onts", []).append(ont_id)
                terminal_capacities[best_terminal_id]["capacity"] -= 1
                terminal_capacities[best_terminal_id]["current_onts"] += 1
                
                connections_made.append({
                    "ont_id": ont_id,
                    "terminal_id": best_terminal_id,
                    "distance": min_dist,
                    "terminal_type": terminal_capacities[best_terminal_id].get("type", "")
                })
                
                print(f"  ✓ Connected {ont_id} to {best_terminal_id} ({min_dist:.1f}m, {terminal_capacities[best_terminal_id].get('type', '')})")
        else:
            print(f"  ⚠ Could not connect {ont_id}: No terminal with capacity within {max_drop_distance}m")
    
    print()
    print(f"Connected {len(connections_made)} unconnected ONTs")
    print()
    
    return terminals, {
        "unconnected_onts": len(unconnected_onts),
        "connected": len(connections_made),
        "details": connections_made
    }


def ensure_all_msts_connected_via_stub_cables(
    terminals: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    cables: List[Dict[str, Any]],
    max_fosc_distance: float = 1000.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rule 20: Ensure all MSTs are connected to FOSCs via stub cables (routed along fiber cables).
    
    This rule ensures:
    1. All MSTs have a connected_fosc_id
    2. All MSTs have a stub_cable_length recorded
    3. Stub cables route along fiber cable infrastructure (handled in visualization)
    
    Args:
        terminals: List of terminal dictionaries
        foscs: List of FOSC dictionaries
        cables: List of cable dictionaries
        max_fosc_distance: Maximum distance to connect MST to FOSC (default 1000m)
    
    Returns:
        (updated_terminals, summary)
    """
    print()
    print("=" * 80)
    print("RULE 20: ENSURING ALL MSTs CONNECTED VIA STUB CABLES")
    print("=" * 80)
    print()
    print("Ensuring all MSTs are connected to FOSCs via stub cables...")
    print()
    
    # Build FOSC position map
    fosc_positions = {}
    for fosc in foscs:
        fosc_id = fosc.get("fosc_id", "")
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_positions[fosc_id] = fosc_pos_utm
    
    connections_made = []
    updated_terminals = []
    
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("type", "").upper()
        
        # Only process MSTs
        if terminal_type != "MST":
            updated_terminals.append(terminal)
            continue
        
        terminal_pos = terminal.get("position")
        if not terminal_pos:
            updated_terminals.append(terminal)
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        connected_fosc_id = terminal.get("connected_fosc_id", "")
        stub_cable_length = terminal.get("stub_cable_length")
        
        # Check if MST is already connected to a FOSC
        if connected_fosc_id and connected_fosc_id in fosc_positions:
            # Verify stub cable length is set
            if stub_cable_length is None:
                fosc_pos = fosc_positions[connected_fosc_id]
                dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos[0], fosc_pos[1])
                terminal["stub_cable_length"] = dist
                connections_made.append({
                    "terminal_id": terminal_id,
                    "fosc_id": connected_fosc_id,
                    "action": f"Added stub cable length: {dist:.1f}m"
                })
                print(f"  ✓ {terminal_id}: Added stub cable length to {connected_fosc_id} ({dist:.1f}m)")
            updated_terminals.append(terminal)
            continue
        
        # Find nearest FOSC
        nearest_fosc_id = None
        min_fosc_dist = float('inf')
        
        for fosc_id, fosc_pos in fosc_positions.items():
            dist = euclidean_distance(term_pos_utm[0], term_pos_utm[1], fosc_pos[0], fosc_pos[1])
            if dist < min_fosc_dist:
                min_fosc_dist = dist
                nearest_fosc_id = fosc_id
        
        # Connect to nearest FOSC if within range
        if nearest_fosc_id and min_fosc_dist <= max_fosc_distance:
            terminal["connected_fosc_id"] = nearest_fosc_id
            terminal["stub_cable_length"] = min_fosc_dist
            connections_made.append({
                "terminal_id": terminal_id,
                "fosc_id": nearest_fosc_id,
                "distance": min_fosc_dist,
                "action": f"Connected to FOSC {nearest_fosc_id} ({min_fosc_dist:.1f}m)"
            })
            print(f"  ✓ {terminal_id}: Connected to FOSC {nearest_fosc_id} ({min_fosc_dist:.1f}m)")
        else:
            if nearest_fosc_id:
                print(f"  ⚠ {terminal_id}: Nearest FOSC {nearest_fosc_id} is {min_fosc_dist:.1f}m away (beyond {max_fosc_distance}m limit)")
            else:
                print(f"  ⚠ {terminal_id}: No FOSC found in network")
        
        updated_terminals.append(terminal)
    
    print()
    print(f"Connected {len(connections_made)} MSTs to FOSCs via stub cables")
    print()
    
    return updated_terminals, {
        "connected": len(connections_made),
        "details": connections_made
    }
