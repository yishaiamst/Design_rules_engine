# Design Generation Engine - Detailed Implementation Plan

## Overview

Build `generate_design.py` - a Python module that takes input GeoJSON files (ONT locations and fiber cable routes) and automatically generates a complete fiber network design by applying all discovered rules (R10-R16).

---

## Input Files

### Required Inputs
1. **`ONT.geojson`** - Point features representing subscriber locations
   - Each feature has: `geometry` (Point), `properties` (id, coordinates, etc.)

2. **`fiber cable.geojson`** - LineString features representing the main fiber route
   - Each feature has: `geometry` (LineString), `properties` (id, from_id, to_id, calclength, etc.)

### Optional Inputs (for validation)
- Your existing output files (Terminal.geojson, FOSC.geojson, etc.) for comparison

---

## Output Files

The engine will generate all network layers matching your existing format:

1. **`Terminal.geojson`** - Aerial Terminals and MSTs
2. **`FOSC.geojson`** - Fiber Optic Splice Closures
3. **`FDH.geojson`** - Fiber Distribution Hubs
4. **`OLT.geojson`** - Optical Line Terminals
5. **`drop cable.geojson`** - Drop cables (ONT → Terminal)
6. **`stub cable.geojson`** - Stub cables (Terminal → FOSC)
7. **`fiber cable.geojson`** - Updated fiber cables with sizing
8. **`bom.json`** - Bill of Materials summary
9. **`design_validation.json`** - Validation report

---

## Step-by-Step Algorithm

### Phase 1: Data Loading & Preprocessing

```python
1. Load ONT.geojson
   - Extract all ONT points with coordinates
   - Build spatial index for fast proximity queries
   
2. Load fiber cable.geojson
   - Extract all fiber cable LineStrings
   - Calculate segment lengths
   - Build connectivity graph
   
3. Load design rules
   - cable_sizing_rules.json (for cable sizing decisions)
   - adaptive_rules_summary.json (for thresholds)
   - olt_placement_rules.json (for R15, R16)
```

### Phase 2: OLT Placement (R15, R16)

```python
1. Cluster ONTs by proximity (2 km radius)
   - Use spatial clustering algorithm
   - Count ONTs per cluster
   
2. For each cluster:
   - Calculate cluster centroid
   - Count subscribers
   - Calculate distance to nearest existing OLT (if any)
   
3. Apply R16 decision logic:
   IF cluster_size >= 2000:
       → Place OLT at cluster centroid
   ELIF cluster_size >= 500 AND distance_to_nearest_OLT > 15km:
       → Place OLT at cluster centroid
   ELIF cluster_size < 500 AND distance_to_nearest_OLT > 15km:
       → Place OLT at cluster centroid (isolated community)
   ELSE:
       → Assign cluster to nearest OLT (within 20km)
   
4. Validate R15:
   - Ensure all ONTs are within 20km of their assigned OLT
   - If violation, add additional OLTs or adjust placement
```

### Phase 3: FDH Placement (R13)

```python
1. For each OLT:
   - Group assigned ONTs by geographic proximity
   - Calculate how many FOSCs will be needed (based on R12)
   
2. Place FDHs:
   - One FDH per OLT initially
   - If ONT count > threshold, consider multiple FDHs
   - Place FDH near OLT or at strategic junction point
   
3. Assign FOSCs to FDHs:
   - Use fdh_id association logic
   - Pair nearest FOSCs to FDHs
```

### Phase 4: Fiber Cable Sizing & Segmentation

```python
1. For each fiber cable segment:
   - Count downstream ONTs (all ONTs reachable from this segment)
   - Apply cable sizing rules:
     * 288F: 10-868 ONTs (feeder)
     * 144F: 12-1019 ONTs (feeder)
     * 96F: 8-119 ONTs (distribution)
     * 48F: 4-250 ONTs (distribution)
     * 12F: 17-100 ONTs (access)
   
2. Determine cable transitions:
   - When ONT count drops below threshold → downsize cable
   - Place FOSC at transition points (R12)
   
3. Segment fiber cables:
   - Break into segments based on:
     * Length (≥1800m → place FOSC)
     * Cable ID changes
     * ONT count transitions
     * Junction points (≥2 cables)
```

### Phase 5: FOSC Placement (R12)

