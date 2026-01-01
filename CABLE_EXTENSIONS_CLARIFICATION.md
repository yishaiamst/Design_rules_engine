# Cable Extensions Clarification

## 📋 Overview

Cable extensions are primarily for **drop cables** and **stub cables**, not infrastructure cables.

---

## 🔌 Cable Types

### **1. Drop Cables**
- **From:** MST or Aerial Terminal
- **To:** ONT
- **Size:** 1F (default, configurable)
- **Purpose:** Connect individual ONTs to terminals
- **Created:** After terminal placement (Phase 5)

### **2. Stub Cables**
- **From:** MST Terminal
- **To:** FOSC
- **Size:** Matches MST type (MST4=4F, MST6=6F, MST8=8F, MST12=12F)
- **Purpose:** Connect MST to FOSC (part of MST product)
- **Created:** After terminal placement (Phase 5)

### **3. Infrastructure Cables (Advanced - Placeholder)**
- **Purpose:** Extend main infrastructure cables to improve service
- **Use Case:** Reduce stub lengths, bring capacity closer to communities
- **Status:** Advanced optimization - placeholder for future implementation

---

## 📊 Implementation Order

### **Phase 4: Terminal Placement**
- Place MSTs and Aerial Terminals
- Determine terminal types and locations
- **Output:** Terminal.geojson

### **Phase 5: Cable Extensions (Drop & Stub)**
- **Drop Cables:**
  - For each Terminal → identify connected ONTs
  - Create drop cable routes (Terminal → ONT)
  - Size: 1F (configurable)
  
- **Stub Cables:**
  - For each MST → find connected FOSC
  - Create stub cable routes (MST → FOSC)
  - Size: Based on MST type (from configuration)
  
- **Output:** drop cable.geojson, stub cable.geojson

### **Phase 6: Cable Sizing (Infrastructure)**
- Size all infrastructure cables (fiber cable.geojson)
- Based on service capacity requirements
- **Output:** Updated fiber cable.geojson (with sizes)

---

## 🔧 Configuration

### **Drop Cable Configuration:**
```json
{
  "cables": {
    "drop_cable": {
      "default_size": 1,
      "configurable": true,
      "description": "Drop cable from ONT to Terminal (default 1F)"
    }
  }
}
```

### **Stub Cable Configuration:**
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
      }
      // ... etc
    }
  }
}
```

---

## 📝 Advanced Use Case (Placeholder)

### **Infrastructure Cable Extensions**
**Status:** Placeholder for future optimization

**Potential Logic:**
- Analyze communities far from infrastructure
- Determine if extending infrastructure cables would improve service
- Reduce stub cable lengths
- Bring capacity closer to communities

**Implementation:** Can be added as an optimization phase after initial design is complete.

---

## ✅ Summary

- **Drop Cables:** Terminal → ONT (1F, created in Phase 5)
- **Stub Cables:** MST → FOSC (size matches MST type, created in Phase 5)
- **Infrastructure Extensions:** Advanced optimization (placeholder for future)



