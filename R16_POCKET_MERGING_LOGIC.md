# R16 Pocket Merging and Validation Logic

## Key Requirements

1. **Merge nearby pockets** (<15km apart) into larger pockets
2. **Validate merged pockets** - check if they meet criteria
3. **Check new communities** - when adding, see if they should merge
4. **Ensure pocket size limits** - no pocket should span >15km in diameter

---

## Pocket Merging Algorithm

### Step 1: Initial Clustering
```
1. Cluster ONTs into initial pockets (2km radius)
2. Calculate pocket centroids
3. Count ONTs per pocket
```

### Step 2: Iterative Merging
```
WHILE there are pockets to merge:
    FOR each pair of pockets:
        IF distance between centroids < 15km:
            → Merge pockets
            → Recalculate centroid
            → Recalculate total ONT count
            → Validate merged pocket size (diameter ≤15km)
    
    IF no merges occurred:
        → BREAK (converged)
```

### Step 3: Validate Merged Pockets
```
FOR each merged pocket:
    Calculate pocket diameter (max distance between any two ONTs in pocket)
    
    IF diameter > 15km:
        → Split pocket (use sub-clustering)
        → Re-validate split pockets
```

### Step 4: Add New Communities
```
WHEN adding new community/pocket:
    1. Check distance to all existing pockets
    2. IF distance to any pocket < 15km:
        → Merge with nearest pocket
        → Recalculate merged pocket properties
        → Validate merged pocket (size, diameter)
    3. ELSE:
        → Create new pocket
```

---

## Detailed Algorithm

### Function: Merge Nearby Pockets

```python
def merge_nearby_pockets(pockets, max_distance_km=15.0):
    """
    Iteratively merge pockets that are within max_distance_km of each other.
    
    Args:
        pockets: List of pocket objects with centroid and ONT list
        max_distance_km: Maximum distance for merging (default 15km)
    
    Returns:
        List of merged pockets
    """
    merged = True
    
    while merged:
        merged = False
        new_pockets = []
        used = set()
        
        for i, pocket1 in enumerate(pockets):
            if i in used:
                continue
            
            # Try to merge with other pockets
            merged_pocket = pocket1.copy()
            
            for j, pocket2 in enumerate(pockets[i+1:], start=i+1):
                if j in used:
                    continue
                
                distance = calculate_distance(pocket1.centroid, pocket2.centroid)
                
                if distance < max_distance_km:
                    # Merge pockets
                    merged_pocket.onts.extend(pocket2.onts)
                    merged_pocket.centroid = calculate_centroid(merged_pocket.onts)
                    merged_pocket.count = len(merged_pocket.onts)
                    used.add(j)
                    merged = True
            
            # Validate merged pocket size
            if merged_pocket.count > 0:
                diameter = calculate_pocket_diameter(merged_pocket.onts)
                
                if diameter > max_distance_km:
                    # Pocket too large - split it
                    sub_pockets = split_large_pocket(merged_pocket, max_distance_km)
                    new_pockets.extend(sub_pockets)
                else:
                    new_pockets.append(merged_pocket)
            
            used.add(i)
        
        pockets = new_pockets
    
    return pockets
```

### Function: Validate Pocket Size

```python
def validate_pocket_size(pocket, max_diameter_km=15.0):
    """
    Ensure pocket doesn't exceed maximum diameter.
    
    Args:
        pocket: Pocket object with ONT list
        max_diameter_km: Maximum allowed diameter
    
    Returns:
        Valid pocket(s) - may be split if too large
    """
    diameter = calculate_pocket_diameter(pocket.onts)
    
    if diameter <= max_diameter_km:
        return [pocket]  # Valid, return as-is
    else:
        # Split into smaller pockets
        return split_large_pocket(pocket, max_diameter_km)
```

### Function: Add New Community

