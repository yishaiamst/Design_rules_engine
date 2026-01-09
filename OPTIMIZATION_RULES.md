# Optimization Rules for FOSC and MST Placement

All rules use **UTM Zone 17N (EPSG:32617)** coordinates - NO transformation during calculations.

## Critical Cable Routing Rule

**Rule 11: Stub Cables Must Run on Fiber Cable Infrastructure**

- **Stub cables** (MST → FOSC) MUST run along fiber cable infrastructure
- **Drop cables** (ONT → Terminal/MST) are **direct connections** and do NOT route along fiber cables

**CRITICAL VALIDATION RULE**:
- Stub cables that cannot route along fiber cables are **INVALID** and must be flagged
- Invalid stub cables are marked with `valid: false` and displayed in red
- Direct connections over empty space (only 2 path points) are NOT allowed
- Stub cables must have >2 path points following fiber cable infrastructure

**Implementation**: 
- Stub cables are routed using `route_stub_cable_along_fiber()` which finds the path along fiber cables between MST and FOSC positions.
- The function searches for paths through:
  1. Same cable (if both MST and FOSC are on the same cable)
  2. Cable junctions (cables sharing endpoints)
  3. Intermediate cables (cables connecting terminal cable to FOSC cable)
  4. FOSC positions as junction points
- If no path can be found along fiber, the stub cable is marked as invalid
- Drop cables are direct straight-line connections from ONT to Terminal/MST.

**Rationale**: 
- Stub cables connect MSTs to FOSCs and must follow the fiber infrastructure for proper deployment.
- Direct connections over empty space violate deployment rules and are physically impossible.
- Invalid stub cables indicate design issues that need correction (e.g., missing cable segments, incorrect FOSC placement).
- Drop cables connect ONTs to terminals and can be direct connections (off-cable) as they are typically aerial or buried drops to customer premises.

---

## Rule 1: Merge Nearby FOSCs

**Purpose**: Consolidate FOSCs that are close together and serve the same cables.

**Criteria**:
- FOSCs within 100m of each other
- Serve the same or overlapping cables
- OR are very close (<50m) regardless of cables

**Action**:
- Keep the FOSC with more connected cables
- Merge all cables from removed FOSCs into kept FOSC
- Update position to weighted average of merged FOSCs

**Example**: F0000015 (11.9m from F0000171) → Merged into F0000171

---

## Rule 2: Consolidate Nearby Terminals

**Purpose**: Reduce equipment cost by consolidating terminals (MSTs and Aerial Terminals) within 250m.

**Rationale**: Drop cables are inexpensive compared to terminal equipment and installation.

**Criteria**:
- Terminals (MSTs or Aerial Terminals) within 250m of each other
- **Merging must not exceed 12 ONTs per terminal** (port limit)

**Action**:
- Prefer MST over Aerial Terminal (if mixed types)
- Keep terminal with more ONTs
- **Check if combined ONT count ≤ 12 before merging**
- Merge all ONTs from removed terminals into kept terminal
- If keeping Aerial Terminal but removing MST, convert to MST
- Remove redundant terminals
- Skip merge if it would exceed 12 ONTs

**Result**: Consolidates nearby terminals while respecting the 12 ONT port limit.

**Example**: 
- T0004292 and T0004473 within 250m → Merged into T0004473 (if combined ONTs ≤ 12)

---

## Rule 3: Remove Redundant FOSCs

**Purpose**: Remove FOSCs that don't serve a purpose.

**Criteria** (FOSC is redundant if):
- Very close to terminal(s) (<50m) - terminal can serve directly
- On single fiber cable (not at junction)

**Exception**: Keep FOSCs at cable junctions (2+ cables) - they're needed for network connectivity.

**Action**: Remove redundant FOSCs, keep junction FOSCs.

---

## Rule 4: Convert Aerial Terminals to MSTs Near FOSCs

**Purpose**: Use MSTs when near FOSCs (<1km) - cheaper than Aerial Terminal + splicing.

