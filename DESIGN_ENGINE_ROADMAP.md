# Design Engine Implementation Roadmap

## ✅ Current Status: Rules Complete & Enhanced

### Completed Work
- ✅ **All Rules Defined (R10-R16)** with enhanced FOSC proximity logic
- ✅ **Cable Sizing Rules** - Statistical thresholds and decision logic
- ✅ **OLT Placement Strategy** - Infrastructure-first approach
- ✅ **Terminal Placement Logic** - Enhanced with FOSC proximity (≤1km threshold)
- ✅ **Design Rules Reference** - Consolidated and up-to-date
- ✅ **Data Analysis** - Baselines, patterns, and validation complete

### Enhanced Rules Summary
- **R10:** Aerial Terminal - Use when FOSC >1km away (mid-cable splicing acceptable)
- **R11:** MST - Use when FOSC ≤1km away (maximize FOSC splicing)
- **R12:** FOSC Placement - Junction, length, ID change, or transition
- **R13:** FDH-FOSC Association - Pair nearest FOSC in same chain
- **R14:** Cable Hierarchy - 288/144 → 96 → 48 → 12 → 1F cascade
- **R15:** OLT-ONT Max Distance - 20km hard limit
- **R16:** OLT Placement - Near main infrastructure (288F/144F/96F), validate ONTs within 15-20km

---

## 🎯 Next Step: Build Design Generation Engine

### Goal
Create `generate_design.py` that takes:
- **Input:** ONT locations (GeoJSON) + Fiber cable routes (GeoJSON)
- **Output:** Complete network design (all layers) + BOM

---

## 📋 Implementation Phases (Refined Order)

### **Phase 0: Create Community Pockets** ⭐ START HERE
**Priority: HIGH | Estimated Time: 2-3 hours**

#### Tasks:
1. **Create Community Pockets**
   - [ ] Cluster ONTs by proximity (2km radius)
   - [ ] Merge pockets if <15km apart
   - [ ] Validate merged pocket diameter (≤15km)
   - [ ] Split oversized pockets
   - [ ] Assign pocket metadata

**Deliverable:** Extended infrastructure network, community pockets

---

### **Phase 1: OLT Placement** 
**Priority: HIGH | Estimated Time: 4-6 hours**

#### Tasks:
1. **Create core module structure**
   - [ ] Create `generate_design.py` with main function
   - [ ] Create helper modules:
     - [ ] `utils/spatial_utils.py` - Distance calculations, point-to-line, clustering
     - [ ] `utils/geojson_utils.py` - Load/save GeoJSON, coordinate conversion
     - [ ] `utils/graph_utils.py` - Graph building, pathfinding, downstream counting

2. **Implement OLT Placement (R15, R16)**
   - [ ] Load ONT and fiber cable data
   - [ ] Cluster ONTs into pockets (2km radius, merge if <15km apart)
   - [ ] For each pocket:
     - [ ] Count ONTs
     - [ ] Find nearest main fiber route (288F/144F/96F)
     - [ ] Place OLT on/near fiber route (<1km)
     - [ ] Validate all ONTs within 20km (R15)
   - [ ] Handle pocket merging and diameter validation
   - [ ] Generate `OLT.geojson`

3. **Test Phase 1**
   - [ ] Test with sample data (100-500 ONTs)
   - [ ] Validate OLT placement against rules
   - [ ] Check distance constraints

**Deliverable:** OLT placement working, validated against R15/R16

---

### **Phase 2: FDH Placement (R13)**
**Priority: MEDIUM | Estimated Time: 2-3 hours**

#### Tasks:
1. **FDH Placement**
   - [ ] For each OLT:
     - [ ] Find associated infrastructure cables
     - [ ] Place FDH near OLT or at strategic junction
     - [ ] Assign unique FDH IDs (FDH*)
   - [ ] Link FDHs to OLTs

**Deliverable:** FDH placement complete

---

### **Phase 3: FOSC Placement (R12)**
**Priority: HIGH | Estimated Time: 3-4 hours**

#### Tasks:
1. **Analyze Extended Cable Network**
   - [ ] Identify junctions (≥2 cables meet)
   - [ ] Find long segments (≥1800m)
   - [ ] Detect cable ID changes
   - [ ] Note: Fiber count transitions determined later (after sizing)

2. **Place FOSCs**
   - [ ] Place FOSC at each trigger point (R12)
   - [ ] Assign unique FOSC IDs (F*)
   - [ ] Associate FOSCs to FDHs (R13)

**Deliverable:** FOSC placement complete

---

### **Phase 4: Terminal Placement (R10, R11 Enhanced)**
**Priority: HIGH | Estimated Time: 3-4 hours**

#### Tasks:
1. **ONT-to-OLT Assignment**
   - [ ] Assign each ONT to nearest OLT (within 20km)
   - [ ] Group ONTs by assigned OLT

