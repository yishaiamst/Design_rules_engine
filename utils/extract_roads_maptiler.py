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
        from pyproj import Transformer
        transformer = Transformer.from_crs(f"EPSG:326{zone}", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(easting, northing)
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


def calculate_bbox_from_center(
    center_lat: float,
    center_lon: float,
    radius_m: float,
    utm_zone: int = 17
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box from center point and radius.
    
    Args:
        center_lat: Center latitude in degrees
        center_lon: Center longitude in degrees
        radius_m: Radius in meters
        utm_zone: UTM zone for conversion
    
    Returns:
        (min_x, min_y, max_x, max_y) in UTM coordinates
    """
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:326{utm_zone}", always_xy=True)
        center_x, center_y = transformer.transform(center_lon, center_lat)
        
        # Calculate bbox (square around center)
        min_x = center_x - radius_m
        max_x = center_x + radius_m
        min_y = center_y - radius_m
        max_y = center_y + radius_m
        
        return (min_x, min_y, max_x, max_y)
    except ImportError:
        # Fallback: approximate conversion
        # 1 degree lat ≈ 111,000m, 1 degree lon ≈ 78,000m at this latitude
        lat_offset = radius_m / 111000.0
        lon_offset = radius_m / (111000.0 * math.cos(math.radians(center_lat)))
        
        min_lat = center_lat - lat_offset
        max_lat = center_lat + lat_offset
        min_lon = center_lon - lon_offset
        max_lon = center_lon + lon_offset
        
        # Convert to UTM (approximate)
        # This is rough - should use pyproj for accuracy
        print("  ⚠️  pyproj not installed - using approximate conversion")
        print("  💡 Install with: pip3 install --user pyproj")
        
        # Rough UTM conversion
        center_lon_approx = -82.0  # Approximate for Zone 17
        center_lat_approx = 45.7   # Approximate for Ontario
        
        # Convert lat/lon bbox to UTM (approximate)
        min_x = 500000 + (min_lon - center_lon_approx) * (111000.0 * math.cos(math.radians(center_lat)))
        max_x = 500000 + (max_lon - center_lon_approx) * (111000.0 * math.cos(math.radians(center_lat)))
        min_y = 5000000 + (min_lat - center_lat_approx) * 111000.0
        max_y = 5000000 + (max_lat - center_lat_approx) * 111000.0
        
        return (min_x, min_y, max_x, max_y)


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
    
    # Overpass API endpoints (retry on failures)
    overpass_urls = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter",
        "https://overpass.osm.ch/api/interpreter",
    ]
    
    # Query for all roads (highways) - expanded to include more road types
    full_query = f"""
    [out:json][timeout:25];
    (
      way["highway"~"^(primary|secondary|tertiary|unclassified|residential|service|track|path|living_street)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """
    # Reduced query for retry if full query times out
    reduced_query = f"""
    [out:json][timeout:25];
    (
      way["highway"~"^(primary|secondary|tertiary|unclassified|residential)$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """
    
    print(f"  Querying OSM for roads in bbox: ({min_lat:.6f}, {min_lon:.6f}) to ({max_lat:.6f}, {max_lon:.6f})")
    
    data = None
    last_error = None
    for query in (full_query, reduced_query):
        for overpass_url in overpass_urls:
            try:
                # Use urllib instead of requests (no external dependency)
                req = Request(overpass_url, data=query.encode('utf-8'), headers={'Content-Type': 'application/x-www-form-urlencoded'})
                with urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))
                break
            except Exception as e:
                last_error = e
                print(f"  ⚠️  Overpass error ({overpass_url}): {e}")
                continue
        if data is not None:
            break

    if data is None:
        print(f"  ✗ Network error extracting roads: {last_error}")
        print("  💡 Check internet connection or try again later")
        return None
        
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


def _tile_coords_to_lonlat(
    x: float,
    y: float,
    bounds_m: Tuple[float, float, float, float],
    extent: int,
    transformer
) -> Tuple[float, float]:
    """
    Convert vector-tile local coords to lon/lat.
    Vector tiles are in WebMercator tile space; interpolate in meters then transform.
    """
    west_m, south_m, east_m, north_m = bounds_m
    xm = west_m + (east_m - west_m) * (x / extent)
    ym = north_m - (north_m - south_m) * (y / extent)
    lon, lat = transformer.transform(xm, ym)
    return lon, lat


def extract_roads_from_maptiler(
    center_lat: float,
    center_lon: float,
    radius_m: float,
    output_path: str,
    api_key: str,
    tileset: str = "v3",
    zoom: int = 14
) -> Dict[str, Any]:
    """
    Extract roads from MapTiler vector tiles and save as GeoJSON (WGS84).
    """
    try:
        import mercantile
        from mapbox_vector_tile import decode
    except ImportError:
        print("  ✗ MapTiler dependencies missing. Install in venv:")
        print("    python3 -m venv .venv && ./.venv/bin/python -m pip install mapbox-vector-tile mercantile")
        return create_feature_collection([], crs="EPSG:4326")

    lat_offset = radius_m / 111000.0
    lon_offset = radius_m / (111000.0 * math.cos(math.radians(center_lat)))
    min_lat = center_lat - lat_offset
    max_lat = center_lat + lat_offset
    min_lon = center_lon - lon_offset
    max_lon = center_lon + lon_offset

    tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, zoom))
    print(f"  Fetching {len(tiles)} tiles from MapTiler (zoom {zoom})")

    features = []
    seen = set()
    for tile in tiles:
        url = f"https://api.maptiler.com/tiles/{tileset}/{tile.z}/{tile.x}/{tile.y}.pbf?key={api_key}"
        try:
            with urlopen(url, timeout=30) as resp:
                data = resp.read()
        except Exception as e:
            print(f"  ⚠️  MapTiler tile error {tile.z}/{tile.x}/{tile.y}: {e}")
            continue

        decoded = decode(data)
        extent = 4096
        from pyproj import Transformer as _Transformer
        merc_to_wgs = _Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

        for layer_name, layer in decoded.items():
            if "transportation" not in layer_name and "road" not in layer_name:
                continue
            extent = layer.get("extent", extent)
            for feat in layer.get("features", []):
                geom = feat.get("geometry")
                props = feat.get("properties", {})
                if not geom or geom.get("type") not in ("LineString", "MultiLineString"):
                    continue
                bounds_m = mercantile.xy_bounds(tile)
                if geom["type"] == "LineString":
                    coords = [
                        list(_tile_coords_to_lonlat(p[0], p[1], bounds_m, extent, merc_to_wgs))
                        for p in geom["coordinates"]
                    ]
                    coord_key = tuple((round(c[0], 7), round(c[1], 7)) for c in coords)
                else:
                    coords = [
                        [list(_tile_coords_to_lonlat(p[0], p[1], bounds_m, extent, merc_to_wgs)) for p in line]
                        for line in geom["coordinates"]
                    ]
                    coord_key = tuple(
                        tuple((round(c[0], 7), round(c[1], 7)) for c in line)
                        for line in coords
                    )
                if coord_key in seen:
                    continue
                seen.add(coord_key)
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": geom["type"],
                        "coordinates": coords
                    },
                    "properties": {
                        "highway": props.get("class") or props.get("type") or props.get("brunnel", "unknown"),
                        "name": props.get("name", ""),
                        "source": "maptiler",
                        "layer": layer_name,
                    }
                })

    geojson = create_feature_collection(features, crs="EPSG:4326")
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  ✓ Saved to {output_path}")
    return geojson


