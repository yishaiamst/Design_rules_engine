#!/usr/bin/env python3
"""
Analyze actual design to understand cable-FOSC connectivity patterns.
"""

import json
from collections import defaultdict
from utils.geojson_utils import load_geojson

def analyze_actual_connectivity():
    """Analyze how cables and FOSCs are connected in the actual design."""
    
    # Load actual design
    print("Loading actual design...")
    actual_cables = load_geojson("fiber cable.geojson")
    actual_foscs = load_geojson("splice closure.geojson")
    
    # Build FOSC ID to position map
    fosc_by_id = {}
    for feat in actual_foscs.get("features", []):
        props = feat.get("properties", {})
        fosc_id = props.get("ID", "")
        geom = feat.get("geometry", {})
        if fosc_id and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if coords and len(coords) >= 2:
                fosc_by_id[fosc_id] = (coords[0], coords[1])
    
    print(f"  Loaded {len(fosc_by_id)} FOSCs with positions")
    
    # Build cable connectivity graph from IDs
    cable_by_id = {}
    fosc_to_cables = defaultdict(list)  # fosc_id -> [cable_ids]
    cable_to_foscs = defaultdict(list)  # cable_id -> [fosc_ids]
    
    for feat in actual_cables.get("features", []):
        props = feat.get("properties", {})
        cable_id = props.get("ID", "")
        if not cable_id:
            continue
        
        cable_by_id[cable_id] = feat
        
        # Parse cable ID: {SIZE}FOC/{FROM_ID}/{TO_ID}
        parts = cable_id.split("/")
        if len(parts) >= 3:
            from_id = parts[1]
            to_id = parts[2]
            
            # Check if FROM/TO are FOSC IDs
            if from_id in fosc_by_id:
                fosc_to_cables[from_id].append(cable_id)
                if from_id not in cable_to_foscs[cable_id]:
                    cable_to_foscs[cable_id].append(from_id)
            
            if to_id in fosc_by_id:
                fosc_to_cables[to_id].append(cable_id)
                if to_id not in cable_to_foscs[cable_id]:
                    cable_to_foscs[cable_id].append(to_id)
    
    print(f"  Loaded {len(cable_by_id)} cables")
    print(f"  Found {len(fosc_to_cables)} FOSCs with cable connections")
    print(f"  Found {len(cable_to_foscs)} cables connected to FOSCs")
    
    # Analyze connectivity
    print("\n" + "=" * 80)
    print("CONNECTIVITY ANALYSIS")
    print("=" * 80)
    
    # Count cables per FOSC
    cables_per_fosc = [len(cables) for cables in fosc_to_cables.values()]
    print(f"\nCables per FOSC distribution:")
    from collections import Counter
    dist = Counter(cables_per_fosc)
    for count in sorted(dist.keys()):
        print(f"  {count} cables: {dist[count]} FOSCs")
    
    # Check if all cables are connected
    connected_cables = set()
    for cables in fosc_to_cables.values():
        connected_cables.update(cables)
    
    print(f"\nConnectivity:")
    print(f"  Total cables: {len(cable_by_id)}")
    print(f"  Cables connected to FOSCs: {len(connected_cables)}")
    print(f"  Unconnected cables: {len(cable_by_id) - len(connected_cables)}")
    
    # Sample some connections
    print(f"\nSample FOSC connections:")
    for fosc_id, cables in list(fosc_to_cables.items())[:10]:
        print(f"  {fosc_id}: {len(cables)} cables")
        for cable_id in cables[:3]:
            print(f"    - {cable_id}")
    
    # Check if cables form a connected graph
    print(f"\nGraph connectivity check:")
    visited_cables = set()
    components = []
    
    def dfs(cable_id, component):
        if cable_id in visited_cables:
            return
        visited_cables.add(cable_id)
        component.add(cable_id)
        
        # Find connected cables through FOSCs
        for fosc_id in cable_to_foscs.get(cable_id, []):
            for other_cable_id in fosc_to_cables.get(fosc_id, []):
                if other_cable_id != cable_id:
                    dfs(other_cable_id, component)
    
    for cable_id in cable_by_id.keys():
        if cable_id not in visited_cables:
            component = set()
            dfs(cable_id, component)
            if component:
                components.append(component)
    
    print(f"  Connected components: {len(components)}")
    if len(components) > 1:
        print(f"  ⚠️  WARNING: {len(components)} disconnected components!")
        for i, comp in enumerate(components[:5]):
            print(f"    Component {i+1}: {len(comp)} cables")
    else:
        print(f"  ✓ All cables form a single connected component")
    
    return {
        "fosc_to_cables": dict(fosc_to_cables),
        "cable_to_foscs": dict(cable_to_foscs),
        "fosc_by_id": fosc_by_id,
        "cable_by_id": cable_by_id,
        "components": components
    }

if __name__ == "__main__":
    analyze_actual_connectivity()

