#!/usr/bin/env python3
"""
Network Graph Builder
Creates a proper tree/graph structure from cables, OLTs, ONTs, FOSCs, and terminals.
This enables clear path finding from ONT to OLT for accurate cable sizing.
"""

from typing import Dict, List, Any, Tuple, Optional, Set
from collections import defaultdict, deque
from utils.spatial_utils import euclidean_distance
from utils.drop_cable_builder import create_drop_cables_for_onts, add_drop_cables_to_graph


class NetworkNode:
    """Represents a node in the network graph."""
    def __init__(self, node_id: str, node_type: str, position: Tuple[float, float], data: Dict[str, Any] = None):
        self.id = node_id
        self.type = node_type  # 'olt', 'ont', 'fosc', 'terminal', 'junction', 'cable_endpoint'
        self.position = position
        self.data = data or {}
        self.edges = []  # List of (target_node_id, cable_idx, direction)
    
    def __repr__(self):
        return f"NetworkNode({self.id}, {self.type}, {self.position})"


class NetworkGraph:
    """
    Network graph representing the fiber infrastructure.
    Nodes: OLTs, ONTs, FOSCs, Terminals, Cable Junctions
    Edges: Cable segments connecting nodes
    """
    
    def __init__(self, tolerance_m: float = 10.0):
        self.nodes: Dict[str, NetworkNode] = {}
        self.cables: List[Dict[str, Any]] = []
        self.cable_to_nodes: Dict[int, List[str]] = defaultdict(list)  # cable_idx -> [node_ids]
        self.node_to_cables: Dict[str, List[int]] = defaultdict(list)  # node_id -> [cable_indices]
        self.tolerance_m = tolerance_m
        self.grid_size = tolerance_m
    
    def add_node(self, node_id: str, node_type: str, position: Tuple[float, float], data: Dict[str, Any] = None):
        """Add a node to the graph."""
        if node_id not in self.nodes:
            self.nodes[node_id] = NetworkNode(node_id, node_type, position, data)
        return self.nodes[node_id]
    
    def add_cable(self, cable_idx: int, cable_data: Dict[str, Any]):
        """Add a cable to the graph and create nodes at its endpoints."""
        self.cables.append(cable_data)
        coords = cable_data.get("coordinates", [])
        if len(coords) < 2:
            return
        
        start = coords[0]
        end = coords[-1]
        
        # Create nodes at endpoints
        start_key = self._round_position(start)
        end_key = self._round_position(end)
        
        start_node_id = f"cable_{cable_idx}_start"
        end_node_id = f"cable_{cable_idx}_end"
        
        # Check if nodes already exist at these positions (junction)
        existing_start = self._find_node_at_position(start, start_node_id)
        existing_end = self._find_node_at_position(end, end_node_id)
        
        if existing_start:
            start_node_id = existing_start
            # Update existing node to include this cable
            if cable_idx not in self.node_to_cables.get(start_node_id, []):
                self.node_to_cables[start_node_id].append(cable_idx)
        else:
            self.add_node(start_node_id, "cable_endpoint", start, {"cable_idx": cable_idx, "endpoint": "start"})
        
        if existing_end:
            end_node_id = existing_end
            # Update existing node to include this cable
            if cable_idx not in self.node_to_cables.get(end_node_id, []):
                self.node_to_cables[end_node_id].append(cable_idx)
        else:
            self.add_node(end_node_id, "cable_endpoint", end, {"cable_idx": cable_idx, "endpoint": "end"})
        
        # Link cable to nodes
        self.cable_to_nodes[cable_idx].extend([start_node_id, end_node_id])
        self.node_to_cables[start_node_id].append(cable_idx)
        self.node_to_cables[end_node_id].append(cable_idx)
        
        # Create edge between start and end (bidirectional)
        start_node = self.nodes[start_node_id]
        end_node = self.nodes[end_node_id]
        
        if (end_node_id, cable_idx, "forward") not in start_node.edges:
            start_node.edges.append((end_node_id, cable_idx, "forward"))
        if (start_node_id, cable_idx, "backward") not in end_node.edges:
            end_node.edges.append((start_node_id, cable_idx, "backward"))
    
    def add_olt(self, olt_id: str, position: Tuple[float, float], data: Dict[str, Any] = None):
        """Add an OLT to the graph and connect it to nearest cable."""
        node = self.add_node(olt_id, "olt", position, data)
        
        # Find nearest cable endpoint
        nearest_cable_idx, nearest_node_id, distance = self._find_nearest_cable_node(position)
        if nearest_cable_idx is not None and distance <= self.tolerance_m * 2:
            # Connect OLT to cable node
            cable_node = self.nodes[nearest_node_id]
            if (olt_id, nearest_cable_idx, "olt_connection") not in cable_node.edges:
                cable_node.edges.append((olt_id, nearest_cable_idx, "olt_connection"))
            if (nearest_node_id, nearest_cable_idx, "olt_connection") not in node.edges:
                node.edges.append((nearest_node_id, nearest_cable_idx, "olt_connection"))
    
    def add_ont(self, ont_id: str, position: Tuple[float, float], terminal_id: Optional[str] = None, data: Dict[str, Any] = None):
        """Add an ONT to the graph and connect it to terminal or nearest cable."""
        node = self.add_node(ont_id, "ont", position, data)
        
        # If terminal_id provided, try to find terminal node
        terminal_node_id = None
        if terminal_id:
            # Try exact match first
            if terminal_id in self.nodes:
                terminal_node_id = terminal_id
            else:
                # Try to find terminal by searching node data
                for node_id, n in self.nodes.items():
                    if n.type == "terminal":
                        term_id = n.data.get("terminal_id") or n.data.get("id", "")
                        if term_id == terminal_id or node_id == terminal_id:
                            terminal_node_id = node_id
                            break
                
                # If still not found, try finding nearest terminal
                if terminal_node_id is None:
                    min_dist = float('inf')
                    for node_id, n in self.nodes.items():
                        if n.type == "terminal":
                            dist = euclidean_distance(position[0], position[1], n.position[0], n.position[1])
                            if dist < min_dist and dist <= self.tolerance_m * 2:
                                min_dist = dist
                                terminal_node_id = node_id
        
        # Connect to terminal if found
        if terminal_node_id:
            terminal_node = self.nodes[terminal_node_id]
            if (ont_id, None, "drop_cable") not in terminal_node.edges:
                terminal_node.edges.append((ont_id, None, "drop_cable"))
            if (terminal_node_id, None, "drop_cable") not in node.edges:
                node.edges.append((terminal_node_id, None, "drop_cable"))
        else:
            # Find nearest cable endpoint (for direct connection)
            nearest_cable_idx, nearest_node_id, distance = self._find_nearest_cable_node(position)
            if nearest_cable_idx is not None and distance <= self.tolerance_m * 2:
                cable_node = self.nodes[nearest_node_id]
                if (ont_id, nearest_cable_idx, "drop_cable") not in cable_node.edges:
                    cable_node.edges.append((ont_id, nearest_cable_idx, "drop_cable"))
                if (nearest_node_id, nearest_cable_idx, "drop_cable") not in node.edges:
                    node.edges.append((nearest_node_id, nearest_cable_idx, "drop_cable"))
    
    def add_fosc(self, fosc_id: str, position: Tuple[float, float], data: Dict[str, Any] = None):
        """Add a FOSC to the graph at a junction point."""
        # Find or create node at FOSC position
        existing_node = self._find_node_at_position(position, fosc_id)
        if existing_node and existing_node != fosc_id:
            # FOSC is at an existing junction
            node = self.nodes[existing_node]
            node.type = "fosc"
            node.data.update(data or {})
            node.data["fosc_id"] = fosc_id
        else:
            node = self.add_node(fosc_id, "fosc", position, data)
    
    def add_terminal(self, terminal_id: str, position: Tuple[float, float], data: Dict[str, Any] = None):
        """Add a terminal to the graph at a junction point."""
        # Find or create node at terminal position
        existing_node = self._find_node_at_position(position, terminal_id)
        if existing_node and existing_node != terminal_id:
            # Terminal is at an existing junction
            node = self.nodes[existing_node]
            node.type = "terminal"
            node.data.update(data or {})
            node.data["terminal_id"] = terminal_id
        else:
            node = self.add_node(terminal_id, "terminal", position, data)
    
    def find_path_ont_to_olt(self, ont_id: str, olt_id: str) -> Optional[List[Tuple[str, int]]]:
        """
        Find path from ONT to OLT using BFS.
        Returns: List of (node_id, cable_idx) tuples, or None if no path found.
        """
        if ont_id not in self.nodes or olt_id not in self.nodes:
            return None
        
        # BFS to find shortest path
        queue = deque([(ont_id, [])])
        visited = {ont_id}
        
        while queue:
            current_id, path = queue.popleft()
            
            if current_id == olt_id:
                return path + [(current_id, None)]
            
            current_node = self.nodes[current_id]
            
            for neighbor_id, cable_idx, direction in current_node.edges:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    new_path = path + [(current_id, cable_idx), (neighbor_id, cable_idx)]
                    queue.append((neighbor_id, new_path))
        
        return None
    
    def find_all_ont_to_olt_paths(self, ont_geojson: Dict[str, Any], olts: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, int]]]:
        """
        Find paths for all ONTs to their assigned OLTs.
        Returns: Dict mapping ont_id -> path (list of (node_id, cable_idx) tuples)
        """
        paths = {}
        
        # Build ONT to OLT mapping
        ont_to_olt = {}
        for ont_feature in ont_geojson.get("features", []):
            ont_props = ont_feature.get("properties", {})
            ont_id = ont_props.get("id") or ont_props.get("ont_id", "")
            olt_id = ont_props.get("olt_id") or ont_props.get("oltid", "")
            
            if ont_id and olt_id:
                ont_to_olt[ont_id] = olt_id
        
        # Find paths
        for ont_id, olt_id in ont_to_olt.items():
            path = self.find_path_ont_to_olt(ont_id, olt_id)
            if path:
                paths[ont_id] = path
        
        return paths
    
    def get_cables_on_path(self, path: List[Tuple[str, int]]) -> Set[int]:
        """Extract unique cable indices from a path."""
        cable_indices = set()
        for node_id, cable_idx in path:
            if cable_idx is not None:
                cable_indices.add(cable_idx)
        return cable_indices
    
    def aggregate_requirements_along_paths(self, paths: Dict[str, List[Tuple[str, int]]], ont_counts: Dict[str, int], config: Dict[str, Any]) -> Dict[int, int]:
        """
        Aggregate fiber requirements for each cable based on all paths that use it.
        Returns: Dict mapping cable_idx -> total_required_fibers
        """
        from phases.phase6_cable_sizing import calculate_required_fibers_from_onts
        
        cable_ont_counts = defaultdict(int)  # cable_idx -> total ONT count
        
        # For each path, add ONT count to all cables on that path
        for ont_id, path in paths.items():
            ont_count = ont_counts.get(ont_id, 1)
            cable_indices = self.get_cables_on_path(path)
            
            for cable_idx in cable_indices:
                cable_ont_counts[cable_idx] += ont_count
        
        # Calculate required fibers for each cable
        cable_requirements = {}
        min_infrastructure_size = 48
        for cable_idx, total_onts in cable_ont_counts.items():
            required_fibers = calculate_required_fibers_from_onts(total_onts, config)
            required_fibers = max(required_fibers, min_infrastructure_size)
            cable_requirements[cable_idx] = required_fibers
        
        return cable_requirements
    
    def _round_position(self, pos: Tuple[float, float]) -> Tuple[int, int]:
        """Round position to grid for junction detection."""
        return (int(pos[0] / self.grid_size), int(pos[1] / self.grid_size))
    
    def _find_node_at_position(self, position: Tuple[float, float], exclude_id: str = None) -> Optional[str]:
        """Find existing node at position (within tolerance)."""
        for node_id, node in self.nodes.items():
            if node_id == exclude_id:
                continue
            dist = euclidean_distance(position[0], position[1], node.position[0], node.position[1])
            if dist <= self.tolerance_m:
                return node_id
        return None
    
    def _find_nearest_cable_node(self, position: Tuple[float, float]) -> Tuple[Optional[int], Optional[str], float]:
        """Find nearest cable endpoint node to position."""
        min_dist = float('inf')
        nearest_cable_idx = None
        nearest_node_id = None
        
        for node_id, node in self.nodes.items():
            if node.type == "cable_endpoint":
                dist = euclidean_distance(position[0], position[1], node.position[0], node.position[1])
                if dist < min_dist:
                    min_dist = dist
                    nearest_node_id = node_id
                    # Get cable_idx from node_to_cables mapping
                    cable_indices = self.node_to_cables.get(node_id, [])
                    if cable_indices:
                        nearest_cable_idx = cable_indices[0]  # Use first cable at this node
        
        return nearest_cable_idx, nearest_node_id, min_dist
    
    def get_junctions(self) -> Dict[Tuple[float, float], List[str]]:
        """Get all junction points (where 2+ cables meet)."""
        junctions = defaultdict(list)
        
        for node_id, node in self.nodes.items():
            if node.type == "cable_endpoint":
                # Count cables connected to this node
                cable_indices = self.node_to_cables.get(node_id, [])
                if len(cable_indices) >= 2:
                    junctions[node.position].append(node_id)
        
        return dict(junctions)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        stats = {
            "total_nodes": len(self.nodes),
            "node_types": defaultdict(int),
            "total_cables": len(self.cables),
            "total_edges": sum(len(node.edges) for node in self.nodes.values()),
            "junctions": len(self.get_junctions())
        }
        
        for node in self.nodes.values():
            stats["node_types"][node.type] += 1
        
        return stats


