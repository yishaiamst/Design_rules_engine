# Which File to Use?

## File Comparison

### `fiber_cable_updated_ids.geojson`
- **Phase**: After Phase 3d (Cable ID Updates)
- **Status**: Cables have updated From_ID/To_ID based on FOSC/terminal positions
- **Rule 23**: NOT applied yet
- **Use Case**: 
  - Base network reference
  - Before isolated cable connections
  - For analysis of ID assignment

### `fiber_cable_connected.geojson`
- **Phase**: After Phase 3e (Rule 23 - Connect Isolated Cables)
- **Status**: Isolated cables connected, may have extended cables
- **Rule 23**: Applied (early + late execution)
- **Use Case**:
  - Connected network (all isolated cables resolved)
  - May have loops if loop detection fails
  - For visualization of connected network

### `fiber cable.geojson` (FINAL)
- **Phase**: After Phase 6 (Cable Sizing)
- **Status**: Final sized cables with fiber counts
- **Rule 23**: Applied
- **Use Case**:
  - **PRIMARY OUTPUT** - Use this for final design
  - Complete network with sizes
  - Ready for BOM generation

## Recommendation

### For Map Visualization
**Use**: `fiber cable.geojson` (final sized cables)
- Most complete
- Includes sizes
- All connections made
- Has CRS for proper display

### For Analysis
**Use**: `fiber_cable_updated_ids.geojson`
- Before Rule 23 connections
- Shows original network structure
- Good for comparing before/after

### For Debugging
**Use**: `fiber_cable_connected.geojson`
- Shows Rule 23 connections
- Can identify loop issues
- Shows extended cables

## Loop Issue

If `fiber_cable_connected.geojson` creates loops:
- **Cause**: Loop detection may not catch all cases
- **Solution**: Enhanced loop detection + infrastructure constraint
- **Workaround**: Use `fiber_cable_updated_ids.geojson` and manually review connections

## CRS Status

All files now include CRS (EPSG:32617) for proper map display:
- ✓ `OLT.geojson`
- ✓ `terminal.geojson`
- ✓ `splice closure.geojson`
- ✓ `fiber cable.geojson`
- ✓ `drop cable.geojson`
- ✓ `stub cable.geojson`
- ✓ `fiber_cable_connected.geojson`
- ✓ `fiber_cable_updated_ids.geojson`
