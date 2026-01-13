# How to Provide Road Layer for Rule 23

## Problem

The algorithm currently uses existing fiber cables as a proxy for roads, but:
- ❌ Not all cables follow roads (some are in fields)
- ❌ Results in cross-country paths like `48FOC/F0000003/F0000011` and `48FOC/T0000004/F1000397`
- ❌ Creates loops because it can't distinguish road-aligned from field cables

## Solution

**Provide a road/street GeoJSON layer from MapLibre** - the algorithm will use actual roads instead of cable proxy.

---

## Step 1: Export Roads from MapLibre

### Option A: Export Visible Roads Layer

1. In MapLibre, ensure roads/streets layer is visible
2. Export the roads layer as GeoJSON
3. Save to: `test_inputs/small_area/roads.geojson`

### Option B: Query OSM/MapLibre for Roads

If you have access to OSM data or MapLibre API:

```javascript
// In MapLibre, query roads in bounding box
const bbox = map.getBounds();
// Query OSM Overpass API or MapLibre tiles for roads
// Export as GeoJSON
```

---

## Step 2: Road Layer Format

The road layer should be a GeoJSON FeatureCollection:

```json
{
  "type": "FeatureCollection",
  "crs": {
    "type": "name",
    "properties": {
      "name": "urn:ogc:def:crs:EPSG::32617"
    }
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[x1, y1], [x2, y2], ...]
      },
      "properties": {
        "name": "Highway 542",
        "type": "highway"
      }
    }
  ]
}
```

**Requirements:**
- ✅ Same CRS as other files (EPSG:32617)
- ✅ LineString or MultiLineString geometry
- ✅ Can include road names/types in properties (optional)

---

## Step 3: Run with Road Layer

```bash
python3 generate_design.py \
  --onts "test_inputs/small_area/ONT.geojson" \
  --cables "test_inputs/small_area/fiber cable.geojson" \
  --roads "test_inputs/small_area/roads.geojson" \
  --output "test_output/small_area_design_fresh"
```

**If no road layer provided:**
```bash
python3 generate_design.py \
  --onts "test_inputs/small_area/ONT.geojson" \
  --cables "test_inputs/small_area/fiber cable.geojson" \
  --output "test_output/small_area_design_fresh"
```
(Will use cables as proxy, with warning)

---

## What Happens

### With Road Layer:
1. ✅ Algorithm loads actual roads
2. ✅ Checks if connection paths follow roads
3. ✅ Rejects cross-country paths
4. ✅ Prevents loops by using accurate road data
5. ✅ Only connects cables along actual roads

### Without Road Layer:
1. ⚠️ Uses infrastructure cables as proxy
2. ⚠️ May accept field cables as "roads"
3. ⚠️ Can create cross-country paths
4. ⚠️ May create loops

---

## Expected Output

**With roads:**
```
Loading input data...
  ✓ Loaded 50 road segments from test_inputs/small_area/roads.geojson
  ✓ Loaded 111 ONTs from test_inputs/small_area/ONT.geojson
  ✓ Loaded 17 fiber cable segments from test_inputs/small_area/fiber cable.geojson

Rule 23 (Early): Connecting Isolated Cables in Input Data...
  Selected: cable (2036.2m, path: 2101m, crossings: 0) [closest] (95% on roads)
    Target: 96FOC/F1000391/F1000397
```

**Without roads:**
```
Loading input data...
  ⚠️  No road layer provided - using infrastructure cables as proxy (may be inaccurate)
     To improve accuracy, provide a road/street GeoJSON layer from MapLibre
  ✓ Loaded 111 ONTs from test_inputs/small_area/ONT.geojson
  ✓ Loaded 17 fiber cable segments from test_inputs/small_area/fiber cable.geojson
```

---

## Next Steps

1. **Export roads from MapLibre** as GeoJSON
2. **Save to** `test_inputs/small_area/roads.geojson`
3. **Run with** `--roads` parameter
4. **Verify** connections now follow roads (not fields)

This will fix:
- ✅ `48FOC/F0000003/F0000011` - will follow roads
- ✅ `48FOC/T0000004/F1000397` - will follow roads
- ✅ Loop issues - prevented by accurate road data
