# Rule 23: Connect Isolated Fiber Cables

## Problem Statement

User input may contain isolated fiber cables that are not connected to the main network. These isolated cables create "islands" where ONTs cannot be served by OLTs.

**Example**: Cable `48FOC/F0000961/UNKNOWN` has one endpoint at FOSC F0000961 but the other endpoint (UNKNOWN) is not connected to any other cable or FOSC, making it an isolated segment.

## Solution

**Rule 23** detects isolated cables and connects them to the nearest cable or FOSC by:
1. Extending the isolated cable to the connection point
2. Placing a FOSC at the new intersection
3. Ensuring all cables are part of a connected network

## Implementation

**File**: `phases/phase3e_connect_isolated_cables.py`

**Key Functions**:
- `detect_isolated_cables()` - Detects cables that are not connected to the network
- `find_nearest_connection_point()` - Finds nearest cable or FOSC to connect to
- `extend_cable_to_connection()` - Extends isolated cable to connection point
- `connect_isolated_cables()` - Main function that orchestrates the process

## Detection Criteria

A cable is considered isolated if:
1. **Neither endpoint connects to FOSC** (within 50m tolerance)
2. **Neither endpoint is shared with other cables** (within 50m tolerance)
3. **OR has UNKNOWN endpoint(s)** - one end may connect but other doesn't

For cables with UNKNOWN endpoints:
- If FROM is UNKNOWN: Check if start point is isolated
- If TO is UNKNOWN: Check if end point is isolated
- Cable is isolated if the UNKNOWN endpoint is isolated

## Connection Process

1. **Find Nearest Connection Point**:
   - Search for nearest FOSC (preferred)
   - Search for nearest cable
   - Default search distance: 2000m (2km)
   - For UNKNOWN endpoints: Extended search up to 5km

2. **Extend Cable**:
   - Determine which endpoint is closer to connection point
   - Add connection point to cable coordinates
   - Extend from the appropriate endpoint

3. **Create FOSC**:
   - Generate new FOSC ID (F0000001, F0000002, etc.)
   - Place FOSC at connection point
   - Add connected cables to FOSC's `connected_cables` list
   - If connecting to existing FOSC, merge instead of creating new one

## Integration

**Phase Order**: Phase 3e runs after:
- Phase 3d: Cable ID Updates (Rule 22)
- Before Phase 6: Cable Sizing

This ensures:
- Cable IDs are updated first
- Isolated cables are connected before sizing
- New FOSCs are included in sizing calculations

## Test Results

**Small Area Test** (5km radius):
- **Isolated cables found**: 4
- **Connected**: 3 cables
- **New FOSCs created**: 3
- **Connections made**:
  - `144FOC/UNKNOWN/T0000003` → FOSC F0000001
  - `48FOC/T0000005/UNKNOWN` → FOSC F0000002
  - `96FOC/UNKNOWN/T0000005` → FOSC F0000003

**One cable** (`48FOC/F1000509/T1002415`) could not be connected within 2km - may need larger search radius or is truly isolated area.

## Output Files

- `fiber_cable_connected.geojson` - Cables with extensions applied
- `isolated_cable_connection_summary.json` - Summary of connections made
- Updated `rules_optimized_foscs.json` - Includes new FOSCs created

## Configuration

**Parameters** (in `connect_isolated_cables()`):
- `tolerance_m`: 50.0m - Distance tolerance for detecting connections
- `max_connection_distance_m`: 2000.0m (2km) - Maximum distance to extend cable
- Extended search: Up to 5km for UNKNOWN endpoints

## Example

**Before**:
```
Cable: 48FOC/F0000961/UNKNOWN
- Start: F0000961 (FOSC) ✓
- End: UNKNOWN (not connected) ✗
- Status: Isolated
```

**After**:
```
Cable: 48FOC/F0000961/F0000123 (extended)
- Start: F0000961 (FOSC) ✓
- End: F0000123 (new FOSC at connection point) ✓
- Extension: 850m to nearest cable
- Status: Connected to network
```

## Notes

- Rule runs automatically in the design generation pipeline
- New FOSCs are added to the FOSC list and included in subsequent phases
- Extended cables maintain original path with connection point appended
- Connection points are placed at the intersection with nearest cable/FOSC
- If no connection found within search distance, cable is kept as-is (may need manual review)
