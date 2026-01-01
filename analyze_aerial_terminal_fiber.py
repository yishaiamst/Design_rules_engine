#!/usr/bin/env python3
"""
Analyze Aerial Terminal Fiber Cable Connectivity
Verifies that Aerial Terminals are connected via fiber cables using cable_id property.
"""

import json
import csv
from collections import defaultdict

print("Loading data files...")

# Load terminal data
with open('terminal.geojson', 'r') as f:
    terminal_data = json.load(f)

# Load fiber cable data
with open('fiber cable.geojson', 'r') as f:
    fiber_cable_data = json.load(f)

# Load FDH data (for context)
with open('fdh.geojson', 'r') as f:
    fdh_data = json.load(f)

# Load logical graph to check virtual links
with open('logical_fiber_graph.json', 'r') as f:
    graph_data = json.load(f)

print(f"Loaded {len(terminal_data['features'])} terminals")
print(f"Loaded {len(fiber_cable_data['features'])} fiber cables")
print(f"Loaded {len(fdh_data['features'])} FDHs")

# Build fiber cable ID index
fiber_cable_ids = set()
fiber_cable_records = {}
for feat in fiber_cable_data['features']:
    props = {k.lower(): v for k, v in feat.get('properties', {}).items()}
    cable_id = props.get('id') or props.get('id')
    if cable_id:
        fiber_cable_ids.add(cable_id)
        fiber_cable_records[cable_id] = props

print(f"Indexed {len(fiber_cable_ids)} fiber cable IDs")

# Build virtual link index (Terminal → FDH)
virtual_fiber_links = {}
for link in graph_data.get('links', []):
    if link.get('virtual') and link.get('cable_layer') == 'fiber cable':
        if link.get('source_layer') == 'terminal' and link.get('target_layer') == 'fdh':
            terminal_id = link['source']
            fdh_id = link['target']
            if terminal_id not in virtual_fiber_links:
                virtual_fiber_links[terminal_id] = []
            virtual_fiber_links[terminal_id].append(fdh_id)

print(f"Found {len(virtual_fiber_links)} terminals with virtual fiber links")

# Analyze Aerial Terminals
aerial_terminal_analysis = []
stats = {
    'total_aerial': 0,
    'with_fdh_id': 0,
    'with_cable_id': 0,
    'has_fiber_cable': 0,
    'missing_fiber_cable': 0,
    'has_virtual_link': 0,
    'unnecessary_virtual': 0
}

fdh_breakdown = defaultdict(lambda: {
    'total_terminals': 0,
    'connected_to_fiber': 0,
    'missing_cable': 0
})

for feat in terminal_data['features']:
    props = {k.lower(): v for k, v in feat.get('properties', {}).items()}
    
    terminal_id = props.get('id') or props.get('terminal_id') or props.get('termnal_id')
    terminal_type = props.get('type') or props.get('terminal_type') or 'Unknown'
    
    # Filter for Aerial Terminals only
    if 'aerial' not in terminal_type.lower():
        continue
    
    stats['total_aerial'] += 1
    
    fdh_id = props.get('fdh_id') or props.get('fdhid')
    trunk_id = props.get('trunk_id') or props.get('trunkid')
    cable_id = props.get('cable_id') or props.get('cableid')
    
    if fdh_id:
        stats['with_fdh_id'] += 1
        fdh_breakdown[fdh_id]['total_terminals'] += 1
    
    if cable_id:
        stats['with_cable_id'] += 1
    
    # Check if cable_id exists in fiber cable layer
    has_fiber_cable = cable_id in fiber_cable_ids if cable_id else False
    
    if has_fiber_cable:
        stats['has_fiber_cable'] += 1
        if fdh_id:
            fdh_breakdown[fdh_id]['connected_to_fiber'] += 1
    else:
        stats['missing_fiber_cable'] += 1
        if fdh_id:
            fdh_breakdown[fdh_id]['missing_cable'] += 1
    
    # Check for virtual link
    has_virtual_link = terminal_id in virtual_fiber_links
    unnecessary_virtual = False
    
    if has_virtual_link:
        stats['has_virtual_link'] += 1
        # Check if this terminal has both fiber cable AND virtual link
        if has_fiber_cable:
            # Check if virtual link goes to the same FDH
            if fdh_id and fdh_id in virtual_fiber_links.get(terminal_id, []):
                unnecessary_virtual = True
                stats['unnecessary_virtual'] += 1
    
    aerial_terminal_analysis.append({
        'terminal_id': terminal_id,
        'fdh_id': fdh_id or '',
        'cable_id': cable_id or '',
        'has_fiber_cable': has_fiber_cable,
        'has_virtual_link': has_virtual_link,
        'unnecessary_virtual': unnecessary_virtual
    })

