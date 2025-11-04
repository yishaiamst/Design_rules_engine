# build_fiber_graph_refined.py
# --------------------------------------------------------------------------
# Refined Fiber Network Logical Graph Generator
# --------------------------------------------------------------------------
# Enhanced connectivity rules based on analysis:
#   - Aerial Terminals use cable_id to connect via fiber cables
#   - MST Terminals use physical stub cables
#   - Minimized virtual links (target: <50)
#   - Proper layer classification (stub vs fiber)
# --------------------------------------------------------------------------

import json
from collections import defaultdict

print("=" * 80)
print("REFINED FIBER NETWORK GRAPH BUILDER")
print("=" * 80)

# Define length field mappings for each cable type
LENGTH_FIELDS = {
    "drop cable": ["length"],
    "stub cable": ["measlength", "length"],
    "fiber cable": ["calclength", "measlength", "length"]
}

# Maximum hops to prevent infinite loops
MAX_HOPS = 100

# Utility functions
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
        if name in props:
            val = props[name]
            if val not in (None, "", "null"):
                return val
        for key in props:
            if key.lower() == name.lower():
                val = props[key]
                if val not in (None, "", "null"):
                    return val
    return None

def get_node_layer(node_id, indexes):
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

# Load layers
print("\nLoading GeoJSON layers...")
ont = load_geojson("ONT.geojson")
terminal = load_geojson("terminal.geojson")
fosc = load_geojson("splice closure.geojson")
fdh = load_geojson("fdh.geojson")
olt = load_geojson("OLT.geojson")
drop_cable = load_geojson("drop cable.geojson")
stub_cable = load_geojson("stub cable.geojson")
fiber_cable = load_geojson("fiber cable.geojson")

# Build indexes
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

# Build fiber cable ID index for Aerial Terminal matching
fiber_cable_ids = {}
for cable in fiber_cable:
    cable_id = get_field_value(cable, "id", "cable_id")
    if cable_id:
        fiber_cable_ids[cable_id] = cable

print(f"Indexed {len(fiber_cable_ids)} fiber cable IDs")

# Build adjacency map from all cable types
print("\nBuilding universal adjacency map...")
adjacency_map = defaultdict(list)

# Drop cables
print("  Processing drop cables...")
for drop in drop_cable:
    from_id = get_field_value(drop, "from_id", "fromid", "from")
    to_id = get_field_value(drop, "to_id", "toid", "to")
    cable_id = get_field_value(drop, "id", "cable_id")
    length_m = get_length(drop, "drop cable")
    
    if from_id and to_id:
        adjacency_map[from_id].append((to_id, cable_id, "drop cable", length_m, False))
        adjacency_map[to_id].append((from_id, cable_id, "drop cable", length_m, False))

# Stub cables
print("  Processing stub cables...")
for stub in stub_cable:
    from_id = get_field_value(stub, "from_id", "fromid", "from")
    to_id = get_field_value(stub, "to_id", "toid", "to")
    cable_id = get_field_value(stub, "id", "cable_id")
    length_m = get_length(stub, "stub cable")
    
    if from_id and to_id:
        adjacency_map[from_id].append((to_id, cable_id, "stub cable", length_m, False))
        adjacency_map[to_id].append((from_id, cable_id, "stub cable", length_m, False))

# Fiber cables
print("  Processing fiber cables...")
for fiber in fiber_cable:
    from_id = get_field_value(fiber, "from_id", "fromid", "from")
    to_id = get_field_value(fiber, "to_id", "toid", "to")
    cable_id = get_field_value(fiber, "id", "cable_id")
    length_m = get_length(fiber, "fiber cable")
    
    if from_id and to_id:
        adjacency_map[from_id].append((to_id, cable_id, "fiber cable", length_m, False))
        adjacency_map[to_id].append((from_id, cable_id, "fiber cable", length_m, False))

