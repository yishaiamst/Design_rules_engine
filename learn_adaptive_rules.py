#!/usr/bin/env python3
"""
learn_adaptive_rules.py
-------------------------------------------------------------------------------
Learn Adaptive Placement Rules from Graph Data
-------------------------------------------------------------------------------
Improves placement classification accuracy by learning statistical baselines
and dynamically adjusting thresholds for R10-R14.

Objectives:
1. Compute statistical baselines (mean ± std) for drop/stub lengths, ONTs per terminal
2. Dynamically adjust thresholds for R10-R11 using those statistics
3. Re-evaluate all terminals and FOSCs with adaptive thresholds
4. Add decision_factors and confidence_score for each classified node
5. Produce adaptive_rules_summary.json and adaptive_rules_report.txt

Goal:
Transition from fixed engineering heuristics to a data-adaptive rule system
that learns local design norms directly from the graph dataset.
-------------------------------------------------------------------------------
"""

import json
import re
import statistics
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple


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
# STATISTICAL BASELINE COMPUTATION
# ============================================================================

def compute_statistical_baselines(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute statistical baselines (mean ± std) for:
    - Drop cable lengths
    - Stub cable lengths
    - ONTs per terminal
    """
    print("\n" + "=" * 80)
    print("COMPUTING STATISTICAL BASELINES")
    print("=" * 80)
    
    links = graph.get("links", [])
    
    # Collect drop cable lengths
    drop_cable_lengths = []
    stub_cable_lengths = []
    fiber_cable_lengths = []
    
    # Collect ONT counts per terminal
    terminal_ont_counts = defaultdict(int)
    terminal_connections = defaultdict(lambda: {"drops": 0, "stubs": 0, "fiber": 0})
    
    for link in links:
        cable_layer = link.get("cable_layer")
        length_m = link.get("length_m")
        source = link.get("source")
        source_layer = link.get("source_layer")
        target = link.get("target")
        target_layer = link.get("target_layer")
        
        if length_m and length_m > 0:
            if cable_layer == "drop cable":
                drop_cable_lengths.append(length_m)
            elif cable_layer == "stub cable":
                stub_cable_lengths.append(length_m)
            elif cable_layer == "fiber cable":
                fiber_cable_lengths.append(length_m)
        
        # Track terminal connections
        if source_layer == "terminal":
            if cable_layer == "drop cable":
                terminal_connections[source]["drops"] += 1
            elif cable_layer == "stub cable":
                terminal_connections[source]["stubs"] += 1
            elif cable_layer == "fiber cable":
                terminal_connections[source]["fiber"] += 1
            
            if target_layer == "ont":
                terminal_ont_counts[source] += 1
        
        if target_layer == "terminal":
            if source_layer == "ont":
                terminal_ont_counts[target] += 1
    
    # Also count from paths file if available
    try:
        with open("olt_ont_paths.json", "r", encoding="utf-8") as f:
            paths = json.load(f)
        
        for path in paths:
            path_segments = path.get("path", [])
            ont_id = path.get("ont_id")
            
            if not ont_id or not path_segments:
                continue
            
            for seg in path_segments:
                from_node = seg.get("from")
                from_layer = seg.get("from_layer")
                
                if from_layer == "terminal":
                    terminal_ont_counts[from_node] += 1
    except FileNotFoundError:
        pass
    
    # Calculate statistics
    def calc_stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}
        return {
            "count": len(values),
            "mean": round(statistics.mean(values), 2),
            "std": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "median": round(statistics.median(values), 2),
            "p25": round(statistics.quantiles(values, n=4)[0], 2) if len(values) > 1 else values[0],
            "p75": round(statistics.quantiles(values, n=4)[2], 2) if len(values) > 1 else values[-1]
        }
    
    ont_counts_list = list(terminal_ont_counts.values()) if terminal_ont_counts else [0]
    
    baselines = {
        "drop_cable_lengths": calc_stats(drop_cable_lengths),
        "stub_cable_lengths": calc_stats(stub_cable_lengths),
        "fiber_cable_lengths": calc_stats(fiber_cable_lengths),
        "onts_per_terminal": calc_stats(ont_counts_list),
        "terminal_connection_stats": {
            "total_terminals": len(terminal_connections),
            "with_drops": sum(1 for t in terminal_connections.values() if t["drops"] > 0),
            "with_stubs": sum(1 for t in terminal_connections.values() if t["stubs"] > 0),
            "with_fiber": sum(1 for t in terminal_connections.values() if t["fiber"] > 0)
        }
    }
    
    print(f"\nDrop Cable Lengths:")
    print(f"  Count: {baselines['drop_cable_lengths']['count']}")
    print(f"  Mean: {baselines['drop_cable_lengths']['mean']}m ± {baselines['drop_cable_lengths']['std']}m")
    print(f"  Range: {baselines['drop_cable_lengths']['min']}-{baselines['drop_cable_lengths']['max']}m")
    
    print(f"\nStub Cable Lengths:")
    print(f"  Count: {baselines['stub_cable_lengths']['count']}")
    print(f"  Mean: {baselines['stub_cable_lengths']['mean']}m ± {baselines['stub_cable_lengths']['std']}m")
    print(f"  Range: {baselines['stub_cable_lengths']['min']}-{baselines['stub_cable_lengths']['max']}m")
    
    print(f"\nONTs per Terminal:")
    print(f"  Count: {baselines['onts_per_terminal']['count']}")
    print(f"  Mean: {baselines['onts_per_terminal']['mean']} ± {baselines['onts_per_terminal']['std']}")
    print(f"  Range: {baselines['onts_per_terminal']['min']}-{baselines['onts_per_terminal']['max']}")
    
    return baselines


# ============================================================================
# ADAPTIVE THRESHOLD CALCULATION
# ============================================================================

def calculate_adaptive_thresholds(baselines: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate adaptive thresholds based on statistical baselines.
    Uses mean ± std for dynamic threshold adjustment.
    """
    print("\n" + "=" * 80)
    print("CALCULATING ADAPTIVE THRESHOLDS")
    print("=" * 80)
    
    drop_stats = baselines["drop_cable_lengths"]
    stub_stats = baselines["stub_cable_lengths"]
    ont_stats = baselines["onts_per_terminal"]
    
    # R10: Aerial Terminal thresholds
    # Original: 1-12 ONTs, avg drop ≤ 150m
    # Adaptive: Use mean ± std for ONT count, mean + 1.5*std for drop length
    aerial_ont_min = max(1, int(ont_stats["mean"] - 1.5 * ont_stats["std"]))
    aerial_ont_max = int(ont_stats["mean"] + 1.5 * ont_stats["std"])
    aerial_drop_max = drop_stats["mean"] + 1.5 * drop_stats["std"]
    
    # R11: MST thresholds
    # Original: ≤500m stub, 6-24 ONTs
    # Adaptive: Use mean ± std for ONT count, mean + 2*std for stub length
    mst_ont_min = max(1, int(ont_stats["mean"] - 1.0 * ont_stats["std"]))
    mst_ont_max = int(ont_stats["mean"] + 2.0 * ont_stats["std"])
    mst_stub_max = stub_stats["mean"] + 2.0 * stub_stats["std"]
    
    if mst_stub_max > 500:  # Cap at reasonable maximum
        mst_stub_max = 500
    
    # R12: FOSC thresholds
    # Original: ≥2 fiber connections OR ≥1800m segment
    # Adaptive: Use median + 1.5*std for length threshold
    fiber_stats = baselines["fiber_cable_lengths"]
    fosc_length_threshold = fiber_stats["median"] + 1.5 * fiber_stats["std"]
    if fosc_length_threshold < 1800:  # Keep minimum
        fosc_length_threshold = 1800
    
    thresholds = {
        "R10_AERIAL_TERMINAL": {
            "ont_count_min": aerial_ont_min,
            "ont_count_max": aerial_ont_max,
            "drop_length_max": round(aerial_drop_max, 2),
            "original": {"ont_min": 1, "ont_max": 12, "drop_max": 150},
            "adjustment": {
                "ont_min_change": aerial_ont_min - 1,
                "ont_max_change": aerial_ont_max - 12,
                "drop_max_change": round(aerial_drop_max - 150, 2)
            }
        },
        "R11_MST": {
            "ont_count_min": mst_ont_min,
            "ont_count_max": mst_ont_max,
            "stub_length_max": round(mst_stub_max, 2),
            "original": {"ont_min": 6, "ont_max": 24, "stub_max": 500},
            "adjustment": {
                "ont_min_change": mst_ont_min - 6,
                "ont_max_change": mst_ont_max - 24,
                "stub_max_change": round(mst_stub_max - 500, 2)
            }
        },
        "R12_FOSC": {
            "fiber_connections_min": 2,  # Keep fixed
            "fiber_length_threshold": round(fosc_length_threshold, 2),
            "original": {"length_threshold": 1800},
            "adjustment": {
                "length_threshold_change": round(fosc_length_threshold - 1800, 2)
            }
        }
    }
    
    print(f"\nR10 Aerial Terminal Adaptive Thresholds:")
    print(f"  ONT count: {aerial_ont_min}-{aerial_ont_max} (original: 1-12)")
    print(f"  Max drop length: {aerial_drop_max:.1f}m (original: 150m)")
    
    print(f"\nR11 MST Adaptive Thresholds:")
    print(f"  ONT count: {mst_ont_min}-{mst_ont_max} (original: 6-24)")
    print(f"  Max stub length: {mst_stub_max:.1f}m (original: 500m)")
    
    print(f"\nR12 FOSC Adaptive Thresholds:")
    print(f"  Fiber length threshold: {fosc_length_threshold:.1f}m (original: 1800m)")
    
    return thresholds


# ============================================================================
# ADAPTIVE RULE EVALUATION
# ============================================================================

def build_graph_structures(graph: Dict[str, Any]) -> Tuple[Dict, Dict, Dict]:
    """Build graph data structures."""
    nodes = {n["id"]: n["layer"] for n in graph.get("nodes", [])}
    links = graph.get("links", [])
    
    adjacency = defaultdict(list)
    reverse_adjacency = defaultdict(list)
    
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
    
    return nodes, adjacency, reverse_adjacency


def precompute_node_metrics(nodes: Dict, adjacency: Dict, reverse_adjacency: Dict) -> Dict[str, Dict]:
    """Pre-compute metrics for all nodes."""
    print("\nPre-computing node metrics...")
    
    node_metrics = {}
    
    for node_id, layer in nodes.items():
        if layer not in ["terminal", "splice closure"]:
            continue
        
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
            "connected_to_fdh": False
        }
        
        # Analyze outgoing
        for adj in adjacency.get(node_id, []):
            cable_layer = adj.get("cable_layer")
            cable_id = adj.get("cable_id")
            length_m = adj.get("length_m")
            
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
            if adj.get("target_layer") == "splice closure":
                metrics["connected_to_fosc"] = True
            if adj.get("target_layer") == "fdh":
                metrics["connected_to_fdh"] = True
        
        # Analyze incoming
        for rev_adj in reverse_adjacency.get(node_id, []):
            cable_layer = rev_adj.get("cable_layer")
            cable_id = rev_adj.get("cable_id")
            length_m = rev_adj.get("length_m")
            
            metrics["incoming_by_cable_type"][cable_layer] += 1
            if length_m:
                metrics["incoming_lengths"][cable_layer].append(length_m)
            if cable_id:
                metrics["incoming_cable_ids"].append(cable_id)
                fiber_count = extract_fiber_count(cable_id)
                if fiber_count:
                    metrics["fiber_counts_in"].append(fiber_count)
            
            if rev_adj.get("source_layer") == "splice closure":
                metrics["connected_to_fosc"] = True
            if rev_adj.get("source_layer") == "fdh":
                metrics["connected_to_fdh"] = True
        
        node_metrics[node_id] = metrics
    
    print(f"  Computed metrics for {len(node_metrics)} nodes")
    return node_metrics


