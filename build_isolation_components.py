#!/usr/bin/env python3
import argparse
import json
import math
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Tuple


def looks_like_lonlat(coords: List[List[float]]) -> bool:
    for x, y in coords:
        if abs(x) > 180 or abs(y) > 90:
            return False
    return True


def to_web_mercator(lon: float, lat: float) -> Tuple[float, float]:
    # EPSG:3857 projection
    r = 6378137.0
    x = math.radians(lon) * r
    lat = max(min(lat, 89.9999), -89.9999)
    y = r * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def euclidean_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def point_to_line_distance(px, py, x1, y1, x2, y2) -> float:
    A = px - x1
    B = py - y1
    C = x2 - x1
    D = y2 - y1
    dot = A * C + B * D
    len_sq = C * C + D * D
    if len_sq == 0:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    param = dot / len_sq
    if param < 0:
        xx, yy = x1, y1
    elif param > 1:
        xx, yy = x2, y2
    else:
        xx, yy = x1 + param * C, y1 + param * D
    return math.sqrt((px - xx) ** 2 + (py - yy) ** 2)


def flatten_lines(geometry: Dict[str, Any]) -> List[List[List[float]]]:
    if geometry.get("type") == "LineString":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiLineString":
        return geometry.get("coordinates", [])
    return []


