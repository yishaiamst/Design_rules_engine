# OLT Placement Analysis Summary

## Key Findings

### Subscriber Distribution Across OLTs

**Total:** 17 OLTs serving 22,769 ONTs

| Category | Subscriber Range | Count | Percentage | Example |
|----------|-----------------|-------|------------|---------|
| **Very Large** | ≥2000 | 3 | 17.6% | OLT 101: 2,237 ONTs |
| **Large** | 1000-2000 | 7 | 41.2% | OLT 103: 1,927 ONTs |
| **Medium** | 500-1000 | 6 | 35.3% | OLT 302: 507 ONTs |
| **Small** | <500 | 1 | 5.9% | OLT 301: 313 ONTs |

### Statistics

- **Mean:** 1,339 ONTs per OLT
- **Median:** 1,468 ONTs per OLT
- **Min:** 313 ONTs (OLT 301)
- **Max:** 2,237 ONTs (OLT 101)
- **25th percentile:** 743 ONTs
- **75th percentile:** 1,954 ONTs

### Notable Case: OLT 301

- **Subscribers:** 313 (well below 500 threshold)
- **Mean distance:** 1.49 km (compact community)
- **Max distance:** 19.15 km (close to 20km limit)
- **Rationale:** Isolated community that warrants its own OLT despite small size

---

## Refined R16 Rule

### Original Rule
- Place OLT if community ≥2000 subscribers
- Otherwise assign to nearest OLT

### Refined Rule (Based on Empirical Data)

**Primary Threshold:**
- **≥2000 subscribers** → Place OLT at cluster centroid (definitive)

**Secondary Thresholds:**
- **500-2000 subscribers** → Consider OLT placement, especially if >15km from nearest OLT
- **<500 subscribers but >15km from nearest OLT** → May warrant OLT for isolated communities
- **<500 subscribers and <15km from existing OLT** → Assign to nearest OLT (within 20 km)

### Decision Logic

```
IF cluster_size >= 2000:
    → Place OLT (primary rule)
    
ELIF cluster_size >= 500:
    → IF distance_to_nearest_OLT > 15km:
        → Consider OLT placement
    → ELSE:
        → Assign to nearest OLT
        
ELIF cluster_size < 500:
    → IF distance_to_nearest_OLT > 15km:
        → May warrant OLT (isolated community)
    → ELSE:
        → Assign to nearest OLT (within 20km)
```

---

## Implications for Design Engine

### OLT Placement Algorithm

1. **Cluster ONTs** by proximity (2 km radius)
2. **Count subscribers** per cluster
3. **Calculate distance** to nearest existing OLT
4. **Apply decision logic** above
5. **Validate** against R15 (max 20km distance)

### Key Thresholds

- **Large community:** ≥2000 subscribers
- **Medium community:** 500-2000 subscribers
- **Small community:** <500 subscribers
- **Isolation distance:** 15 km
- **Max assignment distance:** 20 km (R15)

---

## Files Generated

1. **`olt_subscriber_density_analysis.json`** - Complete analysis with per-OLT statistics
2. **`olt_placement_rules.json`** - Updated R16 rule with empirical evidence
3. **`design_rules_reference.json`** - Updated consolidated rules (now 31 rules total)

---

## Next Steps

✅ Rules R15 and R16 are now refined and ready for design engine implementation.

The design engine should:
1. Cluster ONTs by proximity
2. Apply R16 placement logic
3. Validate against R15 (20km max distance)
4. Optimize OLT placement to minimize violations




