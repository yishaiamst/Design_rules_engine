# Output Files Reference

## Location
All generated files are saved to: `test_output/small_area_design_fresh/`

## Generated GeoJSON Files

### Core Design Layers
1. **`OLT.geojson`** - Optical Line Terminals
   - Point features
   - Properties: OLT ID, position, ONT count

2. **`terminal.geojson`** - Aerial Terminals (MST)
   - Point features
   - Properties: Terminal ID, Type (Aerial/MST), ONT count, connected cable/FOSC IDs

3. **`splice closure.geojson`** - FOSCs (Fiber Optic Splice Closures)
   - Point features
   - Properties: FOSC ID, trigger, cable count, placement method

4. **`fiber cable.geojson`** - Sized fiber cables (FINAL OUTPUT)
   - LineString/MultiLineString features
   - Properties: Cable ID, fiber count, From_ID, To_ID, size

5. **`drop cable.geojson`** - Drop cables (Terminal → ONT)
   - LineString features
   - Properties: Cable ID, from terminal, to ONT

6. **`stub cable.geojson`** - Stub cables (MST → FOSC)
   - LineString features
   - Properties: Cable ID, from MST, to FOSC

### Intermediate Files
7. **`fiber_cable_connected.geojson`** - Connected cables (after Rule 23)
   - Shows cables after isolated cable connection
   - Properties: Extended flag, connection info

8. **`fiber_cable_updated_ids.geojson`** - Cables with updated IDs (after Phase 3d)
   - Shows cables after ID assignment
   - Properties: Updated From_ID/To_ID

## Summary JSON Files

- **`olt_placement_summary.json`** - OLT placement details
- **`optimization_summary.json`** - Rule application summary
- **`cable_id_update_summary.json`** - Cable ID update details
- **`cable_sizing_summary.json`** - Cable sizing statistics
- **`cable_extensions_summary.json`** - Drop/stub cable summary
- **`isolated_cable_connection_summary.json`** - Rule 23 (late) connection summary
- **`early_isolated_cable_connection_summary.json`** - Rule 23 (early) connection summary
- **`rules_optimized_terminals.json`** - Optimized terminal data
- **`rules_optimized_foscs.json`** - Optimized FOSC data

## Usage

All files are ready for:
- Map visualization
- Design validation
- BOM generation
- Further analysis

## Notes

- **`fiber cable.geojson`** is the final sized cable output
- **`fiber_cable_connected.geojson`** shows cables after Rule 23 connections
- All files include CRS (EPSG:32617) for proper map display
