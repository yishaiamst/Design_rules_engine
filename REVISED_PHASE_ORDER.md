# Revised Phase Order - Final Strategy

## 🔍 Problem Identified

### **Issue with Previous Order:**
- Phase 3: Place Terminals (MST/Aerial) based on initial FOSCs
- Phase 6b: Add more FOSCs (ID changes, size transitions)
- **Problem:** MSTs always connect to FOSC via stub cable
- **Result:** MSTs might need re-placement if new FOSCs are added

### **User's Insight:**
> "If there will be a later placement of FOSC in phase 6b, we might need to refine the MST placement since in the design every MST is connected to a FOSC."

---

## ✅ Revised Phase Order (Final)

### **1. Phase 0: Community Pockets** ✅
- Cluster ONTs, merge pockets, validate diameter

### **2. Phase 1: Place OLTs** ✅
- Place OLTs based on pockets and infrastructure
- Calculate required cable sizes

### **3. Phase 2: Place FOSCs (Initial - Geometry-Based)**
- **Triggers:**
  - Junction of ≥2 cables (geometry intersection)
  - Long segments ≥1800m (calculate lengths)
- **Output:** Initial FOSC locations

### **4. Phase 6: Cable Sizing & ID Allocation**
- Determine cable sizes based on ONT counts
- Generate cable IDs (design engine assigns)
- Create sized cable network

### **5. Phase 6b: Refine FOSC Placement**
- **Triggers:**
  - Cable ID changes (now that IDs are assigned)
  - Fiber count transitions (now that sizes are determined)
- **Output:** Final FOSC locations (all triggers)

### **6. Phase 3: Place Terminals (MST/Aerial)**
- **After all FOSCs are finalized**
- Use FOSC locations for R10/R11 logic:
  - R10: Aerial Terminal when FOSC >1km away
  - R11: MST when FOSC ≤1km away
- **Output:** Terminal locations

### **7. Phase 4: Place FDHs**
- Based on FOSC locations (R13)
- Based on terminal/ONT counts (capacity)

### **8. Phase 5: Create Drop/Stub Cables**
- Drop cables: ONT → Terminal
- Stub cables: MST → FOSC

### **9. Phase 7: BOM Generation**
- Generate Bill of Materials

---

## 🎯 Why This Order Works

### **1. FOSCs Finalized Before Terminals**
- ✅ All FOSCs placed (geometry + ID/size triggers)
- ✅ MSTs can connect to correct FOSCs
- ✅ No need to re-place MSTs later

### **2. Cable Sizing Before Terminal Placement**
- ✅ Cable sizes determined
- ✅ FOSCs placed at size transitions
- ✅ Terminals can use accurate FOSC locations

### **3. Logical Flow**
```
OLTs → Cable Sizing → FOSCs (all) → Terminals → FDHs → Cables → BOM
```

---

## 📋 Detailed Phase Breakdown

### **Phase 2: Initial FOSC Placement**
**Input:** Infrastructure cables (geometry only)
**Output:** Initial FOSC locations (geometry-based)

**Logic:**
- Detect cable junctions (≥2 cables intersect)
- Detect long segments (≥1800m)
- Place FOSC at each trigger point

---

### **Phase 6: Cable Sizing & ID Allocation**
**Input:** 
- Infrastructure cables (geometry)
- OLT locations and ONT assignments
- Required cable sizes (from Phase 1)

**Output:**
- Sized cables with IDs
- Cable network with sizes

**Logic:**
- For each cable segment:
  - Count downstream ONTs
  - Calculate required size (from Phase 1 formula)
  - Assign cable ID (design engine generates)
  - Assign cable size

---

### **Phase 6b: Refine FOSC Placement**
**Input:**
- Initial FOSCs (from Phase 2)
- Sized cables with IDs (from Phase 6)

**Output:**
- Final FOSC locations (all triggers)

**Logic:**
- Detect cable ID changes
- Detect fiber count transitions
- Add FOSCs at transition points
- Merge nearby FOSCs if needed

---

### **Phase 3: Place Terminals (After FOSCs Finalized)**
**Input:**
- ONT locations
- Final FOSC locations
- Infrastructure cables

**Output:**
- Terminal locations (Aerial/MST)

**Logic:**
- For each ONT cluster:
  - Find nearest infrastructure cable
  - Find nearest FOSC
  - Apply R10/R11:
    - FOSC >1km → Aerial Terminal
    - FOSC ≤1km → MST

---

## ✅ Benefits

1. **No Re-placement:** MSTs placed after all FOSCs are finalized
2. **Accurate Connections:** MSTs connect to correct FOSCs
3. **Complete Coverage:** All R12 triggers handled before terminals
4. **Logical Flow:** Each phase builds on previous phases

---

## 🔄 Updated Phase Sequence

```
Phase 0: Community Pockets ✅
Phase 1: Place OLTs ✅
Phase 2: Place FOSCs (Initial - Geometry)
Phase 6: Cable Sizing & ID Allocation
Phase 6b: Refine FOSC Placement (ID/Size)
Phase 3: Place Terminals (MST/Aerial)
Phase 4: Place FDHs
Phase 5: Create Drop/Stub Cables
Phase 7: BOM Generation
```

---

**Status: Revised order approved! Ready for implementation!** ✅


