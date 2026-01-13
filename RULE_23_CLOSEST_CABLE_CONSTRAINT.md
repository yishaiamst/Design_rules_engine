# Rule 23: Closest Cable Constraint

## Problem

The algorithm was creating paths that were not acceptable. For example, `96FOC/UNKNOWN/T0000005` was being connected in a way that created an unacceptable path.

## Solution

Added **closest cable constraint** as the primary selection criteria:

1. **Avoid loops** (reject if creates loop/square)
2. **Connect to closest cable** (distance is primary constraint)
3. Minimize path from OLT (secondary)
4. Minimize FOSCs/terminals crossed (tertiary)

## Selection Priority

```
1. Non-loop connections (avoid squares)
2. Closest distance (primary constraint)
3. Shorter path from OLT
4. Fewer FOSCs/terminals crossed
```

## Code Changes

In `phases/phase3e_connect_isolated_cables.py`, the sorting key was updated:

```python
candidates_to_use.sort(key=lambda x: (
    0 if x in non_loop_candidates else 1,  # Non-loops first (avoid squares)
    x["distance"],  # Closest first (primary constraint)
    x["metrics"]["path_length_m"] if x["metrics"]["path_length_m"] != float('inf') else 999999,
    x["metrics"]["total_crossings"]
))
```

## Folder Organization

### Input Files
- **Location**: `test_inputs/small_area/`
- **Purpose**: Original, unprocessed input GeoJSON files
- **Files**:
  - `ONT.geojson` - Original ONT points
  - `fiber cable.geojson` - Original fiber cable infrastructure

### Output Files
- **Location**: `test_output/small_area_design_fresh/`
- **Purpose**: Generated design results
- **Files**: All generated layers and summaries

### Key Principle
- **Inputs** should be kept in `test_inputs/` folder (reference)
- **Outputs** should be saved to `test_output/` folder
- **Never modify** input files - always use fresh inputs for testing

## Testing

To test with fresh input data:

```python
from phases.phase3e_connect_isolated_cables import connect_isolated_cables
import json

# Load FRESH input data
cables = json.load(open('test_inputs/small_area/fiber cable.geojson'))
foscs = []

# Run connection
updated, new_foscs, summary = connect_isolated_cables(
    cables, foscs, 50.0, 3000.0, max_iterations=5,
    terminals=[], olts=[]
)
```

## Results

With fresh input data:
- Found 1 isolated cable: `48FOC/F1000509/T1002415`
- Selected closest cable: `144FOC/F1000392/F1000390` (2362.8m)
- Successfully connected without creating loops
- Network fully connected in 2 passes
