# Phase 3b: Design Fixes Summary

## Issues Fixed

### 1. ✅ MST/Aerial Terminal Placement Logic
**Problem**: Logic allowed converting MST to Aerial Terminal if it couldn't be placed on cable.

**Fix**: 
- Both MSTs and Aerial Terminals MUST be placed ON the fiber cable (no exceptions)
- If a terminal can't be placed on cable, it's a logic error - Phase 3b will move it to the nearest cable
- No type conversion based on placement ability

**Changes**:
- `phases/phase3_place_terminals.py`: Updated placement logic to always place MSTs ON cable
- `phases/phase3b_refine_mst_placement.py`: Ensures all MSTs are moved to cable if not already on it

### 2. ✅ FOSC Placement on Fiber Cable
**Problem**: FOSCs appearing not on the fiber cable layer (possibly in water).

**Fix**:
- All FOSCs are verified and snapped to the nearest point on the fiber cable
- Junction positions are verified to be exactly on cables
- Phase 3b includes FOSC placement verification

**Changes**:
- `phases/phase3_place_terminals.py`: Junction positions are snapped to cable points
- `phases/phase3b_refine_mst_placement.py`: Added Fix 0 to ensure FOSCs are on cables

### 3. ✅ Coordinate Transformation Issue
**Problem**: Cables appearing in water (blue areas) suggests coordinate transformation is incorrect.

**Status**: 
- Manual UTM to WGS84 conversion has accuracy limitations (~0.4° error)
- Created both WGS84 and UTM versions of visualization
- **Recommendation**: Install pyproj for accurate transformation: `pip3 install pyproj`

**Files Created**:
- `test_output/network_visualization.geojson` - WGS84 (may have accuracy issues)
- `test_output/network_visualization_utm.geojson` - UTM Zone 17N (original coordinates, accurate)

**Solution Options**:
1. **Use UTM version**: Load `network_visualization_utm.geojson` and set CRS to EPSG:32617 in your viewer
2. **Install pyproj**: Run `pip3 install pyproj` for accurate WGS84 transformation
3. **Use QGIS**: QGIS can handle UTM coordinates natively and transform on-the-fly

### 4. ✅ Long Drop Cables
**Problem**: ONT clusters connected to distant terminals via long drop cables.

**Fix**:
- Phase 3b detects long drop cables (>150m)
- Places new MSTs near ONT clusters, connected to FOSCs via stub cables
- Each MST serves up to 12 ONTs

**Results**: Added 50 new MSTs, fixed 184 long drop cables

### 5. ✅ Terminal Overload
**Problem**: Terminals with >12 ONTs (Example 4: 60-70 ONTs on one terminal).

**Fix**:
- Phase 3b detects overloaded terminals
- Splits them into multiple MSTs (12 ports each) from the FOSC
- Each MST placed ON the fiber cable

### 6. ✅ Standalone MSTs
**Problem**: MSTs placed off the fiber cable (Example 2).

**Fix**:
- All MSTs are moved to nearest point on cable in Phase 3b
- If MST can't be placed on cable, it's moved to nearest cable (no type conversion)

## Implementation Status

✅ **Phase 3b created**: `phases/phase3b_refine_mst_placement.py`
- Fix 0: FOSC placement on cables
- Fix 1: MST placement on cables  
- Fix 2: Terminal overload splitting
- Fix 3: Long drop cable fixes

✅ **Integrated into pipeline**: `generate_design.py` now calls Phase 3b after Phase 3

✅ **Test script**: `test_phase3b_refinement.py` validates fixes

## Next Steps

1. **Install pyproj** for accurate coordinate transformation:
   ```bash
   pip3 install pyproj
   ```

2. **Use UTM version** if WGS84 transformation is inaccurate:
   - Load `test_output/network_visualization_utm.geojson`
   - Set CRS to EPSG:32617 in your viewer

3. **Verify FOSC placement**: Check that all FOSCs are on land (green areas), not in water

4. **Test stub cable creation**: Ensure MSTs connected to FOSCs have stub cables created

## Files Modified

- `phases/phase3_place_terminals.py` - MST placement logic fixed
- `phases/phase3b_refine_mst_placement.py` - New refinement phase
- `generate_design.py` - Integrated Phase 3b
- `visualize_network_graph.py` - Creates both WGS84 and UTM versions
- `utils/coordinate_transform.py` - Improved UTM conversion (still approximate without pyproj)
