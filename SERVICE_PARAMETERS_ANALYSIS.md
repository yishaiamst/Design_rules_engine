# Service Parameters Analysis - Cable Sizing Impact

## Current Service Parameters (design_config.json)

```json
{
  "service": {
    "service_per_ont_gbps": 1.0,
    "olt_port_capacity_gbps": 1.0,
    "oversubscription_ratios": [8, 16, 32, 64],
    "default_oversubscription": 32,
    "max_subscribers_per_port": 256,
    "future_growth_percentage": 10.0
  }
}
```

---

## How Service Parameters Impact Cable Sizing

### Formula Used in Phase 6

```python
# Step 1: Calculate users per fiber
users_per_fiber = (olt_port_capacity_gbps / service_per_ont_gbps) * oversubscription

# Step 2: Calculate required fibers
required_fibers = ceil(ont_count / users_per_fiber)

# Step 3: Apply future growth
with_growth = required_fibers * (1 + future_growth_percentage / 100)

# Step 4: Round to standard cable size
cable_size = min(standard_sizes where size >= with_growth)
```

---

## Parameter Impact Analysis

### 1. `service_per_ont_gbps` (Current: 1.0 Gbps)

**Impact:** Lower service = more ONTs per fiber = smaller cables

**Examples:**
- **1.0 Gbps** (current): 32 ONTs per fiber (with 32x oversubscription)
- **0.5 Gbps**: 64 ONTs per fiber → **50% smaller cables**
- **0.1 Gbps**: 320 ONTs per fiber → **90% smaller cables**
- **2.0 Gbps**: 16 ONTs per fiber → **2x larger cables**

**Current Value:** 1.0 Gbps (standard)

---

### 2. `olt_port_capacity_gbps` (Current: 1.0 Gbps)

**Impact:** Higher port capacity = more ONTs per fiber = smaller cables

**Examples:**
- **1.0 Gbps** (current): 32 ONTs per fiber
- **10.0 Gbps**: 320 ONTs per fiber → **90% smaller cables**
- **0.5 Gbps**: 16 ONTs per fiber → **2x larger cables**

**Note:** Also comes from OLT equipment config (OLT-8P-1G = 1.0 Gbps per port)

---

### 3. `default_oversubscription` (Current: 32)

**Impact:** Higher oversubscription = more ONTs per fiber = smaller cables

**Examples:**
- **32** (current): 32 ONTs per fiber
- **64**: 64 ONTs per fiber → **50% smaller cables**
- **16**: 16 ONTs per fiber → **2x larger cables**
- **8**: 8 ONTs per fiber → **4x larger cables**

**Current Value:** 32 (standard for residential)

---

### 4. `max_subscribers_per_port` (Current: 256)

**Impact:** Hard limit - caps subscribers per port regardless of calculation

**Examples:**
- **256** (current): Maximum 256 ONTs per port
- Even if formula says 500 ONTs per port, it's capped at 256
- This ensures we don't exceed physical/technical limits

**Current Value:** 256 (hard limit)

---

### 5. `future_growth_percentage` (Current: 10.0%)

**Impact:** Higher growth = larger cables (safety margin)

**Examples:**
- **10%** (current): Adds 10% to cable size
- **20%**: Adds 20% → **~9% larger cables**
- **50%**: Adds 50% → **~36% larger cables**
- **0%**: No growth buffer → **~9% smaller cables**

**Current Value:** 10.0% (standard planning buffer)

---

## Calculation Examples

### Example 1: 100 ONTs

**Current Parameters:**
- service_per_ont_gbps: 1.0
- olt_port_capacity_gbps: 1.0
- default_oversubscription: 32
- future_growth_percentage: 10.0%

**Calculation:**
1. users_per_fiber = (1.0 / 1.0) × 32 = **32 ONTs per fiber**
2. required_fibers = ceil(100 / 32) = **4 fibers**
3. with_growth = 4 × 1.10 = **4.4 fibers**
4. cable_size = **12F** (next standard size ≥ 4.4)

---

### Example 2: 1,000 ONTs

**Current Parameters:**
- users_per_fiber = 32
- required_fibers = ceil(1000 / 32) = **32 fibers**
- with_growth = 32 × 1.10 = **35.2 fibers**
- cable_size = **48F** (next standard size ≥ 35.2)

---

### Example 3: 10,000 ONTs

**Current Parameters:**
- users_per_fiber = 32
- required_fibers = ceil(10000 / 32) = **313 fibers**
- with_growth = 313 × 1.10 = **344.3 fibers**
- cable_size = **288F** (next standard size ≥ 344.3, but capped at max_size)

---

## Parameter Sensitivity

| Parameter | Current | If 2x | If 0.5x | Impact |
|-----------|---------|------|---------|--------|
| `service_per_ont_gbps` | 1.0 | 2.0 | 0.5 | **Inverse** (2x service = 0.5x cable) |
| `olt_port_capacity_gbps` | 1.0 | 2.0 | 0.5 | **Inverse** (2x capacity = 0.5x cable) |
| `default_oversubscription` | 32 | 64 | 16 | **Inverse** (2x oversub = 0.5x cable) |
| `future_growth_percentage` | 10% | 20% | 5% | **Direct** (2x growth = ~9% larger cable) |
| `max_subscribers_per_port` | 256 | 512 | 128 | **Direct** (only if formula exceeds limit) |

---

## Recommendations

### To Increase Cable Sizes:
1. **Decrease `service_per_ont_gbps`** (e.g., 0.5 Gbps → smaller cables)
2. **Decrease `default_oversubscription`** (e.g., 16 → larger cables)
3. **Increase `future_growth_percentage`** (e.g., 20% → larger cables)

### To Decrease Cable Sizes:
1. **Increase `service_per_ont_gbps`** (e.g., 2.0 Gbps → larger cables)
2. **Increase `default_oversubscription`** (e.g., 64 → smaller cables)
3. **Decrease `future_growth_percentage`** (e.g., 5% → smaller cables)

---

## Current Configuration Summary

```json
{
  "service": {
    "service_per_ont_gbps": 1.0,        // Standard 1G service
    "olt_port_capacity_gbps": 1.0,    // 1G per OLT port
    "default_oversubscription": 32,     // 32:1 split ratio
    "max_subscribers_per_port": 256,    // Hard limit
    "future_growth_percentage": 10.0   // 10% growth buffer
  }
}
```

**Result:** 32 ONTs per fiber, with 10% growth buffer

---

## Next Steps

1. ✅ Review current service parameters
2. ⏳ Adjust parameters if needed to match actual design patterns
3. ⏳ Test cable sizing with different parameter values
4. ⏳ Compare results with actual design to find optimal values