# Add Aerial Terminal connections via cable_id
print("  Processing Aerial Terminal fiber cable associations...")
aerial_terminal_connections = 0
for term_rec in terminal:
    terminal_id = get_field_value(term_rec, "id", "terminal_id", "termnal_id")
    terminal_type = get_field_value(term_rec, "type", "terminal_type") or ""
    cable_id = get_field_value(term_rec, "cable_id", "cableid")
    
    # Aerial terminals connect via cable_id to fiber cables
    if "aerial" in terminal_type.lower() and cable_id and cable_id in fiber_cable_ids:
        fiber_cable_rec = fiber_cable_ids[cable_id]
        fiber_from_id = get_field_value(fiber_cable_rec, "from_id", "fromid", "from")
        fiber_to_id = get_field_value(fiber_cable_rec, "to_id", "toid", "to")
        length_m = get_length(fiber_cable_rec, "fiber cable")
        
        # Connect terminal to both ends of the fiber cable
        if fiber_from_id:
            adjacency_map[terminal_id].append((fiber_from_id, cable_id, "fiber cable", length_m, False))
            adjacency_map[fiber_from_id].append((terminal_id, cable_id, "fiber cable", length_m, False))
            aerial_terminal_connections += 1
        if fiber_to_id:
            adjacency_map[terminal_id].append((fiber_to_id, cable_id, "fiber cable", length_m, False))
            adjacency_map[fiber_to_id].append((terminal_id, cable_id, "fiber cable", length_m, False))
            aerial_terminal_connections += 1

print(f"  Added {aerial_terminal_connections} Aerial Terminal ↔ Fiber Cable connections")
print(f"  Built adjacency map with {len(adjacency_map)} nodes")

# Enhanced BFS traversal with refined rules
def bfs_traverse_to_olt(start_node, start_layer, target_olt_id=None, visited_nodes=None, diagnostics=None):
    """
    Enhanced BFS traversal with refined connectivity rules.
    Returns: (path_segments, final_node, final_layer, hop_count, length_summary)
    """
    if diagnostics is None:
        diagnostics = defaultdict(int)
    
    if visited_nodes is None:
        visited_nodes = set()
    
    visited = visited_nodes.copy()
    visited.add(start_node)
    queue = [(start_node, start_layer, [], defaultdict(float), 0)]
    best_path = None
    best_length = None
    best_layer = None
    
    while queue:
        current_node, current_layer, path_so_far, length_so_far, hops = queue.pop(0)
        
        if hops >= MAX_HOPS:
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
            for neighbor_id, cable_id, cable_layer, length_m, is_virtual in adjacency_map[current_node]:
                if neighbor_id in visited:
                    continue
                
                neighbor_layer = get_node_layer(neighbor_id, indexes)
                if not neighbor_layer:
                    continue
                
                new_segment = {
                    "from": current_node,
                    "to": neighbor_id,
                    "from_layer": current_layer,
                    "to_layer": neighbor_layer,
                    "cable_id": cable_id,
                    "cable_layer": cable_layer,
                    "length_m": length_m,
                    "virtual": is_virtual
                }
                
                new_path = path_so_far + [new_segment]
                new_length = length_so_far.copy()
                if length_m:
                    new_length[cable_layer] += length_m
                
                visited.add(neighbor_id)
                
                if neighbor_layer == "olt":
                    return new_path, neighbor_id, neighbor_layer, hops + 1, new_length
                
                queue.append((neighbor_id, neighbor_layer, new_path, new_length, hops + 1))
        
        # Handle edge cases based on node type
        # FDH → OLT
        if current_layer == "fdh" and current_node in indexes["fdh"]:
            fdh_rec = indexes["fdh"][current_node]
            olt_id = get_field_value(fdh_rec, "olt_id", "oltid") or target_olt_id
            
            if olt_id and olt_id not in visited and olt_id in indexes["olt"]:
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
        
        # FOSC → FDH (only if no physical path exists and FDH is referenced)
        if current_layer == "splice closure" and current_node in indexes["fosc"]:
            fosc_rec = indexes["fosc"][current_node]
            fdh_id = get_field_value(fosc_rec, "fdh_id", "fdhid")
            
            # Only create virtual if no physical connection exists and we're stuck
            if fdh_id and fdh_id not in visited and fdh_id in indexes["fdh"]:
                # Check if there's already a physical connection in adjacency
                has_physical = any(
                    n == fdh_id for n, _, _, _, _ in adjacency_map.get(current_node, [])
                )
                
                # Only create virtual if no physical connection AND queue is empty (no other paths)
                if not has_physical and len(queue) == 0:
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
                    fdh_path, final_node, final_layer, fdh_hops, fdh_length = bfs_traverse_to_olt(
                        fdh_id, "fdh", target_olt_id, visited.copy(), diagnostics
                    )
                    if final_layer == "olt":
                        merged_length = length_so_far.copy()
                        return virtual_path + fdh_path, final_node, final_layer, hops + fdh_hops + 1, merged_length
    
    # Return best path found
    if best_path:
        final_node, final_layer = best_path[-1]["to"], best_path[-1]["to_layer"]
        return best_path, final_node, final_layer, len(best_path), best_length
    
    return [], start_node, start_layer, 0, defaultdict(float)

