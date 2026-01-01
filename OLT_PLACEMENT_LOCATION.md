# OLT Placement Location Strategy

## Current Approach: Centroid Placement

**Yes, currently we're placing OLT at the pocket centroid**, but let's refine this based on real-world considerations.

---

## What is "Centroid"?

### Option 1: Geometric Centroid (Current)
- **Definition:** Average of all ONT coordinates
- **Formula:** `centroid = (avg(latitudes), avg(longitudes))`
- **Pros:** Simple, balanced distribution
- **Cons:** May not be optimal for network topology

### Option 2: Weighted Centroid
- **Definition:** Weighted average (if ONTs have different weights)
- **Formula:** `weighted_centroid = Σ(weight_i × coord_i) / Σ(weight_i)`
- **Pros:** Can account for subscriber density
- **Cons:** Requires weight information

### Option 3: Center of Minimum Distance
- **Definition:** Point that minimizes maximum distance to all ONTs
- **Algorithm:** Minimize max distance (1-center problem)
- **Pros:** Ensures all ONTs within minimum radius
- **Cons:** More complex calculation

### Option 4: Strategic Location
- **Definition:** Near fiber cable route, infrastructure, or optimal network point
- **Considerations:**
  - Proximity to main fiber route
  - Access to power/utilities
  - Minimize cable lengths
  - Network topology optimization
- **Pros:** Real-world practical
- **Cons:** Requires additional data (fiber routes, infrastructure)

---

## Recommended Approach: Hybrid Strategy

### Primary: Centroid with Constraints

```python
def place_olt(pocket, fiber_routes=None):
    """
    Place OLT for a pocket of ONTs.
    
    Strategy:
    1. Calculate geometric centroid
    2. If fiber route available, adjust toward route
    3. Ensure all ONTs within 20km (R15)
    4. Optimize for network topology
    """
    # Step 1: Calculate centroid
    centroid = calculate_geometric_centroid(pocket.onts)
    
    # Step 2: Check if near fiber route
    if fiber_routes:
        nearest_route_point = find_nearest_point_on_route(centroid, fiber_routes)
        distance_to_route = calculate_distance(centroid, nearest_route_point)
        
        # If centroid is far from route, adjust toward route
        if distance_to_route > 2.0:  # km
            # Place OLT closer to route (but still near centroid)
            olt_location = interpolate_point(centroid, nearest_route_point, factor=0.7)
        else:
            olt_location = centroid
    else:
        olt_location = centroid
    
    # Step 3: Validate all ONTs within 20km
    max_distance = max([calculate_distance(olt_location, ont) for ont in pocket.onts])
    if max_distance > 20.0:  # km
        # Adjust to minimize max distance
        olt_location = optimize_for_max_distance(pocket.onts, olt_location)
    
    return olt_location
```

---

## Placement Strategies by Scenario

### Scenario 1: Dense Urban Pocket
```
Pocket: 2000 ONTs in 5km × 5km area
Centroid: Center of dense cluster

Strategy: Place at centroid
Rationale: Balanced access to all ONTs
```

### Scenario 2: Linear Pocket (Along Road/Route)
```
Pocket: 1500 ONTs along 20km road
Centroid: Middle of road

Strategy: Place near fiber route (if available)
Rationale: Easier to connect to main infrastructure
```

### Scenario 3: Scattered Rural Pocket
```
Pocket: 800 ONTs spread over 12km diameter
Centroid: Geographic center

Strategy: Place at centroid, validate max distance
Rationale: Minimize maximum distance to all ONTs
```

### Scenario 4: Pocket Near Existing Infrastructure
```
Pocket: 1200 ONTs, centroid 3km from existing fiber route

Strategy: Place closer to fiber route (70% toward route)
Rationale: Reduce connection costs, leverage existing infrastructure
```

---

## Refined Placement Algorithm

### Step 1: Calculate Initial Centroid
```python
centroid = geometric_centroid(pocket.onts)
```

