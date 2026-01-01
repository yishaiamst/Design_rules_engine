#!/usr/bin/env python3
"""
extract_design_intent.py
-------------------------------------------------------------------------------
Design Intent Extraction for Fiber Network Elements
-------------------------------------------------------------------------------
Extends design rules to learn and explain design intent for all network elements
(ONT, Terminal, MST, FOSC, FDH, OLT) using existing analysis outputs.

Objectives:
1. Infer design rationale behind each placement type
2. Compute supporting metrics per element
3. Generate textual explanations
4. Cluster design intents into reusable templates
5. Output design_intent_summary.json and design_templates.txt

Uses:
- adaptive_rules_summary.json
- placement_rules_analysis.json
- logical_fiber_graph.json
- mst_long_reach_comparison.json
- olt_ont_paths.json
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

def load_all_data() -> Dict[str, Any]:
    """Load all required data files."""
    print("=" * 80)
    print("LOADING DATA FOR DESIGN INTENT EXTRACTION")
    print("=" * 80)
    
    data = {}
    
    # Load logical graph
    print("\nLoading logical graph...")
    with open("logical_fiber_graph.json", "r", encoding="utf-8") as f:
        data["graph"] = json.load(f)
    print(f"  ✓ Loaded {len(data['graph'].get('nodes', []))} nodes, {len(data['graph'].get('links', []))} links")
    
    # Load ONT paths
    print("\nLoading ONT paths...")
    with open("olt_ont_paths.json", "r", encoding="utf-8") as f:
        data["paths"] = json.load(f)
    print(f"  ✓ Loaded {len(data['paths'])} ONT paths")
    
    # Load adaptive rules summary
    print("\nLoading adaptive rules summary...")
    try:
        with open("adaptive_rules_summary.json", "r", encoding="utf-8") as f:
            data["adaptive_rules"] = json.load(f)
        print(f"  ✓ Loaded adaptive thresholds and baselines")
    except FileNotFoundError:
        print("  ⚠ adaptive_rules_summary.json not found")
        data["adaptive_rules"] = {}
    
    # Load placement rules analysis
    print("\nLoading placement rules analysis...")
    try:
        with open("placement_rules_analysis.json", "r", encoding="utf-8") as f:
            data["placement_rules"] = json.load(f)
        print(f"  ✓ Loaded placement rules analysis")
    except FileNotFoundError:
        print("  ⚠ placement_rules_analysis.json not found")
        data["placement_rules"] = {}
    
    # Load MST long-reach comparison
    print("\nLoading MST long-reach comparison...")
    try:
        with open("mst_long_reach_comparison.json", "r", encoding="utf-8") as f:
            data["mst_long_reach"] = json.load(f)
        print(f"  ✓ Loaded long-reach MST data")
    except FileNotFoundError:
        print("  ⚠ mst_long_reach_comparison.json not found")
        data["mst_long_reach"] = {}
    
    return data


def extract_fiber_count(cable_id: str) -> Optional[int]:
    """Extract fiber count from cable ID."""
    if not cable_id:
        return None
    match = re.search(r'(\d+)FOC', str(cable_id).upper())
    return int(match.group(1)) if match else None


# ============================================================================
# METRIC COMPUTATION
# ============================================================================

def compute_element_metrics(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Compute comprehensive metrics for each network element.
    Returns dict mapping node_id -> metrics
    """
    print("\n" + "=" * 80)
    print("COMPUTING ELEMENT METRICS")
    print("=" * 80)
    
    graph = data["graph"]
    paths = data["paths"]
    nodes = {n["id"]: n["layer"] for n in graph.get("nodes", [])}
    links = graph.get("links", [])
    
    # Build adjacency structures (store in data for reuse)
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
        
        adjacency[source].append({
            "target": target,
            "target_layer": target_layer,
            "cable_layer": cable_layer,
            "cable_id": cable_id,
            "length_m": length_m
        })
        reverse_adjacency[target].append({
            "source": source,
            "source_layer": source_layer,
            "cable_layer": cable_layer,
            "cable_id": cable_id,
            "length_m": length_m
        })
    
    # Store for reuse in inference functions
    data["_adjacency"] = adjacency
    data["_reverse_adjacency"] = reverse_adjacency
    
    # Pre-compute downstream ONT counts from paths
    print("\nPre-computing downstream ONT counts...")
    downstream_onts = defaultdict(int)
    for path in paths:
        path_segments = path.get("path", [])
        ont_id = path.get("ont_id")
        if not ont_id or not path_segments:
            continue
        
        # Track all nodes this ONT passes through
        for seg in path_segments:
            from_node = seg.get("from")
            from_layer = seg.get("from_layer")
            if from_layer in ["terminal", "splice closure", "fdh"]:
                downstream_onts[from_node] += 1
    
    # Pre-compute path lengths to OLT
    print("Pre-computing path lengths to OLT...")
    path_lengths_to_olt = {}
    
    for path in paths:
        if not path.get("complete", False):
            continue
        
        path_segments = path.get("path", [])
        total_length = path.get("total_length_m", 0)
        
        # Track cumulative length for each node in path
        cumulative_length = 0
        for seg in path_segments:
            from_node = seg.get("from")
            length_seg = seg.get("length_m") or 0
            cumulative_length += length_seg
            
            if from_node not in path_lengths_to_olt:
                path_lengths_to_olt[from_node] = []
            path_lengths_to_olt[from_node].append(total_length - cumulative_length)
    
    # Compute metrics for each node (only terminals, FOSCs, FDHs, OLTs)
    print("\nComputing metrics for each element...")
    element_metrics = {}
    relevant_layers = {"terminal", "splice closure", "fdh", "olt", "ont"}
    
    for node_id, layer in nodes.items():
        if layer not in relevant_layers:
            continue
        metrics = {
            "node_id": node_id,
            "layer": layer,
            "downstream_onts": downstream_onts.get(node_id, 0),
            "avg_drop_length": None,
            "avg_stub_length": None,
            "connected_cables": [],
            "path_length_to_olt": None,
            "confidence_score": 0.5,
            "fiber_counts": [],
            "cable_types": defaultdict(int)
        }
        
        # Collect drop cable lengths
        drop_lengths = []
        stub_lengths = []
        fiber_lengths = []
        
        # Analyze outgoing connections
        for adj in adjacency.get(node_id, []):
            cable_layer = adj.get("cable_layer")
            cable_id = adj.get("cable_id")
            length_m = adj.get("length_m")
            target_layer = adj.get("target_layer")
            
            metrics["cable_types"][cable_layer] += 1
            
            if cable_id:
                metrics["connected_cables"].append(cable_id)
                fiber_count = extract_fiber_count(cable_id)
                if fiber_count:
                    metrics["fiber_counts"].append(fiber_count)
            
            if cable_layer == "drop cable" and length_m:
                drop_lengths.append(length_m)
            elif cable_layer == "stub cable" and length_m:
                stub_lengths.append(length_m)
            elif cable_layer == "fiber cable" and length_m:
                fiber_lengths.append(length_m)
        
        # Analyze incoming connections
        for rev_adj in reverse_adjacency.get(node_id, []):
            cable_layer = rev_adj.get("cable_layer")
            cable_id = rev_adj.get("cable_id")
            length_m = rev_adj.get("length_m")
            
            if cable_id:
                metrics["connected_cables"].append(cable_id)
                fiber_count = extract_fiber_count(cable_id)
                if fiber_count:
                    metrics["fiber_counts"].append(fiber_count)
            
            if cable_layer == "fiber cable" and length_m:
                fiber_lengths.append(length_m)
        
        # Calculate averages
        if drop_lengths:
            metrics["avg_drop_length"] = round(statistics.mean(drop_lengths), 2)
        if stub_lengths:
            metrics["avg_stub_length"] = round(statistics.mean(stub_lengths), 2)
        
        # Path length to OLT
        if node_id in path_lengths_to_olt:
            avg_path_length = statistics.mean(path_lengths_to_olt[node_id])
            metrics["path_length_to_olt"] = round(avg_path_length, 2)
        
        element_metrics[node_id] = metrics
    
    print(f"  ✓ Computed metrics for {len(element_metrics)} elements")
    return element_metrics


