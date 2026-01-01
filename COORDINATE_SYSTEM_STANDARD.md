# Coordinate System Standard

## Current Standard: UTM Zone 17N (EPSG:32617)

**ALL calculations, distance measurements, and spatial operations MUST use UTM coordinates.**

### Why UTM?
- Original GeoJSON files are in UTM Zone 17N (EPSG:32617)
- UTM is a projected coordinate system (meters), perfect for distance calculations
- No transformation errors during calculations
- Only transform to WGS84 (EPSG:4326) at the very end for visualization/mapping

### Rules:
1. **Load coordinates as-is from GeoJSON** (they're already UTM)
2. **All distance calculations use UTM** (euclidean_distance, point_to_line_distance, etc.)
3. **All position comparisons use UTM**
4. **Only transform to WGS84 when writing final visualization GeoJSON files**

### Coordinate Format:
- UTM: `[easting, northing]` where easting ~300000-800000, northing ~4000000-6000000
- Example: `[410000.0, 5073774.0]` (T0000356 position)

### Files Using UTM:
- `ONT.geojson` - UTM coordinates
- `fiber cable.geojson` - UTM coordinates  
- `terminal.geojson` - UTM coordinates
- All summary JSON files should store positions as UTM `[x, y]` arrays

### Transformation:
- Use `utils.coordinate_transform.transform_to_wgs84()` ONLY for final visualization
- Never transform during calculations or comparisons
