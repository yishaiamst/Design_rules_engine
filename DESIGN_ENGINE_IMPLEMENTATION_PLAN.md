# Design Engine Implementation Plan

## 📋 Current Status: Rules & Analysis Complete ✅

### What We Have Accomplished

#### 1. **Complete Rule Set (R10-R16)**
- ✅ **R10:** Aerial Terminal Placement (1-12 ONTs, no stub, avg drop ≤150m)
- ✅ **R11:** MST Placement (Short: ≤500m stub, 6-24 ONTs; Long: 500-2500m stub, 6-48 ONTs)
- ✅ **R12:** FOSC Placement (≥2 cables OR ≥1800m OR ID change OR fiber count transition)
- ✅ **R13:** FDH-FOSC Association (pair nearest FOSC within same chain)
- ✅ **R14:** Cable Hierarchy (288/144 → 96 → 48 → 12 → 1F cascade)
- ✅ **R15:** OLT-to-ONT Maximum Distance (20km hard limit)
- ✅ **R16:** OLT Placement Strategy (infrastructure-first: place near 288F/144F/96F routes, validate ONTs within 15-20km)

#### 2. **Cable Sizing Rules**
- ✅ Statistical thresholds for each fiber size (288F, 144F, 96F, 48F, 12F, 4F)
- ✅ ONT count ranges per cable size
- ✅ Transition logic between sizes
- ✅ Placement context (feeder/distribution/access)

#### 3. **Data Analysis & Baselines**
- ✅ Design intent extraction
- ✅ Cable transition analysis
- ✅ OLT placement pattern analysis
- ✅ Distance and capacity baselines
- ✅ Graph structure understanding
- ✅ ID relationship discovery

#### 4. **Reference Files**
- ✅ `design_rules_reference.json` - Consolidated rule catalog
- ✅ `cable_sizing_rules.json` - Cable sizing thresholds
- ✅ `olt_placement_rules.json` - OLT placement logic
- ✅ `adaptive_rules_summary.json` - Learned thresholds

---

## 🎯 Next Step: Build Design Generation Engine

### Input Files Required
1. **ONT.geojson** (or polygon with ONT points)
   - User provides: Polygon of residential area OR list of ONT coordinates
   - Format: GeoJSON FeatureCollection with Point geometries

2. **fiber cable.geojson** (fiber route infrastructure)
   - User provides: Main fiber cable routes (288F/144F/96F)
   - Format: GeoJSON FeatureCollection with LineString/MultiLineString geometries

### Output Files Generated
1. **All Design Layers (GeoJSON):**
   - `OLT.geojson` - Optical Line Terminals
   - `FDH.geojson` - Feeder Distribution Hubs
   - `FOSC.geojson` - Fiber Optic Splice Closures
   - `Terminal.geojson` - Aerial Terminals
   - `fiber cable.geojson` - Complete fiber cable network (with sizing)
   - `stub cable.geojson` - Stub cables (MST connections)
   - `drop cable.geojson` - Drop cables (ONT to Terminal)

2. **Bill of Materials (BOM):**
   - `bom.json` - Structured BOM data
   - `bom_summary.txt` - Human-readable summary

3. **Design Graph:**
   - `design_graph.json` - Logical connectivity graph
   - `design_metrics.json` - Design statistics

---

## 🏗️ Design Engine Architecture

### Core Module: `generate_design.py`

```python
"""
generate_design.py
Main design generation engine that applies all rules to create network design.
"""

def generate_design(ont_geojson, fiber_cable_geojson, output_dir="output"):
    """
    Main entry point for design generation.
    
    Steps:
    1. Load and validate input files
    2. Phase 1: OLT Placement (R15, R16)
    3. Phase 2: ONT Clustering & Terminal Placement (R10, R11)
    4. Phase 3: FOSC Placement (R12)
    5. Phase 4: FDH Placement (R13)
    6. Phase 5: Cable Sizing & Routing (R14, cable sizing rules)
    7. Phase 6: Generate BOM
    8. Phase 7: Export all layers
    """
    pass
```

### Phase Breakdown