**Criteria**:
- Aerial Terminal within 1km of FOSC
- OR existing MST without FOSC connection within 1km of FOSC

**Action**:
- Convert Aerial Terminal → MST
- Connect MST to nearest FOSC via stub cable
- Record stub cable length

**Rationale**: MST with stub cable is less expensive than Aerial Terminal requiring splicing work.

---

## Rule 5: Filter Distant ONTs

**Purpose**: Leave ONTs >1km from terminals unconnected for later deployment.

**Criteria**:
- ONT distance from terminal > 1000m

**Action**:
- Remove ONT from terminal's connected_onts list
- Record in terminal["removed_distant_onts"]

**Rationale**: Very long drop cables (>1km) may require special deployment and should be handled separately.

---

## Rule 6: Fix ONT-to-FOSC Connections

**Purpose**: Ensure ONTs are never directly connected to FOSCs.

**Rule**: ONTs must connect to terminals (MST or Aerial Terminal), not FOSCs.

**Action**:
- Detect ONTs that are near FOSCs (<100m) but not connected to any terminal
- Find nearest terminal for each such ONT
- Connect ONT to terminal instead

**Rationale**: Network topology is OLT → Cable → FOSC → Terminal → ONT. ONTs cannot bypass terminals.

---

## Rule 7: Place FOSCs at Cable Junctions

**Purpose**: Ensure FOSCs exist at cable junctions where multiple cables meet.

**Detection Method**:
- Parse cable IDs: `"SIZEFOC/ID1/ID2"`
- Find common segment IDs (e.g., `F1000397` appears in multiple cables)
- Junction exists where 2+ cables share a segment ID

**Action**:
- Detect junctions by analyzing cable ID patterns
- Check if FOSC already exists nearby (<50m)
- If not, create new FOSC at junction point
- Connect all junction cables to the FOSC

**Example**: 
- Cables: `96FOC/F1000391/F1000397`, `48FOC/F1000397/F1000398`, `12FOC/F1000397/T1001719`
- Common segment: `F1000397` → Create FOSC at this junction

---

## Rule 8: Fix Isolated Terminals

**Purpose**: Remove terminals that are not on cables and not connected to FOSCs.

**Criteria**:
- Terminal is not on any cable (<50m)
- Terminal is not connected to any FOSC (<1km)

**Action**:
- Move all ONTs from isolated terminal to nearest properly connected terminal
- Remove isolated terminal

**Example**: T0004298 was isolated → ONTs moved to T0004707 (269.5m away)

---

## Rule 9: Convert Terminals to FOSCs (Long Non-Straight Cables)

**Purpose**: Convert terminals to FOSCs when they're on long, curved cables.

**Criteria**:
- Terminal is on a cable
- Cable length > 500m
- Cable curvature ratio > 1.2 (total length / straight distance)

**Action**:
- Convert terminal to FOSC
- Preserve position and cable connection

**Example**: T0004300 on cable 48FOC/F1000397/F1000398 (1522m, curvature 1.29) → Converted to FOSC F0004300

---

## Rule 10: Fix Incorrect Terminal Connections

**Purpose**: Remove incorrect direct connections between terminals.

**Criteria**:
- Terminals are very close (<100m)
- Terminals have incorrect connection metadata

**Action**:
- Remove incorrect connection references
- Let Rule 2 (consolidation) handle proper merging

---

## Rule 12: Split Overloaded Terminals at Cable Endpoints

**Purpose**: Split terminals with >12 ONTs by placing MSTs at unconnected cable endpoints.

**Criteria**:
- Terminal has more than 12 ONTs
- Find cable endpoints not connected to FOSCs, terminals, or other cables
- Place new MSTs at those endpoints (within 1km of overloaded terminal)

**Action**:
- Create new MST at unconnected cable endpoint
- Redistribute ONTs (up to 12 per MST)
- Reduce load on original terminal