2. **Terminal Placement Logic**
   - [ ] For each OLT's ONT group:
     - [ ] Cluster ONTs by proximity (for terminal grouping)
     - [ ] For each cluster:
       - [ ] Find nearest infrastructure cable
       - [ ] Find nearest FOSC
       - [ ] Calculate distances
       - [ ] Apply enhanced decision logic:
         - **IF FOSC ≤1km → Use MST** (R11)
         - **ELIF infrastructure <50m AND FOSC >1km → Use Aerial Terminal** (R10)
         - **ELIF infrastructure ≥200m → Use MST** (R11)
       - [ ] Select MST type based on ONT count (MST4/6/8/12)
   - [ ] Create terminal features (Aerial or MST)

3. **Generate Terminal Layer**
   - [ ] Generate `Terminal.geojson`

**Deliverable:** Terminal placement working with enhanced FOSC proximity logic

---

### **Phase 5: Cable Extensions (Drop & Stub Cables)**
**Priority: HIGH | Estimated Time: 2-3 hours**

#### Tasks:
1. **Create Drop Cables**
   - [ ] For each Terminal:
     - [ ] Identify connected ONTs
     - [ ] Calculate drop cable routes (Terminal → ONT)
     - [ ] Determine drop cable length
     - [ ] Create drop cable features (1F default, configurable)

2. **Create Stub Cables**
   - [ ] For each MST Terminal:
     - [ ] Find connected FOSC
     - [ ] Calculate stub cable route (Terminal → FOSC)
     - [ ] Determine stub cable length
     - [ ] Get stub cable size from MST type (MST4=4F, MST6=6F, etc.)
     - [ ] Create stub cable features

3. **Validate Cable Lengths**
   - [ ] Drop cables: Validate average ≤150m
   - [ ] Stub cables: Validate ≤500m (standard) or ≤2500m (long-reach)

4. **Generate Cable Layers**
   - [ ] Generate `drop cable.geojson`
   - [ ] Generate `stub cable.geojson`

**Deliverable:** Drop and stub cables created

**Note:** Advanced infrastructure cable extensions (to improve service) are a placeholder for future optimization.

---


---

### **Phase 6: Cable Sizing & Routing (R14)**
**Priority: HIGH | Estimated Time: 4-5 hours**

#### Tasks:
1. **Build Connectivity Graph**
   - [ ] Build complete graph: OLT → FDH → FOSC → Terminal → ONT
   - [ ] Pre-compute downstream ONT counts for each node

2. **Apply Cable Sizing Rules**
   - [ ] Load `cable_sizing_rules.json`
   - [ ] For each cable segment:
     - [ ] Count downstream ONTs
     - [ ] Determine cable type (infrastructure/stub/drop)
     - [ ] Apply sizing logic:
       - **Infrastructure:** Multiples of 12F only (12, 24, 48, 72, 96, 144, 288)
       - **Stub:** 1F, 4F, or multiples of 12F
       - **Drop:** 1F or 4F
     - [ ] Assign cable size based on ONT count
   - [ ] Ensure hierarchy (R14: 288/144 → 96 → 48 → 12 → 1F)
   - [ ] Validate transitions (can only downsize, not upsize)

3. **Update Fiber Cables**
   - [ ] Update all fiber cables with proper sizing
   - [ ] Add size property to each cable feature
   - [ ] Update `fiber cable.geojson` (now with sizes)

4. **Create Stub and Drop Cables**
   - [ ] Size stub cables (MST → FOSC)
   - [ ] Size drop cables (ONT → Terminal)
   - [ ] Generate `stub cable.geojson` and `drop cable.geojson`

**Deliverable:** All cables sized correctly, hierarchy maintained

---

### **Phase 7: BOM Generation**
**Priority: MEDIUM | Estimated Time: 2-3 hours**

#### Tasks:
1. **Count Components**
   - [ ] Count OLTs, FDHs, FOSCs, Terminals, ONTs
   - [ ] Calculate cable lengths by size (288F, 144F, 96F, 48F, 12F, 4F, 1F)
   - [ ] Calculate drop cable lengths
   - [ ] Calculate stub cable lengths

2. **Generate BOM Files**
   - [ ] Generate `bom.json` (structured data)
   - [ ] Generate `bom_summary.txt` (human-readable)

**Deliverable:** BOM generation working

---

### **Phase 8: Export & Validation**
**Priority: HIGH | Estimated Time: 3-4 hours**

#### Tasks:
1. **Export All Layers**
   - [ ] Export all GeoJSON layers (matching existing format)
   - [ ] Export design graph (`design_graph.json`)
   - [ ] Export design metrics (`design_metrics.json`)

2. **Validation**
   - [ ] Rule compliance check (all R10-R16)
   - [ ] Distance validation (R15)
   - [ ] Connectivity validation (all ONTs reach OLT)
   - [ ] Generate validation report

3. **Testing**
   - [ ] Test with existing data (reverse engineering)
   - [ ] Compare generated vs actual design
   - [ ] Calculate accuracy metrics
   - [ ] Fix bugs and edge cases

**Deliverable:** Complete design engine, validated and tested

---

## 🏗️ Module Structure

