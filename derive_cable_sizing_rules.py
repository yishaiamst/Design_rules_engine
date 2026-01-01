#!/usr/bin/env python3
"""
derive_cable_sizing_rules.py
-------------------------------------------------------------------------------
Cable Sizing Rules Derivation
-------------------------------------------------------------------------------
Analyzes cable_transitions_summary.json and automatically infers statistical
thresholds and decision rules for selecting fiber cable sizes based on downstream
ONT counts and connectivity hierarchy.

Input:
- cable_transitions_summary.json

Output:
- cable_sizing_rules.json (structured thresholds)
- cable_sizing_summary.txt (readable explanation)
-------------------------------------------------------------------------------
"""

import json
import re
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


# ============================================================================
# DATA LOADING
# ============================================================================

def load_transitions_summary(filepath: str = "cable_transitions_summary.json") -> Dict[str, Any]:
    """Load cable transitions summary data."""
    print(f"Loading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  ✓ Loaded data for {data['metadata']['total_fiber_sizes']} fiber sizes")
    return data


# ============================================================================
# QUANTILE-BASED THRESHOLD ANALYSIS
# ============================================================================

def estimate_quantiles(min_val: float, median_val: float, max_val: float, 
                       avg_val: float) -> Tuple[float, float, float]:
    """
    Estimate Q1, Q2 (median), Q3 from summary statistics.
    Uses approximation based on normal distribution assumption.
    """
    if min_val == max_val:
        return (min_val, median_val, max_val)
    
    # Q2 is the median
    q2 = median_val
    
    # Estimate Q1 and Q3 using approximation
    # If median is closer to min, use left-skewed approximation
    # If median is closer to max, use right-skewed approximation
    
    range_size = max_val - min_val
    
    # For Q1: typically between min and median
    # Use interpolation: if median is at 50th percentile, Q1 should be around 25th
    if median_val > min_val:
        q1 = min_val + (median_val - min_val) * 0.5
    else:
        q1 = min_val
    
    # For Q3: typically between median and max
    # Use interpolation
    if max_val > median_val:
        q3 = median_val + (max_val - median_val) * 0.5
    else:
        q3 = max_val
    
    # Refine based on average
    if avg_val > median_val:
        # Right-skewed: Q3 should be higher
        q3 = max(q3, avg_val)
    elif avg_val < median_val:
        # Left-skewed: Q1 should be lower
        q1 = min(q1, avg_val)
    
    return (round(q1, 1), round(q2, 1), round(q3, 1))


def extract_fiber_count_from_key(size_key: str) -> int:
    """Extract fiber count from key like '288F' -> 288."""
    match = re.match(r'(\d+)F', size_key)
    if match:
        return int(match.group(1))
    return 0


# ============================================================================
# TRANSITION ANALYSIS
# ============================================================================

