# Rule 23: Road Alignment Enhancement

## Problem

The current implementation connects isolated cables using the shortest path, which can result in cross-country routing that doesn't follow roads. This makes it impossible to mount cables on poles/structures.

**Example from user:**
- **Red lines**: Cross-country paths, not near roads ❌
- **Blue line**: Directly on a road ✅

## Solution

Enhanced `check_near_infrastructure()` to verify the **ENTIRE connection path** follows existing infrastructure cables (which represent roads), not just the endpoints.

## Implementation

### Enhanced Infrastructure Check

1. **Path Sampling**: Sample points every 50m along the connection path
2. **Alignment Check**: For each sample point, check distance to nearest infrastructure cable
3. **Alignment Ratio**: Calculate what fraction of the path is near infrastructure
4. **Threshold**: Require at least 80% of path to be within 50m of infrastructure

### Key Changes

```python
def check_near_infrastructure(
    connection_point: Tuple[float, float],
    isolated_endpoint: Tuple[float, float],
    cables_geojson: Dict[str, Any],
    max_distance_m: float = 50.0,  # Stricter: 50m (was 100m)
    path_alignment_threshold: float = 0.8  # 80% of path must follow roads
) -> Tuple[bool, float, float]:
    """
    Returns:
        (is_near_infrastructure, min_distance, path_alignment_ratio)
        - path_alignment_ratio: 0.0 to 1.0 (fraction of path following roads)
    """
```

### Selection Priority (Updated)

```
1. Avoid loops
2. Near infrastructure (80%+ of path follows roads) - ENHANCED
3. Path alignment ratio (higher = better) - NEW
4. Closest distance
5. Shorter path from OLT
6. Fewer FOSCs/terminals crossed
```

### Filtering

- **Before**: Only checked if endpoints were within 100m
- **After**: Requires 80%+ of entire path to be within 50m of infrastructure
- **Result**: Rejects cross-country paths, accepts road-aligned paths

## Example Output

```
Processing isolated cable: 48FOC/T0000005/UNKNOWN
  Selected: cable (2036.2m, path: 2101m, crossings: 0) [closest] (85% on roads)
    Target: 96FOC/F1000391/F1000397
```

If path doesn't follow roads:
```
  ⚠️  Connection path is 245.3m from nearest infrastructure, 35% aligned (may not be mountable)
```

## Benefits

1. **Realistic routing**: Connections follow actual roads
2. **Mountable cables**: Cables can be mounted on poles/structures
3. **Rejects cross-country**: Prevents paths cutting across fields/forests
4. **Prioritizes road-aligned**: Blue line (on road) preferred over red line (cross-country)

## Data Requirements

- **Input**: Existing infrastructure cables (represent roads)
- **Assumption**: Infrastructure cables follow roads
- **Future**: Could add explicit road data if available
