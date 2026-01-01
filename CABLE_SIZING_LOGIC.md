# Cable Sizing Logic - Service-Based Calculation

## 📋 Overview

Cable sizing is determined by **service capacity requirements**, not just ONT count. The system calculates required fiber capacity based on:
- Service level per ONT
- OLT port capacity
- Oversubscription ratio
- Future growth
- OLT port count

---

## 🔧 Configuration File Structure

### **Equipment Configuration**

```json
{
  "equipment": {
    "mst": {
      "MST4": {
        "ports": 4,
        "stub_cable_size": 4,
        "description": "4-port MST with 4F stub cable"
      },
      "MST6": {
        "ports": 6,
        "stub_cable_size": 6,
        "description": "6-port MST with 6F stub cable"
      },
      "MST8": {
        "ports": 8,
        "stub_cable_size": 8,
        "description": "8-port MST with 8F stub cable"
      },
      "MST12": {
        "ports": 12,
        "stub_cable_size": 12,
        "description": "12-port MST with 12F stub cable"
      }
    },
    "aerial_terminal": {
      "AER-TRM4": {
        "ports": 4,
        "description": "4-port Aerial Terminal"
      },
      "AER-TRM6": {
        "ports": 6,
        "description": "6-port Aerial Terminal"
      },
      "AER-TRM8": {
        "ports": 8,
        "description": "8-port Aerial Terminal"
      },
      "AER-TRM12": {
        "ports": 12,
        "description": "12-port Aerial Terminal"
      }
    },
    "fosc": {
      "FOSC-12": {
        "fiber_capacity": 12,
        "description": "12-fiber FOSC"
      },
      "FOSC-24": {
        "fiber_capacity": 24,
        "description": "24-fiber FOSC"
      },
      "FOSC-48": {
        "fiber_capacity": 48,
        "description": "48-fiber FOSC"
      },
      "FOSC-96": {
        "fiber_capacity": 96,
        "description": "96-fiber FOSC"
      },
      "FOSC-144": {
        "fiber_capacity": 144,
        "description": "144-fiber FOSC"
      }
    },
    "fdh": {
      "FDH-288": {
        "fiber_capacity": 288,
        "description": "288-fiber FDH"
      },
      "FDH-576": {
        "fiber_capacity": 576,
        "description": "576-fiber FDH"
      }
    },
    "olt": {
      "OLT-8P": {
        "ports": 8,
        "port_capacity_gbps": 1,
        "description": "8-port OLT, 1G per port"
      },
      "OLT-16P": {
        "ports": 16,
        "port_capacity_gbps": 1,
        "description": "16-port OLT, 1G per port"
      },
      "OLT-8P-10G": {
        "ports": 8,
        "port_capacity_gbps": 10,
        "description": "8-port OLT, 10G per port"
      }
    }
  }
}
```

### **Service Configuration**

```json
{
  "service": {
    "service_per_ont_gbps": 1.0,
    "olt_port_capacity_gbps": 1.0,
    "oversubscription_ratios": [8, 16, 32, 64],
    "default_oversubscription": 32,
    "max_subscribers_per_port": 256,
    "future_growth_percentage": 10.0,
    "description": "Service configuration for capacity planning. max_subscribers_per_port is a hard limit regardless of service level."
  }
}
```

### **Cable Configuration**

```json
{
  "cables": {
    "drop_cable": {
      "default_size": 1,
      "configurable": true,
      "description": "Drop cable from ONT to Terminal (default 1F)"
    },
    "stub_cable": {
      "based_on_mst_type": true,
      "description": "Stub cable size matches MST type (MST4=4F, MST6=6F, etc.)"
    },
    "infrastructure_cable": {
      "standard_sizes": [12, 24, 48, 72, 96, 144, 288],
      "description": "Infrastructure cables are multiples of 12F"
    }
  }
}
```

---

## 📊 Cable Sizing Calculation Logic

### **Step 1: Calculate Subscribers per OLT Port**

```
Subscribers per Port = min(
    (OLT Port Capacity) / (Service per ONT) × Oversubscription Ratio,
    256  // Hard limit: Maximum 256 ONTs per port regardless of service
)

Example 1 (1G service):
  OLT Port Capacity: 1 Gbps
  Service per ONT: 1 Gbps
  Oversubscription: 1:32
  Calculated: 1 / 1 × 32 = 32 subscribers
  Capped at: min(32, 256) = 32 subscribers ✓

Example 2 (100M service):
  OLT Port Capacity: 1 Gbps
  Service per ONT: 0.1 Gbps
  Oversubscription: 1:32
  Calculated: 1 / 0.1 × 32 = 320 subscribers
  Capped at: min(320, 256) = 256 subscribers (hard limit) ✓
```