#### **Phase 1: OLT Placement (R15, R16)**
```python
def place_olts(onts, fiber_routes):
    """
    1. Cluster ONTs into pockets (proximity-based)
    2. For each pocket:
       - Count ONTs
       - Find nearest main fiber route (288F/144F/96F)
       - Apply R16: Place OLT on/near fiber route
       - Validate R15: All ONTs within 20km
    3. Handle pocket merging (if pockets <15km apart)
    4. Validate merged pockets (diameter ≤15km)
    """
    pass
```

#### **Phase 2: ONT Clustering & Terminal Placement (R10, R11)**
```python
def place_terminals(onts, olt_locations):
    """
    1. For each OLT, group assigned ONTs
    2. Cluster ONTs by proximity (for terminal grouping)
    3. For each cluster:
       - Count ONTs (1-12 → Aerial Terminal, R10)
       - Check stub distance (if MST, R11)
       - Place Terminal or MST accordingly
    4. Create drop cables (ONT → Terminal)
    """
    pass
```

#### **Phase 3: FOSC Placement (R12)**
```python
def place_foscs(fiber_cables, terminals):
    """
    1. Analyze fiber cable network:
       - Identify junctions (≥2 cables)
       - Find long segments (≥1800m)
       - Detect cable ID changes
       - Detect fiber count transitions
    2. Place FOSC at each trigger point
    3. Create stub cables (Terminal → FOSC, if MST)
    """
    pass
```

#### **Phase 4: FDH Placement (R13)**
```python
def place_fdhs(olts, foscs):
    """
    1. For each OLT:
       - Group FOSCs by proximity
       - Place FDH near OLT or at strategic junction
    2. Associate FOSCs to FDHs (R13: nearest FOSC in same chain)
    3. Create feeder cables (FDH → FOSC)
    """
    pass
```

#### **Phase 5: Cable Sizing & Routing (R14, Cable Sizing Rules)**
```python
def size_and_route_cables(design_graph, cable_sizing_rules):
    """
    1. Build connectivity graph (OLT → FDH → FOSC → Terminal → ONT)
    2. For each cable segment:
       - Count downstream ONTs
       - Apply cable sizing rules (based on ONT count)
       - Determine cable size (288F/144F/96F/48F/12F)
    3. Ensure hierarchy (R14: 288/144 → 96 → 48 → 12 → 1F)
    4. Create fiber cable segments with proper sizing
    """
    pass
```

#### **Phase 6: Generate BOM**
```python
def generate_bom(design_layers):
    """
    1. Count all components:
       - OLTs, FDHs, FOSCs, Terminals
       - Cable lengths by size (288F, 144F, 96F, 48F, 12F, 4F, 1F)
    2. Calculate totals:
       - Total cable length per size
       - Total component counts
    3. Generate BOM files (JSON + text summary)
    """
    pass
```

#### **Phase 7: Export All Layers**
```python
def export_design(design_layers, output_dir):
    """
    1. Export each layer as GeoJSON:
       - OLT.geojson
       - FDH.geojson
       - FOSC.geojson
       - Terminal.geojson
       - fiber cable.geojson
       - stub cable.geojson
       - drop cable.geojson
    2. Export design graph and metrics
    3. Export BOM
    """
    pass
```

---

## 📐 Implementation Details

### Key Algorithms Needed

#### 1. **Spatial Clustering (ONT Pockets)**
- Use DBSCAN or hierarchical clustering
- Distance threshold: 2km for initial clustering
- Merge clusters if <15km apart (R16)

#### 2. **Nearest Point on Line (OLT Placement)**
- Find nearest point on fiber route to pocket centroid
- Use point-to-line-segment distance calculation
- Place OLT at that point (within 1km tolerance)

#### 3. **Downstream ONT Counting**
- Build directed graph (OLT → FDH → FOSC → Terminal → ONT)
- Use BFS/DFS to count all reachable ONTs from each node
- Cache results for performance

#### 4. **Cable Routing**
- Use existing fiber cable routes as backbone
- Extend routes to terminals/FOSCs as needed
- Follow road/utility infrastructure (if available)