# Build graph
print("\nBuilding ONT → OLT paths with refined connectivity rules...")
links = []
paths = []
unreachable_nodes = set()
diagnostics = defaultdict(int)

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
    
    # Start point determination
    start_node = None
    start_layer = None
    
    # ONT → Terminal via Drop Cable
    if ont_id in adjacency_map:
        start_node = ont_id
        start_layer = "ont"
    elif terminal_id:
        # Create virtual drop cable if terminal referenced
        # Check both adjacency map and terminal index
        terminal_in_adjacency = terminal_id in adjacency_map
        terminal_in_index = terminal_id in indexes["terminal"]
        
        if terminal_in_adjacency or terminal_in_index:
            start_node = terminal_id
            start_layer = "terminal"
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
            diagnostics["onts_rescued_via_virtual_drop"] += 1
        else:
            # Terminal not found - mark as unreachable
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
    
    # Handle Terminal → FOSC/FDH connection based on terminal type
    # Aerial Terminals are already connected via cable_id in adjacency map
    # MST Terminals need stub cable connections
    if start_layer == "terminal" and start_node in indexes["terminal"]:
        term_rec = indexes["terminal"][start_node]
        terminal_type = get_field_value(term_rec, "type", "terminal_type") or ""
        
        # Check if already connected via stub cable (MST) or fiber cable (Aerial)
        has_stub = any(
            get_node_layer(n, indexes) == "splice closure"
            for n, _, _, _, _ in adjacency_map.get(start_node, [])
        )
        has_fiber = any(
            get_node_layer(n, indexes) in ("splice closure", "fdh")
            for n, _, _, _, _ in adjacency_map.get(start_node, [])
        )
        
        # If terminal is already connected, skip manual connection
        if has_stub or has_fiber:
            # Terminal already connected via adjacency map - let BFS handle it
            pass
        # MST Terminal: use stub cable (physical or virtual)
        elif terminal_type.lower() == "mst":
            fosc_id = get_field_value(term_rec, "fosc_id", "foscid")
            fdh_id = get_field_value(term_rec, "fdh_id", "fdhid")
            
            if fosc_id and fosc_id in indexes["fosc"]:
                path_segments.append({
                    "from": start_node,
                    "to": fosc_id,
                    "from_layer": "terminal",
                    "to_layer": "splice closure",
                    "cable_id": None,
                    "cable_layer": "stub cable",
                    "length_m": None,
                    "virtual": True
                })
                diagnostics["mst_virtual_stub"] += 1
                start_node = fosc_id
                start_layer = "splice closure"
            elif fdh_id and fdh_id in indexes["fdh"]:
                # MST terminal directly to FDH (rare)
                path_segments.append({
                    "from": start_node,
                    "to": fdh_id,
                    "from_layer": "terminal",
                    "to_layer": "fdh",
                    "cable_id": None,
                    "cable_layer": "stub cable",
                    "length_m": None,
                    "virtual": True
                })
                diagnostics["mst_virtual_stub"] += 1
                start_node = fdh_id
                start_layer = "fdh"
        # Aerial Terminal: check if cable_id exists but no connection found
        elif "aerial" in terminal_type.lower():
            cable_id = get_field_value(term_rec, "cable_id", "cableid")
            fdh_id = get_field_value(term_rec, "fdh_id", "fdhid")
            
            # If cable_id doesn't match any fiber cable, create virtual stub to FDH
            if cable_id and cable_id not in fiber_cable_ids:
                if fdh_id and fdh_id in indexes["fdh"]:
                    path_segments.append({
                        "from": start_node,
                        "to": fdh_id,
                        "from_layer": "terminal",
                        "to_layer": "fdh",
                        "cable_id": cable_id,
                        "cable_layer": "stub cable",
                        "length_m": None,
                        "virtual": True
                    })
                    diagnostics["aerial_virtual_stub"] += 1
                    start_node = fdh_id
                    start_layer = "fdh"
            # If no cable_id but has FDH, create virtual stub
            elif not cable_id and fdh_id and fdh_id in indexes["fdh"]:
                path_segments.append({
                    "from": start_node,
                    "to": fdh_id,
                    "from_layer": "terminal",
                    "to_layer": "fdh",
                    "cable_id": None,
                    "cable_layer": "stub cable",
                    "length_m": None,
                    "virtual": True
                })
                diagnostics["aerial_virtual_stub"] += 1
                start_node = fdh_id
                start_layer = "fdh"
    
    # Use BFS to find path to OLT from current position
    bfs_segments, final_node, final_layer, bfs_hops, bfs_length = bfs_traverse_to_olt(
        start_node, start_layer, target_olt_id, None, diagnostics
    )
    
    path_segments.extend(bfs_segments)
    hop_count = len(path_segments)
    
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
    is_complete = final_layer == "olt"
    
    paths.append({
        "ont_id": ont_id,
        "olt_id": target_olt_id,
        "path": path_segments,
        "cable_length_summary": dict(length_summary),
        "total_length_m": total_length,
        "hop_count": hop_count,
        "final_node_type": final_node_type,
        "complete": is_complete
    })

