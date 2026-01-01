#!/usr/bin/env python3
"""
graph_utils.py
-------------------------------------------------------------------------------
Utilities for building and traversing network graphs
-------------------------------------------------------------------------------
"""

from typing import Dict, List, Set, Any, Optional
from collections import defaultdict, deque

def build_adjacency_graph(edges: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build adjacency list representation of a directed graph.
    
    Args:
        edges: List of edge dictionaries with 'from' and 'to' keys
        
    Returns:
        Adjacency dictionary: {node_id: [edge1, edge2, ...]}
    """
    graph = defaultdict(list)
    
    for edge in edges:
        from_node = edge.get("from")
        to_node = edge.get("to")
        
        if from_node and to_node:
            graph[from_node].append(edge)
    
    return dict(graph)

def bfs_traverse(graph: Dict[str, List[Dict[str, Any]]], 
                 start_node: str,
                 target_type: Optional[str] = None) -> Set[str]:
    """
    Breadth-first search traversal from start node.
    
    Args:
        graph: Adjacency graph dictionary
        start_node: Starting node ID
        target_type: Optional node type to filter (e.g., "ont")
        
    Returns:
        Set of reachable node IDs
    """
    if start_node not in graph:
        return set()
    
    visited = set()
    queue = deque([start_node])
    visited.add(start_node)
    
    while queue:
        current = queue.popleft()
        
        for edge in graph.get(current, []):
            next_node = edge.get("to")
            node_type = edge.get("to_layer")
            
            if next_node and next_node not in visited:
                if target_type is None or node_type == target_type:
                    visited.add(next_node)
                    queue.append(next_node)
    
    return visited

def count_downstream_nodes(graph: Dict[str, List[Dict[str, Any]]], 
                          node_id: str,
                          target_type: str = "ont",
                          cache: Optional[Dict[str, int]] = None) -> int:
    """
    Count downstream nodes of a specific type using BFS.
    
    Args:
        graph: Adjacency graph dictionary
        node_id: Starting node ID
        target_type: Type of nodes to count (e.g., "ont")
        cache: Optional cache dictionary for memoization
        
    Returns:
        Count of downstream nodes of target type
    """
    if cache is not None and node_id in cache:
        return cache[node_id]
    
    reachable = bfs_traverse(graph, node_id, target_type)
    count = len([n for n in reachable if n.startswith("O")])  # ONT IDs start with O
    
    if cache is not None:
        cache[node_id] = count
    
    return count

def precompute_downstream_counts(graph: Dict[str, List[Dict[str, Any]]], 
                                 target_type: str = "ont") -> Dict[str, int]:
    """
    Pre-compute downstream node counts for all nodes in graph.
    
    Args:
        graph: Adjacency graph dictionary
        target_type: Type of nodes to count
        
    Returns:
        Dictionary mapping node_id to downstream count
    """
    cache = {}
    
    # Process nodes in reverse topological order (leaves first)
    # For simplicity, process all nodes
    for node_id in graph.keys():
        count_downstream_nodes(graph, node_id, target_type, cache)
    
    return cache

def find_path(graph: Dict[str, List[Dict[str, Any]]], 
              start_node: str,
              end_node: str) -> Optional[List[str]]:
    """
    Find path between two nodes using BFS.
    
    Args:
        graph: Adjacency graph dictionary
        start_node: Starting node ID
        end_node: Target node ID
        
    Returns:
        List of node IDs forming the path, or None if no path exists
    """
    if start_node == end_node:
        return [start_node]
    
    if start_node not in graph:
        return None
    
    visited = set()
    queue = deque([(start_node, [start_node])])
    visited.add(start_node)
    
    while queue:
        current, path = queue.popleft()
        
        for edge in graph.get(current, []):
            next_node = edge.get("to")
            
            if next_node == end_node:
                return path + [next_node]
            
            if next_node and next_node not in visited:
                visited.add(next_node)
                queue.append((next_node, path + [next_node]))
    
    return None



