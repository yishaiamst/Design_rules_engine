# Fix 3: Cluster-Based MST Placement (Enhanced)

## Problem
The previous Fix 3 only detected long drop cables (>150m) and placed MSTs reactively. This missed dense ONT clusters that could benefit from local MSTs even if individual drop cables weren't extremely long.

## Solution
**Proactive cluster detection and optimal MST placement:**

1. **Cluster Detection**: Cluster ALL ONTs by proximity (200m radius)
2. **Cluster Analysis**: For each cluster, determine if MST(s) are needed:
   - Check if cluster already has nearby terminal with acceptable drop lengths (<100m average)
   - Calculate number of MSTs needed: `ceil(ont_count / 12)`
3. **Optimal Placement**: For each MST group:
   - Generate candidate positions on nearby cables (within 200m)
   - Find position that **minimizes total drop cable length** from all ONTs in group
   - Place MST ON the fiber cable at optimal position
4. **FOSC Connection**: Connect MST to nearest FOSC (within 1km) via stub cable
5. **ONT Reassignment**: Remove ONTs from existing terminals when new MST is created

## Key Features

### 1. Proactive Clustering
- Detects all ONT clusters (3+ ONTs within 200m)
- Not limited to long drop cables
- Identifies dense areas that need local MSTs

### 2. Optimal Position Selection
- Evaluates multiple candidate positions on cables
- Selects position that minimizes **total drop cable length**
- Ensures shortest possible drop cables from all ONTs

### 3. Capacity Management
- Splits large clusters into multiple MSTs (max 12 ONTs each)
- Each MST placed optimally for its ONT group
- Prevents terminal overload

### 4. Integration
- MSTs placed ON fiber cable (required)
- Connected to FOSC via stub cable (created in Phase 5)
- ONTs removed from original terminals when reassigned

## Results

From test run:
- **2,477 ONT clusters** detected (3+ ONTs)
- **1,462 clusters** identified as needing MST(s)
- **894 new MSTs** added
- **6,028 drop cables** optimized

## Implementation Details

### Cluster Detection Algorithm
```python
# 1. Cluster ONTs by proximity (200m radius)
# 2. For each cluster:
#    - Check if existing terminal serves cluster well (avg drop < 100m)
#    - If not, calculate num_msts = ceil(ont_count / 12)
#    - Split cluster into groups of 12 ONTs
#    - For each group:
#      * Find nearby cables (within 200m)
#      * Generate candidate positions on cables
#      * Select position minimizing total drop cable length
#      * Place MST ON cable
#      * Connect to nearest FOSC
```

### Position Optimization
```python
def find_optimal_mst_position(ont_positions, candidate_positions):
    """Find position that minimizes total drop cable length."""
    best_pos = None
    min_total_length = float('inf')
    
    for candidate_pos in candidate_positions:
        total_length = sum(
            euclidean_distance(candidate_pos, ont_pos)
            for ont_pos in ont_positions
        )
        if total_length < min_total_length:
            min_total_length = total_length
            best_pos = candidate_pos
    
    return best_pos, min_total_length
```

## Next Steps

1. **Stub Cable Creation**: Phase 5 will automatically create stub cables for MSTs with `connected_fosc_id`
2. **Visualization**: Verify MSTs are placed in blue oval areas from user's image
3. **Drop Cable Optimization**: Verify drop cable lengths are minimized

## Files Modified

- `phases/phase3b_refine_mst_placement.py`: Complete rewrite of Fix 3
  - Proactive cluster detection
  - Optimal position selection
  - ONT reassignment from existing terminals