def snap_endpoints(lines: List[Dict[str, Any]], snap_tol: float) -> None:
    # Snap endpoints within tolerance using a grid index
    grid = defaultdict(list)
    reps: List[Tuple[float, float]] = []

    def grid_key(pt: Tuple[float, float]) -> Tuple[int, int]:
        return (int(pt[0] // snap_tol), int(pt[1] // snap_tol))

    def find_rep(pt: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        gx, gy = grid_key(pt)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for idx in grid.get((gx + dx, gy + dy), []):
                    rep = reps[idx]
                    if euclidean_distance(pt, rep) <= snap_tol:
                        return rep
        return None

    def add_rep(pt: Tuple[float, float]) -> Tuple[float, float]:
        reps.append(pt)
        idx = len(reps) - 1
        grid[grid_key(pt)].append(idx)
        return pt

    for item in lines:
        coords = item["coords"]
        if len(coords) < 2:
            continue
        endpoints = [coords[0], coords[-1]]
        for ep_index, ep in enumerate(endpoints):
            rep = find_rep(ep)
            if rep is None:
                rep = add_rep(ep)
            if ep_index == 0:
                coords[0] = rep
            else:
                coords[-1] = rep


def segment_intersection(
    a1: Tuple[float, float],
    a2: Tuple[float, float],
    b1: Tuple[float, float],
    b2: Tuple[float, float],
    eps: float = 1e-9,
) -> List[Tuple[float, float]]:
    # Returns intersection points (0,1, or 2 for overlapping endpoints)
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2

    def det(ax, ay, bx, by):
        return ax * by - ay * bx

    dx1 = x2 - x1
    dy1 = y2 - y1
    dx2 = x4 - x3
    dy2 = y4 - y3

    denom = det(dx1, dy1, dx2, dy2)
    if abs(denom) < eps:
        # Parallel or colinear
        # If colinear, include endpoints that lie on the other segment
        if abs(det(x3 - x1, y3 - y1, dx1, dy1)) > eps:
            return []
        points = []
        for p in [a1, a2, b1, b2]:
            if point_to_line_distance(p[0], p[1], x1, y1, x2, y2) <= eps and \
               min(x1, x2) - eps <= p[0] <= max(x1, x2) + eps and \
               min(y1, y2) - eps <= p[1] <= max(y1, y2) + eps and \
               min(x3, x4) - eps <= p[0] <= max(x3, x4) + eps and \
               min(y3, y4) - eps <= p[1] <= max(y3, y4) + eps:
                points.append(p)
        # Deduplicate
        uniq = []
        for p in points:
            if not any(euclidean_distance(p, q) <= eps for q in uniq):
                uniq.append(p)
        return uniq

    t = det(x3 - x1, y3 - y1, dx2, dy2) / denom
    u = det(x3 - x1, y3 - y1, dx1, dy1) / denom
    if 0 - eps <= t <= 1 + eps and 0 - eps <= u <= 1 + eps:
        return [(x1 + t * dx1, y1 + t * dy1)]
    return []


def build_nodes(points: List[Tuple[float, float]], snap_tol: float) -> Dict[Tuple[float, float], int]:
    node_ids: Dict[Tuple[float, float], int] = {}
    grid = defaultdict(list)

    def grid_key(pt: Tuple[float, float]) -> Tuple[int, int]:
        return (int(pt[0] // snap_tol), int(pt[1] // snap_tol))

    for pt in points:
        gx, gy = grid_key(pt)
        found = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for existing in grid.get((gx + dx, gy + dy), []):
                    if euclidean_distance(pt, existing) <= snap_tol:
                        found = existing
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is None:
            node_ids[pt] = len(node_ids)
            grid[(gx, gy)].append(pt)
        else:
            if found not in node_ids:
                node_ids[found] = len(node_ids)
            node_ids[pt] = node_ids[found]

    return node_ids


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build connectivity graph and find isolated components."
    )
    parser.add_argument("--input", required=True, help="Input GeoJSON file")
    parser.add_argument("--output-report", required=True, help="Output JSON report")
    parser.add_argument("--output-geojson", required=True, help="Output GeoJSON annotated")
    parser.add_argument("--snap-tol-m", type=float, default=0.5, help="Snap tolerance in meters")
    parser.add_argument(
        "--main-by",
        choices=["length", "feature_count"],
        default="length",
        help="How to choose main component",
    )
    parser.add_argument("--min-component-length-m", type=float, default=0.0)
    parser.add_argument("--min-component-feature-count", type=int, default=0)
    args = parser.parse_args()

    with open(args.input, "r") as f:
        geo = json.load(f)

    features = geo.get("features", [])
    # Build line parts with feature ids
    lines = []
    all_coords = []
    for idx, feat in enumerate(features):
        props = feat.get("properties", {})
        fid = feat.get("id")
        if not fid:
            fid = props.get("id") or props.get("ID") or f"feature_{idx}"
        for part in flatten_lines(feat.get("geometry", {})):
            if len(part) < 2:
                continue
            coords = [(float(p[0]), float(p[1])) for p in part]
            lines.append({"feature_id": fid, "coords": coords})
            all_coords.extend(coords)

    if not all_coords:
        raise SystemExit("No line geometry found in input.")

    is_lonlat = looks_like_lonlat(all_coords)
    if is_lonlat:
        for item in lines:
            item["coords"] = [to_web_mercator(x, y) for x, y in item["coords"]]

    snap_endpoints(lines, args.snap_tol_m)

    # Build segments
    segments = []
    for li, item in enumerate(lines):
        coords = item["coords"]
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            segments.append({
                "p1": p1,
                "p2": p2,
                "feature_id": item["feature_id"],
                "line_index": li,
            })

    # Find intersections and split segments
    seg_points = [set() for _ in segments]
    for i, seg in enumerate(segments):
        seg_points[i].add(seg["p1"])
        seg_points[i].add(seg["p2"])

    for i in range(len(segments)):
        s1 = segments[i]
        a1, a2 = s1["p1"], s1["p2"]
        for j in range(i + 1, len(segments)):
            s2 = segments[j]
            b1, b2 = s2["p1"], s2["p2"]
            for pt in segment_intersection(a1, a2, b1, b2):
                seg_points[i].add(pt)
                seg_points[j].add(pt)

    # Build edges
    all_node_points = []
    edges = []
    for i, seg in enumerate(segments):
        pts = list(seg_points[i])
        p1 = seg["p1"]
        p2 = seg["p2"]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        def t_param(p):
            if abs(dx) >= abs(dy):
                return (p[0] - p1[0]) / dx if dx != 0 else 0.0
            return (p[1] - p1[1]) / dy if dy != 0 else 0.0
        pts.sort(key=t_param)
        for k in range(len(pts) - 1):
            a = pts[k]
            b = pts[k + 1]
            if euclidean_distance(a, b) < 1e-9:
                continue
            edges.append({
                "a": a,
                "b": b,
                "feature_id": seg["feature_id"],
                "length": euclidean_distance(a, b),
            })
            all_node_points.extend([a, b])

    node_ids = build_nodes(all_node_points, args.snap_tol_m)

    # Build graph
    adjacency = defaultdict(set)
    edge_records = []
    for e in edges:
        na = node_ids[e["a"]]
        nb = node_ids[e["b"]]
        adjacency[na].add(nb)
        adjacency[nb].add(na)
        edge_records.append({
            "n1": na,
            "n2": nb,
            "feature_id": e["feature_id"],
            "length": e["length"],
        })

    # Components
    visited = set()
    components = []
    node_to_component = {}
    for node in adjacency.keys():
        if node in visited:
            continue
        q = deque([node])
        visited.add(node)
        comp_nodes = []
        while q:
            n = q.popleft()
            comp_nodes.append(n)
            node_to_component[n] = len(components)
            for neigh in adjacency[n]:
                if neigh not in visited:
                    visited.add(neigh)
                    q.append(neigh)
        components.append({"nodes": comp_nodes})

    # Assign edges to components and compute metrics
    for comp in components:
        comp["edges"] = []
        comp["feature_ids"] = set()
        comp["total_length_m"] = 0.0
    for e in edge_records:
        c_id = node_to_component.get(e["n1"])
        if c_id is None:
            continue
        comp = components[c_id]
        comp["edges"].append(e)
        comp["feature_ids"].add(e["feature_id"])
        comp["total_length_m"] += e["length"]

    for comp in components:
        comp["feature_ids"] = sorted(list(comp["feature_ids"]))
        comp["feature_count"] = len(comp["feature_ids"])
        comp["edge_count"] = len(comp["edges"])
        comp["node_count"] = len(comp["nodes"])

    # Pick main component
    main_component_id = None
    if components:
        if args.main_by == "feature_count":
            main_component_id = max(
                range(len(components)),
                key=lambda i: components[i]["feature_count"],
            )
        else:
            main_component_id = max(
                range(len(components)),
                key=lambda i: components[i]["total_length_m"],
            )

    # Isolation rules
    isolated_component_ids = []
    for i, comp in enumerate(components):
        if i == main_component_id:
            continue
        if comp["total_length_m"] < args.min_component_length_m:
            isolated_component_ids.append(i)
            continue
        if comp["feature_count"] < args.min_component_feature_count:
            isolated_component_ids.append(i)
            continue
        isolated_component_ids.append(i)

    # Annotate GeoJSON with component ids
    feature_to_component = {}
    for i, comp in enumerate(components):
        for fid in comp["feature_ids"]:
            feature_to_component[fid] = i

    annotated = json.loads(json.dumps(geo))
    for idx, feat in enumerate(annotated.get("features", [])):
        props = feat.setdefault("properties", {})
        fid = feat.get("id") or props.get("id") or props.get("ID") or f"feature_{idx}"
        comp_id = feature_to_component.get(fid, -1)
        props["component_id"] = comp_id
        props["is_isolated_component"] = comp_id in isolated_component_ids
        props["main_component"] = comp_id == main_component_id

    report = {
        "input": args.input,
        "snap_tol_m": args.snap_tol_m,
        "main_by": args.main_by,
        "main_component_id": main_component_id,
        "min_component_length_m": args.min_component_length_m,
        "min_component_feature_count": args.min_component_feature_count,
        "component_count": len(components),
        "isolated_component_ids": isolated_component_ids,
        "components": [
            {
                "component_id": i,
                "feature_count": c["feature_count"],
                "total_length_m": c["total_length_m"],
                "node_count": c["node_count"],
                "edge_count": c["edge_count"],
                "feature_ids": c["feature_ids"],
            }
            for i, c in enumerate(components)
        ],
    }

    with open(args.output_report, "w") as f:
        json.dump(report, f, indent=2)
    with open(args.output_geojson, "w") as f:
        json.dump(annotated, f, indent=2)

    print(f"Components: {len(components)}")
    print(f"Main component: {main_component_id}")
    print(f"Isolated components: {isolated_component_ids}")
    print(f"Report: {args.output_report}")
    print(f"Annotated GeoJSON: {args.output_geojson}")


if __name__ == "__main__":
    main()
