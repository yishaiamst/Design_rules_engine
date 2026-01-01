# Design Engine Logic - Refined Implementation Order

## 📋 Implementation Order

### **Step 1: Cable Extension Analysis (Drop & Stub Cables)**
**Objective:** Analyze and plan drop cables (MST to ONT) and stub cables (MST to FOSC).

**Primary Focus:**
- **Drop Cables:** From MST/Aerial Terminal to ONT (typically 1F, configurable)
- **Stub Cables:** From MST to FOSC (size matches MST type: MST4=4F, MST6=6F, etc.)

**Logic:**
```python
def analyze_cable_extensions(terminals, onts, foscs):
    """
    After terminals are placed (Phase 6):
    1. For each MST/Aerial Terminal:
       - Identify connected ONTs
       - Calculate drop cable routes (Terminal → ONT)
       - Determine drop cable lengths
       - Create drop cable features (1F default, configurable)
    
    2. For each MST Terminal:
       - Find connected FOSC
       - Calculate stub cable route (Terminal → FOSC)
       - Determine stub cable length
       - Get stub cable size from MST type (MST4=4F, MST6=6F, etc.)
       - Create stub cable features
    
    3. Validate cable lengths:
       - Drop cables: Typically ≤150m average
       - Stub cables: ≤500m (standard) or ≤2500m (long-reach)
    """
    pass
```

**Note:** This analysis happens AFTER terminal placement (Phase 6), not before.

**Advanced Use Case (Placeholder for Future):**
- Infrastructure cable extensions to improve service
- Extend main infrastructure cables to reduce stub lengths
- This is more advanced and can be considered as a second step/optimization phase

**Output:**
- Drop cable.geojson (Terminal → ONT)
- Stub cable.geojson (MST → FOSC)

---

### **Step 2: Create Community Pockets**
**Objective:** Cluster ONTs into community pockets for OLT placement.

**Logic:**
```python
def create_community_pockets(onts, extended_cables):
    """
    1. Cluster ONTs by proximity (2km radius initial)
    2. For each cluster:
       - Calculate centroid
       - Count ONTs
       - Find nearest infrastructure cable
       - Calculate distance to cable
    3. Merge pockets if <15km apart (R16)
    4. Validate merged pocket diameter (≤15km)
    5. Split oversized pockets if needed
    6. Assign pocket metadata:
       - Pocket ID
       - ONT count
       - Centroid coordinates
       - Nearest infrastructure cable
       - Distance to cable
    """
    pass
```

**Output:**
- Community pockets (list of ONT clusters with metadata)

---

### **Step 3: Place OLTs**
**Objective:** Place Optical Line Terminals based on community pockets and infrastructure.

**Logic:**
```python
def place_olts(community_pockets, extended_cables):
    """
    For each community pocket:
    1. Count ONTs in pocket
    2. Find nearest main infrastructure cable (288F/144F/96F route)
    3. Apply R16:
       - If pocket ≥2000 ONTs → always place OLT
       - If pocket 500-2000 ONTs → always place OLT (user can review)
       - If pocket <500 ONTs and >15km from others → place OLT (isolated)
       - If pocket <500 ONTs and ≤15km from others → assign to nearest OLT
    4. Place OLT on/near infrastructure cable (<1km from route):
       - Find nearest point on infrastructure cable
       - Place OLT at that point (or very close, <1km)
    5. Validate R15: All ONTs in pocket within 20km of OLT
    6. Assign ONTs to OLT
    """
    pass
```

**Output:**
- OLT locations (GeoJSON)
- OLT-to-ONT assignments

---

### **Step 4: Place FDHs**
**Objective:** Place Feeder Distribution Hubs to connect OLTs to FOSCs.

**Logic:**
```python
def place_fdhs(olts, extended_cables):
    """
    For each OLT:
    1. Find associated infrastructure cables (feeder routes)
    2. Place FDH:
       - Near OLT (within 50m) OR
       - At strategic junction point on infrastructure cable
    3. Assign unique FDH ID (FDH*)
    4. Link FDH to OLT
    5. Prepare for FOSC association (R13)
    """
    pass
```

**Output:**
- FDH locations (GeoJSON)
- FDH-to-OLT associations

---

### **Step 5: Place FOSCs**
**Objective:** Place Fiber Optic Splice Closures at strategic points.