```
generate_design.py          # Main entry point
├── phases/
│   ├── phase1_olt_placement.py
│   ├── phase2_terminal_placement.py
│   ├── phase3_fosc_placement.py
│   ├── phase4_fdh_placement.py
│   ├── phase5_cable_sizing.py
│   └── phase6_bom_generation.py
├── utils/
│   ├── spatial_utils.py    # Distance, clustering, point-to-line
│   ├── geojson_utils.py    # Load/save GeoJSON
│   ├── graph_utils.py      # Graph building, pathfinding
│   └── rule_loader.py      # Load rules from JSON files
└── validation/
    └── validate_design.py  # Rule compliance, connectivity checks
```

---

## 📊 Key Algorithms Needed

### 1. **Spatial Clustering (ONT Pockets)**
```python
def cluster_onts(onts, radius_km=2.0):
    """
    Cluster ONTs into pockets using DBSCAN or hierarchical clustering.
    Merge clusters if <15km apart (R16).
    """
    pass
```

### 2. **Nearest Point on Line (OLT Placement)**
```python
def find_nearest_point_on_line(point, line):
    """
    Find nearest point on fiber route to pocket centroid.
    Place OLT at that point (within 1km tolerance).
    """
    pass
```

### 3. **Downstream ONT Counting**
```python
def count_downstream_onts(node_id, graph):
    """
    Count all reachable ONTs from a node using BFS/DFS.
    Cache results for performance.
    """
    pass
```

### 4. **FOSC Proximity Decision (Enhanced R10/R11)**
```python
def choose_terminal_type(onts, infrastructure_cable, foscs):
    """
    Enhanced decision logic:
    - IF FOSC ≤1km → MST
    - ELIF infrastructure <50m AND FOSC >1km → Aerial Terminal
    - ELIF infrastructure ≥200m → MST
    """
    pass
```

---

## 🧪 Testing Strategy

### Test Cases

1. **Simple Case:**
   - 100 ONTs in 5km × 5km area
   - One 288F fiber route passing through
   - Expected: 1 OLT, multiple terminals, FOSCs, FDH

2. **Complex Case:**
   - 2000 ONTs spread over 20km × 20km
   - Multiple fiber routes (288F, 144F, 96F)
   - Expected: Multiple OLTs, complex hierarchy

3. **Edge Cases:**
   - Isolated community (>15km from others)
   - Very dense cluster (all ONTs within 1km)
   - Linear distribution (ONTs along a road)

### Validation

1. **Rule Compliance:**
   - All R10-R16 rules satisfied
   - Cable hierarchy maintained
   - Distance constraints met

2. **Connectivity:**
   - All ONTs connected to OLT
   - No orphaned components
   - Valid graph structure

3. **BOM Accuracy:**
   - Component counts match design
   - Cable lengths reasonable

---

## 📦 Dependencies

### Required Python Libraries
```python
import json
import math
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics

# Optional but recommended:
# from shapely.geometry import Point, LineString, MultiLineString
# from sklearn.cluster import DBSCAN
```

---

## 🚀 Recommended Implementation Order

1. **Week 1: Phase 0-1 (Community Pockets & OLT Placement)**
   - Community pocketing logic
   - OLT placement logic
   - Testing and validation

2. **Week 2: Phase 2-3 (FDH & FOSC Placement)**
   - FDH placement
   - FOSC placement
   - Associations

3. **Week 3: Phase 4-5 (Terminal Placement & Cable Extensions)**
   - Enhanced R10/R11 logic
   - Terminal placement
   - Drop cables (Terminal → ONT)
   - Stub cables (MST → FOSC)

4. **Week 4: Phase 6-8 (Cable Sizing, BOM, Export)**
   - Cable sizing
   - BOM generation
   - Export and validation

---

## ✅ Success Criteria

1. **Functional:**
   - Engine generates complete design from inputs
   - All rules (R10-R16) are applied correctly
   - All output layers are valid GeoJSON
   - BOM is accurate and complete

2. **Quality:**
   - Design is realistic and deployable
   - Cable sizing is appropriate
   - Distance constraints are met
   - Connectivity is valid

3. **Performance:**
   - Handles 1000+ ONTs in reasonable time (<5 minutes)
   - Memory usage is reasonable
   - Output files are manageable size

---

## 🎯 Next Actions

1. **✅ Rules Updated** - Enhanced R10/R11 with FOSC proximity logic
2. **⏭️ Start Phase 1** - Implement OLT placement (most critical)
3. **📝 Iterate** - Build incrementally, test with each phase
4. **✅ Validate** - Compare generated designs with existing data

---

## 📝 Notes

- **Coordinate System:** Ensure consistent coordinate system (UTM vs lat/lon)
- **Performance:** Consider spatial indexing (R-tree) for large datasets
- **Error Handling:** Robust error handling for edge cases
- **Logging:** Detailed logging for debugging and validation
- **Documentation:** Code comments and docstrings for maintainability

---

**Ready to start Phase 1?** Let's begin with OLT placement implementation! 🚀

