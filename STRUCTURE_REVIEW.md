# Design Engine Structure Review

## 📁 Current Project Structure

```
Design_rules_engine/
├── generate_design.py          # Main entry point
├── design_config.json          # Configuration file
│
├── utils/                      # Utility modules
│   ├── config_loader.py        # Configuration loading
│   ├── geojson_utils.py        # GeoJSON I/O
│   ├── spatial_utils.py        # Spatial calculations
│   └── graph_utils.py          # Graph operations
│
├── phases/                     # Implementation phases (to be created)
│   ├── phase1_cable_extension.py
│   ├── phase2_community_pockets.py
│   ├── phase3_olt_placement.py
│   ├── phase4_fdh_placement.py
│   ├── phase5_fosc_placement.py
│   ├── phase6_terminal_placement.py
│   ├── phase7_cable_sizing.py
│   └── phase8_bom_generation.py
│
└── validation/                 # Validation modules (to be created)
    └── validate_design.py
```

---

## 📄 File Details

### **1. generate_design.py** (Main Entry Point)

**Purpose:** Main orchestrator for design generation

**Key Functions:**
- `generate_design()` - Main function that coordinates all phases
- `main()` - Command-line interface

**Current Status:**
- ✅ Structure in place
- ✅ Configuration loading
- ✅ Input data loading
- ✅ Phase placeholders (8 phases)
- ⏳ Phase implementations pending

**Command-Line Usage:**
```bash
python3 generate_design.py --onts ONT.geojson --cables "fiber cable.geojson" --config design_config.json --output output/
```

---

### **2. utils/config_loader.py**

**Purpose:** Load and access configuration from `design_config.json`

**Key Functions:**
- `load_config()` - Load configuration file
- `get_equipment_config()` - Get equipment configuration by type and model
- `get_service_config()` - Get service configuration
- `get_cable_config()` - Get cable configuration
- `get_placement_config()` - Get placement thresholds
- `get_mst_config()` - Get MST configuration
- `get_olt_config()` - Get OLT configuration

**Example Usage:**
```python
config = load_config("design_config.json")
mst_config = get_mst_config(config, "MST4")
# Returns: {"ports": 4, "stub_cable_size": 4, ...}
```

**Status:** ✅ Complete

---

### **3. utils/geojson_utils.py**

**Purpose:** GeoJSON file I/O and manipulation

**Key Functions:**
- `load_geojson()` - Load GeoJSON file
- `save_geojson()` - Save GeoJSON to file
- `create_feature()` - Create a GeoJSON feature
- `create_feature_collection()` - Create FeatureCollection
- `extract_points()` - Extract point coordinates from GeoJSON
- `extract_linestrings()` - Extract LineString coordinates
- `get_feature_by_id()` - Find feature by ID

**Example Usage:**
```python
geojson = load_geojson("ONT.geojson")
points = extract_points(geojson)
# Returns: [(x1, y1, props1), (x2, y2, props2), ...]
```

**Status:** ✅ Complete

---

### **4. utils/spatial_utils.py**

**Purpose:** Spatial calculations and geometric operations

**Key Functions:**
- `haversine_distance()` - Calculate distance between two lat/lon points (km)
- `euclidean_distance()` - Calculate Euclidean distance (same units)
- `point_to_line_distance()` - Distance from point to line segment
- `point_to_linestring_distance()` - Distance from point to LineString
- `calculate_centroid()` - Calculate centroid of point set
- `calculate_bounding_box()` - Calculate bounding box
- `calculate_diameter()` - Calculate maximum distance between points
- `simple_cluster()` - Distance-based clustering (DBSCAN-like)

**Example Usage:**
```python
distance = haversine_distance(lat1, lon1, lat2, lon2)
centroid = calculate_centroid([(x1, y1), (x2, y2), ...])
clusters = simple_cluster(points, radius=2000.0)
```

**Status:** ✅ Complete

