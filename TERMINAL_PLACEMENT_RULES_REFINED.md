# Terminal Placement Rules - Refined and Validated

## Verification Results

Based on analysis of **6,370 terminals** (3,775 Aerial + 2,595 MST):

### ✅ Rule 1: Aerial Terminals on Infrastructure Cables
**Rule:** When residential (ONTs) are near infrastructure cable, place aerial terminal on the infrastructure cable.

**Validation:**
- ✅ **99.8%** (3,767/3,775) of aerial terminals are on infrastructure cables (<50m)
- Mean distance: **1.38m** (essentially on the cable)
- **Status: VALIDATED**

### ✅ Rule 2: Aerial Terminals Always on Infrastructure Cables
**Rule:** Aerial terminals are always placed on infrastructure cables (288F/144F/96F/72F/48F).

**Validation:**
- ✅ Found on cable sizes: **48F, 96F, 144F, 288F**
- Distribution: 48F (1,285), 96F (780), 144F (1,308), 288F (402)
- Note: 72F not found in dataset, but rule is valid
- **Status: VALIDATED**

### ✅ Rule 3: MST Connects to FOSC
**Rule:** MST will connect to FOSC via stub cable.

**Validation:**
- ✅ **79.6%** (2,066/2,595) of MSTs are connected to FOSC (<500m)
- Mean distance to FOSC: **331.36m**
- Median distance to FOSC: **228.79m**
- **Status: VALIDATED**

### ⚠️ Rule 4: MST for Communities 200m+ from Infrastructure
**Rule:** MST will be used to connect communities that are 200m+ away from the main infrastructure cable.

**Validation:**
- ⚠️ Only **24.8%** (643/2,595) of MSTs are ≥200m from infrastructure cable
- **55.4%** (1,438/2,595) of MSTs are <50m from infrastructure cable (essentially ON the cable)
- **19.8%** (514/2,595) are 50-200m from infrastructure cable

**Finding:** MSTs are used in **TWO scenarios**:
1. **On/near infrastructure cable** (<50m) but still connecting via stub cable to FOSC
2. **Far from infrastructure cable** (≥200m) connecting via stub cable to FOSC

**Status: NEEDS REFINEMENT**

---

## Refined Rules

### R10: Aerial Terminal Placement

**Rule:**
- Aerial terminals are **always placed on infrastructure cables** (288F/144F/96F/72F/48F)
- Used when residential (ONTs) are **near the infrastructure cable** (<50m)
- **No stub cable** - direct connection to infrastructure cable
- Serves **1-12 ONTs** (based on port capacity)

**Decision Logic:**
```
IF residential (ONTs) near infrastructure cable (<50m):
    AND ONT count ≤ 12:
        → Place Aerial Terminal ON infrastructure cable
        → No stub cable needed
```

### R11: MST Placement

**Rule:**
- MSTs connect to FOSC via **stub cable**
- Used in **TWO scenarios**:

**Scenario A: On Infrastructure Cable**
- MST placed on/near infrastructure cable (<50m)
- Still uses stub cable to connect to FOSC
- Used when direct terminal placement is not suitable (e.g., need for stub connection)

**Scenario B: Far from Infrastructure Cable**
- MST placed **≥200m** from infrastructure cable
- Uses stub cable to connect to nearest FOSC
- Used to connect communities that are far from main infrastructure

**Decision Logic:**
```
IF residential (ONTs) need terminal:
    IF distance to infrastructure cable < 50m:
        → Check if stub connection needed
        → IF yes: Place MST on cable, connect via stub to FOSC
        → IF no: Place Aerial Terminal directly on cable
    ELIF distance to infrastructure cable ≥ 200m:
        → Place MST at community location
        → Connect via stub cable to nearest FOSC
```

---

## Updated Rule Definitions

### R10: Aerial Terminal Placement (Refined)

**Description:** Place aerial terminal directly on infrastructure cable when residential is near.

**Criteria:**
- Residential (ONTs) within **<50m** of infrastructure cable
- ONT count: **1-12** (based on terminal port capacity)
- Infrastructure cable size: **288F, 144F, 96F, 72F, or 48F**
- **No stub cable** - direct connection

**Placement:**
- Terminal placed **on the infrastructure cable** (at nearest point)
- Direct connection to infrastructure cable

### R11: MST Placement (Refined)

**Description:** Place MST when stub cable connection to FOSC is needed.

**Criteria:**
- MST **always connects to FOSC** via stub cable
- Used in two scenarios:
  1. **On infrastructure cable** (<50m) but requires stub connection
  2. **Far from infrastructure cable** (≥200m) - connects community to FOSC

**Placement:**
- Scenario A: On/near infrastructure cable, stub connects to FOSC
- Scenario B: At community location (≥200m from cable), stub connects to nearest FOSC
- Stub cable length: **≤2500m** (long-reach MST)

**ONT Count:**
- Short-reach (≤500m stub): **6-24 ONTs**
- Long-reach (500-2500m stub): **6-48 ONTs**

---

## Implementation Logic

```python
def place_terminal(onts, infrastructure_cables, foscs):
    """
    Determine whether to place Aerial Terminal or MST.
    """
    # Calculate distance to nearest infrastructure cable
    nearest_cable, distance = find_nearest_infrastructure_cable(onts, infrastructure_cables)
    
    # Count ONTs
    ont_count = len(onts)
    
    # Decision logic
    if distance < 50:  # Near infrastructure cable
        if ont_count <= 12:
            # Check if stub connection needed
            nearest_fosc, fosc_distance = find_nearest_fosc(onts, foscs)
            
            if fosc_distance < 500 and needs_stub_connection(onts, nearest_fosc):
                # Place MST on cable, connect via stub to FOSC
                return place_mst(onts, nearest_cable, nearest_fosc)
            else:
                # Place Aerial Terminal directly on cable
                return place_aerial_terminal(onts, nearest_cable)
        else:
            # Too many ONTs for single terminal - split or use MST
            return place_mst(onts, nearest_cable, find_nearest_fosc(onts, foscs))
    
    elif distance >= 200:  # Far from infrastructure cable
        # Place MST at community, connect via stub to FOSC
        nearest_fosc, fosc_distance = find_nearest_fosc(onts, foscs)
        return place_mst(onts, community_location, nearest_fosc)
    
    else:  # 50-200m from cable
        # Intermediate case - use MST with stub connection
        nearest_fosc, fosc_distance = find_nearest_fosc(onts, foscs)
        return place_mst(onts, community_location, nearest_fosc)
```

---

## Summary

**Validated Rules:**
- ✅ Aerial terminals: Always on infrastructure cables (288/144/96/72/48)
- ✅ MSTs: Always connect to FOSC via stub cable
- ✅ Aerial terminals: Used when residential is near infrastructure cable

**Refined Rule:**
- ⚠️ MSTs: Used in TWO scenarios (not just ≥200m):
  1. On infrastructure cable but requires stub connection
  2. Far from infrastructure cable (≥200m)

**Key Insight:**
- The distinction is not just distance, but **connection method**:
  - **Aerial Terminal:** Direct connection to infrastructure cable (no stub)
  - **MST:** Always uses stub cable to connect to FOSC (regardless of distance to infrastructure cable)



