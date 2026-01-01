# OLT Placement Analysis: Generated vs Actual Design

## 🔍 Key Findings

### **1. Actual OLT Placement Strategy**

**Critical Discovery:** Actual OLTs are placed using a **hybrid approach**:
- ✅ **100% of actual OLTs are on infrastructure cables** (0.00 km distance)
- ✅ **Actual OLTs are much closer to ONT centroids** than generated OLTs
- ✅ **Strategy:** Place OLT on infrastructure cable **at the point closest to ONT centroid**

### **2. Comparison Statistics**

| Metric | Generated | Actual | Difference |
|--------|-----------|--------|------------|
| **Mean distance to infrastructure** | 0.89 km | **0.00 km** | ✅ Actual is better |
| **Mean distance to ONT centroid** | 10.44 km | **2.95 km** | ⚠️ Actual is much better |
| **Mean distance between placements** | - | 10.44 km | - |

**Key Insight:** Actual design prioritizes **both** infrastructure proximity AND centroid proximity!

---

## 📊 Detailed Comparison

### **Placement Distance Analysis**

| Generated OLT | Actual OLT | Distance | Gen→Cable | Actual→Cable | Gen→Centroid | Actual→Centroid |
|---------------|------------|----------|-----------|--------------|--------------|-----------------|
| OLT_POCKET_0001_MERGED | 103 | 4.98 km | 0.35 km | **0.00 km** | 7.88 km | **3.11 km** |
| OLT_POCKET_0002_MERGED | 401 | 8.99 km | 1.07 km | **0.00 km** | 10.56 km | **4.03 km** |
| OLT_POCKET_0003_MERGED | 402 | 14.92 km | 1.45 km | **0.00 km** | 12.77 km | **2.15 km** |
| OLT_POCKET_0006_MERGED | 101 | 16.57 km | 0.06 km | **0.00 km** | 16.60 km | **2.59 km** |
| OLT_POCKET_0021_MERGED | 501 | 3.95 km | 0.94 km | **0.00 km** | 6.66 km | **3.07 km** |

**Pattern:** Actual OLTs are consistently:
- ✅ **On infrastructure** (0.00 km)
- ✅ **Much closer to centroid** (2-4 km vs 7-17 km)

---

## 🎯 Actual Design Logic (Inferred)

### **Step 1: Identify Infrastructure Cables**
- Find all main infrastructure cables (288F/144F/96F) in the area

### **Step 2: Calculate ONT Centroid**
- Calculate geometric centroid of all ONTs assigned to the OLT

### **Step 3: Find Optimal Point on Infrastructure**
- For each infrastructure cable near the centroid:
  - Find the point on the cable closest to the ONT centroid
  - Calculate distance from that point to centroid
- Select the infrastructure cable + point that minimizes distance to centroid

### **Step 4: Place OLT**
- Place OLT at the selected point on infrastructure cable
- Validate all ONTs within 25km

---

## ⚠️ Current Implementation Issues

### **Issue 1: Nearest Cable Selection**
- **Current:** Finds nearest infrastructure cable to pocket centroid
- **Problem:** May not be the best cable for minimizing centroid distance
- **Example:** OLT_POCKET_0006_MERGED is 0.06 km from cable, but 16.60 km from centroid

### **Issue 2: Point Selection on Cable**
- **Current:** Places OLT at nearest point on cable to pocket centroid
- **Problem:** Should place at point closest to **ONT centroid** (not pocket centroid)
- **Note:** Pocket centroid ≠ ONT centroid (pockets may be merged)

### **Issue 3: Multiple Cable Consideration**
- **Current:** Only considers nearest cable
- **Problem:** Should consider all nearby infrastructure cables and choose best

---

## ✅ Recommended Improvements

### **1. Update OLT Placement Algorithm**

```python
def place_olt_optimized(pocket, main_cables, ont_geojson):
    """
    Place OLT using actual design logic:
    1. Calculate ONT centroid (not pocket centroid)
    2. Find all infrastructure cables within reasonable distance
    3. For each cable, find point closest to ONT centroid
    4. Select cable + point that minimizes distance to centroid
    5. Place OLT at selected point
    """
    # Calculate ONT centroid
    ont_centroid = calculate_ont_centroid(pocket.onts)
    
    # Find all infrastructure cables within search radius (e.g., 5km)
    candidate_cables = find_cables_within_radius(ont_centroid, main_cables, radius_km=5.0)
    
    # For each candidate cable, find optimal point
    best_placement = None
    min_centroid_distance = float('inf')
    
    for cable in candidate_cables:
        # Find point on cable closest to ONT centroid
        point_on_cable, distance_to_cable = find_nearest_point_on_cable(
            ont_centroid, cable
        )
        
        # Calculate distance from point to ONT centroid
        distance_to_centroid = euclidean_distance(
            ont_centroid, point_on_cable
        )
        
        if distance_to_centroid < min_centroid_distance:
            min_centroid_distance = distance_to_centroid
            best_placement = {
                "position": point_on_cable,
                "cable": cable,
                "distance_to_centroid": distance_to_centroid,
                "distance_to_cable": distance_to_cable
            }
    
    return best_placement
```

### **2. Key Changes**

1. **Use ONT centroid** instead of pocket centroid
2. **Consider multiple cables** within search radius
3. **Optimize for centroid distance** while staying on infrastructure
4. **Validate all ONTs** within 25km after placement

---

## 📈 Expected Improvements

With optimized placement:
- ✅ **Distance to infrastructure:** 0.00 km (same as actual)
- ✅ **Distance to centroid:** ~3 km (vs current 10.44 km)
- ✅ **Overall placement accuracy:** ~3-5 km (vs current 10.44 km)

---

## 🔬 Validation

### **Test Cases**

1. **Large pockets** (POCKET_0001_MERGED, POCKET_0003_MERGED)
   - Current: 7-13 km from centroid
   - Expected: 2-4 km from centroid

2. **Small pockets** (POCKET_0005, POCKET_0009)
   - Current: 11-19 km from centroid
   - Expected: 1-3 km from centroid

3. **Medium pockets** (POCKET_0006_MERGED, POCKET_0021_MERGED)
   - Current: 6-17 km from centroid
   - Expected: 2-4 km from centroid

---

## 📝 Summary

**Actual Design Logic:**
- Place OLT on infrastructure cable at point closest to ONT centroid
- This balances infrastructure access with ONT service distance

**Current Implementation:**
- Places OLT on nearest infrastructure cable to pocket centroid
- Doesn't optimize for ONT centroid distance

**Recommendation:**
- Update Phase 1 to use ONT centroid and optimize placement on infrastructure cables
- This should reduce placement distance from ~10 km to ~3 km

---

**Status:** Analysis complete, ready for implementation improvements! ✅


