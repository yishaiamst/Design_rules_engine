# Extract Roads from MapTiler/OSM for Rule 23

## Quick Start

**I've created a script that automatically extracts roads for your test area!**

### Option 1: Use OSM (Free, No API Key Needed) ✅ RECOMMENDED

```bash
python3 utils/extract_roads_maptiler.py \
  --cables "test_inputs/small_area/fiber cable.geojson" \
  --onts "test_inputs/small_area/ONT.geojson" \
  --output "test_inputs/small_area/roads.geojson"
```

**What it does:**
1. Calculates bounding box from your test data
2. Queries OSM Overpass API for all roads in that area
3. Converts from WGS84 to UTM Zone 17N
4. Saves as `roads.geojson` ready for Rule 23

**No API key needed!** Uses free OSM data.

---

### Option 2: Use MapTiler (Requires API Key)

**What I need from you:**
1. **MapTiler API Key** (if you have one)
2. **That's it!** The script will handle the rest

**If you have a MapTiler API key:**
```bash
export MAPTILER_API_KEY="your_key_here"
python3 utils/extract_roads_maptiler.py \
  --cables "test_inputs/small_area/fiber cable.geojson" \
  --onts "test_inputs/small_area/ONT.geojson" \
  --output "test_inputs/small_area/roads.geojson" \
  --maptiler
```

---

## What the Script Does

1. **Reads your test data** (cables + ONTs)
2. **Calculates bounding box** automatically
3. **Queries road data** from OSM or MapTiler
4. **Converts coordinates** to UTM Zone 17N (matches your data)
5. **Saves GeoJSON** ready for Rule 23

---

## Road Types Extracted

The script extracts:
- Primary roads
- Secondary roads
- Tertiary roads
- Residential streets
- Service roads
- Tracks/paths

All road types that cables can be mounted on.

---

## Output Format

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
        "highway": "residential",
        "name": "Highway 542"
      }
    }
  ]
}
```

**Ready to use with Rule 23!**

---

## After Extraction

Run design generation with roads:

```bash
python3 generate_design.py \
  --onts "test_inputs/small_area/ONT.geojson" \
  --cables "test_inputs/small_area/fiber cable.geojson" \
  --roads "test_inputs/small_area/roads.geojson" \
  --output "test_output/small_area_design_fresh"
```

---

## Dependencies

**Required:**
- `requests` (for API calls)
- `pyproj` (for coordinate conversion)

**Install:**
```bash
pip install requests pyproj
```

---

## What I Need From You

### For OSM (Recommended):
**Nothing!** Just run the script - it's free and works immediately.

### For MapTiler:
1. **MapTiler API Key** (if you prefer MapTiler over OSM)
2. That's it!

---

## Example Output

```
================================================================================
EXTRACTING ROADS FOR TEST AREA
================================================================================

Calculating bounding box from input data...
  ✓ Bounding box: (386704.61, 5063074.66) to (408765.49, 5085272.60)

Extracting roads from OSM Overpass API...
  Querying OSM for roads in bbox: (45.7123, -82.1234) to (45.8234, -81.9876)
  ✓ Found 127 road segments

Converting roads from WGS84 to UTM Zone 17N...
  ✓ Converted and saved to test_inputs/small_area/roads.geojson

✓ Roads extracted successfully!
```

---

## Next Steps

1. **Run the extraction script** (OSM is free, no key needed)
2. **Verify roads.geojson** was created
3. **Run design generation** with `--roads` parameter
4. **Check results** - connections should now follow roads!

This will fix:
- ✅ Cross-country paths (48FOC/F0000003/F0000011)
- ✅ Field routing (48FOC/T0000004/F1000397)
- ✅ Loop issues
