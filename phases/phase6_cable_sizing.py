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
    Calculate required fibers from ONT count using service, split ratio, and growth.
    
    Logic:
    1. Each ONT needs 1 fiber (via drop cable)
    2. Calculate users per fiber: (OLT Port Capacity) / (Service per ONT) × Oversubscription
    3. Apply future growth: fibers × (1 + growth%)
    4. Round up to nearest integer
    
    Example:
    - Service: 100Mbps (0.1Gbps) per ONT
    - OLT port: 1Gbps
    - Split ratio: 64
    - Users per fiber: 1Gbps / 0.1Gbps × 64 = 640 users per fiber
    - 160 ONTs need: 160 / 640 = 0.25 fibers → 1 fiber
    - With 100% growth: 1 × 2 = 2 fibers
    """
    service_config = config.get("service", {})
    service_per_ont_gbps = service_config.get("service_per_ont_gbps", 1.0)
    olt_port_capacity_gbps = service_config.get("olt_port_capacity_gbps", 1.0)
    oversubscription = service_config.get("default_oversubscription", 32)
    future_growth_pct = service_config.get("future_growth_percentage", 10.0)
    
    # Calculate users per fiber
    users_per_fiber = (olt_port_capacity_gbps / service_per_ont_gbps) * oversubscription
    
    # Calculate required fibers (before growth)
    required_fibers = math.ceil(ont_count / users_per_fiber) if users_per_fiber > 0 else ont_count
    
    # Apply future growth
    with_growth = required_fibers * (1 + future_growth_pct / 100.0)
    
    # Round up to integer
    return max(1, int(math.ceil(with_growth)))

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
            # All cables with endpoints at this location are connected
            for i, cable_idx1 in enumerate(cable_indices):
                for cable_idx2 in cable_indices[i+1:]:
                    if cable_idx2 not in cable_connections[cable_idx1]:
                        cable_connections[cable_idx1].append(cable_idx2)
                    if cable_idx1 not in cable_connections[cable_idx2]:
                        cable_connections[cable_idx2].append(cable_idx1)
    
    return dict(cable_connections)

def size_cables(
    fiber_cable_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]],  # Used for FOSC aggregation logic
    terminals: List[Dict[str, Any]],  # Used for terminal placement context
    olts: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
    min_infrastructure_size = 48  # Minimum infrastructure size
    
    # Check if user wants to override all cable sizes
    if default_size_override is not None:
        print(f"    ⚠️  Using default size override: {default_size_override}F for all infrastructure cables")
        print(f"    (This takes priority over formula-based sizing)")
    
    # Extract cables
    print("    Extracting cables...")
    cables = []
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
                cables.append({
                    "index": i,
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props,
                    "extended": False
                })
    
    print(f"    Loaded {len(cables)} cables ({time.time() - start_time:.1f}s)")
    
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
    for cable in cables:
        cable_id = cable.get("id", "")
        if cable_id:
            cable_by_id[cable_id] = cable
    
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
        tolerance_m=10.0
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
    
    # For each path, add ONT count to all cables on that path
    for ont_id, path in ont_to_olt_paths.items():
        ont_count = ont_counts.get(ont_id, 1)
        cable_indices = graph.get_cables_on_path(path)
        
        # Find OLT for this ONT
        ont_feature = None
        for feature in ont_geojson.get("features", []):
            props = feature.get("properties", {})
            if (props.get("id") or props.get("ont_id", "")) == ont_id:
                ont_feature = feature
                break
        
        olt_id = None
        if ont_feature:
            olt_id = ont_feature.get("properties", {}).get("olt_id") or ont_feature.get("properties", {}).get("oltid", "")
        
        for cable_idx in cable_indices:
            cable_ont_counts[cable_idx] += ont_count
            if olt_id:
                # Add OLT info (avoid duplicates)
                existing_olt_ids = {o.get("olt_id") for o in cable_olt_info.get(cable_idx, [])}
                if olt_id not in existing_olt_ids:
                    # Find OLT data
                    olt_data = None
                    for olt in olts:
                        if olt.get("olt_id") == olt_id:
                            olt_data = olt
                            break
                    if olt_data:
                        cable_olt_info[cable_idx].append({
                            "olt_id": olt_id,
                            "ont_count": olt_data.get("ont_count", 0)
                        })
    
    print(f"    Aggregated ONT counts for {len(cable_ont_counts)} cables")
    
    # Calculate required fibers for each cable
    cable_fiber_requirements = {}
    for cable_idx, total_onts in cable_ont_counts.items():
        required_fibers = calculate_required_fibers_from_onts(total_onts, config)
        required_fibers = max(required_fibers, min_infrastructure_size)
        cable_fiber_requirements[cable_idx] = required_fibers
    
    print(f"    Calculated fiber requirements for {len(cable_fiber_requirements)} cables")
    
    # Step 2: Size each cable based on fiber requirements
    print("  Calculating cable sizes from fiber requirements...")
    sized_cables = []
    size_distribution = defaultdict(int)
    
    for cable_idx, cable in enumerate(cables):
        required_fibers = cable_fiber_requirements.get(cable_idx, 0)
        olt_connections = cable_olt_info.get(cable_idx, [])
        total_onts = cable_ont_counts.get(cable_idx, 0)
        
        if required_fibers > 0:
            # Select smallest standard size that meets fiber requirement
            # Ensure minimum infrastructure size (48F)
            required_fibers = max(required_fibers, min_infrastructure_size)
            
            matching_sizes = [s for s in standard_sizes if s >= required_fibers]
            if matching_sizes:
                cable_size = min(matching_sizes)
            else:
                # Exceeds largest size - use multiple cables or largest size
                cable_size = max(standard_sizes)
            
            # Cap at max_size
            cable_size = min(cable_size, max_size)
            
            sized_cable = {
                "index": cable_idx,
                "original_id": cable.get("id", ""),
                "coordinates": cable["coordinates"],
                "fiber_count": cable_size,
                "required_fibers": required_fibers,
                "downstream_onts": total_onts,
                "olt_connections": olt_connections,
                "connected_olts": [olt.get("olt_id") for olt in olt_connections],
                "sizing_method": "graph_path_based",
                "properties": cable.get("properties", {}),
                "extended": False
            }
        else:
            # No OLT connection - use minimum infrastructure size (48F)
            sized_cable = {
                "index": cable_idx,
                "original_id": cable.get("id", ""),
                "coordinates": cable["coordinates"],
                "fiber_count": min_infrastructure_size,
                "required_fibers": 0,
                "downstream_onts": 0,
                "olt_connections": [],
                "connected_olts": [],
                "sizing_method": "minimum_default",
                "properties": cable.get("properties", {}),
                "extended": False
            }
        
        sized_cables.append(sized_cable)
        size_distribution[sized_cable["fiber_count"]] += 1
    
    # Step 4b: Apply FOSC aggregation logic
    print("  Applying FOSC aggregation logic...")
    fosc_aggregations = 0
    
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
        
        # Aggregate incoming cable sizes
        # Rule: If we have incoming cables (from infrastructure/OLT), sum them and apply to outgoing
        if len(incoming_cables) >= 1 and len(outgoing_cables) >= 1:
            incoming_sizes = [sized_cables[idx].get("fiber_count", min_infrastructure_size) for idx in incoming_cables]
            
            # Sum incoming sizes (if multiple incoming, sum them)
            total_incoming = sum(incoming_sizes)
            
            # Round up to next standard size
            matching_sizes = [s for s in standard_sizes if s >= total_incoming]
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
                    sized_cables[outgoing_idx]["sizing_method"] = "fosc_aggregation"
                    fosc_aggregations += 1
        
        # Also handle case where we have multiple incoming cables but need to size the outgoing
        # (This handles the case where 2+ cables come in, we sum them, and apply to outgoing)
        elif len(incoming_cables) >= 2:
            # Multiple incoming cables - sum them and ensure outgoing is at least that size
            incoming_sizes = [sized_cables[idx].get("fiber_count", min_infrastructure_size) for idx in incoming_cables]
            total_incoming = sum(incoming_sizes)
            
            matching_sizes = [s for s in standard_sizes if s >= total_incoming]
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
                    sized_cables[cable_idx]["sizing_method"] = "fosc_aggregation"
                    fosc_aggregations += 1
    
    print(f"    Applied {fosc_aggregations} FOSC aggregations")
    
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
    
    # Step 5: Assign cable IDs (uses FOSCs and terminals for FROM/TO nodes)
    print("  Assigning cable IDs...")
    sized_cables = assign_cable_ids(sized_cables, foscs, terminals, olts)
    
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
    
    return (sized_cables, summary)

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
    # Build index of nodes by position
    node_by_position = {}
    tolerance_m = 50.0
    
    for fosc in foscs:
        pos = fosc.get("position")
        if pos:
            node_by_position[tuple(pos)] = fosc.get("fosc_id", "")
    
    for terminal in terminals:
        pos = terminal.get("position")
        if pos:
            node_by_position[tuple(pos)] = terminal.get("terminal_id", "")
    
    for olt in olts:
        pos = olt.get("position")
        if pos:
            node_by_position[tuple(pos)] = olt.get("olt_id", "")
    
    # Assign IDs
    cable_id_counter = 1
    for cable in sized_cables:
        size = cable.get("fiber_count", 0)
        coords = cable.get("coordinates", [])
        
        if not coords:
            continue
        
        # Find FROM and TO nodes
        start_point = coords[0]
        end_point = coords[-1]
        
        from_node = None
        to_node = None
        min_dist_start = float('inf')
        min_dist_end = float('inf')
        
        for pos, node_id in node_by_position.items():
            dist_start = euclidean_distance(start_point[0], start_point[1], pos[0], pos[1])
            dist_end = euclidean_distance(end_point[0], end_point[1], pos[0], pos[1])
            
            if dist_start < min_dist_start and dist_start < tolerance_m:
                min_dist_start = dist_start
                from_node = node_id
            
            if dist_end < min_dist_end and dist_end < tolerance_m:
                min_dist_end = dist_end
                to_node = node_id
        
        # Generate placeholder IDs if needed
        if not from_node:
            from_node = f"F{cable_id_counter:07d}"
        if not to_node:
            to_node = f"F{cable_id_counter + 1:07d}"
        
        cable_id = f"{size}FOC/{from_node}/{to_node}"
        cable["cable_id"] = cable_id
        cable["from_id"] = from_node
        cable["to_id"] = to_node
        
        cable_id_counter += 2
    
    return sized_cables

def generate_sized_cable_geojson(sized_cables: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate GeoJSON for sized cables."""
    features = []
    
    for cable in sized_cables:
        coords = cable.get("coordinates", [])
        if not coords:
            continue
        
        # Convert to GeoJSON format
        geojson_coords = [[c[0], c[1]] for c in coords]
        
        feature = create_feature(
            geometry={
                "type": "LineString",
                "coordinates": geojson_coords
            },
            properties={
                "ID": cable.get("cable_id") or cable.get("original_id", ""),
                "Size": f"{cable.get('fiber_count', 0)}F",
                "FiberCount": cable.get("fiber_count", 0),
                "from_id": cable.get("from_id", ""),
                "to_id": cable.get("to_id", ""),
                "required_fibers": cable.get("required_fibers", 0),
                "downstream_onts": cable.get("downstream_onts", 0),
                "connected_olts": cable.get("connected_olts", [])
            }
        )
        features.append(feature)
    
    return create_feature_collection(features, crs="EPSG:32617")
