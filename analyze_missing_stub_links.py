#!/usr/bin/env python3
"""
Analyze Missing Stub Cable Links
Identifies terminals with FDH_ID but no stub cable records.
"""

import json
import csv
from collections import defaultdict

print("Loading data files...")

# Load terminal data
with open('terminal.geojson', 'r') as f:
    terminal_data = json.load(f)

# Load stub cable data
with open('stub cable.geojson', 'r') as f:
    stub_cable_data = json.load(f)

# Load FDH data (for context)
with open('fdh.geojson', 'r') as f:
    fdh_data = json.load(f)

# Load logical graph to check virtual links
with open('logical_fiber_graph.json', 'r') as f:
    graph_data = json.load(f)

print(f"Loaded {len(terminal_data['features'])} terminals")
print(f"Loaded {len(stub_cable_data['features'])} stub cables")
print(f"Loaded {len(fdh_data['features'])} FDHs")

# Build stub cable index by terminal ID
stub_cable_terminals = set()
for feat in stub_cable_data['features']:
    props = {k.lower(): v for k, v in feat.get('properties', {}).items()}
    from_id = props.get('from_id') or props.get('fromid') or props.get('from')
    to_id = props.get('to_id') or props.get('toid') or props.get('to')
    
    if from_id:
        stub_cable_terminals.add(from_id)
    if to_id:
        stub_cable_terminals.add(to_id)

print(f"Found {len(stub_cable_terminals)} terminals in stub cable records")

# Build virtual fiber link index from graph
virtual_fiber_links = []
for link in graph_data.get('links', []):
    if link.get('virtual') and link.get('cable_layer') == 'fiber cable':
        if (link.get('source_layer') == 'terminal' and link.get('target_layer') == 'fdh'):
            virtual_fiber_links.append({
                'terminal_id': link['source'],
                'fdh_id': link['target'],
                'link_type': 'virtual_fiber_incorrect'
            })

print(f"Found {len(virtual_fiber_links)} virtual fiber links (Terminal → FDH)")

# Analyze terminals
missing_stub_links = []
terminal_stats = defaultdict(int)
terminals_with_fdh = 0
terminals_with_stub = 0
terminals_missing_stub = 0

for feat in terminal_data['features']:
    props = {k.lower(): v for k, v in feat.get('properties', {}).items()}
    
    terminal_id = props.get('id') or props.get('terminal_id') or props.get('termnal_id')
    if not terminal_id:
        continue
    
    terminal_type = (props.get('type') or 
                    props.get('terminal_type') or 
                    'Unknown')
    fdh_id = props.get('fdh_id') or props.get('fdhid')
    trunk_id = props.get('trunk_id') or props.get('trunkid')
    
    terminal_stats['total'] += 1
    
    # Check if terminal type is Aerial or MST
    is_aerial_or_mst = 'aerial' in terminal_type.lower() or terminal_type.lower() == 'mst'
    
    if terminal_type.lower() == 'mst':
        terminal_stats['mst'] += 1
    elif 'aerial' in terminal_type.lower():
        terminal_stats['aerial'] += 1
    
    # Check if terminal has FDH_ID
    if fdh_id:
        terminals_with_fdh += 1
        
        if terminal_type.lower() == 'mst':
            terminal_stats['mst_with_fdh'] += 1
        elif 'aerial' in terminal_type.lower():
            terminal_stats['aerial_with_fdh'] += 1
        
        # Check if terminal has stub cable
        has_stub = terminal_id in stub_cable_terminals
        
        if has_stub:
            terminals_with_stub += 1
            if terminal_type.lower() == 'mst':
                terminal_stats['mst_with_stub'] += 1
            elif 'aerial' in terminal_type.lower():
                terminal_stats['aerial_with_stub'] += 1
        else:
            terminals_missing_stub += 1
            if terminal_type.lower() == 'mst':
                terminal_stats['mst_missing_stub'] += 1
            elif 'aerial' in terminal_type.lower():
                terminal_stats['aerial_missing_stub'] += 1
            
            # Check if there's a virtual fiber link for this terminal
            virtual_fiber_found = any(
                vf['terminal_id'] == terminal_id and vf['fdh_id'] == fdh_id 
                for vf in virtual_fiber_links
            )
            
            missing_stub_links.append({
                'terminal_id': terminal_id,
                'type': terminal_type,
                'fdh_id': fdh_id,
                'trunk_id': trunk_id or '',
                'has_stub': False,
                'distance_to_fdh_m': '',  # Could calculate from geometry if needed
                'reclassify_as': 'virtual_stub_cable',
                'has_virtual_fiber_link': virtual_fiber_found
            })

