# Road Data Solution for Rule 23

## Problem

The current implementation uses existing fiber cables as a proxy for roads, but:
- ❌ Not all cables follow roads (some are in fields)
- ❌ Small cables (48F, 12F) may not follow roads
- ❌ Algorithm can't distinguish between road-aligned and field cables
- ❌ Results in cross-country paths like `48FOC/F0000003/F0000011` and `48FOC/T0000004/F1000397`

## Solution Options

### Option 1: Accept Road Layer as Input (RECOMMENDED)

**Add road/street GeoJSON as input parameter:**

```python
def generate_design(
    ont_geojson_path: str,
    fiber_cable_geojson_path: str,
    road_geojson_path: str = None,  # NEW: Optional road layer
    config_path: str = "design_config.json",
    output_dir: str = "output"
) -> Dict[str, Any]:
```

**Benefits:**
- ✅ Accurate road data
- ✅ Works with any map source (MapLibre, OSM, etc.)
- ✅ User provides actual road network
- ✅ No external API dependencies

**Implementation:**
1. Load road GeoJSON if provided
2. Use roads instead of cables for infrastructure check
3. Check if connection path follows roads
4. Reject paths not on roads

---

### Option 2: Integrate with MapLibre

**Use MapLibre to query road data:**

```python
def get_roads_from_maplibre(bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Query MapLibre/OSM for roads in bounding box.
    
    Returns GeoJSON FeatureCollection of roads.
    """
    # Use OSM Overpass API or MapLibre tiles
    pass
```

**Benefits:**
- ✅ Automatic road detection
- ✅ No manual input needed
- ✅ Always up-to-date

**Challenges:**
- ⚠️ Requires internet connection
- ⚠️ API rate limits
- ⚠️ More complex implementation

---

### Option 3: Filter Infrastructure Cables (TEMPORARY)

**Only use large cables (144F/288F) as road proxy:**

```python
def is_likely_road_cable(cable_id: str, fiber_count: int) -> bool:
    """
    Large infrastructure cables (144F, 288F) are more likely to follow roads.
    Small cables (48F, 12F) may be in fields.
    """
    return fiber_count >= 144  # Only use 144F+ as road proxy
```

**Benefits:**
- ✅ Quick fix
- ✅ No new data needed
- ✅ Better than using all cables

**Limitations:**
- ⚠️ Still not 100% accurate
- ⚠️ Some large cables may not follow roads
- ⚠️ Temporary solution

---

## Recommended Implementation

### Step 1: Add Road Layer Input

```python
# In generate_design.py
def generate_design(
    ont_geojson_path: str,
    fiber_cable_geojson_path: str,
    road_geojson_path: str = None,  # NEW
    config_path: str = "design_config.json",
    output_dir: str = "output"
) -> Dict[str, Any]:
    
    # Load road data if provided
    roads_geojson = None
    if road_geojson_path and os.path.exists(road_geojson_path):
        roads_geojson = load_geojson(road_geojson_path)
        print(f"✓ Loaded road network: {len(roads_geojson.get('features', []))} road segments")
    else:
        print("⚠️  No road layer provided - using infrastructure cables as proxy")
        roads_geojson = None  # Fall back to cable-based check
```

### Step 2: Update Infrastructure Check

```python
def check_near_infrastructure(
    connection_point: Tuple[float, float],
    isolated_endpoint: Tuple[float, float],
    cables_geojson: Dict[str, Any] = None,  # Fallback
    roads_geojson: Dict[str, Any] = None,   # Primary source
    max_distance_m: float = 50.0,
    path_alignment_threshold: float = 0.8
) -> Tuple[bool, float, float]:
    """
    Check if path follows roads (if provided) or infrastructure cables (fallback).
    """
    # Use roads if available, otherwise fall back to cables
    infrastructure_geojson = roads_geojson if roads_geojson else cables_geojson
    
    if not infrastructure_geojson:
        return True, 0.0, 1.0  # No data - allow connection
    
    # ... rest of implementation using infrastructure_geojson
```

### Step 3: Update Rule 23 Call

```python
# In connect_isolated_cables
metrics = calculate_path_metrics_from_olt(
    cable_id, nearest_point, target_cable_id,
    cables_geojson or {"features": all_cables},
    foscs, terminals, olts,
    isolated_endpoint=iso_point,
    roads_geojson=roads_geojson  # NEW: Pass roads if available
)
```

---

## MapLibre Integration (Future)

If you want to integrate with MapLibre:

```python
def get_roads_from_maplibre(bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Query MapLibre/OSM for roads in bounding box.
    
    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat)
    
    Returns:
        GeoJSON FeatureCollection of roads
    """
    import requests
    
    # Use Overpass API to query OSM
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][bbox:{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}];
    (
      way["highway"];
    );
    out geom;
    """
    
    response = requests.post(overpass_url, data=query)
    # Convert OSM format to GeoJSON
    # ... implementation
```

---

## Immediate Action

**For now, I recommend:**

1. **You provide a road/street GeoJSON layer** from MapLibre
2. **I'll update the code** to accept it as input
3. **Rule 23 will use actual roads** instead of cable proxy

**Road layer format:**
```json
{
  "type": "FeatureCollection",
  "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32617"}},
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

---

## Next Steps

1. **You export road layer from MapLibre** as GeoJSON
2. **I'll update `generate_design.py`** to accept `--roads` parameter
3. **Rule 23 will use actual roads** for alignment checks
4. **This will fix the cross-country path issue**

Would you like me to:
- A) Update code to accept road layer input (recommended)
- B) Implement MapLibre integration
- C) Implement temporary filter (only use 144F+ cables as road proxy)
