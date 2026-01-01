# Terminal Placement Rules - Final Refined Version

## Verification Results

Based on analysis of **6,370 terminals** (3,770 Aerial + 2,600 MST):

### ✅ Key Findings

1. **Splicing Location:**
   - **Aerial Terminals:** 1,264 (33.5%) cause **mid-cable splicing** (FOSC→Terminal pattern in cable ID)
   - **MST Terminals:** 100% connect via **stub cable directly to FOSC** (no mid-cable splicing)

2. **ONT Count:**
   - **Aerial Terminal:** Median 3.0 ONTs (range: 1-11)
   - **MST:** Median 3.0 ONTs (range: 1-11)
   - **Finding:** ONT count is **similar** - not the primary distinguishing factor

3. **Connection Method:**
   - **Aerial Terminal:** Direct connection to infrastructure cable (may cause mid-cable splicing)
   - **MST:** Always uses stub cable to FOSC (stub is part of MST product)

---

## Refined Rules

### R10: Aerial Terminal Placement

**Purpose:** Direct connection to infrastructure cable for small ONT groups.

**Rule:**
- Aerial terminals are **always placed on infrastructure cables** (288F/144F/96F/72F/48F)
- Used when residential (ONTs) are **near the infrastructure cable** (<50m)
- **Direct connection** to infrastructure cable (no stub cable)
- **May cause mid-cable splicing** (terminal spliced into fiber cable between FOSCs)
- Typically serves **few ONTs** (median 3, range 1-12)

**Decision Logic:**
```
IF residential (ONTs) near infrastructure cable (<50m):
    AND ONT count ≤ 12:
        → Place Aerial Terminal ON infrastructure cable
        → Direct connection (may cause mid-cable splicing)
```

**When to Use:**
- Small number of ONTs (typically ≤6)
- ONTs are very close to infrastructure cable
- Acceptable to have mid-cable splicing

---

### R11: MST Placement

**Purpose:** Connect to FOSC via stub cable to **maximize FOSC splicing** and minimize mid-cable splicing.

**Rule:**
- MST **always has stub cable** (part of MST product)
- MST **always connects to FOSC** via stub cable
- Used to **reduce mid-cable splicing** - all splicing done at FOSC
- Can be used in two scenarios:
  1. **On/near infrastructure cable** (<50m) - but still uses stub to FOSC
  2. **Far from infrastructure cable** (≥200m) - connects community to FOSC

**Decision Logic:**
```
IF need to maximize FOSC splicing (minimize mid-cable splicing):
    → Use MST with stub cable to FOSC
    
OR IF residential (ONTs) ≥200m from infrastructure cable:
    → Use MST with stub cable to nearest FOSC
```

**When to Use:**
- When you want to **avoid mid-cable splicing**
- When you want to **maximize splicing at FOSC** (better organization, easier maintenance)
- When connecting communities far from infrastructure cable (≥200m)
- ONT count: Typically 1-12 (similar to Aerial Terminal)

**Stub Cable:**
- **Always part of MST product**
- Length: ≤500m (standard) or 500-2500m (long-reach)
- Connects MST directly to FOSC

---

## Primary Distinction: Splicing Location

### Aerial Terminal
- **Connection:** Direct to infrastructure cable
- **Splicing:** May cause **mid-cable splicing** (terminal spliced into fiber cable)
- **Use Case:** When mid-cable splicing is acceptable, small ONT groups

### MST
- **Connection:** Via stub cable to FOSC
- **Splicing:** All splicing done at **FOSC** (no mid-cable splicing)
- **Use Case:** When you want to maximize FOSC splicing, better organization

---

## Refined Decision Logic

```python
def choose_terminal_type(onts, infrastructure_cables, foscs):
    """
    Choose between Aerial Terminal and MST.
    
    Primary factor: SPLICING LOCATION (not ONT count)
    """
    # Count ONTs
    ont_count = len(onts)
    
    # Find nearest infrastructure cable
    nearest_cable, distance = find_nearest_infrastructure_cable(onts, infrastructure_cables)
    
    # Find nearest FOSC
    nearest_fosc, fosc_distance = find_nearest_fosc(onts, foscs)
    
    # Decision logic
    if distance < 50:  # Near infrastructure cable
        # Choose based on splicing preference
        if prefer_fosc_splicing():
            # Use MST to maximize FOSC splicing
            return place_mst(onts, nearest_cable, nearest_fosc)
        elif ont_count <= 12:
            # Use Aerial Terminal (may cause mid-cable splicing)
            return place_aerial_terminal(onts, nearest_cable)
        else:
            # Too many ONTs - use MST
            return place_mst(onts, nearest_cable, nearest_fosc)
    
    elif distance >= 200:  # Far from infrastructure cable
        # Always use MST with stub to FOSC
        return place_mst(onts, community_location, nearest_fosc)
    
    else:  # 50-200m from cable
        # Use MST to connect to FOSC
        return place_mst(onts, community_location, nearest_fosc)
```

---

## Updated Rule Definitions

### R10: Aerial Terminal Placement (Final)

**Description:** Place aerial terminal directly on infrastructure cable for small ONT groups.

**Criteria:**
- Residential (ONTs) within **<50m** of infrastructure cable
- ONT count: **1-12** (typically ≤6)
- Infrastructure cable size: **288F, 144F, 96F, 72F, or 48F**
- **Direct connection** to infrastructure cable
- **May cause mid-cable splicing** (terminal spliced into fiber cable)

**Placement:**
- Terminal placed **on the infrastructure cable** (at nearest point)
- Direct connection (no stub cable)
- Splicing may occur mid-cable

**Rationale:**
- Simple, direct connection
- Suitable for small ONT groups
- Acceptable to have mid-cable splicing

---

### R11: MST Placement (Final)

**Description:** Place MST to connect to FOSC via stub cable, maximizing FOSC splicing.

**Criteria:**
- MST **always has stub cable** (part of product)
- MST **always connects to FOSC** via stub cable
- Used to **maximize FOSC splicing** (minimize mid-cable splicing)
- ONT count: **1-12** (similar to Aerial Terminal)

**Placement Scenarios:**
1. **On infrastructure cable** (<50m) - uses stub to FOSC
2. **Far from infrastructure cable** (≥200m) - uses stub to nearest FOSC

**Stub Cable:**
- **Always part of MST product**
- Length: ≤500m (standard) or 500-2500m (long-reach)
- Connects MST directly to FOSC

**Rationale:**
- **Maximizes FOSC splicing** (all splicing at FOSC, not mid-cable)
- Better organization and maintenance
- Easier to manage and troubleshoot

---

## Summary

**Key Insight:**
- **Primary distinction is SPLICING LOCATION, not ONT count**
- **Aerial Terminal:** May cause mid-cable splicing
- **MST:** Always goes to FOSC via stub (maximizes FOSC splicing)

**Decision Factors:**
1. **Splicing preference:** Maximize FOSC splicing → Use MST
2. **Distance:** ≥200m from infrastructure → Use MST
3. **ONT count:** Similar for both (typically 1-12, median 3)

**Your Assumptions Validated:**
- ✅ **MST reduces mid-cable splicing** - goes directly to FOSC
- ✅ **Aerial is for few ONTs** - but MST also serves few ONTs
- ✅ **Primary factor:** Splicing location (FOSC vs mid-cable)



