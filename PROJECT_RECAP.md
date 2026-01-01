# 📋 PROJECT RECAP - Fiber Network Design Engine

## 🎯 Project Goal
Build an automated fiber network design engine that takes:
- **Input:** ONT locations (points/polygons) + Fiber cable routes (geometry only, no sizes)
- **Output:** Complete network design (all components) + Bill of Materials (BOM)

---

## ✅ COMPLETED PHASES

### **Phase 0: Community Pockets** ✅
**File:** `phases/phase0_community_pockets.py`
- Clusters ONTs into community pockets
- Merges nearby pockets (<15km apart)
- Validates pocket diameter (configurable, default 50km with warning mode)
- Splits oversized pockets recursively
- **Result:** Creates logical groupings for OLT placement

### **Phase 1: Place OLTs** ✅
**File:** `phases/phase1_place_olts.py`
- Places OLTs based on community pockets
- Finds nearest infrastructure cables (288F/144F/96F routes)
- Places OLT on/near fiber route (within 1km) or at ONT centroid
- Validates all ONTs within 25km max distance
- Calculates required cable sizes using formula:
  - Service per ONT, OLT port capacity, oversubscription, growth, 256 ONT/port limit
- **Output:** OLT GeoJSON + placement summary

### **Phase 2: Place FOSCs (Initial - Geometry-Based)** ✅
**File:** `phases/phase2_place_foscs.py`
- Detects cable junctions (≥2 cables intersect, 10m tolerance)
- Detects long segments (≥1800m)
- Places FOSC at each trigger point
- Merges nearby FOSCs (within 50m)
- Assigns FOSC IDs (F0000001, F0000002, etc.)
- **Output:** Initial FOSC GeoJSON (geometry-based only)
- **Note:** Phase 6b will refine based on cable IDs and sizes

---

## 📁 PROJECT STRUCTURE

```
Design_rules_engine/
├── generate_design.py          # Main entry point
├── design_config.json          # Configuration (equipment, service, cables, placement)
├── phases/
│   ├── phase0_community_pockets.py  ✅
│   ├── phase1_place_olts.py         ✅
│   └── phase2_place_foscs.py        ✅
├── utils/
│   ├── config_loader.py        # Load configuration
│   ├── geojson_utils.py        # GeoJSON I/O
│   ├── spatial_utils.py        # Distance, clustering, geometry
│   └── graph_utils.py          # Graph building/traversal
└── [analysis scripts]          # Rule discovery/analysis
```

---

## 🔧 CONFIGURATION (`design_config.json`)

### Equipment Types:
- **MST Types:** MST4 (4F), MST6 (6F), MST8 (8F), MST12 (12F)
- **Aerial Terminal:** 1-12 ONTs
- **FOSC:** Splice closures
- **FDH:** 96, 144, 288, 432 ports
- **OLT:** 8 ports, 256 ONTs/port max

### Service Configuration:
- Service per ONT: 1 Gbps (configurable)
- OLT port capacity: 1 Gbps (configurable)
- Oversubscription: 1:32 (options: 1:8, 1:16, 1:32, 1:64)
- Max subscribers per port: 256 (hard limit)
- Future growth: 10%

### Cable Configuration:
- Drop cables: 1F (configurable)
- Stub cables: Based on MST type (4F/6F/8F/12F)
- Infrastructure: Multiples of 12F (12, 24, 48, 72, 96, 144, 288)

### Placement Rules:
- OLT: Pocket merge distance 15km, max diameter 25km, max distance 25km
- Terminal: FOSC proximity thresholds
- FOSC: Min segment length 1800m

---

## 📊 RULES DISCOVERED (From Analysis)

### **R10: Aerial Terminal Placement**
- Always placed on infrastructure cables (288F/144F/96F/72F/48F)
- When residential is near (<50m)
- No stub cable
- Serves 1-12 ONTs
- Use when FOSC >1km away (minimize mid-cable splicing)

### **R11: MST Placement**
- Always connects to FOSC via stub cable
- Stub length: ≤2500m (long-reach MST)
- ONT Count: 6-24 ONTs (short-reach), 6-48 ONTs (long-reach)
- Use when FOSC ≤1km away (maximize FOSC splicing)
- OR when ≥200m from infrastructure cable

### **R12: FOSC Placement**
- **Triggers:**
  1. Junction of ≥2 cables (geometry) ✅ Phase 2
  2. Long segments ≥1800m (geometry) ✅ Phase 2
  3. Cable ID changes (requires IDs) ⏳ Phase 6b
  4. Fiber count transitions (requires sizes) ⏳ Phase 6b

### **R13: FDH Placement**
- Based on FOSC locations
- Based on capacity requirements (ONT counts)

### **R15: OLT-ONT Max Distance**
- Maximum 25km (physical limit for OLT port light traverse)

### **R16: OLT Placement Strategy**
- Place OLT on/near main infrastructure (288F/144F/96F routes)
- Validate all ONTs within 15-20km
- Prioritize proximity to infrastructure

---

## ⏳ PENDING PHASES

