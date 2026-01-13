#!/usr/bin/env python3
"""
Extract data for a specific area (5km radius) for testing.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.geojson_utils import load_geojson, save_geojson
from utils.spatial_utils import euclidean_distance

def latlon_to_utm(lat, lon):
    """Convert WGS84 lat/lon to UTM Zone 17N."""
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32617", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return (easting, northing)
    except ImportError:
        # Manual approximation
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

def extract_area(geojson, center_utm, radius_m):
    """Extract features within radius of center point."""
    features = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type", "")
        
        near_center = False
        
        if geom_type == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                point_utm = (float(coords[0]), float(coords[1]))
                dist = euclidean_distance(center_utm[0], center_utm[1], point_utm[0], point_utm[1])
                if dist <= radius_m:
                    near_center = True
        elif geom_type == "LineString":
            coords = geometry.get("coordinates", [])
            for coord in coords:
                if len(coord) >= 2:
                    point_utm = (float(coord[0]), float(coord[1]))
                    dist = euclidean_distance(center_utm[0], center_utm[1], point_utm[0], point_utm[1])
                    if dist <= radius_m:
                        near_center = True
                        break
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                for coord in line:
                    if len(coord) >= 2:
                        point_utm = (float(coord[0]), float(coord[1]))
                        dist = euclidean_distance(center_utm[0], center_utm[1], point_utm[0], point_utm[1])
                        if dist <= radius_m:
                            near_center = True
                            break
                if near_center:
                    break
        
        if near_center:
            features.append(feature)
    
    result = geojson.copy()
    result["features"] = features
    return result

def main():
    # Center point for small area test
    center_lat = 45.731437
    center_lon = -82.401057
    radius_m = 5000.0  # 5km
    
    center_utm = latlon_to_utm(center_lat, center_lon)
    
    print(f"Extracting area around ({center_lat}, {center_lon}) with {radius_m/1000}km radius...")
    print(f"Center UTM: {center_utm}")
    print()
    
    # Create output directory
    output_dir = "test_output/small_area_inputs"
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract ONTs
    print("Extracting ONTs...")
    ont_geojson = load_geojson("ONT.geojson")
    extracted_onts = extract_area(ont_geojson, center_utm, radius_m)
    save_geojson(extracted_onts, f"{output_dir}/ONT.geojson")
    print(f"  ✓ Extracted {len(extracted_onts.get('features', []))} ONTs")
    
    # Extract fiber cables
    print("Extracting fiber cables...")
    fiber_geojson = load_geojson("fiber cable.geojson")
    extracted_cables = extract_area(fiber_geojson, center_utm, radius_m)
    save_geojson(extracted_cables, f"{output_dir}/fiber cable.geojson")
    print(f"  ✓ Extracted {len(extracted_cables.get('features', []))} fiber cable segments")
    
    print()
    print(f"✓ Extracted data saved to {output_dir}/")
    print()
    print("Files created:")
    print(f"  - {output_dir}/ONT.geojson")
    print(f"  - {output_dir}/fiber cable.geojson")

if __name__ == "__main__":
    main()
