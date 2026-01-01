# Cable Sizing Strategy V2 - Based on User Input

## 🎯 Key Understanding

**User Input:**
1. **Cable routes (geometry only)** - User's desired/planned paths (may be incomplete)
2. **ONT locations** - Where subscribers are

**What We Do:**
1. Place OLTs (Phase 1) - Each OLT serves a pocket of ONTs
2. **Extend/improve cable routes** to reach OLTs if needed
3. **Size cables based on OLT capacity requirements** (using our formula)
4. **Assign cable IDs** based on network structure

---

## 💡 Correct Strategy

### **Cable Sizing is OLT-Driven**

**Key Insight:**
- Cable size is determined by **OLT capacity requirements**, not by counting ONTs along the cable
- We already have the formula: `calculate_required_cable_size(ont_count, config)`
- This formula accounts for: service level, oversubscription, growth, 256 ONT/port limit

**Process:**
```
1. OLT placed → serves N ONTs (from pocket)
2. Calculate required cable size for N ONTs using formula
3. Find cable(s) that connect to this OLT
4. Size those cables based on OLT's capacity requirement
5. For branching cables (via FOSCs), trace downstream and sum requirements
```

---

## 📋 Implementation Strategy

### **Step 1: OLT-to-Cable Mapping**

```python
For each OLT:
    - OLT has ONT count (from pocket)
    - Calculate required capacity = calculate_required_cable_size(ont_count, config)
    - Find cables near OLT (within 1km)
    - Assign this capacity requirement to those cables
```

### **Step 2: Cable Sizing (OLT-Driven)**

```python
For each cable:
    - Find all OLTs connected to this cable
    - Sum their capacity requirements
    - Cable size = smallest standard size ≥ total capacity
    - Example: OLT1 needs 288F, OLT2 needs 144F → cable = 288F (or multiple cables)
```

### **Step 3: Handle Cable Branching (Downstream)**

```python
For cables that branch via FOSCs:
    - Trace downstream from OLT
    - For each branch:
        * Find which OLT(s) it serves
        * Calculate capacity requirement
    - Size upstream cable to handle all downstream branches
    - Example: Main cable splits into 3 branches
        * Branch 1: 96F (serves OLT with 100 ONTs)
        * Branch 2: 144F (serves OLT with 150 ONTs)
        * Branch 3: 96F (serves OLT with 100 ONTs)
        * Main cable: 288F (handles all 3 branches)
```

### **Step 4: Cable ID Assignment**

```python
For each cable:
    - Determine FROM_ID and TO_ID:
        * FROM_ID: OLT or FOSC at start
        * TO_ID: FOSC or OLT at end
    - Generate ID: {SIZE}FOC/{FROM_ID}/{TO_ID}
    - Example: "288FOC/OLT102/F1000143"
```

---

## 🔄 Network Flow

```
User Input Cable Route (geometry)
    ↓
Place OLTs (Phase 1)
    ↓
Extend cables to reach OLTs (if needed)
    ↓
Size cables based on OLT capacity:
    - OLT with 256 ONTs → 288F cable
    - OLT with 150 ONTs → 144F cable
    - OLT with 100 ONTs → 96F cable
    ↓
Handle branching:
    - Main cable serves multiple OLTs → sum capacity
    - Branch cables serve individual OLTs → individual capacity
    ↓
Assign cable IDs
    ↓
Place FOSCs at size transitions (Phase 6b)
    ↓
Place terminals (Phase 3)
    ↓
Create drop/stub cables (Phase 5)
```

---

## 📊 Example

**Scenario:**
- OLT 102 serves 256 ONTs
- User provided cable route passes near OLT
- Cable needs to connect to OLT

**Process:**
1. Find cable near OLT (within 1km)
2. Calculate: `calculate_required_cable_size(256, config)` → **288F**
3. Size cable as **288F**
4. Assign ID: `"288FOC/OLT102/F1000143"` (if connects to FOSC F1000143)
5. If cable branches downstream:
   - Trace branches
   - Size each branch based on its OLT's capacity
   - Main cable sized to handle all branches

---

## ✅ Benefits of This Approach

1. **Uses existing formula** - We already have `calculate_required_cable_size()`
2. **OLT-driven** - Reflects actual network capacity requirements
3. **Handles branching** - Can trace downstream and sum requirements
4. **Respects user input** - Uses user's cable routes, extends if needed
5. **Fast** - No need to check every ONT, just OLTs

---

## 🎯 Implementation Plan

### **Phase 6: Cable Sizing & ID Allocation**

```python
def size_cables_olt_driven(olts, cables, foscs, config):
    """
    Size cables based on OLT capacity requirements.
    """
    # 1. Map OLTs to cables
    cable_olt_map = defaultdict(list)  # cable_index -> [olt_info]
    
    for olt in olts:
        olt_pos = olt["position"]
        ont_count = len(olt.get("ont_ids", []))
        required_capacity = calculate_required_cable_size(ont_count, config)
        
        # Find cables near OLT
        for cable_idx, cable in enumerate(cables):
            if is_cable_near_point(cable, olt_pos, max_distance=1000):
                cable_olt_map[cable_idx].append({
                    "olt_id": olt["olt_id"],
                    "ont_count": ont_count,
                    "required_capacity": required_capacity
                })
    
    # 2. Size each cable
    for cable_idx, cable in enumerate(cables):
        olt_connections = cable_olt_map.get(cable_idx, [])
        
        if olt_connections:
            # Sum capacity requirements from all connected OLTs
            total_capacity = sum(olt["required_capacity"] for olt in olt_connections)
            total_onts = sum(olt["ont_count"] for olt in olt_connections)
            
            # Select standard size
            standard_sizes = [12, 24, 48, 72, 96, 144, 288]
            cable_size = min(s for s in standard_sizes if s >= total_capacity)
            
            cable["fiber_count"] = cable_size
            cable["downstream_onts"] = total_onts
            cable["connected_olts"] = [olt["olt_id"] for olt in olt_connections]
        else:
            # Cable not connected to OLT - size based on downstream branches
            # (This will be handled in refinement step)
            cable["fiber_count"] = 12  # Default minimum
            cable["downstream_onts"] = 0
    
    # 3. Handle branching (trace downstream via FOSCs)
    # For cables that branch, sum downstream requirements
    # (Implementation details TBD)
    
    return cables
```

---

## ❓ Questions

1. **Cable Extension:** Should we automatically extend cables to reach OLTs, or just size existing routes?
2. **Branching Logic:** How should we handle cables that split into multiple branches?
   - Sum all downstream requirements?
   - Size each branch independently?
3. **Cables Without OLTs:** What about cables that don't directly connect to OLTs?
   - Trace back through FOSCs to find upstream OLT?
   - Use minimum size (12F)?

---

**Does this strategy align with your vision? Should I implement it this way?**