```python
def add_new_community(new_community, existing_pockets, max_distance_km=15.0):
    """
    Add a new community and merge if needed.
    
    Args:
        new_community: New pocket/community to add
        existing_pockets: List of existing pockets
        max_distance_km: Maximum distance for merging
    
    Returns:
        Updated list of pockets
    """
    # Find nearest existing pocket
    nearest_pocket = None
    min_distance = float('inf')
    
    for pocket in existing_pockets:
        distance = calculate_distance(new_community.centroid, pocket.centroid)
        if distance < min_distance:
            min_distance = distance
            nearest_pocket = pocket
    
    # Check if should merge
    if min_distance < max_distance_km and nearest_pocket:
        # Merge with nearest pocket
        merged_pocket = merge_pockets(nearest_pocket, new_community)
        
        # Validate merged pocket
        validated_pockets = validate_pocket_size(merged_pocket, max_distance_km)
        
        # Replace nearest_pocket with validated pockets
        existing_pockets.remove(nearest_pocket)
        existing_pockets.extend(validated_pockets)
    else:
        # Add as new pocket
        existing_pockets.append(new_community)
    
    return existing_pockets
```

### Function: Calculate Pocket Diameter

```python
def calculate_pocket_diameter(onts):
    """
    Calculate maximum distance between any two ONTs in pocket.
    
    Args:
        onts: List of ONT coordinates
    
    Returns:
        Diameter in kilometers
    """
    max_distance = 0.0
    
    for i, ont1 in enumerate(onts):
        for ont2 in onts[i+1:]:
            distance = calculate_distance(ont1.coordinates, ont2.coordinates)
            max_distance = max(max_distance, distance)
    
    return max_distance
```

---

## Complete Workflow

### Phase 1: Initial Clustering
```
1. Cluster ONTs into initial pockets (2km radius)
   → Pocket A: 800 ONTs, centroid at (lat1, lon1)
   → Pocket B: 600 ONTs, centroid at (lat2, lon2)
   → Pocket C: 400 ONTs, centroid at (lat3, lon3)
```

### Phase 2: Check Distances
```
Distance A-B: 12km (<15km) → Should merge
Distance A-C: 18km (>15km) → Don't merge
Distance B-C: 20km (>15km) → Don't merge
```

### Phase 3: Merge Nearby Pockets
```
Merge A + B:
   → New Pocket AB: 1400 ONTs
   → New centroid: weighted average
   → Validate diameter: 14km (<15km) ✅
```

### Phase 4: Validate Merged Pocket
```
Pocket AB:
   - ONT count: 1400
   - Diameter: 14km (<15km) ✅
   - Decision: Keep as single pocket
```

### Phase 5: Add New Community
```
New Pocket D: 500 ONTs, centroid at (lat4, lon4)
Distance D-AB: 10km (<15km) → Merge
Distance D-C: 25km (>15km) → Don't merge

Merge D + AB:
   → New Pocket ABD: 1900 ONTs
   → Validate diameter: 16km (>15km) ❌
   → Split into smaller pockets
```

### Phase 6: Split Large Pocket
```
Pocket ABD too large (16km diameter):
   → Split using sub-clustering
   → Pocket AB: 1400 ONTs, diameter 12km ✅
   → Pocket D: 500 ONTs, diameter 3km ✅
```

---

## Updated Decision Tree

```
1. Cluster ONTs into initial pockets (2km radius)

2. Iterative Merging:
   WHILE changes occur:
       FOR each pair of pockets:
           IF distance < 15km:
               → Merge
               → Recalculate properties
       
       FOR each merged pocket:
           IF diameter > 15km:
               → Split
               → Re-validate

3. For each final pocket:
   │
   ├─ Pocket size ≥ 2000 ONTs?
   │  └─ YES → Place OLT
   │
   ├─ Pocket size 500-2000 ONTs?
   │  └─ YES → Place OLT (user can review)
   │
   ├─ Pocket size < 500 ONTs?
   │  │
   │  ├─ Distance to nearest pocket > 15km?
   │  │  └─ YES → Place OLT (isolated)
   │  │
   │  └─ Distance to nearest pocket ≤ 15km?
   │     └─ YES → Should have merged! (re-check)
```

---

## Validation Rules