---

### **5. utils/graph_utils.py**

**Purpose:** Graph building and traversal operations

**Key Functions:**
- `build_adjacency_graph()` - Build adjacency list from edges
- `bfs_traverse()` - Breadth-first search traversal
- `count_downstream_nodes()` - Count downstream nodes of specific type
- `precompute_downstream_counts()` - Pre-compute all downstream counts
- `find_path()` - Find path between two nodes

**Example Usage:**
```python
graph = build_adjacency_graph(edges)
downstream_onts = count_downstream_nodes(graph, "F1000123", "ont")
cache = precompute_downstream_counts(graph, "ont")
```

**Status:** ✅ Complete

---

## 🔧 Configuration File: design_config.json

**Structure:**
```json
{
  "equipment": {
    "mst": { "MST4": {...}, "MST6": {...}, ... },
    "aerial_terminal": { "AER-TRM4": {...}, ... },
    "fosc": { "FOSC-12": {...}, ... },
    "fdh": { "FDH-288": {...}, ... },
    "olt": { "OLT-8P-1G": {...}, ... }
  },
  "service": {
    "service_per_ont_gbps": 1.0,
    "olt_port_capacity_gbps": 1.0,
    "oversubscription_ratios": [8, 16, 32, 64],
    "default_oversubscription": 32,
    "max_subscribers_per_port": 256,
    "future_growth_percentage": 10.0
  },
  "cables": {
    "drop_cable": { "default_size": 1 },
    "stub_cable": { "based_on_mst_type": true },
    "infrastructure_cable": { "standard_sizes": [12, 24, 48, 72, 96, 144, 288] }
  },
  "placement": {
    "olt": { "max_distance_to_ont_km": 20.0, ... },
    "terminal": { "fosc_proximity_threshold_m": 1000, ... },
    "fosc": { "min_segment_length_m": 1800, ... }
  }
}
```

**Status:** ✅ Complete and validated

---

## 📋 Implementation Phases (To Be Created)

### **Phase 1: Infrastructure Cable Extension**
**File:** `phases/phase1_cable_extension.py`
**Function:** `analyze_cable_extension(onts, existing_cables, config)`
**Output:** Extended cable network (geometry only, no sizes)

### **Phase 2: Community Pockets**
**File:** `phases/phase2_community_pockets.py`
**Function:** `create_community_pockets(onts, extended_cables, config)`
**Output:** List of community pockets with metadata

### **Phase 3: OLT Placement**
**File:** `phases/phase3_olt_placement.py`
**Function:** `place_olts(community_pockets, extended_cables, config)`
**Output:** OLT.geojson, OLT-to-ONT assignments

### **Phase 4: FDH Placement**
**File:** `phases/phase4_fdh_placement.py`
**Function:** `place_fdhs(olts, extended_cables, config)`
**Output:** FDH.geojson, FDH-to-OLT associations

### **Phase 5: FOSC Placement**
**File:** `phases/phase5_fosc_placement.py`
**Function:** `place_foscs(extended_cables, fdhs, config)`
**Output:** splice closure.geojson, FOSC-to-FDH associations

### **Phase 6: Terminal Placement**
**File:** `phases/phase6_terminal_placement.py`
**Function:** `place_terminals(onts, olt_assignments, extended_cables, foscs, config)`
**Output:** Terminal.geojson, drop cable.geojson, stub cable.geojson

### **Phase 7: Cable Sizing**
**File:** `phases/phase7_cable_sizing.py`
**Function:** `size_cables(design_graph, terminals, foscs, fdhs, olts, config)`
**Output:** Updated fiber cable.geojson (with sizes)

### **Phase 8: BOM Generation**
**File:** `phases/phase8_bom_generation.py`
**Function:** `generate_bom(design_layers, config)`
**Output:** bom.json, bom_summary.txt

---

## 🔄 Data Flow

