# Design Generation Phase - Readiness Assessment

## ✅ What We Have (Sufficient for Design Generation)

### 1. **Complete Rule Set**
- **Placement Rules (R10-R14):**
  - R10: Aerial Terminal (1-12 ONTs, no stub, avg drop ≤150m)
  - R11: MST Short-Reach (≤500m stub, 6-24 ONTs)
  - R11: MST Long-Reach (500-2500m stub, 6-48 ONTs)
  - R12: FOSC Placement (≥2 cables OR ≥1800m OR ID change)
  - R13: FDH-FOSC Association
  - R14: Cable Hierarchy (288/144 → 96 → 48 → 12 → 1F)

### 2. **Cable Sizing Rules**
- Statistical thresholds for each fiber size (288F, 144F, 96F, 48F, 12F, 4F)
- ONT count ranges per cable size
- Transition logic between sizes
- Placement context (feeder/distribution/access)

### 3. **Distance & Capacity Baselines**
- Drop cable: median 90m, avg 115m
- Stub cable: median 212m, avg 308m
- Fiber cable: median 422m, avg 663m
- Terminal-to-FOSC ratios
- FOSC-to-FDH ratios

### 4. **Graph Structure Understanding**
- Node-link representation
- Relationship discovery
- Connectivity patterns

## ⚠️ What We Need (Gaps to Address)

### 1. **ONT Data Source & Integration**
**Question:** How to bring ONTs into the system?

**Options:**
- **Option A: Building Footprints from OSM**
  - MapLibre can display OSM tiles, but doesn't provide building data directly
  - Need to query Overpass API or use external service (e.g., Nominatim, Pelias)
  - Can extract building polygons and convert to ONT points
  
- **Option B: Address Points**
  - Use geocoding services (Google Maps, Mapbox, HERE)
  - Convert addresses to coordinates
  - Create ONT GeoJSON from address list
  
- **Option C: Manual Placement**
  - User clicks on map to place ONTs
  - Draw polygon → auto-generate ONT grid inside
  - Import CSV with lat/lon
  
- **Option D: Import Existing GeoJSON**
  - User uploads ONT.geojson file
  - System validates and uses it

**Recommendation:** Support all options, start with Option C (manual) + Option D (import)

### 2. **Design Generation Engine**
**Core Algorithm Needed:**
```
Input: 
  - Fiber cable route (LineString)
  - ONT locations (Point features in polygon)
  - Design constraints (optional)

Process:
  1. Segment fiber cable route
  2. For each segment:
     a. Count downstream ONTs
     b. Determine cable size (from rules)
     c. Identify FOSC placement points (R12)
     d. Identify Terminal placement (R10/R11)
     e. Calculate drop/stub cables
  3. Aggregate to FDH placement (R13)
  4. Connect to OLT (R14)
  5. Generate all GeoJSON layers

Output:
  - All layer GeoJSONs (ONT, Terminal, FOSC, FDH, OLT, cables)
  - BOM (Bill of Materials)
  - Design validation report
```

### 3. **Map Interface Requirements**
**MapLibre GL JS Setup:**
- ✅ MapLibre supports standard tile sources (OSM, Mapbox, etc.)
- ❌ MapLibre does NOT include building/residential tiles by default
- ✅ Can add custom layers (GeoJSON, vector tiles)

**What We Need:**
- Drawing tools (line for cable route, polygon for ONT area)
- ONT placement interface
- Design preview layer
- Export functionality

**Building Data Sources:**
- **OpenStreetMap Overpass API** (free, requires query)
- **Mapbox Building Tiles** (requires API key)
- **Google Maps Building Footprints** (requires API key)
- **Local building data** (import GeoJSON)

### 4. **BOM Generation**
**Required Calculations:**
- Total cable length by size (288F, 144F, etc.)
- Count of each component type (FOSC, Terminal, FDH, OLT)
- Drop cable lengths
- Stub cable lengths
- Splice closures count

## 📋 Recommended Implementation Plan

### Phase 1: Core Design Engine (Backend)
**Priority: HIGH**
1. Create `generate_design.py` module
2. Implement cable sizing logic (use `cable_sizing_rules.json`)
3. Implement FOSC placement (R12)
4. Implement Terminal placement (R10/R11)
5. Implement FDH placement (R13)
6. Generate GeoJSON outputs
7. Generate BOM

**Deliverables:**
- `generate_design.py`
- Test with sample inputs
- Output GeoJSON files matching input format

### Phase 2: Map Interface (Frontend)
**Priority: HIGH**
1. Set up MapLibre GL JS
2. Add drawing tools (line, polygon)
3. ONT placement interface:
   - Manual click-to-place
   - Polygon → grid generation
   - Import GeoJSON
   - Optional: OSM building query
4. Design preview layer
5. Export functionality

**Deliverables:**
- `index.html` with MapLibre
- Drawing tools
- ONT management UI

### Phase 3: Integration
**Priority: MEDIUM**
1. Connect frontend to backend (API or direct call)
2. Real-time design preview
3. Validation feedback
4. BOM display

### Phase 4: Enhanced Features
**Priority: LOW**
1. OSM building integration
2. Address geocoding
3. Design optimization
4. Cost estimation

## 🎯 Immediate Next Steps

### Step 1: Build Design Engine (1-2 days)
Create `generate_design.py` that:
- Takes fiber route + ONT points as input
- Applies all rules
- Generates complete design
- Outputs GeoJSON + BOM

### Step 2: Test with Sample Data (0.5 days)
- Create test input (simple route + ONT polygon)
- Run design engine
- Validate outputs match expected format

### Step 3: Build Basic Map Interface (1-2 days)
- MapLibre setup
- Drawing tools
- ONT placement
- Export to backend

### Step 4: Integration & Testing (1 day)
- Connect frontend ↔ backend
- End-to-end test
- Fix issues

## 🔧 Technical Stack Recommendations

### Backend
- Python (existing codebase)
- Flask/FastAPI for API (optional, can start with direct calls)
- GeoJSON generation (geojson library)

### Frontend
- MapLibre GL JS (map rendering)
- Mapbox GL Draw (drawing tools) - compatible with MapLibre
- Vanilla JS or React (UI framework)

### ONT Data Sources
- **Primary:** Manual placement + GeoJSON import
- **Secondary:** OSM Overpass API (for building footprints)
- **Future:** Address geocoding services

## ❓ Questions to Resolve

1. **ONT Placement Method:**
   - Start with manual placement?
   - Need OSM building integration immediately?
   - Have existing ONT data to import?

2. **Design Constraints:**
   - Any specific constraints beyond rules?
   - Cost optimization needed?
   - Preferred cable sizes?

3. **Output Format:**
   - Exact GeoJSON structure match required?
   - Additional metadata needed?
   - BOM format preference (JSON, CSV, PDF)?

## ✅ Conclusion

**We are READY to proceed** with design generation, but recommend:

1. **Start with Phase 1** (Design Engine) - can be built and tested independently
2. **Use manual ONT placement initially** - add OSM integration later
3. **Build minimal map interface first** - enhance with building data later

The rule set is comprehensive enough to generate valid designs. The main work is implementing the algorithm and building the interface.