def precompute_ont_counts() -> Dict[str, int]:
    """Pre-compute ONT counts per terminal."""
    downstream_ont_cache = defaultdict(int)
    
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
            
            for seg in path_segments:
                from_layer = seg.get("from_layer")
                from_node = seg.get("from")
                
                if from_layer == "terminal":
                    downstream_ont_cache[from_node] += 1
                elif from_layer == "splice closure":
                    downstream_ont_cache[from_node] += 1
    except FileNotFoundError:
        pass
    
    return downstream_ont_cache


def evaluate_adaptive_r10(node_id: str, metrics: Dict, ont_count: int,
                          thresholds: Dict, baselines: Dict) -> Dict[str, Any]:
    """Evaluate R10 Aerial Terminal with adaptive thresholds."""
    if metrics["layer"] != "terminal":
        return None
    
    t = thresholds["R10_AERIAL_TERMINAL"]
    
    # Calculate decision factors
    decision_factors = {}
    
    # ONT count factor
    ont_min = t["ont_count_min"]
    ont_max = t["ont_count_max"]
    if ont_min <= ont_count <= ont_max:
        decision_factors["ont_count"] = {
            "value": ont_count,
            "threshold": f"{ont_min}-{ont_max}",
            "matches": True,
            "weight": 0.3
        }
    else:
        decision_factors["ont_count"] = {
            "value": ont_count,
            "threshold": f"{ont_min}-{ont_max}",
            "matches": False,
            "weight": 0.3
        }
    
    # Stub cable factor
    has_stub = metrics["has_stub_cable"]
    decision_factors["no_stub"] = {
        "value": not has_stub,
        "matches": not has_stub,
        "weight": 0.25
    }
    
    # Drop cable factor
    has_drop = metrics["has_drop_cable"]
    drop_lengths = metrics["outgoing_lengths"].get("drop cable", [])
    avg_drop = statistics.mean(drop_lengths) if drop_lengths else None
    
    drop_max = t["drop_length_max"]
    if has_drop and avg_drop and avg_drop <= drop_max:
        decision_factors["drop_length"] = {
            "value": round(avg_drop, 2),
            "threshold": f"≤{drop_max}m",
            "matches": True,
            "weight": 0.25
        }
    elif has_drop:
        decision_factors["drop_length"] = {
            "value": round(avg_drop, 2) if avg_drop else None,
            "threshold": f"≤{drop_max}m",
            "matches": False,
            "weight": 0.25
        }
    else:
        decision_factors["drop_length"] = {
            "value": None,
            "threshold": f"≤{drop_max}m",
            "matches": False,
            "weight": 0.25
        }
    
    # Fiber connection factor
    has_fiber = (
        metrics["outgoing_by_cable_type"]["fiber cable"] > 0 or
        metrics["incoming_by_cable_type"]["fiber cable"] > 0
    )
    decision_factors["fiber_connection"] = {
        "value": has_fiber,
        "matches": has_fiber,
        "weight": 0.2
    }
    
    # Calculate confidence score
    total_weight = sum(f["weight"] for f in decision_factors.values())
    matched_weight = sum(f["weight"] for f in decision_factors.values() if f.get("matches", False))
    confidence_score = matched_weight / total_weight if total_weight > 0 else 0.0
    
    # Determine if matches criteria
    matches = all(
        f.get("matches", False) for f in decision_factors.values()
        if f.get("weight", 0) > 0.1
    )
    
    return {
        "node_id": node_id,
        "layer": "terminal",
        "rule_id": "R10_AERIAL_TERMINAL_ADAPTIVE",
        "rule_description": f"Aerial Terminal (adaptive): {ont_min}-{ont_max} ONTs, no stub, avg drop ≤{drop_max}m",
        "confidence_score": round(confidence_score, 3),
        "matches_criteria": matches,
        "decision_factors": decision_factors,
        "supporting_data": {
            "ont_count": ont_count,
            "has_stub": has_stub,
            "has_drop": has_drop,
            "avg_drop_length_m": round(avg_drop, 2) if avg_drop else None,
            "has_fiber_connection": has_fiber,
            "adaptive_thresholds": {
                "ont_min": ont_min,
                "ont_max": ont_max,
                "drop_max": drop_max
            }
        }
    }