**Logic:**
```python
def place_foscs(extended_cables, fdhs):
    """
    1. Analyze extended cable network:
       - Identify junctions (≥2 cables meet)
       - Find long segments (≥1800m)
       - Detect cable ID changes
       - Detect fiber count transitions (will be determined later)
    2. Place FOSC at each trigger point (R12):
       - Junction of ≥2 cables
       - Segment length ≥1800m
       - Cable ID change point
       - Fiber count transition point
    3. Assign unique FOSC ID (F*)
    4. Associate FOSCs to FDHs (R13):
       - Pair nearest FOSC to each FDH (within same chain)
       - Distance threshold: ≤50m
    5. Create FOSC features
    """
    pass
```

**Output:**
- FOSC locations (GeoJSON)
- FOSC-to-FDH associations

---

### **Step 6: Place MSTs and Aerial Terminals**
**Objective:** Place terminals based on enhanced R10/R11 logic.

**Logic:**
```python
def place_terminals(onts, olt_assignments, extended_cables, foscs):
    """
    For each OLT's assigned ONT group:
    1. Cluster ONTs by proximity (for terminal grouping)
    2. For each ONT cluster:
       a. Count ONTs (1-12 typical)
       b. Find nearest infrastructure cable
       c. Find nearest FOSC
       d. Calculate distances:
          - distance_to_cable
          - distance_to_fosc
       
       e. Apply enhanced decision logic:
          IF distance_to_fosc ≤ 1000m:  # Within 1km of FOSC
              → Place MST
              → Connect via stub cable to FOSC
              → Maximize FOSC splicing
          
          ELIF distance_to_cable < 50m AND distance_to_fosc > 1000m:
              → Place Aerial Terminal
              → Direct connection to infrastructure cable
              → Mid-cable splicing acceptable (FOSC is far)
          
          ELIF distance_to_cable ≥ 200m:
              → Place MST
              → Connect via stub cable to nearest FOSC
       
       f. Create terminal feature (Aerial or MST)
       g. Create drop cables (ONT → Terminal)
       h. If MST: Create stub cable (Terminal → FOSC)
    
    3. Generate terminal layer
    """
    pass
```

**Output:**
- Terminal locations (GeoJSON) - Aerial and MST
- Drop cables (GeoJSON)
- Stub cables (GeoJSON)

---

## 🔌 Cable Sizing Logic

### **Important Constraints:**
- **Infrastructure cables:** Multiples of 12F only (12, 24, 48, 72, 96, 144, 288)
- **Stub cables:** Can be smaller (4F, 1F) or multiples of 12F
- **Drop cables:** Typically 1F or 4F
- **Input cables:** No size specified - design engine determines size

### **Cable Sizing Algorithm:**

```python
def determine_cable_size(downstream_ont_count, cable_type="infrastructure"):
    """
    Determine cable size based on downstream ONT count.
    
    Args:
        downstream_ont_count: Number of ONTs downstream from this cable
        cable_type: "infrastructure", "stub", or "drop"
    
    Returns:
        Cable size (fiber count)
    """
    if cable_type == "drop":
        # Drop cables: 1F or 4F
        return 1  # Typically 1F per ONT
    
    elif cable_type == "stub":
        # Stub cables: Can be 1F, 4F, or multiples of 12F
        if downstream_ont_count <= 1:
            return 1
        elif downstream_ont_count <= 4:
            return 4
        else:
            # Use multiples of 12F
            return round_to_multiple_of_12(downstream_ont_count)
    
    else:  # infrastructure
        # Infrastructure cables: Multiples of 12F only
        # Standard sizes: 12, 24, 48, 72, 96, 144, 288
        
        # Load cable sizing rules
        sizing_rules = load_cable_sizing_rules()
        
        # Determine size based on ONT count
        if downstream_ont_count >= sizing_rules["288F"]["min_ONTs"]:
            return 288
        elif downstream_ont_count >= sizing_rules["144F"]["min_ONTs"]:
            return 144
        elif downstream_ont_count >= sizing_rules["96F"]["min_ONTs"]:
            return 96
        elif downstream_ont_count >= sizing_rules["72F"]["min_ONTs"]:
            return 72
        elif downstream_ont_count >= sizing_rules["48F"]["min_ONTs"]:
            return 48
        elif downstream_ont_count >= sizing_rules["24F"]["min_ONTs"]:
            return 24
        else:
            return 12

def round_to_multiple_of_12(count):
    """Round to nearest multiple of 12F for infrastructure cables."""
    # Standard sizes: 12, 24, 48, 72, 96, 144, 288
    standard_sizes = [12, 24, 48, 72, 96, 144, 288]
    
    # Find appropriate size
    for size in standard_sizes:
        if count <= size:
            return size
    
    # If count exceeds 288, use 288 (or consider multiple cables)
    return 288
```