```python
1. Identify FOSC placement points:
   - Junction of ≥2 fiber cables
   - Segment length ≥1800m
   - Cable ID change point
   - Fiber count transition (e.g., 288F → 144F)
   
2. For each placement point:
   - Create FOSC feature
   - Assign unique ID (F*)
   - Link to FDH (R13)
   - Record cable connections
```

### Phase 6: Terminal Placement (R10, R11)

```python
1. For each ONT:
   - Find nearest fiber cable segment
   - Calculate distance to segment
   
2. Group ONTs by proximity to fiber segments:
   - ONTs within 150m of same segment → Aerial Terminal candidate
   - ONTs requiring stub cable → MST candidate
   
3. Apply R10 (Aerial Terminal):
   - Group: 1-35 ONTs, avg drop ≤260m, no stub
   - Place terminal on fiber cable segment
   - Create drop cables (ONT → Terminal)
   
4. Apply R11 (MST):
   - Group: 1-43 ONTs, stub ≤500m (or 500-2500m for long-reach)
   - Place terminal at end of stub cable
   - Create stub cable (Terminal → FOSC)
   - Create drop cables (ONT → Terminal)
   
5. Assign terminals to FOSCs:
   - Aerial terminals: connect to nearest FOSC via fiber cable
   - MSTs: connect via stub cable to FOSC
```

### Phase 7: Cable Generation

```python
1. Drop Cables (ONT → Terminal):
   - For each ONT-terminal pair
   - Calculate straight-line distance (or follow road if available)
   - Create LineString feature
   - Length: typically 90m median, 115m average
   
2. Stub Cables (Terminal → FOSC):
   - For each MST-terminal
   - Create LineString from terminal to FOSC
   - Length: typically 212m median, 308m average
   - Validate: ≤500m (standard) or ≤2500m (long-reach)
   
3. Fiber Cables:
   - Update existing fiber cables with:
     * Fiber count (288F, 144F, etc.)
     * Segment IDs
     * From_ID / To_ID connections
   - Create new segments if needed
```

### Phase 8: BOM Generation

```python
1. Calculate totals:
   - Total length per cable size (288F, 144F, 96F, 48F, 12F)
   - Count of each component:
     * OLTs
     * FDHs
     * FOSCs
     * Terminals (Aerial vs MST)
   - Total drop cable length
   - Total stub cable length
   
2. Generate bom.json:
   {
     "cables": {
       "288F": {"length_km": 100.5, "count": 458},
       "144F": {"length_km": 250.3, "count": 1726},
       ...
     },
     "components": {
       "olt": 5,
       "fdh": 5,
       "fosc": 860,
       "terminal": 4847,
       "terminal_aerial": 3958,
       "terminal_mst": 889
     },
     "total_cost_estimate": null  # Optional
   }
```

### Phase 9: Validation & Reporting

```python
1. Validate against rules:
   - R15: All ONT paths ≤20km to OLT
   - R10: Aerial terminals meet criteria
   - R11: MSTs meet stub length criteria
   - R12: FOSCs placed correctly
   - R13: FDH-FOSC associations valid
   - R14: Cable hierarchy maintained
   
2. Compare with actual design (if provided):
   - Component placement accuracy
   - Cable sizing accuracy
   - Distance accuracy
   
3. Generate validation report:
   {
     "rule_violations": [...],
     "accuracy_metrics": {...},
     "warnings": [...]
   }
```

---

## Implementation Structure

```python
generate_design.py
├── load_inputs()
│   ├── load_onts()
│   ├── load_fiber_cables()
│   └── load_rules()
│
├── place_olts()  # R15, R16
│   ├── cluster_onts()
│   ├── calculate_distances()
│   └── apply_placement_logic()
│
├── place_fdhs()  # R13
│   ├── group_by_olt()
│   └── assign_foscs()
│
├── size_cables()  # Cable sizing rules
│   ├── count_downstream_onts()
│   └── apply_sizing_rules()
│
├── place_foscs()  # R12
│   ├── identify_junctions()
│   ├── identify_long_segments()
│   └── identify_transitions()
│
├── place_terminals()  # R10, R11
│   ├── group_onts_by_proximity()
│   ├── apply_aerial_terminal_rule()
│   └── apply_mst_rule()
│
├── generate_cables()
│   ├── generate_drop_cables()
│   ├── generate_stub_cables()
│   └── update_fiber_cables()
│
├── generate_bom()
│   └── calculate_totals()
│
├── validate_design()
│   └── check_rules()
│
└── save_outputs()
    ├── save_geojson_layers()
    ├── save_bom()
    └── save_validation_report()
```

