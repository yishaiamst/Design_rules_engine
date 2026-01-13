# Rule 23: Infrastructure Constraint

## Problem

Connecting isolated cables can create paths that are not on actual roads, making it impossible to mount the cable on poles/structures. Also, connections can create loops/squares in the network.

## Solution

Added **infrastructure constraint** to ensure connecting cables follow existing infrastructure (roads):

1. **Check if connection path is near infrastructure**: The path from isolated cable endpoint to connection point must be within 100m of existing infrastructure cables
2. **Infrastructure cables represent roads**: Existing fiber cables in the network represent roads/paths where cables can be mounted
3. **Filter out connections not near infrastructure**: Only consider connections where the path is near infrastructure

## Selection Priority (Updated)

```
1. Avoid loops (reject if creates loop/square)
2. Near infrastructure (for mounting) - NEW
3. Closest distance (primary constraint)
4. Shorter path from OLT
5. Fewer FOSCs/terminals crossed
```

## Implementation

### `check_near_infrastructure()` Function

Checks if the connection path (from isolated endpoint to connection point) is within 100m of any existing infrastructure cable.

```python
def check_near_infrastructure(
    connection_point: Tuple[float, float],
    isolated_endpoint: Tuple[float, float],
    cables_geojson: Dict[str, Any],
    max_distance_m: float = 100.0
) -> Tuple[bool, float]:
    """
    Check if connection path is near existing infrastructure cables (roads for mounting).
    
    Returns:
        (is_near_infrastructure, min_distance_to_infrastructure)
    """
```

### Integration

- Added to `calculate_path_metrics_from_olt()` - now includes `near_infrastructure` and `infrastructure_distance_m` in metrics
- Used in candidate sorting - connections near infrastructure are preferred
- Filters out connections that would require mounting cables far from roads

## Which File to Use?

### `fiber_cable_updated_ids.geojson`
- **Purpose**: Cables after Phase 3d (ID assignment)
- **Use**: Base network with updated From_ID/To_ID
- **Status**: Before Rule 23 connections

### `fiber_cable_connected.geojson`
- **Purpose**: Cables after Rule 23 (isolated cable connections)
- **Use**: Final connected network
- **Status**: After Rule 23, may have extended cables
- **Note**: Should NOT create loops (if it does, loop detection needs fixing)

### Recommendation
- **For visualization**: Use `fiber_cable_connected.geojson` (most complete)
- **For analysis**: Use `fiber_cable_updated_ids.geojson` (before connections)
- **For final design**: Use `fiber cable.geojson` (sized cables from Phase 6)

## CRS Addition

All GeoJSON files now include CRS (Coordinate Reference System):
- Format: `EPSG:32617` (UTM Zone 17N)
- Ensures files display correctly on maps
- Added to all `create_feature_collection()` calls

## Example: Loop Detection

**Problem**: Connecting `96FOC/UNKNOWN/T0000005` and `48FOC/T0000005/UNKNOWN` to `48FOC/F1000406/F1000394` creates a loop.

**Solution**: Enhanced loop detection now:
1. Checks if connection point is shared by both cables
2. Traces path from other endpoints through network
3. Rejects connection if path exists (would create loop)

## Benefits

1. **Realistic paths**: Connections follow actual roads/infrastructure
2. **Mountable cables**: Cables can be mounted on poles/structures
3. **No loops**: Prevents creating closed paths/squares
4. **Map compatibility**: All files include CRS for proper display
