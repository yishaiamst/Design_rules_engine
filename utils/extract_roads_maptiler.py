#!/usr/bin/env python3
"""
extract_roads_maptiler.py
-------------------------------------------------------------------------------
Extract road/street data from MapTiler or OSM for use in Rule 23.

Options:
1. MapTiler API (requires API key)
2. OSM Overpass API (free, no key needed)
3. Extract from existing GeoJSON bounding box
-------------------------------------------------------------------------------
"""

import json
import os
import sys
import math
from typing import Dict, List, Any, Tuple, Optional
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.geojson_utils import create_feature_collection, create_feature


def calculate_bbox_from_geojson(geojson: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    """
    Calculate bounding box from GeoJSON features.
    
    Returns:
        (min_x, min_y, max_x, max_y) in UTM coordinates, or None
    """
    all_coords = []
    
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])
        
        if geom_type == "Point":
            if len(coords) >= 2:
                all_coords.append((coords[0], coords[1]))
        elif geom_type == "LineString":
            for coord in coords:
                if len(coord) >= 2:
                    all_coords.append((coord[0], coord[1]))
        elif geom_type == "MultiLineString":
            for line in coords:
                for coord in line:
                    if len(coord) >= 2:
                        all_coords.append((coord[0], coord[1]))
    
    if not all_coords:
        return None
    
    x_coords = [c[0] for c in all_coords]
    y_coords = [c[1] for c in all_coords]
    
    return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))


def utm_to_latlon(easting: float, northing: float, zone: int = 17) -> Tuple[float, float]:
    """
    Convert UTM coordinates to lat/lon.
    
    Args:
        easting: UTM easting (x)
        northing: UTM northing (y)
        zone: UTM zone (default 17 for Ontario)
    
    Returns:
        (latitude, longitude) in degrees
    """
    # Use pyproj if available (accurate)
    try:
        import pyproj
        utm = pyproj.Proj(proj='utm', zone=zone, ellps='WGS84', preserve_units=False)
        wgs84 = pyproj.Proj(proj='latlong', ellps='WGS84')
        lon, lat = pyproj.transform(utm, wgs84, easting, northing)
        return lat, lon
    except ImportError:
        # Fallback: use online service or manual conversion
        # For now, return approximate values (will need pyproj for accuracy)
        print("  ⚠️  pyproj not installed - using approximate conversion")
        print("  💡 Install with: pip3 install --user pyproj")
        # Approximate: UTM Zone 17N center is around -82°W, 45.7°N
        # This is a rough approximation - should use pyproj for accuracy
        center_lon = -82.0  # Approximate for Zone 17
        center_lat = 45.7   # Approximate for Ontario
        
        # Rough conversion (meters to degrees)
        # 1 degree lat ≈ 111,000m, 1 degree lon ≈ 78,000m at this latitude
        lat = center_lat + (northing - 5000000) / 111000.0
        lon = center_lon + (easting - 500000) / (111000.0 * math.cos(math.radians(center_lat)))
        
        return lat, lon


