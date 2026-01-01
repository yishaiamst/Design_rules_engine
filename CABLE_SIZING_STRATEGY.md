# Cable Sizing Strategy - Discussion

## 🔍 Current Problem

**What I'm doing now:**
- Assigning ONTs directly to cables based on spatial proximity
- This is **incorrect** because ONTs don't connect directly to infrastructure cables!

**Actual Network Topology:**
```
OLT → Infrastructure Cable → FOSC → Terminal (MST/Aerial) → ONT
```

---

## 💡 Strategy Options

### **Option 1: Use OLT Pockets (Recommended for Phase 6)**

**Approach:**
- Each OLT has a pocket of ONTs (from Phase 0/1)
- OLTs are placed on/near infrastructure cables
- Size cables based on which OLT(s) they serve
- Cable size = sum of ONT counts from connected OLTs

**Pros:**
- ✅ Uses data we already have (OLT pockets from Phase 1)
- ✅ Reflects actual network hierarchy
- ✅ Fast (no need to check every ONT)
- ✅ Accurate for cables near OLTs

**Cons:**
- ⚠️ Doesn't account for cable branching/splitting downstream
- ⚠️ May over-size cables that branch to multiple FOSCs

**Implementation:**
```python
1. For each OLT:
   - Find cables it connects to (within 1km)
   - Assign OLT's ONT count to those cables
   
2. For each cable:
   - Sum ONT counts from all connected OLTs
   - Calculate required size based on total ONT count
   
3. For downstream cables (via FOSCs):
   - Estimate ONT distribution based on FOSC connections
   - Size based on estimated ONT count
```

---

### **Option 2: Use FOSC Connections**

**Approach:**
- FOSCs are placed on cables (Phase 2)
- Estimate ONTs per FOSC based on spatial proximity
- Size cable based on sum of ONTs from connected FOSCs

**Pros:**
- ✅ Uses FOSC locations (already placed)
- ✅ More granular than OLT-based

**Cons:**
- ⚠️ Still an estimate (terminals not placed yet)
- ⚠️ Requires spatial proximity checks (slower)

**Implementation:**
```python
1. For each FOSC:
   - Find nearby ONTs (within 2km)
   - Estimate ONT count for this FOSC
   
2. For each cable:
   - Find FOSCs on this cable
   - Sum estimated ONT counts from FOSCs
   - Calculate required size
```

---

### **Option 3: Two-Pass Sizing**

**Approach:**
- **Phase 6 (Initial):** Size based on OLT pockets (Option 1)
- **Phase 6b (Refine):** After terminals placed, refine based on actual connections

**Pros:**
- ✅ Best of both worlds
- ✅ Initial sizing is fast and reasonable
- ✅ Refinement improves accuracy

**Cons:**
- ⚠️ More complex
- ⚠️ Requires refinement logic

---

### **Option 4: Use Existing Path Data (If Available)**

**Approach:**
- If we have `olt_ont_paths.json` or similar
- Use actual paths to count ONTs per cable segment
- Most accurate but requires existing analysis data

**Pros:**
- ✅ Most accurate
- ✅ Based on actual design

**Cons:**
- ⚠️ Requires existing path data
- ⚠️ May not be available for new designs

---

## 🎯 Recommendation

**For Phase 6 (Initial Sizing): Use Option 1 (OLT Pockets)**

**Rationale:**
1. We already have OLT pockets with ONT counts (Phase 0/1)
2. OLTs are placed on/near infrastructure cables (Phase 1)
3. Fast and reflects network hierarchy
4. Good enough for initial sizing
5. Can refine later if needed

**For Phase 6b (Refinement):**
- After terminals are placed (Phase 3)
- Refine cable sizes based on actual terminal-ONT connections
- Adjust for cable branching and splitting

---

## 📋 Proposed Implementation

### **Phase 6: Initial Cable Sizing (OLT-Based)**

```python
def size_cables_olt_based(olts, cables, foscs, config):
    """
    Size cables based on OLT pockets.
    """
    # 1. Map OLTs to cables
    olt_cable_map = {}  # cable_index -> [olt_ids]
    
    for olt in olts:
        olt_pos = olt["position"]
        olt_ont_count = len(olt["ont_ids"])  # From pocket
        
        # Find cables near this OLT
        for cable_idx, cable in enumerate(cables):
            if is_cable_near_point(cable, olt_pos, max_distance=1000):
                if cable_idx not in olt_cable_map:
                    olt_cable_map[cable_idx] = []
                olt_cable_map[cable_idx].append({
                    "olt_id": olt["olt_id"],
                    "ont_count": olt_ont_count
                })
    
    # 2. Size each cable
    for cable_idx, cable in enumerate(cables):
        # Sum ONT counts from connected OLTs
        total_onts = sum(
            olt_info["ont_count"]
            for olt_info in olt_cable_map.get(cable_idx, [])
        )
        
        # Calculate required size
        required_size = calculate_required_cable_size(total_onts, config)
        cable["fiber_count"] = required_size
        cable["downstream_onts"] = total_onts
```

---

## ❓ Questions for Discussion

1. **Do you prefer Option 1 (OLT-based) for Phase 6?**
   - Fast, uses existing data, good initial estimate

2. **Should we refine sizing after terminals are placed?**
   - More accurate but adds complexity

3. **How should we handle cable branching?**
   - When one cable splits into multiple cables via FOSCs
   - Should we distribute ONT counts proportionally?

4. **What about cables far from OLTs?**
   - Distribution cables that don't directly connect to OLTs
   - Should we trace back through FOSCs to find upstream OLT?

---

**What do you think? Which strategy makes the most sense for your use case?**