def evaluate_adaptive_r11(node_id: str, metrics: Dict, ont_count: int,
                          adjacency: Dict, reverse_adjacency: Dict,
                          thresholds: Dict) -> Dict[str, Any]:
    """Evaluate R11 MST with adaptive thresholds."""
    if metrics["layer"] != "terminal":
        return None
    
    t = thresholds["R11_MST"]
    
    # Check for stub cable
    has_stub = metrics["has_stub_cable"]
    if not has_stub:
        return None
    
    # Find stub connection
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
    
    # Calculate decision factors
    decision_factors = {}
    
    # ONT count factor
    ont_min = t["ont_count_min"]
    ont_max = t["ont_count_max"]
    if ont_min <= ont_count <= ont_max:
        decision_factors["ont_count"] = {
            "value": ont_count,
            "threshold": f"{ont_min}-{ont_max}",
            "matches": True,
            "weight": 0.4
        }
    else:
        decision_factors["ont_count"] = {
            "value": ont_count,
            "threshold": f"{ont_min}-{ont_max}",
            "matches": False,
            "weight": 0.4
        }
    
    # Stub distance factor
    stub_max = t["stub_length_max"]
    if stub_distance and stub_distance <= stub_max:
        decision_factors["stub_distance"] = {
            "value": round(stub_distance, 2),
            "threshold": f"≤{stub_max}m",
            "matches": True,
            "weight": 0.3
        }
    else:
        decision_factors["stub_distance"] = {
            "value": round(stub_distance, 2) if stub_distance else None,
            "threshold": f"≤{stub_max}m",
            "matches": False,
            "weight": 0.3
        }
    
    # FOSC connection factor
    decision_factors["fosc_connection"] = {
        "value": connected_fosc is not None,
        "matches": connected_fosc is not None,
        "weight": 0.3
    }
    
    # Calculate confidence
    total_weight = sum(f["weight"] for f in decision_factors.values())
    matched_weight = sum(f["weight"] for f in decision_factors.values() if f.get("matches", False))
    confidence_score = matched_weight / total_weight if total_weight > 0 else 0.0
    
    matches = all(
        f.get("matches", False) for f in decision_factors.values()
        if f.get("weight", 0) > 0.1
    )
    
    return {
        "node_id": node_id,
        "layer": "terminal",
        "rule_id": "R11_MST_ADAPTIVE",
        "rule_description": f"MST (adaptive): Stub cable from FOSC, ≤{stub_max}m, {ont_min}-{ont_max} ONTs",
        "confidence_score": round(confidence_score, 3),
        "matches_criteria": matches,
        "decision_factors": decision_factors,
        "supporting_data": {
            "ont_count": ont_count,
            "stub_distance_m": round(stub_distance, 2) if stub_distance else None,
            "connected_fosc": connected_fosc,
            "adaptive_thresholds": {
                "ont_min": ont_min,
                "ont_max": ont_max,
                "stub_max": stub_max
            }
        }
    }