def find_likely_next_size(from_size: int, transitions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the most likely next cable size from transition data."""
    # Filter transitions for this from_size
    relevant_transitions = [
        t for t in transitions 
        if t.get("from_size") == from_size
    ]
    
    if not relevant_transitions:
        return None
    
    # Find self-transition and non-self transitions
    self_transition = next((t for t in relevant_transitions if t.get("to_size") == from_size), None)
    non_self_transitions = [t for t in relevant_transitions if t.get("to_size") != from_size]
    
    total_count = sum(t.get("count", 0) for t in relevant_transitions)
    
    # If no non-self transitions, return None (or self if meaningful)
    if not non_self_transitions:
        if self_transition:
            return {
                "size": from_size,
                "frequency": self_transition.get("count", 0),
                "probability": self_transition.get("count", 0) / total_count if total_count > 0 else 0,
                "is_self": True
            }
        return None
    
    # Find most common non-self transition
    best_non_self = max(non_self_transitions, key=lambda x: x.get("count", 0))
    non_self_prob = best_non_self.get("count", 0) / total_count if total_count > 0 else 0
    
    # If self-transition exists and is dominant (>80%), prefer non-self for "next" guidance
    # but only if non-self is at least 5% of total
    if self_transition:
        self_prob = self_transition.get("count", 0) / total_count if total_count > 0 else 0
        if self_prob > 0.8 and non_self_prob < 0.05:
            # Self-transition is too dominant, but still report most common non-self
            # for guidance on what happens when there IS a transition
            return {
                "size": best_non_self.get("to_size"),
                "frequency": best_non_self.get("count", 0),
                "probability": non_self_prob,
                "is_self": False,
                "note": "Mostly self-transitions, but when transitioning, typically to this size"
            }
    
    # Return the most common non-self transition
    return {
        "size": best_non_self.get("to_size"),
        "frequency": best_non_self.get("count", 0),
        "probability": non_self_prob,
        "is_self": False
    }


# ============================================================================
# PLACEMENT CONTEXT INFERENCE
# ============================================================================

def infer_placement_context(fiber_count: int, stats: Dict[str, Any], 
                           transitions: List[Dict[str, Any]]) -> str:
    """
    Infer placement context: feeder, distribution, or access.
    
    Logic:
    - Feeder: Large sizes (288F, 144F) typically used in feeder/trunk
    - Distribution: Medium sizes (96F, 48F) for mid-distribution
    - Access: Small sizes (12F, 4F) for last-mile access
    """
    if fiber_count >= 144:
        # Check if it transitions to itself frequently (feeder pattern)
        self_transitions = [t for t in transitions 
                          if t.get("from_size") == fiber_count and t.get("to_size") == fiber_count]
        if self_transitions:
            total_self = sum(t.get("count", 0) for t in self_transitions)
            total_from = sum(t.get("count", 0) for t in transitions 
                            if t.get("from_size") == fiber_count)
            if total_from > 0 and total_self / total_from > 0.5:
                return "feeder"
        return "feeder"
    elif fiber_count >= 48:
        # Check transition patterns
        transitions_from = [t for t in transitions 
                           if t.get("from_size") == fiber_count]
        if transitions_from:
            # If mostly transitions to smaller sizes, it's distribution
            smaller_transitions = [t for t in transitions_from 
                                  if t.get("to_size", 0) < fiber_count]
            if len(smaller_transitions) > len(transitions_from) * 0.3:
                return "distribution"
        return "distribution"
    else:
        return "access"


# ============================================================================
# RULESET GENERATION
# ============================================================================

def derive_cable_sizing_rules(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Derive cable sizing rules from transitions summary."""
    print("\nDeriving cable sizing rules...")
    
    size_stats = data.get("size_statistics", {})
    transitions = data.get("transitions", [])
    
    rules = []
    
    # Process each cable size
    for size_key, stats in sorted(size_stats.items(), 
                                 key=lambda x: extract_fiber_count_from_key(x[0]), 
                                 reverse=True):
        fiber_count = extract_fiber_count_from_key(size_key)
        
        # Extract statistics
        min_onts = stats.get("min_onts", 0)
        max_onts = stats.get("max_onts", 0)
        median_onts = stats.get("median_onts", 0)
        avg_onts = stats.get("avg_onts", 0)
        
        # Estimate quantiles
        q1, q2, q3 = estimate_quantiles(min_onts, median_onts, max_onts, avg_onts)
        
        # Find likely next size
        likely_next = find_likely_next_size(fiber_count, transitions)
        
        # Infer placement context
        placement_context = infer_placement_context(fiber_count, stats, transitions)
        
        # Determine threshold range using Q1-Q3
        # Lower threshold: Q1 (25th percentile)
        # Upper threshold: Q3 (75th percentile)
        threshold_min = int(q1)
        threshold_max = int(q3)
        
        # But also consider the actual min/max for boundaries
        if min_onts > 0:
            threshold_min = max(threshold_min, min_onts)
        if max_onts > 0:
            threshold_max = min(threshold_max, max_onts) if threshold_max < max_onts else max_onts
        
        rule = {
            "size": fiber_count,
            "size_label": size_key,
            "min_ONTs": min_onts,
            "max_ONTs": max_onts,
            "median_ONTs": median_onts,
            "avg_ONTs": round(avg_onts, 1),
            "q1_ONTs": q1,
            "q3_ONTs": q3,
            "threshold_min_ONTs": threshold_min,
            "threshold_max_ONTs": threshold_max,
            "likely_next_size": likely_next.get("size") if likely_next else None,
            "likely_next_frequency": likely_next.get("frequency") if likely_next else None,
            "likely_next_probability": round(likely_next.get("probability", 0), 3) if likely_next else None,
            "likely_next_is_self": likely_next.get("is_self", False) if likely_next else None,
            "likely_next_note": likely_next.get("note") if likely_next else None,
            "placement_context": placement_context,
            "total_cables": stats.get("total_cables", 0),
            "cables_with_onts": stats.get("cables_with_onts", 0),
            "avg_length_m": round(stats.get("avg_length_m", 0), 1),
            "median_length_m": round(stats.get("median_length_m", 0), 1)
        }
        
        rules.append(rule)
    
    print(f"  ✓ Derived {len(rules)} cable sizing rules")
    return rules


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_rules_json(rules: List[Dict[str, Any]], output_file: str = "cable_sizing_rules.json") -> None:
    """Generate cable_sizing_rules.json."""
    print(f"\nGenerating {output_file}...")
    
    output = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_rules": len(rules),
        "rules": rules
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"  ✓ Saved {output_file}")


