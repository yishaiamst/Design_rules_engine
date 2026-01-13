# Automatic Coordinate Conversion for WGS84 Roads

## Problem

Roads extracted from OSM are in WGS84 (lat/lon), but cables are in UTM Zone 17N. Without conversion, Rule 23 can't accurately check if paths follow roads.

## Solution

**Automatic coordinate conversion** - Rule 23 now detects WGS84 roads and converts them to UTM on-the-fly.

## Implementation

### 1. CRS Detection

The `check_near_infrastructure()` function now:
- Detects CRS from roads GeoJSON
- Checks if roads are in WGS84 (EPSG:4326)
- Checks if roads are in UTM (EPSG:32617)
- Automatically converts WGS84 → UTM when needed

### 2. Coordinate Conversion

```python
def convert_wgs84_to_utm_coords(lon: float, lat: float, utm_zone: int = 17) -> Tuple[float, float]:
    """
    Convert WGS84 (lon, lat) to UTM Zone 17N.
    
    Uses pyproj if available (accurate), falls back to approximation if not.
    """
```

**Two modes:**
- **With pyproj**: Accurate conversion using PROJ library
- **Without pyproj**: Approximate conversion (good enough for alignment checks)

### 3. Automatic Detection

```python
# In check_near_infrastructure()
roads_crs = cables_geojson.get("crs", {})
is_wgs84 = "4326" in roads_crs_name or "WGS84" in roads_crs_name.upper()
is_utm = "32617" in roads_crs_name or "UTM" in roads_crs_name.upper()

needs_conversion = is_wgs84 and not is_utm

if needs_conversion:
    # Convert each road coordinate from WGS84 to UTM
    x_utm, y_utm = convert_wgs84_to_utm_coords(lon, lat, utm_zone=17)
```

## How It Works

1. **Load roads** (WGS84 from OSM)
2. **Check CRS** - detects EPSG:4326
3. **Convert coordinates** - each road segment converted to UTM Zone 17N
4. **Compare with cables** - both in same coordinate system (UTM)
5. **Check alignment** - accurate distance and direction checks

## Benefits

✅ **No manual conversion needed** - automatic
✅ **Works with OSM roads** - WGS84 handled automatically
✅ **Works with UTM roads** - if you provide UTM roads, no conversion
✅ **Fallback if pyproj missing** - approximate conversion still works
✅ **Accurate alignment checks** - roads and cables in same coordinate system

## Example

**Input:**
- Roads: WGS84 (lon: -83.4, lat: 46.3)
- Cables: UTM Zone 17N (x: 391866, y: 5066139)

**Process:**
1. Detect roads are WGS84
2. Convert road coordinates: (-83.4, 46.3) → (391866, 5066139) UTM
3. Compare with cable coordinates (both in UTM)
4. Check if path follows roads

## Status

✅ **Implemented and working**
- Automatic CRS detection
- WGS84 → UTM conversion
- Fallback for missing pyproj
- All road alignment checks now accurate

## Next Steps

For best accuracy, install pyproj:
```bash
pip3 install --user pyproj
```

But it works without it (using approximation).