### Step 2: Consider Fiber Route Proximity
```python
IF fiber_routes available:
    nearest_route_point = find_nearest_on_route(centroid, fiber_routes)
    distance_to_route = calculate_distance(centroid, nearest_route_point)
    
    IF distance_to_route > 2km:
        # Adjust toward route (but keep near centroid)
        olt_location = weighted_average(centroid, nearest_route_point, weights=[0.7, 0.3])
    ELSE:
        olt_location = centroid
ELSE:
    olt_location = centroid
```

### Step 3: Validate Distance Constraints
```python
max_distance = max([distance(olt_location, ont) for ont in pocket.onts])

IF max_distance > 20km:
    # Optimize to minimize max distance
    olt_location = minimize_max_distance(pocket.onts, initial_location=olt_location)
```

### Step 4: Consider Infrastructure
```python
# Optional: Adjust for infrastructure availability
IF power_utilities available:
    nearest_utility = find_nearest_utility(olt_location)
    IF distance_to_utility < 1km:
        # Prefer location near utilities
        olt_location = adjust_toward_utility(olt_location, nearest_utility)
```

---

## Implementation Options

### Option A: Simple Centroid (Initial Implementation)
- **Use:** Geometric centroid
- **Pros:** Simple, fast, good starting point
- **Cons:** May not be optimal for network topology
- **When to use:** Initial implementation, no fiber route data

### Option B: Centroid + Route Adjustment (Recommended)
- **Use:** Centroid, adjusted toward fiber route if available
- **Pros:** Practical, considers infrastructure
- **Cons:** Requires fiber route data
- **When to use:** When fiber route information is available

### Option C: Optimized Location (Advanced)
- **Use:** Minimize maximum distance or total cable length
- **Pros:** Mathematically optimal
- **Cons:** More complex, computationally expensive
- **When to use:** Final optimization phase

---

## Updated Rule Definition

### R16 OLT Placement Location

**Primary Strategy:**
- Place OLT at pocket centroid (geometric center of ONTs)

**Adjustments:**
- If fiber route available and centroid >2km from route:
  - Adjust location 70% toward route, 30% keep centroid
- Validate: All ONTs must be within 20km (R15)
- If validation fails, optimize location to minimize max distance

**Rationale:**
- Centroid provides balanced access to all ONTs
- Adjusting toward fiber route reduces connection costs
- Validation ensures R15 compliance

---

## Example Calculations

### Example 1: Simple Centroid
```
Pocket ONTs:
  ONT1: (40.0, -74.0)
  ONT2: (40.1, -74.0)
  ONT3: (40.0, -74.1)
  ONT4: (40.1, -74.1)

Centroid: (40.05, -74.05)
OLT Location: (40.05, -74.05)
```

### Example 2: Centroid with Route Adjustment
```
Pocket Centroid: (40.0, -74.0)
Nearest Fiber Route Point: (40.02, -74.01)
Distance to Route: 2.5km (>2km threshold)

Adjusted Location:
  - 70% toward route: (40.014, -74.007)
  - 30% keep centroid: (40.0, -74.0)
  - Final: (40.0098, -74.0049)
```

### Example 3: Validation Failure
```
Initial Centroid: (40.0, -74.0)
Max Distance to ONTs: 22km (>20km limit)

Optimized Location: (40.01, -74.01)
Max Distance to ONTs: 19.5km (<20km limit) ✅
```

---

## Recommendation

**For Initial Implementation:**
1. Start with **geometric centroid** (simple, fast)
2. Validate all ONTs within 20km
3. If validation fails, adjust location

**For Production:**
1. Use **centroid + route adjustment** (if fiber route data available)
2. Validate distance constraints
3. Consider infrastructure availability
4. Optional: Optimize for network topology

**For User Review:**
- Allow user to manually adjust OLT location
- Show distance metrics (max, mean, median)
- Flag if location is suboptimal

---

## Summary

**Yes, OLT is placed at centroid**, but with these considerations:

1. **Primary:** Geometric centroid of ONT pocket
2. **Adjustment:** Toward fiber route if available (>2km away)
3. **Validation:** All ONTs must be within 20km
4. **Optimization:** If validation fails, adjust to minimize max distance
5. **User Control:** Allow manual adjustment during review

This balances simplicity with practical network considerations!