def extract_roads_from_osm_tiled(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    output_path: str,
    step_deg: float = 0.05
) -> Dict[str, Any]:
    """
    Extract OSM roads by tiling the bbox to avoid Overpass timeouts.
    """
    overpass_urls = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
        "https://overpass.osm.ch/api/interpreter",
    ]

    features = []
    seen_ids = set()

    lat = min_lat
    tile_idx = 0
    while lat < max_lat:
        next_lat = min(lat + step_deg, max_lat)
        lon = min_lon
        while lon < max_lon:
            next_lon = min(lon + step_deg, max_lon)
            tile_idx += 1
            query = f"""
            [out:json][timeout:25];
            (
              way["highway"~"^(primary|secondary|tertiary|unclassified|residential|service|track|path|living_street)$"]({lat},{lon},{next_lat},{next_lon});
            );
            out geom;
            """
            data = None
            for overpass_url in overpass_urls:
                try:
                    req = Request(overpass_url, data=query.encode('utf-8'), headers={'Content-Type': 'application/x-www-form-urlencoded'})
                    with urlopen(req, timeout=30) as response:
                        data = json.loads(response.read().decode('utf-8'))
                    break
                except Exception:
                    continue
            if data:
                for element in data.get("elements", []):
                    if element.get("type") == "way" and "geometry" in element:
                        osm_id = element.get("id")
                        if osm_id in seen_ids:
                            continue
                        seen_ids.add(osm_id)
                        coords = [[pt.get("lon"), pt.get("lat")] for pt in element.get("geometry", [])]
                        if len(coords) >= 2:
                            features.append({
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": coords
                                },
                                "properties": {
                                    "highway": element.get("tags", {}).get("highway", "unknown"),
                                    "name": element.get("tags", {}).get("name", ""),
                                    "osm_id": osm_id
                                }
                            })
            lon = next_lon
        lat = next_lat

    geojson = create_feature_collection(features, crs="EPSG:4326")
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)
    print(f"  ✓ Saved to {output_path} ({len(features)} features)")
    return geojson


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
        from pyproj import Transformer
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
        features_utm = []
        transformer = Transformer.from_crs("EPSG:4326", f"EPSG:326{utm_zone}", always_xy=True)
        for feature in geojson_wgs84.get("features", []):
            geometry = feature.get("geometry", {})
            geom_type = geometry.get("type", "")
            coords_wgs84 = geometry.get("coordinates", [])
            
            if geom_type == "LineString":
                coords_utm = []
                for lon, lat in coords_wgs84:
                    x, y = transformer.transform(lon, lat)
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
        print("  ✗ MapTiler extraction for GeoJSON bbox not supported yet.")
        return None
    
    return None


