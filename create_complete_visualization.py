#!/usr/bin/env python3
"""
Create complete visualization with all fixes applied:
- FOSCs at cable junctions
- MSTs connected to FOSCs via stub cables
- Drop cables from terminals to ONTs
- Filtered distant ONTs
"""

import json
import math
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    import math


def latlon_to_utm(lat, lon, zone=17):
    """Convert WGS84 lat/lon to UTM Zone 17N."""
    if PYPROJ_AVAILABLE:
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:32617", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return (easting, northing)
    else:
        import math
        k0 = 0.9996
        a = 6378137.0
        e2 = 0.00669438
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        central_meridian = math.radians(-81.0)
        N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)
        T = math.tan(lat_rad)**2
        C = e2 * math.cos(lat_rad)**2 / (1 - e2)
        A = math.cos(lat_rad) * (lon_rad - central_meridian)
        M = a * ((1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_rad
                 - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_rad)
                 + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_rad)
                 - (35*e2**3/3072) * math.sin(6*lat_rad))
        easting = k0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58)*A**5/120) + 500000.0
        northing = k0 * (M + N*math.tan(lat_rad)*(A**2/2 + (5-T+9*C+4*C**2)*A**4/24 + (61-58*T+T**2+600*C-330)*A**6/720))
        return (easting, northing)