---

## Key Algorithms & Data Structures

### Spatial Indexing
- Use R-tree or KD-tree for fast proximity queries
- Libraries: `rtree`, `scipy.spatial`, or `shapely`

### Graph Representation
- Build connectivity graph for pathfinding
- Use NetworkX or custom adjacency dict
- Calculate downstream ONT counts via BFS/DFS

### Clustering
- DBSCAN or K-means for ONT clustering
- Or simple distance-based clustering (2km radius)

### Distance Calculations
- Haversine formula for geographic distances
- Point-to-line distance for ONT-to-cable distances
- Libraries: `geopy`, `shapely`

---

## Example Workflow

```
Input:
  - 2000 ONT points in a polygon area
  - 1 fiber cable route (LineString, 50km long)

Process:
  1. Cluster 2000 ONTs → 3 clusters:
     - Cluster 1: 800 ONTs (dense urban)
     - Cluster 2: 900 ONTs (suburban)
     - Cluster 3: 300 ONTs (rural, isolated)
  
  2. Place OLTs:
     - Cluster 1: 800 ONTs → No OLT (assign to nearest)
     - Cluster 2: 900 ONTs → No OLT (assign to nearest)
     - Cluster 3: 300 ONTs, 18km from others → Place OLT (isolated)
     - Overall: Need 1 OLT for cluster 3, assign others to it
  
  3. Place FDH:
     - 1 FDH near OLT
  
  4. Size fiber cables:
     - Start: 144F (serving 2000 ONTs)
     - After 20km: Downsize to 96F (serving 800 ONTs)
     - After 35km: Downsize to 48F (serving 300 ONTs)
  
  5. Place FOSCs:
     - At 20km mark (cable transition)
     - At 35km mark (cable transition)
     - Every 1800m along route (long segments)
     - At cable junctions
  
  6. Place Terminals:
     - Group ONTs near fiber segments
     - Create 150 Aerial Terminals (1-12 ONTs each)
     - Create 20 MSTs (6-24 ONTs each, with stub cables)
  
  7. Generate cables:
     - 2000 drop cables (ONT → Terminal)
     - 20 stub cables (Terminal → FOSC)
     - Updated fiber cables with sizing
  
  8. Generate BOM:
     - 1 OLT
     - 1 FDH
     - ~50 FOSCs
     - 170 Terminals
     - 50km of fiber cable (various sizes)
     - 2000 drop cables
     - 20 stub cables

Output:
  - All GeoJSON layers
  - BOM.json
  - Validation report
```

---

## Testing Strategy

### Phase 1: Unit Tests
- Test each function independently
- Use small synthetic datasets

### Phase 2: Integration Tests
- Test with your existing input files
- Compare generated vs actual outputs
- Calculate accuracy metrics

### Phase 3: Validation
- Check rule compliance
- Verify BOM accuracy
- Test edge cases (isolated communities, long routes, etc.)

---

## Dependencies

```python
import json
import math
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Optional

# Spatial operations
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import nearest_points
import rtree  # For spatial indexing

# Or alternatives:
# from scipy.spatial import KDTree
# from geopy.distance import geodesic
```

---

## Success Criteria

1. ✅ Generates all required GeoJSON layers
2. ✅ All rules (R10-R16) are applied correctly
3. ✅ BOM is accurate and complete
4. ✅ Validation report shows <5% rule violations
5. ✅ Generated design matches actual design with >80% accuracy (if comparing)

---

## Next Steps After Implementation

1. **Test with your existing data**
   - Run on your ONT.geojson and fiber cable.geojson
   - Compare outputs with your actual design files
   - Calculate accuracy metrics

2. **Refine rules based on differences**
   - Identify systematic errors
   - Adjust thresholds if needed
   - Update rules

3. **Build map interface** (after validation)
   - MapLibre GL JS
   - Drawing tools
   - Export to GeoJSON
   - Connect to design engine

---

## Questions to Consider

1. **Coordinate System:** What CRS are your GeoJSON files in? (WGS84, UTM, etc.)
2. **Cable Routing:** Should drop/stub cables follow roads, or straight-line?
3. **Terminal Capacity:** Maximum ONTs per terminal? (Current rules suggest 1-35)
4. **FOSC Capacity:** Maximum terminals per FOSC? (Current data shows ~22 average)
5. **Validation Tolerance:** What accuracy threshold is acceptable?

---

This is the detailed plan. Should I start implementing `generate_design.py` now?




