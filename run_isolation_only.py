#!/usr/bin/env python3
import argparse
import json
from typing import Any, Dict

from phases.phase3e_connect_isolated_cables import connect_isolated_cables


def load_geojson(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def write_geojson(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run isolation-only pass and output fiber_cable_no_isolation.geojson"
    )
    parser.add_argument(
        "--cables",
        required=True,
        help="Input fiber cable GeoJSON (e.g. test_inputs/small_area/fiber cable.geojson)",
    )
    parser.add_argument(
        "--roads",
        default=None,
        help="Optional roads GeoJSON for alignment (EPSG:32617).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for fiber_cable_no_isolation.geojson",
    )
    parser.add_argument(
        "--geometry-threshold-m",
        type=float,
        default=5.0,
        help="Geometry isolation threshold in meters (default 5.0)",
    )
    parser.add_argument(
        "--max-connection-distance-m",
        type=float,
        default=3000.0,
        help="Max distance to connect isolated cables (default 3000.0)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max passes to connect isolated islands (default 5)",
    )
    args = parser.parse_args()

    cables = load_geojson(args.cables)
    roads = load_geojson(args.roads) if args.roads else None

    updated_cables, new_foscs, summary = connect_isolated_cables(
        cables_geojson=cables,
        foscs=[],
        tolerance_m=50.0,
        max_connection_distance_m=args.max_connection_distance_m,
        max_iterations=args.max_iterations,
        terminals=None,
        olts=None,
        roads_geojson=roads,
        geometry_isolation_threshold_m=args.geometry_threshold_m,
    )

    write_geojson(args.output, updated_cables)

    print("=" * 80)
    print("Isolation-only run complete")
    print(f"Input cables:  {len(cables.get('features', []))}")
    print(f"Output cables: {len(updated_cables.get('features', []))}")
    print(f"New FOSCs:     {len(new_foscs)}")
    print(f"Summary:       {summary}")
    print(f"Output:        {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
