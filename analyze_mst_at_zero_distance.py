#!/usr/bin/env python3
"""Analyze MST terminals at 0.00m distance - why aren't they Aerial?"""

import json

# Load generated terminals
with open("test_output/terminal_placement_summary.json", "r") as f:
    data = json.load(f)

terminals = data.get("terminals", [])

# Find MST terminals at 0.00m
mst_at_zero = [t for t in terminals if t.get("type") == "MST" and t.get("distance_to_cable_m", 999) < 0.01]
aerial_at_zero = [t for t in terminals if t.get("type") == "Aerial Terminal" and t.get("distance_to_cable_m", 999) < 0.01]

print(f"MST terminals at 0.00m: {len(mst_at_zero)}")
print(f"Aerial terminals at 0.00m: {len(aerial_at_zero)}")

# Analyze FOSC distances
mst_fosc_distances = [t.get("distance_to_fosc_m", 0) for t in mst_at_zero if t.get("distance_to_fosc_m") is not None]
aerial_fosc_distances = [t.get("distance_to_fosc_m", 0) for t in aerial_at_zero if t.get("distance_to_fosc_m") is not None]

if mst_fosc_distances:
    print(f"\nMST at 0.00m - FOSC distances:")
    print(f"  Min: {min(mst_fosc_distances):.1f}m")
    print(f"  Max: {max(mst_fosc_distances):.1f}m")
    print(f"  Mean: {sum(mst_fosc_distances)/len(mst_fosc_distances):.1f}m")
    print(f"  Median: {sorted(mst_fosc_distances)[len(mst_fosc_distances)//2]:.1f}m")
    
    # Count by FOSC distance ranges
    ranges = [(0, 200), (200, 300), (300, float('inf'))]
    print(f"\n  FOSC distance distribution:")
    for min_d, max_d in ranges:
        label = f"{min_d}-{int(max_d) if max_d != float('inf') else '∞'}m"
        count = sum(1 for d in mst_fosc_distances if min_d <= d < max_d)
        print(f"    {label}: {count}")

if aerial_fosc_distances:
    print(f"\nAerial at 0.00m - FOSC distances:")
    print(f"  Min: {min(aerial_fosc_distances):.1f}m")
    print(f"  Max: {max(aerial_fosc_distances):.1f}m")
    print(f"  Mean: {sum(aerial_fosc_distances)/len(aerial_fosc_distances):.1f}m")
    print(f"  Median: {sorted(aerial_fosc_distances)[len(aerial_fosc_distances)//2]:.1f}m")

