# Rule 23 Algorithm Review and Data Locations

## Algorithm Improvements

The algorithm has been enhanced to properly handle cases like `48FOC/F1000509/T1002415` connecting to `F1000390`:

### 1. **FOSC Position Extraction from Cable IDs**
- Extracts FOSC positions from cable IDs (e.g., `144FOC/F1000390/F1000502` → F1000390 at start point)
- Handles both LineString and MultiLineString geometries
- Creates a map of FOSC ID → position for connection targeting

### 2. **FOSC Prioritization**
- **FOSCs are preferred over cables** even if a cable point is slightly closer
- FOSCs represent known network nodes, cables are just paths
- Only uses cable if FOSC is much farther (>1.5x cable distance)

### 3. **Endpoint Exclusion**
- Excludes FOSCs that are already at the isolated cable's endpoints
- Prevents connecting to the same FOSC the cable already connects to
- Example: `48FOC/F1000509/T1002415` excludes F1000509 (already at start)

### 4. **Extended Search Distance**
- Default: 3km (increased from 2km)
- For UNKNOWN endpoints: Extended search up to 5km
- Handles cases where nearest connection is farther away

### 5. **MultiLineString Handling**
- Properly extracts coordinates from MultiLineString geometries
- Handles nested coordinate structures
- Correctly identifies start and end points

## Connection Logic Flow

```
1. Detect isolated cables
   - Cables not connected to FOSCs or other cables
   - Cables with UNKNOWN endpoints

2. For each isolated cable:
   a. Extract FOSC positions from all cable IDs
   b. Exclude FOSCs already at cable endpoints
   c. Find nearest FOSC (from list or cable IDs)
   d. Find nearest cable point
   e. Compare distances:
      - If FOSC within 1.5x cable distance → Use FOSC
      - Otherwise → Use cable
   f. Extend cable to connection point
   g. Create/update FOSC at connection point

3. Update cable geometry and FOSC list
```

## Where to Find Updated Data

### Small Area Test:
**Location**: `test_output/small_area_design_final/`

**Key Files**:
- `fiber_cable_connected.geojson` - **Main output**: Cables with extensions applied
- `isolated_cable_connection_summary.json` - Summary of all connections made
- `rules_optimized_foscs.json` - Updated FOSC list (includes new FOSCs)
- `splice closure.geojson` - FOSC GeoJSON (updated with new FOSCs)

**Connection Details** (from summary):
```json
{
  "isolated_found": 4,
  "connected": 4,
  "new_foscs": 4,
  "connections": [
    {
      "cable_id": "48FOC/F1000509/T1002415",
      "fosc_id": "F1000390",
      "connection_point": [390923.57, 5069299.15],
      "distance_m": 2368.7,
      "target_type": "fosc_from_cable_id"
    },
    ...
  ]
}
```

### Full Design Test:
**Location**: `test_output/full_design/` (when run)

Same file structure as small area test.

## Verification

To verify the connection was made correctly:

1. **Check connection summary**:
   ```bash
   cat test_output/small_area_design_final/isolated_cable_connection_summary.json
   ```

2. **Check updated cables**:
   - Open `fiber_cable_connected.geojson`
   - Find cable `48FOC/F1000509/T1002415`
   - Verify it has been extended to connect to F1000390

3. **Check FOSC list**:
   - Open `rules_optimized_foscs.json`
   - Verify F1000390 is in the list (or was created)
   - Check `connected_cables` includes `48FOC/F1000509/T1002415`

## Algorithm Details

### FOSC Extraction from Cable IDs
```python
# Cable: 144FOC/F1000390/F1000502
# Extracts:
#   F1000390 → start point of cable
#   F1000502 → end point of cable (if it's a FOSC ID)
```

### Connection Priority
1. **FOSCs from FOSC list** (existing FOSCs)
2. **FOSCs from cable IDs** (e.g., F1000390) - **PREFERRED**
3. **Cable points** (only if no FOSC found)

### Distance Calculation
- Uses Euclidean distance in UTM coordinates
- Compares distances from both cable endpoints
- Selects minimum distance endpoint for connection

## Example: 48FOC/F1000509/T1002415 → F1000390

**Before**:
- Cable: `48FOC/F1000509/T1002415`
- Start: F1000509 (FOSC) ✓
- End: T1002415 (Terminal) - not connected to network ✗
- Status: Isolated

**After**:
- Cable: Extended to F1000390
- Start: F1000509 (FOSC) ✓
- End: F1000390 (FOSC, extracted from cable ID) ✓
- Extension: 2368.7m
- Status: Connected to network ✓

## Notes

- The algorithm now correctly identifies and uses F1000390 from the cable ID `144FOC/F1000390/F1000502`
- FOSCs extracted from cable IDs are prioritized over cable points
- Search distance increased to 3km to handle cases like this
- All isolated cables are now properly connected
