#!/usr/bin/env python3
"""
Simple debug: Check why FOSC aggregation returns 0
Focuses on the actual issue in Phase 6
"""

import json
import os
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance

def analyze_fosc_cable_matching():
    """Check if FOSCs from Phase 2/3 match cables in Phase 6."""
    print("=" * 80)
    print("DEBUGGING FOSC AGGREGATION ISSUE")
    print("=" * 80)
    print()
    
    # Load actual FOSCs from design (if available)
    print("1. Checking FOSC positions...")
    try:
        actual_foscs = load_geojson("splice closure.geojson")
        print(f"   ✓ Loaded {len(actual_foscs.get('features', []))} actual FOSCs")
    except:
        print("   ⚠️  Could not load actual FOSCs")
        actual_foscs = None
    
    # Load generated FOSCs (from test_output if available)
    print("2. Checking generated FOSCs...")
    generated_foscs_path = "test_output/splice closure.geojson"
    if os.path.exists(generated_foscs_path):
        generated_foscs = load_geojson(generated_foscs_path)
        print(f"   ✓ Loaded {len(generated_foscs.get('features', []))} generated FOSCs")
    else:
        print("   ⚠️  Generated FOSCs not found (run Phase 2 first)")
        generated_foscs = None
    
    # Load cables
    print("3. Loading cables...")
    cables_geojson = load_geojson("fiber cable.geojson")
    cables = []
    for i, feature in enumerate(cables_geojson.get("features", [])):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        coords = []
        geom_type = geometry.get("type", "")
        if geom_type == "LineString":
            coords = geometry.get("coordinates", [])
        elif geom_type == "MultiLineString":
            for line in geometry.get("coordinates", []):
                coords.extend(line)
        
        if len(coords) >= 2:
            cables.append({
                "index": i,
                "id": props.get("ID") or props.get("id", ""),
                "start": coords[0],
                "end": coords[-1],
                "coordinates": coords
            })
    
    print(f"   ✓ Loaded {len(cables)} cables")
    print()
    
    # Check FOSC-cable matching
    print("=" * 80)
    print("FOSC-CABLE MATCHING ANALYSIS")
    print("=" * 80)
    print()
    
    tolerance_m = 10.0
    
    # Check generated FOSCs
    if generated_foscs:
        print("Checking generated FOSCs against cables...")
        fosc_positions = []
        for feature in generated_foscs.get("features", []):
            geometry = feature.get("geometry", {})
            props = feature.get("properties", {})
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                fosc_positions.append({
                    "id": props.get("ID") or props.get("id", ""),
                    "position": (coords[0], coords[1])
                })
        
        print(f"  Checking {len(fosc_positions)} FOSCs...")
        
        matches_per_fosc = []
        for fosc in fosc_positions[:20]:  # Check first 20
            fosc_pos = fosc["position"]
            matching_cables = []
            
            for cable in cables:
                dist_to_start = euclidean_distance(fosc_pos[0], fosc_pos[1], cable["start"][0], cable["start"][1])
                dist_to_end = euclidean_distance(fosc_pos[0], fosc_pos[1], cable["end"][0], cable["end"][1])
                
                if dist_to_start <= tolerance_m or dist_to_end <= tolerance_m:
                    matching_cables.append({
                        "cable_idx": cable["index"],
                        "dist_to_start": dist_to_start,
                        "dist_to_end": dist_to_end
                    })
            
            matches_per_fosc.append({
                "fosc_id": fosc["id"],
                "position": fosc_pos,
                "matching_cables": len(matching_cables)
            })
            
            if len(matching_cables) >= 2:
                print(f"  ✓ FOSC {fosc['id']}: {len(matching_cables)} matching cables")
        
        print()
        
        # Summary
        foscs_with_2plus = sum(1 for m in matches_per_fosc if m["matching_cables"] >= 2)
        foscs_with_1 = sum(1 for m in matches_per_fosc if m["matching_cables"] == 1)
        foscs_with_0 = sum(1 for m in matches_per_fosc if m["matching_cables"] == 0)
        
        print("SUMMARY:")
        print(f"  FOSCs checked: {len(matches_per_fosc)}")
        print(f"  FOSCs with 2+ cables: {foscs_with_2plus}")
        print(f"  FOSCs with 1 cable: {foscs_with_1}")
        print(f"  FOSCs with 0 cables: {foscs_with_0}")
        print()
        
        if foscs_with_2plus == 0:
            print("⚠️  ISSUE FOUND:")
            print("  No FOSCs have 2+ matching cables!")
            print("  This explains why FOSC aggregation returns 0.")
            print()
            print("Possible causes:")
            print("  1. FOSC positions don't match cable endpoints (tolerance too small?)")
            print("  2. FOSCs placed at mid-segment, not at endpoints")
            print("  3. Cable coordinates don't match FOSC positions")
            print()
            print("Recommendation:")
            print("  - Check Phase 2 FOSC placement logic")
            print("  - Verify FOSCs are placed at cable junctions/endpoints")
            print("  - Consider increasing tolerance or checking mid-segment matches")
    
    # Check Phase 6 logic issue
    print("=" * 80)
    print("PHASE 6 LOGIC ANALYSIS")
    print("=" * 80)
    print()
    
    print("The FOSC aggregation logic in Phase 6:")
    print("  1. Builds FOSC position map (rounded to 10m grid)")
    print("  2. For each FOSC, finds cables within 10m of start/end")
    print("  3. Determines incoming vs outgoing based on OLT distance")
    print("  4. Aggregates incoming sizes and applies to outgoing")
    print()
    print("If 0 aggregations, possible issues:")
    print("  - FOSC positions rounded incorrectly")
    print("  - Cable endpoints don't match FOSC positions")
    print("  - Direction detection (incoming/outgoing) failing")
    print("  - Less than 2 cables found at any FOSC")
    print()
    
    # Save results
    results = {
        "cables_loaded": len(cables),
        "fosc_analysis": matches_per_fosc if generated_foscs else [],
        "tolerance_m": tolerance_m
    }
    
    os.makedirs("test_output", exist_ok=True)
    with open("test_output/fosc_aggregation_simple_debug.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("✓ Saved results to test_output/fosc_aggregation_simple_debug.json")


if __name__ == "__main__":
    analyze_fosc_cable_matching()