### **Step 2: Calculate Total Subscribers per OLT**

```
Total Subscribers = Subscribers per Port × OLT Port Count

Example:
  Subscribers per Port: 32
  OLT Ports: 8
  Total Subscribers = 32 × 8 = 256 subscribers
```

### **Step 3: Apply Future Growth**

```
Subscribers with Growth = Total Subscribers × (1 + Future Growth %)

Example:
  Total Subscribers: 256
  Future Growth: 10%
  Subscribers with Growth = 256 × 1.10 = 281.6 subscribers
```

### **Step 4: Adjust for Service Level**

```
Service Ratio = Service per ONT (Gbps) / 1.0 Gbps
Adjusted Capacity = Subscribers with Growth × Service Ratio

Key Insight: If service is smaller than 1G, cable size can be proportionally smaller
  Example: 100M service (0.1G) = 10× smaller → cable can be 10× smaller

Example:
  Subscribers with Growth: 281.6
  Service per ONT: 0.1 Gbps (100M)
  Service Ratio: 0.1 / 1.0 = 0.1 (10× smaller)
  Adjusted Capacity: 281.6 × 0.1 = 28.16 fibers
```

### **Step 5: Select Standard Cable Size**

```
Select smallest standard size that meets adjusted requirement:
  Standard Sizes: 12, 24, 48, 72, 96, 144, 288

Example 1 (1G service):
  Adjusted Capacity: 281.6 fibers
  Selected: 288F (smallest size ≥ 281.6)

Example 2 (100M service):
  Adjusted Capacity: 28.16 fibers
  Selected: 48F (smallest size ≥ 28.16, but could use 24F if acceptable)

Note: If required capacity exceeds 288F, use multiple 288F cables
  or consider larger OLT configuration.
```

---

## 🔄 Complete Calculation Examples

### **Example 1: Standard 1G Service, 1:32 Oversubscription**

**Input:**
- Service per ONT: 1 Gbps
- OLT Port Capacity: 1 Gbps
- Oversubscription: 1:32
- OLT Ports: 8
- Future Growth: 10%
- ONTs in area: 256

**Calculation:**
1. Subscribers per Port = 1 / 1 × 32 = **32**
2. Total Subscribers = 32 × 8 = **256**
3. With Growth = 256 × 1.10 = **281.6**
4. Required Fibers = **281.6**
5. Selected Cable Size = **288F** ✓

**Result:** Use 288F cable from OLT

---

### **Example 2: Smaller Community, Same Service**

**Input:**
- Service per ONT: 1 Gbps
- OLT Port Capacity: 1 Gbps
- Oversubscription: 1:32
- OLT Ports: 8
- Future Growth: 10%
- ONTs in area: 100

**Calculation:**
1. Subscribers per Port = 1 / 1 × 32 = **32**
2. Total Subscribers = 32 × 8 = **256** (OLT capacity)
3. With Growth = 256 × 1.10 = **281.6**
4. Required Fibers = **281.6** (based on OLT capacity, not actual ONTs)
5. Selected Cable Size = **288F**

**Alternative (if OLT sized for actual demand):**
- If we size OLT for 100 ONTs:
  - Required Ports = 100 / 32 = 3.125 → **4 ports**
  - Total Subscribers = 32 × 4 = **128**
  - With Growth = 128 × 1.10 = **140.8**
  - Selected Cable Size = **144F** ✓

**Result:** Use 144F cable (if OLT sized for demand) or 288F (if using standard OLT)

---

### **Example 3: Lower Service Level (100M per ONT)**

**Input:**
- Service per ONT: 0.1 Gbps (100 Mbps)
- OLT Port Capacity: 1 Gbps
- Oversubscription: 1:32
- OLT Ports: 8
- Future Growth: 10%
- ONTs in area: 256

