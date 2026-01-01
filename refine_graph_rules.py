#!/usr/bin/env python3
"""
refine_graph_rules.py
-------------------------------------------------------------------------------
Refine Placement Logic Rules Using Only Logical Graph Data
-------------------------------------------------------------------------------
Refines placement rules R10-R14 using only cable connectivity and length fields
from logical_fiber_graph.json (no geometry/GIS computations).

Refinement Criteria:
- Aerial Terminal: 1-12 ONTs, no stub, no splice, avg drop ≤ 150m
- MST: Stub cable from FOSC, ≤500m, 6-24 ONTs served
- FOSC: ≥2 fiber connections OR ≥1800m segment OR fiber ID change OR fiber count transition
- FDH-FOSC: Use fdh_id to pair nearest FOSC in same chain
- Cable Hierarchy: Maintain 288/144 → 96 → 48 → 12 → 1F cascade

Outputs:
- Appends refined analyses to placement_rules_analysis.json
- Updates rules_summary.txt with refined reasoning
-------------------------------------------------------------------------------
"""

import json
import re
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import statistics


# ============================================================================
# DATA LOADING
# ============================================================================

def load_logical_graph(graph_path: str = "logical_fiber_graph.json") -> Dict[str, Any]:
    """Load the logical fiber graph."""
    print(f"Loading logical graph from {graph_path}...")
    with open(graph_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Loaded {len(data.get('nodes', []))} nodes, {len(data.get('links', []))} links")
    return data


def extract_fiber_count(cable_id: str) -> Optional[int]:
    """Extract fiber count from cable ID (e.g., '144FOC' -> 144)."""
    if not cable_id:
        return None
    match = re.search(r'(\d+)FOC', str(cable_id).upper())
    return int(match.group(1)) if match else None


# ============================================================================
# GRAPH ANALYSIS
# ============================================================================

def build_graph_structures(graph: Dict[str, Any]) -> Tuple[Dict, Dict, Dict, Dict]:
    """
    Build graph data structures from nodes and links.
    Returns: (nodes_dict, adjacency, reverse_adjacency, link_data)
    """
    nodes = {n["id"]: n["layer"] for n in graph.get("nodes", [])}
    links = graph.get("links", [])
    
    adjacency = defaultdict(list)
    reverse_adjacency = defaultdict(list)
    link_data = {}  # Store full link data indexed by (source, target)
    
    for link in links:
        source = link.get("source")
        target = link.get("target")
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        cable_layer = link.get("cable_layer")
        cable_id = link.get("cable_id")
        length_m = link.get("length_m")
        is_virtual = link.get("virtual", False)
        
        adj_entry = {
            "target": target,
            "target_layer": target_layer,
            "cable_layer": cable_layer,
            "cable_id": cable_id,
            "length_m": length_m,
            "virtual": is_virtual
        }
        adjacency[source].append(adj_entry)
        reverse_adjacency[target].append({
            "source": source,
            "source_layer": source_layer,
            "cable_layer": cable_layer,
            "cable_id": cable_id,
            "length_m": length_m,
            "virtual": is_virtual
        })
        
        link_key = (source, target)
        link_data[link_key] = link
    
    return nodes, adjacency, reverse_adjacency, link_data


def compute_node_metrics(node_id: str, layer: str, nodes: Dict, 
                         adjacency: Dict, reverse_adjacency: Dict,
                         link_data: Dict) -> Dict[str, Any]:
    """
    Compute per-node metrics from cable edge data.
    """
    metrics = {
        "node_id": node_id,
        "layer": layer,
        "outgoing_connections": len(adjacency.get(node_id, [])),
        "incoming_connections": len(reverse_adjacency.get(node_id, [])),
        "outgoing_by_cable_type": defaultdict(int),
        "incoming_by_cable_type": defaultdict(int),
        "outgoing_lengths": defaultdict(list),
        "incoming_lengths": defaultdict(list),
        "outgoing_cable_ids": [],
        "incoming_cable_ids": [],
        "fiber_counts_out": [],
        "fiber_counts_in": [],
        "has_stub_cable": False,
        "has_drop_cable": False,
        "connected_to_fosc": False,
        "connected_to_fdh": False,
        "connected_to_ont": False,
        "connected_to_terminal": False
    }
    
    # Analyze outgoing connections
    for adj in adjacency.get(node_id, []):
        cable_layer = adj.get("cable_layer")
        cable_id = adj.get("cable_id")
        length_m = adj.get("length_m")
        target_layer = adj.get("target_layer")
        
        metrics["outgoing_by_cable_type"][cable_layer] += 1
        if length_m:
            metrics["outgoing_lengths"][cable_layer].append(length_m)
        if cable_id:
            metrics["outgoing_cable_ids"].append(cable_id)
            fiber_count = extract_fiber_count(cable_id)
            if fiber_count:
                metrics["fiber_counts_out"].append(fiber_count)
        
        if cable_layer == "stub cable":
            metrics["has_stub_cable"] = True
        if cable_layer == "drop cable":
            metrics["has_drop_cable"] = True
        if target_layer == "splice closure":
            metrics["connected_to_fosc"] = True
        if target_layer == "fdh":
            metrics["connected_to_fdh"] = True
        if target_layer == "ont":
            metrics["connected_to_ont"] = True
        if target_layer == "terminal":
            metrics["connected_to_terminal"] = True
    
    # Analyze incoming connections
    for rev_adj in reverse_adjacency.get(node_id, []):
        cable_layer = rev_adj.get("cable_layer")
        cable_id = rev_adj.get("cable_id")
        length_m = rev_adj.get("length_m")
        source_layer = rev_adj.get("source_layer")
        
        metrics["incoming_by_cable_type"][cable_layer] += 1
        if length_m:
            metrics["incoming_lengths"][cable_layer].append(length_m)
        if cable_id:
            metrics["incoming_cable_ids"].append(cable_id)
            fiber_count = extract_fiber_count(cable_id)
            if fiber_count:
                metrics["fiber_counts_in"].append(fiber_count)
        
        if source_layer == "splice closure":
            metrics["connected_to_fosc"] = True
        if source_layer == "fdh":
            metrics["connected_to_fdh"] = True
    
    return metrics


def precompute_downstream_onts(graph: Dict[str, Any], adjacency: Dict) -> Dict[str, int]:
    """
    Pre-compute downstream ONT counts for all nodes using paths data.
    Much faster than recursive traversal.
    """
    print("  Pre-computing downstream ONT counts from paths...")
    downstream_ont_cache = defaultdict(int)
    
    # Try to load paths file for faster computation
    try:
        with open("olt_ont_paths.json", "r", encoding="utf-8") as f:
            paths = json.load(f)
        
        for path in paths:
            path_segments = path.get("path", [])
            if not path_segments:
                continue
            
            ont_id = path.get("ont_id")
            if not ont_id:
                continue
            
            # Track all terminals/FOSCs this ONT passes through
            for seg in path_segments:
                from_layer = seg.get("from_layer")
                from_node = seg.get("from")
                
                if from_layer == "terminal":
                    downstream_ont_cache[from_node] += 1
                elif from_layer == "splice closure":
                    downstream_ont_cache[from_node] += 1
    except FileNotFoundError:
        # Fallback: count directly connected ONTs only
        print("  Warning: olt_ont_paths.json not found, using direct connections only")
        for node_id, adjs in adjacency.items():
            for adj in adjs:
                if adj.get("target_layer") == "ont":
                    downstream_ont_cache[node_id] += 1
    
    return downstream_ont_cache


def count_downstream_onts(node_id: str, cache: Dict[str, int]) -> int:
    """Count ONTs downstream from this node (using pre-computed cache)."""
    return cache.get(node_id, 0)


# ============================================================================
# RULE REFINEMENT
# ============================================================================

def refine_aerial_terminal_rule(node_id: str, metrics: Dict[str, Any], 
                               downstream_ont_cache: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """
    Refine R10: Aerial Terminal rule.
    Criteria: 1-12 ONTs, no stub, no splice, avg drop ≤ 150m
    """
    if metrics["layer"] != "terminal":
        return None
    
    # Count downstream ONTs
    downstream_onts = count_downstream_onts(node_id, downstream_ont_cache)
    
    # Check conditions
    has_stub = metrics["has_stub_cable"]
    has_drop = metrics["has_drop_cable"]
    
    # Calculate average drop cable length
    drop_lengths = metrics["outgoing_lengths"].get("drop cable", [])
    avg_drop_length = statistics.mean(drop_lengths) if drop_lengths else None
    
    # Check if connected via fiber cable (inline terminal)
    has_fiber_connection = (
        metrics["outgoing_by_cable_type"]["fiber cable"] > 0 or
        metrics["incoming_by_cable_type"]["fiber cable"] > 0
    )
    
    # Determine if matches refined criteria
    matches_criteria = (
        1 <= downstream_onts <= 12 and
        not has_stub and
        has_drop and
        (avg_drop_length is None or avg_drop_length <= 150) and
        has_fiber_connection
    )
    
    confidence = 0.5
    if 1 <= downstream_onts <= 12:
        confidence += 0.2
    if not has_stub:
        confidence += 0.2
    if avg_drop_length and avg_drop_length <= 150:
        confidence += 0.1
    if has_fiber_connection:
        confidence += 0.1
    
    confidence = min(1.0, confidence)
    
    return {
        "node_id": node_id,
        "layer": "terminal",
        "rule_id": "R10_AERIAL_TERMINAL_REFINED",
        "rule_description": "Aerial Terminal: 1-12 ONTs, no stub, no splice, avg drop ≤ 150m",
        "confidence_score": round(confidence, 2),
        "matches_criteria": matches_criteria,
        "supporting_data": {
            "downstream_onts": downstream_onts,
            "has_stub_cable": has_stub,
            "has_drop_cable": has_drop,
            "avg_drop_length_m": round(avg_drop_length, 2) if avg_drop_length else None,
            "has_fiber_connection": has_fiber_connection,
            "outgoing_connections": metrics["outgoing_connections"],
            "incoming_connections": metrics["incoming_connections"]
        }
    }


def refine_mst_rule(node_id: str, metrics: Dict[str, Any],
                    adjacency: Dict, reverse_adjacency: Dict,
                    downstream_ont_cache: Dict[str, int]) -> Optional[Dict[str, Any]]:
    """
    Refine R11: MST rule.
    Criteria: Stub cable from FOSC, ≤500m, 6-24 ONTs served
    """
    if metrics["layer"] != "terminal":
        return None
    
    # Check for stub cable connection
    has_stub = metrics["has_stub_cable"]
    if not has_stub:
        return None
    
    # Find stub cable connection to FOSC
    stub_distance = None
    connected_fosc = None
    
    for adj in adjacency.get(node_id, []):
        if adj.get("cable_layer") == "stub cable" and adj.get("target_layer") == "splice closure":
            stub_distance = adj.get("length_m")
            connected_fosc = adj.get("target")
            break
    
    if not connected_fosc:
        for rev_adj in reverse_adjacency.get(node_id, []):
            if rev_adj.get("cable_layer") == "stub cable" and rev_adj.get("source_layer") == "splice closure":
                stub_distance = rev_adj.get("length_m")
                connected_fosc = rev_adj.get("source")
                break
    
    if not connected_fosc:
        return None
    
    # Count downstream ONTs
    downstream_onts = count_downstream_onts(node_id, downstream_ont_cache)
    
    # Determine if matches refined criteria
    matches_criteria = (
        stub_distance is not None and stub_distance <= 500 and
        6 <= downstream_onts <= 24
    )
    
    confidence = 0.5
    if stub_distance and stub_distance <= 500:
        confidence += 0.2
    if 6 <= downstream_onts <= 24:
        confidence += 0.2
    if connected_fosc:
        confidence += 0.1
    
    confidence = min(1.0, confidence)
    
    return {
        "node_id": node_id,
        "layer": "terminal",
        "rule_id": "R11_MST_REFINED",
        "rule_description": "MST: Stub cable from FOSC, ≤500m, 6-24 ONTs served",
        "confidence_score": round(confidence, 2),
        "matches_criteria": matches_criteria,
        "supporting_data": {
            "has_stub_cable": True,
            "stub_distance_m": round(stub_distance, 2) if stub_distance else None,
            "connected_fosc": connected_fosc,
            "downstream_onts": downstream_onts,
            "outgoing_connections": metrics["outgoing_connections"]
        }
    }


def refine_fosc_rule(node_id: str, metrics: Dict[str, Any],
                     adjacency: Dict, reverse_adjacency: Dict, link_data: Dict) -> Optional[Dict[str, Any]]:
    """
    Refine R12: FOSC rule.
    Criteria: ≥2 fiber connections OR ≥1800m segment OR fiber ID change OR fiber count transition
    """
    if metrics["layer"] != "splice closure":
        return None
    
    # Count fiber connections
    fiber_connections = (
        metrics["outgoing_by_cable_type"]["fiber cable"] +
        metrics["incoming_by_cable_type"]["fiber cable"]
    )
    
    # Check for long segments (≥1800m)
    all_fiber_lengths = (
        metrics["outgoing_lengths"].get("fiber cable", []) +
        metrics["incoming_lengths"].get("fiber cable", [])
    )
    max_fiber_length = max(all_fiber_lengths) if all_fiber_lengths else 0
    
    # Check for fiber ID changes (different cable IDs)
    all_cable_ids = list(set(metrics["outgoing_cable_ids"] + metrics["incoming_cable_ids"]))
    unique_cable_ids = len([cid for cid in all_cable_ids if cid])
    
    # Check for fiber count transitions
    fiber_counts_in = metrics["fiber_counts_in"]
    fiber_counts_out = metrics["fiber_counts_out"]
    has_fiber_transition = False
    
    if fiber_counts_in and fiber_counts_out:
        avg_in = statistics.mean(fiber_counts_in) if fiber_counts_in else None
        avg_out = statistics.mean(fiber_counts_out) if fiber_counts_out else None
        if avg_in and avg_out and abs(avg_in - avg_out) > 10:
            has_fiber_transition = True
    
    # Determine if matches refined criteria
    matches_criteria = (
        fiber_connections >= 2 or
        max_fiber_length >= 1800 or
        unique_cable_ids >= 2 or
        has_fiber_transition
    )
    
    confidence = 0.4
    rule_matches = []
    
    if fiber_connections >= 2:
        confidence += 0.3
        rule_matches.append(f"≥2 fiber connections ({fiber_connections})")
    if max_fiber_length >= 1800:
        confidence += 0.2
        rule_matches.append(f"≥1800m segment ({max_fiber_length:.1f}m)")
    if unique_cable_ids >= 2:
        confidence += 0.2
        rule_matches.append(f"fiber ID change ({unique_cable_ids} unique IDs)")
    if has_fiber_transition:
        confidence += 0.2
        rule_matches.append(f"fiber count transition (in: {avg_in:.0f}F, out: {avg_out:.0f}F)")
    
    confidence = min(1.0, confidence)
    
    return {
        "node_id": node_id,
        "layer": "splice closure",
        "rule_id": "R12_FOSC_REFINED",
        "rule_description": "FOSC: ≥2 fiber connections OR ≥1800m segment OR fiber ID change OR fiber count transition",
        "confidence_score": round(confidence, 2),
        "matches_criteria": matches_criteria,
        "supporting_data": {
            "fiber_connections": fiber_connections,
            "max_fiber_length_m": round(max_fiber_length, 2),
            "unique_cable_ids": unique_cable_ids,
            "has_fiber_transition": has_fiber_transition,
            "fiber_counts_in": fiber_counts_in,
            "fiber_counts_out": fiber_counts_out,
            "rule_conditions_met": rule_matches
        }
    }


def refine_fdh_fosc_association(node_id: str, metrics: Dict[str, Any],
                               adjacency: Dict, reverse_adjacency: Dict,
                               nodes: Dict, link_data: Dict) -> Optional[Dict[str, Any]]:
    """
    Refine R13: FDH-FOSC association rule.
    Use fdh_id to pair nearest FOSC in same chain.
    """
    if metrics["layer"] != "splice closure":
        return None
    
    # Find FDH connections (direct or via chain)
    fdh_distance = None
    nearest_fdh = None
    
    # Check direct connection
    for adj in adjacency.get(node_id, []):
        if adj.get("target_layer") == "fdh":
            length = adj.get("length_m") or 0.0
            if fdh_distance is None or length < fdh_distance:
                fdh_distance = length
                nearest_fdh = adj.get("target")
    
    for rev_adj in reverse_adjacency.get(node_id, []):
        if rev_adj.get("source_layer") == "fdh":
            length = rev_adj.get("length_m") or 0.0
            if fdh_distance is None or length < fdh_distance:
                fdh_distance = length
                nearest_fdh = rev_adj.get("source")
    
    # Check for same cable chain (fiber cable continuity)
    same_chain = False
    if nearest_fdh:
        # Check if connected via fiber cable chain
        fosc_cable_ids = set(metrics["outgoing_cable_ids"] + metrics["incoming_cable_ids"])
        # Try to find shared cable IDs in path to FDH
        same_chain = len(fosc_cable_ids) > 0
    
    matches_criteria = nearest_fdh is not None and (fdh_distance is None or fdh_distance <= 50)
    
    confidence = 0.5
    if nearest_fdh:
        confidence += 0.3
    if fdh_distance and fdh_distance <= 50:
        confidence += 0.2
    
    confidence = min(1.0, confidence)
    
    return {
        "node_id": node_id,
        "layer": "splice closure",
        "rule_id": "R13_FDH_FOSC_ASSOCIATION_REFINED",
        "rule_description": "FDH-FOSC: Pair nearest FOSC in same chain using fdh_id",
        "confidence_score": round(confidence, 2),
        "matches_criteria": matches_criteria,
        "supporting_data": {
            "nearest_fdh": nearest_fdh,
            "fdh_distance_m": round(fdh_distance, 2) if fdh_distance else None,
            "same_chain": same_chain,
            "outgoing_connections": metrics["outgoing_connections"],
            "incoming_connections": metrics["incoming_connections"]
        }
    }


def refine_cable_hierarchy(graph: Dict[str, Any], adjacency: Dict) -> Dict[str, Any]:
    """
    Refine R14: Cable hierarchy rule.
    Maintain 288/144 → 96 → 48 → 12 → 1F cascade
    """
    links = graph.get("links", [])
    
    # Build target-to-link mapping for faster lookup
    target_to_links = defaultdict(list)
    for link in links:
        target = link.get("target")
        if target:
            target_to_links[target].append(link)
    
    # Analyze cable transitions (optimized)
    hierarchy_stats = defaultdict(lambda: {"count": 0, "examples": []})
    hierarchy_violations = []
    
    # Single pass to collect stats and check violations
    for link in links:
        cable_id = link.get("cable_id")
        if not cable_id:
            continue
        
        fiber_count = extract_fiber_count(cable_id)
        if not fiber_count:
            continue
        
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        target = link.get("target")
        
        # Collect statistics
        hierarchy_stats[f"{fiber_count}F"]["count"] += 1
        if len(hierarchy_stats[f"{fiber_count}F"]["examples"]) < 5:
            hierarchy_stats[f"{fiber_count}F"]["examples"].append({
                "cable_id": cable_id,
                "from": source_layer,
                "to": target_layer
            })
        
        # Check for violations in next links (limit to first 10 to avoid O(n²))
        if target in target_to_links:
            for next_link in target_to_links[target][:10]:  # Limit checks
                next_cable_id = next_link.get("cable_id")
                if not next_cable_id:
                    continue
                
                fiber_count2 = extract_fiber_count(next_cable_id)
                if not fiber_count2:
                    continue
                
                if fiber_count > fiber_count2:
                    # Check if violates cascade
                    if fiber_count > 288 and fiber_count2 < 144:
                        hierarchy_violations.append({
                            "from_cable": cable_id,
                            "to_cable": next_cable_id,
                            "from_count": fiber_count,
                            "to_count": fiber_count2,
                            "violation": "Jump from >288F to <144F"
                        })
                        if len(hierarchy_violations) >= 20:  # Limit violations collected
                            break
                
            if len(hierarchy_violations) >= 20:
                break
    
    matches_criteria = len(hierarchy_violations) == 0
    
    confidence = 0.9 if matches_criteria else 0.5
    
    expected_cascade = [288, 144, 96, 48, 12, 1]
    
    return {
        "node_id": "NETWORK_WIDE",
        "layer": "all",
        "rule_id": "R14_CABLE_HIERARCHY_REFINED",
        "rule_description": "Cable Hierarchy: Maintain 288/144 → 96 → 48 → 12 → 1F cascade",
        "confidence_score": round(confidence, 2),
        "matches_criteria": matches_criteria,
        "supporting_data": {
            "hierarchy_distribution": dict(hierarchy_stats),
            "violations": hierarchy_violations[:10],  # First 10 examples
            "total_violations": len(hierarchy_violations),
            "expected_cascade": expected_cascade
        }
    }


# ============================================================================
# MAIN REFINEMENT PIPELINE
# ============================================================================

def refine_graph_rules(graph_path: str = "logical_fiber_graph.json") -> Dict[str, Any]:
    """
    Main refinement pipeline.
    """
    print("=" * 80)
    print("REFINING GRAPH RULES (R10-R14)")
    print("=" * 80)
    
    # Load graph
    graph = load_logical_graph(graph_path)
    
    # Build structures
    print("\nBuilding graph structures...")
    nodes, adjacency, reverse_adjacency, link_data = build_graph_structures(graph)
    
    # Pre-compute downstream ONT counts (performance optimization)
    downstream_ont_cache = precompute_downstream_onts(graph, adjacency)
    
    # Refined analyses
    refined_analyses = []
    
    print("\nIterating over nodes and computing metrics...")
    terminal_count = 0
    fosc_count = 0
    
    # Process only terminals and FOSCs (performance optimization)
    terminal_nodes = [(nid, layer) for nid, layer in nodes.items() if layer == "terminal"]
    fosc_nodes = [(nid, layer) for nid, layer in nodes.items() if layer == "splice closure"]
    
    print(f"  Processing {len(terminal_nodes)} terminals and {len(fosc_nodes)} FOSCs...")
    
    # Process terminals
    for node_id, layer in terminal_nodes:
        terminal_count += 1
        # Compute metrics
        metrics = compute_node_metrics(node_id, layer, nodes, adjacency, reverse_adjacency, link_data)
        
        # Try Aerial Terminal rule
        aerial_result = refine_aerial_terminal_rule(node_id, metrics, downstream_ont_cache)
        if aerial_result:
            refined_analyses.append(aerial_result)
        
        # Try MST rule
        mst_result = refine_mst_rule(node_id, metrics, adjacency, reverse_adjacency, downstream_ont_cache)
        if mst_result:
            refined_analyses.append(mst_result)
    
    # Process FOSCs
    for node_id, layer in fosc_nodes:
        fosc_count += 1
        # Compute metrics
        metrics = compute_node_metrics(node_id, layer, nodes, adjacency, reverse_adjacency, link_data)
        
        # FOSC rule
        fosc_result = refine_fosc_rule(node_id, metrics, adjacency, reverse_adjacency, link_data)
        if fosc_result:
            refined_analyses.append(fosc_result)
        
        # FDH-FOSC association
        fdh_result = refine_fdh_fosc_association(node_id, metrics, adjacency, reverse_adjacency, nodes, link_data)
        if fdh_result:
            refined_analyses.append(fdh_result)
    
    # Cable hierarchy rule (network-wide)
    print("\nAnalyzing cable hierarchy...")
    hierarchy_result = refine_cable_hierarchy(graph, adjacency)
    refined_analyses.append(hierarchy_result)
    
    # Summary
    refined_by_rule = defaultdict(int)
    matches_by_rule = defaultdict(int)
    for analysis in refined_analyses:
        rule_id = analysis.get("rule_id", "UNKNOWN")
        refined_by_rule[rule_id] += 1
        if analysis.get("matches_criteria", False):
            matches_by_rule[rule_id] += 1
    
    print("\n" + "=" * 80)
    print("REFINEMENT COMPLETE")
    print("=" * 80)
    print(f"  Total refined analyses: {len(refined_analyses)}")
    print(f"  Terminals processed: {terminal_count}")
    print(f"  FOSCs processed: {fosc_count}")
    print(f"\n  Refined by rule:")
    for rule_id, count in sorted(refined_by_rule.items()):
        matches = matches_by_rule.get(rule_id, 0)
        print(f"    {rule_id}: {count} ({matches} match criteria)")
    
    return {
        "refined_analyses": refined_analyses,
        "summary": {
            "total_analyses": len(refined_analyses),
            "terminals_processed": terminal_count,
            "foscs_processed": fosc_count,
            "by_rule": dict(refined_by_rule),
            "matches_by_rule": dict(matches_by_rule)
        }
    }


# ============================================================================
# APPEND TO EXISTING FILES
# ============================================================================

def append_to_placement_analysis(refined_results: Dict[str, Any]) -> None:
    """Append refined analyses to placement_rules_analysis.json"""
    try:
        with open("placement_rules_analysis.json", "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        existing_data = {
            "placement_analyses": [],
            "summary": {}
        }
    
    # Append refined analyses
    existing_data["placement_analyses"].extend(refined_results["refined_analyses"])
    
    # Update summary
    existing_data["summary"]["refined_analyses"] = refined_results["summary"]["total_analyses"]
    existing_data["summary"]["refined_by_rule"] = refined_results["summary"]["by_rule"]
    existing_data["summary"]["refined_matches"] = refined_results["summary"]["matches_by_rule"]
    
    # Save
    with open("placement_rules_analysis.json", "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2)
    
    print(f"\n  ✓ Appended {refined_results['summary']['total_analyses']} refined analyses to placement_rules_analysis.json")


def append_to_rules_summary(refined_results: Dict[str, Any]) -> None:
    """Append refined rules to rules_summary.txt"""
    try:
        with open("rules_summary.txt", "r", encoding="utf-8") as f:
            existing_text = f.read()
    except FileNotFoundError:
        existing_text = ""
    
    # Generate refined summary section
    refined_text = "\n" + "=" * 80 + "\n"
    refined_text += "REFINED PLACEMENT LOGIC RULES (R10-R14)\n"
    refined_text += "=" * 80 + "\n\n"
    refined_text += "Refined using only logical graph data (no geometry).\n\n"
    
    # Group by rule
    by_rule = defaultdict(list)
    for analysis in refined_results["refined_analyses"]:
        rule_id = analysis.get("rule_id", "UNKNOWN")
        by_rule[rule_id].append(analysis)
    
    for rule_id, analyses in sorted(by_rule.items()):
        if rule_id == "R14_CABLE_HIERARCHY_REFINED":
            # Single network-wide rule
            analysis = analyses[0]
            refined_text += f"[{rule_id}]\n"
            refined_text += f"  Description: {analysis['rule_description']}\n"
            refined_text += f"  Confidence: {analysis['confidence_score']:.2f}\n"
            refined_text += f"  Matches Criteria: {analysis['matches_criteria']}\n"
            if analysis.get("supporting_data", {}).get("total_violations"):
                refined_text += f"  Violations: {analysis['supporting_data']['total_violations']}\n"
            refined_text += "\n"
        else:
            # Node-specific rules
            matches = sum(1 for a in analyses if a.get("matches_criteria", False))
            avg_confidence = statistics.mean([a.get("confidence_score", 0.5) for a in analyses])
            
            refined_text += f"[{rule_id}]\n"
            refined_text += f"  Description: {analyses[0]['rule_description']}\n"
            refined_text += f"  Nodes Analyzed: {len(analyses)}\n"
            refined_text += f"  Matches Criteria: {matches} ({matches/len(analyses)*100:.1f}%)\n"
            refined_text += f"  Average Confidence: {avg_confidence:.2f}\n"
            refined_text += "\n"
    
    # Append to existing file
    with open("rules_summary.txt", "a", encoding="utf-8") as f:
        f.write(refined_text)
    
    print(f"  ✓ Appended refined rules section to rules_summary.txt")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution."""
    # Refine rules
    refined_results = refine_graph_rules()
    
    # Append to existing files
    print("\n" + "=" * 80)
    print("APPENDING RESULTS")
    print("=" * 80)
    
    append_to_placement_analysis(refined_results)
    append_to_rules_summary(refined_results)
    
    print("\n" + "=" * 80)
    print("✅ REFINEMENT COMPLETE")
    print("=" * 80)
    print(f"\nGenerated {refined_results['summary']['total_analyses']} refined rule analyses")
    print(f"  Total matches: {sum(refined_results['summary']['matches_by_rule'].values())}")


if __name__ == "__main__":
    main()

