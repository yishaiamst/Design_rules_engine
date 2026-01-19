#!/usr/bin/env python3
"""
phase6_cable_sizing.py
-------------------------------------------------------------------------------
Phase 6: Cable Sizing & ID Allocation (OLT-Driven, Geometry-Based)

Key insight: FOSCs are placed AFTER cable sizing, not before!
- Cable sizing is determined by OLT capacity requirements
- Cable connectivity is determined from geometry (intersections/endpoints)
- FOSCs are placed at intersections and long segments (Phase 2)
- Cable IDs are assigned after FOSC placement

Process:
1. Map OLTs to cables (from Phase 1 nearest_cable data)
2. Calculate required capacity for each OLT
3. Build cable network topology from geometry (cable intersections/endpoints)
4. Size cables based on OLT requirements:
   - Direct OLT connections: size based on that OLT's capacity
   - Multiple OLTs: sum capacity requirements
   - Upstream cables: sum all downstream OLT requirements (trace through network)
5. Assign cable IDs (after FOSC placement - uses FOSCs for FROM/TO nodes)
-------------------------------------------------------------------------------
"""

import json
import math
import time
import os
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import defaultdict, deque, Counter
from utils.spatial_utils import euclidean_distance, point_to_line_distance
from utils.geojson_utils import create_feature, create_feature_collection
from phases.phase1_place_olts import calculate_required_cable_size
from utils.network_graph import build_network_graph, NetworkGraph

def load_intersection_patterns(pattern_file: str = "intersection_patterns.json") -> Dict[str, int]:
    """
    Load learned patterns from actual design.
    Returns patterns for use in multi-factor sizing.
    Only loads the transition_patterns summary (counts), not full examples.
    """
    if not os.path.exists(pattern_file):
        return {}
    
    try:
        # Try to load just the summary part to avoid JSON parsing issues with large files
        with open(pattern_file, "r", encoding="utf-8") as f:
            # Read file in chunks to find the transition_patterns section
            content = f.read()
            # Extract just the transition_patterns section using regex
            import re
            match = re.search(r'"transition_patterns"\s*:\s*\{([^}]+)\}', content)
            if match:
                # Parse just this section
                patterns_str = "{" + match.group(1) + "}"
                patterns = json.loads(patterns_str)
                return patterns
            else:
                # Fallback: try full JSON load
                f.seek(0)
                data = json.load(f)
                return data.get("transition_analysis", {}).get("transition_patterns", {})
    except Exception as e:
        print(f"    Warning: Could not load intersection patterns: {e}")
        # Return hardcoded common patterns as fallback
        return {
            "2x 48F → 144F": 51,
            "3x 48F → 144F": 20,
            "2x 96F → 144F": 18,
            "2x 144F → 288F": 44
        }

def calculate_size_from_patterns(
    downstream_sizes: List[int],
    patterns: Dict[str, int],
    standard_sizes: List[int]
) -> Optional[int]:
    """
    Determine upstream cable size based on learned patterns from actual design.
    
    Args:
        downstream_sizes: List of fiber counts from downstream cables
        patterns: Learned patterns from actual design (e.g., {"2x 48F → 144F": 51})
        standard_sizes: Available standard cable sizes
    
    Returns:
        Suggested size based on patterns, or None if no pattern matches
    """
    if not downstream_sizes or not patterns:
        return None
    
    size_counts = Counter(downstream_sizes)
    
    # Look for matching patterns (e.g., "2x 48F → 144F")
    best_match = None
    best_confidence = 0
    
    for pattern, count in patterns.items():
        # Parse pattern like "2x 48F → 144F"
        parts = pattern.split("→")
        if len(parts) != 2:
            continue
        
        input_part = parts[0].strip()
        output_part = parts[1].strip()
        
        # Parse input (e.g., "2x 48F")
        input_match = input_part.split("x")
        if len(input_match) != 2:
            continue
        
        try:
            pattern_count = int(input_match[0].strip())
            pattern_size = int(input_match[1].strip().replace("F", ""))
            output_size = int(output_part.strip().replace("F", ""))
        except (ValueError, IndexError):
            continue
        
        # Check if this pattern matches our downstream sizes
        if size_counts.get(pattern_size, 0) >= pattern_count:
            # Pattern matches! Use confidence based on occurrence count
            confidence = count
            if confidence > best_confidence:
                best_match = output_size
                best_confidence = confidence
    
    # Verify the suggested size is a standard size
    if best_match and best_match in standard_sizes:
        return best_match
    
    return None

def calculate_multi_factor_cable_size(
    required_fibers_from_capacity: int,
    downstream_sizes: List[int],
    patterns: Dict[str, int],
    standard_sizes: List[int],
    min_infrastructure_size: int,
    config: Dict[str, Any]
) -> int:
    """
    Multi-factor cable sizing considering:
    1. Capacity requirements (ONT count → fiber requirement)
    2. Design patterns (learned from actual design)
    3. Predefined rules (placeholders for future)
    
    Args:
        required_fibers_from_capacity: Fiber requirement from capacity calculation
        downstream_sizes: List of downstream cable sizes at intersection
        patterns: Learned patterns from actual design
        standard_sizes: Available standard cable sizes
        min_infrastructure_size: Minimum infrastructure cable size
        config: Configuration dict (for future rule-based logic)
    
    Returns:
        Selected cable size
    """
    # Factor 1: Capacity-based requirement
    capacity_based_size = max(required_fibers_from_capacity, min_infrastructure_size)
    capacity_based_size = min([s for s in standard_sizes if s >= capacity_based_size], default=max(standard_sizes))
    
    # Factor 2: Pattern-based suggestion (from actual design)
    pattern_based_size = calculate_size_from_patterns(downstream_sizes, patterns, standard_sizes)
    
    # Factor 3: Predefined rules (placeholder for future)
    # rules_based_size = apply_predefined_rules(downstream_sizes, config)
    
    # Decision logic: Use the maximum of capacity and pattern-based, but be conservative
    # If pattern suggests a size and it's reasonable (not too much larger than capacity), use it
    if pattern_based_size:
        # Use pattern if it's within 2x of capacity requirement (conservative)
        if pattern_based_size <= capacity_based_size * 2:
            # Prefer pattern if it's close to capacity or slightly larger
            if pattern_based_size >= capacity_based_size:
                return pattern_based_size
            # If pattern is smaller but still meets minimum, consider it
            elif pattern_based_size >= min_infrastructure_size:
                # Use capacity-based if pattern is too small
                return max(capacity_based_size, pattern_based_size)
    
    # Default: Use capacity-based size
    return capacity_based_size

def calculate_required_fibers_from_onts(
    ont_count: int,
    config: Dict[str, Any]
) -> int:
    """
    Calculate required fibers from ONT count using service demand,
    oversubscription, and growth.
    
    Logic:
    1) users_per_fiber = min(max_subscribers_per_port,
       (olt_port_capacity_gbps / service_per_ont_gbps) * oversubscription)
    2) required_fibers = ceil(ont_count / users_per_fiber)
    3) apply growth percentage
    """
    service_config = config.get("service", {})
    service_per_ont_gbps = service_config.get("service_per_ont_gbps", 1.0)
    olt_port_capacity_gbps = service_config.get("olt_port_capacity_gbps", 1.0)
    oversubscription = service_config.get("default_oversubscription", 32)
    max_subscribers_per_port = service_config.get("max_subscribers_per_port", 256)
    future_growth_pct = service_config.get("future_growth_percentage", 0.0)
    
    if olt_port_capacity_gbps <= 0 or service_per_ont_gbps <= 0:
        return max(1, ont_count)
    
    users_per_fiber = (olt_port_capacity_gbps / service_per_ont_gbps) * oversubscription
    users_per_fiber = min(users_per_fiber, max_subscribers_per_port)
    if users_per_fiber <= 0:
        return max(1, ont_count)
    
    required = math.ceil(ont_count / users_per_fiber)
    with_growth = math.ceil(required * (1 + future_growth_pct / 100.0))
    return max(1, with_growth)

