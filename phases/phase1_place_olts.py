#!/usr/bin/env python3
"""
phase1_place_olts.py
-------------------------------------------------------------------------------
Phase 1: Place OLTs based on community pockets and infrastructure.

Strategy:
1. For each community pocket, find nearest main infrastructure cable (288F/144F/96F)
2. Place OLT on/near the fiber route (within 1km)
3. Validate all ONTs in pocket are within 25km of OLT
4. Generate OLT GeoJSON output
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any, Tuple, Optional
from utils.spatial_utils import (
    euclidean_distance,
    calculate_centroid,
    point_to_linestring_distance
)
from utils.geojson_utils import create_feature, create_feature_collection

def find_infrastructure_cables(fiber_cable_geojson: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract all infrastructure cables from input.
    
    Note: Only uses ID and geometry from input. Cable sizes are not known
    and will be determined by the design engine in Phase 6.
    
    Returns list of cables with their coordinates and ID.
    """
    cables = []
    
    for feature in fiber_cable_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        # Only use ID and geometry - ignore FiberCount, Size, etc.
        cable_id = props.get("ID") or props.get("id", "")
        
        coords = []
        geom_type = geometry.get("type", "")
        
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            # Flatten MultiLineString
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            # Convert to list of tuples
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                cables.append({
                    "id": str(cable_id),
                    "coordinates": coord_tuples,
                    "properties": props  # Keep original properties for reference
                })
    
    return cables

def find_nearest_infrastructure_cable(
    point: Tuple[float, float],
    cables: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], float, Optional[Tuple[float, float]]]:
    """
    Find nearest infrastructure cable to a point.
    
    Returns:
        (cable, distance_m, nearest_point_on_cable) or (None, inf, None)
    """
    if not cables:
        return (None, float('inf'), None)
    
    min_distance = float('inf')
    nearest_cable = None
    nearest_point = None
    
    for cable in cables:
        coords = cable["coordinates"]
        distance, point_on_line = point_to_linestring_distance(point, coords)
        
        if distance < min_distance:
            min_distance = distance
            nearest_cable = cable
            nearest_point = point_on_line
    
    return (nearest_cable, min_distance, nearest_point)