def extract_roads_from_coordinates(
    center_lat: float,
    center_lon: float,
    radius_m: float = 5000.0,
    output_path: str = "test_inputs/small_area/roads.geojson",
    utm_zone: int = 17,
    use_osm: bool = True,
    maptiler_key: Optional[str] = None,
    maptiler_tileset: str = "v3",
    maptiler_zoom: int = 14
) -> Dict[str, Any]:
    """
    Extract roads around a center point with specified radius.
    
    Args:
        center_lat: Center latitude in degrees
        center_lon: Center longitude in degrees
        radius_m: Radius in meters (default 5000m = 5km)
        output_path: Where to save roads GeoJSON
        utm_zone: UTM zone for coordinate conversion
        use_osm: If True, use OSM Overpass API (free). If False, use MapTiler (requires API key)
    
    Returns:
        GeoJSON FeatureCollection of roads
    """
    print("=" * 80)
    print("EXTRACTING ROADS FROM COORDINATES")
    print("=" * 80)
    print()
    print(f"Center: ({center_lat:.6f}, {center_lon:.6f})")
    print(f"Radius: {radius_m:.0f}m ({radius_m/1000:.1f}km)")
    print()
    
    # Calculate bounding box from center and radius
    print("Calculating bounding box...")
    bbox = calculate_bbox_from_center(center_lat, center_lon, radius_m, utm_zone)
    print(f"  ✓ Bounding box: ({bbox[0]:.2f}, {bbox[1]:.2f}) to ({bbox[2]:.2f}, {bbox[3]:.2f})")
    print()
    
    # Extract roads
    if use_osm:
        # Use OSM Overpass API (free, no key needed)
        roads_wgs84 = extract_roads_from_osm_overpass(bbox, output_path.replace(".geojson", "_wgs84.geojson"), utm_zone)
        
        if not roads_wgs84 or not roads_wgs84.get("features"):
            # Fallback to tiled Overpass queries (smaller bbox chunks)
            min_lat, min_lon = utm_to_latlon(bbox[0], bbox[1], utm_zone)
            max_lat, max_lon = utm_to_latlon(bbox[2], bbox[3], utm_zone)
            print("  ⚠️  Falling back to tiled OSM queries...")
            roads_wgs84 = extract_roads_from_osm_tiled(
                min_lat, min_lon, max_lat, max_lon,
                output_path.replace(".geojson", "_wgs84.geojson")
            )

        if roads_wgs84:
            # Convert to UTM
            print("\nConverting roads from WGS84 to UTM Zone 17N...")
            roads_utm = convert_wgs84_to_utm(roads_wgs84, utm_zone=utm_zone, output_path=output_path)
            if roads_utm and roads_utm.get("crs"):
                # Conversion successful
                return roads_utm
            else:
                # Conversion failed (pyproj not installed), but keep WGS84 version
                # Rule 23 will handle conversion automatically
                print("  ⚠️  Keeping roads in WGS84 - Rule 23 will convert automatically")
                return roads_wgs84
    else:
        if not maptiler_key:
            maptiler_key = os.environ.get("MAPTILER_API_KEY")
        if not maptiler_key:
            print("  ✗ MAPTILER_API_KEY not set. Use --maptiler-key or set env var.")
            return None
        roads_wgs84 = extract_roads_from_maptiler(
            center_lat,
            center_lon,
            radius_m,
            output_path.replace(".geojson", "_wgs84.geojson"),
            maptiler_key,
            tileset=maptiler_tileset,
            zoom=maptiler_zoom
        )
        if roads_wgs84:
            print("\nConverting roads from WGS84 to UTM Zone 17N...")
            roads_utm = convert_wgs84_to_utm(roads_wgs84, utm_zone=utm_zone, output_path=output_path)
            if roads_utm and roads_utm.get("crs"):
                return roads_utm
            print("  ⚠️  Keeping roads in WGS84 - Rule 23 will convert automatically")
            return roads_wgs84
    
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract roads from OSM/MapTiler for Rule 23")
    
    # Two modes: from GeoJSON files or from coordinates
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cables", help="Path to fiber cable GeoJSON (for bbox calculation)")
    group.add_argument("--center", nargs=2, metavar=("LAT", "LON"), type=float, 
                      help="Center coordinates (lat, lon) for road extraction")
    
    parser.add_argument("--onts", default=None, help="Path to ONT GeoJSON (optional, used with --cables)")
    parser.add_argument("--radius", type=float, default=5000.0, 
                       help="Radius in meters for --center mode (default: 5000m = 5km)")
    parser.add_argument("--output", default="test_inputs/small_area/roads.geojson", 
                       help="Output path for roads GeoJSON")
    parser.add_argument("--osm", action="store_true", default=True, 
                       help="Use OSM Overpass API (default, free)")
    parser.add_argument("--maptiler", action="store_true", 
                       help="Use MapTiler API (requires API key)")
    parser.add_argument("--maptiler-key", default=None,
                       help="MapTiler API key (or set MAPTILER_API_KEY)")
    parser.add_argument("--maptiler-tileset", default="v3",
                       help="MapTiler tileset (default: v3)")
    parser.add_argument("--maptiler-zoom", type=int, default=14,
                       help="MapTiler zoom level for vector tiles")
    
    args = parser.parse_args()
    
    if args.center:
        # Extract from coordinates
        center_lat, center_lon = args.center
        extract_roads_from_coordinates(
            center_lat,
            center_lon,
            radius_m=args.radius,
            output_path=args.output,
            use_osm=args.osm and not args.maptiler,
            maptiler_key=args.maptiler_key,
            maptiler_tileset=args.maptiler_tileset,
            maptiler_zoom=args.maptiler_zoom
        )
    else:
        # Extract from GeoJSON files
        extract_roads_from_geojson(
            args.cables,
            args.onts,
            args.output,
            use_osm=args.osm and not args.maptiler
        )