def evaluate_r11_long_reach(node_id: str, metrics: Dict, ont_count: int,
                            adjacency: Dict, reverse_adjacency: Dict,
                            thresholds: Dict) -> Dict[str, Any]:
    """
    Evaluate R11 Long-Reach MST with extended threshold (up to 2500m).
    """
    if metrics["layer"] != "terminal":
        return None
    
    t = thresholds["R11_MST"]
    
    # Check for stub cable
    has_stub = metrics["has_stub_cable"]
    if not has_stub:
        return None
    
    # Find stub connection
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
    
    # Long-reach threshold: 2500m
    stub_max_long_reach = 2500.0
    
    # Calculate decision factors
    decision_factors = {}
    
    # ONT count factor (same as regular R11)
    ont_min = t["ont_count_min"]
    ont_max = t["ont_count_max"]
    if ont_min <= ont_count <= ont_max:
        decision_factors["ont_count"] = {
            "value": ont_count,
            "threshold": f"{ont_min}-{ont_max}",
            "matches": True,
            "weight": 0.4
        }
    else:
        decision_factors["ont_count"] = {
            "value": ont_count,
            "threshold": f"{ont_min}-{ont_max}",
            "matches": False,
            "weight": 0.4
        }
    
    # Stub distance factor (extended to 2500m)
    if stub_distance and stub_distance <= stub_max_long_reach:
        decision_factors["stub_distance"] = {
            "value": round(stub_distance, 2),
            "threshold": f"≤{stub_max_long_reach}m (long-reach)",
            "matches": True,
            "weight": 0.3
        }
        # Classify as long-reach if > 500m
        is_long_reach = stub_distance > 500
    else:
        decision_factors["stub_distance"] = {
            "value": round(stub_distance, 2) if stub_distance else None,
            "threshold": f"≤{stub_max_long_reach}m (long-reach)",
            "matches": False,
            "weight": 0.3
        }
        is_long_reach = False
    
    # FOSC connection factor
    decision_factors["fosc_connection"] = {
        "value": connected_fosc is not None,
        "matches": connected_fosc is not None,
        "weight": 0.3
    }
    
    # Calculate confidence
    total_weight = sum(f["weight"] for f in decision_factors.values())
    matched_weight = sum(f["weight"] for f in decision_factors.values() if f.get("matches", False))
    confidence_score = matched_weight / total_weight if total_weight > 0 else 0.0
    
    matches = all(
        f.get("matches", False) for f in decision_factors.values()
        if f.get("weight", 0) > 0.1
    )
    
    # This is always long-reach (only called for >500m)
    return {
        "node_id": node_id,
        "layer": "terminal",
        "rule_id": "R11_MST_LONG_REACH",
        "rule_description": f"MST (long-reach): Stub cable from FOSC, ≤{stub_max_long_reach}m, {ont_min}-{ont_max} ONTs",
        "confidence_score": round(confidence_score, 3),
        "matches_criteria": matches,
        "is_long_reach": True,
        "decision_factors": decision_factors,
        "supporting_data": {
            "ont_count": ont_count,
            "stub_distance_m": round(stub_distance, 2) if stub_distance else None,
            "connected_fosc": connected_fosc,
            "stub_max_standard": t["stub_length_max"],
            "stub_max_long_reach": stub_max_long_reach,
            "adaptive_thresholds": {
                "ont_min": ont_min,
                "ont_max": ont_max,
                "stub_max": stub_max_long_reach
            }
        }
    }