print(f"\nAnalysis complete:")
print(f"  Total Aerial Terminals: {stats['total_aerial']}")
print(f"  With FDH_ID: {stats['with_fdh_id']}")
print(f"  With cable_id: {stats['with_cable_id']}")
print(f"  Has matching fiber cable: {stats['has_fiber_cable']}")
print(f"  Missing fiber cable: {stats['missing_fiber_cable']}")
print(f"  Has virtual link: {stats['has_virtual_link']}")
print(f"  Unnecessary virtual links: {stats['unnecessary_virtual']}")

# Save detailed CSV
with open('aerial_terminal_fiber_check.csv', 'w', encoding='utf-8', newline='') as f:
    if aerial_terminal_analysis:
        fieldnames = ['terminal_id', 'fdh_id', 'cable_id', 'has_fiber_cable', 
                     'has_virtual_link', 'unnecessary_virtual']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(aerial_terminal_analysis)

print(f"\n✅ Saved {len(aerial_terminal_analysis)} Aerial Terminal records to aerial_terminal_fiber_check.csv")

# Generate FDH breakdown
fdh_summary = []
for fdh_id, data in sorted(fdh_breakdown.items()):
    total = data['total_terminals']
    connected = data['connected_to_fiber']
    missing = data['missing_cable']
    percentage = (connected / total * 100) if total > 0 else 0
    fdh_summary.append({
        'fdh_id': fdh_id,
        'total_terminals': total,
        'connected_to_fiber': connected,
        'missing_cable': missing,
        'percentage_connected': round(percentage, 2)
    })

# Save FDH breakdown
with open('aerial_terminal_fdh_breakdown.csv', 'w', encoding='utf-8', newline='') as f:
    if fdh_summary:
        fieldnames = ['fdh_id', 'total_terminals', 'connected_to_fiber', 
                     'missing_cable', 'percentage_connected']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(fdh_summary)

print(f"✅ Saved FDH breakdown to aerial_terminal_fdh_breakdown.csv")

# Save summary statistics
summary = {
    'total_aerial_terminals': stats['total_aerial'],
    'with_fdh_id': stats['with_fdh_id'],
    'with_cable_id': stats['with_cable_id'],
    'has_fiber_cable': stats['has_fiber_cable'],
    'missing_fiber_cable': stats['missing_fiber_cable'],
    'has_fiber_cable_percentage': round((stats['has_fiber_cable'] / stats['total_aerial'] * 100) if stats['total_aerial'] > 0 else 0, 2),
    'missing_fiber_cable_percentage': round((stats['missing_fiber_cable'] / stats['total_aerial'] * 100) if stats['total_aerial'] > 0 else 0, 2),
    'has_virtual_link': stats['has_virtual_link'],
    'unnecessary_virtual': stats['unnecessary_virtual'],
    'unnecessary_virtual_percentage': round((stats['unnecessary_virtual'] / stats['has_virtual_link'] * 100) if stats['has_virtual_link'] > 0 else 0, 2),
    'fdh_count': len(fdh_breakdown)
}

with open('aerial_terminal_fiber_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)

print(f"✅ Saved summary to aerial_terminal_fiber_summary.json")

# Print summary
print("\n" + "=" * 80)
print("AERIAL TERMINAL FIBER CABLE CONNECTIVITY ANALYSIS")
print("=" * 80)
print(f"\n📊 OVERALL STATISTICS:")
print(f"   Total Aerial Terminals: {stats['total_aerial']:,}")
print(f"   With FDH_ID: {stats['with_fdh_id']:,}")
print(f"   With cable_id property: {stats['with_cable_id']:,}")
print(f"\n   ✓ Found matching fiber cable: {stats['has_fiber_cable']:,} ({summary['has_fiber_cable_percentage']:.1f}%)")
print(f"   ✗ Missing fiber cable: {stats['missing_fiber_cable']:,} ({summary['missing_fiber_cable_percentage']:.1f}%)")
print(f"\n🔄 VIRTUAL LINK ANALYSIS:")
print(f"   Has virtual fiber link: {stats['has_virtual_link']:,}")
print(f"   Unnecessary virtual links (cable exists): {stats['unnecessary_virtual']:,} ({summary['unnecessary_virtual_percentage']:.1f}%)")
print(f"   → These can be safely removed from the graph")
print(f"\n📈 FDH BREAKDOWN:")
print(f"   Unique FDHs with Aerial Terminals: {len(fdh_breakdown):,}")
print(f"   Detailed breakdown saved to: aerial_terminal_fdh_breakdown.csv")
print("\n" + "=" * 80)