# ============================================================================
# DESIGN INTENT INFERENCE
# ============================================================================

def infer_design_intent(node_id: str, layer: str, metrics: Dict[str, Any],
                       data: Dict[str, Any], element_metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Infer design intent for a specific node.
    """
    intent = {
        "node_id": node_id,
        "layer": layer,
        "design_rationale": None,
        "pattern_id": None,
        "confidence_score": 0.5,
        "supporting_metrics": metrics,
        "rule_references": [],
        "textual_explanation": None
    }
    
    if layer == "terminal":
        intent.update(infer_terminal_intent(node_id, metrics, data, element_metrics))
    elif layer == "splice closure":
        intent.update(infer_fosc_intent(node_id, metrics, data, element_metrics))
    elif layer == "fdh":
        intent.update(infer_fdh_intent(node_id, metrics, data, element_metrics))
    elif layer == "olt":
        intent.update(infer_olt_intent(node_id, metrics, data, element_metrics))
    elif layer == "ont":
        intent.update(infer_ont_intent(node_id, metrics, data, element_metrics))
    
    return intent


def infer_terminal_intent(node_id: str, metrics: Dict[str, Any],
                         data: Dict[str, Any], element_metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """Infer design intent for Terminal (Aerial or MST)."""
    
    # Check placement rules analysis (pre-indexed for performance)
    placement_rules = data.get("_placement_rules_index", {})
    matching_rules = placement_rules.get(node_id, [])
    
    # Check if Aerial Terminal
    is_aerial = False
    is_mst = False
    is_long_reach = False
    
    for rule in matching_rules:
        rule_id = rule.get("rule_id", "")
        if "AERIAL" in rule_id:
            is_aerial = True
        elif "MST" in rule_id:
            is_mst = True
            if "LONG_REACH" in rule_id:
                is_long_reach = True
    
    downstream_onts = metrics.get("downstream_onts", 0)
    avg_drop = metrics.get("avg_drop_length")
    avg_stub = metrics.get("avg_stub_length")
    
    # Find connected FOSC (use pre-built adjacency)
    adjacency = data.get("_adjacency", {})
    reverse_adjacency = data.get("_reverse_adjacency", {})
    connected_fosc = None
    stub_distance = None
    
    # Check outgoing
    for adj in adjacency.get(node_id, []):
        if adj.get("target_layer") == "splice closure" and adj.get("cable_layer") == "stub cable":
            connected_fosc = adj.get("target")
            stub_distance = adj.get("length_m")
            break
    
    # Check incoming
    if not connected_fosc:
        for rev_adj in reverse_adjacency.get(node_id, []):
            if rev_adj.get("source_layer") == "splice closure" and rev_adj.get("cable_layer") == "stub cable":
                connected_fosc = rev_adj.get("source")
                stub_distance = rev_adj.get("length_m")
                break
    
    # Determine pattern and rationale
    if is_aerial:
        # Aerial Terminal pattern
        pattern_id = "AERIAL_INLINE_DISTRIBUTION"
        rationale = "Inline ONT distribution along continuous fiber cable segment"
        
        # Build explanation
        ont_text = f"{downstream_onts} ONTs" if downstream_onts > 0 else "multiple ONTs"
        drop_text = f"avg drop {avg_drop}m" if avg_drop else "short drop cables"
        explanation = f"Aerial Terminal {node_id} serves {ont_text} ({drop_text}) along a continuous fiber cable segment"
        
        if metrics.get("fiber_counts"):
            max_fiber = max(metrics["fiber_counts"])
            explanation += f" using {max_fiber}F cable"
        
        confidence = 0.8 if downstream_onts <= 35 and (not avg_drop or avg_drop <= 260) else 0.6
        
    elif is_mst:
        if is_long_reach:
            # Long-reach MST pattern
            pattern_id = "MST_LONG_REACH_RURAL_CLUSTER"
            rationale = "Long-reach MST deployment for rural/low-density clusters"
            
            explanation = f"MST {node_id}"
            if stub_distance:
                explanation += f" deployed {stub_distance/1000:.1f} km from FOSC {connected_fosc}" if connected_fosc else f" deployed {stub_distance/1000:.1f} km from FOSC"
            if downstream_onts > 0:
                explanation += f" to serve {downstream_onts} ONTs"
            if avg_stub:
                explanation += f" (average stub = {avg_stub}m)"
            explanation += " in a low-density branch"
            
            confidence = 0.9 if stub_distance and 500 < stub_distance <= 2500 else 0.7
        else:
            # Short-reach MST pattern
            pattern_id = "MST_SHORT_REACH_URBAN_CLUSTER"
            rationale = "Short-reach MST deployment for urban/dense clusters"
            
            explanation = f"MST {node_id}"
            if stub_distance:
                explanation += f" deployed {stub_distance}m from FOSC {connected_fosc}" if connected_fosc else f" deployed {stub_distance}m from FOSC"
            if downstream_onts > 0:
                explanation += f" to serve {downstream_onts} ONTs"
            if avg_stub:
                explanation += f" (average stub = {avg_stub}m)"
            explanation += " in a dense cluster"
            
            confidence = 0.85 if stub_distance and stub_distance <= 500 else 0.7
    else:
        # Generic terminal
        pattern_id = "TERMINAL_GENERIC"
        rationale = "Distribution access point"
        explanation = f"Terminal {node_id} serves {downstream_onts} downstream ONTs"
        confidence = 0.5
    
    return {
        "design_rationale": rationale,
        "pattern_id": pattern_id,
        "confidence_score": confidence,
        "rule_references": [r.get("rule_id") for r in matching_rules if r.get("rule_id")],
        "textual_explanation": explanation,
        "supporting_data": {
            "is_aerial": is_aerial,
            "is_mst": is_mst,
            "is_long_reach": is_long_reach,
            "connected_fosc": connected_fosc,
            "stub_distance_m": round(stub_distance, 2) if stub_distance else None
        }
    }


def infer_fosc_intent(node_id: str, metrics: Dict[str, Any],
                     data: Dict[str, Any], element_metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """Infer design intent for FOSC (Splice Closure)."""
    
    # Check placement rules (pre-indexed)
    placement_rules = data.get("_placement_rules_index", {})
    matching_rules = placement_rules.get(node_id, [])
    
    # Analyze connectivity (use pre-computed metrics)
    fiber_connections = metrics.get("cable_types", {}).get("fiber cable", 0)
    fiber_counts = metrics.get("fiber_counts", [])
    connected_cables = metrics.get("connected_cables", [])
    unique_cable_ids = len(set([c for c in connected_cables if c]))
    
    # Check for fiber transitions
    has_transition = False
    if len(fiber_counts) >= 2:
        if max(fiber_counts) - min(fiber_counts) > 10:
            has_transition = True
    
    # Check for long segments (from metrics)
    max_fiber_length = 0
    fiber_lengths = metrics.get("outgoing_lengths", {}).get("fiber cable", []) + \
                     metrics.get("incoming_lengths", {}).get("fiber cable", [])
    if fiber_lengths:
        max_fiber_length = max(fiber_lengths)
    
    # Find connected FDH (use adjacency)
    adjacency = data.get("_adjacency", {})
    reverse_adjacency = data.get("_reverse_adjacency", {})
    connected_fdh = None
    fdh_distance = None
    
    for adj in adjacency.get(node_id, []):
        if adj.get("target_layer") == "fdh":
            connected_fdh = adj.get("target")
            fdh_distance = adj.get("length_m")
            break
    
    if not connected_fdh:
        for rev_adj in reverse_adjacency.get(node_id, []):
            if rev_adj.get("source_layer") == "fdh":
                connected_fdh = rev_adj.get("source")
                fdh_distance = rev_adj.get("length_m")
                break
    
    # Determine pattern
    if connected_fdh and fdh_distance and fdh_distance <= 50:
        pattern_id = "FOSC_FEEDER_JUNCTION"
        rationale = "Feeder splice point between 144F/288F feeders and 96F distributors"
        explanation = f"FOSC {node_id} serves as feeder splice point within {fdh_distance}m of FDH {connected_fdh}"
        confidence = 0.9
    elif fiber_connections >= 2:
        pattern_id = "FOSC_MULTI_CABLE_JUNCTION"
        rationale = "Junction of multiple fiber cables"
        explanation = f"FOSC {node_id} connects {fiber_connections} fiber cables"
        if has_transition:
            explanation += f" with fiber count transition ({min(fiber_counts)}F → {max(fiber_counts)}F)"
        confidence = 0.85
    elif max_fiber_length >= 1800:
        pattern_id = "FOSC_LONG_SEGMENT_SPLICE"
        rationale = "Splice point for long fiber cable segment"
        explanation = f"FOSC {node_id} placed on {max_fiber_length:.0f}m fiber cable segment"
        confidence = 0.8
    elif unique_cable_ids >= 2:
        pattern_id = "FOSC_CABLE_ID_TRANSITION"
        rationale = "Fiber cable ID transition point"
        explanation = f"FOSC {node_id} marks transition between {unique_cable_ids} different fiber cables"
        confidence = 0.75
    else:
        pattern_id = "FOSC_DISTRIBUTION_SPLICE"
        rationale = "Distribution fiber splice point"
        explanation = f"FOSC {node_id} serves as distribution splice point"
        confidence = 0.6
    
    return {
        "design_rationale": rationale,
        "pattern_id": pattern_id,
        "confidence_score": confidence,
        "rule_references": [r.get("rule_id") for r in matching_rules if r.get("rule_id")],
        "textual_explanation": explanation,
        "supporting_data": {
            "fiber_connections": fiber_connections,
            "unique_cable_ids": unique_cable_ids,
            "has_fiber_transition": has_transition,
            "max_fiber_length_m": round(max_fiber_length, 2),
            "connected_fdh": connected_fdh,
            "fdh_distance_m": round(fdh_distance, 2) if fdh_distance else None
        }
    }


def infer_fdh_intent(node_id: str, metrics: Dict[str, Any],
                    data: Dict[str, Any], element_metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """Infer design intent for FDH."""
    
    adjacency = data.get("_adjacency", {})
    reverse_adjacency = data.get("_reverse_adjacency", {})
    
    # Count connected FOSCs
    connected_foscs = []
    for adj in adjacency.get(node_id, []):
        if adj.get("target_layer") == "splice closure":
            connected_foscs.append(adj.get("target"))
    for rev_adj in reverse_adjacency.get(node_id, []):
        if rev_adj.get("source_layer") == "splice closure":
            connected_foscs.append(rev_adj.get("source"))
    
    downstream_onts = metrics.get("downstream_onts", 0)
    
    pattern_id = "FDH_FEEDER_ROOT"
    rationale = "Feeder distribution hub connecting to multiple FOSCs"
    
    explanation = f"FDH {node_id} serves as feeder root node"
    if connected_foscs:
        explanation += f" connecting to {len(connected_foscs)} FOSCs"
    if downstream_onts > 0:
        explanation += f" serving {downstream_onts} downstream ONTs"
    
    confidence = 0.95
    
    return {
        "design_rationale": rationale,
        "pattern_id": pattern_id,
        "confidence_score": confidence,
        "rule_references": ["R13_FDH_ASSOCIATION"],
        "textual_explanation": explanation,
        "supporting_data": {
            "connected_foscs": len(connected_foscs),
            "downstream_onts": downstream_onts
        }
    }


def infer_olt_intent(node_id: str, metrics: Dict[str, Any],
                    data: Dict[str, Any], element_metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """Infer design intent for OLT."""
    
    adjacency = data.get("_adjacency", {})
    reverse_adjacency = data.get("_reverse_adjacency", {})
    
    # Count connected FDHs
    connected_fdhs = []
    for adj in adjacency.get(node_id, []):
        if adj.get("target_layer") == "fdh":
            connected_fdhs.append(adj.get("target"))
    for rev_adj in reverse_adjacency.get(node_id, []):
        if rev_adj.get("source_layer") == "fdh":
            connected_fdhs.append(rev_adj.get("source"))
    
    pattern_id = "OLT_FEEDER_ROOT"
    rationale = "Optical Line Terminal - root of feeder → FDH → FOSC → Terminal → ONT chain"
    
    explanation = f"OLT {node_id} serves as feeder root"
    if connected_fdhs:
        explanation += f" connecting to {len(connected_fdhs)} FDHs"
    explanation += " in the OLT → FDH → FOSC → Terminal → ONT hierarchy"
    
    confidence = 0.98
    
    return {
        "design_rationale": rationale,
        "pattern_id": pattern_id,
        "confidence_score": confidence,
        "rule_references": [],
        "textual_explanation": explanation,
        "supporting_data": {
            "connected_fdhs": len(connected_fdhs)
        }
    }


def infer_ont_intent(node_id: str, metrics: Dict[str, Any],
                    data: Dict[str, Any], element_metrics: Dict[str, Dict]) -> Dict[str, Any]:
    """Infer design intent for ONT."""
    
    # Find path for this ONT
    paths = data["paths"]
    ont_path = None
    for path in paths:
        if path.get("ont_id") == node_id:
            ont_path = path
            break
    
    pattern_id = "ONT_END_USER"
    rationale = "Optical Network Terminal - end user access point"
    
    explanation = f"ONT {node_id} serves as end user access point"
    if ont_path and ont_path.get("complete"):
        explanation += " with complete path to OLT"
        if ont_path.get("total_length_m"):
            explanation += f" ({ont_path['total_length_m']:.0f}m total)"
    else:
        explanation += " (incomplete path to OLT)"
    
    confidence = 0.9
    
    return {
        "design_rationale": rationale,
        "pattern_id": pattern_id,
        "confidence_score": confidence,
        "rule_references": [],
        "textual_explanation": explanation,
        "supporting_data": {
            "path_complete": ont_path.get("complete", False) if ont_path else False
        }
    }


# ============================================================================
# DESIGN TEMPLATE CLUSTERING
# ============================================================================

def cluster_design_templates(intents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Cluster design intents into reusable templates.
    Groups by pattern_id and creates template summaries.
    """
    print("\n" + "=" * 80)
    print("CLUSTERING DESIGN TEMPLATES")
    print("=" * 80)
    
    # Group by pattern_id
    templates = defaultdict(list)
    for intent in intents:
        pattern_id = intent.get("pattern_id")
        if pattern_id:
            templates[pattern_id].append(intent)
    
    print(f"\n  Found {len(templates)} unique design patterns")
    for pattern_id, examples in templates.items():
        print(f"    {pattern_id}: {len(examples)} instances")
    
    return dict(templates)


def generate_template_summaries(templates: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Generate summaries for each template pattern."""
    
    template_summaries = {}
    
    for pattern_id, examples in templates.items():
        if not examples:
            continue
        
        # Aggregate metrics
        confidences = [e.get("confidence_score", 0.5) for e in examples]
        avg_confidence = statistics.mean(confidences) if confidences else 0.5
        
        # Extract common characteristics
        sample_explanation = examples[0].get("textual_explanation", "")
        
        # Create template summary
        template_summaries[pattern_id] = {
            "pattern_id": pattern_id,
            "description": examples[0].get("design_rationale", ""),
            "instance_count": len(examples),
            "average_confidence": round(avg_confidence, 3),
            "example_explanation": sample_explanation,
            "typical_characteristics": extract_typical_characteristics(examples)
        }
    
    return template_summaries


def extract_typical_characteristics(examples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract typical characteristics from a set of examples."""
    characteristics = {}
    
    # Collect metrics
    downstream_onts = []
    avg_drops = []
    avg_stubs = []
    path_lengths = []
    
    for example in examples:
        metrics = example.get("supporting_metrics", {})
        if metrics.get("downstream_onts", 0) > 0:
            downstream_onts.append(metrics["downstream_onts"])
        if metrics.get("avg_drop_length"):
            avg_drops.append(metrics["avg_drop_length"])
        if metrics.get("avg_stub_length"):
            avg_stubs.append(metrics["avg_stub_length"])
        if metrics.get("path_length_to_olt"):
            path_lengths.append(metrics["path_length_to_olt"])
    
    if downstream_onts:
        characteristics["typical_downstream_onts"] = {
            "mean": round(statistics.mean(downstream_onts), 1),
            "median": round(statistics.median(downstream_onts), 1),
            "range": f"{min(downstream_onts)}-{max(downstream_onts)}"
        }
    
    if avg_drops:
        characteristics["typical_avg_drop_length_m"] = {
            "mean": round(statistics.mean(avg_drops), 1),
            "median": round(statistics.median(avg_drops), 1)
        }
    
    if avg_stubs:
        characteristics["typical_avg_stub_length_m"] = {
            "mean": round(statistics.mean(avg_stubs), 1),
            "median": round(statistics.median(avg_stubs), 1)
        }
    
    if path_lengths:
        characteristics["typical_path_length_to_olt_m"] = {
            "mean": round(statistics.mean(path_lengths), 1),
            "median": round(statistics.median(path_lengths), 1)
        }
    
    return characteristics


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_design_intent_summary(all_intents: List[Dict[str, Any]],
                                   templates: Dict[str, List[Dict[str, Any]]],
                                   template_summaries: Dict[str, Dict[str, Any]]) -> None:
    """Generate design_intent_summary.json."""
    
    summary = {
        "metadata": {
            "total_elements": len(all_intents),
            "unique_patterns": len(templates),
            "generation_timestamp": None
        },
        "design_intents": all_intents,
        "template_clusters": {
            pattern_id: {
                "count": len(examples),
                "examples": [e["node_id"] for e in examples[:5]]  # First 5 examples
            }
            for pattern_id, examples in templates.items()
        },
        "template_summaries": template_summaries
    }
    
    with open("design_intent_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n  ✓ Saved design_intent_summary.json ({len(all_intents)} intents)")


def generate_design_templates(templates: Dict[str, List[Dict[str, Any]]],
                             template_summaries: Dict[str, Dict[str, Any]]) -> None:
    """Generate design_templates.txt with human-readable templates."""
    
    output = "=" * 80 + "\n"
    output += "DESIGN INTENT TEMPLATES\n"
    output += "=" * 80 + "\n\n"
    output += "Reusable design patterns extracted from network analysis.\n\n"
    
    # Group by element type
    by_layer = defaultdict(list)
    for pattern_id, examples in templates.items():
        if examples:
            layer = examples[0].get("layer", "unknown")
            by_layer[layer].append((pattern_id, examples))
    
    for layer in ["olt", "fdh", "splice closure", "terminal", "ont"]:
        if layer not in by_layer:
            continue
        
        output += "=" * 80 + "\n"
        output += f"{layer.upper()} DESIGN PATTERNS\n"
        output += "=" * 80 + "\n\n"
        
        for pattern_id, examples in by_layer[layer]:
            summary = template_summaries.get(pattern_id, {})
            
            output += f"[{pattern_id}]\n"
            output += f"  Description: {summary.get('description', 'N/A')}\n"
            output += f"  Instance Count: {summary.get('instance_count', 0)}\n"
            output += f"  Average Confidence: {summary.get('average_confidence', 0):.3f}\n"
            output += f"\n  Example Explanation:\n"
            output += f"    {summary.get('example_explanation', 'N/A')}\n"
            
            characteristics = summary.get("typical_characteristics", {})
            if characteristics:
                output += f"\n  Typical Characteristics:\n"
                for key, value in characteristics.items():
                    if isinstance(value, dict):
                        output += f"    {key}: {value}\n"
                    else:
                        output += f"    {key}: {value}\n"
            
            # Show 3 example explanations
            output += f"\n  Example Instances:\n"
            for i, example in enumerate(examples[:3], 1):
                output += f"    {i}. {example.get('textual_explanation', 'N/A')}\n"
            
            output += "\n"
    
    output += "=" * 80 + "\n"
    output += "END OF TEMPLATES\n"
    output += "=" * 80 + "\n"
    
    with open("design_templates.txt", "w", encoding="utf-8") as f:
        f.write(output)
    
    print(f"  ✓ Saved design_templates.txt")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main execution pipeline."""
    print("=" * 80)
    print("DESIGN INTENT EXTRACTION PIPELINE")
    print("=" * 80)
    
    # Step 1: Load all data
    data = load_all_data()
    
    # Step 2: Compute element metrics
    element_metrics = compute_element_metrics(data)
    
    # Pre-index placement rules for faster lookup
    print("\nIndexing placement rules...")
    placement_analyses = data.get("placement_rules", {}).get("placement_analyses", [])
    placement_rules_index = defaultdict(list)
    for analysis in placement_analyses:
        node_id = analysis.get("node_id")
        if node_id:
            placement_rules_index[node_id].append(analysis)
    data["_placement_rules_index"] = placement_rules_index
    print(f"  ✓ Indexed {len(placement_rules_index)} nodes with placement rules")
    
    # Step 3: Infer design intent for each element
    print("\n" + "=" * 80)
    print("INFERRING DESIGN INTENT")
    print("=" * 80)
    
    all_intents = []
    nodes = {n["id"]: n["layer"] for n in data["graph"].get("nodes", [])}
    
    # Process each node (only those with metrics)
    processed = 0
    for node_id in element_metrics.keys():
        layer = nodes.get(node_id)
        if not layer:
            continue
        
        metrics = element_metrics[node_id]
        intent = infer_design_intent(node_id, layer, metrics, data, element_metrics)
        all_intents.append(intent)
        processed += 1
        
        if processed % 1000 == 0:
            print(f"  Processed {processed} elements...")
    
    print(f"\n  ✓ Inferred design intent for {len(all_intents)} elements")
    
    # Step 4: Cluster into templates
    templates = cluster_design_templates(all_intents)
    template_summaries = generate_template_summaries(templates)
    
    # Step 5: Generate outputs
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)
    
    generate_design_intent_summary(all_intents, templates, template_summaries)
    generate_design_templates(templates, template_summaries)
    
    print("\n" + "=" * 80)
    print("✅ DESIGN INTENT EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"\nGenerated design intents for {len(all_intents)} network elements")
    print(f"  Identified {len(templates)} unique design patterns")
    print(f"  Average confidence: {statistics.mean([i.get('confidence_score', 0.5) for i in all_intents]):.3f}")


if __name__ == "__main__":
    main()