**Example**: T0004627 had 14 ONTs → Created MST T0000032 at endpoint of 48FOC/F1000406/F1000394 with 12 ONTs, leaving T0004627 with 2 ONTs

---

## Rule 13: Place MST Near FOSC for Specific ONTs

**Purpose**: Place an MST near a specific FOSC to connect a list of ONTs.

**Use Case**: When a FOSC needs to serve specific ONTs that aren't currently connected to terminals, place an MST near the FOSC.

**Action**:
- Calculate centroid of specified ONTs
- Find nearest cable to centroid
- Place MST on cable (or at centroid if no cable nearby)
- Ensure MST is within max_distance_from_fosc (default 500m)
- Connect all specified ONTs to the new MST
- Connect MST to FOSC via stub cable
- Remove ONTs from any existing terminal connections

**Example**: F0000962 → Created MST T0000033 with 10 ONTs (O1007640, O1007649, etc.), stub cable 165.1m

---

## Rule 14: Enforce MST Placement Rules

**Purpose**: Ensure ALL MSTs follow placement requirements - must be on fiber cables and connected to FOSCs.

**Critical Requirements**:
1. **ALL MSTs MUST be placed ON fiber cables** (within 50m, snapped to cable if needed)
2. **ALL MSTs MUST be connected to FOSCs** via stub cables (find nearest FOSC if not connected)

**Action**:
- For each MST:
  1. Find nearest fiber cable
  2. Snap MST position to nearest point on cable (even if far from original position)
  3. Set `connected_cable_id` to nearest cable
  4. Find nearest FOSC
  5. Connect MST to nearest FOSC (even if beyond normal 1000m range)
  6. Set `connected_fosc_id` and `stub_cable_length`

**Rationale**: MSTs are network infrastructure components that must be properly placed on the fiber network and connected to FOSCs for proper network topology.

**Example**: 
- T0004266: Was isolated → Snapped to cable 48FOC/F1000406/F1000394, connected to FOSC F1000397 (2327.7m)
- T0004476: Was on cable but not connected → Connected to FOSC F0000961 (409.7m)

---

## Rule 15: Convert FOSCs to MSTs for ONT Connections

**Purpose**: Convert FOSCs to MSTs when they should serve ONTs directly.

**Use Case**: Some FOSCs should actually be MSTs that connect ONTs. This handles specific cases where a FOSC needs to be converted to an MST.

**Action**:
- For each specified FOSC:
  1. Remove FOSC from FOSC list
  2. Create new MST at FOSC position (convert F0004456 → T0004456)
  3. Snap MST to nearest fiber cable (MSTs must be on cables)
  4. Connect specified ONTs to the new MST
  5. Find nearest FOSC for the new MST to connect to (MSTs must connect to FOSCs)
  6. Set `connected_fosc_id` and `stub_cable_length`

**Rationale**: Some locations that were initially placed as FOSCs should actually be MSTs that serve ONTs directly, while still connecting to a FOSC for network connectivity.

**Example**: 
- F0004456 → Converted to MST T0004456
  - Connected ONTs: O1007875, O1007873
  - Connected to FOSC: F1000397 (stub: 74.4m)
  - On cable: 48FOC/F1000397/F1000398

---

## Rule 16: All Terminals and FOSCs Must Be On Fiber Cables

**Purpose**: Ensure ALL terminals (MST and Aerial) and FOSCs are placed ON fiber cables.

**Critical Requirement**: 
- **ALL MSTs** must be on fiber cables
- **ALL Aerial Terminals** must be on fiber cables  
- **ALL FOSCs** must be on fiber cables

**Action**:
- For each terminal (MST or Aerial):
  1. Find nearest fiber cable
  2. Snap terminal position to nearest point on cable (regardless of distance)
  3. Set `connected_cable_id` and `distance_to_cable_m = 0.0`
  