#### 5. **Distance Validation**
- Haversine formula for geographic distances
- Validate all ONTs within 20km of assigned OLT
- Flag violations for review

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
   - Total cost estimate

---

## 📦 Dependencies

### Required Python Libraries
```python
import json
import math
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics

# Spatial operations
from shapely.geometry import Point, LineString, MultiLineString  # Optional but recommended
# OR implement custom distance calculations

# Clustering (optional)
from sklearn.cluster import DBSCAN  # Optional
# OR implement custom clustering
```

### Input Data Format
- GeoJSON (standard format)
- Coordinate system: EPSG:32617 (UTM Zone 17N) or WGS84 (lat/lon)

---

## 🚀 Implementation Steps

### Step 1: Create Core Structure
- [ ] Create `generate_design.py` with main function
- [ ] Create helper modules:
  - [ ] `olt_placement.py` - R15, R16 logic
  - [ ] `terminal_placement.py` - R10, R11 logic
  - [ ] `fosc_placement.py` - R12 logic
  - [ ] `fdh_placement.py` - R13 logic
  - [ ] `cable_sizing.py` - R14 + cable sizing rules
  - [ ] `bom_generator.py` - BOM generation
  - [ ] `export_utils.py` - GeoJSON export

### Step 2: Implement Phase 1 (OLT Placement)
- [ ] Load ONT and fiber cable data
- [ ] Implement ONT clustering
- [ ] Implement OLT placement (near fiber routes)
- [ ] Implement distance validation (R15)
- [ ] Test with sample data

### Step 3: Implement Phase 2 (Terminal Placement)
- [ ] Implement ONT-to-OLT assignment
- [ ] Implement terminal clustering
- [ ] Implement R10 (Aerial Terminal) logic
- [ ] Implement R11 (MST) logic
- [ ] Create drop cables

### Step 4: Implement Phase 3 (FOSC Placement)
- [ ] Analyze fiber cable network
- [ ] Implement R12 triggers (junction, length, ID change, transition)
- [ ] Place FOSCs
- [ ] Create stub cables

### Step 5: Implement Phase 4 (FDH Placement)
- [ ] Implement FDH placement (near OLTs)
- [ ] Implement R13 (FDH-FOSC association)
- [ ] Create feeder cables

### Step 6: Implement Phase 5 (Cable Sizing)
- [ ] Build connectivity graph
- [ ] Implement downstream ONT counting
- [ ] Apply cable sizing rules
- [ ] Ensure hierarchy (R14)

### Step 7: Implement Phase 6 & 7 (BOM & Export)
- [ ] Generate BOM
- [ ] Export all GeoJSON layers
- [ ] Export design graph and metrics

### Step 8: Testing & Validation
- [ ] Test with existing data (reverse engineering)
- [ ] Validate against known designs
- [ ] Fix bugs and edge cases
- [ ] Performance optimization

---

## 📊 Expected Output Example

### BOM Summary (Example)
```
Bill of Materials
================

OLTs: 3
FDHs: 5
FOSCs: 127
Terminals: 342
ONTs: 2,237

Cable Lengths:
  288F: 12.5 km
  144F: 45.3 km
  96F: 78.2 km
  48F: 123.5 km
  12F: 89.7 km
  4F: 34.1 km
  1F: 12.3 km

Total Fiber Cable: 395.6 km
```

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

1. **Review this plan** - Confirm approach and priorities
2. **Start with Phase 1** - Implement OLT placement (most critical)
3. **Iterate** - Build incrementally, test with each phase
4. **Validate** - Compare generated designs with existing data

---

## 📝 Notes

- **Coordinate System:** Ensure consistent coordinate system (UTM vs lat/lon)
- **Performance:** Consider spatial indexing (R-tree) for large datasets
- **Error Handling:** Robust error handling for edge cases
- **Logging:** Detailed logging for debugging and validation
- **Documentation:** Code comments and docstrings for maintainability

---

**Ready to proceed?** Let's start with Phase 1 (OLT Placement) implementation!



