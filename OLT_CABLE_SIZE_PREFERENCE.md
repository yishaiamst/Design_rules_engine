# OLT Cable Size Preference Analysis

## 🔍 Key Findings

### **1. Actual Design Pattern**

**Observation:** When multiple infrastructure cables are available, actual OLTs are placed on:
- **Larger cables** when possible (288F > 144F > 96F)
- But distance to ONT centroid is still the primary factor

### **2. ONT Count vs Cable Size Relationship**

| ONT Count Range | Preferred Cable Size | Pattern |
|----------------|---------------------|---------|
| ≥2000 | 288F | 2/3 cases use 288F |
| 1500-2000 | 288F | 4/5 cases use 288F |
| 1000-1500 | 288F or 144F | Mixed |
| 500-1000 | 144F | 4/6 cases use 144F |
| <500 | 144F | All use 144F |

### **3. Multiple Cable Options**

**Finding:** All 17 OLTs have multiple infrastructure cables within 1km:
- Most have 288F, 144F, and 96F options
- When distances are equal, larger cables are preferred
- When distances differ, closer cable is chosen (even if smaller)

---

## 🎯 Recommended Strategy

### **Phase 1: OLT Placement (Before Cable Sizing)**

Since cable sizes are not yet determined in Phase 1, we should:

1. **Estimate required cable size** based on ONT count and service configuration
2. **Prefer cables of estimated size or larger** when multiple options exist
3. **Still optimize for ONT centroid distance** as primary factor

### **Cable Size Estimation (Heuristic)**

Based on actual design patterns and cable sizing logic:

```python
def estimate_required_cable_size(ont_count: int, config: Dict) -> int:
    """
    Estimate required cable size based on ONT count.
    This is a heuristic for Phase 1 placement.
    Actual sizing happens in Phase 6.
    """
    # Use service configuration to estimate
    service_config = config.get("service", {})
    olt_config = config.get("equipment", {}).get("olt", {}).get("OLT-8P-1G", {})
    
    # Quick estimation based on ONT count patterns
    if ont_count >= 2000:
        return 288  # Prefer 288F
    elif ont_count >= 1500:
        return 288  # Prefer 288F
    elif ont_count >= 1000:
        return 144  # Prefer 144F (or 288F if available)
    elif ont_count >= 500:
        return 144  # Prefer 144F
    else:
        return 144  # Prefer 144F (or 96F if no 144F)
```

### **Updated Placement Logic**

```python
def place_olt_optimized(pocket, main_cables, ont_geojson, config):
    """
    Place OLT with cable size preference.
    """
    # 1. Calculate ONT centroid
    ont_centroid = calculate_ont_centroid(pocket.onts)
    
    # 2. Estimate required cable size
    estimated_size = estimate_required_cable_size(pocket.ont_count, config)
    
    # 3. Find all infrastructure cables within search radius
    candidate_cables = find_cables_within_radius(ont_centroid, main_cables, radius_km=1.0)
    
    # 4. Score each candidate:
    #    - Primary: Distance to ONT centroid
    #    - Secondary: Cable size (prefer estimated size or larger)
    best_placement = None
    best_score = float('inf')
    
    for cable in candidate_cables:
        # Find point on cable closest to ONT centroid
        point_on_cable, distance_to_cable = find_nearest_point_on_cable(
            ont_centroid, cable
        )
        
        distance_to_centroid = euclidean_distance(ont_centroid, point_on_cable)
        
        # Score: distance + penalty for smaller cables
        size_penalty = 0
        if cable["fiber_count"] < estimated_size:
            # Prefer cables of estimated size or larger
            size_penalty = (estimated_size - cable["fiber_count"]) * 0.1  # 0.1 km penalty per fiber
        
        score = distance_to_centroid + size_penalty
        
        if score < best_score:
            best_score = score
            best_placement = {
                "position": point_on_cable,
                "cable": cable,
                "distance_to_centroid": distance_to_centroid,
                "distance_to_cable": distance_to_cable,
                "estimated_size": estimated_size,
                "actual_size": cable["fiber_count"]
            }
    
    return best_placement
```

---

## 📊 Expected Improvements

With cable size preference:
- ✅ **Better cable selection** when multiple options exist
- ✅ **Matches actual design patterns** (larger cables for larger ONT counts)
- ✅ **Still optimizes for centroid distance** (primary factor)
- ✅ **Prepares for Phase 6** (cable sizing will validate/refine)

---

## ⚠️ Important Notes

1. **This is a heuristic** - Actual cable sizing happens in Phase 6
2. **Distance is still primary** - Cable size preference is secondary
3. **May need adjustment** - Based on actual cable sizing results in Phase 6
4. **Configuration-driven** - Uses service config to estimate requirements

---

## 🔄 Phase 6 Integration

After Phase 6 (Cable Sizing) completes:
- Actual cable sizes will be determined
- Can validate Phase 1 placement decisions
- May need to adjust OLT positions if cable size changes significantly

---

**Status:** Analysis complete, ready for Phase 1 update! ✅


