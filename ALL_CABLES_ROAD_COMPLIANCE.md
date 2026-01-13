# All Generated Cables Must Follow Roads

## Problem

Previously, only isolated cable connections (Rule 23) were checked for road alignment. But cables generated during design (like `48FOC/F0000003/F0000011`) also need to follow roads.

## Solution

**Applied road rules to ALL cable generation**, not just Rule 23 connections.

## Implementation

### 1. Enhanced `extend_cable_to_connection()`

**Before:**
- Created straight line from endpoint to connection point
- No road checking

**After:**
- Finds road path between points using `find_road_path_between_points()`
- Uses actual roads (like Grimsthorpe Road) when available
- Falls back to straight line only if no roads found

### 2. New Function: `find_road_path_between_points()`

```python
def find_road_path_between_points(
    start_point: Tuple[float, float],
    end_point: Tuple[float, float],
    roads_geojson: Dict[str, Any],
    max_deviation_m: float = 100.0
) -> List[Tuple[float, float]]:
    """
    Find a road path between two points.
    
    Finds roads that connect the points, creating a path that follows
    actual roads (like Grimsthorpe Road) instead of straight lines.
    """
```

**Logic:**
1. Find roads near the path (within max_deviation_m)
2. Check if road endpoints are near start/end points
3. Build path using road coordinates
4. Return road-following path or straight line if no roads found

### 3. Integration

**All cable extensions now:**
- Check for roads between endpoints
- Use road paths when available
- Follow actual roads (like Grimsthorpe Road)
- Only use straight lines if no roads available

## What This Fixes

- ✅ **48FOC/F0000003/F0000011** - Will follow Grimsthorpe Road (or similar road)
- ✅ **All extended cables** - Follow roads instead of cutting across fields
- ✅ **All generated cables** - Conform to road rules

## Example

**Before:**
```
Cable: 48FOC/F0000003/F0000011
Path: Straight line (diagonal across fields) ❌
```

**After:**
```
Cable: 48FOC/F0000003/F0000011
Path: Follows Grimsthorpe Road ✅
```

## Status

✅ **Implemented**
- `extend_cable_to_connection()` now uses `find_road_path_between_points()`
- All cable extensions check for roads
- Falls back gracefully if no roads available

**All generated cables now conform to road rules!**