def build_network_graph(
    fiber_cable_geojson: Dict[str, Any],
    olts: List[Dict[str, Any]],
    ont_geojson: Dict[str, Any],
    foscs: List[Dict[str, Any]] = None,
    terminals: List[Dict[str, Any]] = None,
    config: Dict[str, Any] = None,
    tolerance_m: float = 10.0
) -> NetworkGraph:
    """
    Build a complete network graph from all infrastructure components.
    
    Args:
        fiber_cable_geojson: Cable GeoJSON
        olts: List of OLTs
        ont_geojson: ONT GeoJSON
        foscs: List of FOSCs (optional)
        terminals: List of terminals (optional)
        tolerance_m: Spatial tolerance for connections
    
    Returns:
        NetworkGraph instance
    """
    graph = NetworkGraph(tolerance_m=tolerance_m)
    
    # Step 1: Add all cables
    print("  Building network graph: Adding cables...")
    for i, feature in enumerate(fiber_cable_geojson.get("features", [])):
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
            coord_tuples = [(c[0], c[1]) for c in coords if len(c) >= 2]
            if coord_tuples:
                graph.add_cable(i, {
                    "index": i,
                    "id": props.get("ID") or props.get("id", ""),
                    "coordinates": coord_tuples,
                    "properties": props
                })
    
    print(f"    Added {len(graph.cables)} cables")
    
    # Step 2: Add FOSCs (before terminals, as they take precedence at junctions)
    if foscs:
        print("  Adding FOSCs...")
        for fosc in foscs:
            fosc_id = fosc.get("fosc_id") or fosc.get("id", "")
            fosc_pos = fosc.get("position")
            if fosc_id and fosc_pos:
                graph.add_fosc(fosc_id, tuple(fosc_pos), fosc)
        print(f"    Added {len(foscs)} FOSCs")
    
    # Step 3: Add terminals
    if terminals:
        print("  Adding terminals...")
        for terminal in terminals:
            terminal_id = terminal.get("terminal_id") or terminal.get("id", "")
            terminal_pos = terminal.get("position")
            if terminal_id and terminal_pos:
                graph.add_terminal(terminal_id, tuple(terminal_pos), terminal)
        print(f"    Added {len(terminals)} terminals")
    
    # Step 4: Add OLTs
    print("  Adding OLTs...")
    for olt in olts:
        olt_id = olt.get("olt_id") or olt.get("id", "")
        olt_pos = olt.get("position")
        if olt_id and olt_pos:
            graph.add_olt(olt_id, tuple(olt_pos), olt)
    print(f"    Added {len(olts)} OLTs")
    
    # Step 5: Create drop cables and add ONTs
    print("  Creating drop cables to connect ONTs to terminals...")
    drop_cables = create_drop_cables_for_onts(ont_geojson, terminals, config=config, tolerance_m=1000.0)
    
    # Step 6: Add ONTs and drop cables to graph
    print("  Adding ONTs and drop cables to graph...")
    ont_count = 0
    for feature in ont_geojson.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        
        ont_id = props.get("id") or props.get("ont_id", "")
        coords = geometry.get("coordinates", [])
        
        if ont_id and len(coords) >= 2:
            ont_pos = (coords[0], coords[1])
            graph.add_node(ont_id, "ont", ont_pos, props)
            ont_count += 1
    
    # Add drop cable connections
    add_drop_cables_to_graph(graph, drop_cables)
    
    print(f"    Added {ont_count} ONTs with {len(drop_cables)} drop cable connections")
    
    # Print statistics
    stats = graph.get_statistics()
    print()
    print("  Graph Statistics:")
    print(f"    Total nodes: {stats['total_nodes']}")
    print(f"    Node types: {dict(stats['node_types'])}")
    print(f"    Total cables: {stats['total_cables']}")
    print(f"    Total edges: {stats['total_edges']}")
    print(f"    Junctions: {stats['junctions']}")
    print()
    
    return graph
