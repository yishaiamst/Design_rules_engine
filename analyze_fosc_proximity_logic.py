#!/usr/bin/env python3
"""
analyze_fosc_proximity_logic.py
-------------------------------------------------------------------------------
Analyze the refined logic:
- If communities within 1km of FOSC → use MST (maximize FOSC splicing)
- If communities near infrastructure cable → use Aerial Terminal
- Objective: Minimize mid-cable splicing
-------------------------------------------------------------------------------
"""

import json
from typing import Dict, List, Any
import statistics

def load_data():
    """Load all required data."""
    print("Loading data...")
    
    # Load terminal analysis
    with open('terminal_placement_analysis.json', 'r') as f:
        terminal_analysis = json.load(f)
    
    # Load terminals
    with open('Terminal.geojson', 'r') as f:
        terminals = json.load(f)
    
    # Load stub cables
    with open('stub cable.geojson', 'r') as f:
        stubs = json.load(f)
    
    stub_terminal_ids = set()
    for feature in stubs.get('features', []):
        to_id = feature.get('properties', {}).get('To_ID')
        if to_id:
            stub_terminal_ids.add(to_id)
    
    return terminal_analysis, terminals, stub_terminal_ids

def analyze_fosc_proximity_logic(terminal_analysis, terminals, stub_terminal_ids):
    """Analyze the refined logic based on FOSC proximity."""
    print("\nAnalyzing FOSC proximity logic...")
    
    # Categorize terminals
    aerial_near_fosc = []  # Aerial terminals ≤1km from FOSC
    aerial_far_fosc = []   # Aerial terminals >1km from FOSC
    mst_near_fosc = []     # MST terminals ≤1km from FOSC
    mst_far_fosc = []      # MST terminals >1km from FOSC
    
    # Check mid-cable splicing patterns
    aerial_near_fosc_mid_cable = []  # Aerial near FOSC that cause mid-cable splicing
    aerial_far_fosc_mid_cable = []   # Aerial far from FOSC that cause mid-cable splicing
    
    # Process aerial terminals
    for aerial_term in terminal_analysis['detailed_analysis']['aerial_terminals']:
        terminal_id = aerial_term['terminal_id']
        fosc_dist = aerial_term.get('distance_to_fosc_m')
        cable_dist = aerial_term.get('distance_to_infrastructure_cable_m', 9999)
        
        # Check if causes mid-cable splicing
        causes_mid_cable = False
        for feature in terminals.get('features', []):
            if feature.get('properties', {}).get('ID') == terminal_id:
                cable_id = feature.get('properties', {}).get('Cable_ID', '')
                if cable_id and '/F' in cable_id and '/T' in cable_id:
                    causes_mid_cable = True
                break
        
        term_data = {
            'terminal_id': terminal_id,
            'fosc_distance_m': fosc_dist,
            'cable_distance_m': cable_dist,
            'causes_mid_cable_splicing': causes_mid_cable
        }
        
        if fosc_dist is not None:
            if fosc_dist <= 1000:  # Within 1km
                aerial_near_fosc.append(term_data)
                if causes_mid_cable:
                    aerial_near_fosc_mid_cable.append(term_data)
            else:
                aerial_far_fosc.append(term_data)
                if causes_mid_cable:
                    aerial_far_fosc_mid_cable.append(term_data)
    
    # Process MST terminals
    for mst_term in terminal_analysis['detailed_analysis']['mst_terminals']:
        terminal_id = mst_term['terminal_id']
        fosc_dist = mst_term.get('distance_to_fosc_m')
        cable_dist = mst_term.get('distance_to_infrastructure_cable_m', 9999)
        
        term_data = {
            'terminal_id': terminal_id,
            'fosc_distance_m': fosc_dist,
            'cable_distance_m': cable_dist
        }
        
        if fosc_dist is not None:
            if fosc_dist <= 1000:  # Within 1km
                mst_near_fosc.append(term_data)
            else:
                mst_far_fosc.append(term_data)
    
    return {
        'aerial_near_fosc': aerial_near_fosc,
        'aerial_far_fosc': aerial_far_fosc,
        'mst_near_fosc': mst_near_fosc,
        'mst_far_fosc': mst_far_fosc,
        'aerial_near_fosc_mid_cable': aerial_near_fosc_mid_cable,
        'aerial_far_fosc_mid_cable': aerial_far_fosc_mid_cable
    }