def evaluate_adaptive_r12(node_id: str, metrics: Dict, thresholds: Dict) -> Dict[str, Any]:
    """Evaluate R12 FOSC with adaptive thresholds."""
    if metrics["layer"] != "splice closure":
        return None
    
    t = thresholds["R12_FOSC"]
    
    # Calculate decision factors
    decision_factors = {}
    
    # Fiber connections factor
    fiber_connections = (
        metrics["outgoing_by_cable_type"]["fiber cable"] +
        metrics["incoming_by_cable_type"]["fiber cable"]
    )
    fiber_min = t["fiber_connections_min"]
    if fiber_connections >= fiber_min:
        decision_factors["fiber_connections"] = {
            "value": fiber_connections,
            "threshold": f"≥{fiber_min}",
            "matches": True,
            "weight": 0.3
        }
    else:
        decision_factors["fiber_connections"] = {
            "value": fiber_connections,
            "threshold": f"≥{fiber_min}",
            "matches": False,
            "weight": 0.3
        }
    
    # Fiber length factor
    all_fiber_lengths = (
        metrics["outgoing_lengths"].get("fiber cable", []) +
        metrics["incoming_lengths"].get("fiber cable", [])
    )
    max_fiber_length = max(all_fiber_lengths) if all_fiber_lengths else 0
    length_threshold = t["fiber_length_threshold"]
    
    if max_fiber_length >= length_threshold:
        decision_factors["fiber_length"] = {
            "value": round(max_fiber_length, 2),
            "threshold": f"≥{length_threshold}m",
            "matches": True,
            "weight": 0.25
        }
    else:
        decision_factors["fiber_length"] = {
            "value": round(max_fiber_length, 2),
            "threshold": f"≥{length_threshold}m",
            "matches": False,
            "weight": 0.25
        }
    
    # Fiber ID change factor
    all_cable_ids = list(set(metrics["outgoing_cable_ids"] + metrics["incoming_cable_ids"]))
    unique_cable_ids = len([cid for cid in all_cable_ids if cid])
    if unique_cable_ids >= 2:
        decision_factors["fiber_id_change"] = {
            "value": unique_cable_ids,
            "threshold": "≥2",
            "matches": True,
            "weight": 0.25
        }
    else:
        decision_factors["fiber_id_change"] = {
            "value": unique_cable_ids,
            "threshold": "≥2",
            "matches": False,
            "weight": 0.25
        }
    
    # Fiber count transition factor
    fiber_counts_in = metrics["fiber_counts_in"]
    fiber_counts_out = metrics["fiber_counts_out"]
    has_transition = False
    if fiber_counts_in and fiber_counts_out:
        avg_in = statistics.mean(fiber_counts_in) if fiber_counts_in else None
        avg_out = statistics.mean(fiber_counts_out) if fiber_counts_out else None
        if avg_in and avg_out and abs(avg_in - avg_out) > 10:
            has_transition = True
    
    decision_factors["fiber_transition"] = {
        "value": has_transition,
        "matches": has_transition,
        "weight": 0.2
    }
    
    # Calculate confidence (any factor matching is sufficient)
    matching_factors = sum(1 for f in decision_factors.values() if f.get("matches", False))
    confidence_score = matching_factors / len(decision_factors) if decision_factors else 0.0
    
    matches = matching_factors > 0  # Any factor matches
    
    return {
        "node_id": node_id,
        "layer": "splice closure",
        "rule_id": "R12_FOSC_ADAPTIVE",
        "rule_description": f"FOSC (adaptive): ≥{fiber_min} fiber connections OR ≥{length_threshold}m segment OR fiber ID change OR fiber count transition",
        "confidence_score": round(confidence_score, 3),
        "matches_criteria": matches,
        "decision_factors": decision_factors,
        "supporting_data": {
            "fiber_connections": fiber_connections,
            "max_fiber_length_m": round(max_fiber_length, 2),
            "unique_cable_ids": unique_cable_ids,
            "has_fiber_transition": has_transition,
            "adaptive_thresholds": {
                "fiber_min": fiber_min,
                "length_threshold": length_threshold
            }
        }
    }


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def learn_adaptive_rules(graph_path: str = "logical_fiber_graph.json") -> Dict[str, Any]:
    """Main adaptive learning pipeline."""
    print("LEARNING ADAPTIVE PLACEMENT RULES")
    print("=" * 60)
    
    # Load graph
    graph = load_logical_graph(graph_path)
    
    # Step 1: Compute statistical baselines
    print("Computing baselines...")
    baselines = compute_statistical_baselines(graph)
    
    # Step 2: Calculate adaptive thresholds
    thresholds = calculate_adaptive_thresholds(baselines)
    
    # Step 3: Build graph structures
    print("Building graph structures...")
    nodes, adjacency, reverse_adjacency = build_graph_structures(graph)
    
    # Step 4: Pre-compute metrics
    node_metrics = precompute_node_metrics(nodes, adjacency, reverse_adjacency)
    ont_counts = precompute_ont_counts()
    
    # Step 5: Re-evaluate with adaptive thresholds
    print("Re-evaluating with adaptive thresholds...")
    
    adaptive_results = []
    
    terminal_count = 0
    fosc_count = 0
    
    for node_id, metrics in node_metrics.items():
        layer = metrics["layer"]
        
        if layer == "terminal":
            terminal_count += 1
            ont_count = ont_counts.get(node_id, 0)
            
            # R10
            r10_result = evaluate_adaptive_r10(node_id, metrics, ont_count, thresholds, baselines)
            if r10_result:
                adaptive_results.append(r10_result)
            
            # Check stub distance first to determine which rule to apply
            stub_distance = None
            for adj in adjacency.get(node_id, []):
                if adj.get("cable_layer") == "stub cable" and adj.get("target_layer") == "splice closure":
                    stub_distance = adj.get("length_m")
                    break
            if not stub_distance:
                for rev_adj in reverse_adjacency.get(node_id, []):
                    if rev_adj.get("cable_layer") == "stub cable" and rev_adj.get("source_layer") == "splice closure":
                        stub_distance = rev_adj.get("length_m")
                        break
            
            # Apply standard R11 for ≤500m, long-reach for >500m and ≤2500m
            if stub_distance and stub_distance <= 500:
                # Standard R11
                r11_result = evaluate_adaptive_r11(node_id, metrics, ont_count, adjacency, reverse_adjacency, thresholds)
                if r11_result:
                    adaptive_results.append(r11_result)
            elif stub_distance and 500 < stub_distance <= 2500:
                # Long-reach R11
                r11_long_reach_result = evaluate_r11_long_reach(node_id, metrics, ont_count, adjacency, reverse_adjacency, thresholds)
                if r11_long_reach_result:
                    adaptive_results.append(r11_long_reach_result)
            else:
                # Still try standard R11 for terminals without stub distance info
                r11_result = evaluate_adaptive_r11(node_id, metrics, ont_count, adjacency, reverse_adjacency, thresholds)
                if r11_result:
                    adaptive_results.append(r11_result)
        
        elif layer == "splice closure":
            fosc_count += 1
            # R12
            r12_result = evaluate_adaptive_r12(node_id, metrics, thresholds)
            if r12_result:
                adaptive_results.append(r12_result)
    
    # Summary
    by_rule = defaultdict(list)
    for result in adaptive_results:
        by_rule[result["rule_id"]].append(result)
    
    matches_by_rule = {}
    avg_confidence_by_rule = {}
    for rule_id, results in by_rule.items():
        matches = sum(1 for r in results if r.get("matches_criteria", False))
        matches_by_rule[rule_id] = matches
        avg_confidence = statistics.mean([r.get("confidence_score", 0) for r in results])
        avg_confidence_by_rule[rule_id] = round(avg_confidence, 3)
    
    print(f"\n  Evaluations: {len(adaptive_results)} | Terminals: {terminal_count} | FOSCs: {fosc_count}")
    print(f"  Results by rule:")
    for rule_id, results in sorted(by_rule.items()):
        matches = matches_by_rule[rule_id]
        avg_conf = avg_confidence_by_rule[rule_id]
        print(f"    {rule_id}: {matches}/{len(results)} matches ({matches/len(results)*100:.1f}%), conf: {avg_conf}")
    
    # Generate long-reach comparison
    long_reach_comparison = generate_long_reach_comparison(by_rule, matches_by_rule, avg_confidence_by_rule)
    
    return {
        "baselines": baselines,
        "adaptive_thresholds": thresholds,
        "adaptive_results": adaptive_results,
        "summary": {
            "total_evaluations": len(adaptive_results),
            "terminals_processed": terminal_count,
            "foscs_processed": fosc_count,
            "by_rule": {k: len(v) for k, v in by_rule.items()},
            "matches_by_rule": matches_by_rule,
            "avg_confidence_by_rule": avg_confidence_by_rule
        },
        "long_reach_comparison": long_reach_comparison
    }


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_adaptive_summary(adaptive_data: Dict[str, Any]) -> None:
    """Generate adaptive_rules_summary.json."""
    summary = {
        "metadata": {
            "generation_timestamp": None,
            "total_evaluations": adaptive_data["summary"]["total_evaluations"]
        },
        "baselines": adaptive_data["baselines"],
        "adaptive_thresholds": adaptive_data["adaptive_thresholds"],
        "results_summary": adaptive_data["summary"]
    }
    
    with open("adaptive_rules_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n  ✓ Saved adaptive_rules_summary.json")