```
INPUT:
  ONT.geojson (Point features)
  fiber cable.geojson (MultiLineString, NO SIZE)

↓ Phase 1: Cable Extension
  Extended cable network (geometry only)

↓ Phase 2: Community Pockets
  Community pockets (clustered ONTs)

↓ Phase 3: OLT Placement
  OLT.geojson, OLT-to-ONT assignments

↓ Phase 4: FDH Placement
  FDH.geojson, FDH-to-OLT associations

↓ Phase 5: FOSC Placement
  splice closure.geojson, FOSC-to-FDH associations

↓ Phase 6: Terminal Placement
  Terminal.geojson, drop cable.geojson, stub cable.geojson

↓ Phase 7: Cable Sizing
  Updated fiber cable.geojson (WITH SIZES)

↓ Phase 8: BOM Generation
  bom.json, bom_summary.txt

OUTPUT:
  All design layers (GeoJSON with sizes)
  BOM files
  Validation report
```

---

## ✅ Current Status Summary

### **Completed:**
- ✅ Core structure and module organization
- ✅ Configuration loading system
- ✅ GeoJSON I/O utilities
- ✅ Spatial calculation utilities
- ✅ Graph building and traversal utilities
- ✅ Main entry point with CLI
- ✅ Configuration file validated

### **Pending Implementation:**
- ⏳ Phase 1: Cable Extension Analysis
- ⏳ Phase 2: Community Pockets
- ⏳ Phase 3: OLT Placement
- ⏳ Phase 4: FDH Placement
- ⏳ Phase 5: FOSC Placement
- ⏳ Phase 6: Terminal Placement
- ⏳ Phase 7: Cable Sizing
- ⏳ Phase 8: BOM Generation
- ⏳ Validation module

---

## 🎯 Design Decisions

### **1. Modular Architecture**
- Each phase is a separate module for maintainability
- Utilities are separated from business logic
- Clear separation of concerns

### **2. Configuration-Driven**
- All parameters configurable via `design_config.json`
- No hardcoded values
- Easy to adjust for different scenarios

### **3. State Management**
- `design_state` dictionary tracks all intermediate results
- Each phase adds to the state
- Final state contains complete design

### **4. Error Handling**
- File existence checks
- JSON validation
- Graceful error messages

### **5. Coordinate System**
- Utilities support both UTM and lat/lon
- Haversine for geographic distances
- Euclidean for projected coordinates

---

## 📊 Testing Strategy

### **Unit Tests (To Be Created):**
- Test each utility function independently
- Test configuration loading
- Test spatial calculations
- Test graph operations

### **Integration Tests:**
- Test each phase with sample data
- Test phase dependencies
- Test end-to-end flow

### **Validation Tests:**
- Compare generated design with existing data
- Validate rule compliance
- Check distance constraints
- Verify cable sizing

---

## 🔍 Code Quality

### **Strengths:**
- ✅ Clear module separation
- ✅ Comprehensive utility functions
- ✅ Configuration-driven design
- ✅ Type hints in function signatures
- ✅ Docstrings for all functions
- ✅ Error handling

### **Areas for Enhancement:**
- ⏳ Add unit tests
- ⏳ Add logging framework
- ⏳ Add progress indicators
- ⏳ Add validation checks
- ⏳ Add performance optimization (spatial indexing)

---

## 🚀 Next Steps

1. **Review this structure** - Confirm approach
2. **Implement Phase 1** - Cable Extension Analysis
3. **Test incrementally** - Validate each phase
4. **Continue through all phases** - Build complete engine

---

## 📝 Notes

- All utilities are pure functions (no side effects)
- Configuration is loaded once and passed through phases
- GeoJSON format matches existing data structure
- Coordinate system should be consistent (UTM or lat/lon)
- Performance considerations: May need spatial indexing (R-tree) for large datasets

---

**Status: Structure reviewed and ready for phase implementation!** ✅



