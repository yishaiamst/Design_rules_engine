# FOSC Placement Strategy - Handling Cable IDs and Sizing

## 🔍 Problem Statement

### **R12 FOSC Placement Triggers:**
1. ✅ **Junction of ≥2 cables** (geometry-based) - Can detect without IDs/sizes
2. ✅ **Long segments ≥1800m** (geometry-based) - Can detect without IDs/sizes
3. ❌ **Cable ID changes** (requires cable IDs) - Cannot detect without IDs
4. ❌ **Fiber count transitions** (requires cable sizes) - Cannot detect without sizes

### **Input Constraints:**
- Input cables have **NO IDs** (design engine will generate)
- Input cables have **NO sizes** (design engine will determine in Phase 6)
- Design engine needs **full flexibility** to assign IDs and sizes

### **Dependency Challenge:**
- Terminals (Phase 3) need FOSC locations for R10/R11 logic
- But FOSCs need cable IDs/sizes for triggers 3 & 4
- Cable sizing (Phase 6) happens after terminals

---

## 💡 Solution: Two-Pass FOSC Placement

### **Phase 2: Initial FOSC Placement (Geometry-Based)**
**Objective:** Place FOSCs based on geometry triggers only

**Triggers:**
1. ✅ Junction of ≥2 cables (detect by geometry intersection)
2. ✅ Long segments ≥1800m (calculate segment lengths)

**Logic:**
```python
def place_foscs_initial(fiber_cables):
    """
    Place FOSCs based on geometry only.
    """
    foscs = []
    
    # 1. Detect junctions (≥2 cables meet)
    junctions = find_cable_junctions(fiber_cables)
    for junction in junctions:
        fosc = create_fosc(junction.position, trigger="junction")
        foscs.append(fosc)
    
    # 2. Detect long segments (≥1800m)
    long_segments = find_long_segments(fiber_cables, min_length=1800)
    for segment in long_segments:
        # Place FOSC at midpoint or strategic point
        fosc = create_fosc(segment.midpoint, trigger="long_segment")
        foscs.append(fosc)
    
    return foscs
```

**Output:** Initial FOSC locations (geometry-based)

---

### **Phase 6b: Refine FOSC Placement (After Cable Sizing)**
**Objective:** Add/refine FOSCs based on cable IDs and sizes

**Triggers:**
3. ✅ Cable ID changes (now that IDs are assigned)
4. ✅ Fiber count transitions (now that sizes are determined)

**Logic:**
```python
def refine_foscs_placement(foscs, sized_cables):
    """
    Add/refine FOSCs after cable sizing.
    """
    # 1. Detect cable ID changes
    id_transitions = find_cable_id_transitions(sized_cables)
    for transition in id_transitions:
        # Check if FOSC already exists nearby
        existing_fosc = find_nearby_fosc(transition.position, foscs, radius=50)
        if not existing_fosc:
            fosc = create_fosc(transition.position, trigger="id_change")
            foscs.append(fosc)
    
    # 2. Detect fiber count transitions
    size_transitions = find_fiber_count_transitions(sized_cables)
    for transition in size_transitions:
        # Check if FOSC already exists nearby
        existing_fosc = find_nearby_fosc(transition.position, foscs, radius=50)
        if not existing_fosc:
            fosc = create_fosc(transition.position, trigger="size_transition")
            foscs.append(fosc)
        else:
            # Update existing FOSC to note size transition
            existing_fosc.triggers.append("size_transition")
    
    return foscs
```

**Output:** Final FOSC locations (all triggers)

---

## 📋 Revised Phase Order

### **Updated Implementation Plan:**

1. **Phase 0:** Community Pockets ✅
2. **Phase 1:** Place OLTs ✅
3. **Phase 2:** Place FOSCs (Initial - Geometry-Based)
   - Junctions (≥2 cables)
   - Long segments (≥1800m)
4. **Phase 3:** Place Terminals (MST/Aerial)
   - Uses FOSCs from Phase 2 for R10/R11 logic
5. **Phase 4:** Place FDHs
   - Uses FOSCs from Phase 2 for R13 association
6. **Phase 5:** Create Drop/Stub Cables
7. **Phase 6:** Cable Sizing
   - Determines cable IDs and sizes
8. **Phase 6b:** Refine FOSC Placement
   - Add FOSCs for ID changes
   - Add FOSCs for size transitions
   - Merge nearby FOSCs if needed
9. **Phase 7:** BOM Generation

---

## 🎯 Benefits of Two-Pass Approach

1. **Early FOSC Placement:** Terminals can use FOSC locations for R10/R11
2. **Complete Coverage:** All R12 triggers are eventually handled
3. **Flexibility:** Design engine has full control over IDs and sizes
4. **No Circular Dependencies:** Geometry-based FOSCs don't depend on sizing

---

## 🔧 Implementation Details

### **Cable ID Generation:**
- Design engine generates IDs based on:
  - OLT ID (e.g., "OLT_101")
  - Cable sequence number
  - Pattern: `{OLT_ID}_CABLE_{sequence}_{size}F`
  - Example: `OLT_101_CABLE_001_288F`

### **FOSC ID Generation:**
- Design engine generates IDs based on:
  - OLT ID or region
  - FOSC sequence number
  - Pattern: `F{region}{sequence}`
  - Example: `F1000001`, `F4000001`

### **Merging Logic:**
- If Phase 6b adds FOSC within 50m of existing FOSC:
  - Merge into single FOSC
  - Combine triggers
  - Update associations

---

## ✅ Recommendation

**Adopt Two-Pass FOSC Placement:**
- Phase 2: Geometry-based FOSCs (junctions, long segments)
- Phase 6b: ID/size-based FOSCs (after cable sizing)

This gives us:
- ✅ Early FOSC locations for terminals
- ✅ Complete R12 trigger coverage
- ✅ Full flexibility for ID/size assignment
- ✅ No circular dependencies

---

**Status: Strategy defined, ready for implementation!** ✅


