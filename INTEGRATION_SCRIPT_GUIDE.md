# Design Engine Integration Script Guide

## Overview

The `generate_design.py` script is the main integration script that orchestrates all phases of the fiber network design generation process. It runs all phases in the correct order, applies optimization rules, and generates all output files.

## Phase Execution Order

The script executes phases in the following order:

1. **Phase 0: Community Pockets**
   - Clusters ONTs into community pockets for OLT placement decisions
   - Merges nearby pockets and validates diameters

2. **Phase 1: Place OLTs**
   - Places OLTs based on community pockets and infrastructure
   - Validates all ONTs are within 20km of their assigned OLT

3. **Phase 2: Place FOSCs (Initial - Geometry-Based)**
   - Places FOSCs at cable junctions (≥2 cables)
   - Places FOSCs on long segments (≥1800m)
   - Geometry-based placement only

4. **Phase 3: Place Terminals**
   - Places MSTs and Aerial Terminals based on ONT clusters
   - Uses R10/R11 logic (FOSC proximity)
   - Connects terminals to FOSCs

5. **Phase 3b: Refine MST Placement**
   - Fixes design issues
   - Refines MST positions based on cable locations

6. **Phase 3c: Apply Optimization Rules (R1-R22)**
   - Applies all 22 optimization rules
   - Merges nearby FOSCs and terminals
   - Converts terminals to MSTs where appropriate
   - Optimizes ONT-to-terminal connections
   - Ensures all MSTs are connected via stub cables
   - **Output**: `rules_optimized_terminals.json` and `rules_optimized_foscs.json`

7. **Phase 3d: Update Cable IDs (Rule 22)**
   - Updates fiber cable IDs based on FOSC and terminal positions
   - Format: `<size>FOC/From/To`
   - Ensures cables connect to FOSCs, not MSTs

8. **Phase 5: Create Drop and Stub Cables**
   - Creates drop cables (ONT → Terminal)
   - Creates stub cables (MST → FOSC)
   - Routes stub cables along fiber infrastructure

9. **Phase 6: Cable Sizing & ID Allocation**
   - Determines cable sizes based on downstream ONT counts
   - Applies cable sizing rules
   - Maintains cable hierarchy (288/144 → 96 → 48 → 12 → 1F)

10. **Phase 7: Create Layered Visualization**
    - Note: Run `create_layered_visualization.py` separately
    - Generates separate GeoJSON layers for each component type
    - Applies visual offsets for overlapping features
    - Ensures precise endpoint connections

11. **Phase 8: BOM Generation**
    - TODO: Generate Bill of Materials
    - Will count components and calculate cable lengths

## Usage

### Basic Usage

```bash
python3 generate_design.py \
  --onts ONT.geojson \
  --cables "fiber cable.geojson" \
  --config design_config.json \
  --output test_output
```

### Arguments

- `--onts`: Path to ONT GeoJSON file (required)
- `--cables`: Path to fiber cable GeoJSON file (required)
- `--config`: Path to configuration file (default: `design_config.json`)
- `--output`: Output directory (default: `output`)

## Output Files

### GeoJSON Files
- `OLT.geojson` - OLT locations
- `terminal.geojson` - Terminal locations (MSTs and Aerial Terminals)
- `splice closure.geojson` - FOSC locations
- `drop cable.geojson` - Drop cable connections
- `stub cable.geojson` - Stub cable connections
- `fiber cable.geojson` - Sized fiber cables (after Phase 6)

### Summary Files
- `olt_placement_summary.json` - OLT placement details
- `optimization_summary.json` - Optimization rules application summary
- `cable_id_update_summary.json` - Cable ID update details
- `cable_sizing_summary.json` - Cable sizing details

### Intermediate Files
- `rules_optimized_terminals.json` - Optimized terminals (for visualization)
- `rules_optimized_foscs.json` - Optimized FOSCs (for visualization)
- `fiber_cable_updated_ids.geojson` - Cables with updated IDs (before sizing)

## Visualization

After running `generate_design.py`, run the visualization script to generate layered GeoJSON files:

```bash
python3 create_layered_visualization.py
```

This will create separate GeoJSON files in `test_output/layers/`:
- `fosc.geojson`
- `aerial_terminal.geojson`
- `mst.geojson`
- `ont.geojson`
- `fiber_cable.geojson`
- `drop_cable.geojson`
- `stub_cable.geojson`
- `fdh.geojson`
- `vault.geojson`

## Error Handling

The script includes comprehensive error handling:
- Each phase is wrapped in try/except blocks
- Import errors are caught and reported (phase not implemented)
- Runtime errors are caught, logged, and execution continues
- Failed phases don't stop the entire process

## State Management

The script maintains a `design_state` dictionary that tracks:
- Configuration
- Input data (ONTs, fiber cables)
- Intermediate results (pockets, OLTs, terminals, FOSCs)
- Final results (cables, BOM)

Each phase updates the design state, and subsequent phases use the updated state.

## Dependencies

The script requires:
- All phase modules in `phases/` directory
- Utility modules in `utils/` directory
- Configuration file (`design_config.json`)
- Input GeoJSON files

## Next Steps

1. **BOM Generation**: Implement Phase 8 to generate Bill of Materials
2. **Validation**: Add comprehensive design validation
3. **Performance**: Optimize for large datasets (1000+ ONTs)
4. **Testing**: Add unit tests for each phase

## Notes

- The script is designed to be idempotent (can be run multiple times)
- All phases are optional (missing phases are skipped with warnings)
- The script generates intermediate files for debugging and visualization
- Coordinate system: All calculations use UTM Zone 17N (EPSG:32617)
