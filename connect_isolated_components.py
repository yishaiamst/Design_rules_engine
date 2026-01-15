#!/usr/bin/env python3
import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, "/Users/yishai/.cursor/worktrees/Design_rules_engine/cld/phases")
from phase3e_connect_isolated_cables import convert_wgs84_to_utm_coords


def euclidean_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def flatten_lines(geometry: Dict[str, Any]) -> List[List[List[float]]]:
    if geometry.get("type") == "LineString":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiLineString":
        return geometry.get("coordinates", [])
    return []


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


def build_segments(features: List[Dict[str, Any]]) -> List[Tuple[Tuple[float, float], Tuple[float, float], str]]:
    segments = []
    for feat in features:
        props = feat.get("properties", {})
        fid = feat.get("id") or props.get("id") or props.get("ID", "")
        for part in flatten_lines(feat.get("geometry", {})):
            if len(part) < 2:
                continue
            coords = [(float(p[0]), float(p[1])) for p in part]
            for i in range(len(coords) - 1):
                segments.append((coords[i], coords[i + 1], fid))
    return segments


def build_points(features: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    points = []
    for feat in features:
        for part in flatten_lines(feat.get("geometry", {})):
            if len(part) < 2:
                continue
            for p in part:
                points.append((float(p[0]), float(p[1])))
    return points


def is_wgs84_coords(sample: Tuple[float, float]) -> bool:
    x, y = sample
    return -180.0 <= x <= 180.0 and -90.0 <= y <= 90.0


def normalize_roads(roads_geojson: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
    # Convert roads to UTM if needed; return list of polylines
    polylines: List[List[Tuple[float, float]]] = []
    sample_coord = None
    for feature in roads_geojson.get("features", [])[:1]:
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if coords:
            if isinstance(coords[0], list) and len(coords[0]) >= 2:
                sample_coord = coords[0]
            elif len(coords) >= 2:
                sample_coord = coords[0]
            break

    needs_conversion = False
    if sample_coord:
        needs_conversion = is_wgs84_coords((float(sample_coord[0]), float(sample_coord[1])))

    for feature in roads_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        for part in flatten_lines(geometry):
            if len(part) < 2:
                continue
            coords = []
            for p in part:
                x, y = float(p[0]), float(p[1])
                if needs_conversion:
                    x, y = convert_wgs84_to_utm_coords(x, y, utm_zone=17)
                coords.append((x, y))
            if len(coords) >= 2:
                polylines.append(coords)
    return polylines


def nearest_point_on_polyline(
    point: Tuple[float, float], polyline: List[Tuple[float, float]]
) -> Tuple[Tuple[float, float], int, float, float]:
    # Returns (nearest_point, segment_index, t, distance)
    best = None
    for i in range(len(polyline) - 1):
        a = polyline[i]
        b = polyline[i + 1]
        q = nearest_point_on_segment(point[0], point[1], a[0], a[1], b[0], b[1])
        d = euclidean_distance(point, q)
        if best is None or d < best[3]:
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            seg_len = dx * dx + dy * dy
            t = 0.0
            if seg_len > 0:
                t = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / seg_len
                t = max(0.0, min(1.0, t))
            best = (q, i, t, d)
    return best  # type: ignore


def build_subpath_on_polyline(
    polyline: List[Tuple[float, float]],
    proj_a: Tuple[float, float],
    idx_a: int,
    proj_b: Tuple[float, float],
    idx_b: int,
) -> List[Tuple[float, float]]:
    if idx_a == idx_b:
        return [proj_a, proj_b]
    if idx_a < idx_b:
        path = [proj_a]
        path.extend(polyline[idx_a + 1 : idx_b + 1])
        path.append(proj_b)
        return path
    # reverse
    path = [proj_a]
    path.extend(reversed(polyline[idx_b + 1 : idx_a + 1]))
    path.append(proj_b)
    return path


def closest_points_between_segments(
    p1: Tuple[float, float],
    q1: Tuple[float, float],
    p2: Tuple[float, float],
    q2: Tuple[float, float],
) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
    # Returns closest points (c1 on p1-q1, c2 on p2-q2) and distance
    # Based on algorithm from geomalgorithms.com
    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1]

    u = (q1[0] - p1[0], q1[1] - p1[1])
    v = (q2[0] - p2[0], q2[1] - p2[1])
    w = (p1[0] - p2[0], p1[1] - p2[1])
    a = dot(u, u)
    b = dot(u, v)
    c = dot(v, v)
    d = dot(u, w)
    e = dot(v, w)
    D = a * c - b * b
    sc, sN, sD = 0.0, 0.0, D
    tc, tN, tD = 0.0, 0.0, D

    if D < 1e-9:
        sN = 0.0
        sD = 1.0
        tN = e
        tD = c
    else:
        sN = (b * e - c * d)
        tN = (a * e - b * d)
        if sN < 0.0:
            sN = 0.0
            tN = e
            tD = c
        elif sN > sD:
            sN = sD
            tN = e + b
            tD = c

    if tN < 0.0:
        tN = 0.0
        if -d < 0.0:
            sN = 0.0
        elif -d > a:
            sN = sD
        else:
            sN = -d
            sD = a
    elif tN > tD:
        tN = tD
        if (-d + b) < 0.0:
            sN = 0.0
        elif (-d + b) > a:
            sN = sD
        else:
            sN = (-d + b)
            sD = a

    sc = 0.0 if abs(sN) < 1e-9 else sN / sD
    tc = 0.0 if abs(tN) < 1e-9 else tN / tD

    c1 = (p1[0] + sc * u[0], p1[1] + sc * u[1])
    c2 = (p2[0] + tc * v[0], p2[1] + tc * v[1])
    return c1, c2, euclidean_distance(c1, c2)


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
            adjacency.setdefault(n1, []).append((n2, euclidean_distance(a, b)))
            adjacency.setdefault(n2, []).append((n1, euclidean_distance(a, b)))
            segments.append({"a": a, "b": b, "n1": n1, "n2": n2})

    return nodes, adjacency, segments


def insert_projection_node(
    point: Tuple[float, float],
    nodes: List[Tuple[float, float]],
    adjacency: Dict[int, List[Tuple[int, float]]],
    segments: List[Dict[str, Any]],
    snap_tol: float,
    max_snap_m: float,
    force_segment_index: Optional[int] = None,
) -> Optional[Tuple[int, Tuple[float, float], float, Optional[int]]]:
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

    return node_id, proj, dist, seg_index


def dijkstra(
    adjacency: Dict[int, List[Tuple[int, float]]],
    start: int,
    goal: int,
) -> Optional[List[int]]:
    import heapq

    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    visited = set()

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        if u == goal:
            break
        for v, w in adjacency.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if goal not in dist:
        return None

    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def path_length(coords: List[Tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        total += euclidean_distance(coords[i], coords[i + 1])
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connect isolated components to main component via roads."
    )
    parser.add_argument("--input-geojson", required=True, help="Input fiber GeoJSON")
    parser.add_argument("--components-report", required=True, help="Connectivity report JSON")
    parser.add_argument("--roads", required=True, help="Roads GeoJSON (UTM or WGS84)")
    parser.add_argument("--output", required=True, help="Output GeoJSON for connections")
    parser.add_argument("--max-road-deviation-m", type=float, default=200.0)
    parser.add_argument("--max-road-snap-m", type=float, default=50.0)
    parser.add_argument("--road-node-snap-m", type=float, default=0.5)
    args = parser.parse_args()

    with open(args.input_geojson, "r") as f:
        fiber = json.load(f)
    with open(args.components_report, "r") as f:
        report = json.load(f)
    with open(args.roads, "r") as f:
        roads = json.load(f)

    main_component_id = report.get("main_component_id")
    isolated_component_ids = report.get("isolated_component_ids", [])

    components = report.get("components", [])
    comp_to_features = {
        c["component_id"]: set(c.get("feature_ids", [])) for c in components
    }

    # Build feature lookup
    feature_lookup: Dict[str, Dict[str, Any]] = {}
    for idx, feat in enumerate(fiber.get("features", [])):
        props = feat.get("properties", {})
        fid = feat.get("id") or props.get("id") or props.get("ID") or f"feature_{idx}"
        feature_lookup[fid] = feat

    main_features = [feature_lookup[fid] for fid in comp_to_features.get(main_component_id, [])]
    main_segments = build_segments(main_features)
    road_polylines = normalize_roads(roads)
    road_nodes, road_adjacency, road_segments = build_road_graph(
        road_polylines, snap_tol=args.road_node_snap_m
    )

    output_features = []

    for comp_id in isolated_component_ids:
        iso_fids = comp_to_features.get(comp_id, [])
        iso_features = [feature_lookup[fid] for fid in iso_fids if fid in feature_lookup]
        iso_points = build_points(iso_features)

        if not iso_points or not main_segments:
            continue

        # Precompute candidate main-road projections (closest road segment per main segment)
        main_candidates = []
        for (a, b, main_fid) in main_segments:
            best = None
            for i, seg in enumerate(road_segments):
                r1 = seg["a"]
                r2 = seg["b"]
                main_pt, road_pt, d = closest_points_between_segments(a, b, r1, r2)
                if best is None or d < best["distance_m"]:
                    best = {
                        "main_point": main_pt,
                        "road_point": road_pt,
                        "road_seg_index": i,
                        "main_feature_id": main_fid,
                        "distance_m": d,
                    }
            if best and best["distance_m"] <= args.max_road_snap_m:
                main_candidates.append(best)

        # Try all points on the isolated component and pick the best road-based path
        best_road = None
        for p in iso_points:
            iso_insert = insert_projection_node(
                p,
                road_nodes,
                road_adjacency,
                road_segments,
                snap_tol=args.road_node_snap_m,
                max_snap_m=args.max_road_snap_m,
            )
            if iso_insert is None:
                continue
            iso_node, iso_proj, iso_offroad, _ = iso_insert

            for cand in main_candidates:
                main_insert = insert_projection_node(
                    cand["road_point"],
                    road_nodes,
                    road_adjacency,
                    road_segments,
                    snap_tol=args.road_node_snap_m,
                    max_snap_m=args.max_road_snap_m,
                    force_segment_index=cand["road_seg_index"],
                )
                if main_insert is None:
                    continue
                main_node, main_proj, main_offroad, _ = main_insert
                node_path = dijkstra(road_adjacency, iso_node, main_node)
                if node_path is None:
                    continue
                road_path = [road_nodes[nid] for nid in node_path]
                road_path_tuples = [p, iso_proj] + road_path + [main_proj, cand["main_point"]]
                total_len = path_length(road_path_tuples)
                if best_road is None or total_len < best_road["distance_path_m"]:
                    best_road = {
                        "road_path_tuples": road_path_tuples,
                        "iso_point": p,
                        "main_point": cand["main_point"],
                        "main_feature_id": cand["main_feature_id"],
                        "distance_path_m": total_len,
                    }

        if best_road is None:
            continue

        road_path_tuples = best_road["road_path_tuples"]
        iso_point = best_road["iso_point"]
        main_point = best_road["main_point"]
        main_feature_id = best_road["main_feature_id"]

        output_features.append({
            "type": "Feature",
            "properties": {
                "type": "connection_path",
                "component_id": comp_id,
                "main_component_id": main_component_id,
                "from_feature_ids": sorted(list(iso_fids)),
                "to_feature_id": main_feature_id,
                "distance_direct_m": euclidean_distance(iso_point, main_point),
                "distance_path_m": path_length(road_path_tuples),
                "uses_road": True,
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[p[0], p[1]] for p in road_path_tuples],
            },
        })

        output_features.append({
            "type": "Feature",
            "properties": {
                "type": "isolated_connection_point",
                "component_id": comp_id,
                "from_feature_ids": sorted(list(iso_fids)),
            },
            "geometry": {
                "type": "Point",
                "coordinates": [iso_point[0], iso_point[1]],
            },
        })

        output_features.append({
            "type": "Feature",
            "properties": {
                "type": "main_connection_point",
                "component_id": comp_id,
                "to_feature_id": main_feature_id,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [main_point[0], main_point[1]],
            },
        })

    out_geojson = {
        "type": "FeatureCollection",
        "features": output_features,
    }
    if "crs" in fiber:
        out_geojson["crs"] = fiber["crs"]

    with open(args.output, "w") as f:
        json.dump(out_geojson, f, indent=2)

    print(f"Created {len(output_features)} features in {args.output}")


if __name__ == "__main__":
    main()
