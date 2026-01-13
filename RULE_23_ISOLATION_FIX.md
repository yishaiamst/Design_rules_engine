# Rule 23: Isolated Cable Detection and Connection - Enhanced

## Problem Identified

The original algorithm was connecting isolated cables to OTHER isolated cables, creating isolated islands. For example:
- `48FOC/T0000005/UNKNOWN` connects to `96FOC/UNKNOWN/T0000005` 
- Both are still isolated because they only connect to each other, not to the main network

## Solution: Multi-Pass Iterative Connection

The algorithm now runs multiple passes (up to 5 iterations) to:
1. **Pass 1**: Connect isolated cables to the main network (FOSCs or connected cables)
2. **Pass 2+**: Re-detect isolation after Pass 1 connections, catching cables that were connected to other isolated cables
3. Continue until no more isolated cables are found

## Integration into Pipeline

**Rule 23 is automatically executed** in `generate_design.py` as **Phase 3e**:
- Runs after Phase 3d (Update Cable IDs)
- Before Phase 6 (Cable Sizing)
- Ensures all cables are connected before sizing

## Algorithm Flow

```
1. Detect isolated cables (not connected to FOSCs or main network)
2. For each isolated cable:
   a. Find nearest FOSC (from list or extracted from cable IDs)
   b. Find nearest cable point
   c. Prioritize FOSC over cable
   d. Extend cable to connection point
   e. Create/update FOSC at connection point
3. Re-detect isolation (new FOSCs may have connected previously isolated cables)
4. Repeat until no isolated cables found (max 5 passes)
```

## Key Features

1. **FOSC Extraction from Cable IDs**: Extracts FOSC positions from cable IDs (e.g., F1000390 from `144FOC/F1000390/F1000502`)
2. **FOSC Prioritization**: Prefers FOSCs over cable points (even if cable is slightly closer)
3. **Multi-Pass Iteration**: Catches isolated islands that form after initial connections
4. **Extended Search**: For UNKNOWN endpoints, searches up to 5km
5. **Geometry Fix**: Converts MultiLineString to LineString for extended cables

## Usage

The algorithm is automatically called in `generate_design.py`:

```python
# Phase 3e: Connect Isolated Fiber Cables (Rule 23)
connected_cables_geojson, new_foscs, connection_summary = connect_isolated_cables(
    updated_cables_geojson,
    foscs,
    tolerance_m=50.0,
    max_connection_distance_m=3000.0,  # 3km default
    max_iterations=5  # Multiple passes to catch islands
)
```

## Output Files

- `fiber_cable_connected.geojson` - Cables with extensions applied
- `isolated_cable_connection_summary.json` - Summary of all connections
- `rules_optimized_foscs.json` - Updated FOSC list (includes new FOSCs)

## Notes

- The algorithm ensures all cables are connected to the main network
- Isolated islands are automatically detected and connected in subsequent passes
- No manual intervention required - fully automated in the design pipeline
