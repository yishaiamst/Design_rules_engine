#!/usr/bin/env python3
"""
extract_design_rules.py
-------------------------------------------------------------------------------
Design Rules Extraction Pipeline for Fiber Network
-------------------------------------------------------------------------------
Reads logical_fiber_graph.json and optionally raw layer GeoJSONs to:
1. Verify known design rules (connectivity, cable limits, hierarchy alignment)
2. Discover new rules statistically (distance, branching, capacity, cable transitions)
3. Generate AI-readable and human-readable summaries of learned rules

Outputs:
- rule_verification_report.json: Deterministic rule checks
- pattern_discovery.json: Statistical pattern discovery results
- discovered_rules.json: Consolidated rulebook with confidence scores
- rules_summary.txt: Human-readable summary
-------------------------------------------------------------------------------
"""

import json
import statistics
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional, Tuple
import math


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


def load_ont_paths(paths_path: str = "olt_ont_paths.json") -> List[Dict[str, Any]]:
    """Load ONT to OLT paths."""
    print(f"Loading ONT paths from {paths_path}...")
    with open(paths_path, "r", encoding="utf-8") as f:
        paths = json.load(f)
    print(f"  Loaded {len(paths)} ONT paths")
    return paths


def load_geojson_optional(path: str) -> Optional[List[Dict[str, Any]]]:
    """Optionally load GeoJSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        features = data.get("features", [])
        return [{k.lower(): v for k, v in f.get("properties", {}).items()} for f in features]
    except FileNotFoundError:
        return None


# ============================================================================
# RULE VERIFICATION
# ============================================================================

def verify_rules(graph: Dict[str, Any], paths: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify known design rules deterministically.
    Returns verification report with pass/fail status for each rule.
    """
    print("\n" + "=" * 80)
    print("VERIFYING KNOWN DESIGN RULES")
    print("=" * 80)
    
    nodes = {n["id"]: n["layer"] for n in graph.get("nodes", [])}
    links = graph.get("links", [])
    
    # Build adjacency and reverse adjacency maps
    adjacency = defaultdict(list)
    reverse_adjacency = defaultdict(list)
    for link in links:
        source = link.get("source")
        target = link.get("target")
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        cable_layer = link.get("cable_layer")
        length_m = link.get("length_m")
        is_virtual = link.get("virtual", False)
        
        adjacency[source].append({
            "target": target,
            "target_layer": target_layer,
            "cable_layer": cable_layer,
            "length_m": length_m,
            "virtual": is_virtual
        })
        reverse_adjacency[target].append({
            "source": source,
            "source_layer": source_layer,
            "cable_layer": cable_layer,
            "length_m": length_m,
            "virtual": is_virtual
        })
    
    verification_results = {
        "timestamp": None,
        "rules_checked": [],
        "summary": {
            "total_rules": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
    }
    
    # Rule 1: Connectivity - ONT must connect to Terminal
    print("\n[Rule 1] ONT → Terminal Connectivity")
    ont_to_terminal = 0
    ont_without_terminal = 0
    ont_ids = [n["id"] for n in graph.get("nodes", []) if n["layer"] == "ont"]
    
    for ont_id in ont_ids:
        has_terminal = any(
            adj["target_layer"] == "terminal" for adj in adjacency.get(ont_id, [])
        )
        if has_terminal:
            ont_to_terminal += 1
        else:
            ont_without_terminal += 1
    
    rule1_passed = ont_without_terminal == 0 or (ont_without_terminal / len(ont_ids)) < 0.05
    verification_results["rules_checked"].append({
        "rule_id": "CONNECTIVITY_ONT_TERMINAL",
        "description": "ONT must connect to Terminal via drop cable",
        "status": "PASS" if rule1_passed else "WARNING",
        "details": {
            "onts_with_terminal": ont_to_terminal,
            "onts_without_terminal": ont_without_terminal,
            "percentage_without": round(ont_without_terminal / len(ont_ids) * 100, 2) if ont_ids else 0
        }
    })
    print(f"  ✓ ONTs with Terminal: {ont_to_terminal}/{len(ont_ids)}")
    print(f"  {'⚠' if not rule1_passed else '✓'} ONTs without Terminal: {ont_without_terminal}")
    
    # Rule 2: Hierarchy - Terminal must connect to FOSC or FDH
    print("\n[Rule 2] Terminal → FOSC/FDH Hierarchy")
    terminal_to_fosc = 0
    terminal_to_fdh = 0
    terminal_orphaned = 0
    terminal_ids = [n["id"] for n in graph.get("nodes", []) if n["layer"] == "terminal"]
    
    for term_id in terminal_ids:
        has_fosc = any(adj["target_layer"] == "splice closure" for adj in adjacency.get(term_id, []))
        has_fdh = any(adj["target_layer"] == "fdh" for adj in adjacency.get(term_id, []))
        if has_fosc:
            terminal_to_fosc += 1
        elif has_fdh:
            terminal_to_fdh += 1
        else:
            terminal_orphaned += 1
    
    rule2_passed = terminal_orphaned == 0 or (terminal_orphaned / len(terminal_ids)) < 0.05
    verification_results["rules_checked"].append({
        "rule_id": "HIERARCHY_TERMINAL_FOSC_FDH",
        "description": "Terminal must connect to FOSC (splice closure) or FDH",
        "status": "PASS" if rule2_passed else "WARNING",
        "details": {
            "terminals_to_fosc": terminal_to_fosc,
            "terminals_to_fdh": terminal_to_fdh,
            "orphaned_terminals": terminal_orphaned,
            "percentage_orphaned": round(terminal_orphaned / len(terminal_ids) * 100, 2) if terminal_ids else 0
        }
    })
    print(f"  ✓ Terminals → FOSC: {terminal_to_fosc}")
    print(f"  ✓ Terminals → FDH: {terminal_to_fdh}")
    print(f"  {'⚠' if not rule2_passed else '✓'} Orphaned Terminals: {terminal_orphaned}")
    
    # Rule 3: Hierarchy - FOSC must connect to FDH or another FOSC
    print("\n[Rule 3] FOSC → FDH/FOSC Hierarchy")
    fosc_to_fdh = 0
    fosc_to_fosc = 0
    fosc_orphaned = 0
    fosc_ids = [n["id"] for n in graph.get("nodes", []) if n["layer"] == "splice closure"]
    
    for fosc_id in fosc_ids:
        has_fdh = any(adj["target_layer"] == "fdh" for adj in adjacency.get(fosc_id, []))
        has_fosc = any(adj["target_layer"] == "splice closure" for adj in adjacency.get(fosc_id, []))
        if has_fdh:
            fosc_to_fdh += 1
        elif has_fosc:
            fosc_to_fosc += 1
        else:
            fosc_orphaned += 1
    
    rule3_passed = fosc_orphaned == 0 or (fosc_orphaned / len(fosc_ids)) < 0.05
    verification_results["rules_checked"].append({
        "rule_id": "HIERARCHY_FOSC_FDH",
        "description": "FOSC must connect to FDH or another FOSC",
        "status": "PASS" if rule3_passed else "WARNING",
        "details": {
            "fosc_to_fdh": fosc_to_fdh,
            "fosc_to_fosc": fosc_to_fosc,
            "orphaned_fosc": fosc_orphaned,
            "percentage_orphaned": round(fosc_orphaned / len(fosc_ids) * 100, 2) if fosc_ids else 0
        }
    })
    print(f"  ✓ FOSC → FDH: {fosc_to_fdh}")
    print(f"  ✓ FOSC → FOSC: {fosc_to_fosc}")
    print(f"  {'⚠' if not rule3_passed else '✓'} Orphaned FOSC: {fosc_orphaned}")
    
    # Rule 4: Hierarchy - FDH must connect to OLT
    print("\n[Rule 4] FDH → OLT Hierarchy")
    fdh_to_olt = 0
    fdh_orphaned = 0
    fdh_ids = [n["id"] for n in graph.get("nodes", []) if n["layer"] == "fdh"]
    
    for fdh_id in fdh_ids:
        has_olt = any(adj["target_layer"] == "olt" for adj in adjacency.get(fdh_id, []))
        if has_olt:
            fdh_to_olt += 1
        else:
            fdh_orphaned += 1
    
    rule4_passed = fdh_orphaned == 0 or (fdh_orphaned / len(fdh_ids)) < 0.10
    verification_results["rules_checked"].append({
        "rule_id": "HIERARCHY_FDH_OLT",
        "description": "FDH must connect to OLT",
        "status": "PASS" if rule4_passed else "WARNING",
        "details": {
            "fdh_to_olt": fdh_to_olt,
            "orphaned_fdh": fdh_orphaned,
            "percentage_orphaned": round(fdh_orphaned / len(fdh_ids) * 100, 2) if fdh_ids else 0
        }
    })
    print(f"  ✓ FDH → OLT: {fdh_to_olt}")
    print(f"  {'⚠' if not rule4_passed else '✓'} Orphaned FDH: {fdh_orphaned}")
    
    # Rule 5: Cable Layer Consistency - Drop cables only for ONT→Terminal
    print("\n[Rule 5] Cable Layer Consistency")
    drop_cable_usage = defaultdict(int)
    stub_cable_usage = defaultdict(int)
    fiber_cable_usage = defaultdict(int)
    
    for link in links:
        cable_layer = link.get("cable_layer")
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        layer_pair = f"{source_layer}→{target_layer}"
        
        if cable_layer == "drop cable":
            drop_cable_usage[layer_pair] += 1
        elif cable_layer == "stub cable":
            stub_cable_usage[layer_pair] += 1
        elif cable_layer == "fiber cable":
            fiber_cable_usage[layer_pair] += 1
    
    rule5_passed = (
        drop_cable_usage.get("ont→terminal", 0) > 0 and
        len([k for k in drop_cable_usage.keys() if "ont" not in k]) == 0
    )
    
    verification_results["rules_checked"].append({
        "rule_id": "CABLE_LAYER_CONSISTENCY",
        "description": "Drop cables only used for ONT→Terminal connections",
        "status": "PASS" if rule5_passed else "WARNING",
        "details": {
            "drop_cable_usage": dict(drop_cable_usage),
            "stub_cable_usage": dict(stub_cable_usage),
            "fiber_cable_usage": dict(fiber_cable_usage)
        }
    })
    print(f"  ✓ Drop cable usage: {dict(drop_cable_usage)}")
    print(f"  ✓ Stub cable usage: {dict(stub_cable_usage)}")
    print(f"  ✓ Fiber cable usage: {dict(fiber_cable_usage)}")
    
    # Rule 6: Path Completeness - Most paths should reach OLT
    print("\n[Rule 6] Path Completeness")
    complete_paths = sum(1 for p in paths if p.get("complete", False))
    total_paths = len(paths)
    completeness_rate = complete_paths / total_paths if total_paths > 0 else 0
    
    rule6_passed = completeness_rate >= 0.90
    verification_results["rules_checked"].append({
        "rule_id": "PATH_COMPLETENESS",
        "description": "ONT paths should reach OLT (≥90% completion rate)",
        "status": "PASS" if rule6_passed else "FAIL",
        "details": {
            "complete_paths": complete_paths,
            "total_paths": total_paths,
            "completeness_rate": round(completeness_rate * 100, 2)
        }
    })
    print(f"  {'✓' if rule6_passed else '✗'} Complete paths: {complete_paths}/{total_paths} ({completeness_rate*100:.2f}%)")
    
    # Rule 7: Virtual Link Limits
    print("\n[Rule 7] Virtual Link Limits")
    virtual_links = sum(1 for link in links if link.get("virtual", False))
    total_links = len(links)
    virtual_rate = virtual_links / total_links if total_links > 0 else 0
    
    rule7_passed = virtual_rate < 0.20  # Less than 20% virtual
    verification_results["rules_checked"].append({
        "rule_id": "VIRTUAL_LINK_LIMITS",
        "description": "Virtual links should be <20% of total links",
        "status": "PASS" if rule7_passed else "WARNING",
        "details": {
            "virtual_links": virtual_links,
            "total_links": total_links,
            "virtual_rate": round(virtual_rate * 100, 2)
        }
    })
    print(f"  {'✓' if rule7_passed else '⚠'} Virtual links: {virtual_links}/{total_links} ({virtual_rate*100:.2f}%)")
    
    # Summary
    verification_results["summary"]["total_rules"] = len(verification_results["rules_checked"])
    verification_results["summary"]["passed"] = sum(
        1 for r in verification_results["rules_checked"] if r["status"] == "PASS"
    )
    verification_results["summary"]["failed"] = sum(
        1 for r in verification_results["rules_checked"] if r["status"] == "FAIL"
    )
    verification_results["summary"]["warnings"] = sum(
        1 for r in verification_results["rules_checked"] if r["status"] == "WARNING"
    )
    
    print("\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY: {verification_results['summary']['passed']} passed, "
          f"{verification_results['summary']['warnings']} warnings, "
          f"{verification_results['summary']['failed']} failed")
    print("=" * 80)
    
    return verification_results


# ============================================================================
# PATTERN MINING
# ============================================================================

def mine_patterns(graph: Dict[str, Any], paths: List[Dict[str, Any]], 
                  geojson_data: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """
    Discover design patterns statistically through clustering and analysis.
    Focus on: distance, branching, capacity, cable transitions, placement logic.
    """
    print("\n" + "=" * 80)
    print("MINING DESIGN PATTERNS")
    print("=" * 80)
    
    nodes = {n["id"]: n["layer"] for n in graph.get("nodes", [])}
    links = graph.get("links", [])
    
    # Build comprehensive data structures
    adjacency = defaultdict(list)
    reverse_adjacency = defaultdict(list)
    node_degrees = defaultdict(int)
    
    for link in links:
        source = link.get("source")
        target = link.get("target")
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        cable_layer = link.get("cable_layer")
        length_m = link.get("length_m")
        is_virtual = link.get("virtual", False)
        
        adjacency[source].append({
            "target": target,
            "target_layer": target_layer,
            "cable_layer": cable_layer,
            "length_m": length_m,
            "virtual": is_virtual
        })
        reverse_adjacency[target].append({
            "source": source,
            "source_layer": source_layer,
            "cable_layer": cable_layer,
            "length_m": length_m,
            "virtual": is_virtual
        })
        node_degrees[source] += 1
        node_degrees[target] += 1
    
    patterns = {
        "distance_patterns": {},
        "branching_patterns": {},
        "capacity_patterns": {},
        "cable_transitions": {},
        "placement_logic": {},
        "next_hop_decisions": {}
    }
    
    # ========================================================================
    # 1. DISTANCE PATTERNS
    # ========================================================================
    print("\n[1] Analyzing Distance Patterns...")
    
    drop_cable_lengths = []
    stub_cable_lengths = []
    fiber_cable_lengths = []
    inter_layer_distances = defaultdict(list)
    
    for link in links:
        length_m = link.get("length_m")
        if length_m and length_m > 0:
            cable_layer = link.get("cable_layer")
            source_layer = link.get("source_layer")
            target_layer = link.get("target_layer")
            layer_pair = f"{source_layer}→{target_layer}"
            
            if cable_layer == "drop cable":
                drop_cable_lengths.append(length_m)
            elif cable_layer == "stub cable":
                stub_cable_lengths.append(length_m)
            elif cable_layer == "fiber cable":
                fiber_cable_lengths.append(length_m)
            
            inter_layer_distances[layer_pair].append(length_m)
    
    def calc_stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {}
        return {
            "count": len(values),
            "mean": round(statistics.mean(values), 2),
            "median": round(statistics.median(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "p25": round(statistics.quantiles(values, n=4)[0], 2) if len(values) > 1 else values[0],
            "p75": round(statistics.quantiles(values, n=4)[2], 2) if len(values) > 1 else values[-1]
        }
    
    patterns["distance_patterns"] = {
        "drop_cable": calc_stats(drop_cable_lengths),
        "stub_cable": calc_stats(stub_cable_lengths),
        "fiber_cable": calc_stats(fiber_cable_lengths),
        "inter_layer_distances": {k: calc_stats(v) for k, v in inter_layer_distances.items()}
    }
    
    print(f"  ✓ Drop cable lengths: {len(drop_cable_lengths)} samples")
    print(f"  ✓ Stub cable lengths: {len(stub_cable_lengths)} samples")
    print(f"  ✓ Fiber cable lengths: {len(fiber_cable_lengths)} samples")
    
    # ========================================================================
    # 2. BRANCHING PATTERNS
    # ========================================================================
    print("\n[2] Analyzing Branching Patterns...")
    
    # Branching factor by layer (how many downstream connections)
    branching_by_layer = defaultdict(list)
    for node_id, layer in nodes.items():
        out_degree = len(adjacency.get(node_id, []))
        if out_degree > 0:
            branching_by_layer[layer].append(out_degree)
    
    # In-degree (fan-in) patterns
    fan_in_by_layer = defaultdict(list)
    for node_id, layer in nodes.items():
        in_degree = len(reverse_adjacency.get(node_id, []))
        if in_degree > 0:
            fan_in_by_layer[layer].append(in_degree)
    
    patterns["branching_patterns"] = {
        "out_degree_by_layer": {k: calc_stats(v) for k, v in branching_by_layer.items()},
        "in_degree_by_layer": {k: calc_stats(v) for k, v in fan_in_by_layer.items()}
    }
    
    print(f"  ✓ Analyzed branching for {len(branching_by_layer)} layer types")
    
    # ========================================================================
    # 3. CAPACITY PATTERNS (from cable IDs - extract fiber counts)
    # ========================================================================
    print("\n[3] Analyzing Capacity Patterns...")
    
    cable_fiber_counts = defaultdict(list)
    for link in links:
        cable_id = link.get("cable_id")
        if cable_id:
            # Extract fiber count from cable ID (e.g., "144FOC" -> 144)
            import re
            match = re.search(r'(\d+)FOC', str(cable_id).upper())
            if match:
                fiber_count = int(match.group(1))
                cable_layer = link.get("cable_layer")
                cable_fiber_counts[cable_layer].append(fiber_count)
    
    patterns["capacity_patterns"] = {
        "fiber_counts_by_cable_type": {
            k: {
                "count": len(v),
                "unique_values": sorted(set(v)),
                "most_common": Counter(v).most_common(5) if v else []
            }
            for k, v in cable_fiber_counts.items()
        }
    }
    
    print(f"  ✓ Extracted fiber counts from {sum(len(v) for v in cable_fiber_counts.values())} cables")
    
    # ========================================================================
    # 4. CABLE TRANSITIONS (when cable types change along path)
    # ========================================================================
    print("\n[4] Analyzing Cable Transitions...")
    
    transition_patterns = defaultdict(list)
    for path in paths:
        path_segments = path.get("path", [])
        if len(path_segments) < 2:
            continue
        
        transitions = []
        for i in range(len(path_segments) - 1):
            curr_layer = path_segments[i].get("cable_layer")
            next_layer = path_segments[i + 1].get("cable_layer")
            if curr_layer and next_layer and curr_layer != next_layer:
                transition = f"{curr_layer}→{next_layer}"
                transitions.append(transition)
                transition_patterns[transition].append({
                    "from_layer": path_segments[i].get("from_layer"),
                    "to_layer": path_segments[i].get("to_layer"),
                    "next_from_layer": path_segments[i + 1].get("from_layer"),
                    "next_to_layer": path_segments[i + 1].get("to_layer")
                })
    
    patterns["cable_transitions"] = {
        "transition_counts": {k: len(v) for k, v in transition_patterns.items()},
        "transition_examples": {k: v[:5] for k, v in transition_patterns.items()}  # First 5 examples
    }
    
    print(f"  ✓ Found {len(transition_patterns)} unique transition types")
    
    # ========================================================================
    # 5. PLACEMENT LOGIC (Why FOSCs, Terminals, MSTs are placed where they are)
    # ========================================================================
    print("\n[5] Analyzing Placement Logic...")
    
    # Terminal placement analysis
    terminal_placement = {
        "terminal_types": defaultdict(int),
        "terminal_to_fosc_distance": [],
        "terminal_to_fdh_distance": [],
        "terminals_per_fosc": defaultdict(int),
        "terminals_per_fdh": defaultdict(int)
    }
    
    # FOSC placement analysis
    fosc_placement = {
        "fosc_to_fdh_distance": [],
        "fosc_to_fosc_distance": [],
        "foscs_per_fdh": defaultdict(int),
        "fosc_chain_lengths": []
    }
    
    # Analyze paths to understand placement
    for path in paths:
        path_segments = path.get("path", [])
        terminals_in_path = []
        foscs_in_path = []
        fdhs_in_path = []
        
        for seg in path_segments:
            from_layer = seg.get("from_layer")
            to_layer = seg.get("to_layer")
            length_m = seg.get("length_m")
            
            if from_layer == "terminal":
                terminals_in_path.append(seg.get("from"))
            if to_layer == "terminal":
                terminals_in_path.append(seg.get("to"))
            
            if from_layer == "splice closure":
                foscs_in_path.append(seg.get("from"))
            if to_layer == "splice closure":
                foscs_in_path.append(seg.get("to"))
            
            if from_layer == "fdh":
                fdhs_in_path.append(seg.get("from"))
            if to_layer == "fdh":
                fdhs_in_path.append(seg.get("to"))
        
        # Count terminals per FOSC
        for term in set(terminals_in_path):
            for seg in path_segments:
                if seg.get("from") == term and seg.get("to_layer") == "splice closure":
                    fosc_id = seg.get("to")
                    terminal_placement["terminals_per_fosc"][fosc_id] += 1
                    if seg.get("length_m"):
                        terminal_placement["terminal_to_fosc_distance"].append(seg.get("length_m"))
                elif seg.get("to") == term and seg.get("from_layer") == "splice closure":
                    fosc_id = seg.get("from")
                    terminal_placement["terminals_per_fosc"][fosc_id] += 1
                    if seg.get("length_m"):
                        terminal_placement["terminal_to_fosc_distance"].append(seg.get("length_m"))
        
        # Count FOSCs per FDH
        for fosc in set(foscs_in_path):
            for seg in path_segments:
                if seg.get("from") == fosc and seg.get("to_layer") == "fdh":
                    fdh_id = seg.get("to")
                    fosc_placement["foscs_per_fdh"][fdh_id] += 1
                    if seg.get("length_m"):
                        fosc_placement["fosc_to_fdh_distance"].append(seg.get("length_m"))
    
    patterns["placement_logic"] = {
        "terminal_placement": {
            "terminals_per_fosc_stats": calc_stats(list(terminal_placement["terminals_per_fosc"].values())),
            "terminal_to_fosc_distance_stats": calc_stats(terminal_placement["terminal_to_fosc_distance"]),
            "terminal_to_fdh_distance_stats": calc_stats(terminal_placement["terminal_to_fdh_distance"])
        },
        "fosc_placement": {
            "foscs_per_fdh_stats": calc_stats(list(fosc_placement["foscs_per_fdh"].values())),
            "fosc_to_fdh_distance_stats": calc_stats(fosc_placement["fosc_to_fdh_distance"]),
            "fosc_to_fosc_distance_stats": calc_stats(fosc_placement["fosc_to_fosc_distance"])
        }
    }
    
    print(f"  ✓ Analyzed terminal placement patterns")
    print(f"  ✓ Analyzed FOSC placement patterns")
    
    # ========================================================================
    # 6. NEXT HOP DECISIONS (What defines the next hop in path)
    # ========================================================================
    print("\n[6] Analyzing Next Hop Decisions...")
    
    next_hop_patterns = defaultdict(lambda: defaultdict(int))
    
    for path in paths:
        path_segments = path.get("path", [])
        for i, seg in enumerate(path_segments):
            if i == len(path_segments) - 1:
                break  # Last segment
            
            current_layer = seg.get("to_layer")
            next_seg = path_segments[i + 1]
            next_layer = next_seg.get("to_layer")
            next_cable_type = next_seg.get("cable_layer")
            
            decision_key = f"{current_layer}→{next_layer}"
            next_hop_patterns[decision_key][next_cable_type] += 1
    
    patterns["next_hop_decisions"] = {
        "layer_transitions": {k: dict(v) for k, v in next_hop_patterns.items()},
        "most_common_transitions": sorted(
            [(k, sum(v.values())) for k, v in next_hop_patterns.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
    }
    
    print(f"  ✓ Analyzed {len(next_hop_patterns)} next-hop decision patterns")
    
    # ========================================================================
    # 7. PATH HOP ANALYSIS
    # ========================================================================
    print("\n[7] Analyzing Path Hop Patterns...")
    
    hop_counts = [p.get("hop_count", 0) for p in paths]
    path_lengths = [p.get("total_length_m", 0) for p in paths]
    
    # Calculate correlation manually if needed
    def pearson_correlation(x, y):
        """Calculate Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return None
        try:
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)
            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
            denom_x = sum((x[i] - mean_x) ** 2 for i in range(len(x)))
            denom_y = sum((y[i] - mean_y) ** 2 for i in range(len(x)))
            if denom_x == 0 or denom_y == 0:
                return None
            return numerator / math.sqrt(denom_x * denom_y)
        except:
            return None
    
    corr_value = pearson_correlation(hop_counts, path_lengths)
    patterns["path_analysis"] = {
        "hop_count_stats": calc_stats(hop_counts),
        "path_length_stats": calc_stats(path_lengths),
        "hop_vs_length_correlation": {
            "pearson_correlation": round(corr_value, 4) if corr_value is not None else None
        }
    }
    
    print(f"  ✓ Analyzed {len(hop_counts)} paths")
    
    print("\n" + "=" * 80)
    print("PATTERN MINING COMPLETE")
    print("=" * 80)
    
    return patterns


# ============================================================================
# PLACEMENT LOGIC ANALYSIS
# ============================================================================

def analyze_placement_logic(graph: Dict[str, Any], paths: List[Dict[str, Any]],
                           geojson_data: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """
    Analyze placement logic for Aerial Terminals, MSTs, and FOSCs.
    Implements Rules R10-R14 to determine why and where each node is placed.
    """
    print("\n" + "=" * 80)
    print("ANALYZING PLACEMENT LOGIC (R10-R14)")
    print("=" * 80)
    
    nodes = {n["id"]: n["layer"] for n in graph.get("nodes", [])}
    links = graph.get("links", [])
    
    # Build data structures
    adjacency = defaultdict(list)
    reverse_adjacency = defaultdict(list)
    node_to_links = defaultdict(list)
    
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
        node_to_links[source].append(link)
        node_to_links[target].append(link)
    
    # Build indexes from GeoJSON data
    terminal_records = {}
    fosc_records = {}
    fdh_records = {}
    fiber_cable_records = {}
    
    if geojson_data:
        # Terminal records
        for term in geojson_data.get("terminal", []):
            term_id = term.get("id") or term.get("terminal_id") or term.get("termnal_id")
            if term_id:
                terminal_records[term_id] = term
        
        # FOSC records
        for fosc in geojson_data.get("fosc", []):
            fosc_id = fosc.get("id") or fosc.get("fosc_id")
            if fosc_id:
                fosc_records[fosc_id] = fosc
        
        # FDH records
        for fdh in geojson_data.get("fdh", []):
            fdh_id = fdh.get("id") or fdh.get("fdh_id")
            if fdh_id:
                fdh_records[fdh_id] = fdh
    
    # Load fiber cable data for cable_id matching
    fiber_cable_data = load_geojson_optional("fiber cable.geojson") or []
    fiber_cable_by_id = {}
    for cable in fiber_cable_data:
        cable_id = cable.get("id") or cable.get("cable_id")
        if cable_id:
            fiber_cable_by_id[cable_id] = cable
    
    # Extract fiber count from cable ID
    def extract_fiber_count(cable_id: str) -> Optional[int]:
        """Extract fiber count from cable ID (e.g., '144FOC' -> 144)."""
        if not cable_id:
            return None
        import re
        match = re.search(r'(\d+)FOC', str(cable_id).upper())
        return int(match.group(1)) if match else None
    
    # Pre-compute downstream ONT counts using paths data (much faster)
    print("  Pre-computing downstream ONT counts...")
    downstream_ont_cache = defaultdict(int)
    
    # Count ONTs per terminal from paths
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
    
    def count_downstream_onts(node_id: str) -> int:
        """Count how many ONTs are downstream from this node (cached)."""
        return downstream_ont_cache.get(node_id, 0)
    
    # Pre-compute FDH distances (limit depth for performance)
    print("  Pre-computing FDH distances...")
    fdh_distance_cache = {}
    MAX_FDH_SEARCH_DEPTH = 5  # Limit BFS depth
    
    from collections import deque
    for fdh_id in [nid for nid, layer in nodes.items() if layer == "fdh"]:
        fdh_distance_cache[fdh_id] = 0.0
    
    # Find FOSCs directly connected to FDHs
    for link in links:
        source = link.get("source")
        target = link.get("target")
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        length_m = link.get("length_m") or 0.0
        
        if source_layer == "splice closure" and target_layer == "fdh":
            if source not in fdh_distance_cache or fdh_distance_cache[source] > length_m:
                fdh_distance_cache[source] = length_m
        elif source_layer == "fdh" and target_layer == "splice closure":
            if target not in fdh_distance_cache or fdh_distance_cache[target] > length_m:
                fdh_distance_cache[target] = length_m
    
    def distance_to_fdh(node_id: str, node_layer: str) -> Optional[float]:
        """Calculate shortest path distance to nearest FDH (cached with limited BFS)."""
        if node_layer == "fdh":
            return 0.0
        
        if node_id in fdh_distance_cache:
            return fdh_distance_cache[node_id]
        
        # Limited BFS search (max 5 hops)
        queue = deque([(node_id, 0.0, 0)])
        visited = {node_id}
        best_distance = None
        
        while queue:
            current, dist, depth = queue.popleft()
            
            if depth >= MAX_FDH_SEARCH_DEPTH:
                continue
            
            for adj in adjacency.get(current, []):
                target = adj["target"]
                target_layer = adj["target_layer"]
                length = adj.get("length_m") or 0.0
                
                if target_layer == "fdh":
                    total_dist = dist + length
                    if best_distance is None or total_dist < best_distance:
                        best_distance = total_dist
                
                if target not in visited and target_layer in ["terminal", "splice closure"]:
                    visited.add(target)
                    queue.append((target, dist + length, depth + 1))
        
        # Cache result
        if best_distance is not None:
            fdh_distance_cache[node_id] = best_distance
        
        return best_distance
    
    # Analyze placement for each node
    placement_analyses = []
    
    # ========================================================================
    # R10: Aerial Terminal Placement Rule
    # ========================================================================
    print("\n[R10] Analyzing Aerial Terminal Placement...")
    aerial_terminal_count = 0
    
    for node_id, layer in nodes.items():
        if layer != "terminal":
            continue
        
        term_rec = terminal_records.get(node_id, {})
        terminal_type = (term_rec.get("type") or 
                        term_rec.get("terminal_type") or 
                        "").lower()
        
        if "aerial" not in terminal_type:
            continue
        
        aerial_terminal_count += 1
        cable_id = term_rec.get("cable_id") or term_rec.get("cableid")
        fdh_id = term_rec.get("fdh_id") or term_rec.get("fdhid")
        
        # Check R10 conditions
        has_cable_id = cable_id is not None
        has_fiber_cable = cable_id in fiber_cable_by_id if cable_id else False
        downstream_onts = count_downstream_onts(node_id)
        has_stub_cable = any(
            adj["cable_layer"] == "stub cable" 
            for adj in adjacency.get(node_id, [])
        )
        
        # Calculate average drop cable distance
        drop_distances = [
            adj.get("length_m", 0) 
            for adj in adjacency.get(node_id, [])
            if adj.get("cable_layer") == "drop cable" and adj.get("length_m")
        ]
        avg_drop_distance = statistics.mean(drop_distances) if drop_distances else None
        
        # Determine confidence
        confidence = 0.5
        rule_matches = []
        
        if has_cable_id and has_fiber_cable:
            confidence += 0.2
            rule_matches.append("cable_id exists in fiber cable layer")
        
        if downstream_onts <= 12:
            confidence += 0.2
            rule_matches.append(f"downstream ONTs ≤ 12 ({downstream_onts})")
        else:
            confidence -= 0.1
            rule_matches.append(f"downstream ONTs > 12 ({downstream_onts})")
        
        if not has_stub_cable:
            confidence += 0.1
            rule_matches.append("no stub cable originates")
        else:
            confidence -= 0.1
            rule_matches.append("stub cable present (may be MST)")
        
        if avg_drop_distance and avg_drop_distance <= 150:
            confidence += 0.1
            rule_matches.append(f"average drop distance ≤ 150m ({avg_drop_distance:.1f}m)")
        
        confidence = max(0.0, min(1.0, confidence))
        
        placement_analyses.append({
            "node_id": node_id,
            "layer": layer,
            "rule_id": "R10_AERIAL_TERMINAL_PLACEMENT",
            "rule_description": "Place Aerial Terminal when fiber cable segment continues within same trunk, serving ≤12 drops within ~150m, without requiring fiber splicing",
            "confidence_score": round(confidence, 2),
            "supporting_data": {
                "terminal_type": term_rec.get("type", "Unknown"),
                "has_cable_id": has_cable_id,
                "cable_id": cable_id,
                "has_fiber_cable": has_fiber_cable,
                "downstream_onts": downstream_onts,
                "has_stub_cable": has_stub_cable,
                "avg_drop_distance_m": round(avg_drop_distance, 2) if avg_drop_distance else None,
                "fdh_id": fdh_id,
                "rule_conditions_met": rule_matches
            }
        })
    
    print(f"  ✓ Analyzed {aerial_terminal_count} Aerial Terminals")
    
    # ========================================================================
    # R11: MST (Stub) Placement Rule
    # ========================================================================
    print("\n[R11] Analyzing MST Placement...")
    mst_count = 0
    
    for node_id, layer in nodes.items():
        if layer != "terminal":
            continue
        
        term_rec = terminal_records.get(node_id, {})
        terminal_type = (term_rec.get("type") or 
                        term_rec.get("terminal_type") or 
                        "").lower()
        
        if terminal_type != "mst":
            continue
        
        mst_count += 1
        fosc_id = term_rec.get("fosc_id") or term_rec.get("foscid")
        fdh_id = term_rec.get("fdh_id") or term_rec.get("fdhid")
        
        # Check for stub cable connections
        stub_connections = [
            adj for adj in adjacency.get(node_id, [])
            if adj.get("cable_layer") == "stub cable"
        ]
        has_stub_cable = len(stub_connections) > 0
        
        # Find connected FOSC
        connected_fosc = None
        stub_distance = None
        for adj in adjacency.get(node_id, []):
            if adj.get("target_layer") == "splice closure":
                connected_fosc = adj["target"]
                if adj.get("cable_layer") == "stub cable":
                    stub_distance = adj.get("length_m")
                break
        
        # If not found in forward, check reverse
        if not connected_fosc:
            for rev_adj in reverse_adjacency.get(node_id, []):
                if rev_adj.get("source_layer") == "splice closure":
                    connected_fosc = rev_adj["source"]
                    if rev_adj.get("cable_layer") == "stub cable":
                        stub_distance = rev_adj.get("length_m")
                    break
        
        # Get FOSC category
        fosc_category = None
        if connected_fosc and connected_fosc in fosc_records:
            fosc_rec = fosc_records[connected_fosc]
            fosc_category = (fosc_rec.get("fosccate") or 
                           fosc_rec.get("fosc_cate") or 
                           fosc_rec.get("splice_category") or 
                           "Unknown")
        
        downstream_onts = count_downstream_onts(node_id)
        
        # Determine confidence
        confidence = 0.5
        rule_matches = []
        
        if has_stub_cable:
            confidence += 0.3
            rule_matches.append("stub cable connection present")
        
        if connected_fosc:
            confidence += 0.2
            rule_matches.append(f"connected to FOSC {connected_fosc}")
        
        if stub_distance and stub_distance <= 500:
            confidence += 0.1
            rule_matches.append(f"stub distance ≤ 500m ({stub_distance:.1f}m)")
        elif stub_distance:
            confidence -= 0.1
            rule_matches.append(f"stub distance > 500m ({stub_distance:.1f}m)")
        
        if fosc_category and ("full" in fosc_category.lower() or "partial" in fosc_category.lower()):
            confidence += 0.1
            rule_matches.append(f"FOSC category: {fosc_category}")
        
        if downstream_onts >= 1 and downstream_onts <= 12:
            confidence += 0.1
            rule_matches.append(f"serves 1-12 ONTs ({downstream_onts})")
        
        confidence = max(0.0, min(1.0, confidence))
        
        placement_analyses.append({
            "node_id": node_id,
            "layer": layer,
            "rule_id": "R11_MST_PLACEMENT",
            "rule_description": "Place MST when stub cable branches from FOSC, typically ≤500m away, to serve small clusters of ONTs (1-12)",
            "confidence_score": round(confidence, 2),
            "supporting_data": {
                "terminal_type": term_rec.get("type", "MST"),
                "has_stub_cable": has_stub_cable,
                "connected_fosc": connected_fosc,
                "stub_distance_m": round(stub_distance, 2) if stub_distance else None,
                "fosc_category": fosc_category,
                "fosc_id": fosc_id,
                "fdh_id": fdh_id,
                "downstream_onts": downstream_onts,
                "rule_conditions_met": rule_matches
            }
        })
    
    print(f"  ✓ Analyzed {mst_count} MST Terminals")
    
    # ========================================================================
    # R12: FOSC (Splice Closure) Placement Rule
    # ========================================================================
    print("\n[R12] Analyzing FOSC Placement...")
    fosc_count = 0
    
    for node_id, layer in nodes.items():
        if layer != "splice closure":
            continue
        
        fosc_count += 1
        fosc_rec = fosc_records.get(node_id, {})
        fosc_category = (fosc_rec.get("fosccate") or 
                        fosc_rec.get("fosc_cate") or 
                        fosc_rec.get("splice_category") or 
                        "Unknown")
        
        # Count incoming and outgoing fiber cables
        incoming_fiber = [
            adj for adj in reverse_adjacency.get(node_id, [])
            if adj.get("cable_layer") == "fiber cable"
        ]
        outgoing_fiber = [
            adj for adj in adjacency.get(node_id, [])
            if adj.get("cable_layer") == "fiber cable"
        ]
        
        # Check for intersections (≥2 fiber cables)
        total_fiber_connections = len(incoming_fiber) + len(outgoing_fiber)
        is_intersection = total_fiber_connections >= 2
        
        # Check for fiber count transitions
        incoming_fiber_counts = []
        outgoing_fiber_counts = []
        for adj in incoming_fiber:
            cable_id = adj.get("cable_id")
            if cable_id:
                fiber_count = extract_fiber_count(cable_id)
                if fiber_count:
                    incoming_fiber_counts.append(fiber_count)
        
        for adj in outgoing_fiber:
            cable_id = adj.get("cable_id")
            if cable_id:
                fiber_count = extract_fiber_count(cable_id)
                if fiber_count:
                    outgoing_fiber_counts.append(fiber_count)
        
        has_fiber_transition = False
        if incoming_fiber_counts and outgoing_fiber_counts:
            avg_in = statistics.mean(incoming_fiber_counts) if incoming_fiber_counts else None
            avg_out = statistics.mean(outgoing_fiber_counts) if outgoing_fiber_counts else None
            if avg_in and avg_out and abs(avg_in - avg_out) > 10:  # Significant change
                has_fiber_transition = True
        
        # Check for stub cable branching
        has_stub_branching = any(
            adj.get("cable_layer") == "stub cable"
            for adj in adjacency.get(node_id, [])
        ) or any(
            adj.get("cable_layer") == "stub cable"
            for adj in reverse_adjacency.get(node_id, [])
        )
        
        # Calculate distance to nearest FOSC
        nearest_fosc_distance = None
        for adj in adjacency.get(node_id, []):
            if adj.get("target_layer") == "splice closure" and adj.get("length_m"):
                if nearest_fosc_distance is None or adj.get("length_m") < nearest_fosc_distance:
                    nearest_fosc_distance = adj.get("length_m")
        
        # Determine confidence
        confidence = 0.4
        rule_matches = []
        
        if is_intersection:
            confidence += 0.3
            rule_matches.append(f"intersection of {total_fiber_connections} fiber cables")
        
        if has_fiber_transition:
            confidence += 0.2
            rule_matches.append(f"fiber count transition (in: {avg_in:.0f}F, out: {avg_out:.0f}F)")
        
        if has_stub_branching:
            confidence += 0.2
            rule_matches.append("branches to stub cables (MST fan-outs)")
        
        if nearest_fosc_distance:
            if 800 <= nearest_fosc_distance <= 900:
                confidence += 0.1
                rule_matches.append(f"spacing ~800-900m ({nearest_fosc_distance:.1f}m)")
            else:
                rule_matches.append(f"spacing {nearest_fosc_distance:.1f}m")
        
        if "full" in fosc_category.lower():
            confidence += 0.1
            rule_matches.append("Full Splice (all fibers spliced)")
        elif "partial" in fosc_category.lower():
            confidence += 0.1
            rule_matches.append("Partial Splice (subset tapped)")
        
        confidence = max(0.0, min(1.0, confidence))
        
        placement_analyses.append({
            "node_id": node_id,
            "layer": layer,
            "rule_id": "R12_FOSC_PLACEMENT",
            "rule_description": "Place FOSC at intersections of ≥2 fiber cables, fiber count transitions, or branching points to stub cables. Spacing ~800-900m",
            "confidence_score": round(confidence, 2),
            "supporting_data": {
                "fosc_category": fosc_category,
                "is_intersection": is_intersection,
                "total_fiber_connections": total_fiber_connections,
                "has_fiber_transition": has_fiber_transition,
                "incoming_fiber_counts": incoming_fiber_counts,
                "outgoing_fiber_counts": outgoing_fiber_counts,
                "has_stub_branching": has_stub_branching,
                "nearest_fosc_distance_m": round(nearest_fosc_distance, 2) if nearest_fosc_distance else None,
                "rule_conditions_met": rule_matches
            }
        })
    
    print(f"  ✓ Analyzed {fosc_count} FOSCs")
    
    # ========================================================================
    # R13: FDH Association Rule
    # ========================================================================
    print("\n[R13] Analyzing FDH-FOSC Association...")
    fdh_association_count = 0
    
    # Check FOSCs near FDHs
    for fosc_id in fosc_records.keys():
        if fosc_id not in nodes or nodes[fosc_id] != "splice closure":
            continue
        
        # Find nearest FDH
        fdh_distance = distance_to_fdh(fosc_id, "splice closure")
        
        if fdh_distance is not None and fdh_distance <= 50:
            fdh_association_count += 1
            
            # Find which FDH
            nearest_fdh = None
            for node_id, layer in nodes.items():
                if layer == "fdh":
                    # Check if this FDH is reachable within 50m
                    test_dist = distance_to_fdh(node_id, "fdh")
                    if test_dist == 0:  # This is the FDH itself
                        # Check if FOSC connects to this FDH
                        for adj in adjacency.get(fosc_id, []):
                            if adj.get("target") == node_id:
                                nearest_fdh = node_id
                                break
                        if not nearest_fdh:
                            for rev_adj in reverse_adjacency.get(fosc_id, []):
                                if rev_adj.get("source") == node_id:
                                    nearest_fdh = node_id
                                    break
            
            # Get fiber cable info
            fosc_rec = fosc_records.get(fosc_id, {})
            fdh_id = fosc_rec.get("fdh_id") or fosc_rec.get("fdhid")
            
            # Check cable sizes
            fiber_cables_near = []
            for adj in adjacency.get(fosc_id, []):
                if adj.get("cable_layer") == "fiber cable":
                    cable_id = adj.get("cable_id")
                    if cable_id:
                        fiber_count = extract_fiber_count(cable_id)
                        fiber_cables_near.append({
                            "cable_id": cable_id,
                            "fiber_count": fiber_count,
                            "length_m": adj.get("length_m")
                        })
            
            confidence = 0.9 if fdh_distance <= 50 else 0.5
            
            placement_analyses.append({
                "node_id": fosc_id,
                "layer": "splice closure",
                "rule_id": "R13_FDH_ASSOCIATION",
                "rule_description": "FOSC within ≤50m of FDH serves as feeder splice point between 144F/288F feeders and 96F distributors",
                "confidence_score": round(confidence, 2),
                "supporting_data": {
                    "nearest_fdh": nearest_fdh,
                    "fdh_distance_m": round(fdh_distance, 2),
                    "fdh_id": fdh_id,
                    "fiber_cables": fiber_cables_near[:5],  # First 5 examples
                    "rule_conditions_met": [f"FOSC within {fdh_distance:.1f}m of FDH"] if fdh_distance <= 50 else []
                }
            })
    
    print(f"  ✓ Found {fdh_association_count} FOSCs within 50m of FDH")
    
    # ========================================================================
    # R14: Cable Size-Based Placement Rule
    # ========================================================================
    print("\n[R14] Analyzing Cable Size Hierarchy...")
    
    # Analyze cable sizes across the network
    cable_size_analysis = defaultdict(lambda: {
        "count": 0,
        "associated_nodes": [],
        "typical_use": None
    })
    
    for link in links:
        cable_id = link.get("cable_id")
        if not cable_id:
            continue
        
        fiber_count = extract_fiber_count(cable_id)
        if not fiber_count:
            continue
        
        cable_layer = link.get("cable_layer")
        source_layer = link.get("source_layer")
        target_layer = link.get("target_layer")
        
        # Classify by size
        if fiber_count >= 144:
            size_category = "feeder_trunk"
            typical_use = "FDH, OLT"
        elif fiber_count >= 96:
            size_category = "mid_distribution"
            typical_use = "FOSC chain"
        elif fiber_count >= 24:
            size_category = "distribution"
            typical_use = "Aerial terminals, MSTs"
        else:
            size_category = "access"
            typical_use = "ONTs"
        
        cable_size_analysis[f"{fiber_count}F"]["count"] += 1
        cable_size_analysis[f"{fiber_count}F"]["typical_use"] = typical_use
        cable_size_analysis[f"{fiber_count}F"]["size_category"] = size_category
        
        # Associate with nodes
        if source_layer in ["fdh", "olt"] and fiber_count >= 144:
            cable_size_analysis[f"{fiber_count}F"]["associated_nodes"].append({
                "node_id": link.get("source"),
                "layer": source_layer,
                "role": "feeder_source"
            })
        if target_layer in ["fdh", "olt"] and fiber_count >= 144:
            cable_size_analysis[f"{fiber_count}F"]["associated_nodes"].append({
                "node_id": link.get("target"),
                "layer": target_layer,
                "role": "feeder_target"
            })
    
    # Create summary rule for R14
    cable_size_summary = {}
    for size, data in sorted(cable_size_analysis.items(), key=lambda x: int(x[0].replace('F', '')), reverse=True):
        if data["count"] > 0:
            cable_size_summary[size] = {
                "count": data["count"],
                "typical_use": data["typical_use"],
                "examples": data["associated_nodes"][:5]
            }
    
    # Add R14 as a general rule (not node-specific)
    placement_analyses.append({
        "node_id": "NETWORK_WIDE",
        "layer": "all",
        "rule_id": "R14_CABLE_SIZE_HIERARCHY",
        "rule_description": "Cable size hierarchy: 288F/144F (feeder/trunk) → 96F (mid-distribution) → 48F/24F/12F (distribution) → 4F/1F (access)",
        "confidence_score": 0.95,
        "supporting_data": {
            "cable_size_distribution": cable_size_summary,
            "hierarchy": {
                "288F/144F": "Feeder / trunk - FDH, OLT",
                "96F": "Mid-distribution - FOSC chain",
                "48F/24F/12F": "Distribution - Aerial terminals, MSTs",
                "4F/1F": "Access - ONTs"
            }
        }
    })
    
    print(f"  ✓ Analyzed cable size hierarchy")
    
    # Summary
    print("\n" + "=" * 80)
    print("PLACEMENT LOGIC ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"  Total placement analyses: {len(placement_analyses)}")
    print(f"  - Aerial Terminals (R10): {aerial_terminal_count}")
    print(f"  - MST Terminals (R11): {mst_count}")
    print(f"  - FOSCs (R12): {fosc_count}")
    print(f"  - FDH Associations (R13): {fdh_association_count}")
    print(f"  - Cable Hierarchy (R14): 1")
    
    return {
        "placement_analyses": placement_analyses,
        "summary": {
            "total_analyses": len(placement_analyses),
            "aerial_terminals": aerial_terminal_count,
            "mst_terminals": mst_count,
            "foscs": fosc_count,
            "fdh_associations": fdh_association_count
        }
    }


# ============================================================================
# RULE SUMMARY GENERATION
# ============================================================================

def generate_rule_summary(verification_results: Dict[str, Any], 
                         patterns: Dict[str, Any],
                         placement_logic: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], str]:
    """
    Generate AI-readable JSON and human-readable text summaries of discovered rules.
    Each rule includes: rule_id, description, supporting_data, example_instances, confidence_score.
    """
    print("\n" + "=" * 80)
    print("GENERATING RULE SUMMARIES")
    print("=" * 80)
    
    discovered_rules = []
    
    # ========================================================================
    # Convert Verification Results to Rules
    # ========================================================================
    for rule_check in verification_results.get("rules_checked", []):
        rule_id = rule_check["rule_id"]
        status = rule_check["status"]
        
        # Calculate confidence based on status
        if status == "PASS":
            confidence = 1.0
        elif status == "WARNING":
            confidence = 0.7
        else:
            confidence = 0.3
        
        discovered_rules.append({
            "rule_id": rule_id,
            "description": rule_check["description"],
            "supporting_data": rule_check.get("details", {}),
            "example_instances": [],
            "confidence_score": confidence,
            "rule_type": "verification",
            "status": status
        })
    
    # ========================================================================
    # Convert Distance Patterns to Rules
    # ========================================================================
    distance_patterns = patterns.get("distance_patterns", {})
    
    # Drop cable length rule
    drop_stats = distance_patterns.get("drop_cable", {})
    if drop_stats:
        discovered_rules.append({
            "rule_id": "DISTANCE_DROP_CABLE_TYPICAL",
            "description": f"Typical drop cable length: {drop_stats.get('mean', 0)}m (median: {drop_stats.get('median', 0)}m, range: {drop_stats.get('min', 0)}-{drop_stats.get('max', 0)}m)",
            "supporting_data": drop_stats,
            "example_instances": [],
            "confidence_score": 0.95 if drop_stats.get("count", 0) > 100 else 0.75,
            "rule_type": "statistical_discovery"
        })
    
    # Stub cable length rule
    stub_stats = distance_patterns.get("stub_cable", {})
    if stub_stats:
        discovered_rules.append({
            "rule_id": "DISTANCE_STUB_CABLE_TYPICAL",
            "description": f"Typical stub cable length: {stub_stats.get('mean', 0)}m (median: {stub_stats.get('median', 0)}m, range: {stub_stats.get('min', 0)}-{stub_stats.get('max', 0)}m)",
            "supporting_data": stub_stats,
            "example_instances": [],
            "confidence_score": 0.95 if stub_stats.get("count", 0) > 100 else 0.75,
            "rule_type": "statistical_discovery"
        })
    
    # Fiber cable length rule
    fiber_stats = distance_patterns.get("fiber_cable", {})
    if fiber_stats:
        discovered_rules.append({
            "rule_id": "DISTANCE_FIBER_CABLE_TYPICAL",
            "description": f"Typical fiber cable length: {fiber_stats.get('mean', 0)}m (median: {fiber_stats.get('median', 0)}m, range: {fiber_stats.get('min', 0)}-{fiber_stats.get('max', 0)}m)",
            "supporting_data": fiber_stats,
            "example_instances": [],
            "confidence_score": 0.95 if fiber_stats.get("count", 0) > 100 else 0.75,
            "rule_type": "statistical_discovery"
        })
    
    # ========================================================================
    # Convert Branching Patterns to Rules
    # ========================================================================
    branching_patterns = patterns.get("branching_patterns", {})
    out_degree = branching_patterns.get("out_degree_by_layer", {})
    
    for layer, stats in out_degree.items():
        if stats.get("count", 0) > 0:
            discovered_rules.append({
                "rule_id": f"BRANCHING_{layer.upper()}_OUTDEGREE",
                "description": f"{layer.title()} typically has {stats.get('mean', 0):.1f} outgoing connections (median: {stats.get('median', 0)}, range: {stats.get('min', 0)}-{stats.get('max', 0)})",
                "supporting_data": stats,
                "example_instances": [],
                "confidence_score": 0.90 if stats.get("count", 0) > 50 else 0.70,
                "rule_type": "statistical_discovery"
            })
    
    # ========================================================================
    # Convert Capacity Patterns to Rules
    # ========================================================================
    capacity_patterns = patterns.get("capacity_patterns", {})
    fiber_counts = capacity_patterns.get("fiber_counts_by_cable_type", {})
    
    for cable_type, data in fiber_counts.items():
        if data.get("unique_values"):
            common_values = data.get("most_common", [])
            if common_values:
                most_common = common_values[0][0]
                discovered_rules.append({
                    "rule_id": f"CAPACITY_{cable_type.upper().replace(' ', '_')}_FIBER_COUNT",
                    "description": f"{cable_type.title()} most commonly uses {most_common} fibers",
                    "supporting_data": data,
                    "example_instances": common_values[:3],
                    "confidence_score": 0.85,
                    "rule_type": "statistical_discovery"
                })
    
    # ========================================================================
    # Convert Cable Transitions to Rules
    # ========================================================================
    cable_transitions = patterns.get("cable_transitions", {})
    transition_counts = cable_transitions.get("transition_counts", {})
    
    for transition, count in sorted(transition_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        discovered_rules.append({
            "rule_id": f"TRANSITION_{transition.replace('→', '_TO_').upper().replace(' ', '_')}",
            "description": f"Cable type transitions from {transition.split('→')[0]} to {transition.split('→')[1]} occur {count} times",
            "supporting_data": {"transition": transition, "count": count},
            "example_instances": cable_transitions.get("transition_examples", {}).get(transition, [])[:3],
            "confidence_score": 0.80,
            "rule_type": "statistical_discovery"
        })
    
    # ========================================================================
    # Convert Placement Logic to Rules
    # ========================================================================
    placement_logic = patterns.get("placement_logic", {})
    
    # Terminal placement
    term_placement = placement_logic.get("terminal_placement", {})
    terms_per_fosc = term_placement.get("terminals_per_fosc_stats", {})
    if terms_per_fosc.get("count", 0) > 0:
        discovered_rules.append({
            "rule_id": "PLACEMENT_TERMINALS_PER_FOSC",
            "description": f"On average, {terms_per_fosc.get('mean', 0):.1f} terminals connect to each FOSC (median: {terms_per_fosc.get('median', 0)}, range: {terms_per_fosc.get('min', 0)}-{terms_per_fosc.get('max', 0)})",
            "supporting_data": terms_per_fosc,
            "example_instances": [],
            "confidence_score": 0.90 if terms_per_fosc.get("count", 0) > 50 else 0.70,
            "rule_type": "statistical_discovery"
        })
    
    # FOSC placement
    fosc_placement = placement_logic.get("fosc_placement", {})
    foscs_per_fdh = fosc_placement.get("foscs_per_fdh_stats", {})
    if foscs_per_fdh.get("count", 0) > 0:
        discovered_rules.append({
            "rule_id": "PLACEMENT_FOSCS_PER_FDH",
            "description": f"On average, {foscs_per_fdh.get('mean', 0):.1f} FOSCs connect to each FDH (median: {foscs_per_fdh.get('median', 0)}, range: {foscs_per_fdh.get('min', 0)}-{foscs_per_fdh.get('max', 0)})",
            "supporting_data": foscs_per_fdh,
            "example_instances": [],
            "confidence_score": 0.90 if foscs_per_fdh.get("count", 0) > 50 else 0.70,
            "rule_type": "statistical_discovery"
        })
    
    # ========================================================================
    # Convert Next Hop Decisions to Rules
    # ========================================================================
    next_hop = patterns.get("next_hop_decisions", {})
    most_common = next_hop.get("most_common_transitions", [])
    
    for transition, count in most_common[:5]:
        discovered_rules.append({
            "rule_id": f"NEXT_HOP_{transition.replace('→', '_TO_').upper()}",
            "description": f"Most common next hop: {transition} (occurs {count} times)",
            "supporting_data": {
                "transition": transition,
                "count": count,
                "cable_types": next_hop.get("layer_transitions", {}).get(transition, {})
            },
            "example_instances": [],
            "confidence_score": 0.85,
            "rule_type": "statistical_discovery"
        })
    
    # ========================================================================
    # Convert Placement Logic to Rules (R10-R14)
    # ========================================================================
    if placement_logic:
        placement_analyses = placement_logic.get("placement_analyses", [])
        
        # Group by rule_id and create summary rules
        rule_groups = defaultdict(list)
        for analysis in placement_analyses:
            rule_id = analysis.get("rule_id")
            rule_groups[rule_id].append(analysis)
        
        for rule_id, analyses in rule_groups.items():
            if rule_id == "R14_CABLE_SIZE_HIERARCHY":
                # R14 is already a summary rule
                discovered_rules.append({
                    "rule_id": rule_id,
                    "description": analyses[0].get("rule_description"),
                    "supporting_data": analyses[0].get("supporting_data", {}),
                    "example_instances": [],
                    "confidence_score": analyses[0].get("confidence_score", 0.95),
                    "rule_type": "placement_logic"
                })
            else:
                # Create summary for R10-R13
                avg_confidence = statistics.mean([a.get("confidence_score", 0.5) for a in analyses])
                high_confidence = [a for a in analyses if a.get("confidence_score", 0) >= 0.7]
                
                discovered_rules.append({
                    "rule_id": rule_id,
                    "description": analyses[0].get("rule_description"),
                    "supporting_data": {
                        "total_nodes_analyzed": len(analyses),
                        "average_confidence": round(avg_confidence, 2),
                        "high_confidence_count": len(high_confidence),
                        "example_nodes": [a.get("node_id") for a in analyses[:5]]
                    },
                    "example_instances": [a.get("node_id") for a in high_confidence[:3]],
                    "confidence_score": round(avg_confidence, 2),
                    "rule_type": "placement_logic"
                })
    
    # ========================================================================
    # Generate Human-Readable Summary
    # ========================================================================
    summary_text = "=" * 80 + "\n"
    summary_text += "FIBER NETWORK DESIGN RULES SUMMARY\n"
    summary_text += "=" * 80 + "\n\n"
    
    summary_text += f"Total Rules Discovered: {len(discovered_rules)}\n\n"
    
    # Group by type
    verification_rules = [r for r in discovered_rules if r["rule_type"] == "verification"]
    discovery_rules = [r for r in discovered_rules if r["rule_type"] == "statistical_discovery"]
    placement_rules = [r for r in discovered_rules if r["rule_type"] == "placement_logic"]
    
    summary_text += f"Verified Rules: {len(verification_rules)}\n"
    summary_text += f"Discovered Rules: {len(discovery_rules)}\n"
    summary_text += f"Placement Logic Rules: {len(placement_rules)}\n\n"
    
    summary_text += "=" * 80 + "\n"
    summary_text += "VERIFIED CONNECTIVITY RULES\n"
    summary_text += "=" * 80 + "\n\n"
    
    for rule in verification_rules:
        summary_text += f"[{rule['rule_id']}]\n"
        summary_text += f"  Description: {rule['description']}\n"
        summary_text += f"  Status: {rule.get('status', 'UNKNOWN')}\n"
        summary_text += f"  Confidence: {rule['confidence_score']:.2f}\n\n"
    
    summary_text += "=" * 80 + "\n"
    summary_text += "STATISTICALLY DISCOVERED RULES\n"
    summary_text += "=" * 80 + "\n\n"
    
    # Group discovery rules by category
    distance_rules = [r for r in discovery_rules if "DISTANCE" in r["rule_id"]]
    branching_rules = [r for r in discovery_rules if "BRANCHING" in r["rule_id"]]
    capacity_rules = [r for r in discovery_rules if "CAPACITY" in r["rule_id"]]
    transition_rules = [r for r in discovery_rules if "TRANSITION" in r["rule_id"]]
    placement_rules = [r for r in discovery_rules if "PLACEMENT" in r["rule_id"]]
    next_hop_rules = [r for r in discovery_rules if "NEXT_HOP" in r["rule_id"]]
    
    if distance_rules:
        summary_text += "DISTANCE PATTERNS:\n"
        for rule in distance_rules:
            summary_text += f"  • {rule['description']} (confidence: {rule['confidence_score']:.2f})\n"
        summary_text += "\n"
    
    if branching_rules:
        summary_text += "BRANCHING PATTERNS:\n"
        for rule in branching_rules:
            summary_text += f"  • {rule['description']} (confidence: {rule['confidence_score']:.2f})\n"
        summary_text += "\n"
    
    if capacity_rules:
        summary_text += "CAPACITY PATTERNS:\n"
        for rule in capacity_rules:
            summary_text += f"  • {rule['description']} (confidence: {rule['confidence_score']:.2f})\n"
        summary_text += "\n"
    
    if transition_rules:
        summary_text += "CABLE TRANSITION PATTERNS:\n"
        for rule in transition_rules:
            summary_text += f"  • {rule['description']} (confidence: {rule['confidence_score']:.2f})\n"
        summary_text += "\n"
    
    if placement_rules:
        summary_text += "PLACEMENT LOGIC:\n"
        for rule in placement_rules:
            summary_text += f"  • {rule['description']} (confidence: {rule['confidence_score']:.2f})\n"
        summary_text += "\n"
    
    if next_hop_rules:
        summary_text += "NEXT HOP DECISIONS:\n"
        for rule in next_hop_rules:
            summary_text += f"  • {rule['description']} (confidence: {rule['confidence_score']:.2f})\n"
        summary_text += "\n"
    
    if placement_rules:
        summary_text += "=" * 80 + "\n"
        summary_text += "PLACEMENT LOGIC RULES (R10-R14)\n"
        summary_text += "=" * 80 + "\n\n"
        for rule in placement_rules:
            summary_text += f"[{rule['rule_id']}]\n"
            summary_text += f"  Description: {rule['description']}\n"
            summary_text += f"  Confidence: {rule['confidence_score']:.2f}\n"
            if rule.get("supporting_data", {}).get("total_nodes_analyzed"):
                summary_text += f"  Nodes Analyzed: {rule['supporting_data']['total_nodes_analyzed']}\n"
                summary_text += f"  High Confidence: {rule['supporting_data'].get('high_confidence_count', 0)}\n"
            summary_text += "\n"
    
    summary_text += "=" * 80 + "\n"
    summary_text += "END OF SUMMARY\n"
    summary_text += "=" * 80 + "\n"
    
    # Create JSON output
    discovered_rules_json = {
        "metadata": {
            "total_rules": len(discovered_rules),
            "verification_rules": len(verification_rules),
            "discovered_rules": len(discovery_rules),
            "placement_logic_rules": len(placement_rules),
            "generation_timestamp": None
        },
        "rules": discovered_rules
    }
    
    print(f"  ✓ Generated {len(discovered_rules)} rules")
    print(f"  ✓ Created human-readable summary ({len(summary_text)} characters)")
    
    return discovered_rules_json, summary_text


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution pipeline."""
    print("=" * 80)
    print("DESIGN RULES EXTRACTION PIPELINE")
    print("=" * 80)
    
    # Load data
    graph = load_logical_graph()
    paths = load_ont_paths()
    
    # Optionally load GeoJSON data
    geojson_data = {}
    optional_files = {
        "terminal": "terminal.geojson",
        "fosc": "splice closure.geojson",
        "fdh": "fdh.geojson",
        "olt": "OLT.geojson"
    }
    
    for key, filename in optional_files.items():
        data = load_geojson_optional(filename)
        if data:
            geojson_data[key] = data
            print(f"  Loaded {len(data)} {key} features from {filename}")
    
    # Step 1: Verify rules
    verification_results = verify_rules(graph, paths)
    
    # Step 2: Mine patterns
    patterns = mine_patterns(graph, paths, geojson_data if geojson_data else None)
    
    # Step 3: Analyze placement logic
    placement_logic = analyze_placement_logic(graph, paths, geojson_data if geojson_data else None)
    
    # Step 4: Generate summaries
    discovered_rules_json, summary_text = generate_rule_summary(verification_results, patterns, placement_logic)
    
    # Save outputs
    print("\n" + "=" * 80)
    print("SAVING OUTPUTS")
    print("=" * 80)
    
    with open("rule_verification_report.json", "w", encoding="utf-8") as f:
        json.dump(verification_results, f, indent=2)
    print("  ✓ Saved rule_verification_report.json")
    
    with open("pattern_discovery.json", "w", encoding="utf-8") as f:
        json.dump(patterns, f, indent=2)
    print("  ✓ Saved pattern_discovery.json")
    
    with open("discovered_rules.json", "w", encoding="utf-8") as f:
        json.dump(discovered_rules_json, f, indent=2)
    print("  ✓ Saved discovered_rules.json")
    
    with open("rules_summary.txt", "w", encoding="utf-8") as f:
        f.write(summary_text)
    print("  ✓ Saved rules_summary.txt")
    
    # Save placement rules analysis
    with open("placement_rules_analysis.json", "w", encoding="utf-8") as f:
        json.dump(placement_logic, f, indent=2)
    print("  ✓ Saved placement_rules_analysis.json")
    
    print("\n" + "=" * 80)
    print("✅ PIPELINE COMPLETE")
    print("=" * 80)
    print(f"\nGenerated {discovered_rules_json['metadata']['total_rules']} design rules:")
    print(f"  • {discovered_rules_json['metadata']['verification_rules']} verified rules")
    print(f"  • {discovered_rules_json['metadata']['discovered_rules']} statistically discovered rules")
    print(f"  • {discovered_rules_json['metadata']['placement_logic_rules']} placement logic rules")
    print(f"\nPlacement analysis:")
    print(f"  • {placement_logic['summary']['aerial_terminals']} Aerial Terminals analyzed (R10)")
    print(f"  • {placement_logic['summary']['mst_terminals']} MST Terminals analyzed (R11)")
    print(f"  • {placement_logic['summary']['foscs']} FOSCs analyzed (R12)")
    print(f"  • {placement_logic['summary']['fdh_associations']} FDH-FOSC associations (R13)")


if __name__ == "__main__":
    main()

