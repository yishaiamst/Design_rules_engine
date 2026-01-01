#!/usr/bin/env python3
"""
geojson_utils.py
-------------------------------------------------------------------------------
Utilities for loading and saving GeoJSON files
-------------------------------------------------------------------------------
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple

def load_geojson(filepath: str) -> Dict[str, Any]:
    """
    Load GeoJSON file.
    
    Args:
        filepath: Path to GeoJSON file
        
    Returns:
        GeoJSON dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is invalid JSON
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"GeoJSON file not found: {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_geojson(data: Dict[str, Any], filepath: str) -> None:
    """
    Save GeoJSON to file.
    
    Args:
        data: GeoJSON dictionary
        filepath: Path to output file
    """
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def create_feature(geometry: Dict[str, Any], properties: Dict[str, Any], feature_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a GeoJSON feature.
    
    Args:
        geometry: Geometry dictionary (type, coordinates)
        properties: Feature properties
        feature_id: Optional feature ID
        
    Returns:
        GeoJSON feature dictionary
    """
    feature = {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties
    }
    
    if feature_id:
        feature["id"] = feature_id
    
    return feature

def create_feature_collection(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a GeoJSON FeatureCollection.
    
    Args:
        features: List of GeoJSON features
        
    Returns:
        GeoJSON FeatureCollection dictionary
    """
    return {
        "type": "FeatureCollection",
        "features": features
    }

def extract_points(geojson: Dict[str, Any]) -> List[Tuple[float, float, Dict[str, Any]]]:
    """
    Extract point coordinates and properties from GeoJSON.
    
    Args:
        geojson: GeoJSON dictionary
        
    Returns:
        List of tuples: (x, y, properties)
    """
    points = []
    
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                points.append((coords[0], coords[1], feature.get("properties", {})))
    
    return points

def extract_linestrings(geojson: Dict[str, Any]) -> List[Tuple[List[Tuple[float, float]], Dict[str, Any]]]:
    """
    Extract LineString coordinates and properties from GeoJSON.
    
    Args:
        geojson: GeoJSON dictionary
        
    Returns:
        List of tuples: (coordinates, properties)
    """
    linestrings = []
    
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
            linestrings.append((coords, props))
        elif geometry.get("type") == "MultiLineString":
            for line_coords in geometry.get("coordinates", []):
                linestrings.append((line_coords, props))
    
    return linestrings

def get_feature_by_id(geojson: Dict[str, Any], feature_id: str, id_field: str = "ID") -> Optional[Dict[str, Any]]:
    """
    Find feature by ID in properties.
    
    Args:
        geojson: GeoJSON dictionary
        feature_id: Feature ID to find
        id_field: Property field name containing ID
        
    Returns:
        Feature dictionary or None if not found
    """
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        if props.get(id_field) == feature_id or props.get(id_field.lower()) == feature_id:
            return feature
    return None