def main():
    print("=" * 80)
    print("CREATING COMPLETE VISUALIZATION")
    print("=" * 80)
    print()
    
    # Center point
    center_lat = 45.731437
    center_lon = -82.401057
    radius_m = 5000.0
    center_utm = latlon_to_utm(center_lat, center_lon)
    
    # Load fixed data
    print("Loading fixed data...")
    with open("test_output/fixed_terminals.json") as f:
        terminals = json.load(f)
    
    with open("test_output/fixed_foscs.json") as f:
        foscs = json.load(f)
    
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    
    # Extract area
    extracted_onts = []
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            ont_pos_utm = (float(coords[0]), float(coords[1]))
            dist = euclidean_distance(center_utm[0], center_utm[1], ont_pos_utm[0], ont_pos_utm[1])
            if dist <= radius_m:
                extracted_onts.append(feature)
    
    extracted_cables = []
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        coords_list = []
        
        if geometry.get("type") == "LineString":
            coords_list = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords_list.extend(line)
        
        near_center = False
        for coord in coords_list:
            if len(coord) >= 2:
                cable_pos_utm = (float(coord[0]), float(coord[1]))
                dist = euclidean_distance(center_utm[0], center_utm[1], cable_pos_utm[0], cable_pos_utm[1])
                if dist <= radius_m:
                    near_center = True
                    break
        
        if near_center:
            extracted_cables.append(feature)
    
    print(f"  Loaded {len(terminals)} terminals, {len(foscs)} FOSCs")
    print(f"  Extracted {len(extracted_onts)} ONTs, {len(extracted_cables)} cables")
    print()
    
    # Build ONT position map
    onts_by_id = {}
    for feature in extracted_onts:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        ont_id = props.get("ID") or props.get("id", "")
        
        coords = None
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        elif geometry.get("type") == "MultiPoint":
            coords_list = geometry.get("coordinates", [])
            if coords_list:
                coords = coords_list[0]
        
        if ont_id and coords and len(coords) >= 2:
            onts_by_id[ont_id] = (float(coords[0]), float(coords[1]))
    
    # Create visualization features
    vis_features = []
    
    # Center point
    center_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [center_utm[0], center_utm[1]]
        },
        "properties": {
            "name": "Center Point",
            "marker-color": "#FF0000",
            "marker-size": "large",
            "marker-symbol": "star"
        }
    }
    vis_features.append(center_feature)
    
    # Radius circle
    circle_points = []
    for angle in range(0, 360, 10):
        angle_rad = math.radians(angle)
        x = center_utm[0] + radius_m * math.cos(angle_rad)
        y = center_utm[1] + radius_m * math.sin(angle_rad)
        circle_points.append([x, y])
    circle_points.append(circle_points[0])
    
    radius_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": circle_points
        },
        "properties": {
            "name": "5km Radius",
            "stroke": "#FF0000",
            "stroke-width": 2,
            "stroke-opacity": 0.3
        }
    }
    vis_features.append(radius_feature)
    
    # Cables
    vis_features.extend(extracted_cables)
    
    # Stub cables (MST to FOSC)
    stub_cables = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_type = terminal.get("type", "")
        terminal_pos = terminal.get("position")
        connected_fosc_id = terminal.get("connected_fosc_id")
        
        if terminal_type == "MST" and connected_fosc_id and terminal_pos:
            term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
            
            # Find FOSC
            fosc = next((f for f in foscs if f.get("fosc_id") == connected_fosc_id), None)
            if fosc:
                fosc_pos = fosc.get("position")
                if fosc_pos:
                    fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
                    
                    stub_cable = {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [term_pos_utm[0], term_pos_utm[1]],
                                [fosc_pos_utm[0], fosc_pos_utm[1]]
                            ]
                        },
                        "properties": {
                            "id": f"stub_{terminal_id}_{connected_fosc_id}",
                            "terminal_id": terminal_id,
                            "fosc_id": connected_fosc_id,
                            "stroke": "#00FF00",
                            "stroke-width": 3,
                            "stroke-opacity": 0.8
                        }
                    }
                    stub_cables.append(stub_cable)
    
    vis_features.extend(stub_cables)
    print(f"  Created {len(stub_cables)} stub cables")
    
    # Drop cables (Terminal to ONT)
    drop_cables = []
    for terminal in terminals:
        terminal_id = terminal.get("terminal_id", "")
        terminal_pos = terminal.get("position")
        connected_onts = terminal.get("connected_onts", [])
        
        if not terminal_pos or not connected_onts:
            continue
        
        term_pos_utm = (terminal_pos[0], terminal_pos[1]) if isinstance(terminal_pos, list) else terminal_pos
        
        for ont_id in connected_onts:
            if ont_id in onts_by_id:
                ont_pos = onts_by_id[ont_id]
                
                drop_cable = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [ont_pos[0], ont_pos[1]],
                            [term_pos_utm[0], term_pos_utm[1]]
                        ]
                    },
                    "properties": {
                        "id": f"drop_{ont_id}_{terminal_id}",
                        "ont_id": ont_id,
                        "terminal_id": terminal_id,
                        "stroke": "#FFA500",
                        "stroke-width": 2,
                        "stroke-opacity": 0.7
                    }
                }
                drop_cables.append(drop_cable)
    
    vis_features.extend(drop_cables)
    print(f"  Created {len(drop_cables)} drop cables")
    
    # ONTs
    vis_features.extend(extracted_onts)
    
    # Terminals
    for terminal in terminals:
        term_pos = terminal.get("position")
        if term_pos:
            term_pos_utm = (term_pos[0], term_pos[1]) if isinstance(term_pos, list) else term_pos
            term_type = terminal.get("type", "Terminal")
            color = "#800080" if term_type == "MST" else "#FF00FF"
            
            term_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [term_pos_utm[0], term_pos_utm[1]]
                },
                "properties": {
                    "id": terminal.get("terminal_id", ""),
                    "type": term_type,
                    "connected_onts": len(terminal.get("connected_onts", [])),
                    "marker-color": color,
                    "marker-size": "medium",
                    "marker-symbol": "triangle" if term_type == "MST" else "circle"
                }
            }
            vis_features.append(term_feature)
    
    # FOSCs
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        if fosc_pos:
            fosc_pos_utm = (fosc_pos[0], fosc_pos[1]) if isinstance(fosc_pos, list) else fosc_pos
            fosc_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [fosc_pos_utm[0], fosc_pos_utm[1]]
                },
                "properties": {
                    "id": fosc.get("fosc_id", ""),
                    "restored": fosc.get("restored", False),
                    "marker-color": "#0000FF",
                    "marker-size": "medium",
                    "marker-symbol": "circle"
                }
            }
            vis_features.append(fosc_feature)
    
    vis_geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:EPSG::32617"
            }
        },
        "features": vis_features
    }
    
    with open("test_output/complete_fixed_visualization.geojson", "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    print()
    print(f"✓ Saved visualization: test_output/complete_fixed_visualization.geojson")
    print(f"  Total features: {len(vis_features)}")
    print(f"  - {len(stub_cables)} stub cables (green)")
    print(f"  - {len(drop_cables)} drop cables (orange)")
    print(f"  - {len(extracted_onts)} ONTs")
    print(f"  - {len(terminals)} terminals")
    print(f"  - {len(foscs)} FOSCs")
    print(f"  - {len(extracted_cables)} cables")
    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