**Calculation:**
1. Subscribers per Port = 1 / 0.1 × 32 = **320** (can serve 10× more subscribers per port)
2. Required Ports for 256 ONTs = 256 / 320 = **0.8 → 1 port** (only need 1 port!)
3. Total Capacity = 320 × 1 = **320** subscribers
4. With Growth = 320 × 1.10 = **352** subscribers
5. **Key Insight:** Since service is 10× smaller (0.1G vs 1G), cable size can be 10× smaller
6. Service Ratio = 0.1 / 1.0 = **0.1** (10× smaller)
7. Adjusted Capacity = 352 × 0.1 = **35.2** fibers
8. Selected Cable Size = **48F** (smallest standard size ≥ 35.2F)

**Result:** Lower service level allows smaller cable size (48F instead of 288F)

---

## 🧮 Cable Sizing Algorithm

```python
def calculate_required_cable_size(ont_count, service_config, olt_config):
    """
    Calculate required fiber cable size based on service capacity.
    
    Args:
        ont_count: Number of ONTs in the area
        service_config: {
            "service_per_ont_gbps": 1.0,
            "oversubscription": 32,
            "future_growth_percentage": 10.0
        }
        olt_config: {
            "ports": 8,
            "port_capacity_gbps": 1.0
        }
    
    Returns:
        Required cable size (fiber count)
    """
    # Step 1: Calculate subscribers per port (capped at hard limit)
    calculated_subscribers = (
        olt_config["port_capacity_gbps"] / 
        service_config["service_per_ont_gbps"] * 
        service_config["oversubscription"]
    )
    # Hard limit: Maximum 256 ONTs per port regardless of service
    max_subscribers = service_config.get("max_subscribers_per_port", 256)
    subscribers_per_port = min(calculated_subscribers, max_subscribers)
    
    # Step 2: Calculate required OLT ports
    required_ports = math.ceil(ont_count / subscribers_per_port)
    
    # Step 3: Calculate total capacity
    total_capacity = subscribers_per_port * required_ports
    
    # Step 4: Apply future growth
    with_growth = total_capacity * (1 + service_config["future_growth_percentage"] / 100)
    
    # Step 5: Adjust for service level
    # If service is smaller than 1G, cable size can be proportionally smaller
    # Base calculation assumes 1G service, adjust proportionally
    service_ratio = service_config["service_per_ont_gbps"] / 1.0  # Ratio to 1G
    adjusted_capacity = with_growth * service_ratio
    
    # Step 6: Select standard cable size
    standard_sizes = [12, 24, 48, 72, 96, 144, 288]
    matching_sizes = [s for s in standard_sizes if s >= adjusted_capacity]
    
    if matching_sizes:
        required_size = min(matching_sizes)
    else:
        # If exceeds 288F, use multiple 288F cables
        required_size = math.ceil(adjusted_capacity / 288) * 288
    
    return required_size
```

---

## 📐 Decision Tree for Cable Sizing

```
1. Calculate service capacity requirements:
   - Subscribers per port = (OLT port capacity) / (Service per ONT) × Oversubscription
   - Required ports = ceil(ONT count / Subscribers per port)
   - Total capacity = Subscribers per port × Required ports

2. Apply future growth:
   - Capacity with growth = Total capacity × (1 + Growth %)

3. Select cable size:
   - Find smallest standard size ≥ Capacity with growth
   - Standard sizes: 12, 24, 48, 72, 96, 144, 288

4. Consider actual ONT count:
   - If actual ONTs < calculated capacity, may use smaller cable
   - But must account for future growth and OLT capacity
```

---

## 🔑 Key Parameters (All Configurable)

1. **Service per ONT** (Gbps): 0.1, 0.5, 1.0, 2.5, 10.0
2. **OLT Port Capacity** (Gbps): 1, 10, 25
3. **Oversubscription Ratio**: 1:8, 1:16, 1:32, 1:64
4. **OLT Port Count**: 4, 8, 16, 32
5. **Future Growth %**: 0, 5, 10, 15, 20
6. **Drop Cable Size**: 1F (default, configurable)
7. **Stub Cable Size**: Based on MST type (MST4=4F, MST6=6F, etc.)

---

## ✅ Validation

- [ ] Service capacity calculations are correct
- [ ] Oversubscription ratios are applied correctly
- [ ] Future growth is accounted for
- [ ] Standard cable sizes are selected appropriately
- [ ] All parameters are configurable
- [ ] Equipment types match configuration

---

**This logic makes perfect sense!** Cable sizing is driven by service capacity requirements, not just ONT count. The configuration file allows flexibility for different service levels and equipment types.

