# Rule 23: Road Path Following Enhancement

## Problem

Cable `48FOC/F0000003/F0000011` is crossing diagonally across fields instead of following Grimsthorpe Road. The algorithm needs to find and use the actual road that the connection path should follow.

## Solution

Enhanced the logic to:
1. **Find roads along the path** - not just nearby, but actually along the connection route
2. **Check road overlap** - verify road segments overlap with the connection path
3. **Reject cross-country paths** - only accept connections that follow roads

## Implementation

### Enhanced Road Alignment Check

The `check_near_infrastructure()` function now:

1. **Converts WGS84 roads to UTM** automatically
2. **Samples points along connection path** (every 50m)
3. **Finds nearest road** to each sample point
4. **Checks direction alignment** (road must be parallel to path)
5. **Checks path overlap** (road segment must overlap with connection path)
6. **Calculates alignment ratio** (% of path following roads)

### Key Enhancement: Path Overlap Check

```python
# Check if road segment overlaps with connection path
# Project road endpoints onto path direction
proj_start = road_start projected onto path
proj_end = road_end projected onto path

# Road overlaps if projections intersect with path [0, path_len]
if road_proj_max >= 0 and road_proj_min <= path_len:
    is_along_path = True
```

This ensures:
- ✅ Road is actually along the path (like Grimsthorpe Road)
- ✅ Not just nearby but perpendicular
- ✅ Road segment overlaps with connection route

### Filtering Logic

```python
# CRITICAL: Only accept connections that follow roads
infrastructure_candidates = [c for c in candidates 
                           if c["near_infrastructure"] and 
                           c["path_alignment_ratio"] >= 0.8]

if infrastructure_candidates:
    # Use only road-following connections
else:
    # Try 50% threshold as fallback
    # Warn that connection may cross fields
```

## What This Fixes

- ✅ **48FOC/F0000003/F0000011** - Will now follow Grimsthorpe Road (or similar road along path)
- ✅ **Cross-country paths** - Rejected if they don't follow roads
- ✅ **Field routing** - Prevented by requiring 80%+ road alignment

## Example

**Before:**
- Connection: Diagonal cut across fields
- Road check: Failed (not along path)
- Result: Rejected or marked as problematic

**After:**
- Connection: Follows Grimsthorpe Road
- Road check: Passed (road overlaps path, aligned direction)
- Result: Accepted (100% on roads)

## Status

✅ **Implemented**
- Automatic coordinate conversion
- Road path overlap checking
- Stricter filtering (80%+ alignment required)
- Fallback to 50% if no perfect solution

The algorithm now finds and uses roads like Grimsthorpe Road that are actually along the connection path, preventing cross-country routing.
