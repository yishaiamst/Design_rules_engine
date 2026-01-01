#!/usr/bin/env python3
"""Check if ONTs are actually close to cables in the input data."""

from utils.geojson_utils import load_geojson
from utils.spatial_utils import point_to_line_distance
from collections import Counter

# Load ONTs
onts = load_geojson("ONT.geojson")
ont_features = onts.get("features", [])

# Load cables
cables = load_geojson("fiber cable.geojson")
cable_features = cables.get("features", [])

# Build cable data
cables_data = []
for feat in cable_features:
    props = feat.get("properties", {})
    geometry = feat.get("geometry", {})
    coords = []
    geom_type = geometry.get("type", "")
    if geom_type == "LineString":
        coords = geometry.get("coordinates", [])
    elif geom_type == "MultiLineString":
        for line in geometry.get("coordinates", []):
            coords.extend(line)
    if coords and len(coords) >= 2:
        cables_data.append({"coordinates": coords})

print(f"Loaded {len(ont_features)} ONTs")
print(f"Loaded {len(cables_data)} cables")

# Sample first 1000 ONTs to check distances
sample_size = min(1000, len(ont_features))
distances = []

for i, feat in enumerate(ont_features[:sample_size]):
    props = feat.get("properties", {})
    geometry = feat.get("geometry", {})
    coords = geometry.get("coordinates", [])
    if not coords or len(coords) < 2:
        continue
    
    ont_pos = (coords[0], coords[1])
    
    # Find nearest cable
    min_dist = float('inf')
    for cable in cables_data:
        cable_coords = cable["coordinates"]
        # Check first 50 segments for performance
        for j in range(min(50, len(cable_coords) - 1)):
            p1 = cable_coords[j]
            p2 = cable_coords[j + 1]
            if isinstance(p1, list) and len(p1) >= 2 and isinstance(p2, list) and len(p2) >= 2:
                dist = point_to_line_distance(ont_pos, p1, p2)
                if dist < min_dist:
                    min_dist = dist
                    if min_dist < 1.0:  # Early exit if very close
                        break
        if min_dist < 1.0:
            break
    
    distances.append(min_dist)
    if (i + 1) % 100 == 0:
        print(f"  Processed {i + 1}/{sample_size} ONTs...")

# Analyze distances
print(f"\nDistance distribution (sample of {len(distances)} ONTs):")
ranges = [(0, 1), (1, 10), (10, 50), (50, 100), (100, 200), (200, float('inf'))]
for min_d, max_d in ranges:
    label = f"{min_d}-{int(max_d) if max_d != float('inf') else '∞'}m"
    count = sum(1 for d in distances if min_d <= d < max_d)
    pct = count / len(distances) * 100 if distances else 0
    print(f"  {label}: {count} ({pct:.1f}%)")

if distances:
    sorted_dists = sorted(distances)
    print(f"\nStatistics:")
    print(f"  Min: {min(distances):.2f}m")
    print(f"  Max: {max(distances):.2f}m")
    print(f"  Mean: {sum(distances)/len(distances):.2f}m")
    print(f"  Median: {sorted_dists[len(sorted_dists)//2]:.2f}m")
    print(f"  P75: {sorted_dists[3*len(sorted_dists)//4]:.2f}m")
    print(f"  P90: {sorted_dists[9*len(sorted_dists)//10]:.2f}m")