### **Phase 6: Cable Sizing & ID Allocation** ⏳
**Status:** Not yet implemented
**Tasks:**
- Count downstream ONTs per cable segment
- Calculate required cable size using formula:
  ```
  Subscribers per Port = OLT Port Capacity / (Service per ONT × Oversubscription)
  Required Ports = ONT Count / Subscribers per Port
  Total Capacity = Required Ports × OLT Port Capacity
  With Growth = Total Capacity × (1 + Growth %)
  Cable Size = Next standard size ≥ With Growth
  ```
- Assign cable IDs (design engine generates, pattern from existing design)
- Handle service level adjustments (100M = 10x smaller cable)
- Apply 256 ONT/port hard limit

### **Phase 6b: Refine FOSC Placement** ⏳
**Status:** Not yet implemented
**Tasks:**
- Detect cable ID changes (now that IDs are assigned)
- Detect fiber count transitions (now that sizes are determined)
- Add FOSCs at transition points
- Merge with existing FOSCs if nearby

### **Phase 3: Place Terminals (MST/Aerial)** ⏳
**Status:** Not yet implemented
**Tasks:**
- For each ONT cluster:
  - Find nearest infrastructure cable
  - Find nearest FOSC
  - Apply R10/R11:
    - FOSC >1km → Aerial Terminal
    - FOSC ≤1km → MST
- Assign terminal IDs
- Determine MST type based on ONT count

### **Phase 4: Place FDHs** ⏳
**Status:** Not yet implemented
**Tasks:**
- Based on FOSC locations (R13)
- Based on capacity requirements
- Select FDH size (96/144/288/432) based on ONT count

### **Phase 5: Create Drop/Stub Cables** ⏳
**Status:** Not yet implemented
**Tasks:**
- Drop cables: ONT → Terminal (1F)
- Stub cables: MST → FOSC (4F/6F/8F/12F based on MST type)

### **Phase 7: BOM Generation** ⏳
**Status:** Not yet implemented
**Tasks:**
- Generate Bill of Materials:
  - Cable lengths by size (e.g., 100 km of 144F)
  - Equipment counts (e.g., 3000 FOSCs, 200 terminals, 5 OLTs)
  - Export to JSON and text formats

---

## 🔄 REVISED PHASE ORDER

Based on dependencies, the final order is:

1. ✅ **Phase 0:** Community Pockets
2. ✅ **Phase 1:** Place OLTs
3. ✅ **Phase 2:** Place FOSCs (Initial - Geometry)
4. ⏳ **Phase 6:** Cable Sizing & ID Allocation
5. ⏳ **Phase 6b:** Refine FOSC Placement (ID/Size triggers)
6. ⏳ **Phase 3:** Place Terminals (MST/Aerial) ← After all FOSCs finalized
7. ⏳ **Phase 4:** Place FDHs
8. ⏳ **Phase 5:** Create Drop/Stub Cables
9. ⏳ **Phase 7:** BOM Generation

**Why this order?**
- FOSCs must be finalized before terminals (MSTs connect to FOSCs)
- Cable sizing must happen before FOSC refinement (needs sizes for transitions)
- Logical flow: OLTs → Sizing → FOSCs → Terminals → FDHs → Cables → BOM

---

## 📝 KEY DESIGN DECISIONS

1. **Input Cables Have No Size:** Design engine determines all sizes
2. **Cable IDs Generated by Engine:** Full flexibility for assignments
3. **Two-Pass FOSC Placement:** Geometry first, then refine with IDs/sizes
4. **Service-Based Sizing:** Cable size depends on service level (100M = 10x smaller)
5. **Hard Limit:** 256 ONTs per OLT port (regardless of service)
6. **Configurable Everything:** All parameters in `design_config.json`

---

## 🚀 HOW TO RUN

```bash
python3 generate_design.py \
  --onts ONT.geojson \
  --cables "fiber cable.geojson" \
  --config design_config.json \
  --output test_output
```

**Current Output:**
- `test_output/OLT.geojson` ✅
- `test_output/splice closure.geojson` ✅
- `test_output/olt_placement_summary.json` ✅
- `test_output/fosc_placement_summary.json` ✅

---

## 📚 ANALYSIS & RULE DISCOVERY (Completed)

The project includes extensive analysis scripts that discovered rules from existing design data:
- `refine_graph_rules.py` - Refined placement rules from graph data
- `learn_adaptive_rules.py` - Learned adaptive thresholds
- `extract_design_intent.py` - Extracted design rationale
- `analyze_cable_transitions.py` - Analyzed cable size transitions
- `derive_cable_sizing_rules.py` - Derived sizing rules
- `analyze_olt_placement_patterns.py` - Analyzed OLT placement
- And many more...

---

## 🎯 NEXT STEPS

**Immediate Next Phase:** Phase 6 - Cable Sizing & ID Allocation

This is the critical phase that will:
1. Determine all cable sizes based on ONT counts and service levels
2. Assign cable IDs to enable Phase 6b (FOSC refinement)
3. Enable Phase 3 (Terminal placement) to proceed

---

**Last Updated:** 2025-11-22
**Status:** 3 of 9 phases completed (33%)
