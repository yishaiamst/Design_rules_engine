# Coordinate Transformation and Visualization Fix

## Issues Identified

1. **Coordinate Transformation Error**: Manual UTM→WGS84 conversion has ~0.14° error (~15km)
2. **Visualization Compatibility**: Single large file (65MB) confuses QGIS and map viewers

## Solutions Implemented

### 1. Separate Layer Files
Created individual GeoJSON files for each layer in `test_output/layers_utm/`:
- `terminal.geojson` - 8,156 terminals (MSTs and Aerial)
- `fosc.geojson` - 675 FOSCs
- `fiber_cable.geojson` - 4,543 fiber cables
- `drop_cable.geojson` - 21,398 drop cables
- `ont.geojson` - 22,769 ONTs
- `olt.geojson` - 17 OLTs

**Benefits**:
- Better rendering in QGIS (colors and symbols work correctly)
- Easier to toggle layers on/off
- Smaller individual files load faster

### 2. Accurate Coordinate Transformation
**Install pyproj for accurate transformation**:
```bash
pip3 install --user pyproj
```

After installation, the visualization will use accurate pyproj transformation instead of manual approximation.

**Current Status**:
- Manual transformation: ~0.14° error (~15km)
- With pyproj: <0.001° error (<100m)

## Files Created

### Main Visualization Files
- `test_output/network_visualization_utm.geojson` - UTM coordinates (accurate, use this)
- `test_output/network_visualization.geojson` - WGS84 (may have errors without pyproj)

### Separate Layer Files (Recommended for QGIS)
- `test_output/layers_utm/terminal.geojson` - Terminals only
- `test_output/layers_utm/fosc.geojson` - FOSCs only
- `test_output/layers_utm/fiber_cable.geojson` - Fiber cables only
- `test_output/layers_utm/drop_cable.geojson` - Drop cables only
- `test_output/layers_utm/ont.geojson` - ONTs only
- `test_output/layers_utm/olt.geojson` - OLTs only

## Usage in QGIS

1. **Load separate layer files** (recommended):
   - Add Vector Layer → Select `terminal.geojson`
   - Repeat for other layers
   - Each layer will render with correct colors/symbols

2. **Or load main file**:
   - Add Vector Layer → Select `network_visualization_utm.geojson`
   - Set CRS to EPSG:32617 (UTM Zone 17N)
   - Use layer filter: `layer = 'terminal'` to see terminals only

## MST Visualization

MSTs should appear as:
- **Color**: Purple (#800080)
- **Symbol**: Triangle
- **Size**: Medium

If triangles don't appear:
1. Check layer file `terminal.geojson` separately
2. Verify `marker-symbol` property is "triangle"
3. Some viewers may need custom styling

## Next Steps

1. **Install pyproj** for accurate coordinates:
   ```bash
   pip3 install --user pyproj
   ```

2. **Regenerate visualization** after pyproj installation:
   ```bash
   python3 visualize_network_graph.py
   ```

3. **Use separate layer files** in QGIS for best results