### Rule 1: Pocket Diameter Constraint
- **No pocket should span >15km in diameter**
- If merged pocket exceeds 15km, split it
- Use sub-clustering to split large pockets

### Rule 2: Merging Constraint
- **Pockets <15km apart should be merged**
- After merging, validate diameter
- If still too large, split appropriately

### Rule 3: New Community Integration
- **When adding new community, check all existing pockets**
- Merge if within 15km of any pocket
- Validate merged pocket size
- Re-check all pockets after merge

### Rule 4: Iterative Convergence
- **Continue merging until no more merges possible**
- After each merge, re-check all pocket pairs
- Ensure convergence (no infinite loops)

---

## Example Scenarios

### Scenario 1: Simple Merge
```
Initial:
  Pocket A: 800 ONTs, centroid (0, 0)
  Pocket B: 600 ONTs, centroid (0, 12km)
  Distance: 12km (<15km)

After Merge:
  Pocket AB: 1400 ONTs, centroid (0, 6km)
  Diameter: 12km (<15km) ✅
  Decision: Place OLT (1400 ONTs, 500-2000 range)
```

### Scenario 2: Merge Creates Large Pocket
```
Initial:
  Pocket A: 1000 ONTs, centroid (0, 0)
  Pocket B: 800 ONTs, centroid (0, 14km)
  Distance: 14km (<15km)

After Merge:
  Pocket AB: 1800 ONTs
  Diameter: 16km (>15km) ❌

Split:
  Pocket A': 1000 ONTs, diameter 8km ✅
  Pocket B': 800 ONTs, diameter 6km ✅
  Decision: Both get OLTs (both 500-2000 range)
```

### Scenario 3: Adding New Community
```
Existing:
  Pocket A: 1200 ONTs, centroid (0, 0)

New:
  Pocket B: 500 ONTs, centroid (0, 10km)
  Distance: 10km (<15km)

Merge:
  Pocket AB: 1700 ONTs, centroid (0, 5km)
  Diameter: 10km (<15km) ✅
  Decision: Place OLT (1700 ONTs, 500-2000 range)
```

### Scenario 4: Multiple Merges
```
Initial:
  Pocket A: 600 ONTs, centroid (0, 0)
  Pocket B: 500 ONTs, centroid (0, 10km)
  Pocket C: 400 ONTs, centroid (0, 20km)

Iteration 1:
  A-B distance: 10km → Merge → AB: 1100 ONTs
  AB-C distance: 15km → Don't merge (exactly 15km)

Final:
  Pocket AB: 1100 ONTs, diameter 10km ✅ → Place OLT
  Pocket C: 400 ONTs, isolated → Place OLT (isolated)
```

---

## Implementation Considerations

### 1. Distance Calculation
- Use Haversine formula for geographic distances
- Account for coordinate system (WGS84, UTM, etc.)

### 2. Centroid Calculation
- Weighted average of ONT coordinates
- Or geometric centroid of ONT locations

### 3. Diameter Calculation
- Maximum pairwise distance between ONTs
- Or bounding box diagonal
- Or convex hull diameter

### 4. Splitting Large Pockets
- Use K-means clustering (k=2 or more)
- Or DBSCAN with appropriate parameters
- Or geographic splitting (divide by median)

### 5. Performance
- Use spatial indexing (R-tree) for fast distance queries
- Cache distance calculations
- Limit iterations to prevent infinite loops

---

## Updated R16 Rule Summary

**Pocket Management:**
1. Cluster ONTs into initial pockets (2km radius)
2. Iteratively merge pockets <15km apart
3. Validate merged pockets (diameter ≤15km)
4. Split pockets that exceed 15km diameter
5. When adding new communities, check for merging

**OLT Placement:**
- ≥2000 ONTs → Always place OLT
- 500-2000 ONTs → Always place OLT (user can review)
- <500 ONTs, isolated (>15km) → Place OLT
- <500 ONTs, not isolated → Assign to nearest OLT

This ensures pockets are properly sized and merged, preventing oversized pockets and ensuring efficient OLT placement!