def validate_olt_placement(
    olt_position: Tuple[float, float],
    ont_positions: List[Tuple[float, float]],
    max_distance_km: float
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate that all ONTs are within max_distance_km of OLT.
    
    Returns:
        (is_valid, validation_info)
    """
    distances = []
    violations = []
    
    for ont_pos in ont_positions:
        dist_km = euclidean_distance(
            olt_position[0], olt_position[1],
            ont_pos[0], ont_pos[1]
        ) / 1000.0  # Convert to km
        
        distances.append(dist_km)
        
        if dist_km > max_distance_km:
            violations.append({
                "position": ont_pos,
                "distance_km": dist_km
            })
    
    import statistics
    
    validation_info = {
        "max_distance_km": max(distances) if distances else 0.0,
        "mean_distance_km": statistics.mean(distances) if distances else 0.0,
        "min_distance_km": min(distances) if distances else 0.0,
        "violations": violations,
        "violation_count": len(violations),
        "total_onts": len(ont_positions)
    }
    
    is_valid = len(violations) == 0
    
    return (is_valid, validation_info)

def calculate_required_cable_size(ont_count: int, config: Dict[str, Any]) -> int:
    """
    Calculate required cable size using the cable sizing formula.
    
    This considers:
    - Service per ONT
    - OLT port capacity
    - Oversubscription ratio
    - Future growth
    - Max subscribers per port (256)
    
    Args:
        ont_count: Number of ONTs in the area
        config: Design configuration
        
    Returns:
        Required cable size (fiber count)
    """
    import math
    
    # Get service configuration
    service_config = config.get("service", {})
    service_per_ont_gbps = service_config.get("service_per_ont_gbps", 1.0)
    olt_port_capacity_gbps = service_config.get("olt_port_capacity_gbps", 1.0)
    default_oversubscription = service_config.get("default_oversubscription", 32)
    max_subscribers_per_port = service_config.get("max_subscribers_per_port", 256)
    future_growth_percentage = service_config.get("future_growth_percentage", 10.0)
    
    # Get OLT configuration
    olt_config = config.get("equipment", {}).get("olt", {})
    # Use first available OLT config (typically OLT-8P-1G)
    olt_type = list(olt_config.keys())[0] if olt_config else None
    if olt_type:
        olt_ports = olt_config[olt_type].get("ports", 8)
        olt_port_capacity = olt_config[olt_type].get("port_capacity_gbps", 1.0)
    else:
        olt_ports = 8
        olt_port_capacity = olt_port_capacity_gbps
    
    # Step 1: Calculate subscribers per port (capped at hard limit)
    calculated_subscribers = (
        olt_port_capacity / service_per_ont_gbps * default_oversubscription
    )
    subscribers_per_port = min(calculated_subscribers, max_subscribers_per_port)
    
    # Step 2: Calculate required OLT ports
    required_ports = math.ceil(ont_count / subscribers_per_port)
    
    # Step 3: Calculate total capacity
    total_capacity = subscribers_per_port * required_ports
    
    # Step 4: Apply future growth
    with_growth = total_capacity * (1 + future_growth_percentage / 100)
    
    # Step 5: Adjust for service level
    # If service is smaller than 1G, cable size can be proportionally smaller
    service_ratio = service_per_ont_gbps / 1.0  # Ratio to 1G
    adjusted_capacity = with_growth * service_ratio
    
    # Step 6: Select standard cable size
    standard_sizes = config.get("cables", {}).get("infrastructure_cable", {}).get("standard_sizes", [12, 24, 48, 72, 96, 144, 288])
    matching_sizes = [s for s in standard_sizes if s >= adjusted_capacity]
    
    if matching_sizes:
        required_size = min(matching_sizes)
    else:
        # If exceeds largest size, use multiple cables
        largest_size = max(standard_sizes)
        required_size = math.ceil(adjusted_capacity / largest_size) * largest_size
    
    return required_size

def find_cables_within_radius(
    point: Tuple[float, float],
    cables: List[Dict[str, Any]],
    radius_km: float
) -> List[Tuple[Dict[str, Any], float, Tuple[float, float]]]:
    """
    Find all infrastructure cables within radius, with optimal point on each cable.
    Returns list of (cable, distance_km, nearest_point) sorted by distance.
    """
    candidates = []
    
    for cable in cables:
        _, distance_m, nearest_point = find_nearest_infrastructure_cable(point, [cable])
        distance_km = distance_m / 1000.0
        
        if distance_km <= radius_km:
            candidates.append((cable, distance_km, nearest_point))
    
    # Sort by distance
    candidates.sort(key=lambda x: x[1])
    
    return candidates

def place_olt_for_pocket(
    pocket: Dict[str, Any],
    infrastructure_cables: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Place OLT for a community pocket using optimized strategy:
    1. Calculate ONT centroid (not pocket centroid)
    2. Estimate required cable size based on ONT count
    3. Find all infrastructure cables within search radius
    4. Select best cable: optimize for ONT centroid distance, prefer larger cables
    5. Place OLT on selected cable at point closest to ONT centroid
    6. Validate all ONTs within 25km
    """
    olt_config = config.get("placement", {}).get("olt", {})
    max_distance_to_fiber_km = olt_config.get("max_distance_to_fiber_route_km", 1.0)
    max_distance_from_olt_km = olt_config.get("max_distance_from_olt_km", 25.0)
    
    # Get ONT positions for this pocket
    ont_ids = pocket.get("ont_ids", [])
    ont_positions = []
    
    for feature in ont_geojson.get("features", []):
        ont_id = str(feature.get("properties", {}).get("ID") or 
                    feature.get("properties", {}).get("id", ""))
        if ont_id in ont_ids:
            geometry = feature.get("geometry", {})
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if len(coords) >= 2:
                    pos = (coords[0], coords[1])
                    ont_positions.append(pos)
    
    if not ont_positions:
        raise ValueError(f"Pocket {pocket.get('pocket_id')} has no ONT positions")
    
    # Calculate ONT centroid (not pocket centroid)
    ont_centroid = calculate_centroid(ont_positions)
    
    # Calculate required cable size using formula
    ont_count = len(ont_positions)
    required_cable_size = calculate_required_cable_size(ont_count, config)
    
    # Find all infrastructure cables within search radius
    candidate_cables = find_cables_within_radius(
        ont_centroid, infrastructure_cables, radius_km=max_distance_to_fiber_km
    )
    
    # Select best cable: optimize for ONT centroid distance
    # Note: We don't know actual cable sizes from input, so we just optimize for distance
    # Cable sizes will be determined in Phase 6
    best_placement = None
    best_distance = float('inf')
    
    if candidate_cables:
        for cable, distance_to_cable_km, point_on_cable in candidate_cables:
            # Calculate distance from point on cable to ONT centroid
            distance_to_centroid = euclidean_distance(
                ont_centroid[0], ont_centroid[1],
                point_on_cable[0], point_on_cable[1]
            ) / 1000.0  # Convert to km
            
            # Select cable closest to ONT centroid
            if distance_to_centroid < best_distance:
                best_distance = distance_to_centroid
                best_placement = {
                    "cable": cable,
                    "position": point_on_cable,
                    "distance_to_cable_km": distance_to_cable_km,
                    "distance_to_centroid_km": distance_to_centroid,
                    "required_cable_size": required_cable_size
                }
    
    # Determine OLT position
    if best_placement:
        olt_position = best_placement["position"]
        nearest_cable = best_placement["cable"]
        distance_to_cable_km = best_placement["distance_to_cable_km"]
        placement_method = "on_fiber_route" if distance_to_cable_km <= 0.01 else "near_fiber_route"
    else:
        # No nearby infrastructure, use ONT centroid
        olt_position = ont_centroid
        nearest_cable = None
        distance_to_cable_km = float('inf')
        placement_method = "centroid"
        
        # Try to find nearest cable for reporting
        if infrastructure_cables:
            nearest_cable, distance_m, _ = find_nearest_infrastructure_cable(ont_centroid, infrastructure_cables)
            distance_to_cable_km = distance_m / 1000.0
            if distance_to_cable_km > max_distance_to_fiber_km:
                print(f"    ⚠️  Warning: Pocket {pocket.get('pocket_id')} is {distance_to_cable_km:.2f}km from nearest infrastructure")
    
    # Validate OLT placement
    is_valid, validation_info = validate_olt_placement(
        olt_position,
        ont_positions,
        max_distance_from_olt_km
    )
    
    # Generate OLT ID
    pocket_id = pocket.get("pocket_id", "UNKNOWN")
    olt_id = f"OLT_{pocket_id}"
    
    # Create OLT record
    olt = {
        "olt_id": olt_id,
        "pocket_id": pocket_id,
        "position": olt_position,
        "ont_count": ont_count,
        "ont_centroid": ont_centroid,
        "placement_method": placement_method,
        "required_cable_size": required_cable_size,
        "nearest_cable": {
            "id": nearest_cable.get("id") if nearest_cable else None,
            "distance_km": distance_to_cable_km
        } if nearest_cable else None,
        "placement_optimization": {
            "distance_to_centroid_km": best_placement["distance_to_centroid_km"] if best_placement else None
        } if best_placement else None,
        "validation": validation_info,
        "is_valid": is_valid
    }
    
    return olt

def place_olts(
    community_pockets: List[Dict[str, Any]],
    fiber_cable_geojson: Dict[str, Any],
    ont_geojson: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Place OLTs for all community pockets.
    
    Returns:
        (olts_list, summary_stats)
    """
    print("  Placing OLTs...")
    
    # Find infrastructure cables (only ID and geometry from input)
    print("    Loading infrastructure cables (ID and geometry only)...")
    infrastructure_cables = find_infrastructure_cables(fiber_cable_geojson)
    print(f"    Found {len(infrastructure_cables)} infrastructure cables")
    
    if not infrastructure_cables:
        print("    ⚠️  Warning: No infrastructure cables found!")
    
    # Place OLT for each pocket
    olts = []
    total_violations = 0
    
    for i, pocket in enumerate(community_pockets, 1):
        pocket_id = pocket.get("pocket_id", f"POCKET_{i}")
        print(f"    Processing {pocket_id} ({pocket.get('ont_count', 0)} ONTs)...")
        
        try:
            olt = place_olt_for_pocket(pocket, infrastructure_cables, ont_geojson, config)
            olts.append(olt)
            
            if not olt["is_valid"]:
                violations = olt["validation"]["violation_count"]
                total_violations += violations
                print(f"      ⚠️  {violations} ONTs exceed {olt['validation']['max_distance_km']:.2f}km limit")
            else:
                print(f"      ✓ All ONTs within {olt['validation']['max_distance_km']:.2f}km")
            
        except Exception as e:
            print(f"      ❌ Error placing OLT for {pocket_id}: {e}")
            continue
    
    # Generate summary
    summary = {
        "total_olts": len(olts),
        "valid_placements": sum(1 for o in olts if o["is_valid"]),
        "invalid_placements": sum(1 for o in olts if not o["is_valid"]),
        "total_violations": total_violations,
        "placement_methods": {
            "on_fiber_route": sum(1 for o in olts if o["placement_method"] == "on_fiber_route"),
            "near_fiber_route": sum(1 for o in olts if o["placement_method"] == "near_fiber_route"),
            "centroid": sum(1 for o in olts if o["placement_method"] == "centroid")
        }
    }
    
    print(f"  ✓ Placed {len(olts)} OLTs")
    print(f"    Valid: {summary['valid_placements']}, Invalid: {summary['invalid_placements']}")
    print(f"    Total violations: {total_violations}")
    
    return (olts, summary)

def generate_olt_geojson(olts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate GeoJSON for OLTs.
    """
    features = []
    
    for olt in olts:
        position = olt["position"]
        
        properties = {
            "ID": olt["olt_id"],
            "pocket_id": olt["pocket_id"],
            "ont_count": olt["ont_count"],
            "placement_method": olt["placement_method"],
            "max_distance_km": olt["validation"]["max_distance_km"],
            "mean_distance_km": olt["validation"]["mean_distance_km"],
            "violation_count": olt["validation"]["violation_count"],
            "is_valid": olt["is_valid"]
        }
        
        if olt.get("nearest_cable"):
            properties["nearest_cable_id"] = olt["nearest_cable"]["id"]
            properties["distance_to_cable_km"] = olt["nearest_cable"]["distance_km"]
        
        if olt.get("required_cable_size"):
            properties["required_cable_size"] = olt["required_cable_size"]
        
        geometry = {
            "type": "Point",
            "coordinates": [position[0], position[1]]
        }
        feature = create_feature(
            geometry,
            properties
        )
        features.append(feature)
    
    return create_feature_collection(features)