### **Cable Sizing Process:**

```python
def size_all_cables(design_graph, terminals, foscs, fdhs, olts):
    """
    Size all cables in the network.
    
    Process:
    1. Build complete connectivity graph:
       OLT → FDH → FOSC → Terminal → ONT
    2. For each cable segment:
       a. Count downstream ONTs (using BFS/DFS)
       b. Determine cable type (infrastructure/stub/drop)
       c. Apply sizing logic
       d. Assign cable size
    3. Ensure hierarchy (R14):
       - Feeder: 288F/144F
       - Distribution: 96F/72F/48F
       - Access: 24F/12F
    4. Validate transitions (can only downsize, not upsize)
    """
    pass
```

---

## 📊 Complete Design Flow

```
INPUT:
  - ONT.geojson (Point features)
  - fiber cable.geojson (MultiLineString, NO SIZE specified)

STEP 0: Community Pockets
  → Cluster ONTs
  → Merge/split pockets
  → Output: Community pockets

STEP 1: OLT Placement
  → Place OLTs based on pockets
  → Place on/near infrastructure cables
  → Validate distances (R15)
  → Output: OLT.geojson

STEP 2: FDH Placement
  → Place FDHs near OLTs
  → Link to infrastructure cables
  → Output: FDH.geojson

STEP 3: FOSC Placement
  → Identify trigger points (R12)
  → Place FOSCs
  → Associate to FDHs (R13)
  → Output: splice closure.geojson (FOSC)

STEP 4: Terminal Placement
  → Place MSTs and Aerial Terminals (R10/R11)
  → Output: Terminal.geojson

STEP 5: Cable Extensions (Drop & Stub)
  → Create drop cables (Terminal → ONT, 1F default)
  → Create stub cables (MST → FOSC, size matches MST type)
  → Validate cable lengths
  → Output: drop cable.geojson, stub cable.geojson

STEP 6: Cable Sizing (Infrastructure)
  → Build connectivity graph
  → Count downstream ONTs
  → Determine cable sizes (multiples of 12F)
  → Apply hierarchy (R14)
  → Output: Updated fiber cable.geojson (with sizes)

STEP 7: BOM Generation
  → Count components
  → Calculate cable lengths
  → Generate BOM
  → Output: bom.json, bom_summary.txt

ADVANCED (Placeholder for Future):
  → Infrastructure cable extensions to improve service
  → Extend main infrastructure cables to reduce stub lengths
  → This is an optimization step that can be added later

OUTPUT:
  - All design layers (GeoJSON with sizes)
  - BOM
  - Design validation report
```

---

## 🔑 Key Implementation Notes

### **Cable Extension Logic:**
- Analyze each community's distance from infrastructure
- If >200m and significant ONT count, propose extension
- Extension size based on community ONT count
- Extensions become part of infrastructure network

### **Cable Sizing:**
- **Infrastructure:** 12, 24, 48, 72, 96, 144, 288 (multiples of 12F)
- **Stub:** 1, 4, or multiples of 12F
- **Drop:** 1F or 4F
- Size determined by downstream ONT count
- Maintain hierarchy (R14)

### **Order Matters:**
1. Extend infrastructure first (reduces stub lengths)
2. Create pockets (needed for OLT placement)
3. Place OLTs (needed for terminal assignment)
4. Place FDHs (needed for FOSC association)
5. Place FOSCs (needed for terminal decisions)
6. Place terminals (final step, uses all previous placements)

---

## ✅ Validation Checklist

- [ ] All infrastructure cables are multiples of 12F (12, 24, 48, 72, 96, 144, 288)
- [ ] Stub cables are 1F, 4F, or multiples of 12F
- [ ] Drop cables are 1F or 4F
- [ ] Cable hierarchy maintained (R14)
- [ ] All ONTs within 20km of OLT (R15)
- [ ] FOSC proximity logic applied (R10/R11)
- [ ] All terminals connected to FOSC or infrastructure
- [ ] All ONTs connected to terminals
- [ ] BOM matches design

---

**This logic makes perfect sense!** The order ensures we build infrastructure first, then place components in dependency order, and finally size everything based on actual demand.