def generate_long_reach_comparison(by_rule: Dict, matches_by_rule: Dict, 
                                  avg_confidence_by_rule: Dict) -> Dict[str, Any]:
    """Generate comparison between standard R11 and long-reach R11."""
    
    r11_standard = by_rule.get("R11_MST_ADAPTIVE", [])
    r11_long_reach = by_rule.get("R11_MST_LONG_REACH", [])
    
    # Collect stub distances
    standard_stub_distances = [
        r["supporting_data"]["stub_distance_m"] 
        for r in r11_standard 
        if r.get("matches_criteria", False) and r["supporting_data"].get("stub_distance_m")
    ]
    
    long_reach_stub_distances = [
        r["supporting_data"]["stub_distance_m"] 
        for r in r11_long_reach 
        if r.get("matches_criteria", False) and r["supporting_data"].get("stub_distance_m")
    ]
    
    # Calculate statistics
    def calc_stats(values: List[float]) -> Dict:
        if not values:
            return {}
        return {
            "count": len(values),
            "mean": round(statistics.mean(values), 2),
            "median": round(statistics.median(values), 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "std": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0
        }
    
    standard_matches = sum(1 for r in r11_standard if r.get("matches_criteria", False))
    long_reach_matches = sum(1 for r in r11_long_reach if r.get("matches_criteria", False))
    
    # Count by distance ranges (all MST terminals)
    distance_ranges = {
        "0-500m": 0,
        "500-1000m": 0,
        "1000-1500m": 0,
        "1500-2000m": 0,
        "2000-2500m": 0,
        ">2500m": 0
    }
    
    all_mst_distances = standard_stub_distances + long_reach_stub_distances
    for dist in all_mst_distances:
        if dist <= 500:
            distance_ranges["0-500m"] += 1
        elif dist <= 1000:
            distance_ranges["500-1000m"] += 1
        elif dist <= 1500:
            distance_ranges["1000-1500m"] += 1
        elif dist <= 2000:
            distance_ranges["1500-2000m"] += 1
        elif dist <= 2500:
            distance_ranges["2000-2500m"] += 1
        else:
            distance_ranges[">2500m"] += 1
    
    # Calculate improvement: compare against previous adaptive results
    # Load previous results for comparison
    try:
        with open("adaptive_rules_summary.json", "r", encoding="utf-8") as f:
            prev_data = json.load(f)
        prev_r11_matches = prev_data.get("results_summary", {}).get("matches_by_rule", {}).get("R11_MST_ADAPTIVE", 0)
    except (FileNotFoundError, KeyError):
        prev_r11_matches = standard_matches  # Use current as baseline
    
    # Improvement is the additional terminals captured by long-reach (500-2500m)
    total_with_stubs = len(r11_standard) + len(r11_long_reach)
    increase_pct = (long_reach_matches / total_with_stubs * 100) if total_with_stubs > 0 else 0
    
    return {
        "before": {
            "rule_id": "R11_MST_ADAPTIVE",
            "evaluations": len(r11_standard),
            "matches": standard_matches,
            "match_rate": round(standard_matches / len(r11_standard) * 100, 2) if r11_standard else 0,
            "avg_confidence": avg_confidence_by_rule.get("R11_MST_ADAPTIVE", 0),
            "stub_distance_stats": calc_stats(standard_stub_distances),
            "max_stub_threshold": 500
        },
        "after": {
            "rule_id": "R11_MST_LONG_REACH",
            "evaluations": len(r11_long_reach),
            "matches": long_reach_matches,
            "match_rate": round(long_reach_matches / len(r11_long_reach) * 100, 2) if r11_long_reach else 0,
            "avg_confidence": avg_confidence_by_rule.get("R11_MST_LONG_REACH", 0),
            "stub_distance_stats": calc_stats(long_reach_stub_distances),
            "max_stub_threshold": 2500
        },
        "improvement": {
            "additional_matches": long_reach_matches,
            "percentage_increase": round(increase_pct, 2),
            "total_matches": long_reach_matches + standard_matches,
            "newly_classified": long_reach_matches,
            "total_terminals_with_stubs": total_with_stubs,
            "previous_adaptive_matches": prev_r11_matches,
            "improvement_over_previous": long_reach_matches + standard_matches - prev_r11_matches
        },
        "stub_distance_distribution": distance_ranges,
        "combined_stub_stats": calc_stats(all_mst_distances)
    }


def generate_adaptive_report(adaptive_data: Dict[str, Any]) -> None:
    """Generate adaptive_rules_report.txt comparing static vs adaptive."""
    
    # Load original refined results for comparison
    try:
        with open("placement_rules_analysis.json", "r", encoding="utf-8") as f:
            original_data = json.load(f)
        original_analyses = original_data.get("placement_analyses", [])
    except FileNotFoundError:
        original_analyses = []
    
    # Group original results by rule
    original_by_rule = defaultdict(list)
    for analysis in original_analyses:
        rule_id = analysis.get("rule_id", "")
        if "REFINED" in rule_id:
            original_by_rule[rule_id].append(analysis)
    
    # Group adaptive results by rule
    adaptive_by_rule = defaultdict(list)
    for result in adaptive_data["adaptive_results"]:
        rule_id = result.get("rule_id", "")
        if "ADAPTIVE" in rule_id:
            adaptive_by_rule[rule_id].append(result)
    
    report = "ADAPTIVE RULES REPORT\n"
    report += "=" * 60 + "\n\n"
    
    # Statistical Baselines (condensed)
    baselines = adaptive_data["baselines"]
    report += "BASELINES:\n"
    report += f"  Drop: {baselines['drop_cable_lengths']['mean']:.0f}m (med: {baselines['drop_cable_lengths']['median']:.0f}m)\n"
    report += f"  Stub: {baselines['stub_cable_lengths']['mean']:.0f}m (med: {baselines['stub_cable_lengths']['median']:.0f}m)\n"
    report += f"  ONTs/Terminal: {baselines['onts_per_terminal']['mean']:.1f} (med: {baselines['onts_per_terminal']['median']:.1f})\n\n"
    
    # Adaptive Thresholds (condensed)
    report += "ADAPTIVE THRESHOLDS:\n"
    thresholds = adaptive_data["adaptive_thresholds"]
    for rule_id, threshold_data in thresholds.items():
        report += f"  {rule_id}: "
        key_vals = [f"{k}={v}" for k, v in threshold_data.items() if k not in ["original", "adjustment"]]
        report += ", ".join(key_vals[:3]) + "\n"  # Limit to first 3 values
    report += "\n"
    
    # Comparison (condensed)
    report += "STATIC vs ADAPTIVE:\n"
    rule_mapping = {
        "R10_AERIAL_TERMINAL_REFINED": "R10_AERIAL_TERMINAL_ADAPTIVE",
        "R11_MST_REFINED": "R11_MST_ADAPTIVE",
        "R12_FOSC_REFINED": "R12_FOSC_ADAPTIVE"
    }
    
    for original_rule, adaptive_rule in rule_mapping.items():
        original_results = original_by_rule.get(original_rule, [])
        adaptive_results = adaptive_by_rule.get(adaptive_rule, [])
        
        if not original_results and not adaptive_results:
            continue
        
        original_matches = sum(1 for r in original_results if r.get("matches_criteria", False))
        adaptive_matches = sum(1 for r in adaptive_results if r.get("matches_criteria", False))
        
        original_avg_conf = statistics.mean([r.get("confidence_score", 0) for r in original_results]) if original_results else 0
        adaptive_avg_conf = statistics.mean([r.get("confidence_score", 0) for r in adaptive_results]) if adaptive_results else 0
        
        improvement = ((adaptive_matches - original_matches) / len(adaptive_results) * 100) if adaptive_results else 0
        report += f"  {original_rule}:\n"
        report += f"    Static: {original_matches}/{len(original_results)} ({original_matches/len(original_results)*100:.1f}%), conf: {original_avg_conf:.3f}\n"
        report += f"    Adaptive: {adaptive_matches}/{len(adaptive_results)} ({adaptive_matches/len(adaptive_results)*100:.1f}%), conf: {adaptive_avg_conf:.3f}\n"
        report += f"    Improvement: {improvement:+.1f}%\n\n"
    
    report += "=" * 60 + "\n"
    
    with open("adaptive_rules_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"  ✓ Saved adaptive_rules_report.txt")


def generate_long_reach_outputs(comparison: Dict[str, Any]) -> None:
    """Generate long-reach MST comparison outputs."""
    
    # Generate JSON comparison
    with open("mst_long_reach_comparison.json", "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    
    print(f"  ✓ Saved mst_long_reach_comparison.json")
    
    # Generate concise summary text
    summary = "MST LONG-REACH REFINEMENT SUMMARY\n"
    summary += "=" * 60 + "\n\n"
    summary += "R11 Threshold: 500m → 2500m\n\n"
    
    summary += f"BEFORE: {comparison['before']['matches']}/{comparison['before']['evaluations']} matches "
    summary += f"({comparison['before']['match_rate']:.1f}%), conf: {comparison['before']['avg_confidence']:.3f}\n"
    
    summary += f"AFTER: {comparison['after']['matches']}/{comparison['after']['evaluations']} matches "
    summary += f"({comparison['after']['match_rate']:.1f}%), conf: {comparison['after']['avg_confidence']:.3f}\n\n"
    
    summary += f"IMPROVEMENT: +{comparison['improvement']['additional_matches']} matches "
    summary += f"({comparison['improvement']['percentage_increase']:.1f}% increase)\n"
    summary += f"Total: {comparison['improvement']['total_matches']} matches\n\n"
    
    summary += "Distance Distribution:\n"
    for range_name, count in comparison['stub_distance_distribution'].items():
        if count > 0:
            summary += f"  {range_name}: {count}\n"
    
    if comparison['combined_stub_stats']:
        stats = comparison['combined_stub_stats']
        summary += f"\nStats: Mean={stats.get('mean', 0)}m, Median={stats.get('median', 0)}m, "
        summary += f"Range={stats.get('min', 0)}-{stats.get('max', 0)}m\n"
    
    summary += "\n" + "=" * 60 + "\n"
    
    with open("mst_long_reach_summary.txt", "w", encoding="utf-8") as f:
        f.write(summary)
    
    print(f"  ✓ Saved mst_long_reach_summary.txt")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution."""
    # Learn adaptive rules
    adaptive_data = learn_adaptive_rules()
    
    # Generate outputs
    print("\nGenerating outputs...")
    
    generate_adaptive_summary(adaptive_data)
    generate_adaptive_report(adaptive_data)
    
    # Generate long-reach specific outputs
    if "long_reach_comparison" in adaptive_data:
        generate_long_reach_outputs(adaptive_data["long_reach_comparison"])
    
    print("\n✅ ADAPTIVE LEARNING COMPLETE")
    print(f"Evaluations: {adaptive_data['summary']['total_evaluations']}, "
          f"Matches: {sum(adaptive_data['summary']['matches_by_rule'].values())}")
    
    if "long_reach_comparison" in adaptive_data:
        comp = adaptive_data["long_reach_comparison"]
        print(f"Long-Reach: {comp['before']['matches']} → {comp['after']['matches']} "
              f"(+{comp['improvement']['additional_matches']}, {comp['improvement']['percentage_increase']:.1f}%)")


if __name__ == "__main__":
    main()

