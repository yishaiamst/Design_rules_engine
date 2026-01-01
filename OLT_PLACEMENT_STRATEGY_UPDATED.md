# OLT Placement Strategy - Updated Based on Field Analysis

## Key Finding from Actual Design Data

**Analysis of 17 OLTs shows:**
- **100% of OLTs are placed directly on or within <1km of main fiber infrastructure (288F/144F/96F)**
- **Average distance to nearest fiber cable: <0.01km** (essentially on the route)
- **Distribution:**
  - 8 OLTs near 288F cables
  - 8 OLTs near 144F cables
  - 1 OLT near 96F cable

## Updated Placement Strategy

### Primary Rule: Place OLT Near Main Fiber Infrastructure

**Strategy:**
1. **Identify main infrastructure cables** (288F, 144F, 96F) in the area
2. **Place OLT at or very close to the fiber route** (within 1km, ideally on the route)
3. **Validate:** Ensure all ONTs in the residential polygon are within 15-20km from the OLT

### Rationale

**Field Deployment Perspective:**
- OLTs need to connect to the main fiber backbone (288F/144F/96F)
- Placing OLTs directly on the fiber route:
  - **Reduces connection costs** (no need for long feeder cables)
  - **Simplifies deployment** (easier access to existing infrastructure)
  - **Improves reliability** (shorter connection paths)
  - **Leverages existing infrastructure** (poles, conduits, etc.)

**Distance Constraint:**
- The constraint is that **ONTs must be within 15-20km**, not that OLT must be at centroid
- This allows flexibility to place OLT at optimal infrastructure location
- Residential polygons can extend up to 20km from the OLT location

---

## Implementation Algorithm

### Step 1: Identify Main Fiber Infrastructure
```python
def find_main_fiber_routes(fiber_cables):
    """
    Filter for main infrastructure cables (288F, 144F, 96F).
    """
    main_routes = []
    for cable in fiber_cables:
        fiber_count = extract_fiber_count(cable)
        if fiber_count >= 96:  # 288F, 144F, or 96F
            main_routes.append(cable)
    return main_routes
```

### Step 2: Find Optimal OLT Location
```python
def place_olt_near_fiber(ont_pocket, main_fiber_routes):
    """
    Place OLT near main fiber infrastructure, ensuring ONTs are within range.
    
    Strategy:
    1. Find nearest main fiber route to ONT pocket centroid
    2. Place OLT on or very close to the fiber route
    3. Validate all ONTs within 15-20km
    """
    # Calculate ONT pocket centroid (for reference)
    centroid = calculate_centroid(ont_pocket.onts)
    
    # Find nearest main fiber route
    nearest_route, distance, nearest_point = find_nearest_fiber_route(
        centroid, main_fiber_routes
    )
    
    # Place OLT on the fiber route (at nearest point)
    olt_location = nearest_point
    
    # Validate all ONTs within 15-20km
    max_distance = max([
        calculate_distance(olt_location, ont) 
        for ont in ont_pocket.onts
    ])
    
    if max_distance > 20.0:  # km
        # If validation fails, we may need:
        # - Additional OLT placement
        # - Or adjust location slightly (but keep near fiber)
        # - Or split the pocket
        return None  # Requires review
    
    return olt_location
```

### Step 3: Validation
```python
def validate_olt_placement(olt_location, ont_pocket):
    """
    Validate that all ONTs are within acceptable range.
    """
    distances = [
        calculate_distance(olt_location, ont)
        for ont in ont_pocket.onts
    ]
    
    max_distance = max(distances)
    mean_distance = statistics.mean(distances)
    
    # R15: Maximum distance constraint
    if max_distance > 20.0:  # km
        return False, f"Max distance {max_distance:.2f}km exceeds 20km limit"
    
    # Optional: Warn if mean distance is high
    if mean_distance > 15.0:  # km
        return True, f"Warning: Mean distance {mean_distance:.2f}km is high"
    
    return True, "OK"
```

---

## Updated R16 Rule Definition

### R16: OLT Placement Strategy (Infrastructure-First)

**Primary Strategy:**
- Place OLT **on or very close to main fiber infrastructure** (288F/144F/96F routes)
- Distance to fiber route: **<1km** (ideally on the route)

**Validation:**
- All ONTs in the residential polygon must be within **15-20km** from the OLT
- If validation fails, consider:
  - Additional OLT placement
  - Pocket splitting
  - Route adjustment (if fiber route data allows)

**Decision Logic:**
```
1. Identify ONT pocket (cluster of ONTs)
2. Find nearest main fiber route (288F/144F/96F)
3. Place OLT on fiber route (at nearest point to pocket)
4. Validate: All ONTs within 20km?
   - YES → Accept placement
   - NO → Review (split pocket, add OLT, or adjust)
```

---

## Comparison: Centroid vs Infrastructure-First

| Approach | Pros | Cons | Use Case |
|----------|------|------|----------|
| **Centroid** | Balanced access to all ONTs | May be far from infrastructure | When no fiber route data available |
| **Infrastructure-First** | Lower deployment costs, simpler | May not be optimal for ONT distances | **Recommended (when fiber routes available)** |

**Recommendation:** Use **Infrastructure-First** approach when fiber route data is available, as it aligns with field deployment practices and reduces costs.

---

## Example Scenarios

### Scenario 1: OLT on 288F Route
```
ONT Pocket: 2000 ONTs spread over 15km diameter
Nearest Fiber: 288F cable passing 2km from pocket centroid

Strategy:
- Place OLT on 288F route (at nearest point to pocket)
- Distance from pocket centroid: 2km
- Max ONT distance: 17km (<20km limit) ✅
```

### Scenario 2: OLT on 144F Route
```
ONT Pocket: 1500 ONTs spread over 12km diameter
Nearest Fiber: 144F cable passing through pocket

Strategy:
- Place OLT directly on 144F route (within pocket)
- Distance from pocket centroid: 0.5km
- Max ONT distance: 12km (<20km limit) ✅
```

### Scenario 3: Validation Failure
```
ONT Pocket: 2500 ONTs spread over 25km diameter
Nearest Fiber: 288F cable at edge of pocket

Strategy:
- Place OLT on 288F route
- Max ONT distance: 22km (>20km limit) ❌
- Action: Split pocket or add second OLT
```

---

## Implementation Notes

1. **Fiber Route Priority:**
   - Prefer 288F > 144F > 96F (larger capacity routes)
   - But consider proximity - if 96F is much closer, use it

2. **Distance Tolerance:**
   - OLT can be up to 1km from fiber route (for practical reasons)
   - But prefer on-route placement when possible

3. **ONT Distance Validation:**
   - Hard limit: 20km (R15)
   - Soft limit: 15km (recommended for better performance)
   - If exceeded, flag for review

4. **Pocket Merging:**
   - When merging pockets, ensure merged pocket diameter ≤15km
   - This ensures OLT placement near fiber route can serve all ONTs

---

## Summary

**Key Insight:** OLT placement should prioritize **proximity to main fiber infrastructure** over geometric centroid, as this aligns with field deployment practices and reduces costs.

**Updated Rule:**
- Place OLT on or near main fiber routes (288F/144F/96F)
- Ensure residential polygon (ONT cluster) is within 15-20km
- This is more practical and cost-effective than centroid placement