def generate_summary(analysis):
    """Generate summary statistics."""
    print("\n" + "=" * 80)
    print("FOSC PROXIMITY LOGIC ANALYSIS")
    print("=" * 80)
    
    aerial_near = analysis['aerial_near_fosc']
    aerial_far = analysis['aerial_far_fosc']
    mst_near = analysis['mst_near_fosc']
    mst_far = analysis['mst_far_fosc']
    aerial_near_mid = analysis['aerial_near_fosc_mid_cable']
    aerial_far_mid = analysis['aerial_far_fosc_mid_cable']
    
    print(f"\n1. CURRENT DISTRIBUTION:")
    print(f"   Aerial Terminals:")
    print(f"     Near FOSC (≤1km): {len(aerial_near)} ({len(aerial_near)/(len(aerial_near)+len(aerial_far))*100:.1f}%)")
    print(f"     Far from FOSC (>1km): {len(aerial_far)} ({len(aerial_far)/(len(aerial_near)+len(aerial_far))*100:.1f}%)")
    
    print(f"\n   MST Terminals:")
    print(f"     Near FOSC (≤1km): {len(mst_near)} ({len(mst_near)/(len(mst_near)+len(mst_far))*100:.1f}%)")
    print(f"     Far from FOSC (>1km): {len(mst_far)} ({len(mst_far)/(len(mst_near)+len(mst_far))*100:.1f}%)")
    
    print(f"\n2. MID-CABLE SPLICING ANALYSIS:")
    print(f"   Aerial terminals near FOSC (≤1km) that cause mid-cable splicing:")
    print(f"     Count: {len(aerial_near_mid)} ({len(aerial_near_mid)/len(aerial_near)*100:.1f}% of aerial near FOSC)")
    print(f"     These could use MST instead to maximize FOSC splicing!")
    
    print(f"\n   Aerial terminals far from FOSC (>1km) that cause mid-cable splicing:")
    print(f"     Count: {len(aerial_far_mid)} ({len(aerial_far_mid)/len(aerial_far)*100:.1f}% of aerial far from FOSC)")
    
    # Calculate potential improvement
    if aerial_near:
        fosc_distances = [t['fosc_distance_m'] for t in aerial_near if t.get('fosc_distance_m')]
        if fosc_distances:
            print(f"\n3. DISTANCE STATISTICS:")
            print(f"   Aerial terminals near FOSC:")
            print(f"     Mean distance: {statistics.mean(fosc_distances):.1f}m")
            print(f"     Median distance: {statistics.median(fosc_distances):.1f}m")
            print(f"     Max distance: {max(fosc_distances):.1f}m")
    
    if mst_near:
        fosc_distances = [t['fosc_distance_m'] for t in mst_near if t.get('fosc_distance_m')]
        if fosc_distances:
            print(f"\n   MST terminals near FOSC:")
            print(f"     Mean distance: {statistics.mean(fosc_distances):.1f}m")
            print(f"     Median distance: {statistics.median(fosc_distances):.1f}m")
            print(f"     Max distance: {max(fosc_distances):.1f}m")
    
    print(f"\n4. REFINED LOGIC VALIDATION:")
    print(f"   ✅ If community ≤1km from FOSC → Use MST (maximize FOSC splicing)")
    print(f"      Current: {len(mst_near)} MSTs near FOSC")
    print(f"      Potential: {len(aerial_near_mid)} aerial terminals could be converted to MST")
    
    print(f"\n   ✅ If community near infrastructure cable (>1km from FOSC) → Use Aerial")
    print(f"      Current: {len(aerial_far)} aerial terminals far from FOSC")
    
    print(f"\n   📊 Potential reduction in mid-cable splicing:")
    print(f"      Current mid-cable splicing (aerial near FOSC): {len(aerial_near_mid)}")
    print(f"      If converted to MST: 0 mid-cable splicing")
    print(f"      Reduction: {len(aerial_near_mid)} terminals ({len(aerial_near_mid)/(len(aerial_near)+len(aerial_far))*100:.1f}% of all aerial terminals)")

def main():
    """Main execution."""
    terminal_analysis, terminals, stub_terminal_ids = load_data()
    analysis = analyze_fosc_proximity_logic(terminal_analysis, terminals, stub_terminal_ids)
    generate_summary(analysis)
    
    # Save results
    with open('fosc_proximity_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"\n✅ Saved fosc_proximity_analysis.json")

if __name__ == "__main__":
    main()



