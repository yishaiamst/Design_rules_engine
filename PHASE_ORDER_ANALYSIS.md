# Phase Order Analysis - Revised Strategy

## 🔍 Analysis of Actual Design

### **Component Counts:**
- **OLTs:** 17
- **FDHs:** 210 (average ~12 FDHs per OLT)
- **FOSCs:** 2,109 (average ~10 FOSCs per FDH)
- **Terminals:** 6,370 (average ~3 terminals per FOSC)

### **FDH Sizes in Actual Design:**
- **72F:** 56 FDHs
- **144F:** 84 FDHs
- **288F:** 70 FDHs
- **User Requirement:** 96, 144, 288, 432

### **Connectivity Hierarchy:**
```
OLT → FDH → FOSC → Terminal → ONT
```

**Key Relationships:**
- 1 OLT → Multiple FDHs (e.g., OLT 101 has 16 FDHs)
- 1 FDH → Multiple FOSCs (e.g., FDH103003 has 10 FOSCs)
- 1 FOSC → Multiple Terminals (via stub cables for MST, direct for Aerial)
- 1 Terminal → Multiple ONTs (via drop cables)

---

## 💡 User's Insight: Revised Phase Order

### **Current Order (Original Plan):**
1. Phase 0: Community Pockets ✅
2. Phase 1: Place OLTs ✅
3. Phase 2: Place FDHs
4. Phase 3: Place FOSCs
5. Phase 4: Place Terminals (MST/Aerial)
6. Phase 5: Create Drop/Stub Cables
7. Phase 6: Cable Sizing
8. Phase 7: BOM Generation

### **Proposed Order (User's Suggestion):**
1. Phase 0: Community Pockets ✅
2. Phase 1: Place OLTs ✅
3. **Phase 2: Place FOSCs** (based on cable network structure)
4. **Phase 3: Place Terminals** (MST/Aerial based on ONT locations + FOSC proximity)
5. **Phase 4: Place FDHs** (based on FOSC locations + OLT locations)
6. Phase 5: Create Drop/Stub Cables
7. Phase 6: Cable Sizing
8. Phase 7: BOM Generation

---

## ✅ Why This Order Makes Sense

### **1. FOSCs First (Phase 2)**
**Rationale:**
- FOSCs are determined by **cable network structure** (independent of terminals)
- R12 triggers: junctions, long segments (≥1800m), cable ID changes
- These are **geometric/structural** decisions, not dependent on terminals
- FOSCs define the **splicing infrastructure** that terminals will connect to

**Dependencies:**
- ✅ OLTs (Phase 1) - to know service areas
- ✅ Infrastructure cables (input)
- ❌ Terminals - NOT needed
- ❌ FDHs - NOT needed

### **2. Terminals Second (Phase 3)**
**Rationale:**
- Terminals need to know **FOSC locations** for R10/R11 logic:
  - R10: Aerial Terminal when FOSC >1km away
  - R11: MST when FOSC ≤1km away
- Terminals are placed based on **ONT locations** and **FOSC proximity**
- This determines the **access layer** structure

**Dependencies:**
- ✅ OLTs (Phase 1) - to know ONT assignments
- ✅ FOSCs (Phase 2) - for proximity-based placement logic
- ❌ FDHs - NOT needed for terminal placement

### **3. FDHs Last (Phase 4)**
**Rationale:**
- FDHs connect **OLTs to FOSCs** (R13: pair nearest FOSC to FDH)
- FDH sizing depends on:
  - **Number of FOSCs** it needs to serve
  - **Number of ONTs** downstream (via terminals)
  - **Required capacity** (calculated from ONT count)
- FDH placement can be optimized after we know:
  - Where FOSCs are
  - How many terminals/ONTs each FOSC serves
  - What capacity is needed

**Dependencies:**
- ✅ OLTs (Phase 1) - to know where to connect from
- ✅ FOSCs (Phase 2) - to know where to connect to
- ✅ Terminals (Phase 3) - to calculate capacity requirements

---

## 📊 FDH Sizing Logic

### **FDH Capacity Requirements:**
- **Input:** Number of ONTs downstream from FDH
- **Calculation:** Use same formula as cable sizing
- **FDH Types:** 96F, 144F, 288F, 432F (configurable)

### **FDH Placement Strategy:**
1. For each OLT:
   - Find all FOSCs in the OLT's service area
   - Group FOSCs by proximity
   - Calculate total ONT count per FOSC group
   - Determine required FDH capacity
   - Place FDH near OLT or at strategic junction
   - Associate FOSCs to FDH (R13: nearest FOSC, ≤50m)

---

## 🎯 Revised Implementation Plan

### **Phase 2: Place FOSCs (R12)**
**Objective:** Place Fiber Optic Splice Closures at strategic points

**Logic:**
1. Analyze infrastructure cable network:
   - Identify junctions (≥2 cables meet)
   - Find long segments (≥1800m)
   - Detect cable ID changes
   - Note: Fiber count transitions determined later (after sizing)
2. Place FOSC at each trigger point
3. Assign unique FOSC ID (F*)

**Output:** `splice closure.geojson` (FOSC locations)

---

### **Phase 3: Place Terminals (R10, R11 Enhanced)**
**Objective:** Place Aerial Terminals and MSTs based on ONT locations and FOSC proximity

**Logic:**
1. For each ONT cluster:
   - Find nearest infrastructure cable
   - Find nearest FOSC
   - Calculate distances
2. Apply R10/R11:
   - **R10 (Aerial Terminal):** Use when FOSC >1km away
   - **R11 (MST):** Use when FOSC ≤1km away
3. Place terminals accordingly
4. Assign unique Terminal IDs (T*)

**Output:** `terminal.geojson` (Aerial Terminal and MST locations)

---

### **Phase 4: Place FDHs (R13)**
**Objective:** Place Feeder Distribution Hubs connecting OLTs to FOSCs

**Logic:**
1. For each OLT:
   - Find all FOSCs in service area
   - Group FOSCs by proximity
   - Calculate total ONT count per group (via terminals)
   - Determine required FDH capacity (96/144/288/432F)
   - Place FDH near OLT or at strategic junction
2. Associate FOSCs to FDHs (R13: nearest FOSC, ≤50m)
3. Assign unique FDH IDs (FDH*)

**Output:** `FDH.geojson`, FDH-to-OLT associations, FDH-to-FOSC associations

---

## ✅ Benefits of Revised Order

1. **Logical Dependencies:** Each phase builds on previous phases
2. **Better Capacity Planning:** FDH sizing based on actual terminal/ONT counts
3. **Clearer Logic:** FOSCs define infrastructure, terminals use it, FDHs connect it
4. **Matches Actual Design:** Aligns with how components are actually placed

---

## 📝 Updated Configuration

### **FDH Configuration:**
```json
{
  "fdh": {
    "FDH-96": {
      "fiber_capacity": 96,
      "description": "96-fiber FDH"
    },
    "FDH-144": {
      "fiber_capacity": 144,
      "description": "144-fiber FDH"
    },
    "FDH-288": {
      "fiber_capacity": 288,
      "description": "288-fiber FDH"
    },
    "FDH-432": {
      "fiber_capacity": 432,
      "description": "432-fiber FDH"
    }
  }
}
```

---

**Recommendation: Adopt the revised order!** ✅


