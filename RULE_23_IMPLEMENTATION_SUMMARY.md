# Rule 23 Implementation Summary

## Dual Execution Strategy

Rule 23 (Connect Isolated Cables) runs **TWICE**:

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

## Detection Logic

A cable is considered isolated if:

1. **Neither endpoint connects to FOSC** AND **neither endpoint is shared with other cables**
2. **Has UNKNOWN endpoint(s)** - one end may connect but other doesn't
3. **Has From_ID/To_ID but endpoints don't actually connect** - catches phase3d issues where IDs are assigned but FOSCs don't exist or aren't at endpoints

## Selection Criteria

When connecting isolated cables, priority order:

1. **Avoid loops** (reject if creates loop/square)
2. **Closest distance** (primary constraint)
3. **Shorter path from OLT** (secondary)
4. **Fewer FOSCs/terminals crossed** (tertiary)

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

## Example: `96FOC/F1000395/F1000406`

This cable:
- Has `From_ID: F1000395` and `To_ID: F1000406`
- But these FOSCs may not exist or may not be at the cable endpoints
- May be created during phase3d (cable ID assignment)
- Detection: If neither endpoint connects to FOSC or other cables, it's isolated
- Solution: Late execution catches this and connects it properly

## Benefits

1. **Early execution**: Ensures clean input data before design process
2. **Late execution**: Catches phase3d issues where IDs don't match actual connections
3. **Comprehensive detection**: Handles UNKNOWN endpoints and incorrect ID assignments
4. **Complete outputs**: All generated layers saved to output folder