# Build node list
nodes = {}
for l in links:
    nodes[l["source"]] = l["source_layer"]
    nodes[l["target"]] = l["target_layer"]
node_list = [{"id": nid, "layer": lyr} for nid, lyr in nodes.items()]

# Calculate summary metrics
print("\nCalculating summary metrics...")

ont_lengths = [p["total_length_m"] for p in paths if p["total_length_m"] > 0]
avg_length = sum(ont_lengths) / len(ont_lengths) if ont_lengths else 0
max_length = max(ont_lengths) if ont_lengths else 0

complete_paths = [p for p in paths if p.get("complete", False)]
complete_percentage = (len(complete_paths) / len(paths) * 100) if paths else 0

hop_counts = [p.get("hop_count", 0) for p in paths]
avg_hop_count = sum(hop_counts) / len(hop_counts) if hop_counts else 0
max_hop_count = max(hop_counts) if hop_counts else 0

# Count virtual connections
virtual_count = sum(1 for l in links if l.get("virtual", False))
virtual_by_layer = defaultdict(int)
for l in links:
    if l.get("virtual", False):
        virtual_by_layer[l.get("cable_layer", "unknown")] += 1

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
    "average_hop_count": round(avg_hop_count, 2),
    "max_hop_count": max_hop_count,
    "unreachable_nodes_count": len(unreachable_nodes),
    "virtual_connections_total": virtual_count,
    "virtual_by_layer": dict(virtual_by_layer),
    "final_node_type_distribution": dict(final_node_types)
}

diagnostics_refinement = {
    "onts_rescued_via_virtual_drop": diagnostics.get("onts_rescued_via_virtual_drop", 0),
    "aerial_virtual_stub": diagnostics.get("aerial_virtual_stub", 0),
    "mst_virtual_stub": diagnostics.get("mst_virtual_stub", 0),
    "edge_fosc_virtual_links": diagnostics.get("edge_fosc_virtual_links", 0),
    "total_virtual_connections": virtual_count
}

# Save outputs
print("\nSaving outputs...")

with open("logical_fiber_graph.json", "w", encoding="utf-8") as f:
    json.dump({"nodes": node_list, "links": links}, f, indent=2)

with open("olt_ont_paths.json", "w", encoding="utf-8") as f:
    json.dump(paths, f, indent=2)

with open("summary_metrics.json", "w", encoding="utf-8") as f:
    json.dump(summary_metrics, f, indent=2)

with open("diagnostics_refinement.json", "w", encoding="utf-8") as f:
    json.dump(diagnostics_refinement, f, indent=2)

unreachable_nodes_list = sorted(list(unreachable_nodes))
with open("unreachable_nodes.json", "w", encoding="utf-8") as f:
    json.dump({"unreachable_nodes": unreachable_nodes_list, "count": len(unreachable_nodes_list)}, f, indent=2)

print("\n" + "=" * 80)
print("✅ REFINED GRAPH BUILD COMPLETE")
print("=" * 80)
print(f"   • Nodes: {len(node_list):,}")
print(f"   • Links: {len(links):,}")
print(f"   • Complete paths: {len(complete_paths):,} ({complete_percentage:.2f}%)")
print(f"   • Virtual connections: {virtual_count:,}")
print(f"   • Unreachable nodes: {len(unreachable_nodes):,}")
print("=" * 80)

