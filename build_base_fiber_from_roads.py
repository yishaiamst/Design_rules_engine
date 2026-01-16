#!/usr/bin/env python3
import argparse
import json
import math
from typing import Any, Dict, List, Optional, Tuple

from phases.phase3e_connect_isolated_cables import convert_wgs84_to_utm_coords
from utils.geojson_utils import create_feature, create_feature_collection


def euclidean_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def point_to_segment_distance(
    p: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]
) -> float:
    x0, y0 = p
    x1, y1 = a
    x2, y2 = b
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return euclidean_distance(p, a)
    t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
    proj = (x1 + t * dx, y1 + t * dy)
    return euclidean_distance(p, proj)


def flatten_lines(geometry: Dict[str, Any]) -> List[List[List[float]]]:
    if geometry.get("type") == "LineString":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiLineString":
        return geometry.get("coordinates", [])
    return []


def path_length(coords: List[Tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        total += euclidean_distance(coords[i], coords[i + 1])
    return total


def build_ont_grid(points: List[Tuple[float, float]], cell_size: float) -> Dict[Tuple[int, int], List[Tuple[float, float]]]:
    grid: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
    for p in points:
        gx = int(p[0] // cell_size)
        gy = int(p[1] // cell_size)
        grid.setdefault((gx, gy), []).append(p)
    return grid


def min_distance_to_onts(
    road_coords: List[Tuple[float, float]],
    grid: Dict[Tuple[int, int], List[Tuple[float, float]]],
    cell_size: float,
    max_dist: float
) -> float:
    min_dist = float("inf")
    for i in range(len(road_coords) - 1):
        a = road_coords[i]
        b = road_coords[i + 1]
        gx = int(((a[0] + b[0]) / 2) // cell_size)
        gy = int(((a[1] + b[1]) / 2) // cell_size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for p in grid.get((gx + dx, gy + dy), []):
                    d = point_to_segment_distance(p, a, b)
                    if d < min_dist:
                        min_dist = d
                        if min_dist <= max_dist:
                            return min_dist
    return min_dist


def nearest_road_for_point(
    p: Tuple[float, float],
    roads: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], float]:
    best = None
    min_dist = float("inf")
    for road in roads:
        coords = road["coords"]
        for i in range(len(coords) - 1):
            d = point_to_segment_distance(p, coords[i], coords[i + 1])
            if d < min_dist:
                min_dist = d
                best = road
    return best, min_dist


def snap_key(p: Tuple[float, float], snap_tol: float) -> Tuple[int, int]:
    return (round(p[0] / snap_tol), round(p[1] / snap_tol))


def add_node(
    point: Tuple[float, float],
    nodes: List[Tuple[float, float]],
    snap_tol: float,
) -> int:
    for idx, p in enumerate(nodes):
        if euclidean_distance(point, p) <= snap_tol:
            return idx
    nodes.append(point)
    return len(nodes) - 1


def build_road_graph(
    road_polylines: List[List[Tuple[float, float]]],
    snap_tol: float,
) -> Tuple[List[Tuple[float, float]], Dict[int, List[Tuple[int, float]]], List[Dict[str, Any]]]:
    nodes: List[Tuple[float, float]] = []
    adjacency: Dict[int, List[Tuple[int, float]]] = {}
    segments: List[Dict[str, Any]] = []

    for poly in road_polylines:
        for i in range(len(poly) - 1):
            a = poly[i]
            b = poly[i + 1]
            n1 = add_node(a, nodes, snap_tol)
            n2 = add_node(b, nodes, snap_tol)
            d = euclidean_distance(a, b)
            adjacency.setdefault(n1, []).append((n2, d))
            adjacency.setdefault(n2, []).append((n1, d))
            segments.append({"a": a, "b": b, "n1": n1, "n2": n2})

    return nodes, adjacency, segments


def nearest_point_on_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> Tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return (x1, y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return (x1 + t * dx, y1 + t * dy)


def insert_projection_node(
    point: Tuple[float, float],
    nodes: List[Tuple[float, float]],
    adjacency: Dict[int, List[Tuple[int, float]]],
    segments: List[Dict[str, Any]],
    snap_tol: float,
    max_snap_m: float,
    force_segment_index: Optional[int] = None,
) -> Optional[Tuple[int, Tuple[float, float], float]]:
    best = None
    seg_indices = [force_segment_index] if force_segment_index is not None else range(len(segments))
    for i in seg_indices:
        if i is None:
            continue
        seg = segments[i]
        a = seg["a"]
        b = seg["b"]
        proj = nearest_point_on_segment(point[0], point[1], a[0], a[1], b[0], b[1])
        d = euclidean_distance(point, proj)
        if best is None or d < best[2]:
            best = (proj, i, d)

    if best is None or best[2] > max_snap_m:
        return None

    proj, seg_index, dist = best
    node_id = add_node(proj, nodes, snap_tol)
    seg = segments[seg_index]
    n1 = seg["n1"]
    n2 = seg["n2"]
    adjacency.setdefault(node_id, [])
    adjacency[node_id].append((n1, euclidean_distance(proj, seg["a"])))
    adjacency[node_id].append((n2, euclidean_distance(proj, seg["b"])))
    adjacency.setdefault(n1, []).append((node_id, euclidean_distance(proj, seg["a"])))
    adjacency.setdefault(n2, []).append((node_id, euclidean_distance(proj, seg["b"])))

    return node_id, proj, dist


def dijkstra_multi_source(
    adjacency: Dict[int, List[Tuple[int, float]]],
    sources: List[int],
) -> Tuple[Dict[int, float], Dict[int, int]]:
    import heapq

    dist = {}
    prev = {}
    heap = []
    for s in sources:
        dist[s] = 0.0
        heap.append((0.0, s))

    heapq.heapify(heap)
    visited = set()

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        for v, w in adjacency.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, prev


def reconstruct_path_to_source(prev: Dict[int, int], goal: int) -> List[int]:
    path = [goal]
    while path[-1] in prev:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build base fiber route from roads and ONTs.")
    parser.add_argument("--onts", required=True, help="ONT GeoJSON (UTM)")
    parser.add_argument("--roads", required=True, help="Roads GeoJSON (WGS84 or UTM)")
    parser.add_argument("--output", required=True, help="Output fiber cable GeoJSON (UTM)")
    parser.add_argument("--min-distance-m", type=float, default=200.0)
    parser.add_argument("--max-distance-m", type=float, default=500.0)
    parser.add_argument("--snap-tol-m", type=float, default=1.0)
    parser.add_argument(
        "--prefer-highway",
        default="motorway,trunk,primary,secondary,tertiary",
        help="Comma list of preferred highway classes"
    )
    parser.add_argument("--min-ont-count", type=int, default=3)
    parser.add_argument("--skip-low-ont", dest="skip_low_ont", action="store_true", default=True)
    parser.add_argument("--no-skip-low-ont", dest="skip_low_ont", action="store_false")
    parser.add_argument("--road-node-snap-m", type=float, default=0.5)
    parser.add_argument("--max-road-snap-m", type=float, default=50.0)
    parser.add_argument("--max-tiles", type=int, default=9)  # placeholder, no-op
    args = parser.parse_args()

    with open(args.onts) as f:
        ont_geo = json.load(f)
    with open(args.roads) as f:
        roads_geo = json.load(f)

    ont_points = []
    for feat in ont_geo.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            ont_points.append((float(coords[0]), float(coords[1])))

    if not ont_points:
        raise SystemExit("No ONT points found.")

    # Detect roads CRS via coordinate range
    roads = []
    for feat in roads_geo.get("features", []):
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        for part in flatten_lines(geom):
            if len(part) < 2:
                continue
            coords = []
            for p in part:
                x, y = float(p[0]), float(p[1])
                if -180 <= x <= 180 and -90 <= y <= 90:
                    x, y = convert_wgs84_to_utm_coords(x, y, utm_zone=17)
                coords.append((x, y))
            roads.append({
                "coords": coords,
                "highway": props.get("highway", ""),
                "name": props.get("name", ""),
                "osm_id": props.get("osm_id", ""),
                "ont_count": 0
            })

    grid = build_ont_grid(ont_points, args.max_distance_m)
    preferred = {h.strip() for h in args.prefer_highway.split(",") if h.strip()}

    # Assign ONTs to nearest road (within max distance)
    for p in ont_points:
        best_road = None
        min_dist = float("inf")
        for road in roads:
            coords = road["coords"]
            for i in range(len(coords) - 1):
                d = point_to_segment_distance(p, coords[i], coords[i + 1])
                if d < min_dist:
                    min_dist = d
                    best_road = road
        if best_road and min_dist <= args.max_distance_m:
            best_road["ont_count"] += 1

    selected = []
    for road in roads:
        dist = min_distance_to_onts(road["coords"], grid, args.max_distance_m, args.max_distance_m)
        road["min_ont_dist"] = dist
        if road["highway"] in preferred and dist <= args.max_distance_m:
            if args.skip_low_ont and road["ont_count"] < args.min_ont_count:
                continue
            selected.append(road)

    # Ensure coverage: add nearest road for ONTs beyond max-distance
    for p in ont_points:
        best_road, best_dist = nearest_road_for_point(p, selected)
        if best_dist <= args.max_distance_m:
            continue
        fallback_road, _ = nearest_road_for_point(p, roads)
        if fallback_road and fallback_road not in selected:
            if args.skip_low_ont and fallback_road["ont_count"] < args.min_ont_count:
                continue
            selected.append(fallback_road)

    # Build graph edges from selected roads (endpoint graph)
    edges = []
    for idx, road in enumerate(selected):
        coords = road["coords"]
        if len(coords) < 2:
            continue
        start = coords[0]
        end = coords[-1]
        edges.append({
            "start": start,
            "end": end,
            "coords": coords,
            "length": path_length(coords),
            "props": road
        })

    # Union-Find for MST per component
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra
            return True
        return False

    # Initialize nodes
    nodes = {}
    for e in edges:
        for p in [e["start"], e["end"]]:
            key = snap_key(p, args.snap_tol_m)
            nodes[key] = p
    for key in nodes.keys():
        parent[key] = key

    # Sort edges by length
    edges_sorted = sorted(edges, key=lambda e: e["length"])
    mst_edges = []
    for e in edges_sorted:
        a = snap_key(e["start"], args.snap_tol_m)
        b = snap_key(e["end"], args.snap_tol_m)
        if union(a, b):
            mst_edges.append(e)

    # Output GeoJSON
    features = []
    for idx, e in enumerate(mst_edges, start=1):
        props = e["props"]
        feature_props = {
            "ID": f"BASE_FIBER_{idx:04d}",
            "highway": props.get("highway", ""),
            "name": props.get("name", ""),
            "osm_id": props.get("osm_id", ""),
            "min_ont_dist_m": props.get("min_ont_dist", None),
            "ont_count": props.get("ont_count", 0)
        }
        geometry = {
            "type": "LineString",
            "coordinates": [[p[0], p[1]] for p in e["coords"]]
        }
        features.append(create_feature(geometry, feature_props))

    # Connect isolated components via shortest road path to main component
    if mst_edges:
        road_polylines = [r["coords"] for r in roads]
        road_nodes, road_adjacency, road_segments = build_road_graph(
            road_polylines, snap_tol=args.road_node_snap_m
        )

        # Build component map from MST edges
        comp_parent = {}
        comp_nodes = {}
        comp_length = {}

        def comp_find(x):
            while comp_parent[x] != x:
                comp_parent[x] = comp_parent[comp_parent[x]]
                x = comp_parent[x]
            return x

        def comp_union(a, b):
            ra = comp_find(a)
            rb = comp_find(b)
            if ra != rb:
                comp_parent[rb] = ra

        for e in mst_edges:
            for p in [e["start"], e["end"]]:
                key = snap_key(p, args.snap_tol_m)
                comp_parent.setdefault(key, key)
        for e in mst_edges:
            a = snap_key(e["start"], args.snap_tol_m)
            b = snap_key(e["end"], args.snap_tol_m)
            comp_union(a, b)

        for e in mst_edges:
            comp = comp_find(snap_key(e["start"], args.snap_tol_m))
            comp_length[comp] = comp_length.get(comp, 0.0) + e["length"]
            comp_nodes.setdefault(comp, set()).update([
                snap_key(e["start"], args.snap_tol_m),
                snap_key(e["end"], args.snap_tol_m),
            ])

        main_comp = max(comp_length.items(), key=lambda kv: kv[1])[0]

        # Build road graph nodes for main component endpoints
        main_nodes = []
        for key in comp_nodes.get(main_comp, set()):
            point = nodes.get(key)
            if point is None:
                continue
            inserted = insert_projection_node(
                point, road_nodes, road_adjacency, road_segments,
                snap_tol=args.road_node_snap_m, max_snap_m=args.max_road_snap_m
            )
            if inserted:
                main_nodes.append(inserted[0])

        if main_nodes:
            dist_map, prev_map = dijkstra_multi_source(road_adjacency, main_nodes)
            connection_edges = []
            for comp_id, node_keys in comp_nodes.items():
                if comp_id == main_comp:
                    continue
                best_node = None
                best_dist = float("inf")
                for key in node_keys:
                    point = nodes.get(key)
                    if point is None:
                        continue
                    inserted = insert_projection_node(
                        point, road_nodes, road_adjacency, road_segments,
                        snap_tol=args.road_node_snap_m, max_snap_m=args.max_road_snap_m
                    )
                    if not inserted:
                        continue
                    node_id = inserted[0]
                    if node_id in dist_map and dist_map[node_id] < best_dist:
                        best_dist = dist_map[node_id]
                        best_node = node_id
                if best_node is None:
                    continue
                path = reconstruct_path_to_source(prev_map, best_node)
                if len(path) < 2:
                    continue
                coords = [road_nodes[n] for n in path]
                connection_edges.append(coords)

            for coords in connection_edges:
                props = {"ID": f"BASE_CONNECT_{len(features) + 1:04d}", "type": "connection_path"}
                geometry = {"type": "LineString", "coordinates": [[p[0], p[1]] for p in coords]}
                features.append(create_feature(geometry, props))
            connection_count = len(connection_edges)
        else:
            connection_count = 0
    else:
        connection_count = 0

    out_geo = create_feature_collection(features, crs="EPSG:32617")
    with open(args.output, "w") as f:
        json.dump(out_geo, f, indent=2)

    # Coverage stats
    min_dists = []
    for p in ont_points:
        best, d = nearest_road_for_point(p, selected)
        min_dists.append(d)

    within_min = sum(1 for d in min_dists if d <= args.min_distance_m)
    within_max = sum(1 for d in min_dists if d <= args.max_distance_m)

    print(f"Selected roads: {len(selected)}")
    print(f"MST edges output: {len(mst_edges)}")
    print(f"Connection paths added: {connection_count}")
    print(f"Skip low-ONT roads: {args.skip_low_ont} (min {args.min_ont_count})")
    print(f"ONTs within {args.min_distance_m}m: {within_min}/{len(min_dists)}")
    print(f"ONTs within {args.max_distance_m}m: {within_max}/{len(min_dists)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
