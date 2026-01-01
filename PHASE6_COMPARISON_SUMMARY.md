# Phase 6 Cable Sizing - Comparison Results

## Current Status

**Match Rate: 16.0%** (726/4,536 cables match actual design)

### Size Distribution Comparison

| Size | Actual Design | Generated | Difference |
|------|---------------|-----------|------------|
| 288F | 461 | 1,680 | +1,219 (oversized) |
| 144F | 1,726 | 309 | -1,417 (undersized) |
| 96F | 679 | 0 | -679 (missing) |
| 72F | 55 | 1 | -54 (missing) |
| 48F | 1,482 | 991 | -491 (undersized) |
| 24F | 71 | 0 | -71 (missing) |
| 12F | 62 | 1,558 | +1,496 (too many defaults) |

### Key Findings

✅ **Improvements:**
- 2,978 cables now have OLT connections (up from 17)
- Network traversal is working (downstream tracing from OLTs)
- Large OLTs (10,062 ONTs) are correctly requiring 288F cables

⚠️ **Issues:**
1. **Oversizing:** Many 48F cables are being sized as 288F because they're connected to large OLTs
   - Example: `48FOC/T1001007/F1000256` should be 48F but generated as 288F
   - Cause: Propagating full OLT capacity to all downstream cables

2. **Undersizing:** Many 144F cables are being sized as 12F (1,558 total)
   - Cause: Cables not reachable through FOSC graph or not connected to OLTs

3. **Missing sizes:** No 96F, 72F, or 24F cables generated
   - Cause: Formula/standard sizes don't match actual design patterns

### Root Causes

1. **Network Topology:** We're not distinguishing between:
   - Main trunk cables (should sum all downstream)
   - Branch cables (should size based on their specific OLT)

2. **FOSC Graph:** 1,558 cables aren't connected through FOSCs, so they default to 12F

3. **Sizing Logic:** All cables in a path get the same size (sum of all downstream OLTs), but actual design has size transitions at FOSCs

### Next Steps

1. **Improve network topology understanding:**
   - Identify main trunk vs. branch cables
   - Size branches individually, sum for trunks

2. **Fix FOSC connectivity:**
   - Improve FOSC-cable graph building
   - Handle cables not connected through FOSCs

3. **Add size transitions:**
   - Implement Phase 6b to place FOSCs at size transitions
   - Size cables based on their position in the network hierarchy

