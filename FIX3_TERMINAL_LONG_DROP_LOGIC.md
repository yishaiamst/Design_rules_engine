# Fix 3: Terminal Long Drop Cable Logic

## Problem Statement
Terminals with long drop cables (like T0000356) should have MSTs placed closer to ONT clusters, connected to nearby FOSCs via stub cables, to reduce total drop cable length.

## Example Case
- **Terminal**: T0000356
- **Issue**: Very long drop cables to ONTs
- **Solution**: Place MST at optimal position (e.g., 45.745811, -82.318093)
- **Connection**: Connect to FOSC F0000178 via stub cable (~500m)
- **Benefit**: Significant reduction in drop cable length

## Logic Definition

### Step 1: Detect Terminals with Long Drop Cables
For each terminal:
1. Calculate drop cable lengths to all connected ONTs
2. Calculate statistics:
   - Average drop length
   - Maximum drop length
   - Total drop length
3. **Criteria for "long drop"**:
   - Average drop length > 100m **OR**
   - Maximum drop length > 150m

### Step 2: Evaluate ONT Clustering
For each terminal with long drops:
1. Calculate cluster centroid from ONT positions
2. Check if ONTs form a cluster:
   - ONTs within 200m of centroid
   - At least 3 ONTs in cluster
3. If not clustered, skip (ONTs too spread out)

### Step 3: Find Nearby Infrastructure
For each clustered terminal:
1. **Find nearby FOSC**:
   - Within 1km of cluster centroid
   - Required for stub cable connection
2. **Find nearby cables**:
   - Within 200m of cluster centroid
   - Required for MST placement (MST must be ON cable)

### Step 4: Calculate Optimal MST Position
1. Generate candidate positions:
   - Nearest point on each nearby cable
   - Midpoints of cable segments near cluster
2. For each candidate position:
   - Calculate total drop cable length from all ONTs in cluster
3. Select position that **minimizes total drop cable length**

### Step 5: Calculate Savings
1. **Old total drop length**: Sum of current drop cables from terminal to ONTs
2. **New total drop length**: Sum of drop cables from optimal MST position to ONTs
3. **Stub cable length**: Distance from MST to FOSC
4. **Savings**: `(old total drop) - (new total drop + stub cable)`
5. **Decision**: Only place MST if savings > 100m (significant improvement)

### Step 6: Place MST and Reassign ONTs
1. Create MST:
   - Position: Optimal position ON cable
   - Model: MST12 (12 ports)
   - Connected to: Nearest FOSC (for stub cable)
   - ON cable: Yes (required)
2. Split ONTs into groups (max 12 per MST if needed)
3. Reassign ONTs:
   - Remove ONTs from original terminal
   - Assign to new MST
4. Stub cable will be created in Phase 5

## Implementation Details

### Key Functions

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

### Thresholds
- **Long drop threshold**: avg > 100m OR max > 150m
- **Cluster radius**: 200m
- **FOSC max distance**: 1km
- **Cable max distance**: 200m
- **Minimum savings**: 100m
- **Minimum cluster size**: 3 ONTs

### MST Placement Rules
1. MST must be placed ON the fiber cable (required)
2. Position minimizes total drop cable length
3. Max 12 ONTs per MST
4. Connected to FOSC within 1km
5. Savings must justify stub cable cost (>100m)

## Results

From test run:
- **2,687 terminals** with long drop cables detected
- **48 candidates** for MST placement (after filtering)
- **48 new MSTs** added
- **407 drop cables** optimized

## Verification

To verify T0000356 is handled:
1. Check if terminal has avg drop > 100m OR max drop > 150m
2. Check if ONTs form cluster (within 200m)
3. Check if FOSC F0000178 is within 1km
4. Check if cable is within 200m of cluster
5. Verify savings calculation
6. Verify MST placement at optimal position

## Next Steps

1. **Verify specific cases**: Check T0000356 and other blue oval areas
2. **Tune thresholds**: Adjust if needed based on results
3. **Stub cable creation**: Ensure Phase 5 creates stub cables for new MSTs
4. **Visualization**: Verify MSTs are placed in correct locations
