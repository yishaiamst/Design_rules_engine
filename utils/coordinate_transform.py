#!/usr/bin/env python3
"""
Coordinate Transformation Utilities
Converts between projected coordinate systems and WGS84 (EPSG:4326)
"""

try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    # Fallback: Manual UTM to WGS84 conversion
    import math


def detect_coordinate_system(coords):
    """
    Detect likely coordinate system from coordinates.
    Returns EPSG code or None.
    """
    if not coords or len(coords) < 2:
        return None
    
    x, y = coords[0], coords[1]
    
    # WGS84 bounds: lon -180 to 180, lat -90 to 90
    if -180 <= x <= 180 and -90 <= y <= 90:
        return 4326  # WGS84
    
    # UTM Zone 17N (EPSG:32617) - based on original data files
    # Coordinates in range: 300000-800000 (easting), 4000000-6000000 (northing)
    if 300000 <= x <= 800000 and 4000000 <= y <= 6000000:
        return 32617  # UTM Zone 17N (confirmed from original GeoJSON files)
    
    return None


def utm_to_latlon_manual(easting, northing, zone=17, northern=True):
    """
    Manual UTM to Lat/Lon conversion (simplified, approximate).
    For accurate conversion, use pyproj.
    Based on UTM Zone 17N (EPSG:32617) for Ontario, Canada.
    
    UTM Zone 17N parameters:
    - Central meridian: -81° (zone 17 = -180 + (17-1)*6 + 3 = -81)
    - False easting: 500000m
    - False northing: 0m (northern hemisphere)
    
    Reference: Manitoulin Island ~45.79°N, 82.25°W
    UTM for Manitoulin: ~400000-450000 easting, 5060000-5080000 northing
    """
    import math
    
    # More accurate UTM to Lat/Lon conversion
    k0 = 0.9996  # UTM scale factor
    a = 6378137.0  # WGS84 semi-major axis (meters)
    e2 = 0.00669438  # WGS84 first eccentricity squared
    e = math.sqrt(e2)  # First eccentricity
    
    # Remove false easting and northing
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    
    # Calculate latitude
    m = y / k0
    mu = m / (a * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))
    
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    J1 = 3*e1/2 - 27*e1**3/32
    J2 = 21*e1**2/16 - 55*e1**4/32
    J3 = 151*e1**3/96
    J4 = 1097*e1**4/512
    
    fp = mu + J1*math.sin(2*mu) + J2*math.sin(4*mu) + J3*math.sin(6*mu) + J4*math.sin(8*mu)
    
    # Calculate longitude
    e_2 = e2 / (1 - e2)
    C1 = e_2 * math.cos(fp)**2
    T1 = math.tan(fp)**2
    N1 = a / math.sqrt(1 - e2 * math.sin(fp)**2)
    R1 = a * (1 - e2) / (1 - e2 * math.sin(fp)**2)**1.5
    D = x / (N1 * k0)
    
    lat_rad = fp - (N1 * math.tan(fp) / R1) * (D**2/2 - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*e_2)*D**4/24 + (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*e_2 - 3*C1**2)*D**6/720)
    
    central_meridian_rad = math.radians(-81.0)  # Zone 17N
    lon_rad = central_meridian_rad + (D - (1 + 2*T1 + C1)*D**3/6 + (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*e_2 + 24*T1**2)*D**5/120) / math.cos(fp)
    
    lat = math.degrees(lat_rad)
    lon = math.degrees(lon_rad)
    
    return [lon, lat]  # Return as [lon, lat] for GeoJSON


def transform_to_wgs84(coords, source_epsg=None):
    """
    Transform coordinates to WGS84 (EPSG:4326).
    
    Args:
        coords: List of [x, y] or (x, y) coordinates
        source_epsg: Source EPSG code (if None, will try to detect)
    
    Returns:
        Transformed coordinates as [lon, lat]
    """
    if source_epsg is None:
        source_epsg = detect_coordinate_system(coords)
        if source_epsg is None:
            # Assume already WGS84
            return coords
    
    if source_epsg == 4326:
        # Already WGS84
        return coords
    
    x, y = coords[0], coords[1]
    
    if PYPROJ_AVAILABLE:
        try:
            transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:4326", always_xy=True)
            lon, lat = transformer.transform(x, y)
            return [lon, lat]
        except Exception as e:
            print(f"Warning: pyproj transformation failed: {e}, using manual conversion")
    
    # Fallback: Manual UTM conversion for Zone 17N
    if source_epsg == 32617:
        try:
            return utm_to_latlon_manual(x, y, zone=17, northern=True)
        except Exception as e:
            print(f"Warning: Manual UTM conversion failed: {e}")
            return coords
    
    # If we can't transform, return as-is with warning
    print(f"Warning: Cannot transform from EPSG:{source_epsg} to WGS84. Coordinates may be incorrect.")
    return coords


def transform_geojson_to_wgs84(geojson, source_epsg=None):
    """
    Transform all coordinates in a GeoJSON to WGS84.
    
    Args:
        geojson: GeoJSON dictionary
        source_epsg: Source EPSG code (if None, will try to detect from first feature)
    
    Returns:
        Transformed GeoJSON
    """
    # Always try to transform, even without pyproj (will use manual conversion)
    
    # Detect source CRS from first feature if not provided
    if source_epsg is None:
        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])
            if coords:
                if geometry.get("type") == "Point":
                    source_epsg = detect_coordinate_system(coords)
                elif geometry.get("type") == "LineString" and len(coords) > 0:
                    source_epsg = detect_coordinate_system(coords[0])
                elif geometry.get("type") == "MultiLineString" and len(coords) > 0:
                    if len(coords[0]) > 0:
                        source_epsg = detect_coordinate_system(coords[0][0])
                break
    
    if source_epsg is None or source_epsg == 4326:
        return geojson
    
    # Transform all coordinates
    def transform_coords(coords, geom_type):
        if geom_type == "Point":
            return transform_to_wgs84(coords, source_epsg)
        elif geom_type == "LineString":
            return [transform_to_wgs84(coord, source_epsg) for coord in coords]
        elif geom_type == "MultiLineString":
            return [[transform_to_wgs84(coord, source_epsg) for coord in line] for line in coords]
        return coords
    
    transformed_features = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])
        
        if coords:
            transformed_coords = transform_coords(coords, geom_type)
            geometry["coordinates"] = transformed_coords
        
        transformed_features.append({
            **feature,
            "geometry": geometry
        })
    
    return {
        **geojson,
        "features": transformed_features,
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:EPSG::4326"
            }
        }
    }