- For each FOSC:
  1. Find nearest fiber cable
  2. Snap FOSC position to nearest point on cable (regardless of distance)
  3. Update `connected_cables` list

**Rationale**: All network infrastructure (terminals and FOSCs) must be physically placed on the fiber cable infrastructure. This prevents isolated islands and ensures proper network connectivity.

**Example**: 
- T0004284: Was 715.4m from cable → Snapped to cable 144FOC/F1000396/F1000399 (now on cable)
- All terminals and FOSCs are now guaranteed to be on cables

---

## Rule 17: Optimize ONT-to-Terminal Connections

**Purpose**: Connect each ONT to the nearest terminal with available capacity (≤12 ONTs).

**Criteria**:
- For each ONT, find the nearest terminal that has capacity (current ONTs < 12)
- If ONT is connected to a distant terminal but a closer terminal with capacity exists, reconnect it
- Only reconnect if the new terminal is closer AND has capacity

**Action**:
- For each ONT:
  1. Find all terminals with capacity (< 12 ONTs)
  2. Calculate distance to each terminal
  3. Find nearest terminal with capacity
  4. If nearest terminal is closer than current terminal, reconnect ONT
  5. Update both terminals' `connected_onts` lists

**Rationale**: Minimizes drop cable lengths by connecting ONTs to the nearest available terminal, reducing deployment costs while respecting terminal capacity limits.

**Example**: 
- O1007861: Was connected to T0004627 (1284.6m) → Reconnected to T0004266 (961.2m, saved 323.5m)
- O1007672: Was connected to T0004627 (859.0m) → Reconnected to T0004266 (216.5m, saved 642.5m)

---

## Rule 21: Optimize Stub Cable Connections

**Purpose**: After all calculations, find shorter paths for stub cables, preferring FOSCs over Aerial Terminals.

**Criteria**:
- For each MST, check if there's a shorter path to a FOSC or Aerial Terminal
- Priority: FOSC first, unless Aerial Terminal is < 0.5x FOSC distance
- Only switch if new connection is shorter AND can route along fiber

**Action**:
- For each MST:
  1. Find all FOSCs and Aerial Terminals that can be reached via fiber routing
  2. Calculate stub cable lengths for each option
  3. Select best option:
     - Prefer FOSC if available
     - Use Aerial Terminal only if its distance is < 0.5x FOSC distance
  4. Update MST connection if better option found
  5. Record new stub cable length

**Rationale**: This optimization runs after all other rules to find the most efficient stub cable connections. FOSCs are preferred for network topology, but Aerial Terminals can be used if they're significantly closer (less than half the FOSC distance).

**Example**: 
- MST finds FOSC at 1000m and Aerial Terminal at 400m
- Since 400m < 0.5 * 1000m, switch to Aerial Terminal
- Saves 600m of stub cable length

---

## Post-Processing: Merge Very Close FOSCs

**Purpose**: Prevent duplicate FOSCs created by different rules at the same location.

**Problem**: 
- Rule 7 places FOSCs at cable junctions
- Rule 9 converts terminals to FOSCs on long curved cables
- If a terminal is at a junction, both rules can create FOSCs at the same location

**Criteria**:
- FOSCs within 1.0m of each other
- Applied after all optimization rules

**Action**:
- For each pair of FOSCs within 1m:
  1. Priority: Keep junction FOSC (Rule 7) if present
  2. Otherwise: Keep FOSC with more connected cables
  3. Merge connected cables from removed FOSC into kept FOSC
  4. Remove duplicate FOSC

**Rationale**: Prevents duplicate FOSCs at the same location, ensuring clean network topology.

**Example**: 
- F0000962 (junction FOSC) and F0004300 (converted from T0004300) at 0.51m apart
- F0004300 is removed, F0000962 is kept with merged cables

---

## Rule 22: Update Cable IDs Based on FOSC and Terminal Positions

**Purpose**: Review and fix fiber cable IDs based on actual FOSC and terminal positions at cable endpoints.

