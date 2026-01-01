#!/usr/bin/env python3
"""
Compare generated cable sizing against actual design.
"""

import json
import re
from collections import Counter, defaultdict
from utils.geojson_utils import load_geojson

def extract_fiber_count(value):
    """Extract fiber count from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        # Extract number from strings like "96F", "288FOC", etc.
        match = re.search(r'(\d+)', str(value))
        if match:
            return int(match.group(1))
    return None

def load_actual_design():
    """Load actual design cables with sizes."""
    print("Loading actual design...")
    actual = load_geojson("fiber cable.geojson")
    
    cables = []
    for feat in actual.get("features", []):
        props = feat.get("properties", {})
        cable_id = props.get("ID") or props.get("id", "")
        
        # Try multiple fields for size
        size = None
        for field in ["FiberCount", "Size", "size", "fiber_count"]:
            val = props.get(field)
            if val:
                size = extract_fiber_count(val)
                if size:
                    break
        
        # If still not found, try extracting from ID
        if not size and cable_id:
            size = extract_fiber_count(cable_id)
        
        cables.append({
            "id": cable_id,
            "size": size,
            "properties": props
        })
    
    print(f"  Loaded {len(cables)} cables")
    return cables

def load_generated_design():
    """Load generated cable sizing results."""
    print("Loading generated design...")
    
    # Load summary
    with open("test_output/cable_sizing_summary.json", "r") as f:
        summary_data = json.load(f)
    
    summary = summary_data.get("summary", {})
    sized_cables = summary_data.get("sized_cables", [])
    
    cables = {}
    for cable in sized_cables:
        cable_id = cable.get("original_id", "")
        # Try multiple field names for size
        size = cable.get("fiber_count") or cable.get("size", 12)  # Default to 12
        cables[cable_id] = {
            "id": cable_id,
            "size": size,
            "olt_connections": cable.get("olt_connections", []) or cable.get("connected_olts", []),
            "total_capacity": cable.get("total_capacity", 0) or cable.get("required_capacity", 0) or cable.get("required_fibers", 0)
        }
    
    print(f"  Loaded {len(cables)} sized cables")
    return cables, summary

def compare_sizes():
    """Compare actual vs generated cable sizes."""
    print("\n" + "=" * 80)
    print("CABLE SIZING COMPARISON")
    print("=" * 80)
    print()
    
    actual_cables = load_actual_design()
    generated_cables, generated_summary = load_generated_design()
    
    # Analyze actual design
    actual_sizes = Counter()
    actual_by_id = {}
    for cable in actual_cables:
        size = cable["size"]
        if size:
            actual_sizes[size] += 1
            actual_by_id[cable["id"]] = size
    
    print("ACTUAL DESIGN SIZE DISTRIBUTION:")
    for size in sorted(actual_sizes.keys()):
        print(f"  {size}F: {actual_sizes[size]:,} cables")
    print(f"  Total: {sum(actual_sizes.values()):,} cables with size info")
    print()
    
    print("GENERATED DESIGN SIZE DISTRIBUTION:")
    gen_dist = generated_summary.get("size_distribution", {})
    for size in sorted(gen_dist.keys(), key=int):
        print(f"  {size}F: {gen_dist[size]:,} cables")
    print(f"  Total: {generated_summary.get('total_cables', 0):,} cables")
    print()
    
    # Compare matching cables
    print("=" * 80)
    print("MATCHING CABLES COMPARISON")
    print("=" * 80)
    print()
    
    matches = 0
    mismatches = []
    only_actual = []
    only_generated = []
    
    all_ids = set(actual_by_id.keys()) | set(generated_cables.keys())
    
    for cable_id in all_ids:
        actual_size = actual_by_id.get(cable_id)
        generated = generated_cables.get(cable_id)
        generated_size = generated["size"] if generated else None
        
        if actual_size and generated_size:
            if actual_size == generated_size:
                matches += 1
            else:
                mismatches.append({
                    "id": cable_id,
                    "actual": actual_size,
                    "generated": generated_size,
                    "diff": generated_size - actual_size,
                    "olt_connections": generated.get("olt_connections", [])
                })
        elif actual_size and not generated_size:
            only_actual.append({"id": cable_id, "size": actual_size})
        elif generated_size and not actual_size:
            only_generated.append({"id": cable_id, "size": generated_size})
    
    print(f"Total cables in actual design: {len(actual_by_id)}")
    print(f"Total cables in generated design: {len(generated_cables)}")
    print(f"Matching cables (same ID): {len(set(actual_by_id.keys()) & set(generated_cables.keys()))}")
    print(f"Size matches: {matches}")
    print(f"Size mismatches: {len(mismatches)}")
    print(f"Cables only in actual: {len(only_actual)}")
    print(f"Cables only in generated: {len(only_generated)}")
    print()
    
    if mismatches:
        print("=" * 80)
        print("SIZE MISMATCHES (showing first 20):")
        print("=" * 80)
        print(f"{'Cable ID':<40} {'Actual':<10} {'Generated':<12} {'Diff':<10} {'OLT Connections':<15}")
        print("-" * 80)
        for m in mismatches[:20]:
            olt_info = f"{len(m['olt_connections'])} OLTs" if m['olt_connections'] else "None"
            print(f"{m['id']:<40} {m['actual']}F{'':<7} {m['generated']}F{'':<9} {m['diff']:+d}{'':<7} {olt_info}")
        if len(mismatches) > 20:
            print(f"... and {len(mismatches) - 20} more mismatches")
        print()
    
    # Analyze OLT-connected cables
    print("=" * 80)
    print("OLT-CONNECTED CABLES ANALYSIS")
    print("=" * 80)
    print()
    
    olt_cables = [c for c in generated_cables.values() if c.get("olt_connections")]
    print(f"Cables with OLT connections: {len(olt_cables)}")
    
    if olt_cables:
        print("\nOLT-connected cable sizes:")
        olt_size_dist = Counter(c["size"] for c in olt_cables)
        for size in sorted(olt_size_dist.keys(), key=int):
            print(f"  {size}F: {olt_size_dist[size]} cables")
        
        print("\nSample OLT-connected cables:")
        for cable in list(olt_cables)[:10]:
            actual_size = actual_by_id.get(cable["id"])
            match_str = f"✓ Match" if actual_size == cable["size"] else f"✗ Mismatch (actual: {actual_size}F)" if actual_size else "? No actual data"
            print(f"  {cable['id']:<40} Generated: {cable['size']}F  {match_str}")
            olt_conns = cable.get("olt_connections", [])
            if olt_conns:
                # Handle both list of dicts and list of strings
                for olt in olt_conns[:2]:
                    if isinstance(olt, dict):
                        print(f"    - OLT {olt.get('olt_id', 'N/A')}: {olt.get('ont_count', 0)} ONTs, req: {olt.get('required_capacity', 0)}F")
                    else:
                        print(f"    - OLT: {olt}")
            print(f"    Total capacity: {cable.get('total_capacity', 0)}F")
    
    # Key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    print()
    
    if len(mismatches) > 0:
        avg_diff = sum(m["diff"] for m in mismatches) / len(mismatches)
        print(f"⚠️  Average size difference: {avg_diff:+.1f}F")
        print(f"⚠️  {len(mismatches)} cables have size mismatches")
    
    if len(only_actual) > 0:
        print(f"⚠️  {len(only_actual)} cables in actual design not in generated")
    
    if len(only_generated) > 0:
        print(f"⚠️  {len(only_generated)} cables in generated design not in actual")
    
    if matches > 0:
        match_rate = matches / (matches + len(mismatches)) * 100 if (matches + len(mismatches)) > 0 else 0
        print(f"✓ Match rate: {match_rate:.1f}% ({matches}/{matches + len(mismatches)})")
    
    # Check if we're defaulting too many to 12F
    gen_12f = gen_dist.get("12", 0)
    actual_12f = actual_sizes.get(12, 0)
    if gen_12f > actual_12f * 2:
        print(f"\n⚠️  WARNING: Generated {gen_12f:,} cables as 12F, but actual has {actual_12f:,}")
        print("   This suggests we're defaulting too many cables to minimum size")

if __name__ == "__main__":
    compare_sizes()

