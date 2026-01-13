# Which Fiber Cable File to Use?

## Quick Answer

**For final design and visualization: Use `fiber cable.geojson`**

This is the complete, final network with:
- ✅ All connections made (Rule 23 applied)
- ✅ Cable sizes assigned (Phase 6)
- ✅ CRS included (can be viewed on maps)
- ✅ Ready for production

---

## All Fiber Cable Files

### 1. `fiber_cable_updated_ids.geojson`
**When to use:**
- Analyzing cable ID assignment (Phase 3d)
- Before Rule 23 connections
- Understanding original network structure

**Contains:**
- Cables with updated From_ID/To_ID
- Before isolated cable connections
- May have isolated cables

**Status:** Intermediate file (before Rule 23)

---

### 2. `fiber_cable_connected.geojson`
**When to use:**
- Debugging Rule 23 connections
- Checking which cables were extended/connected
- Verifying road alignment (after enhancement)

**Contains:**
- All isolated cables connected (Rule 23 applied)
- Extended cables (with `extended: true` property)
- May have loops if loop detection failed

**Status:** After Rule 23, before cable sizing

---

### 3. `fiber cable.geojson` ⭐ **USE THIS**
**When to use:**
- **Final design visualization**
- **Production-ready network**
- **Map display**
- **BOM generation**

**Contains:**
- Complete connected network
- Cable sizes assigned (FiberCount property)
- All phases applied
- CRS included

**Status:** Final output (after all phases)

---

## Comparison Table

| File | Phase | Connections | Sizes | CRS | Use Case |
|------|-------|-------------|-------|-----|----------|
| `fiber_cable_updated_ids.geojson` | After 3d | ❌ | ❌ | ✅ | Analysis |
| `fiber_cable_connected.geojson` | After 3e | ✅ | ❌ | ✅ | Debugging |
| `fiber cable.geojson` | After 6 | ✅ | ✅ | ✅ | **Production** |

---

## For Your Current Task (Road Alignment)

**To see Rule 23 road alignment results:**
- Use `fiber_cable_connected.geojson` to see which connections were made
- Check the `extended` and `connected_to` properties
- Look for cables that follow roads vs. cross-country paths

**For final visualization:**
- Use `fiber cable.geojson` (final sized cables)

---

## File Locations

All files are in: `test_output/small_area_design_fresh/`

```
test_output/small_area_design_fresh/
├── fiber_cable_updated_ids.geojson    (intermediate)
├── fiber_cable_connected.geojson      (after Rule 23)
└── fiber cable.geojson                (FINAL - use this)
```

---

## Recommendation

**Always use `fiber cable.geojson` for:**
- ✅ Map visualization
- ✅ Final design review
- ✅ Production deployment
- ✅ Sharing with stakeholders

**Use other files only for:**
- 🔍 Debugging specific phases
- 🔍 Understanding intermediate steps
- 🔍 Analyzing rule application