**Format**: `<size>FOC/From/To`
- Example: `144FOC/T123456/F67890`
- Example: `48FOC/F0000157/F0000171`

**Critical Rule**: **Fiber cables MUST connect to FOSCs, not MSTs**
- If both FOSC and MST are at the same location, prefer FOSC
- MSTs are connected to FOSCs via stub cables, not directly via fiber cables
- Only Aerial Terminals can be endpoints of fiber cables (not MSTs)

**Criteria**:
- For each cable, find FOSCs and terminals at start and end points (within 50m tolerance)
- Extract fiber size from current cable ID or properties
- Build new cable ID: `<size>FOC/<from_id>/<to_id>`
- Where `from_id` and `to_id` are:
  - **FOSC IDs (F...)** - preferred if FOSC is at endpoint
  - **Aerial Terminal IDs (T...)** - only if no FOSC is found (Aerial Terminals can be cable endpoints)
  - **MST IDs are NOT used** - MSTs connect via stub cables, not directly to fiber cables
  - UNKNOWN if no element found at endpoint

**Action**:
- For each cable:
  1. Get start and end point coordinates
  2. Find nearest FOSC or Aerial Terminal at each endpoint (within 50m)
  3. **Prefer FOSC over Terminal** if both are at same location
  4. **Skip MSTs** - they don't connect directly to fiber cables
  5. Extract fiber size from current cable ID
  6. Build new cable ID: `<size>FOC/<from_id>/<to_id>`
  7. Update cable properties with new ID and endpoint information

**Rationale**: Cable IDs should accurately reflect the network topology. Fiber cables connect infrastructure (FOSCs, Aerial Terminals), while MSTs connect via stub cables. After FOSCs and terminals are placed and optimized, cable IDs should be updated to match the actual connections at cable endpoints.

**Example**: 
- Cable `144FOC/F1000391/F1000392` has:
  - Start point near F0000157 (FOSC, 9.0m)
  - End point near F0000171 (FOSC, 2.4m)
- Updated to: `144FOC/F0000157/F0000171`
- Cable `48FOC/T0004300/UNKNOWN` where T0004300 is an MST:
  - Should be updated to `48FOC/F0000962/UNKNOWN` (F0000962 is the FOSC T0004300 connects to)

---

## Visualization Offset Rules

**Purpose**: Maintain logical connections when applying visual offsets for clarity.

**Rule 1: Fiber Cables Always Connect to FOSCs**
- Fiber cables connect to FOSCs or Aerial Terminals (not MSTs)
- When updating cable IDs, prefer FOSCs over MSTs at the same location
- MSTs connect to FOSCs via stub cables, not directly via fiber cables
- **Implementation**: `find_nearest_element_at_point()` skips MSTs and prefers FOSCs

**Rule 2: Stub Cables Connect MST to FOSC/Terminal**
- Stub cables connect MSTs to FOSCs or Aerial Terminals
- **Critical**: Stub cable endpoints MUST touch the exact center of offset MST and FOSC
- When MST or FOSC is offset for visualization:
  - Stub cable routing uses original positions for pathfinding (along fiber cables)
  - Stub cable endpoints are adjusted to connect to exact offset positions
  - **After overlap offsetting**: Endpoints are restored to exact offset positions
- **Implementation**:
  - Load exact offset positions from saved `mst.geojson` and `fosc.geojson` files
  - Create new `path_coords` list with exact offset endpoints
  - After `offset_line_perpendicular()` for overlaps, restore endpoints to exact positions
  - Ensures stub cable visually connects to both offset MST and offset FOSC

**Rule 3: Drop Cables Always Connect to MST/Terminal**
- Drop cables connect ONTs to MSTs or Aerial Terminals
- When MST or Aerial Terminal is offset for visualization:
  - Drop cable terminal end uses `visualization_position` (offset position)
  - Drop cable ONT end remains at original position
  - Ensures drop cable visually connects to offset terminal
