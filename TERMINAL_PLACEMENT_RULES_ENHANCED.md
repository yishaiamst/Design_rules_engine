# Terminal Placement Rules - Enhanced with FOSC Proximity Logic

## Objective
**Minimize mid-cable splicing activity** by maximizing FOSC splicing.

## Enhanced Decision Logic

### Primary Distinction
**Splicing Location (FOSC vs mid-cable), not ONT count**

### Refined Rules

#### R10: Aerial Terminal Placement (Enhanced)

**Use Aerial Terminal when:**
- Communities are **near infrastructure cable** (<50m)
- **AND** nearest FOSC is **>1km away**
- Direct connection to infrastructure cable is acceptable
- Mid-cable splicing is acceptable when FOSC is far

**Criteria:**
- Residential (ONTs) within **<50m** of infrastructure cable
- Nearest FOSC is **>1km away**
- ONT count: **1-12** (typically ≤6, median 3)
- Infrastructure cable size: **288F, 144F, 96F, 72F, or 48F**
- **Direct connection** to infrastructure cable (no stub cable)
- May cause mid-cable splicing (acceptable when FOSC is far)

**Rationale:**
- When FOSC is far (>1km), it's more practical to connect directly to infrastructure cable
- Mid-cable splicing is acceptable in this scenario
- Simpler deployment when FOSC is not nearby

---

#### R11: MST Placement (Enhanced)

**Use MST when:**
- Communities are **within 1km of a FOSC**
- **OR** communities are **≥200m from infrastructure cable**
- Objective: **Maximize FOSC splicing** and minimize mid-cable splicing

**Criteria:**
- MST **always has stub cable** (part of product)
- MST **always connects to FOSC** via stub cable
- **Primary use case:** Communities within **≤1km of FOSC** → use MST to maximize FOSC splicing
- **Secondary use case:** Communities **≥200m from infrastructure cable** → use MST to connect to nearest FOSC
- ONT count: **1-12** (typically ≤6, median 3, similar to Aerial Terminal)
- Stub cable length: **≤500m** (standard) or **500-2500m** (long-reach)

**Rationale:**
- **Maximizes FOSC splicing** (all splicing at FOSC, no mid-cable splicing)
- When FOSC is nearby (≤1km), use MST to connect to it
- Better organization and maintenance
- Easier to manage and troubleshoot

---

## Decision Flow

```
FOR each community (group of ONTs):
    1. Find nearest infrastructure cable
    2. Find nearest FOSC
    3. Calculate distances:
       - distance_to_cable = distance to nearest infrastructure cable
       - distance_to_fosc = distance to nearest FOSC
    
    4. DECISION LOGIC:
    
    IF distance_to_fosc ≤ 1000m:  # Within 1km of FOSC
        → Use MST
        → Connect via stub cable to FOSC
        → Maximize FOSC splicing (no mid-cable splicing)
    
    ELIF distance_to_cable < 50m AND distance_to_fosc > 1000m:
        → Use Aerial Terminal
        → Direct connection to infrastructure cable
        → Mid-cable splicing acceptable (FOSC is far)
    
    ELIF distance_to_cable ≥ 200m:
        → Use MST
        → Connect via stub cable to nearest FOSC
        → Connect community to FOSC
    
    ELSE:  # 50-200m from cable, >1km from FOSC
        → Use Aerial Terminal
        → Direct connection to infrastructure cable
```

---

## Analysis Results

Based on analysis of **6,370 terminals**:

### Current Distribution
- **Aerial Terminals near FOSC (≤1km):** 3,555 (94.2%)
  - **1,131 (31.8%) cause mid-cable splicing** → Could use MST instead!
- **Aerial Terminals far from FOSC (>1km):** 220 (5.8%)
  - **135 (61.4%) cause mid-cable splicing** → Acceptable (FOSC is far)

- **MST Terminals near FOSC (≤1km):** 2,444 (94.2%)
- **MST Terminals far from FOSC (>1km):** 151 (5.8%)

### Potential Improvement
- **Current mid-cable splicing (aerial near FOSC):** 1,131 terminals
- **If converted to MST:** 0 mid-cable splicing
- **Reduction:** 1,131 terminals (**30.0% of all aerial terminals**)

### Distance Statistics
- **Aerial terminals near FOSC:**
  - Mean distance: **340.4m**
  - Median distance: **273.2m**
  - Max distance: **1000.0m**

- **MST terminals near FOSC:**
  - Mean distance: **300.7m**
  - Median distance: **248.8m**
  - Max distance: **999.2m**

---

## Implementation Logic

```python
def choose_terminal_type(onts, infrastructure_cables, foscs):
    """
    Choose between Aerial Terminal and MST based on FOSC proximity.
    Objective: Minimize mid-cable splicing by maximizing FOSC splicing.
    """
    # Count ONTs
    ont_count = len(onts)
    
    # Find nearest infrastructure cable
    nearest_cable, distance_to_cable = find_nearest_infrastructure_cable(onts, infrastructure_cables)
    
    # Find nearest FOSC
    nearest_fosc, distance_to_fosc = find_nearest_fosc(onts, foscs)
    
    # Decision logic
    if distance_to_fosc <= 1000:  # Within 1km of FOSC
        # Use MST to maximize FOSC splicing
        return place_mst(onts, community_location, nearest_fosc)
    
    elif distance_to_cable < 50 and distance_to_fosc > 1000:
        # Near infrastructure cable but far from FOSC
        # Use Aerial Terminal (mid-cable splicing acceptable)
        if ont_count <= 12:
            return place_aerial_terminal(onts, nearest_cable)
        else:
            # Too many ONTs - use MST anyway
            return place_mst(onts, nearest_cable, nearest_fosc)
    
    elif distance_to_cable >= 200:  # Far from infrastructure cable
        # Always use MST to connect to FOSC
        return place_mst(onts, community_location, nearest_fosc)
    
    else:  # 50-200m from cable, >1km from FOSC
        # Use Aerial Terminal
        if ont_count <= 12:
            return place_aerial_terminal(onts, nearest_cable)
        else:
            return place_mst(onts, nearest_cable, nearest_fosc)
```

---

## Summary

**Enhanced Logic:**
1. **If community ≤1km from FOSC → Use MST** (maximize FOSC splicing)
2. **If community near infrastructure cable (>1km from FOSC) → Use Aerial Terminal** (mid-cable splicing acceptable)

**Key Benefits:**
- **Minimizes mid-cable splicing** by prioritizing FOSC connections when nearby
- **Maximizes FOSC splicing** for better organization and maintenance
- **Clear decision criteria** based on FOSC proximity
- **Potential reduction:** 30% of mid-cable splicing can be eliminated

**Primary Distinction:**
- **Splicing Location (FOSC vs mid-cable), not ONT count**
- **FOSC proximity (≤1km) is the key decision factor**