def generate_summary_txt(rules: List[Dict[str, Any]], output_file: str = "cable_sizing_summary.txt") -> None:
    """Generate cable_sizing_summary.txt."""
    print(f"\nGenerating {output_file}...")
    
    output = "=" * 80 + "\n"
    output += "CABLE SIZING RULES SUMMARY\n"
    output += "=" * 80 + "\n\n"
    output += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    output += f"Total Rules: {len(rules)}\n\n"
    output += "Actionable rules for selecting fiber cable sizes based on downstream ONT counts.\n\n"
    
    # Group by placement context
    by_context = defaultdict(list)
    for rule in rules:
        context = rule.get("placement_context", "unknown")
        by_context[context].append(rule)
    
    # Output by context
    context_order = ["feeder", "distribution", "access"]
    for context in context_order:
        if context not in by_context:
            continue
        
        output += "=" * 80 + "\n"
        output += f"{context.upper()} CABLES\n"
        output += "=" * 80 + "\n\n"
        
        for rule in by_context[context]:
            size = rule.get("size")
            size_label = rule.get("size_label", f"{size}F")
            
            output += f"[{size_label}]\n"
            output += f"  Placement Context: {context}\n"
            output += f"  Recommended ONT Range: {rule.get('threshold_min_ONTs')} - {rule.get('threshold_max_ONTs')} ONTs\n"
            output += f"  Statistics:\n"
            output += f"    Min ONTs: {rule.get('min_ONTs')}\n"
            output += f"    Median ONTs: {rule.get('median_ONTs')}\n"
            output += f"    Max ONTs: {rule.get('max_ONTs')}\n"
            output += f"    Average ONTs: {rule.get('avg_ONTs')}\n"
            output += f"    Q1 (25th percentile): {rule.get('q1_ONTs')}\n"
            output += f"    Q3 (75th percentile): {rule.get('q3_ONTs')}\n"
            
            likely_next = rule.get("likely_next_size")
            if likely_next:
                prob = rule.get("likely_next_probability", 0)
                is_self = rule.get("likely_next_is_self", False)
                note = rule.get("likely_next_note", "")
                
                if is_self:
                    output += f"  Typical Continuation: {likely_next}F (probability: {prob:.1%})\n"
                    output += f"    (Cable typically continues at same size)\n"
                else:
                    output += f"  Typical Next Size: {likely_next}F (probability: {prob:.1%})\n"
                    if note:
                        output += f"    ({note})\n"
            
            output += f"  Deployment Count: {rule.get('total_cables')} cables ({rule.get('cables_with_onts')} with ONTs)\n"
            output += f"  Typical Length: {rule.get('median_length_m')} m (avg: {rule.get('avg_length_m')} m)\n"
            
            # Decision guidance
            output += f"\n  When to Use:\n"
            threshold_min = rule.get("threshold_min_ONTs", 0)
            threshold_max = rule.get("threshold_max_ONTs", 0)
            
            if threshold_min > 0 and threshold_max > 0:
                if threshold_min == threshold_max:
                    output += f"    Use {size_label} when serving approximately {threshold_min} ONTs.\n"
                else:
                    output += f"    Use {size_label} when serving {threshold_min}-{threshold_max} ONTs.\n"
            
            if likely_next:
                is_self = rule.get("likely_next_is_self", False)
                if is_self:
                    output += f"    Typically continues at {likely_next}F (same size).\n"
                else:
                    output += f"    When transitioning, typically moves to {likely_next}F cables downstream.\n"
            
            output += "\n"
    
    # Summary table
    output += "=" * 80 + "\n"
    output += "QUICK REFERENCE TABLE\n"
    output += "=" * 80 + "\n\n"
    output += f"{'Size':<8} {'Context':<15} {'ONT Range':<20} {'Median ONTs':<15} {'Next Size':<12}\n"
    output += "-" * 80 + "\n"
    
    for rule in sorted(rules, key=lambda x: x.get("size", 0), reverse=True):
        size_label = rule.get("size_label", "N/A")
        context = rule.get("placement_context", "unknown")
        ont_range = f"{rule.get('threshold_min_ONTs')}-{rule.get('threshold_max_ONTs')}"
        median = rule.get("median_ONTs", 0)
        next_size = f"{rule.get('likely_next_size')}F" if rule.get("likely_next_size") else "N/A"
        
        output += f"{size_label:<8} {context:<15} {ont_range:<20} {median:<15.1f} {next_size:<12}\n"
    
    output += "\n" + "=" * 80 + "\n"
    output += "END OF SUMMARY\n"
    output += "=" * 80 + "\n"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)
    
    print(f"  ✓ Saved {output_file}")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main execution pipeline."""
    print("=" * 80)
    print("CABLE SIZING RULES DERIVATION")
    print("=" * 80)
    
    # Step 1: Load data
    data = load_transitions_summary()
    
    # Step 2: Derive rules
    rules = derive_cable_sizing_rules(data)
    
    # Step 3: Generate outputs
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)
    
    generate_rules_json(rules)
    generate_summary_txt(rules)
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ DERIVATION COMPLETE")
    print("=" * 80)
    print(f"\nDerived {len(rules)} cable sizing rules")
    print(f"\nGenerated files:")
    print(f"  📄 cable_sizing_rules.json")
    print(f"  📄 cable_sizing_summary.txt")
    
    # Print quick stats
    by_context = defaultdict(int)
    for rule in rules:
        by_context[rule.get("placement_context", "unknown")] += 1
    
    print(f"\nRules by context:")
    for context, count in sorted(by_context.items()):
        print(f"  {context}: {count} rules")
    print()


if __name__ == "__main__":
    main()

