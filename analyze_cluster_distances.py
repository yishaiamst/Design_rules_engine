#!/usr/bin/env python3
"""Quick analysis of cluster distances to understand the issue."""

import json
from collections import Counter
from utils.geojson_utils import load_geojson
from utils.spatial_utils import point_to_line_distance, euclidean_distance

# Load generated terminals
with open("test_output/terminal_placement_summary.json", "r") as f:
    data = json.load(f)

terminals = data.get("terminals", [])
print(f"Total terminals: {len(terminals)}")

# Count by type
aerial = [t for t in terminals if t.get("type") == "Aerial Terminal"]
mst = [t for t in terminals if t.get("type") == "MST"]

print(f"Aerial: {len(aerial)}")
print(f"MST: {len(mst)}")

# Analyze distances
aerial_distances = [t.get("distance_to_cable_m", 0) for t in aerial]
mst_distances = [t.get("distance_to_cable_m", 0) for t in mst]

print(f"\nAerial distances: min={min(aerial_distances) if aerial_distances else 0:.2f}m, max={max(aerial_distances) if aerial_distances else 0:.2f}m, mean={sum(aerial_distances)/len(aerial_distances) if aerial_distances else 0:.2f}m")
print(f"MST distances: min={min(mst_distances) if mst_distances else 0:.2f}m, max={max(mst_distances) if mst_distances else 0:.2f}m, mean={sum(mst_distances)/len(mst_distances) if mst_distances else 0:.2f}m")

# Count by distance ranges
ranges = [(0, 1), (1, 10), (10, 50), (50, 100), (100, 200), (200, float('inf'))]
print("\nDistance distribution:")
print(f"{'Range':<15} {'Aerial':<10} {'MST':<10}")
print("-" * 35)
for min_d, max_d in ranges:
    label = f"{min_d}-{int(max_d) if max_d != float('inf') else '∞'}m"
    aerial_count = sum(1 for d in aerial_distances if min_d <= d < max_d)
    mst_count = sum(1 for d in mst_distances if min_d <= d < max_d)
    print(f"{label:<15} {aerial_count:<10} {mst_count:<10}")

