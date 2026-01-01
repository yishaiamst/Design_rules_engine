#!/usr/bin/env python3
"""
analyze_cable_transitions.py
-------------------------------------------------------------------------------
Fiber Cable Transition Analysis
-------------------------------------------------------------------------------
Identifies and visualizes fiber size transitions and determines threshold logic
for cable sizing decisions (e.g., 288F → 144F → 96F → 48F → 12F).

Input:
- fiber cable.geojson
- olt_ont_paths.json

Output:
- cable_transitions_summary.json
- cable_transitions_matrix.csv
- fiber_size_thresholds.txt
- cable_transitions_visualization.png (bar chart and transition matrix)
-------------------------------------------------------------------------------
"""

import json
import re
import csv
import os
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import statistics

try:
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("  ⚠ matplotlib not available - skipping visualization")


# ============================================================================
# DATA LOADING
# ============================================================================

def load_geojson(path: str) -> List[Dict[str, Any]]:
    """Load GeoJSON file and normalize property names to lowercase."""
    print(f"  Loading {path}...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    normalized = []
    for f in features:
        props = {k.lower(): v for k, v in f.get("properties", {}).items()}
        normalized.append(props)
    print(f"    Loaded {len(normalized)} features")
    return normalized


def extract_fiber_count(cable_id: str) -> Optional[int]:
    """Extract fiber count from cable ID (e.g., '288FOC' -> 288)."""
    if not cable_id:
        return None
    
    # Pattern: "288FOC", "144FOC", "96FOC", "48FOC", "12FOC", etc.
    match = re.match(r'(\d+)F(?:OC)?', cable_id.upper())
    if match:
        return int(match.group(1))
    
    # Also check for patterns like "288F", "144F"
    match = re.match(r'(\d+)F', cable_id.upper())
    if match:
        return int(match.group(1))
    
    return None


def get_field_value(props: Dict[str, Any], *field_names: str) -> Optional[str]:
    """Get field value trying multiple field name variations."""
    for field in field_names:
        if field in props:
            return str(props[field]) if props[field] is not None else None
        # Try case variations
        for key in props.keys():
            if key.lower() == field.lower():
                return str(props[key]) if props[key] is not None else None
    return None


# ============================================================================
# CABLE ANALYSIS
# ============================================================================

def parse_fiber_cables(fiber_cable_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Parse fiber cables and extract size, from/to IDs, and length."""
    print("\nParsing fiber cables...")
    
    cables = {}
    
    for props in fiber_cable_data:
        cable_id = get_field_value(props, "id", "cable_id", "cableid")
        if not cable_id:
            continue
        
        # Extract fiber count from cable ID
        fiber_count = extract_fiber_count(cable_id)
        if not fiber_count:
            continue
        
        # Extract from/to IDs
        from_id = get_field_value(props, "from_id", "fromid", "from", "source_id", "sourceid")
        to_id = get_field_value(props, "to_id", "toid", "to", "target_id", "targetid")
        
        # Extract length
        length = None
        for field in ["calclength", "measlength", "length", "length_m"]:
            value = get_field_value(props, field)
            if value:
                try:
                    length = float(value)
                    break
                except (ValueError, TypeError):
                    continue
        
        cables[cable_id] = {
            "cable_id": cable_id,
            "fiber_count": fiber_count,
            "from_id": from_id,
            "to_id": to_id,
            "length_m": length
        }
    
    print(f"  ✓ Parsed {len(cables)} fiber cables")
    return cables


def compute_downstream_onts_per_cable(cables: Dict[str, Dict[str, Any]], 
                                      paths: List[Dict[str, Any]]) -> Dict[str, int]:
    """Compute downstream ONT count for each cable."""
    print("\nComputing downstream ONT counts per cable...")
    
    # Count ONTs per cable
    cable_ont_counts = defaultdict(set)
    
    for path_data in paths:
        if not path_data.get("complete", False):
            continue
        
        path_segments = path_data.get("path", [])
        
        # For each cable in the path, count all ONTs downstream
        for i, seg in enumerate(path_segments):
            cable_id = seg.get("cable_id")
            cable_layer = seg.get("cable_layer")
            
            if cable_layer == "fiber cable" and cable_id:
                # Count this ONT and all downstream ONTs
                ont_id = path_data.get("ont_id")
                if ont_id:
                    cable_ont_counts[cable_id].add(ont_id)
    
    # Convert sets to counts
    cable_counts = {cable_id: len(ont_set) for cable_id, ont_set in cable_ont_counts.items()}
    
    print(f"  ✓ Computed counts for {len(cable_counts)} cables")
    return cable_counts


def compute_size_statistics(cables: Dict[str, Dict[str, Any]], 
                           cable_ont_counts: Dict[str, int]) -> Dict[int, Dict[str, Any]]:
    """Compute statistics for each fiber size."""
    print("\nComputing statistics per fiber size...")
    
    size_stats = defaultdict(lambda: {
        "fiber_count": 0,
        "cables": [],
        "ont_counts": [],
        "lengths": []
    })
    
    for cable_id, cable_info in cables.items():
        fiber_count = cable_info["fiber_count"]
        size_stats[fiber_count]["fiber_count"] = fiber_count
        size_stats[fiber_count]["cables"].append(cable_id)
        
        # Get ONT count for this cable
        ont_count = cable_ont_counts.get(cable_id, 0)
        if ont_count > 0:
            size_stats[fiber_count]["ont_counts"].append(ont_count)
        
        # Get length
        length = cable_info.get("length_m")
        if length:
            size_stats[fiber_count]["lengths"].append(length)
    
    # Calculate statistics
    result = {}
    for fiber_count, stats in size_stats.items():
        ont_counts = stats["ont_counts"]
        lengths = stats["lengths"]
        
        result[fiber_count] = {
            "fiber_count": fiber_count,
            "total_cables": len(stats["cables"]),
            "cables_with_onts": len(ont_counts),
            "avg_onts": round(statistics.mean(ont_counts), 1) if ont_counts else 0,
            "min_onts": min(ont_counts) if ont_counts else 0,
            "max_onts": max(ont_counts) if ont_counts else 0,
            "median_onts": round(statistics.median(ont_counts), 1) if ont_counts else 0,
            "avg_length_m": round(statistics.mean(lengths), 1) if lengths else 0,
            "median_length_m": round(statistics.median(lengths), 1) if lengths else 0
        }
    
    print(f"  ✓ Computed statistics for {len(result)} fiber sizes")
    return result


# ============================================================================
# TRANSITION MATRIX
# ============================================================================

def build_transition_matrix(cables: Dict[str, Dict[str, Any]], 
                           paths: List[Dict[str, Any]]) -> Dict[Tuple[int, int], int]:
    """Build transition matrix showing how often cable sizes connect."""
    print("\nBuilding transition matrix...")
    
    transitions = defaultdict(int)
    
    # For each path, find consecutive fiber cable segments
    for path_data in paths:
        if not path_data.get("complete", False):
            continue
        
        path_segments = path_data.get("path", [])
        fiber_segments = [seg for seg in path_segments if seg.get("cable_layer") == "fiber cable"]
        
        # Find transitions between consecutive fiber cables
        for i in range(len(fiber_segments) - 1):
            current_seg = fiber_segments[i]
            next_seg = fiber_segments[i + 1]
            
            current_cable_id = current_seg.get("cable_id")
            next_cable_id = next_seg.get("cable_id")
            
            if current_cable_id and next_cable_id:
                current_size = extract_fiber_count(current_cable_id)
                next_size = extract_fiber_count(next_cable_id)
                
                if current_size and next_size:
                    transitions[(current_size, next_size)] += 1
    
    print(f"  ✓ Found {len(transitions)} unique transitions")
    return transitions


# ============================================================================
# THRESHOLD INFERENCE
# ============================================================================

def infer_thresholds(size_stats: Dict[int, Dict[str, Any]]) -> Dict[int, Tuple[int, int]]:
    """Infer threshold logic for cable sizing based on ONT counts."""
    print("\nInferring size thresholds...")
    
    # Sort sizes in descending order
    sorted_sizes = sorted(size_stats.keys(), reverse=True)
    
    thresholds = {}
    
    # First pass: use actual min/max from data
    for size in sorted_sizes:
        stats = size_stats[size]
        cables_with_onts = stats.get("cables_with_onts", 0)
        
        if cables_with_onts > 0:
            min_actual = stats.get("min_onts", 0)
            max_actual = stats.get("max_onts", 0)
            median_onts = stats.get("median_onts", 0)
            p75_estimate = int(median_onts * 1.5) if median_onts > 0 else max_actual
            
            # Use percentiles for better thresholds
            # Lower bound: actual min or 1
            # Upper bound: use 75th percentile estimate or max
            lower_bound = max(1, min_actual)
            upper_bound = max(p75_estimate, max_actual)
            thresholds[size] = (lower_bound, upper_bound)
        else:
            # No ONT data - set to 0
            thresholds[size] = (0, 0)
    
    # Second pass: refine based on hierarchical logic
    # Ensure larger cables have higher thresholds
    for i in range(len(sorted_sizes) - 1):
        current_size = sorted_sizes[i]
        next_size = sorted_sizes[i + 1]
        
        current_lower, current_upper = thresholds[current_size]
        next_lower, next_upper = thresholds[next_size]
        
        # Ensure next size's max is less than or equal to current size's min
        # (allowing overlap for flexibility)
        if next_upper > current_lower and next_upper > 0:
            # Adjust next size's upper bound
            next_upper = min(next_upper, current_lower)
            thresholds[next_size] = (next_lower, next_upper)
    
    # Third pass: create more realistic ranges based on typical usage
    # Use median values to create typical ranges
    for size in sorted_sizes:
        stats = size_stats[size]
        cables_with_onts = stats.get("cables_with_onts", 0)
        
        if cables_with_onts > 0:
            median_onts = stats.get("median_onts", 0)
            min_onts = stats.get("min_onts", 0)
            max_onts = stats.get("max_onts", 0)
            
            # Create a more realistic range
            # Lower: min or 1
            # Upper: use max, but if median is much lower, use median * 3 as upper bound
            lower = max(1, min_onts)
            
            # Use 75th percentile estimate or max
            if median_onts > 0:
                upper_estimate = int(median_onts * 3)
                upper = max(max_onts, upper_estimate)
            else:
                upper = max_onts if max_onts > 0 else 1
            
            thresholds[size] = (lower, upper)
    
    print(f"  ✓ Inferred thresholds for {len(thresholds)} sizes")
    return thresholds


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def generate_summary_json(size_stats: Dict[int, Dict[str, Any]], 
                         transitions: Dict[Tuple[int, int], int],
                         thresholds: Dict[int, Tuple[int, int]]) -> None:
    """Generate cable_transitions_summary.json."""
    print("\nGenerating cable_transitions_summary.json...")
    
    # Convert transitions to list format
    transition_list = [
        {
            "from_size": from_size,
            "to_size": to_size,
            "count": count
        }
        for (from_size, to_size), count in sorted(transitions.items())
    ]
    
    summary = {
        "metadata": {
            "total_fiber_sizes": len(size_stats),
            "total_transitions": len(transitions),
            "generated_at": None
        },
        "size_statistics": {
            f"{size}F": stats for size, stats in sorted(size_stats.items(), reverse=True)
        },
        "transitions": transition_list,
        "inferred_thresholds": {
            f"{size}F": {
                "min_onts": lower,
                "max_onts": upper
            }
            for size, (lower, upper) in sorted(thresholds.items(), reverse=True)
        }
    }
    
    with open("cable_transitions_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    print("  ✓ Saved cable_transitions_summary.json")


def generate_transition_matrix_csv(transitions: Dict[Tuple[int, int], int],
                                   size_stats: Dict[int, Dict[str, Any]]) -> None:
    """Generate cable_transitions_matrix.csv."""
    print("\nGenerating cable_transitions_matrix.csv...")
    
    # Get all unique sizes
    all_sizes = sorted(set(size_stats.keys()), reverse=True)
    
    # Create matrix
    with open("cable_transitions_matrix.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # Header row
        header = ["From Size"] + [f"{size}F" for size in all_sizes]
        writer.writerow(header)
        
        # Data rows
        for from_size in all_sizes:
            row = [f"{from_size}F"]
            for to_size in all_sizes:
                count = transitions.get((from_size, to_size), 0)
                row.append(count)
            writer.writerow(row)
    
    print("  ✓ Saved cable_transitions_matrix.csv")


def generate_thresholds_txt(size_stats: Dict[int, Dict[str, Any]],
                           thresholds: Dict[int, Tuple[int, int]]) -> None:
    """Generate fiber_size_thresholds.txt."""
    print("\nGenerating fiber_size_thresholds.txt...")
    
    output = "=" * 80 + "\n"
    output += "FIBER CABLE SIZE THRESHOLDS\n"
    output += "=" * 80 + "\n\n"
    output += "Inferred placement logic based on downstream ONT counts.\n\n"
    
    # Sort sizes in descending order
    sorted_sizes = sorted(thresholds.keys(), reverse=True)
    
    output += "THRESHOLD RANGES:\n"
    output += "-" * 80 + "\n"
    
    for size in sorted_sizes:
        lower, upper = thresholds[size]
        stats = size_stats[size]
        
        output += f"\n{size}F:\n"
        output += f"  ONT Range: {lower} - {upper} ONTs\n"
        output += f"  Statistics:\n"
        output += f"    Total Cables: {stats.get('total_cables', 0)}\n"
        output += f"    Cables with ONTs: {stats.get('cables_with_onts', 0)}\n"
        output += f"    Average ONTs: {stats.get('avg_onts', 0)}\n"
        output += f"    Median ONTs: {stats.get('median_onts', 0)}\n"
        output += f"    Min ONTs: {stats.get('min_onts', 0)}\n"
        output += f"    Max ONTs: {stats.get('max_onts', 0)}\n"
        output += f"    Average Length: {stats.get('avg_length_m', 0):.1f} m\n"
        output += f"    Median Length: {stats.get('median_length_m', 0):.1f} m\n"
    
    output += "\n" + "=" * 80 + "\n"
    output += "END OF THRESHOLDS\n"
    output += "=" * 80 + "\n"
    
    with open("fiber_size_thresholds.txt", "w", encoding="utf-8") as f:
        f.write(output)
    
    print("  ✓ Saved fiber_size_thresholds.txt")


def generate_visualizations(size_stats: Dict[int, Dict[str, Any]],
                            transitions: Dict[Tuple[int, int], int]) -> None:
    """Generate visualization charts."""
    if not MATPLOTLIB_AVAILABLE:
        print("\n  ⚠ Skipping visualizations (matplotlib not available)")
        return
    
    print("\nGenerating visualizations...")
    
    # Prepare data
    sorted_sizes = sorted(size_stats.keys(), reverse=True)
    sizes_str = [f"{s}F" for s in sorted_sizes]
    avg_onts = [size_stats[s].get("avg_onts", 0) for s in sorted_sizes]
    
    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Bar chart: Average ONTs per cable size
    ax1.bar(sizes_str, avg_onts, color='steelblue', alpha=0.7)
    ax1.set_xlabel('Fiber Cable Size', fontsize=12)
    ax1.set_ylabel('Average Downstream ONTs', fontsize=12)
    ax1.set_title('Average ONTs per Cable Size', fontsize=14, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for i, (size, value) in enumerate(zip(sizes_str, avg_onts)):
        ax1.text(i, value, f'{value:.1f}', ha='center', va='bottom', fontsize=9)
    
    # Transition matrix heatmap
    matrix_data = []
    for from_size in sorted_sizes:
        row = []
        for to_size in sorted_sizes:
            count = transitions.get((from_size, to_size), 0)
            row.append(count)
        matrix_data.append(row)
    
    matrix_array = np.array(matrix_data)
    
    im = ax2.imshow(matrix_array, cmap='YlOrRd', aspect='auto')
    ax2.set_xticks(range(len(sorted_sizes)))
    ax2.set_xticklabels(sizes_str)
    ax2.set_yticks(range(len(sorted_sizes)))
    ax2.set_yticklabels(sizes_str)
    ax2.set_xlabel('To Size', fontsize=12)
    ax2.set_ylabel('From Size', fontsize=12)
    ax2.set_title('Cable Size Transition Matrix', fontsize=14, fontweight='bold')
    
    # Add text annotations
    for i in range(len(sorted_sizes)):
        for j in range(len(sorted_sizes)):
            count = matrix_array[i, j]
            if count > 0:
                ax2.text(j, i, str(count), ha='center', va='center', 
                        color='white' if count > matrix_array.max() * 0.5 else 'black',
                        fontsize=8)
    
    # Add colorbar
    plt.colorbar(im, ax=ax2, label='Transition Count')
    
    plt.tight_layout()
    plt.savefig('cable_transitions_visualization.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print("  ✓ Saved cable_transitions_visualization.png")


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main execution pipeline."""
    print("=" * 80)
    print("FIBER CABLE TRANSITION ANALYSIS")
    print("=" * 80)
    
    # Step 1: Load data
    print("\nLoading input files...")
    fiber_cable_data = load_geojson("fiber cable.geojson")
    
    print("\nLoading ONT paths...")
    with open("olt_ont_paths.json", "r", encoding="utf-8") as f:
        paths = json.load(f)
    print(f"  ✓ Loaded {len(paths)} ONT paths")
    
    # Step 2: Parse fiber cables
    cables = parse_fiber_cables(fiber_cable_data)
    
    # Step 3: Compute downstream ONT counts
    cable_ont_counts = compute_downstream_onts_per_cable(cables, paths)
    
    # Step 4: Compute size statistics
    size_stats = compute_size_statistics(cables, cable_ont_counts)
    
    # Step 5: Build transition matrix
    transitions = build_transition_matrix(cables, paths)
    
    # Step 6: Infer thresholds
    thresholds = infer_thresholds(size_stats)
    
    # Step 7: Generate outputs
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)
    
    generate_summary_json(size_stats, transitions, thresholds)
    generate_transition_matrix_csv(transitions, size_stats)
    generate_thresholds_txt(size_stats, thresholds)
    generate_visualizations(size_stats, transitions)
    
    # Final summary
    print("\n" + "=" * 80)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nAnalyzed {len(cables)} fiber cables")
    print(f"Found {len(size_stats)} unique fiber sizes")
    print(f"Identified {len(transitions)} cable size transitions")
    print(f"\nGenerated files:")
    print(f"  📄 cable_transitions_summary.json")
    print(f"  📄 cable_transitions_matrix.csv")
    print(f"  📄 fiber_size_thresholds.txt")
    if MATPLOTLIB_AVAILABLE:
        print(f"  📊 cable_transitions_visualization.png")
    print()


if __name__ == "__main__":
    main()

