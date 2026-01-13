# Rule 23 Enhancement: Loop Avoidance and Path-Based Selection

## Problem

When connecting isolated cables, the algorithm was creating loops/squares in the network. For example:
- `48FOC/T0000005/UNKNOWN` was connected to `F1000397`
- This created a loop with `144FOC/T0000003/T0000020` and `96FOC/UNKNOWN/T0000005`
- The user wants to connect to `144FOC/T0000003/T0000020` instead, with FOSCs at each side

## Solution

Enhanced Rule 23 with:
1. **Loop Detection**: Detects if a connection would create a closed path/loop
2. **Path-Based Selection**: Evaluates all connection options based on:
   - Distance from OLT (minimize path length)
   - Number of FOSCs/terminals crossed (minimize crossings)
   - Avoid loops (reject connections that create loops)
3. **Comprehensive Candidate Evaluation**: Considers both FOSCs and cables, evaluates all options together

## Algorithm Flow

```
1. Find all connection candidates:
   a. FOSCs from FOSC list
   b. FOSCs extracted from cable IDs
   c. Cables (filtered by size: target >= isolated)

2. For each candidate:
   a. Check if it would create a loop
   b. Calculate path metrics from OLT
   c. Count FOSCs/terminals crossed

3. Filter out candidates that create loops

4. Sort candidates by:
   - Path length from OLT (ascending)
   - Total crossings (FOSCs + terminals) (ascending)
   - Distance (ascending)

5. Select best candidate

6. Connect isolated cable to selected candidate
```

## Loop Detection

A loop is detected if:
- The isolated cable and target cable share an endpoint
- There's an existing path from the other endpoint of isolated cable
- To the other endpoint of target cable through existing cables

This prevents creating closed polygons/squares in the network.

## Path Metrics

For each candidate connection:
- **Distance from OLT**: Straight-line distance from nearest OLT to connection point
- **FOSC Count**: Number of FOSCs within 50m of connection point
- **Terminal Count**: Number of terminals within 50m of connection point
- **Total Crossings**: FOSC count + Terminal count

## Selection Criteria

**Priority Order**:
1. **Avoid loops** (reject if creates loop)
2. **Minimize path from OLT** (shorter is better)
3. **Minimize crossings** (fewer FOSCs/terminals is better)
4. **Minimize distance** (closer is better)

## Example

**Isolated cable**: `48FOC/T0000005/UNKNOWN` (48 fibers)

**Candidates**:
1. `F1000397` (FOSC from cable ID) - 2044m, path: 15km, crossings: 2
2. `144FOC/T0000003/T0000020` (cable) - 2036m, path: 12km, crossings: 1, **no loop** ✓
3. `96FOC/UNKNOWN/T0000005` (cable) - 0m, path: 18km, crossings: 3, **creates loop** ✗

**Selected**: `144FOC/T0000003/T0000020` (best path metrics, no loop)

## Integration

The enhanced algorithm is integrated into:
- `phases/phase3e_connect_isolated_cables.py`
- Called from `generate_design.py` as Phase 3e
- Receives OLTs and terminals for path analysis

## Notes

- **Loop detection is conservative**: If uncertain, prefers non-loop connections
- **Path metrics are estimates**: Uses straight-line distance from OLT (simplified)
- **Size constraint still applies**: Only considers cables with size >= isolated cable
- **FOSCs have no size constraint**: Can handle any cable size
