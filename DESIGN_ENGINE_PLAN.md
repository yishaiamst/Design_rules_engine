# Design Engine Implementation Plan

## Query 1: OLT Placement Rules

### Current Status
- ✅ We have OLT placement pattern (PATTERN_OLT_FEEDER_ROOT)
- ❌ **NO distance constraint rules** (max OLT-to-ONT distance)
- ⚠️ Current data shows max chain length: **31.7 km** (exceeds 20km limit)

### Required Rules to Add

#### R15: OLT-to-ONT Maximum Distance
- **Rule:** Maximum path length from OLT to any ONT ≤ 20 km
- **Validation:** Check all ONT paths in `olt_ont_paths.json`
- **Action:** If path exceeds 20km, need additional OLT placement

#### R16: OLT Placement Strategy
- **Rule:** Place OLTs near large communities (≥2000 residential units)
- **Logic:**
  1. Cluster ONTs by proximity (e.g., 2km radius)
  2. Count ONTs per cluster
  3. If cluster ≥ 2000 ONTs → place OLT at cluster centroid
  4. If cluster < 2000 ONTs → assign to nearest OLT (within 20km)
- **Fallback:** If no large cluster, place OLTs to minimize max distance

### Implementation Steps
1. Analyze existing `olt_ont_paths.json` to find paths > 20km
2. Add R15 and R16 to `design_rules_reference.json`
3. Create `analyze_olt_placement.py` to validate and suggest OLT locations
4. Integrate into design engine

---

## Query 2: Input Method for Design Engine

### Recommended Approach: **Option B - Reverse Engineering with Existing Data**

**Why this is better:**
- ✅ We have both input (ONT.geojson, fiber cable.geojson) and output (all layers)
- ✅ Can validate engine accuracy by comparing generated vs actual
- ✅ Faster iteration - no UI needed initially
- ✅ Can refine rules before building map interface
- ✅ Easier to debug and test

### Implementation Strategy

#### Phase 1: Design Engine (Backend Only)
**Input:** Existing GeoJSON files
- `ONT.geojson` (or polygon with ONT points)
- `fiber cable.geojson` (fiber route)

**Process:**
1. Load input GeoJSON files
2. Apply all design rules (R10-R16)
3. Generate all output layers:
   - Terminal.geojson
   - FOSC.geojson
   - FDH.geojson
   - OLT.geojson
   - Drop cable.geojson
   - Stub cable.geojson
   - (Updated) fiber cable.geojson

**Output:**
- All layer GeoJSON files (matching your format)
- BOM (Bill of Materials)
- Validation report (comparing generated vs actual)

**Validation:**
- Compare generated design vs your actual design files
- Calculate accuracy metrics (placement matches, cable sizing matches)
- Identify rule gaps or issues

#### Phase 2: Map Interface (After Engine Validated)
Once engine is validated and accurate:
- Build MapLibre interface
- Add drawing tools (line for cable, polygon for ONT area)
- Export drawn features to GeoJSON
- Feed to design engine
- Display generated design on map

### Input Format Options

#### Option A: Use Existing Files Directly
```python
# Load your existing files
onts = load_geojson("ONT.geojson")
fiber_cables = load_geojson("fiber cable.geojson")

# Generate design
design = generate_design(onts, fiber_cables)
```

#### Option B: Simplified Input (for testing)
```python
# Simplified input format
input_data = {
    "fiber_route": {
        "type": "LineString",
        "coordinates": [[lon1, lat1], [lon2, lat2], ...]
    },
    "onts": {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}},
            ...
        ]
    }
}
```

#### Option C: Polygon + Route (for future map interface)
```python
# What user will draw on map
input_data = {
    "fiber_route": LineString,  # User draws cable route
    "ont_polygon": Polygon,     # User draws area with ONTs
    "ont_density": 50           # ONTs per km² (or specific ONT points)
}
```

---

## Proposed Implementation Plan

### Step 1: Add OLT Distance Rules (1-2 hours)
- [ ] Create `analyze_olt_distances.py`
- [ ] Analyze `olt_ont_paths.json` for paths > 20km
- [ ] Add R15 and R16 to rules
- [ ] Update `design_rules_reference.json`

### Step 2: Build Design Engine Core (2-3 days)
- [ ] Create `generate_design.py`
- [ ] Implement cable sizing logic (use `cable_sizing_rules.json`)
- [ ] Implement FOSC placement (R12)
- [ ] Implement Terminal placement (R10/R11)
- [ ] Implement FDH placement (R13)
- [ ] Implement OLT placement (R15/R16)
- [ ] Generate all GeoJSON outputs
- [ ] Generate BOM

### Step 3: Validation & Testing (1-2 days)
- [ ] Test with your existing input files
- [ ] Compare generated vs actual outputs
- [ ] Calculate accuracy metrics
- [ ] Refine rules based on differences
- [ ] Iterate until acceptable accuracy

### Step 4: Map Interface (After validation) (2-3 days)
- [ ] Set up MapLibre GL JS
- [ ] Add drawing tools (Mapbox GL Draw)
- [ ] ONT placement interface
- [ ] Export to GeoJSON
- [ ] Connect to design engine
- [ ] Display generated design

---

## File Structure

```
Design_rules_engine/
├── generate_design.py          # Main design engine
├── analyze_olt_distances.py    # OLT distance analysis
├── validate_design.py          # Compare generated vs actual
├── rules/
│   ├── design_rules_reference.json
│   ├── cable_sizing_rules.json
│   └── adaptive_rules_summary.json
├── inputs/                     # Test input files
│   ├── ONT.geojson
│   └── fiber cable.geojson
├── outputs/                    # Generated designs
│   ├── Terminal.geojson
│   ├── FOSC.geojson
│   ├── FDH.geojson
│   ├── OLT.geojson
│   └── bom.json
└── validation/                 # Comparison results
    └── accuracy_report.json
```

---

## Next Steps

**Immediate:**
1. ✅ Add OLT distance rules (R15, R16)
2. ✅ Start building `generate_design.py`
3. ✅ Test with existing files

**After validation:**
4. Build map interface
5. Add drawing tools
6. Integrate with engine

---

## Questions to Confirm

1. **OLT Placement:**
   - Confirm 20km max distance?
   - Confirm 2000 ONT threshold for OLT placement?
   - Any other OLT placement constraints?

2. **Input Format:**
   - Should we start with your existing GeoJSON files?
   - Or create simplified test inputs first?

3. **Validation Criteria:**
   - What accuracy threshold is acceptable? (e.g., 80% component placement match?)
   - Which aspects are most critical? (cable sizing, component placement, distances?)