def _split_line_by_distances(
    coords: List[Tuple[float, float]],
    split_distances: List[float],
    min_segment_len: float = 1.0
) -> List[List[Tuple[float, float]]]:
    if len(coords) < 2 or not split_distances:
        return [coords]

    # Build segment lengths and total length
    seg_lengths = []
    total_len = 0.0
    for i in range(len(coords) - 1):
        dx = coords[i + 1][0] - coords[i][0]
        dy = coords[i + 1][1] - coords[i][1]
        seg_len = math.hypot(dx, dy)
        seg_lengths.append(seg_len)
        total_len += seg_len

    # Filter split distances too close to ends
    filtered = [d for d in split_distances if min_segment_len <= d <= total_len - min_segment_len]
    if not filtered:
        return [coords]

    # Map split distances to segment indices
    insertions = defaultdict(list)  # seg_idx -> [(t, point)]
    cum = 0.0
    for d in sorted(set(filtered)):
        for i, seg_len in enumerate(seg_lengths):
            if cum + seg_len >= d:
                if seg_len == 0:
                    break
                t = (d - cum) / seg_len
                x = coords[i][0] + t * (coords[i + 1][0] - coords[i][0])
                y = coords[i][1] + t * (coords[i + 1][1] - coords[i][1])
                insertions[i].append((t, (x, y)))
                break
            cum += seg_len
        cum = 0.0

    # Build new coordinate list with inserted points
    new_coords = [coords[0]]
    split_indices = []
    for i in range(len(coords) - 1):
        if insertions.get(i):
            for _, pt in sorted(insertions[i], key=lambda p: p[0]):
                new_coords.append(pt)
                split_indices.append(len(new_coords) - 1)
        new_coords.append(coords[i + 1])

    if not split_indices:
        return [coords]

    # Split into segments at split indices
    segments = []
    start_idx = 0
    for cut_idx in split_indices:
        segment = new_coords[start_idx:cut_idx + 1]
        if len(segment) >= 2:
            segments.append(segment)
        start_idx = cut_idx
    tail = new_coords[start_idx:]
    if len(tail) >= 2:
        segments.append(tail)

    return segments

