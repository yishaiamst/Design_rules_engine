# Rule 23: Dual Execution Strategy

## Problem

1. Input data may have isolated cables from the start
2. Phase 3d (cable ID assignment) may create cables with From_ID/To_ID that don't actually connect to anything
3. Example: `96FOC/F1000395/F1000406` has From_ID and To_ID but is still isolated

## Solution

Run Rule 23 (Connect Isolated Cables) **TWICE**:

### 1. Early Execution (After Loading Inputs)
- **Location**: Right after loading input data, before Phase 0
- **Purpose**: Clean up any isolated cables in the original input data
- **Input**: Original `fiber_cable_geojson` from file
- **FOSCs**: Empty (no FOSCs yet)
- **Output**: Cleaned cable network for design process

### 2. Late Execution (After Phase 3d)
- **Location**: After Phase 3d (cable ID updates)
- **Purpose**: Catch any new isolations created by cable ID assignment
- **Input**: `updated_cables_geojson` from Phase 3d
- **FOSCs**: Existing FOSCs from Phase 2/3
- **Output**: Fully connected cable network

## Why This Works

**Early Execution**:
- Cleans input data before design process starts
- Ensures all input cables are connected
- Prevents issues downstream

**Late Execution**:
- Catches cables with incorrect From_ID/To_ID assignments
- Handles cases where phase3d creates IDs that don't match actual connections
- Uses existing FOSCs for better connection decisions

## Example: `96FOC/F1000395/F1000406`

This cable:
- Has `From_ID: F1000395` and `To_ID: F1000406`
- But these FOSCs may not exist or may not be at the cable endpoints
- Created during phase3d (cable ID assignment)
- Not detected as isolated until after phase3d

**Solution**: Late execution catches this and connects it properly.

## Implementation

```python
# Early: After loading inputs
cleaned_cables_geojson, early_foscs, early_summary = connect_isolated_cables(
    fiber_cable_geojson,  # Original input
    [],  # No FOSCs yet
    ...
)

# Late: After phase3d
connected_cables_geojson, new_foscs, connection_summary = connect_isolated_cables(
    updated_cables_geojson,  # After cable ID updates
    foscs,  # Existing FOSCs
    ...
)
```

## Output Files

All generated layers are saved to output directory:
- `OLT.geojson` - Optical Line Terminals
- `terminal.geojson` - Aerial Terminals (MST)
- `splice closure.geojson` - FOSCs
- `fiber cable.geojson` - Sized fiber cables
- `drop cable.geojson` - Drop cables (Terminal → ONT)
- `stub cable.geojson` - Stub cables (MST → FOSC)
- `fiber_cable_connected.geojson` - Connected cables (after Rule 23)
- `early_isolated_cable_connection_summary.json` - Early execution summary
- `isolated_cable_connection_summary.json` - Late execution summary
