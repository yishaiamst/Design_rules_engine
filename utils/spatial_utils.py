#!/usr/bin/env python3
"""
spatial_utils.py
-------------------------------------------------------------------------------
Spatial utilities for distance calculations, clustering, and geometric operations
-------------------------------------------------------------------------------
"""

import math
from typing import List, Tuple, Dict, Any, Optional

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    Args:
        lat1, lon1: First point (latitude, longitude in degrees)
        lat2, lon2: Second point (latitude, longitude in degrees)
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in km
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat/2)**2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * 
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def euclidean_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calculate Euclidean distance between two points.
    
    Args:
        x1, y1: First point coordinates
        x2, y2: Second point coordinates
        
    Returns:
        Distance in same units as input coordinates
    """
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def point_to_line_distance(point: Tuple[float, float], 
                          line_start: Tuple[float, float], 
                          line_end: Tuple[float, float]) -> float:
    """
    Calculate shortest distance from a point to a line segment.
    
    Args:
        point: Point coordinates (x, y)
        line_start: Line segment start (x, y)
        line_end: Line segment end (x, y)
        
    Returns:
        Distance from point to line segment
    """
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    # Vector from line_start to line_end
    dx = x2 - x1
    dy = y2 - y1
    
    # If line segment is a point
    if dx == 0 and dy == 0:
        return euclidean_distance(px, py, x1, y1)
    
    # Calculate t (parameter along line segment)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    
    # Closest point on line segment
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return euclidean_distance(px, py, closest_x, closest_y)

def point_to_linestring_distance(point: Tuple[float, float], 
                                 linestring: List[Tuple[float, float]]) -> Tuple[float, Tuple[float, float]]:
    """
    Calculate shortest distance from a point to a LineString.
    
    Args:
        point: Point coordinates (x, y)
        linestring: List of line segment coordinates
        
    Returns:
        Tuple of (distance, nearest_point_on_line)
    """
    if len(linestring) < 2:
        return (float('inf'), point)
    
    min_distance = float('inf')
    nearest_point = point
    
    for i in range(len(linestring) - 1):
        segment_start = linestring[i]
        segment_end = linestring[i + 1]
        
        distance = point_to_line_distance(point, segment_start, segment_end)
        
        if distance < min_distance:
            min_distance = distance
            # Calculate nearest point on this segment
            px, py = point
            x1, y1 = segment_start
            x2, y2 = segment_end
            
            dx = x2 - x1
            dy = y2 - y1
            
            if dx == 0 and dy == 0:
                nearest_point = segment_start
            else:
                t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
                nearest_point = (x1 + t * dx, y1 + t * dy)
    
    return (min_distance, nearest_point)

def calculate_centroid(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate centroid (center of mass) of a set of points.
    
    Args:
        points: List of point coordinates (x, y)
        
    Returns:
        Centroid coordinates (x, y)
    """
    if not points:
        return (0.0, 0.0)
    
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    
    return (sum_x / len(points), sum_y / len(points))

def calculate_bounding_box(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box of a set of points.
    
    Args:
        points: List of point coordinates (x, y)
        
    Returns:
        Tuple of (min_x, min_y, max_x, max_y)
    """
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    
    return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))

def calculate_diameter(points: List[Tuple[float, float]]) -> float:
    """
    Calculate maximum distance between any two points (diameter).
    
    Args:
        points: List of point coordinates (x, y)
        
    Returns:
        Maximum distance between any two points
    """
    if len(points) < 2:
        return 0.0
    
    max_distance = 0.0
    
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            distance = euclidean_distance(points[i][0], points[i][1], 
                                         points[j][0], points[j][1])
            max_distance = max(max_distance, distance)
    
    return max_distance

def simple_cluster(points: List[Tuple[float, float, Dict[str, Any]]], 
                   radius: float) -> List[List[int]]:
    """
    Simple distance-based clustering (DBSCAN-like).
    
    Args:
        points: List of points with properties (x, y, properties)
        radius: Clustering radius (same units as coordinates)
        
    Returns:
        List of clusters, each cluster is a list of point indices
    """
    if not points:
        return []
    
    n = len(points)
    visited = [False] * n
    clusters = []
    
    for i in range(n):
        if visited[i]:
            continue
        
        # Start new cluster
        cluster = [i]
        visited[i] = True
        
        # Find all points within radius
        to_check = [i]
        
        while to_check:
            current_idx = to_check.pop(0)
            current_point = points[current_idx]
            
            for j in range(n):
                if visited[j]:
                    continue
                
                other_point = points[j]
                distance = euclidean_distance(
                    current_point[0], current_point[1],
                    other_point[0], other_point[1]
                )
                
                if distance <= radius:
                    cluster.append(j)
                    visited[j] = True
                    to_check.append(j)
        
        clusters.append(cluster)
    
    return clusters



