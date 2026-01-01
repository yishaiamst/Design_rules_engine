#!/usr/bin/env python3
"""
Fix FOSC Placement on Fiber Cables
Ensures all FOSCs are placed ON the fiber cable (not floating).
"""

from utils.geojson_utils import load_geojson
from utils.config_loader import load_config
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from utils.spatial_utils import euclidean_distance, point_to_line_distance


def find_nearest_point_on_cable(point, cable):
    """Find nearest point on cable to given point."""
    coords = cable.get("coordinates", [])
    if not coords or len(coords) < 2:
        return point, float('inf')
    
    min_dist = float('inf')
    nearest_point = coords[0]
    
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i + 1]
        
        # Project point onto line segment
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        px, py = point[0], point[1]
        
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            t = 0
        else:
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        proj_point = (proj_x, proj_y)
        
        dist = euclidean_distance(px, py, proj_x, proj_y)
        if dist < min_dist:
            min_dist = dist
            nearest_point = proj_point
    
    return nearest_point, min_dist


def fix_fosc_placement_on_cables(foscs, fiber_cable_geojson, tolerance_m=10.0):
    """
    Ensure all FOSCs are placed ON the fiber cable.
    If a FOSC is not on a cable, move it to the nearest point on the nearest cable.
    """
    # Load cables
    cables = []
    for feature in fiber_cable_geojson.get("features", []):
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
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples
                })
    
    print(f"  Loaded {len(cables)} cables for FOSC placement verification")
    
    fixed_count = 0
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if not fosc_pos:
            continue
        
        # Check if FOSC is on any cable
        is_on_cable = False
        min_dist = float('inf')
        nearest_cable = None
        nearest_point = fosc_pos
        
        for cable in cables:
            nearest_pt, dist = find_nearest_point_on_cable(fosc_pos, cable)
            if dist < min_dist:
                min_dist = dist
                nearest_cable = cable
                nearest_point = nearest_pt
                if dist < tolerance_m:
                    is_on_cable = True
        
        if not is_on_cable:
            # Move FOSC to nearest point on cable
            fosc["position"] = nearest_point
            fosc["distance_to_cable_m"] = min_dist
            fixed_count += 1
    
    print(f"  Fixed {fixed_count} FOSCs that were not on cables")
    return foscs


def main():
    print("=" * 80)
    print("FIXING FOSC PLACEMENT ON FIBER CABLES")
    print("=" * 80)
    print()
    
    # Load data
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Run pipeline
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
    terminals, foscs, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, config)
    
    # Fix FOSC placement
    print()
    print("Fixing FOSC placement on cables...")
    fixed_foscs = fix_fosc_placement_on_cables(foscs, fiber_cable_geojson, tolerance_m=10.0)
    
    print()
    print(f"✓ Fixed {len(fixed_foscs)} FOSCs")
    print()


if __name__ == "__main__":
    main()