def extract_roads_from_osm_overpass(
    bbox: Tuple[float, float, float, float],
    output_path: str,
    utm_zone: int = 17
) -> Dict[str, Any]:
    """
    Extract roads from OSM using Overpass API (free, no API key needed).
    
    Args:
        bbox: (min_x, min_y, max_x, max_y) in UTM coordinates
        output_path: Path to save GeoJSON
        utm_zone: UTM zone for coordinate conversion
    
    Returns:
        GeoJSON FeatureCollection of roads
    """
    print("Extracting roads from OSM Overpass API...")
    
    # Convert UTM bbox to lat/lon
    min_lat, min_lon = utm_to_latlon(bbox[0], bbox[1], utm_zone)
    max_lat, max_lon = utm_to_latlon(bbox[2], bbox[3], utm_zone)
    
    # Overpass API query
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Query for all roads (highways)
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"~"^(primary|secondary|tertiary|unclassified|residential|service|track|path)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """
    
    print(f"  Querying OSM for roads in bbox: ({min_lat:.6f}, {min_lon:.6f}) to ({max_lat:.6f}, {max_lon:.6f})")
    
    try:
        # Use urllib instead of requests (no external dependency)
        req = Request(overpass_url, data=query.encode('utf-8'), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Convert OSM format to GeoJSON
        # OSM returns nodes and ways separately
        nodes = {node["id"]: (node["lon"], node["lat"]) for node in data.get("elements", []) if node.get("type") == "node"}
        
        roads = []
        for element in data.get("elements", []):
            if element.get("type") == "way" and "geometry" in element:
                # Get coordinates from geometry
                coords = []
                for point in element.get("geometry", []):
                    lon, lat = point.get("lon"), point.get("lat")
                    # Convert back to UTM
                    # For now, keep as lat/lon - we'll convert in a separate step
                    coords.append([lon, lat])
                
                if len(coords) >= 2:
                    highway_type = element.get("tags", {}).get("highway", "unknown")
                    name = element.get("tags", {}).get("name", "")
                    
                    roads.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coords
                        },
                        "properties": {
                            "highway": highway_type,
                            "name": name,
                            "osm_id": element.get("id")
                        }
                    })
        
        print(f"  ✓ Found {len(roads)} road segments")
        
        # Create GeoJSON (OSM uses WGS84, but we'll convert to UTM later)
        geojson = create_feature_collection(roads, crs="EPSG:4326")  # OSM uses WGS84
        
        # Save
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(geojson, f, indent=2)
        
        print(f"  ✓ Saved to {output_path}")
        print(f"  ⚠️  Note: Roads are in WGS84 (lat/lon). Convert to UTM Zone {utm_zone} for use with Rule 23.")
        
        return geojson
        
    except URLError as e:
        print(f"  ✗ Network error extracting roads: {e}")
        print(f"  💡 Check internet connection or try again later")
        return None
    except Exception as e:
        print(f"  ✗ Error extracting roads: {e}")
        import traceback
        traceback.print_exc()
        return None


def convert_wgs84_to_utm(
    geojson_wgs84: Dict[str, Any],
    utm_zone: int = 17,
    output_path: str = None
) -> Dict[str, Any]:
    """
    Convert GeoJSON from WGS84 (lat/lon) to UTM Zone 17N.
    
    Args:
        geojson_wgs84: GeoJSON in WGS84
        utm_zone: UTM zone (default 17)
        output_path: Optional path to save converted GeoJSON
    
    Returns:
        GeoJSON in UTM coordinates
    """
    try:
        import pyproj
    except ImportError:
        print("  ⚠️  pyproj not installed. Install with: pip3 install --user pyproj")
        print("  ⚠️  For now, saving roads in WGS84 (lat/lon) format")
        print("  ⚠️  Rule 23 will need coordinate conversion or use WGS84 roads")
        if output_path:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(geojson_wgs84, f, indent=2)
        return geojson_wgs84
    
    try:
        
        # Create transformers
        wgs84 = pyproj.Proj(proj='latlong', ellps='WGS84')
        utm = pyproj.Proj(proj='utm', zone=utm_zone, ellps='WGS84')
        
        features_utm = []
        for feature in geojson_wgs84.get("features", []):
            geometry = feature.get("geometry", {})
            geom_type = geometry.get("type", "")
            coords_wgs84 = geometry.get("coordinates", [])
            
            if geom_type == "LineString":
                coords_utm = []
                for lon, lat in coords_wgs84:
                    x, y = pyproj.transform(wgs84, utm, lon, lat)
                    coords_utm.append([x, y])
                
                feature_utm = feature.copy()
                feature_utm["geometry"] = {
                    "type": "LineString",
                    "coordinates": coords_utm
                }
                features_utm.append(feature_utm)
        
        geojson_utm = create_feature_collection(features_utm, crs=f"EPSG:{32600 + utm_zone}")
        
        if output_path:
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(geojson_utm, f, indent=2)
            print(f"  ✓ Converted and saved to {output_path}")
        
        return geojson_utm
        
    except ImportError:
        print("  ⚠️  pyproj not installed. Install with: pip install pyproj")
        print("  ⚠️  Returning WGS84 GeoJSON (needs conversion before use)")
        return geojson_wgs84


def extract_roads_from_geojson(
    cable_geojson_path: str,
    ont_geojson_path: str = None,
    output_path: str = "test_inputs/small_area/roads.geojson",
    use_osm: bool = True
) -> Dict[str, Any]:
    """
    Extract roads for test area.
    
    Args:
        cable_geojson_path: Path to fiber cable GeoJSON (for bbox)
        ont_geojson_path: Optional path to ONT GeoJSON (for bbox)
        output_path: Where to save roads GeoJSON
        use_osm: If True, use OSM Overpass API (free). If False, use MapTiler (requires API key)
    
    Returns:
        GeoJSON FeatureCollection of roads
    """
    from utils.geojson_utils import load_geojson
    
    print("=" * 80)
    print("EXTRACTING ROADS FOR TEST AREA")
    print("=" * 80)
    print()
    
    # Load GeoJSON files to calculate bbox
    print("Calculating bounding box from input data...")
    cable_geojson = load_geojson(cable_geojson_path)
    bbox = calculate_bbox_from_geojson(cable_geojson)
    
    if ont_geojson_path and os.path.exists(ont_geojson_path):
        ont_geojson = load_geojson(ont_geojson_path)
        bbox_ont = calculate_bbox_from_geojson(ont_geojson)
        if bbox_ont:
            # Expand bbox to include ONTs
            bbox = (
                min(bbox[0], bbox_ont[0]),
                min(bbox[1], bbox_ont[1]),
                max(bbox[2], bbox_ont[2]),
                max(bbox[3], bbox_ont[3])
            )
    
    if not bbox:
        print("  ✗ Could not calculate bounding box")
        return None
    
    print(f"  ✓ Bounding box: ({bbox[0]:.2f}, {bbox[1]:.2f}) to ({bbox[2]:.2f}, {bbox[3]:.2f})")
    print()
    
    # Extract roads
    if use_osm:
        # Use OSM Overpass API (free, no key needed)
        roads_wgs84 = extract_roads_from_osm_overpass(bbox, output_path.replace(".geojson", "_wgs84.geojson"))
        
        if roads_wgs84:
            # Convert to UTM
            print("\nConverting roads from WGS84 to UTM Zone 17N...")
            roads_utm = convert_wgs84_to_utm(roads_wgs84, utm_zone=17, output_path=output_path)
            if roads_utm and roads_utm.get("crs"):
                # Conversion successful
                return roads_utm
            else:
                # Conversion failed (pyproj not installed), but keep WGS84 version
                # Rule 23 will handle conversion automatically
                print("  ⚠️  Keeping roads in WGS84 - Rule 23 will convert automatically")
                return roads_wgs84
    else:
        # TODO: Implement MapTiler API extraction
        print("  ⚠️  MapTiler API extraction not yet implemented")
        print("  💡 Using OSM Overpass API instead (free, no key needed)")
        return extract_roads_from_geojson(cable_geojson_path, ont_geojson_path, output_path, use_osm=True)
    
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract roads from OSM/MapTiler for Rule 23")
    parser.add_argument("--cables", required=True, help="Path to fiber cable GeoJSON")
    parser.add_argument("--onts", default=None, help="Path to ONT GeoJSON (optional)")
    parser.add_argument("--output", default="test_inputs/small_area/roads.geojson", help="Output path for roads GeoJSON")
    parser.add_argument("--osm", action="store_true", default=True, help="Use OSM Overpass API (default, free)")
    parser.add_argument("--maptiler", action="store_true", help="Use MapTiler API (requires API key)")
    
    args = parser.parse_args()
    
    extract_roads_from_geojson(
        args.cables,
        args.onts,
        args.output,
        use_osm=args.osm and not args.maptiler
    )
