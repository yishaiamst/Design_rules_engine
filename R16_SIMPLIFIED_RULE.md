# R16 Simplified Rule: OLT Placement by ONT Pockets

## Simplified Approach

**Key Insight:** If there is a pocket of ONTs, those pockets need their own OLT.

---

## Simplified Rule Logic

### Rule 1: Large Communities (≥2000 subscribers)
- **Always place OLT** at community center
- No exceptions

### Rule 2: Medium Communities (500-2000 subscribers)
- **Always place OLT** at community center
- User can review and remove during optimization if needed
- Rationale: Since 2000+ always needs OLT anyway, this simplifies the logic

### Rule 3: Isolated Pockets (>15km from other communities)
- **Always place OLT** regardless of size
- If a pocket of ONTs is >15km from nearest other community, it can't connect anyway
- Requires its own OLT

### Rule 4: Small Communities (<500 subscribers, <15km from others)
- **Assign to nearest OLT** (within 20km)
- Can share with nearby communities

---

## Decision Tree (Simplified)

```
Step 1: Cluster ONTs into pockets (2km radius)

For each pocket:
│
├─ Pocket size ≥ 2000 ONTs?
│  └─ YES → Place OLT (Rule 1)
│
├─ Pocket size 500-2000 ONTs?
│  └─ YES → Place OLT (Rule 2 - user can review later)
│
├─ Pocket size < 500 ONTs?
│  │
│  ├─ Distance to nearest pocket > 15km?
│  │  └─ YES → Place OLT (Rule 3 - isolated)
│  │
│  └─ Distance to nearest pocket ≤ 15km?
│     └─ YES → Assign to nearest OLT (Rule 4)
```

---

## Why This Simplification Works

### 1. **Pocket-Based Thinking**
- Natural geographic boundaries
- If pockets are >15km apart, they're effectively isolated
- Each isolated pocket needs its own OLT

### 2. **500-2000 Always Gets OLT**
- Simpler logic: no complex distance calculations for medium communities
- User can optimize later (remove OLTs if too close together)
- Since 2000+ always needs OLT, this is consistent

### 3. **15km as Isolation Boundary**
- If two pockets are >15km apart, they can't really share infrastructure efficiently
- Natural boundary for "separate communities"
- Matches real-world geographic separation

### 4. **User Review Phase**
- Design engine generates initial design with OLTs
- User reviews and can:
  - Remove redundant OLTs (if two are too close)
  - Merge small pockets if desired
  - Optimize based on cost/coverage

---

## Implementation Logic

```python
def place_olts(ont_clusters):
    """
    Simplified OLT placement logic.
    
    Args:
        ont_clusters: List of ONT clusters (pockets)
    
    Returns:
        List of OLT placements
    """
    olts = []
    
    for cluster in ont_clusters:
        cluster_size = len(cluster.onts)
        nearest_cluster_distance = find_nearest_cluster_distance(cluster, ont_clusters)
        
        # Rule 1: Large communities (≥2000)
        if cluster_size >= 2000:
            olts.append(place_olt_at_centroid(cluster))
        
        # Rule 2: Medium communities (500-2000)
        elif cluster_size >= 500:
            olts.append(place_olt_at_centroid(cluster))
            # User can review and remove later if needed
        
        # Rule 3: Isolated small communities (>15km from others)
        elif nearest_cluster_distance > 15.0:  # km
            olts.append(place_olt_at_centroid(cluster))
        
        # Rule 4: Small communities close to others
        else:
            # Assign to nearest OLT (will be created for other clusters)
            assign_to_nearest_olt(cluster)
    
    return olts
```

---

## Example Scenarios

### Scenario 1: Large Community
```
Pocket A: 2500 ONTs
→ Place OLT (Rule 1: ≥2000)
```

### Scenario 2: Medium Community
```
Pocket B: 1200 ONTs
→ Place OLT (Rule 2: 500-2000)
→ User can review: if nearby pocket also has OLT, might merge
```

### Scenario 3: Isolated Small Community
```
Pocket C: 400 ONTs
Distance to nearest pocket: 18km
→ Place OLT (Rule 3: isolated >15km)
→ Can't connect to others anyway
```

### Scenario 4: Small Community Near Others
```
Pocket D: 300 ONTs
Distance to nearest pocket: 8km
→ Assign to nearest OLT (Rule 4: <15km)
→ Can share infrastructure
```

### Scenario 5: Multiple Medium Communities
```
Pocket E: 800 ONTs (distance to F: 12km)
Pocket F: 900 ONTs (distance to E: 12km)

→ Both get OLTs (Rule 2: 500-2000)
→ User review: Might keep both, or merge if too close
```

---

## Benefits of Simplified Approach

### 1. **Easier to Implement**
- Clear, simple rules
- No complex conditional logic
- Straightforward decision tree

### 2. **Easier to Understand**
- "Pockets need their own OLT"
- Natural geographic thinking
- Clear boundaries (15km isolation)

### 3. **User Control**
- Design engine generates initial design
- User reviews and optimizes
- Can remove redundant OLTs
- Can merge nearby communities

### 4. **Consistent Logic**
- 2000+ always gets OLT
- 500-2000 always gets OLT (consistent)
- Isolated pockets always get OLT
- Only small, non-isolated pockets share

### 5. **Real-World Alignment**
- Matches how networks are actually planned
- Geographic pockets = service areas
- Isolation = separate infrastructure

---

## Updated Rule Summary

| Pocket Size | Distance to Nearest Pocket | Decision |
|-------------|---------------------------|----------|
| **≥2000** | Any | **Place OLT** |
| **500-2000** | Any | **Place OLT** (user can review) |
| **<500** | **>15km** | **Place OLT** (isolated) |
| **<500** | **≤15km** | **Assign to nearest OLT** |

---

## Validation

After OLT placement, validate:
1. All ONTs are within 20km of their assigned OLT (R15)
2. No two OLTs are unnecessarily close (<5km) - flag for user review
3. All isolated pockets (>15km) have their own OLT

---

## User Review Phase

After initial design generation:
1. **Review OLT placements**
   - Check if any OLTs are too close (<5km)
   - Consider merging nearby communities
   - Remove redundant OLTs if desired

2. **Optimize based on:**
   - Cost (fewer OLTs = lower cost)
   - Coverage (all ONTs within 20km)
   - Future growth (communities that might expand)

3. **Finalize design**
   - Approve OLT placements
   - Proceed with FDH, FOSC, Terminal placement

---

This simplified approach is much cleaner and more practical!