- **Implementation**:
  - Store `visualization_offset` and `visualization_position` in terminal objects
  - Use `visualization_position` for drop cable terminal endpoint

**Implementation Details**:
- Store `visualization_offset` and `visualization_position` in terminal objects
- Apply offsets after all logical connections are established
- Update visualization features to use offset positions
- Maintain original positions for routing and logical connections
- **Critical for Stub Cables**: After overlap offsetting, restore endpoints to exact offset positions

---

## Rule Application Order

1. **Rule 1**: Merge nearby FOSCs (consolidate first)
2. **Rule 3**: Remove redundant FOSCs (but keep junction FOSCs)
3. **Rule 7**: Place FOSCs at cable junctions (before connecting terminals)
4. **Rule 4**: Convert Aerial to MST and connect MSTs to FOSCs
5. **Rule 2**: Consolidate nearby terminals (after conversion)
6. **Rule 8**: Fix isolated terminals (remove islands)
7. **Rule 9**: Convert terminals to FOSCs (long non-straight cables)
8. **Rule 10**: Fix incorrect terminal connections
9. **Rule 12**: Split overloaded terminals at cable endpoints
10. **Rule 13**: Place MST near FOSC for specific ONTs
11. **Rule 15**: Convert FOSCs to MSTs for ONT connections
12. **Rule 14**: Enforce MST placement rules (ALL MSTs on cables and connected to FOSCs)
13. **Rule 16**: Enforce all terminals and FOSCs on fiber cables (comprehensive placement)
14. **Rule 17**: Optimize ONT-to-terminal connections (connect to nearest with capacity)
15. **Rule 18**: Merge underutilized MSTs (within 500m, one has 1-2 ONTs)
16. **Rule 19**: Ensure all ONTs are connected (final cleanup)
17. **Rule 20**: Ensure all MSTs connected via stub cables (routed along fiber)
18. **Rule 21**: Optimize stub cable connections (prefer shorter paths, FOSC over Aerial Terminal)
19. **Post-processing**: Merge very close FOSCs (within 1m) to prevent duplicates
20. **Rule 22**: Update cable IDs based on FOSC and terminal positions at endpoints
21. **Rule 5**: Filter distant ONTs (final cleanup)
22. **Rule 6**: Fix ONT-to-FOSC connections (ensure topology)

**Note**: Stub cable routing along fiber cables is handled in the visualization step using `route_stub_cable_along_fiber()`, which finds paths along existing fiber cable infrastructure.

---

## Implementation

All rules are implemented in `phases/phase3c_optimization_rules.py`:

```python
from phases.phase3c_optimization_rules import apply_all_optimization_rules

optimized_terminals, optimized_foscs, summary = apply_all_optimization_rules(
    terminals,
    foscs,
    cables,
    ont_geojson,
    config
)
```

---

## Results

Applied to test area (5km radius around 45.731437, -82.401057):

- **FOSCs merged**: 23 pairs
- **FOSCs removed (redundant)**: 6 (kept junction FOSCs)
- **FOSCs added at junctions**: 3 (including F1000397 for cables 96FOC/F1000391/F1000397, 48FOC/F1000397/F1000398, 12FOC/F1000397/T1001719)
- **Aerial Terminals converted to MST**: Variable
- **MSTs connected to FOSCs**: Variable
- **MSTs consolidated**: 6 pairs
- **ONTs filtered (>1km)**: Variable
- **ONTs fixed (was near FOSC)**: 0 (all ONTs correctly connected to terminals)

**Final state**:
- 61 terminals (43 MSTs, 18 Aerial)
- 7 FOSCs (4 original + 3 at cable junctions)
- All coordinates in UTM Zone 17N

---

## Notes

- All rules preserve cable junction FOSCs (needed for network topology)
- MST consolidation prioritizes keeping MSTs with more ONTs
- Rules can be applied to any area by extracting features within radius
- Rules are idempotent (can be run multiple times safely)
