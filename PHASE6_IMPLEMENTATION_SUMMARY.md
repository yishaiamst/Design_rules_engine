# Phase 6 Implementation Summary - Cable Sizing

## ✅ Implementation Complete

### Key Features Implemented

1. **Configuration Override**
   - User can set `default_size_override` in config (e.g., 96F)
   - Takes priority over formula-based sizing
   - Applied to all infrastructure cables

2. **Formula-Based Sizing**
   - Calculates cable sizes based on service requirements
   - Uses `calculate_required_cable_size()` function
   - Considers: ONT count, service level, oversubscription, future growth

3. **FOSC Aggregation Logic**
   - At FOSCs: Sum incoming cable sizes (from infrastructure/OLT side)
   - Example: 48F + 48F = 96F (even if formula says 48F is enough)
   - Safety margin: Use larger size even if formula doesn't require it
   - Applied to outgoing cables at FOSC

4. **Max Size Limit**
   - Configurable `max_size` parameter (default: 288F)
   - All cables capped at max_size
   - Prevents oversized cables

5. **Cable ID Assignment**
   - Only after FOSCs and terminals are placed
   - Pattern: `{SIZE}FOC/{FROM_ID}/{TO_ID}`
   - Uses FOSCs, terminals, and OLTs as FROM/TO nodes

---

## Configuration

### design_config.json

```json
{
  "cables": {
    "infrastructure_cable": {
      "standard_sizes": [12, 24, 48, 72, 96, 144, 288],
      "default_size_override": null,  // Set to 96 for all cables, or null for formula
      "max_size": 288  // Maximum cable size (default 288F)
    }
  }
}
```

### Usage Examples

**Example 1: Use default size for all cables**
```json
"default_size_override": 96
```
→ All infrastructure cables will be 96F

**Example 2: Formula-based with max size**
```json
"default_size_override": null,
"max_size": 288
```
→ Calculate sizes from formula, cap at 288F

**Example 3: Custom max size**
```json
"default_size_override": null,
"max_size": 144
```
→ Calculate from formula, cap at 144F

---

## FOSC Aggregation Logic

### Rule

**At FOSCs:**
1. Identify incoming cables (from infrastructure/OLT side)
2. Sum their sizes: `total = sum(incoming_sizes)`
3. Round up to next standard size
4. Apply to outgoing cables: `outgoing_size = max(current_size, aggregated_size)`
5. Apply max_size limit

### Example

```
FOSC at junction:
  Incoming: 48F + 48F = 96F total
  Outgoing: 48F (from formula)
  Result: Outgoing = max(48F, 96F) = 96F
```

**Even if formula says 48F is enough, we use 96F for safety.**

---

## Process Flow

1. **Check Configuration Override**
   - If `default_size_override` is set → Use for all cables, skip to ID assignment
   - If null → Continue with formula-based sizing

2. **Calculate Initial Sizes**
   - Map OLTs to cables
   - Calculate required fibers from ONT count (service formula)
   - Round to standard sizes
   - Apply min_infrastructure_size (48F)

3. **Apply FOSC Aggregation**
   - For each FOSC:
     - Find connected cables
     - Separate incoming (from OLT) vs outgoing (to ONTs)
     - Sum incoming sizes
     - Apply aggregated size to outgoing cables

4. **Apply Max Size Limit**
   - Cap all cables at max_size

5. **Assign Cable IDs**
   - After FOSCs and terminals are placed
   - Pattern: `{SIZE}FOC/{FROM_ID}/{TO_ID}`
   - Uses FOSCs, terminals, OLTs as nodes

---

## Files Modified

- ✅ `phases/phase6_cable_sizing.py` - Updated with new logic
- ✅ `design_config.json` - Added default_size_override and max_size
- ✅ `generate_design.py` - Updated to pass terminals parameter
- ✅ `PHASE6_IMPLEMENTATION_SUMMARY.md` - This document

---

## Next Steps

1. ✅ **Phase 6 Complete** - Cable sizing with FOSC aggregation
2. ⏳ **Phase 6b** - Refine FOSC placement (convert some terminals to FOSCs)
3. ⏳ **Testing** - Validate cable sizes against actual design
4. ⏳ **Cable Building** - Break cables at break points (if needed)

---

## Summary

**Phase 6 is complete with:**
- ✅ Configuration override support
- ✅ Formula-based sizing
- ✅ FOSC aggregation logic
- ✅ Max size limit
- ✅ Cable ID assignment (after FOSCs and terminals)

**Ready for:**
- Phase 6b: Refine FOSC placement
- Testing and validation

