#!/usr/bin/env python3
"""
Analyze Virtual Fiber Cables
Identifies all virtual fiber connections and their characteristics.
"""

import json
import csv
from collections import defaultdict

# Load data
print("Loading data...")
with open('olt_ont_paths.json', 'r') as f:
    paths = json.load(f)

with open('splice closure.geojson', 'r') as f:
    fosc_data = json.load(f)

# Load terminal data to get terminal types
with open('terminal.geojson', 'r') as f:
    terminal_data = json.load(f)

# Build terminal type index
terminal_types = {}
terminal_records = {}
for feat in terminal_data['features']:
    props = {k.lower(): v for k, v in feat.get('properties', {}).items()}
    term_id = props.get('id') or props.get('terminal_id') or props.get('termnal_id')
    if term_id:
        # Try multiple possible field names for terminal type
        term_type = (props.get('type') or 
                    props.get('terminal_type') or 
                    props.get('termtype') or
                    props.get('terminaltype') or
                    'Unknown')
        terminal_types[term_id] = term_type
        terminal_records[term_id] = props

print(f"Loaded {len(terminal_types)} terminal records")

# Build FOSC category index
fosc_categories = {}
fosc_records = {}
for feat in fosc_data['features']:
    props = {k.lower(): v for k, v in feat.get('properties', {}).items()}
    fosc_id = props.get('id') or props.get('fosc_id')
    if fosc_id:
        category = (props.get('fosccate') or 
                   props.get('fosc_cate') or 
                   props.get('splice_category') or 
                   props.get('category') or 
                   'Unknown')
        fosc_categories[fosc_id] = category
        fosc_records[fosc_id] = props

print(f"Loaded {len(fosc_categories)} FOSC records")

# Collect all virtual fiber cables
virtual_fibers = []
connection_types = defaultdict(int)
terminal_type_connections = defaultdict(int)  # Track terminal type connections
fosc_type_combinations = defaultdict(int)
partial_splice_count = 0

for path in paths:
    for seg in path.get('path', []):
        if seg.get('virtual', False) and seg.get('cable_layer') == 'fiber cable':
            source_id = seg['from']
            target_id = seg['to']
            source_type = seg['from_layer']
            target_type = seg['to_layer']
            
            # Get FOSC categories
            source_fosc_type = fosc_categories.get(source_id, None) if source_type == 'splice closure' else None
            target_fosc_type = fosc_categories.get(target_id, None) if target_type == 'splice closure' else None
            
            # Get trunk_id (try from source if it's a FOSC)
            trunk_id = None
            if source_id in fosc_records:
                trunk_id = fosc_records[source_id].get('trunk_id') or fosc_records[source_id].get('trunkid')
            
            # Get terminal type if source is a terminal
            source_terminal_type = terminal_types.get(source_id, '') if source_type == 'terminal' else ''
            target_terminal_type = terminal_types.get(target_id, '') if target_type == 'terminal' else ''
            
            # Check if involves partial splice
            involves_partial = False
            if source_fosc_type and 'partial' in str(source_fosc_type).lower():
                involves_partial = True
            if target_fosc_type and 'partial' in str(target_fosc_type).lower():
                involves_partial = True
            
            if involves_partial:
                partial_splice_count += 1
            
            # Record connection type
            conn_type = f"{source_type} → {target_type}"
            connection_types[conn_type] += 1
            
            # Record terminal type connections
            if source_type == 'terminal' and source_terminal_type:
                terminal_type_connections[source_terminal_type] += 1
            if target_type == 'terminal' and target_terminal_type:
                terminal_type_connections[f"target_{target_terminal_type}"] += 1
            
            # Record FOSC type combinations
            if source_type == 'splice closure' and target_type == 'splice closure':
                combo_key = f"{source_fosc_type or 'Unknown'} → {target_fosc_type or 'Unknown'}"
                fosc_type_combinations[combo_key] += 1
            
            virtual_fibers.append({
                'source_id': source_id,
                'source_type': source_type,
                'source_terminal_type': source_terminal_type,
                'target_id': target_id,
                'target_type': target_type,
                'target_terminal_type': target_terminal_type,
                'source_fosc_type': source_fosc_type or '',
                'target_fosc_type': target_fosc_type or '',
                'trunk_id': trunk_id or '',
                'length_m': seg.get('length_m') or ''
            })

print(f"\nFound {len(virtual_fibers)} virtual fiber cables")

# Save detailed table as JSON
with open('virtual_fiber_analysis.json', 'w', encoding='utf-8') as f:
    json.dump({
        'virtual_fibers': virtual_fibers,
        'summary': {
            'total_virtual_fibers': len(virtual_fibers),
            'connection_types': dict(connection_types),
            'terminal_type_connections': dict(terminal_type_connections),
            'fosc_type_combinations': dict(fosc_type_combinations),
            'involving_partial_splice': partial_splice_count,
            'percentage_partial': round((partial_splice_count / len(virtual_fibers) * 100) if virtual_fibers else 0, 2)
        }
    }, f, indent=2)

# Save as CSV
with open('virtual_fiber_analysis.csv', 'w', encoding='utf-8', newline='') as f:
    if virtual_fibers:
        writer = csv.DictWriter(f, fieldnames=virtual_fibers[0].keys())
        writer.writeheader()
        writer.writerows(virtual_fibers)

print(f"\n✅ Analysis complete!")
print(f"   - virtual_fiber_analysis.json")
print(f"   - virtual_fiber_analysis.csv")

