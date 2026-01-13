# Rule 23 Enhancement: Cable Size Constraint

## Problem

When connecting isolated cables to the network, we need to ensure that the connection follows infrastructure rules:
- **A cable can only connect to cables that are equal or larger in size**
- This prevents connecting a larger cable to a smaller infrastructure cable, which would violate network design principles

## Solution

Enhanced Rule 23 to include **cable size filtering**:

### Size Extraction
- Extracts cable size from cable ID format: `{SIZE}FOC/{FROM}/{TO}`
- Examples:
  - `48FOC/F1000509/T1002415` → 48 fibers
  - `144FOC/UNKNOWN/T0000003` → 144 fibers
  - `96FOC/UNKNOWN/T0000005` → 96 fibers

### Connection Logic
When finding connection points for an isolated cable:
1. **Extract isolated cable size** from its ID
2. **Filter candidate cables** by size:
   - Only consider cables where `target_size >= isolated_size`
   - Skip cables that are smaller than the isolated cable
3. **Prioritize FOSCs** (no size constraint - FOSCs can handle any size)
4. **Then consider filtered cables** (only those meeting size requirement)

### Example

**Isolated cable**: `48FOC/T0000005/UNKNOWN` (48 fibers)

**Candidate cables**:
- `144FOC/F1000391/F1000397` (144 fibers) ✓ **Can connect** (144 >= 48)
- `96FOC/UNKNOWN/T0000005` (96 fibers) ✓ **Can connect** (96 >= 48)
- `12FOC/F1000397/T1001719` (12 fibers) ✗ **Cannot connect** (12 < 48)
- `48FOC/F1000397/F1000398` (48 fibers) ✓ **Can connect** (48 >= 48)

## Implementation

```python
def extract_cable_size(cable_id: str) -> Optional[int]:
    """Extract cable size (fiber count) from cable ID."""
    # Example: "48FOC/F1000390/F1000502" -> 48
    
def find_nearest_connection_point(...):
    # Extract isolated cable size
    isolated_cable_size = extract_cable_size(cable_id)
    
    # Filter cables by size
    for cable_feat in all_cables:
        target_cable_size = extract_cable_size(target_cable_id)
        if target_cable_size < isolated_cable_size:
            continue  # Skip - too small
        # ... check distance ...
```

## Benefits

1. **Infrastructure Compliance**: Ensures connections follow proper network hierarchy
2. **Prevents Invalid Connections**: Won't connect 144F cable to 12F infrastructure
3. **Maintains Network Integrity**: Preserves the size hierarchy in the network design
4. **Automatic Enforcement**: No manual intervention needed

## Integration

The size constraint is automatically applied in:
- `phases/phase3e_connect_isolated_cables.py`
- Called from `generate_design.py` as Phase 3e
- Runs before cable sizing (Phase 6) to ensure all connections are valid

## Notes

- **FOSCs have no size constraint** - they can handle any cable size
- **Size is extracted from cable ID** - format must be `{SIZE}FOC/{FROM}/{TO}`
- **If size cannot be extracted**, the cable is still considered (fallback behavior)
- **Size constraint only applies to cable-to-cable connections**, not FOSC connections