def split_cables_by_junctions(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    olts: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> Dict[str, Any]:
    """
    Split cables wherever they cross a FOSC position.
    """
    junctions = []
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            junctions.append(tuple(pos))

    features = []
    for feature in fiber_cable_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type", "")
        coords = []
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        if len(coords) < 2:
            continue

        coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
        if len(coord_tuples) < 2:
            continue

        split_distances = []
        # Find junction projections on this cable
        for jx, jy in junctions:
            min_dist = float("inf")
            best_dist_along = None
            dist_along = 0.0
            for i in range(len(coord_tuples) - 1):
                a = coord_tuples[i]
                b = coord_tuples[i + 1]
                seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
                if seg_len == 0:
                    continue
                # Project point onto segment
                t = ((jx - a[0]) * (b[0] - a[0]) + (jy - a[1]) * (b[1] - a[1])) / (seg_len ** 2)
                t = max(0.0, min(1.0, t))
                px = a[0] + t * (b[0] - a[0])
                py = a[1] + t * (b[1] - a[1])
                d = math.hypot(px - jx, py - jy)
                if d < min_dist and d <= tolerance_m:
                    min_dist = d
                    best_dist_along = dist_along + t * seg_len
                dist_along += seg_len
            dist_along = 0.0
            if best_dist_along is not None:
                split_distances.append(best_dist_along)

        segments = _split_line_by_distances(coord_tuples, split_distances, min_segment_len=1.0)
        original_id = props.get("original_id") or props.get("ID") or props.get("id", "")
        for idx, seg in enumerate(segments):
            new_props = props.copy()
            if original_id:
                new_props["original_id"] = original_id
                new_props["ID"] = f"{original_id}_S{idx + 1:02d}"
                new_props["id"] = new_props["ID"]
            geometry = {
                "type": "LineString",
                "coordinates": [[p[0], p[1]] for p in seg]
            }
            features.append(create_feature(geometry, new_props))

    return create_feature_collection(features, crs="EPSG:32617")

def merge_cables_without_fosc(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> Dict[str, Any]:
    """
    Merge cable segments that meet at endpoints where there is no FOSC.
    This prevents false breaks when input cables are split without a FOSC.
    """
    fosc_positions = []
    for fosc in foscs or []:
        pos = fosc.get("position")
        if pos:
            fosc_positions.append((pos[0], pos[1]))

    def is_fosc_near(pt):
        for fx, fy in fosc_positions:
            if euclidean_distance(pt[0], pt[1], fx, fy) <= tolerance_m:
                return True
        return False

    def coord_key(pt):
        return (int(pt[0] / tolerance_m), int(pt[1] / tolerance_m))

    features = fiber_cable_geojson.get("features", [])
    changed = True
    angle_tol_deg = 20.0
    while changed:
        changed = False
        # Build endpoint index per original_id
        endpoint_map = defaultdict(list)  # key -> [(feat_idx, is_start)]
        for idx, feat in enumerate(features):
            coords = feat.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            start = coords[0][:2]
            end = coords[-1][:2]
            endpoint_map[coord_key(start)].append((idx, True))
            endpoint_map[coord_key(end)].append((idx, False))

        merge_pair = None
        for key, endpoints in endpoint_map.items():
            if len(endpoints) != 2:
                continue
            # Only consider the first pair found for a simple iterative merge
            (idx_a, a_is_start), (idx_b, b_is_start) = endpoints[0], endpoints[1]
            if idx_a == idx_b:
                continue
            coords_a = features[idx_a].get("geometry", {}).get("coordinates", [])
            coords_b = features[idx_b].get("geometry", {}).get("coordinates", [])
            if len(coords_a) < 2 or len(coords_b) < 2:
                continue
            shared = coords_a[0][:2] if a_is_start else coords_a[-1][:2]
            if is_fosc_near(shared):
                continue
            # Check collinearity at shared endpoint to avoid merging branches
            other_a = coords_a[1][:2] if a_is_start else coords_a[-2][:2]
            other_b = coords_b[1][:2] if b_is_start else coords_b[-2][:2]
            va = (other_a[0] - shared[0], other_a[1] - shared[1])
            vb = (other_b[0] - shared[0], other_b[1] - shared[1])
            mag_a = math.hypot(va[0], va[1])
            mag_b = math.hypot(vb[0], vb[1])
            if mag_a == 0 or mag_b == 0:
                continue
            cosang = (va[0] * vb[0] + va[1] * vb[1]) / (mag_a * mag_b)
            cosang = max(-1.0, min(1.0, cosang))
            angle = math.degrees(math.acos(cosang))
            if abs(180.0 - angle) > angle_tol_deg:
                continue
            merge_pair = (idx_a, a_is_start, idx_b, b_is_start)
            break

        if not merge_pair:
            break

        idx_a, a_is_start, idx_b, b_is_start = merge_pair
        feat_a = features[idx_a]
        feat_b = features[idx_b]
        coords_a = feat_a.get("geometry", {}).get("coordinates", [])
        coords_b = feat_b.get("geometry", {}).get("coordinates", [])

        # Orient segments to connect at shared endpoint
        if a_is_start:
            coords_a = list(reversed(coords_a))
        if b_is_start:
            coords_b = coords_b
        else:
            coords_b = list(reversed(coords_b))

        # Merge, dropping duplicate shared point
        merged_coords = coords_a + coords_b[1:]
        feat_a["geometry"]["coordinates"] = merged_coords
        # Preserve merged original IDs when combining different sources
        props_a = feat_a.get("properties", {})
        props_b = feat_b.get("properties", {})
        orig_a = props_a.get("original_id") or props_a.get("ID") or props_a.get("id")
        orig_b = props_b.get("original_id") or props_b.get("ID") or props_b.get("id")
        if orig_a and orig_b and orig_a != orig_b:
            merged = list(dict.fromkeys([orig_a, orig_b]))
            props_a["merged_original_ids"] = merged

        # Remove feature b
        features.pop(idx_b)
        changed = True

    return {
        "type": "FeatureCollection",
        "features": features,
        "crs": fiber_cable_geojson.get("crs")
    }

def build_cable_network_from_geometry(
    cables: List[Dict[str, Any]],
    tolerance_m: float = 10.0
) -> Dict[int, List[int]]:
    """
    Build cable network topology from geometry.
    Cables are connected if their endpoints are close together (within tolerance).
    This is where FOSCs will be placed later.
    
    Returns: cable_idx -> [connected_cable_indices]
    """
    cable_connections = defaultdict(list)
    
    # Build spatial index for cable endpoints
    endpoint_to_cables = defaultdict(list)  # (rounded_x, rounded_y) -> [cable_idx]
    grid_size = tolerance_m  # Use tolerance as grid size
    
    for cable_idx, cable in enumerate(cables):
        coords = cable["coordinates"]
        if not coords or len(coords) < 2:
            continue
        
        # Check start and end points
        start = coords[0]
        end = coords[-1]
        
        # Round to grid
        start_key = (int(start[0] / grid_size), int(start[1] / grid_size))
        end_key = (int(end[0] / grid_size), int(end[1] / grid_size))
        
        endpoint_to_cables[start_key].append(cable_idx)
        endpoint_to_cables[end_key].append(cable_idx)
    
    # Find connections: cables with endpoints in same grid cell
    for endpoint_key, cable_indices in endpoint_to_cables.items():
        if len(cable_indices) >= 2:
            for i, cable_idx1 in enumerate(cable_indices):
                for cable_idx2 in cable_indices[i+1:]:
                    if cable_idx2 not in cable_connections[cable_idx1]:
                        cable_connections[cable_idx1].append(cable_idx2)
                    if cable_idx1 not in cable_connections[cable_idx2]:
                        cable_connections[cable_idx2].append(cable_idx1)

    def segment_intersection(a1, a2, b1, b2, eps=1e-6):
        x1, y1 = a1
        x2, y2 = a2
        x3, y3 = b1
        x4, y4 = b2
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < eps:
            return None
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
        def on_segment(p, s1, s2):
            return (
                min(s1[0], s2[0]) - eps <= p[0] <= max(s1[0], s2[0]) + eps
                and min(s1[1], s2[1]) - eps <= p[1] <= max(s1[1], s2[1]) + eps
            )
        p = (px, py)
        return p if on_segment(p, a1, a2) and on_segment(p, b1, b2) else None

    # Additional connections: segment intersections and endpoint-to-segment proximity
    for i, c1 in enumerate(cables):
        coords1 = c1.get("coordinates", [])
        if len(coords1) < 2:
            continue
        for j in range(i + 1, len(cables)):
            c2 = cables[j]
            coords2 = c2.get("coordinates", [])
            if len(coords2) < 2:
                continue
            idx1 = c1.get("index")
            idx2 = c2.get("index")
            if idx1 is None or idx2 is None:
                continue
            if idx2 in cable_connections.get(idx1, []):
                continue
            connected = False
            for a in range(len(coords1) - 1):
                for b in range(len(coords2) - 1):
                    if segment_intersection(coords1[a], coords1[a + 1], coords2[b], coords2[b + 1]):
                        connected = True
                        break
                if connected:
                    break
            if not connected:
                # Check endpoint proximity to other cable segments
                for ep in (coords1[0], coords1[-1]):
                    for b in range(len(coords2) - 1):
                        if point_to_line_distance(ep, coords2[b], coords2[b + 1]) <= tolerance_m:
                            connected = True
                            break
                    if connected:
                        break
            if not connected:
                for ep in (coords2[0], coords2[-1]):
                    for a in range(len(coords1) - 1):
                        if point_to_line_distance(ep, coords1[a], coords1[a + 1]) <= tolerance_m:
                            connected = True
                            break
                    if connected:
                        break
            if connected:
                cable_connections[idx1].append(idx2)
                cable_connections[idx2].append(idx1)
    
    return dict(cable_connections)

def size_cables(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],  # Used for FOSC aggregation logic
    terminals: List[Dict[str, Any]],  # Used for terminal placement context
    olts: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """
    Size cables based on service requirements with FOSC aggregation logic.
    
    Key features:
    1. Configuration override: If default_size_override is set, use it for all cables
    2. Formula-based sizing: Calculate based on service requirements
    3. FOSC aggregation: At FOSCs, sum incoming cable sizes (from infrastructure side)
    4. Max size limit: Cap at max_size (default 288F)
    5. Safety margin: Use larger size even if formula doesn't require it
    
    Args:
        fiber_cable_geojson: Input cable GeoJSON
        foscs: List of FOSCs (for aggregation logic)
        terminals: List of terminals (for context)
        olts: List of OLTs
        ont_geojson: ONT GeoJSON
        config: Configuration dictionary
        
    Returns:
        Tuple of (sized_cables_list, summary_dict)
    """
    print("  Sizing cables (Service Formula + FOSC Aggregation)...")
    start_time = time.time()
    
    # Get configuration
    placement_config = config.get("placement", {})
    auto_extend = placement_config.get("cable_auto_extend", True)
    
    # Get infrastructure cable configuration
    infrastructure_config = config.get("cables", {}).get("infrastructure_cable", {})
    standard_sizes = infrastructure_config.get("standard_sizes", [12, 24, 48, 72, 96, 144, 288])
    default_size_override = infrastructure_config.get("default_size_override")  # User override (e.g., 96F)
    max_size = infrastructure_config.get("max_size", 288)  # Maximum cable size (default 288F)
    min_infrastructure_size = min(standard_sizes) if standard_sizes else 12
    size_selection = infrastructure_config.get("size_selection", "max")  # min|max|formula_only
    
    # Check if user wants to override all cable sizes
    if default_size_override is not None:
        print(f"    ⚠️  Using default size override: {default_size_override}F for all infrastructure cables")
        print(f"    (This takes priority over formula-based sizing)")
    
    # Extract cables
    # CRITICAL: All input cables are preserved - they are constraints, not suggestions
    print("    Extracting cables (preserving all input cables as constraints)...")
    fiber_cable_geojson = split_cables_by_junctions(
        fiber_cable_geojson, foscs or [], terminals or [], olts or [], tolerance_m=10.0
    )
    fiber_cable_geojson = merge_cables_without_fosc(
        fiber_cable_geojson, foscs or [], tolerance_m=10.0
    )
    # Remove duplicate/overlapping cable segments by geometry within same original_id
    deduped_features = []
    seen_keys = set()
    for feature in fiber_cable_geojson.get("features", []):
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords or len(coords) < 2:
            continue
        props = feature.get("properties", {})
        original_id = props.get("original_id") or props.get("ID") or props.get("id", "") or "__no_id__"
        start = tuple(coords[0][:2]) if isinstance(coords[0], list) else tuple(coords[0][:2])
        end = tuple(coords[-1][:2]) if isinstance(coords[-1], list) else tuple(coords[-1][:2])
        key = (original_id, start, end)
        key_rev = (original_id, end, start)
        if key in seen_keys or key_rev in seen_keys:
            continue
        seen_keys.add(key)
        deduped_features.append(feature)
    fiber_cable_geojson = {"type": "FeatureCollection", "features": deduped_features, "crs": fiber_cable_geojson.get("crs")}
    cables = []
    input_cable_ids = set()  # Track which cables are from input (user-provided)
    total_features = len(fiber_cable_geojson.get("features", []))
    
    for i, feature in enumerate(fiber_cable_geojson.get("features", [])):
        if i % 1000 == 0 and i > 0:
            print(f"      Processed {i}/{total_features} features...")
        
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cable_id = props.get("ID") or props.get("id", "")
                if cable_id:
                    input_cable_ids.add(cable_id)  # Mark as input cable
                
                cables.append({
                    "index": i,
                    "id": cable_id,
                    "coordinates": coord_tuples,
                    "properties": props,
                    "extended": False,
                    "is_input_cable": bool(cable_id)  # Mark input cables
                })
    
    print(f"    Loaded {len(cables)} cables ({len(input_cable_ids)} input cables) ({time.time() - start_time:.1f}s)")

    def _extract_size_hint(props: Dict[str, Any], cable_id: str) -> Optional[int]:
        if not props:
            props = {}
        if "FiberCount" in props and isinstance(props["FiberCount"], (int, float)):
            return int(props["FiberCount"])
        if "Size" in props:
            size_str = str(props["Size"]).replace("F", "").replace("FOC", "")
            if size_str.isdigit():
                return int(size_str)
        if cable_id and "FOC" in cable_id:
            try:
                size_part = cable_id.split("FOC")[0]
                if size_part.isdigit():
                    return int(size_part)
            except Exception:
                pass
        return None
    
    # Check if default_size_override is set - if so, use it for all cables
    if default_size_override is not None:
        print(f"    Applying default size override: {default_size_override}F to all cables")
        sized_cables = []
        for cable in cables:
            sized_cables.append({
                "index": cable["index"],
                "original_id": cable.get("id", ""),
                "coordinates": cable["coordinates"],
                "fiber_count": default_size_override,
                "required_fibers": default_size_override,
                "downstream_onts": 0,
                "sizing_method": "default_override",
                "properties": cable.get("properties", {})
            })
        
        # Assign cable IDs
        print("    Assigning cable IDs...")
        sized_cables = assign_cable_ids(sized_cables, foscs, terminals, olts)
        
        summary = {
            "total_cables": len(sized_cables),
            "default_size_override": default_size_override,
            "sizing_method": "default_override",
            "max_size": max_size
        }
        
        print(f"  ✓ Sized {len(sized_cables)} cables using default override ({default_size_override}F)")
        return sized_cables, summary
    
    # Build cable index by ID for fast lookup
    print("  Building cable index by ID...")
    cable_by_id = {}
    original_to_indices = defaultdict(list)
    for cable in cables:
        cable_id = cable.get("id", "")
        if cable_id:
            cable_by_id[cable_id] = cable
        original_id = cable.get("properties", {}).get("original_id")
        if original_id:
            original_to_indices[original_id].append(cable.get("index"))
    
    print(f"    Indexed {len(cable_by_id)} cables by ID ({time.time() - start_time:.1f}s)")
    
    # NEW APPROACH: Build network graph and find ONT→OLT paths
    print("  Building network graph (tree structure)...")
    graph = build_network_graph(
        fiber_cable_geojson,
        olts,
        ont_geojson,
        foscs=foscs,
        terminals=terminals,
        config=config,
        tolerance_m=50.0
    )
    
    # Find all ONT→OLT paths
    print("  Finding ONT→OLT paths...")
    ont_to_olt_paths = graph.find_all_ont_to_olt_paths(ont_geojson, olts)
    print(f"    Found {len(ont_to_olt_paths)} paths from {len(ont_geojson.get('features', []))} ONTs")
    
    # Build ONT count map (each ONT counts as 1)
    ont_counts = {}
    for ont_feature in ont_geojson.get("features", []):
        ont_props = ont_feature.get("properties", {})
        ont_id = ont_props.get("id") or ont_props.get("ont_id", "")
        if ont_id:
            ont_counts[ont_id] = 1
    
    # Aggregate requirements along paths using graph
    print("  Aggregating fiber requirements along paths...")
    cable_ont_counts = defaultdict(int)  # cable_idx -> total ONT count
    cable_olt_info = defaultdict(list)  # cable_idx -> [olt_info] (for tracking)

    # Build geometry key map for deduping identical paths
    def _geometry_key(coords, precision=3):
        rounded = tuple((round(p[0], precision), round(p[1], precision)) for p in coords)
        rev = tuple(reversed(rounded))
        return min(rounded, rev)

    cable_geom_key = {}
    for c in cables:
        coords = c.get("coordinates", [])
        idx = c.get("index")
        if idx is None or len(coords) < 2:
            continue
        cable_geom_key[idx] = _geometry_key(coords)

    # Build unique ONT->OLT paths by geometry sequence
    unique_paths = {}
    for ont_id, path in ont_to_olt_paths.items():
        ont_count = ont_counts.get(ont_id, 1)

        ordered = []
        seen = set()
        for _, cable_idx in path:
            if cable_idx is None or cable_idx in seen:
                continue
            seen.add(cable_idx)
            ordered.append(cable_idx)

        geom_seq = tuple(cable_geom_key.get(i) for i in ordered if i in cable_geom_key)
        if not geom_seq:
            continue

        if geom_seq not in unique_paths:
            unique_paths[geom_seq] = {
                "ordered": ordered,
                "ont_count": 0,
                "olt_id": None
            }
        unique_paths[geom_seq]["ont_count"] += ont_count

        # Resolve OLT for this ONT (first seen wins)
        if unique_paths[geom_seq]["olt_id"] is None:
            ont_feature = None
            for feature in ont_geojson.get("features", []):
                props = feature.get("properties", {})
                if (props.get("id") or props.get("ont_id", "")) == ont_id:
                    ont_feature = feature
                    break
            if ont_feature:
                props = ont_feature.get("properties", {})
                unique_paths[geom_seq]["olt_id"] = props.get("olt_id") or props.get("OLT_ID") or props.get("oltid", "")

    # Apply counts across unique paths
    for info in unique_paths.values():
        group_count = info["ont_count"]
        olt_id = info.get("olt_id")
        for cable_idx in info["ordered"]:
            cable_ont_counts[cable_idx] += group_count
            if olt_id:
                existing_olt_ids = {o.get("olt_id") for o in cable_olt_info.get(cable_idx, [])}
                if olt_id not in existing_olt_ids:
                    olt_data = next((o for o in olts if o.get("olt_id") == olt_id), None)
                    if olt_data:
                        cable_olt_info[cable_idx].append({
                            "olt_id": olt_id,
                            "ont_count": olt_data.get("ont_count", 0)
                        })

    # Always aggregate by cable connectivity to enforce direction toward OLT
    ont_feature_count = len(ont_geojson.get("features", []))
    cable_direct_counts = defaultdict(int)
    if ont_feature_count:
        # Build ONT -> OLT map
        ont_to_olt = {}
        for feature in ont_geojson.get("features", []):
            props = feature.get("properties", {})
            ont_id = props.get("id") or props.get("ID") or props.get("ont_id", "")
            olt_id = props.get("olt_id") or props.get("OLT_ID") or props.get("oltid", "")
            if ont_id and olt_id:
                ont_to_olt[ont_id] = olt_id

        # Direct ONT counts per cable from terminals
        for terminal in terminals:
            cable_id = terminal.get("connected_cable_id")
            if not cable_id:
                continue
            if cable_id in cable_by_id:
                cable_idx = cable_by_id[cable_id]["index"]
            else:
                # If cable was split, map by original_id and pick nearest segment
                candidates = original_to_indices.get(cable_id, [])
                if not candidates:
                    continue
                term_pos = terminal.get("position")
                if not term_pos:
                    continue
                best_idx = None
                best_dist = float("inf")
                for idx in candidates:
                    coords = cables[idx].get("coordinates", [])
                    for i in range(len(coords) - 1):
                        d = point_to_line_distance(term_pos, coords[i], coords[i + 1])
                        if d < best_dist:
                            best_dist = d
                            best_idx = idx
                if best_idx is None:
                    continue
                cable_idx = best_idx
            ont_ids = terminal.get("connected_onts", [])
            for oid in ont_ids:
                if oid in ont_to_olt:
                    cable_direct_counts[cable_idx] += 1

        # Build cable adjacency graph
        cable_connections = build_cable_network_from_geometry(cables, tolerance_m=10.0)

        # Connect cables that meet at FOSCs
        for fosc in foscs:
            pos = fosc.get("position")
            if not pos:
                continue
            nearby = []
            for cable in cables:
                coords = cable.get("coordinates", [])
                for i in range(len(coords) - 1):
                    if point_to_line_distance(pos, coords[i], coords[i + 1]) <= 10.0:
                        nearby.append(cable.get("index"))
                        break
            for i in range(len(nearby)):
                for j in range(i + 1, len(nearby)):
                    a = nearby[i]
                    b = nearby[j]
                    if a is None or b is None:
                        continue
                    if b not in cable_connections.get(a, []):
                        cable_connections[a].append(b)
                    if a not in cable_connections.get(b, []):
                        cable_connections[b].append(a)

        # Aggregate per OLT
        tree_ont_counts = defaultdict(int)
        tree_olt_info = defaultdict(list)
        for olt in olts:
            olt_id = olt.get("olt_id")
            olt_pos = olt.get("position")
            if not olt_id or not olt_pos:
                continue

            # Find cables touching OLT position
            root_candidates = []
            for cable in cables:
                coords = cable.get("coordinates", [])
                for i in range(len(coords) - 1):
                    dist = point_to_line_distance(olt_pos, coords[i], coords[i + 1])
                    if dist <= 10.0:
                        root_candidates.append(cable.get("index"))
                        break

            if not root_candidates:
                # Fallback to nearest cable
                root_dist = float("inf")
                root_idx = None
                for cable in cables:
                    coords = cable.get("coordinates", [])
                    for i in range(len(coords) - 1):
                        dist = point_to_line_distance(olt_pos, coords[i], coords[i + 1])
                        if dist < root_dist:
                            root_dist = dist
                            root_idx = cable.get("index")
                if root_idx is None:
                    continue
                root_candidates = [root_idx]

            # Parent selection based on distance to OLT (flow toward OLT)
            cable_distance = {}
            cable_original_id = {}
            for cable in cables:
                idx = cable.get("index")
                coords = cable.get("coordinates", [])
                if idx is None or len(coords) < 2:
                    continue
                min_dist = float("inf")
                for i in range(len(coords) - 1):
                    min_dist = min(min_dist, point_to_line_distance(olt_pos, coords[i], coords[i + 1]))
                cable_distance[idx] = min_dist
                cable_original_id[idx] = cable.get("properties", {}).get("original_id") or cable.get("id")

            parent = {}
            for idx in cable_distance:
                best_parent = None
                best_dist = cable_distance[idx]
                same_orig_parent = None
                same_orig_dist = best_dist
                for neighbor in cable_connections.get(idx, []):
                    if cable_distance.get(neighbor, float("inf")) < best_dist:
                        best_dist = cable_distance[neighbor]
                        best_parent = neighbor
                    if cable_original_id.get(neighbor) == cable_original_id.get(idx):
                        if cable_distance.get(neighbor, float("inf")) < same_orig_dist:
                            same_orig_dist = cable_distance[neighbor]
                            same_orig_parent = neighbor
                if same_orig_parent is not None:
                    best_parent = same_orig_parent
                parent[idx] = best_parent

            children = defaultdict(list)
            for node, p in parent.items():
                if p is not None:
                    children[p].append(node)

            order = sorted(cable_distance.keys(), key=lambda x: cable_distance[x], reverse=True)
            totals = defaultdict(int)
            for u in order:
                totals[u] += cable_direct_counts.get(u, 0)
                for child in children.get(u, []):
                    totals[u] += totals.get(child, 0)

            for idx, count in totals.items():
                if count <= 0:
                    continue
                tree_ont_counts[idx] += count
                tree_olt_info[idx].append({"olt_id": olt_id, "ont_count": count})

        # Merge path-based counts with tree-based (use max to avoid inflation)
        for idx, count in tree_ont_counts.items():
            if count > cable_ont_counts.get(idx, 0):
                cable_ont_counts[idx] = count
                cable_olt_info[idx] = tree_olt_info.get(idx, [])

    print(f"    Aggregated ONT counts for {len(cable_ont_counts)} cables")
    
    # Calculate required fibers for each cable
    cable_fiber_requirements = {}
    for cable_idx, total_onts in cable_ont_counts.items():
        required_fibers = calculate_required_fibers_from_onts(total_onts, config)
        required_fibers = max(required_fibers, min_infrastructure_size)
        cable_fiber_requirements[cable_idx] = required_fibers
    
    print(f"    Calculated fiber requirements for {len(cable_fiber_requirements)} cables")
    
    # Step 2: Size each cable based on fiber requirements
    # CRITICAL: ALL input cable geometries must be preserved
    # Geometries are constraints - IDs and sizes can change, but coordinates must remain
    print("  Calculating cable sizes from fiber requirements...")
    sized_cables = []
    size_distribution = defaultdict(int)
    processed_cable_indices = set()  # Track which cables were processed
    
    # CRITICAL: Process ALL cables (including those not in graph)
    # This ensures all input geometries are preserved
    for cable_idx, cable in enumerate(cables):
        required_fibers = cable_fiber_requirements.get(cable_idx, 0)
        olt_connections = cable_olt_info.get(cable_idx, [])
        total_onts = cable_ont_counts.get(cable_idx, 0)
        
        cable_id = cable.get("id", "")
        size_hint = _extract_size_hint(cable.get("properties", {}), cable_id)

        if required_fibers > 0:
            # Select smallest standard size that meets fiber requirement
            # Ensure minimum infrastructure size (48F)
            required_fibers = max(required_fibers, min_infrastructure_size)
            
            matching_sizes = [s for s in standard_sizes if s >= required_fibers]
            if matching_sizes:
                computed_size = min(matching_sizes)
            else:
                # Exceeds largest size - use multiple cables or largest size
                computed_size = max(standard_sizes)
            
            # Combine computed size with size hint if present
            if size_hint and size_selection in ("min", "max"):
                if size_selection == "min":
                    cable_size = min(computed_size, size_hint)
                else:
                    cable_size = max(computed_size, size_hint)
            else:
                cable_size = computed_size
            
            # Enforce bounds
            cable_size = max(cable_size, min_infrastructure_size)
            cable_size = min(cable_size, max_size)
        else:
            # No OLT connection - use minimum infrastructure size (48F)
            cable_size = min_infrastructure_size
            if size_hint and size_selection in ("min", "max"):
                if size_selection == "min":
                    cable_size = max(min_infrastructure_size, min(cable_size, size_hint))
                else:
                    cable_size = max(cable_size, size_hint)
            cable_size = min(cable_size, max_size)
            required_fibers = 0
            total_onts = 0
            olt_connections = []

        sized_cable = {
            "index": cable_idx,
            "original_id": cable.get("properties", {}).get("original_id") or cable.get("id", ""),
            "coordinates": cable["coordinates"],
            "fiber_count": cable_size,
            "required_fibers": required_fibers,
            "downstream_onts": total_onts,
            "associated_onts": cable_direct_counts.get(cable_idx, 0),
            "aggregated_onts": total_onts,
            "olt_connections": olt_connections,
            "connected_olts": [olt.get("olt_id") for olt in olt_connections],
            "sizing_method": "graph_path_based" if required_fibers > 0 else "minimum_default",
            "properties": cable.get("properties", {}),
            "is_input_cable": cable.get("is_input_cable", False),
            "extended": False
        }
        
        # Enforce a non-zero size for all cables
        if sized_cable.get("fiber_count", 0) <= 0:
            sized_cable["fiber_count"] = min_infrastructure_size
            sized_cable["required_fibers"] = max(
                sized_cable.get("required_fibers", 0), min_infrastructure_size
            )
            sized_cable["sizing_method"] = "forced_minimum"

        sized_cables.append(sized_cable)
        size_distribution[sized_cable["fiber_count"]] += 1
        processed_cable_indices.add(cable_idx)
    
    # CRITICAL: Ensure ALL input cable geometries are preserved
    # Even if they're not in the graph or not connected to OLTs
    # Geometries are constraints - IDs and sizes can change, but geometries must remain
    print("  Ensuring all input cable geometries are preserved...")
    preserved_count = 0
    for cable_idx, cable in enumerate(cables):
        if cable_idx not in processed_cable_indices:
            # This cable wasn't processed by graph - preserve its geometry
            original_id = cable.get("id", "")
            props = cable.get("properties", {})
            
            # Try to extract size from original ID (e.g., "48FOC" -> 48F)
            fiber_count = min_infrastructure_size  # Default
            if "FOC" in original_id:
                try:
                    size_part = original_id.split("FOC")[0]
                    fiber_count = int(size_part)
                except:
                    pass
            
            # Or use size from properties if available
            if "FiberCount" in props:
                fiber_count = props["FiberCount"]
            elif "Size" in props:
                size_str = str(props["Size"]).replace("F", "")
                try:
                    fiber_count = int(size_str)
                except:
                    pass
            
            sized_cable = {
                "index": cable_idx,
                "original_id": original_id,
                "coordinates": cable["coordinates"],  # PRESERVE ORIGINAL GEOMETRY
                "fiber_count": fiber_count,
                "required_fibers": fiber_count,
                "downstream_onts": 0,
                "olt_connections": [],
                "connected_olts": [],
                "sizing_method": "geometry_preserved",
                "properties": props,
                "extended": False,
                "is_input_cable": cable.get("is_input_cable", False)
            }
            sized_cables.append(sized_cable)
            size_distribution[fiber_count] += 1
            processed_cable_indices.add(cable_idx)
            preserved_count += 1
            if original_id:
                print(f"    ✓ Preserved input cable geometry: {original_id} ({fiber_count}F, {len(cable['coordinates'])} points)")
    
    if preserved_count > 0:
        print(f"    ✓ Preserved {preserved_count} input cable geometries that were not in graph")
    
    # Step 4b: Apply FOSC aggregation logic
    print("  Applying FOSC aggregation logic...")
    fosc_aggregations = 0
    if cable_ont_counts:
        print("    Skipping size aggregation (using OLT-directed ONT counts)")
        fosc_positions = []
    else:
        # Build FOSC position list (use actual positions, not rounded)
        tolerance_m = 10.0
        fosc_positions = []
        for fosc in foscs:
            pos = fosc.get("position")
            if pos:
                fosc_positions.append({
                    "position": pos,
                    "fosc": fosc
                })
    
    if fosc_positions:
        print(f"    Checking {len(fosc_positions)} FOSCs for cable connections...")
    
    # For each FOSC, find connected cables and aggregate
    for fosc_info in fosc_positions:
        fosc_pos = fosc_info["position"]
        
        # Find cables at this FOSC position (use actual FOSC position, not rounded)
        connected_cable_indices = []
        
        for i, cable in enumerate(cables):
            coords = cable.get("coordinates", [])
            if len(coords) < 2:
                continue
            
            start = coords[0]
            end = coords[-1]
            
            dist_to_start = euclidean_distance(fosc_pos[0], fosc_pos[1], start[0], start[1])
            dist_to_end = euclidean_distance(fosc_pos[0], fosc_pos[1], end[0], end[1])
            
            if dist_to_start <= tolerance_m or dist_to_end <= tolerance_m:
                connected_cable_indices.append(i)
        
        if len(connected_cable_indices) < 2:
            continue  # Need at least 2 cables for aggregation
        
        # Determine incoming (from infrastructure/OLT) vs outgoing (to ONTs)
        # Strategy: Cables closer to OLTs are incoming
        incoming_cables = []
        outgoing_cables = []
        
        olt_positions = [olt.get("position") for olt in olts if olt.get("position")]
        
        for cable_idx in connected_cable_indices:
            cable = cables[cable_idx]
            coords = cable.get("coordinates", [])
            if len(coords) < 2:
                continue
            
            start = coords[0]
            end = coords[-1]
            
            # Check which endpoint is at FOSC
            dist_start_to_fosc = euclidean_distance(start[0], start[1], fosc_pos[0], fosc_pos[1])
            dist_end_to_fosc = euclidean_distance(end[0], end[1], fosc_pos[0], fosc_pos[1])
            
            # Find nearest OLT
            min_olt_dist = float('inf')
            if olt_positions:
                for olt_pos in olt_positions:
                    dist = euclidean_distance(fosc_pos[0], fosc_pos[1], olt_pos[0], olt_pos[1])
                    min_olt_dist = min(min_olt_dist, dist)
            
            # Determine if cable is incoming (toward OLT) or outgoing (away from OLT)
            # Simplified: If cable endpoint at FOSC is closer to OLT, it's incoming
            if dist_start_to_fosc < dist_end_to_fosc:
                # Start is at FOSC
                dist_start_to_olt = min(
                    euclidean_distance(start[0], start[1], olt_pos[0], olt_pos[1])
                    for olt_pos in olt_positions
                ) if olt_positions else float('inf')
                dist_end_to_olt = min(
                    euclidean_distance(end[0], end[1], olt_pos[0], olt_pos[1])
                    for olt_pos in olt_positions
                ) if olt_positions else float('inf')
                
                if dist_start_to_olt < dist_end_to_olt:
                    incoming_cables.append(cable_idx)
                else:
                    outgoing_cables.append(cable_idx)
            else:
                # End is at FOSC
                dist_start_to_olt = min(
                    euclidean_distance(start[0], start[1], olt_pos[0], olt_pos[1])
                    for olt_pos in olt_positions
                ) if olt_positions else float('inf')
                dist_end_to_olt = min(
                    euclidean_distance(end[0], end[1], olt_pos[0], olt_pos[1])
                    for olt_pos in olt_positions
                ) if olt_positions else float('inf')
                
                if dist_end_to_olt < dist_start_to_olt:
                    incoming_cables.append(cable_idx)
                else:
                    outgoing_cables.append(cable_idx)
        
        # Aggregate incoming requirements by ONT counts (preferred) or size
        # Rule: If we have incoming cables (from infrastructure/OLT), aggregate and apply to outgoing
        if len(incoming_cables) >= 1 and len(outgoing_cables) >= 1:
            total_incoming_onts = sum(
                sized_cables[idx].get("downstream_onts", 0) for idx in incoming_cables
            )
            if total_incoming_onts > 0:
                total_required = calculate_required_fibers_from_onts(total_incoming_onts, config)
            else:
                incoming_sizes = [
                    sized_cables[idx].get("fiber_count", min_infrastructure_size)
                    for idx in incoming_cables
                ]
                total_required = sum(incoming_sizes)
            
            total_required = max(total_required, min_infrastructure_size)
            matching_sizes = [s for s in standard_sizes if s >= total_required]
            if matching_sizes:
                aggregated_size = min(matching_sizes)
            else:
                aggregated_size = max_size
            
            # Apply max_size limit
            aggregated_size = min(aggregated_size, max_size)
            
            # Apply aggregated size to outgoing cables (use larger of current or aggregated)
            for outgoing_idx in outgoing_cables:
                current_size = sized_cables[outgoing_idx].get("fiber_count", min_infrastructure_size)
                new_size = max(current_size, aggregated_size)
                
                if new_size > current_size:  # Only count if we actually changed the size
                    sized_cables[outgoing_idx]["fiber_count"] = new_size
                    sized_cables[outgoing_idx]["required_fibers"] = new_size
                    sized_cables[outgoing_idx]["sizing_method"] = "fosc_aggregation_onts"
                    fosc_aggregations += 1
        
        # Also handle case where we have multiple incoming cables but need to size the outgoing
        # (This handles the case where 2+ cables come in, we sum them, and apply to outgoing)
        elif len(incoming_cables) >= 2:
            # Multiple incoming cables - aggregate by ONTs if possible
            total_incoming_onts = sum(
                sized_cables[idx].get("downstream_onts", 0) for idx in incoming_cables
            )
            if total_incoming_onts > 0:
                total_required = calculate_required_fibers_from_onts(total_incoming_onts, config)
            else:
                incoming_sizes = [
                    sized_cables[idx].get("fiber_count", min_infrastructure_size)
                    for idx in incoming_cables
                ]
                total_required = sum(incoming_sizes)
            
            total_required = max(total_required, min_infrastructure_size)
            matching_sizes = [s for s in standard_sizes if s >= total_required]
            if matching_sizes:
                aggregated_size = min(matching_sizes)
            else:
                aggregated_size = max_size
            
            aggregated_size = min(aggregated_size, max_size)
            
            # Apply to all cables at this FOSC (both incoming and outgoing) to ensure consistency
            for cable_idx in connected_cable_indices:
                current_size = sized_cables[cable_idx].get("fiber_count", min_infrastructure_size)
                if aggregated_size > current_size:
                    sized_cables[cable_idx]["fiber_count"] = aggregated_size
                    sized_cables[cable_idx]["required_fibers"] = aggregated_size
                    sized_cables[cable_idx]["sizing_method"] = "fosc_aggregation_onts"
                    fosc_aggregations += 1
    
    print(f"    Applied {fosc_aggregations} FOSC aggregations")

    # Step 4c: Roll up sizes along OLT-directed tree
    if olts:
        print("  Rolling up sizes along OLT-directed tree...")
        cable_connections = build_cable_network_from_geometry(cables, tolerance_m=10.0)
        # Connect cables that meet at FOSCs
        for fosc in foscs:
            pos = fosc.get("position")
            if not pos:
                continue
            nearby = []
            for cable in cables:
                coords = cable.get("coordinates", [])
                for i in range(len(coords) - 1):
                    if point_to_line_distance(pos, coords[i], coords[i + 1]) <= 10.0:
                        nearby.append(cable.get("index"))
                        break
            for i in range(len(nearby)):
                for j in range(i + 1, len(nearby)):
                    a = nearby[i]
                    b = nearby[j]
                    if a is None or b is None:
                        continue
                    if b not in cable_connections.get(a, []):
                        cable_connections[a].append(b)
                    if a not in cable_connections.get(b, []):
                        cable_connections[b].append(a)

        for olt in olts:
            olt_pos = olt.get("position")
            if not olt_pos:
                continue
            cable_distance = {}
            for cable in cables:
                idx = cable.get("index")
                coords = cable.get("coordinates", [])
                if idx is None or len(coords) < 2:
                    continue
                min_dist = float("inf")
                for i in range(len(coords) - 1):
                    min_dist = min(min_dist, point_to_line_distance(olt_pos, coords[i], coords[i + 1]))
                cable_distance[idx] = min_dist

            parent = {}
            for idx in cable_distance:
                best_parent = None
                best_dist = cable_distance[idx]
                for neighbor in cable_connections.get(idx, []):
                    if cable_distance.get(neighbor, float("inf")) < best_dist:
                        best_dist = cable_distance[neighbor]
                        best_parent = neighbor
                parent[idx] = best_parent

            children = defaultdict(list)
            for node, p in parent.items():
                if p is not None:
                    children[p].append(node)

            order = sorted(cable_distance.keys(), key=lambda x: cable_distance[x], reverse=True)
            for idx in order:
                child_sizes = [sized_cables[c].get("fiber_count", min_infrastructure_size) for c in children.get(idx, [])]
                if not child_sizes:
                    continue
                total_child = sum(child_sizes)
                matching_sizes = [s for s in standard_sizes if s >= total_child]
                aggregated_size = min(matching_sizes) if matching_sizes else max_size
                aggregated_size = min(aggregated_size, max_size)
                if aggregated_size > sized_cables[idx].get("fiber_count", min_infrastructure_size):
                    sized_cables[idx]["fiber_count"] = aggregated_size
                    sized_cables[idx]["required_fibers"] = aggregated_size
                    sized_cables[idx]["sizing_method"] = "tree_rollup"
    
    # Apply max_size limit to all cables
    for cable in sized_cables:
        current_size = cable.get("fiber_count", min_infrastructure_size)
        if current_size > max_size:
            cable["fiber_count"] = max_size
            cable["required_fibers"] = max_size
            if "sizing_method" not in cable:
                cable["sizing_method"] = "max_size_limit"
    
    # Recalculate size distribution
    size_distribution = defaultdict(int)
    for cable in sized_cables:
        size_distribution[cable.get("fiber_count", min_infrastructure_size)] += 1
    
    # Step 4d: Build debug graph summary (OLT-directed)
    graph_debug = {"olts": [], "cables": []}
    fosc_positions = []
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            fosc_positions.append((fosc.get("fosc_id") or fosc.get("ID"), pos))

    for olt in olts:
        olt_id = olt.get("olt_id")
        olt_pos = olt.get("position")
        if not olt_id or not olt_pos:
            continue
        cable_distance = {}
        for cable in cables:
            idx = cable.get("index")
            coords = cable.get("coordinates", [])
            if idx is None or len(coords) < 2:
                continue
            min_dist = float("inf")
            for i in range(len(coords) - 1):
                min_dist = min(min_dist, point_to_line_distance(olt_pos, coords[i], coords[i + 1]))
            cable_distance[idx] = min_dist

        parent = {}
        for idx in cable_distance:
            best_parent = None
            best_dist = cable_distance[idx]
            for neighbor in cable_connections.get(idx, []):
                if cable_distance.get(neighbor, float("inf")) < best_dist:
                    best_dist = cable_distance[neighbor]
                    best_parent = neighbor
            parent[idx] = best_parent

        children = defaultdict(list)
        for node, p in parent.items():
            if p is not None:
                children[p].append(node)

        graph_debug["olts"].append({
            "olt_id": olt_id,
            "position": olt_pos,
            "root_candidates": root_candidates if "root_candidates" in locals() else []
        })

        for cable in cables:
            idx = cable.get("index")
            if idx is None:
                continue
            fosc_hits = []
            coords = cable.get("coordinates", [])
            for fosc_id, pos in fosc_positions:
                for i in range(len(coords) - 1):
                    if point_to_line_distance(pos, coords[i], coords[i + 1]) <= 10.0:
                        fosc_hits.append(fosc_id)
                        break
            graph_debug["cables"].append({
                "index": idx,
                "id": cable.get("id"),
                "original_id": cable.get("properties", {}).get("original_id") or cable.get("id"),
                "distance_to_olt": cable_distance.get(idx),
                "parent_index": parent.get(idx),
                "child_indices": children.get(idx, []),
                "connected_indices": cable_connections.get(idx, []),
                "downstream_onts": cable_ont_counts.get(idx, 0),
                "fiber_count": sized_cables[idx].get("fiber_count", min_infrastructure_size),
                "cable_id": sized_cables[idx].get("cable_id"),
                "fosc_ids_on_cable": list(dict.fromkeys(fosc_hits))
            })

        break

    # Step 5: Assign cable IDs (uses FOSCs and terminals for FROM/TO nodes)
    # CRITICAL: Geometries are preserved, but IDs can be reassigned
    # Input cable geometries are constraints - they must remain, but IDs/sizes can change
    print("  Assigning cable IDs...")
    sized_cables = assign_cable_ids(sized_cables, foscs, terminals, olts)

    # Propagate ONT counts across duplicate geometries (same coordinates)
    # This keeps input duplicates consistent when only one copy appears on BFS paths.
    def _geometry_key(coords, precision=3):
        rounded = tuple((round(p[0], precision), round(p[1], precision)) for p in coords)
        rev = tuple(reversed(rounded))
        return min(rounded, rev)

    geom_groups = defaultdict(list)
    for cable in sized_cables:
        coords = cable.get("coordinates", [])
        if len(coords) < 2:
            continue
        geom_groups[_geometry_key(coords)].append(cable)

    for group in geom_groups.values():
        donor = None
        for c in group:
            if c.get("aggregated_onts", 0) > 0:
                if not donor or c.get("aggregated_onts", 0) > donor.get("aggregated_onts", 0):
                    donor = c
        if not donor:
            continue

        donor_agg = donor.get("aggregated_onts", 0)
        donor_req = calculate_required_fibers_from_onts(donor_agg, config)
        donor_req = max(donor_req, min_infrastructure_size)
        matching_sizes = [s for s in standard_sizes if s >= donor_req]
        donor_size = min(matching_sizes) if matching_sizes else max_size

        for c in group:
            if not c.get("is_input_cable"):
                continue
            if c.get("aggregated_onts", 0) > 0:
                continue
            c["aggregated_onts"] = donor_agg
            c["downstream_onts"] = donor_agg
            c["required_fibers"] = donor_req
            if c.get("fiber_count", 0) < donor_size:
                c["fiber_count"] = donor_size
            if donor.get("olt_connections"):
                c["olt_connections"] = donor.get("olt_connections", [])
                c["connected_olts"] = donor.get("connected_olts", [])
            c["sizing_method"] = "duplicate_geometry_propagation"

    # Re-assign IDs in case fiber_count changed during propagation
    sized_cables = assign_cable_ids(sized_cables, foscs, terminals, olts)

    # Remove duplicate base_id cables with no ONT contribution
    base_max_agg = defaultdict(int)
    for cable in sized_cables:
        base_id = cable.get("base_id")
        if not base_id:
            continue
        base_max_agg[base_id] = max(base_max_agg[base_id], cable.get("aggregated_onts", 0))
    filtered_cables = []
    for cable in sized_cables:
        base_id = cable.get("base_id")
        agg = cable.get("aggregated_onts", 0)
        assoc = cable.get("associated_onts", 0)
        if cable.get("is_input_cable"):
            filtered_cables.append(cable)
            continue
        if base_id and base_max_agg.get(base_id, 0) > 0 and agg == 0 and assoc == 0:
            continue
        filtered_cables.append(cable)
    sized_cables = filtered_cables
    
    # Generate summary
    total_time = time.time() - start_time
    summary = {
        "total_cables": len(sized_cables),
        "size_distribution": dict(size_distribution),
        "cables_with_olts": len(cable_fiber_requirements),
        "cables_extended": 0,  # Graph-based approach doesn't extend cables
        "fosc_aggregations": fosc_aggregations,
        "max_size": max_size,
        "default_size_override": default_size_override,
        "total_onts_served": sum(sum(olt["ont_count"] for olt in cable_olt_info.get(i, [])) for i in range(len(cables))),
        "processing_time_seconds": total_time
    }
    
    print(f"  ✓ Sized {len(sized_cables)} cables ({total_time:.1f}s total)")
    print(f"    Size distribution: {dict(size_distribution)}")
    print(f"    Cables with OLT connections: {summary['cables_with_olts']}")
    print(f"    FOSC aggregations: {fosc_aggregations}")
    print(f"    Max size limit: {max_size}F")
    print(f"    ONT paths found: {len(ont_to_olt_paths)}")
    # Build ONT -> cable ID path map for debugging/visualization
    cable_id_by_index = {c.get("index"): c.get("base_id") or c.get("cable_id") for c in sized_cables}
    ont_cable_paths = {}
    for ont_id, path in ont_to_olt_paths.items():
        ordered_cables = []
        seen = set()
        for _, cable_idx in path:
            if cable_idx is None or cable_idx in seen:
                continue
            seen.add(cable_idx)
            ordered_cables.append(cable_idx)
        ont_cable_paths[ont_id] = [
            cable_id_by_index.get(i)
            for i in ordered_cables
            if cable_id_by_index.get(i)
        ]
    
    graph_debug["ont_cable_paths"] = ont_cable_paths
    return (sized_cables, summary, graph_debug)

def assign_cable_ids(
    sized_cables: List[Dict[str, Any]],
    foscs: List[Dict[str, Any]],
    terminals: List[Dict[str, Any]],
    olts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Assign cable IDs following pattern: {SIZE}FOC/{FROM_ID}/{TO_ID}
    Uses FOSCs, terminals, and OLTs as FROM/TO nodes.
    
    Args:
        sized_cables: List of sized cable dicts
        foscs: List of FOSC dicts
        terminals: List of terminal dicts
        olts: List of OLT dicts
        
    Returns:
        Updated sized_cables with cable_id, from_id, to_id
    """
    # Build index of FOSC nodes by position
    fosc_positions = []
    tolerance_m = 50.0
    
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            fosc_positions.append((fosc.get("fosc_id", ""), (pos[0], pos[1])))
    
    # Cable IDs are based only on FOSCs for now
    
    # Assign IDs
    cable_id_counter = 1
    for cable in sized_cables:
        size = cable.get("fiber_count", 0)
        coords = cable.get("coordinates", [])
        
        if not coords:
            continue
        
        # Find FROM and TO nodes (FOSC-only)
        start_point = coords[0]
        end_point = coords[-1]
        
        from_node = None
        to_node = None
        min_dist_start = float('inf')
        min_dist_end = float('inf')
        
        for node_id, pos in fosc_positions:
            dist_start = euclidean_distance(start_point[0], start_point[1], pos[0], pos[1])
            dist_end = euclidean_distance(end_point[0], end_point[1], pos[0], pos[1])
            
            if dist_start < min_dist_start and dist_start < tolerance_m:
                min_dist_start = dist_start
                from_node = node_id
            
            if dist_end < min_dist_end and dist_end < tolerance_m:
                min_dist_end = dist_end
                to_node = node_id
        
        # Avoid false FOSC-to-same-FOSC IDs
        if from_node and to_node and from_node == to_node:
            if min_dist_end >= min_dist_start:
                to_node = None
            else:
                from_node = None

        # Generate placeholder IDs if needed
        if not from_node:
            from_node = "UNKNOWN"
        if not to_node:
            to_node = "UNKNOWN"
        
        cable_id = f"{size}FOC/{from_node}/{to_node}"
        cable["cable_id"] = cable_id
        cable["base_id"] = f"{from_node}/{to_node}"
        cable["from_id"] = from_node
        cable["to_id"] = to_node
        
        cable_id_counter += 2
    
    return sized_cables

def generate_sized_cable_geojson(sized_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate GeoJSON for sized cables.
    
    CRITICAL: Preserves all input cable geometries.
    IDs and sizes can be reassigned, but geometries (coordinates) must remain unchanged.
    """
    features = []
    
    for cable in sized_cables:
        coords = cable.get("coordinates", [])
        if not coords:
            continue
        
        # CRITICAL: Preserve original geometry exactly as provided
        # Convert to GeoJSON format (preserve coordinate structure)
        geojson_coords = [[c[0], c[1]] for c in coords]
        
        # Get properties - preserve original properties but update ID/size
        original_props = cable.get("properties", {})
        props = original_props.copy() if original_props else {}
        
        # Update with new ID and size (geometries are preserved)
        props["ID"] = cable.get("cable_id") or cable.get("original_id", "")
        props["Size"] = f"{cable.get('fiber_count', 0)}F"
        props["FiberCount"] = cable.get("fiber_count", 0)
        props["base_id"] = cable.get("base_id", "")
        props["from_id"] = cable.get("from_id", "")
        props["to_id"] = cable.get("to_id", "")
        props["required_fibers"] = cable.get("required_fibers", 0)
        props["downstream_onts"] = cable.get("downstream_onts", 0)
        props["associated_onts"] = cable.get("associated_onts", 0)
        props["aggregated_onts"] = cable.get("aggregated_onts", props.get("downstream_onts", 0))
        props["connected_olts"] = cable.get("connected_olts", [])
        if "ont_count" in props:
            del props["ont_count"]
        
        # Mark if this was an input cable (geometry preserved)
        if cable.get("is_input_cable", False):
            props["geometry_preserved"] = True
            props["original_id"] = cable.get("original_id", "")
            props["is_input_cable"] = True
        
        feature = create_feature(
            geometry={
                "type": "LineString",
                "coordinates": geojson_coords  # PRESERVED GEOMETRY
            },
            properties=props
        )
        features.append(feature)
    
    return create_feature_collection(features, crs="EPSG:32617")
