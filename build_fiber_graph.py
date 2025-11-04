# build_fiber_graph.py
# --------------------------------------------------------------------------
# Fiber Network Logical Graph Generator (Enhanced)
# --------------------------------------------------------------------------
# Goal:
# Build a complete ONT → OLT logical graph across all relevant layers
# (ONT, Terminal, FOSC, FDH, OLT, Drop Cable, Stub Cable, Fiber Cable)
#
# Outputs:
#   1. logical_fiber_graph.json : node-link representation
#   2. olt_ont_paths.json       : per-ONT full connection path
#   3. summary_metrics.json     : aggregated statistics
#
# Key Improvements:
#   - Includes drop cable layer directly
#   - Multi-segment (no early break)
#   - ID-based mapping (From_ID, To_ID, FDH_ID, OLT_ID, etc.)
#   - Retains all cable IDs and lengths
#   - Case-insensitive property matching
# --------------------------------------------------------------------------

import json
from collections import defaultdict


# Define length field mappings for each cable type
LENGTH_FIELDS = {
    "drop cable": ["length"],
    "stub cable": ["measlength", "length"],
    "fiber cable": ["calclength", "measlength", "length"]
}


# Utility -----------------------------------------------------------------
def load_geojson(path):
    """Load GeoJSON file and normalize property names to lowercase."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    return [{k.lower(): v for k, v in f.get("properties", {}).items()} for f in features]


def get_length(props, layer):
    """Extract length value from properties for given cable layer."""
    for field in LENGTH_FIELDS.get(layer, []):
        if field in props and props[field] not in (None, "", "null"):
            try:
                return float(props[field])
            except (ValueError, TypeError):
                pass
    return None


def get_field_value(props, *field_names):
    """Get field value with case-insensitive matching and multiple name variants."""
    for name in field_names:
        # Try exact match (lowercase)
        if name in props:
            val = props[name]
            if val not in (None, "", "null"):
                return val
        # Try variations
        for key in props:
            if key.lower() == name.lower():
                val = props[key]
                if val not in (None, "", "null"):
                    return val
    return None


def find_matching_cables(cable_list, source_id, target_id=None):
    """Find all cables that connect to source_id, optionally to target_id."""
    matches = []
    for cable in cable_list:
        from_id = get_field_value(cable, "from_id", "fromid", "from")
        to_id = get_field_value(cable, "to_id", "toid", "to")
        
        # Match if cable connects to source_id
        if from_id == source_id or to_id == source_id:
            # If target specified, verify it matches
            if target_id is None or from_id == target_id or to_id == target_id:
                matches.append(cable)
    return matches


# Load layers -------------------------------------------------------------
print("Loading GeoJSON layers...")

ont = load_geojson("ONT.geojson")
terminal = load_geojson("terminal.geojson")
fosc = load_geojson("splice closure.geojson")
fdh = load_geojson("fdh.geojson")
olt = load_geojson("OLT.geojson")
drop_cable = load_geojson("drop cable.geojson")
stub_cable = load_geojson("stub cable.geojson")
fiber_cable = load_geojson("fiber cable.geojson")

# Build ID index for quick lookup
def build_index(layer_data, *id_fields):
    """Build index from layer data using multiple possible ID field names."""
    idx = {}
    for r in layer_data:
        for field in id_fields:
            rid = get_field_value(r, field, f"{field}_id")
            if rid:
                idx[rid] = r
                break
    return idx


indexes = {
    "ont": build_index(ont, "id", "ont_id"),
    "terminal": build_index(terminal, "id", "terminal_id", "termnal_id"),
    "fosc": build_index(fosc, "id", "fosc_id"),
    "fdh": build_index(fdh, "id", "fdh_id"),
    "olt": build_index(olt, "id", "olt_id")
}


# Graph building ----------------------------------------------------------
print("Building universal adjacency map...")

# Maximum hops to prevent infinite loops
MAX_HOPS = 100  # Increased for comprehensive exploration

def get_node_layer(node_id):
    """Determine the layer type of a node ID."""
    if node_id in indexes["ont"]:
        return "ont"
    elif node_id in indexes["terminal"]:
        return "terminal"
    elif node_id in indexes["fosc"]:
        return "splice closure"
    elif node_id in indexes["fdh"]:
        return "fdh"
    elif node_id in indexes["olt"]:
        return "olt"
    return None

# Build universal adjacency map from all cable types
# Structure: {node_id: [(neighbor_id, cable_id, cable_layer, length_m), ...]}
adjacency_map = defaultdict(list)

print("  Processing drop cables...")
for drop in drop_cable:
    from_id = get_field_value(drop, "from_id", "fromid", "from")
    to_id = get_field_value(drop, "to_id", "toid", "to")
    cable_id = get_field_value(drop, "id", "cable_id")
    length_m = get_length(drop, "drop cable")
    
    if from_id and to_id:
        adjacency_map[from_id].append((to_id, cable_id, "drop cable", length_m))
        adjacency_map[to_id].append((from_id, cable_id, "drop cable", length_m))

print("  Processing stub cables...")
for stub in stub_cable:
    from_id = get_field_value(stub, "from_id", "fromid", "from")
    to_id = get_field_value(stub, "to_id", "toid", "to")
    cable_id = get_field_value(stub, "id", "cable_id")
    length_m = get_length(stub, "stub cable")
    
    if from_id and to_id:
        adjacency_map[from_id].append((to_id, cable_id, "stub cable", length_m))
        adjacency_map[to_id].append((from_id, cable_id, "stub cable", length_m))

print("  Processing fiber cables...")
for fiber in fiber_cable:
    from_id = get_field_value(fiber, "from_id", "fromid", "from")
    to_id = get_field_value(fiber, "to_id", "toid", "to")
    cable_id = get_field_value(fiber, "id", "cable_id")
    length_m = get_length(fiber, "fiber cable")
    
    if from_id and to_id:
        adjacency_map[from_id].append((to_id, cable_id, "fiber cable", length_m))
        adjacency_map[to_id].append((from_id, cable_id, "fiber cable", length_m))

print(f"  Built adjacency map with {len(adjacency_map)} nodes and {sum(len(neighbors) for neighbors in adjacency_map.values())} connections")

# BFS traversal function with enhanced edge-case handling
def bfs_traverse_to_olt(start_node, start_layer, target_olt_id=None, visited_nodes=None, diagnostics=None):
    """
    Enhanced BFS traversal from start_node to find path to OLT.
    Handles virtual connections and edge cases.
    Returns: (path_segments, final_node, final_layer, hop_count, length_summary)
    """
    if diagnostics is None:
        diagnostics = defaultdict(int)
    
    if visited_nodes is None:
        visited_nodes = set()
    
    visited = visited_nodes.copy()
    visited.add(start_node)
    queue = [(start_node, start_layer, [], defaultdict(float), 0)]  # (node, layer, path, length_summary, hops)
    best_path = None
    best_length = None
    best_layer = None
    
    while queue:
        current_node, current_layer, path_so_far, length_so_far, hops = queue.pop(0)
        
        if hops >= MAX_HOPS:
            # Save as best path if it's better than current best
            if best_path is None or len(path_so_far) > len(best_path):
                best_path = path_so_far
                best_length = length_so_far
                best_layer = current_layer
            continue
        
        # OLT: always terminate
        if current_layer == "olt":
            return path_so_far, current_node, current_layer, hops, length_so_far
        
        # Save path if it's to FDH (better than terminal/ont/fosc)
        if current_layer == "fdh":
            if best_path is None or best_layer != "fdh" or len(path_so_far) >= len(best_path):
                best_path = path_so_far
                best_length = length_so_far.copy()
                best_layer = "fdh"
        
        # Explore neighbors from adjacency map
        if current_node in adjacency_map:
            for neighbor_id, cable_id, cable_layer, length_m in adjacency_map[current_node]:
                if neighbor_id in visited:
                    continue
                
                neighbor_layer = get_node_layer(neighbor_id)
                if not neighbor_layer:
                    continue
                
                # Build new path segment
                new_segment = {
                    "from": current_node,
                    "to": neighbor_id,
                    "from_layer": current_layer,
                    "to_layer": neighbor_layer,
                    "cable_id": cable_id,
                    "cable_layer": cable_layer,
                    "length_m": length_m,
                    "virtual": False
                }
                
                new_path = path_so_far + [new_segment]
                new_length = length_so_far.copy()
                if length_m:
                    new_length[cable_layer] += length_m
                
                visited.add(neighbor_id)
                
                # If we found an OLT, return immediately
                if neighbor_layer == "olt":
                    return new_path, neighbor_id, neighbor_layer, hops + 1, new_length
                
                # Otherwise, add to queue
                queue.append((neighbor_id, neighbor_layer, new_path, new_length, hops + 1))
        
        # Handle edge cases based on node type
        # FDH: Check for direct OLT link or continue via Fiber Cable
        if current_layer == "fdh" and current_node in indexes["fdh"]:
            fdh_rec = indexes["fdh"][current_node]
            olt_id = get_field_value(fdh_rec, "olt_id", "oltid") or target_olt_id
            
            if olt_id and olt_id not in visited:
                if olt_id in indexes["olt"]:
                    # Direct FDH → OLT link
                    logical_segment = {
                        "from": current_node,
                        "to": olt_id,
                        "from_layer": "fdh",
                        "to_layer": "olt",
                        "cable_id": None,
                        "cable_layer": None,
                        "length_m": None,
                        "virtual": False
                    }
                    final_path = path_so_far + [logical_segment]
                    return final_path, olt_id, "olt", hops + 1, length_so_far
        
        # FOSC: Check if it's referenced by any Fiber Cable (even if not in adjacency)
        if current_layer == "splice closure" and current_node in indexes["fosc"]:
            fosc_rec = indexes["fosc"][current_node]
            # Try to get FDH from FOSC record
            fdh_id = get_field_value(fosc_rec, "fdh_id", "fdhid")
            if fdh_id and fdh_id not in visited and fdh_id in indexes["fdh"]:
                # Add virtual FOSC → FDH link
                virtual_segment = {
                    "from": current_node,
                    "to": fdh_id,
                    "from_layer": "splice closure",
                    "to_layer": "fdh",
                    "cable_id": None,
                    "cable_layer": "fiber cable",
                    "length_m": None,
                    "virtual": True
                }
                diagnostics["edge_fosc_virtual_links"] += 1
                virtual_path = path_so_far + [virtual_segment]
                # Continue from FDH
                fdh_path, final_node, final_layer, fdh_hops, fdh_length = bfs_traverse_to_olt(
                    fdh_id, "fdh", target_olt_id, visited.copy(), diagnostics
                )
                if final_layer == "olt":
                    return virtual_path + fdh_path, final_node, final_layer, hops + fdh_hops + 1, length_so_far
        
        # Terminal: Enhanced continuation logic
        if current_layer == "terminal" and current_node in indexes["terminal"]:
            term_rec = indexes["terminal"][current_node]
            terminal_type = get_field_value(term_rec, "type", "terminal_type")
            
            # Check if terminal has direct FDH reference (can skip FOSC)
            fdh_id = get_field_value(term_rec, "fdh_id", "fdhid")
            if fdh_id and fdh_id not in visited and fdh_id in indexes["fdh"]:
                # Add virtual Terminal → FDH link (via fiber, skipping FOSC)
                virtual_segment = {
                    "from": current_node,
                    "to": fdh_id,
                    "from_layer": "terminal",
                    "to_layer": "fdh",
                    "cable_id": None,
                    "cable_layer": "fiber cable",
                    "length_m": None,
                    "virtual": True
                }
                diagnostics["terminal_virtual_fiber_links"] += 1
                virtual_path = path_so_far + [virtual_segment]
                # Continue from FDH
                fdh_path, final_node, final_layer, fdh_hops, fdh_length = bfs_traverse_to_olt(
                    fdh_id, "fdh", target_olt_id, visited.copy(), diagnostics
                )
                if final_layer == "olt":
                    return virtual_path + fdh_path, final_node, final_layer, hops + fdh_hops + 1, length_so_far
            
            # Try to continue via Fiber Cable if no Stub Cable found
            has_stub_to_fosc = False
            if current_node in adjacency_map:
                has_stub_to_fosc = any(
                    get_node_layer(n) == "splice closure" 
                    for n, _, _, _ in adjacency_map[current_node]
                )
            
            if not has_stub_to_fosc:
                # Check if terminal has FOSC reference
                fosc_id = get_field_value(term_rec, "fosc_id", "foscid")
                if fosc_id and fosc_id not in visited and fosc_id in indexes["fosc"]:
                    # Add virtual Terminal → FOSC link
                    virtual_segment = {
                        "from": current_node,
                        "to": fosc_id,
                        "from_layer": "terminal",
                        "to_layer": "splice closure",
                        "cable_id": None,
                        "cable_layer": "stub cable",
                        "length_m": None,
                        "virtual": True
                    }
                    diagnostics["terminal_virtual_stub_links"] += 1
                    virtual_path = path_so_far + [virtual_segment]
                    # Continue from FOSC
                    fosc_path, final_node, final_layer, fosc_hops, fosc_length = bfs_traverse_to_olt(
                        fosc_id, "splice closure", target_olt_id, visited.copy(), diagnostics
                    )
                    if final_layer == "olt":
                        return virtual_path + fosc_path, final_node, final_layer, hops + fosc_hops + 1, length_so_far
    
    # Return best path found if no OLT reached
    if best_path:
        final_node, final_layer = best_path[-1]["to"], best_path[-1]["to_layer"]
        return best_path, final_node, final_layer, len(best_path), best_length
    
    return [], start_node, start_layer, 0, defaultdict(float)

links = []
paths = []
unreachable_nodes = set()
diagnostics = defaultdict(int)

print("Building ONT → OLT paths with enhanced BFS traversal...")

for ont_rec in ont:
    ont_id = get_field_value(ont_rec, "id", "ont_id")
    if not ont_id:
        continue
    
    target_olt_id = get_field_value(ont_rec, "olt_id", "oltid")
    terminal_id = get_field_value(ont_rec, "terminal_id", "termnal_id")
    path_segments = []
    length_summary = defaultdict(float)
    hop_count = 0
    final_node_type = "ont"
    
    # Try to find starting point: ONT itself or referenced Terminal
    start_node = None
    start_layer = None
    virtual_drop_added = False
    
    # Check if ONT has direct connections
    if ont_id in adjacency_map:
        start_node = ont_id
        start_layer = "ont"
    elif terminal_id:
        # ONT has Terminal_ID but no drop cable - create virtual connection
        if terminal_id in adjacency_map or terminal_id in indexes["terminal"]:
            start_node = terminal_id
            start_layer = "terminal"
            # Add virtual drop cable link from ONT to Terminal
            path_segments.append({
                "from": ont_id,
                "to": terminal_id,
                "from_layer": "ont",
                "to_layer": "terminal",
                "cable_id": None,
                "cable_layer": "drop cable",
                "length_m": None,
                "virtual": True
            })
            virtual_drop_added = True
            diagnostics["onts_rescued_via_virtual_drop"] += 1
        else:
            # Terminal not found - truly unreachable
            unreachable_nodes.add(ont_id)
            paths.append({
                "ont_id": ont_id,
                "olt_id": target_olt_id,
                "path": [],
                "cable_length_summary": {},
                "total_length_m": 0,
                "hop_count": 0,
                "final_node_type": "ont",
                "complete": False
            })
            continue
    else:
        # No terminal reference and no connections - unreachable
        unreachable_nodes.add(ont_id)
        paths.append({
            "ont_id": ont_id,
            "olt_id": target_olt_id,
            "path": [],
            "cable_length_summary": {},
            "total_length_m": 0,
            "hop_count": 0,
            "final_node_type": "ont",
            "complete": False
        })
        continue
    
    # Use enhanced BFS to find path to OLT from starting node
    bfs_segments, final_node, final_layer, bfs_hops, bfs_length = bfs_traverse_to_olt(
        start_node, start_layer, target_olt_id, None, diagnostics
    )
    
    # Combine initial segment with BFS path
    path_segments.extend(bfs_segments)
    hop_count = len(path_segments)
    
    # Merge length summaries
    for cable_type, length in bfs_length.items():
        length_summary[cable_type] += length
    
    final_node_type = final_layer
    
    # Build node-link pairs for graph
    for seg in path_segments:
        link = {
            "source": seg["from"],
            "source_layer": seg["from_layer"],
            "target": seg["to"],
            "target_layer": seg["to_layer"],
            "cable_id": seg["cable_id"],
            "cable_layer": seg["cable_layer"],
            "length_m": seg["length_m"]
        }
        if "virtual" in seg:
            link["virtual"] = seg["virtual"]
        links.append(link)
    
    total_length = sum(v for v in length_summary.values() if v) if length_summary else 0
    
    # Determine if path is complete (reached OLT)
    is_complete = final_layer == "olt"
    
    paths.append({
        "ont_id": ont_id,
        "olt_id": target_olt_id,
        "path": path_segments,
        "cable_length_summary": dict(length_summary),
        "total_length_m": total_length,
        "hop_count": hop_count,
        "final_node_type": final_layer,
        "complete": is_complete
    })


# Build node list
nodes = {}
for l in links:
    nodes[l["source"]] = l["source_layer"]
    nodes[l["target"]] = l["target_layer"]
node_list = [{"id": nid, "layer": lyr} for nid, lyr in nodes.items()]


# Calculate summary metrics -----------------------------------------------
print("Calculating summary metrics...")

# Average total cable length per ONT
ont_lengths = [p["total_length_m"] for p in paths if p["total_length_m"] > 0]
avg_length = sum(ont_lengths) / len(ont_lengths) if ont_lengths else 0

# Max chain length
max_length = max(ont_lengths) if ont_lengths else 0

# Completion statistics
complete_paths = [p for p in paths if p.get("complete", False)]
complete_percentage = (len(complete_paths) / len(paths) * 100) if paths else 0

# Paths ending at different node types
paths_ending_at_fdh = [p for p in paths if p.get("final_node_type") == "fdh" and not p.get("complete")]
paths_ending_at_fosc = [p for p in paths if p.get("final_node_type") == "splice closure"]
paths_ending_at_terminal = [p for p in paths if p.get("final_node_type") == "terminal"]
paths_ending_at_ont = [p for p in paths if p.get("final_node_type") == "ont"]

fdh_percentage = (len(paths_ending_at_fdh) / len(paths) * 100) if paths else 0
fosc_percentage = (len(paths_ending_at_fosc) / len(paths) * 100) if paths else 0

# Count virtual connections in paths
virtual_connections_count = 0
virtual_drop_count = 0
virtual_stub_count = 0
virtual_fiber_count = 0

for path in paths:
    for seg in path.get("path", []):
        if seg.get("virtual", False):
            virtual_connections_count += 1
            if seg.get("cable_layer") == "drop cable":
                virtual_drop_count += 1
            elif seg.get("cable_layer") == "stub cable":
                virtual_stub_count += 1
            elif seg.get("cable_layer") == "fiber cable":
                virtual_fiber_count += 1

# Average hop count
hop_counts = [p.get("hop_count", 0) for p in paths]
avg_hop_count = sum(hop_counts) / len(hop_counts) if hop_counts else 0
max_hop_count = max(hop_counts) if hop_counts else 0

# Count FOSC per OLT and per FDH
fosc_per_olt = defaultdict(int)
fosc_per_fdh = defaultdict(int)

# FOSC-to-FOSC hop frequency
fosc_to_fosc_hops = defaultdict(int)  # Count of FOSC→FOSC transitions

for path in paths:
    olt_id = path.get("olt_id")
    if olt_id:
        # Count unique FOSCs in this path
        foscs_in_path = set()
        fdh_in_path = None
        
        prev_layer = None
        for seg in path["path"]:
            # Track FOSC-to-FOSC hops
            if prev_layer == "splice closure" and seg["to_layer"] == "splice closure":
                fosc_to_fosc_hops[(seg["from"], seg["to"])] += 1
            
            if seg["to_layer"] == "splice closure":
                foscs_in_path.add(seg["to"])
            elif seg["to_layer"] == "fdh":
                fdh_in_path = seg["to"]
            
            prev_layer = seg["to_layer"]
        
        for fosc_id in foscs_in_path:
            fosc_per_olt[olt_id] += 1
            if fdh_in_path:
                fosc_per_fdh[fdh_in_path] += 1

# Count total FOSC-to-FOSC hops (not unique pairs)
total_fosc_to_fosc_hops = sum(fosc_to_fosc_hops.values())

# Final node type distribution
final_node_types = defaultdict(int)
for path in paths:
    final_type = path.get("final_node_type", "unknown")
    final_node_types[final_type] += 1

summary_metrics = {
    "average_total_cable_length_per_ont_m": round(avg_length, 2),
    "max_chain_length_m": round(max_length, 2),
    "total_onts_processed": len(paths),
    "complete_paths": len(complete_paths),
    "complete_paths_percentage": round(complete_percentage, 2),
    "paths_ending_at_fdh": len(paths_ending_at_fdh),
    "paths_ending_at_fdh_percentage": round(fdh_percentage, 2),
    "paths_ending_at_fosc": len(paths_ending_at_fosc),
    "paths_ending_at_fosc_percentage": round(fosc_percentage, 2),
    "paths_ending_at_terminal": len(paths_ending_at_terminal),
    "paths_ending_at_ont": len(paths_ending_at_ont),
    "unreachable_nodes_count": len(unreachable_nodes),
    "average_hop_count": round(avg_hop_count, 2),
    "max_hop_count": max_hop_count,
    "total_fosc_to_fosc_hops": total_fosc_to_fosc_hops,
    "unique_fosc_to_fosc_pairs": len(fosc_to_fosc_hops),
    "fosc_count_per_olt": dict(fosc_per_olt),
    "fosc_count_per_fdh": dict(fosc_per_fdh),
    "final_node_type_distribution": dict(final_node_types),
    "virtual_connections_total": virtual_connections_count,
    "virtual_drop_cables": virtual_drop_count,
    "virtual_stub_cables": virtual_stub_count,
    "virtual_fiber_cables": virtual_fiber_count
}

# Create diagnostics refinement report
diagnostics_refinement = {
    "onts_rescued_via_virtual_drop": diagnostics.get("onts_rescued_via_virtual_drop", 0),
    "terminal_virtual_stub_links": diagnostics.get("terminal_virtual_stub_links", 0),
    "edge_fosc_virtual_links": diagnostics.get("edge_fosc_virtual_links", 0),
    "total_virtual_connections": virtual_connections_count,
    "virtual_breakdown": {
        "drop_cable": virtual_drop_count,
        "stub_cable": virtual_stub_count,
        "fiber_cable": virtual_fiber_count
    },
    "paths_with_virtual_connections": len([p for p in paths if any(
        seg.get("virtual", False) for seg in p.get("path", [])
    )])
}


# Save outputs ------------------------------------------------------------
print("Saving outputs...")

with open("logical_fiber_graph.json", "w", encoding="utf-8") as f:
    json.dump({"nodes": node_list, "links": links}, f, indent=2)

with open("olt_ont_paths.json", "w", encoding="utf-8") as f:
    json.dump(paths, f, indent=2)

with open("summary_metrics.json", "w", encoding="utf-8") as f:
    json.dump(summary_metrics, f, indent=2)

# Save unreachable nodes
unreachable_nodes_list = sorted(list(unreachable_nodes))
with open("unreachable_nodes.json", "w", encoding="utf-8") as f:
    json.dump({"unreachable_nodes": unreachable_nodes_list, "count": len(unreachable_nodes_list)}, f, indent=2)

# Save diagnostics refinement
with open("diagnostics_refinement.json", "w", encoding="utf-8") as f:
    json.dump(diagnostics_refinement, f, indent=2)

print("✅ Done! Files saved:")
print("   - logical_fiber_graph.json")
print("   - olt_ont_paths.json")
print("   - summary_metrics.json")
print("   - unreachable_nodes.json")
print("   - diagnostics_refinement.json")

