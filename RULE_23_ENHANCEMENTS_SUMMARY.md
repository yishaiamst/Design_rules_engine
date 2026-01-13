# Rule 23 Enhancements Summary

## Enhancements Made

### 1. **Cable Size Constraint**
- **Rule**: Isolated cables can only connect to cables with size >= their own size
- **Example**: `48FOC` can connect to `48FOC`, `96FOC`, `144FOC`, `288FOC` but NOT to `12FOC`
- **Rationale**: Prevents connecting larger cables to smaller infrastructure cables

### 2. **Loop Detection**
- **Function**: `detect_loop_enhanced()` - Detects if a connection would create a closed path/loop
- **Logic**: Checks if there's an existing path from the other endpoint of isolated cable to the other endpoint of target cable
- **Priority**: Non-loop connections are preferred over loop-creating connections

### 3. **Path-Based Selection**
- **Metrics Calculated**:
  - Distance from nearest OLT (straight-line)
  - Number of FOSCs crossed (within 50m)
  - Number of terminals crossed (within 50m)
  - Total crossings (FOSCs + terminals)
- **Selection Criteria** (in order):
  1. Avoid loops (reject if creates loop)
  2. Minimize path from OLT (shorter is better)
  3. Minimize crossings (fewer FOSCs/terminals is better)
  4. Minimize distance (closer is better)

### 4. **Comprehensive Candidate Evaluation**
- Evaluates ALL connection options (FOSCs and cables) together
- Filters by size constraint
- Filters by loop detection
- Selects best based on path metrics

### 5. **Multi-Pass Iteration**
- Runs up to 5 passes to catch isolated islands
- Each pass re-detects isolation after previous connections
- Continues until network is fully connected

### 6. **FOSC Extraction from Cable IDs**
- Extracts FOSC positions from cable IDs (e.g., F1000390 from `144FOC/F1000390/F1000502`)
- Uses these FOSC positions as connection targets
- Prioritizes FOSCs over cables

### 7. **CRS Support**
- Adds CRS (Coordinate Reference System) to output GeoJSON
- Format: `EPSG:32617` (UTM Zone 17N)
- Ensures files display correctly in mapping applications

## Current Status

The algorithm is working but `144FOC/T0000003/T0000020` is not appearing in the candidate list for `48FOC/T0000005/UNKNOWN`. This needs investigation to ensure:
1. The cable is being found in the search
2. The distance is being calculated correctly
3. The coordinate flattening is working for MultiLineString

## Next Steps

1. Verify `144FOC/T0000003/T0000020` is being found and distance calculated
2. Ensure loop detection correctly identifies connections that would create squares
3. Test with actual OLT positions to get accurate path metrics
4. Verify the final connection avoids loops and minimizes path length

## Integration

All enhancements are integrated into:
- `phases/phase3e_connect_isolated_cables.py`
- `generate_design.py` (Phase 3e)
- Automatically runs in the design pipeline