print(f"\nAnalysis complete:")
print(f"  Total terminals: {terminal_stats['total']}")
print(f"  Terminals with FDH_ID: {terminals_with_fdh}")
print(f"  Terminals with stub cable: {terminals_with_stub}")
print(f"  Terminals missing stub cable: {terminals_missing_stub}")

# Save missing stub links CSV
with open('missing_stub_links.csv', 'w', encoding='utf-8', newline='') as f:
    if missing_stub_links:
        fieldnames = ['terminal_id', 'type', 'fdh_id', 'trunk_id', 'has_stub', 
                     'distance_to_fdh_m', 'reclassify_as', 'has_virtual_fiber_link']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(missing_stub_links)

print(f"\n✅ Saved {len(missing_stub_links)} missing stub links to missing_stub_links.csv")

# Generate summary report
summary = {
    'total_terminals_checked': terminal_stats['total'],
    'aerial_terminals': terminal_stats['aerial'],
    'mst_terminals': terminal_stats['mst'],
    'terminals_with_fdh': terminals_with_fdh,
    'terminals_with_stub': terminals_with_stub,
    'terminals_missing_stub': terminals_missing_stub,
    'missing_stub_percentage': round((terminals_missing_stub / terminals_with_fdh * 100) if terminals_with_fdh > 0 else 0, 2),
    'aerial_with_fdh': terminal_stats['aerial_with_fdh'],
    'aerial_with_stub': terminal_stats['aerial_with_stub'],
    'aerial_missing_stub': terminal_stats['aerial_missing_stub'],
    'aerial_missing_stub_percentage': round((terminal_stats['aerial_missing_stub'] / terminal_stats['aerial_with_fdh'] * 100) if terminal_stats['aerial_with_fdh'] > 0 else 0, 2),
    'mst_with_fdh': terminal_stats['mst_with_fdh'],
    'mst_with_stub': terminal_stats['mst_with_stub'],
    'mst_missing_stub': terminal_stats['mst_missing_stub'],
    'mst_missing_stub_percentage': round((terminal_stats['mst_missing_stub'] / terminal_stats['mst_with_fdh'] * 100) if terminal_stats['mst_with_fdh'] > 0 else 0, 2),
    'virtual_fiber_links_to_reclassify': len([vf for vf in virtual_fiber_links if any(
        ms['terminal_id'] == vf['terminal_id'] and ms['fdh_id'] == vf['fdh_id']
        for ms in missing_stub_links
    )])
}

with open('missing_stub_links_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"✅ Saved summary to missing_stub_links_summary.json")

# Print summary
print("\n" + "=" * 80)
print("MISSING STUB CABLE ANALYSIS SUMMARY")
print("=" * 80)
print(f"\n📊 OVERALL STATISTICS:")
print(f"   Total terminals checked: {summary['total_terminals_checked']:,}")
print(f"   Terminals with FDH_ID: {summary['terminals_with_fdh']:,}")
print(f"   Terminals with stub cable: {summary['terminals_with_stub']:,}")
print(f"   Terminals missing stub cable: {summary['terminals_missing_stub']:,} ({summary['missing_stub_percentage']:.2f}%)")
print(f"\n🏁 AERIAL TERMINALS:")
print(f"   Total with FDH: {summary['aerial_with_fdh']:,}")
print(f"   With stub cable: {summary['aerial_with_stub']:,} ({summary['aerial_with_stub']/summary['aerial_with_fdh']*100:.1f}%)" if summary['aerial_with_fdh'] > 0 else "   With stub cable: 0")
print(f"   Missing stub: {summary['aerial_missing_stub']:,} ({summary['aerial_missing_stub_percentage']:.2f}%) → reclassified as virtual_stub_cable")
print(f"\n🏗️  MST TERMINALS:")
print(f"   Total with FDH: {summary['mst_with_fdh']:,}")
print(f"   With stub cable: {summary['mst_with_stub']:,} ({summary['mst_with_stub']/summary['mst_with_fdh']*100:.1f}%)" if summary['mst_with_fdh'] > 0 else "   With stub cable: 0")
print(f"   Missing stub: {summary['mst_missing_stub']:,} ({summary['mst_missing_stub_percentage']:.2f}%) → reclassified as virtual_stub_cable")
print(f"\n🔄 VIRTUAL LINK RECLASSIFICATION:")
print(f"   Virtual fiber links to reclassify: {summary['virtual_fiber_links_to_reclassify']:,}")
print("\n" + "=" * 80)

print("\n📋 REFINEMENT RULE FOR GRAPH LOGIC:")
print("""
if link.virtual and link.source_type == "terminal" and link.target_type == "fdh":
    link.cable_layer = "stub cable"
    link.virtual_type = "virtual_stub_cable"
    # Keep virtual flag but change layer classification
""")


