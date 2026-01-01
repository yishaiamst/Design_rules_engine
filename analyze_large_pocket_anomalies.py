#!/usr/bin/env python3
"""
analyze_large_pocket_anomalies.py
-------------------------------------------------------------------------------
Analyze large pockets to understand if they are anomalies or widespread.
Check if large diameters are caused by a few outlier ONTs.
Physical limit: OLT port max distance = 25km
-------------------------------------------------------------------------------
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, List, Any, Tuple
from utils.geojson_utils import load_geojson
from utils.spatial_utils import euclidean_distance, calculate_centroid, calculate_diameter
from utils.config_loader import load_config

def analyze_olt_ont_distances():
    """Analyze actual OLT-ONT distances in the design."""
    print("=" * 80)
    print("ANALYZING OLT-ONT DISTANCES IN ACTUAL DESIGN")
    print("=" * 80)
    print()
    
    # Load OLT-ONT paths
    with open('olt_ont_paths.json', 'r') as f:
        paths = json.load(f)
    
    # Load positions
    ont_geojson = load_geojson('ONT.geojson')
    olt_geojson = load_geojson('OLT.geojson')
    
    # Extract positions
    ont_positions = {}
    for feature in ont_geojson.get('features', []):
        ont_id = str(feature.get('properties', {}).get('ID') or feature.get('properties', {}).get('id', ''))
        geometry = feature.get('geometry', {})
        if geometry.get('type') == 'Point':
            coords = geometry.get('coordinates', [])
            if len(coords) >= 2:
                ont_positions[ont_id] = (coords[0], coords[1])
    
    olt_positions = {}
    for feature in olt_geojson.get('features', []):
        olt_id = str(feature.get('properties', {}).get('ID') or feature.get('properties', {}).get('id', ''))
        geometry = feature.get('geometry', {})
        if geometry.get('type') == 'Point':
            coords = geometry.get('coordinates', [])
            if len(coords) >= 2:
                olt_positions[olt_id] = (coords[0], coords[1])
        elif geometry.get('type') == 'MultiPoint':
            coords_list = geometry.get('coordinates', [])
            if coords_list and len(coords_list[0]) >= 2:
                olt_positions[olt_id] = (coords_list[0][0], coords_list[0][1])
    
    # Group ONTs by OLT
    olt_ont_map = {}
    for path in paths:
        olt_id = str(path.get('olt_id', ''))
        ont_id = str(path.get('ont_id', ''))
        if olt_id and ont_id:
            if olt_id not in olt_ont_map:
                olt_ont_map[olt_id] = []
            olt_ont_map[olt_id].append(ont_id)
    
    # Analyze each OLT
    print("OLT Distance Analysis:")
    print(f"{'OLT ID':<10} {'ONT Count':<12} {'Mean Dist':<12} {'Max Dist':<12} {'>25km':<10} {'% >25km':<10} {'Diameter':<12}")
    print("-" * 90)
    
    violations = []
    total_violations = 0
    total_onts = 0
    
    for olt_id in sorted(olt_ont_map.keys()):
        ont_ids = olt_ont_map[olt_id]
        if olt_id not in olt_positions:
            continue
        
        olt_pos = olt_positions[olt_id]
        distances = []
        ont_positions_list = []
        
        for ont_id in ont_ids:
            if ont_id in ont_positions:
                ont_pos = ont_positions[ont_id]
                ont_positions_list.append(ont_pos)
                dist = euclidean_distance(olt_pos[0], olt_pos[1], ont_pos[0], ont_pos[1]) / 1000
                distances.append(dist)
        
        if not distances:
            continue
        
        # Count violations (>25km)
        violations_count = len([d for d in distances if d > 25.0])
        violations_pct = (violations_count / len(distances) * 100) if distances else 0
        
        # Calculate diameter
        diameter = calculate_diameter(ont_positions_list) / 1000
        
        import statistics
        mean_dist = statistics.mean(distances) if distances else 0
        max_dist = max(distances) if distances else 0
        
        status = "⚠️" if violations_count > 0 else "✓"
        
        print(f"{olt_id:<10} {len(ont_ids):<12} {mean_dist:<12.2f} {max_dist:<12.2f} "
              f"{violations_count:<10} {violations_pct:<10.1f} {diameter:<12.2f} {status}")
        
        if violations_count > 0:
            violations.append({
                'olt_id': olt_id,
                'violations': violations_count,
                'total_onts': len(distances),
                'max_distance': max_dist,
                'diameter': diameter
            })
            total_violations += violations_count
        
        total_onts += len(distances)
    
    print()
    print("=" * 80)
    print("VIOLATION SUMMARY")
    print("=" * 80)
    print(f"Total ONTs analyzed: {total_onts}")
    print(f"Total violations (>25km): {total_violations} ({total_violations/total_onts*100:.2f}%)")
    print(f"OLTs with violations: {len(violations)} out of {len(olt_ont_map)}")
    print()
    
    if violations:
        print("OLTs with violations:")
        for v in violations:
            print(f"  OLT {v['olt_id']}: {v['violations']} violations ({v['violations']/v['total_onts']*100:.1f}%) "
                  f"out of {v['total_onts']} ONTs, max distance: {v['max_distance']:.2f}km, diameter: {v['diameter']:.2f}km")
    
    return violations

def analyze_large_pocket_outliers(olt_id: str, max_distance_km: float = 25.0):
    """Analyze if large pocket diameter is caused by outlier ONTs."""
    print(f"\n{'='*80}")
    print(f"ANALYZING OUTLIERS IN OLT {olt_id}")
    print(f"{'='*80}\n")
    
    # Load data
    with open('olt_ont_paths.json', 'r') as f:
        paths = json.load(f)
    
    ont_geojson = load_geojson('ONT.geojson')
    olt_geojson = load_geojson('OLT.geojson')
    
    # Get OLT position
    olt_pos = None
    for feature in olt_geojson.get('features', []):
        olt_id_check = str(feature.get('properties', {}).get('ID') or feature.get('properties', {}).get('id', ''))
        if olt_id_check == olt_id:
            geometry = feature.get('geometry', {})
            if geometry.get('type') == 'Point':
                coords = geometry.get('coordinates', [])
                if len(coords) >= 2:
                    olt_pos = (coords[0], coords[1])
            elif geometry.get('type') == 'MultiPoint':
                coords_list = geometry.get('coordinates', [])
                if coords_list and len(coords_list[0]) >= 2:
                    olt_pos = (coords_list[0][0], coords_list[0][1])
            break
    
    if not olt_pos:
        print(f"OLT {olt_id} not found")
        return
    
    # Get ONT positions for this OLT
    ont_positions = {}
    for path in paths:
        if str(path.get('olt_id', '')) == olt_id:
            ont_id = str(path.get('ont_id', ''))
            for feature in ont_geojson.get('features', []):
                ont_id_check = str(feature.get('properties', {}).get('ID') or feature.get('properties', {}).get('id', ''))
                if ont_id_check == ont_id:
                    geometry = feature.get('geometry', {})
                    if geometry.get('type') == 'Point':
                        coords = geometry.get('coordinates', [])
                        if len(coords) >= 2:
                            ont_positions[ont_id] = (coords[0], coords[1])
                    break
    
    # Calculate distances
    distances = []
    for ont_id, ont_pos in ont_positions.items():
        dist = euclidean_distance(olt_pos[0], olt_pos[1], ont_pos[0], ont_pos[1]) / 1000
        distances.append((ont_id, dist, ont_pos))
    
    distances.sort(key=lambda x: x[1], reverse=True)
    
    # Find violations
    violations = [d for d in distances if d[1] > max_distance_km]
    
    print(f"Total ONTs: {len(distances)}")
    print(f"Violations (>25km): {len(violations)} ({len(violations)/len(distances)*100:.1f}%)")
    print()
    
    if violations:
        print("Top 10 farthest ONTs:")
        for i, (ont_id, dist, pos) in enumerate(violations[:10]):
            print(f"  {i+1}. {ont_id}: {dist:.2f} km from OLT")
        
        # Check if removing outliers reduces diameter
        print(f"\nAnalyzing diameter with and without outliers...")
        
        all_positions = [d[2] for d in distances]
        diameter_all = calculate_diameter(all_positions) / 1000
        
        # Remove outliers (>25km)
        valid_positions = [d[2] for d in distances if d[1] <= max_distance_km]
        diameter_valid = calculate_diameter(valid_positions) / 1000 if valid_positions else 0
        
        print(f"  Diameter with all ONTs: {diameter_all:.2f} km")
        print(f"  Diameter without outliers (>25km): {diameter_valid:.2f} km")
        print(f"  Reduction: {diameter_all - diameter_valid:.2f} km")
        
        # Check if diameter is caused by outliers
        if diameter_valid <= 25.0:
            print(f"\n  ✅ Diameter is within 25km when outliers are removed")
            print(f"  → Large diameter is caused by {len(violations)} outlier ONTs ({len(violations)/len(distances)*100:.1f}%)")
        else:
            print(f"\n  ⚠️  Diameter still exceeds 25km even without outliers")
            print(f"  → Large diameter is widespread, not just outliers")

def test_pocket_splitting_with_25km_limit():
    """Test how many pockets we get with 25km diameter limit."""
    print(f"\n{'='*80}")
    print("TESTING POCKET SPLITTING WITH 25KM DIAMETER LIMIT")
    print(f"{'='*80}\n")
    
    config = load_config()
    ont_geojson = load_geojson('ONT.geojson')
    fiber_cable_geojson = load_geojson('fiber cable.geojson')
    
    # Test with 25km limit (strict mode)
    config['placement']['olt']['pocket_max_diameter_km'] = 25.0
    config['placement']['olt']['pocket_diameter_enforcement'] = 'strict'
    
    from phases.phase0_community_pockets import create_community_pockets
    
    print("Creating pockets with 25km diameter limit (strict mode)...")
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    
    print(f"\nResult: {len(pockets)} pockets with 25km diameter limit")
    
    # Compare to 17 OLTs
    print(f"Comparison: {len(pockets)} pockets vs 17 OLTs")
    if len(pockets) == 17:
        print("  ✅ Perfect match!")
    elif len(pockets) > 17:
        print(f"  ⚠️  {len(pockets) - 17} more pockets than OLTs")
    else:
        print(f"  ⚠️  {17 - len(pockets)} fewer pockets than OLTs")
    
    return pockets

def main():
    """Main analysis."""
    # 1. Analyze OLT-ONT distances
    violations = analyze_olt_ont_distances()
    
    # 2. Analyze outliers in large pockets
    if violations:
        print("\n" + "=" * 80)
        print("ANALYZING LARGE POCKET OUTLIERS")
        print("=" * 80)
        
        # Analyze the OLTs with largest diameters
        large_olts = sorted(violations, key=lambda x: x['diameter'], reverse=True)
        
        for v in large_olts[:3]:  # Top 3
            analyze_large_pocket_outliers(v['olt_id'], max_distance_km=25.0)
    
    # 3. Test pocket splitting with 25km limit
    pockets_25km = test_pocket_splitting_with_25km_limit()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 80)
    print()
    print("Physical Limit: OLT port max distance = 25km")
    print()
    print("Findings:")
    print(f"  • OLTs with violations: {len(violations)}")
    print(f"  • Pockets with 25km limit: {len(pockets_25km)}")
    print(f"  • Target: 17 pockets (matching OLTs)")
    print()
    print("Recommendations:")
    if len(pockets_25km) == 17:
        print("  ✅ Use 25km diameter limit - matches OLT count perfectly!")
    elif len(pockets_25km) > 17:
        print(f"  ⚠️  25km limit creates {len(pockets_25km)} pockets (more than 17 OLTs)")
        print("  → May need to adjust clustering/merging logic")
    else:
        print(f"  ⚠️  25km limit creates {len(pockets_25km)} pockets (fewer than 17 OLTs)")
        print("  → May need to relax limit slightly")

if __name__ == "__main__":
    main()


