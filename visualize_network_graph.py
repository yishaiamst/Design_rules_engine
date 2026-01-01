#!/usr/bin/env python3
"""
Visualize Network Graph
Creates a comprehensive GeoJSON visualization of all network layers:
- Fiber cables (infrastructure)
- FOSCs
- Terminals (Aerial and MST)
- Drop cables
- ONTs
- OLTs
"""

import json
from utils.geojson_utils import load_geojson, create_feature, create_feature_collection
from utils.config_loader import load_config
from utils.coordinate_transform import transform_geojson_to_wgs84
from phases.phase0_community_pockets import create_community_pockets
from phases.phase1_place_olts import place_olts
from phases.phase3_place_terminals import place_terminals
from phases.phase3b_refine_mst_placement import refine_mst_placement
from phases.phase6_cable_sizing import size_cables
from utils.network_graph import build_network_graph
from utils.drop_cable_builder import create_drop_cables_for_onts


def create_visualization_geojson(
    fiber_cable_geojson,
    olts,
    ont_geojson,
    foscs,
    terminals,
    drop_cables,
    sized_cables=None,
    transform_to_wgs84_flag=True
):
    """
    Create a comprehensive GeoJSON visualization with all network layers.
    Each layer has distinct styling for easy identification.
    
    Args:
        transform_to_wgs84_flag: If True, transform coordinates to WGS84. If False, keep in UTM.
    """
    if transform_to_wgs84_flag:
        from utils.coordinate_transform import transform_to_wgs84 as transform_coords
    else:
        # No transformation - return coordinates as-is
        def transform_coords(coords, epsg=None):
            return coords
    
    features = []
    
    # Layer 1: Fiber Cables (Infrastructure)
    print("  Adding fiber cables...")
    for feature in fiber_cable_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        # Transform coordinates if flag is set
        coords = geometry.get("coordinates", [])
        if coords and transform_to_wgs84_flag:
            geom_type = geometry.get("type", "")
            if geom_type == "LineString":
                transformed_coords = [transform_coords(coord, 32617) for coord in coords]
                geometry = {**geometry, "coordinates": transformed_coords}
            elif geom_type == "MultiLineString":
                transformed_coords = [[transform_coords(coord, 32617) for coord in line] for line in coords]
                geometry = {**geometry, "coordinates": transformed_coords}
        
        # Get size from sized_cables if available
        fiber_count = props.get("FiberCount") or props.get("Size", "48F")
        if isinstance(fiber_count, str):
            fiber_count = int(fiber_count.replace("F", ""))
        
        # Color based on size
        size_colors = {
            12: "#FF6B6B",   # Red
            24: "#FF8E53",   # Orange
            48: "#FFA500",   # Orange
            72: "#FFD700",   # Gold
            96: "#ADFF2F",   # Green-Yellow
            144: "#32CD32",  # Lime Green
            288: "#00CED1"   # Dark Turquoise
        }
        color = size_colors.get(fiber_count, "#808080")  # Gray for unknown
        
        vis_feature = create_feature(
            geometry=geometry,
            properties={
                **props,
                "layer": "fiber_cable",
                "fiber_count": fiber_count,
                "stroke": color,
                "strokeWidth": 3,
                "stroke-opacity": 1.0,
                "fill": color,
                "fill-opacity": 0.5,
                "description": f"Fiber Cable: {fiber_count}F"
            }
        )
        features.append(vis_feature)
    
    # Layer 2: FOSCs
    print("  Adding FOSCs...")
    for fosc in foscs:
        fosc_pos = fosc.get("position")
        fosc_id = fosc.get("fosc_id") or fosc.get("id", "")
        
        if fosc_pos:
            # Transform to WGS84 if flag is set
            fosc_coords = transform_coords([fosc_pos[0], fosc_pos[1]], 32617) if transform_to_wgs84_flag else [fosc_pos[0], fosc_pos[1]]
            vis_feature = create_feature(
                geometry={
                    "type": "Point",
                    "coordinates": fosc_coords
                },
                properties={
                    "layer": "fosc",
                    "fosc_id": fosc_id,
                    "marker-color": "#FF0000",  # Red
                    "marker-size": "large",
                    "marker-symbol": "circle",
                    "marker-opacity": 1.0,
                    "description": f"FOSC: {fosc_id}"
                }
            )
            features.append(vis_feature)
    
    # Layer 3: Terminals (Aerial and MST)
    print("  Adding terminals...")
    for terminal in terminals:
        terminal_pos = terminal.get("position")
        terminal_id = terminal.get("terminal_id") or terminal.get("id", "")
        terminal_type = terminal.get("type", "Unknown")
        
        if terminal_pos:
            # Transform to WGS84 if flag is set
            terminal_coords = transform_coords([terminal_pos[0], terminal_pos[1]], 32617) if transform_to_wgs84_flag else [terminal_pos[0], terminal_pos[1]]
            # Different colors for Aerial vs MST
            if terminal_type == "Aerial Terminal":
                color = "#0000FF"  # Blue
                symbol = "square"
            elif terminal_type == "MST":
                color = "#800080"  # Purple
                symbol = "triangle"  # Triangle for MSTs - ensure this renders correctly
                # Some viewers use different symbol names, try both
                marker_symbol = "triangle"  # Standard GeoJSON symbol  # Triangle symbol for MSTs
            else:
                color = "#808080"  # Gray
                symbol = "circle"
            
            vis_feature = create_feature(
                geometry={
                    "type": "Point",
                    "coordinates": terminal_coords
                },
                properties={
                    "layer": "terminal",
                    "terminal_id": terminal_id,
                    "terminal_type": terminal_type,
                    "marker-color": color,
                    "marker-size": "medium",
                    "marker-symbol": symbol,
                    "marker-opacity": 1.0,
                    "description": f"{terminal_type}: {terminal_id}"
                }
            )
            features.append(vis_feature)
    
    # Layer 4: Drop Cables
    print("  Adding drop cables...")
    for drop_cable in drop_cables:
        coords = drop_cable.get("coordinates", [])
        if len(coords) >= 2:
            # Transform to WGS84 if flag is set
            transformed_coords = [transform_coords([c[0], c[1]], 32617) if transform_to_wgs84_flag else [c[0], c[1]] for c in coords]
            vis_feature = create_feature(
                geometry={
                    "type": "LineString",
                    "coordinates": transformed_coords
                },
                properties={
                    "layer": "drop_cable",
                    "drop_cable_id": drop_cable.get("drop_cable_id", ""),
                    "ont_id": drop_cable.get("ont_id", ""),
                    "terminal_id": drop_cable.get("terminal_id", ""),
                    "terminal_type": drop_cable.get("terminal_type", ""),
                    "length_m": drop_cable.get("length_m", 0),
                    "stroke": "#00FF00",  # Green
                    "strokeWidth": 1,
                    "stroke-opacity": 0.8,
                    "description": f"Drop Cable: {drop_cable.get('ont_id')} → {drop_cable.get('terminal_id')}"
                }
            )
            features.append(vis_feature)
    
    # Layer 5: ONTs
    print("  Adding ONTs...")
    ont_count = 0
    for feature in ont_geojson.get("features", []):
        geometry = feature.get("geometry", {})
        props = feature.get("properties", {})
        
        if geometry.get("type") == "Point":
            # Transform to WGS84 if flag is set
            coords = geometry.get("coordinates", [])
            if coords and len(coords) >= 2:
                if transform_to_wgs84_flag:
                    transformed_coords = transform_coords([coords[0], coords[1]], 32617)
                    geometry = {"type": "Point", "coordinates": transformed_coords}
                # else keep as-is
            vis_feature = create_feature(
                geometry=geometry,
                properties={
                    **props,
                    "layer": "ont",
                    "ont_id": props.get("ID") or props.get("id", ""),
                    "marker-color": "#FFFF00",  # Yellow
                    "marker-size": "small",
                    "marker-symbol": "dot",
                    "marker-opacity": 1.0,
                    "description": f"ONT: {props.get('ID') or props.get('id', '')}"
                }
            )
            features.append(vis_feature)
            ont_count += 1
    
    print(f"    Added {ont_count} ONTs")
    
    # Layer 6: OLTs
    print("  Adding OLTs...")
    for olt in olts:
        olt_pos = olt.get("position")
        olt_id = olt.get("olt_id") or olt.get("id", "")
        
        if olt_pos:
            # Transform to WGS84 if flag is set
            olt_coords = transform_coords([olt_pos[0], olt_pos[1]], 32617) if transform_to_wgs84_flag else [olt_pos[0], olt_pos[1]]
            vis_feature = create_feature(
                geometry={
                    "type": "Point",
                    "coordinates": olt_coords
                },
                properties={
                    "layer": "olt",
                    "olt_id": olt_id,
                    "ont_count": olt.get("ont_count", 0),
                    "marker-color": "#FF00FF",  # Magenta
                    "marker-size": "large",
                    "marker-symbol": "star",
                    "marker-opacity": 1.0,
                    "description": f"OLT: {olt_id} ({olt.get('ont_count', 0)} ONTs)"
                }
            )
            features.append(vis_feature)
    
    return create_feature_collection(features)


def main():
    print("=" * 80)
    print("NETWORK GRAPH VISUALIZATION")
    print("=" * 80)
    print()
    
    # Load data
    print("Loading data...")
    ont_geojson = load_geojson("ONT.geojson")
    fiber_cable_geojson = load_geojson("fiber cable.geojson")
    config = load_config("design_config.json")
    
    # Run pipeline
    print()
    print("Running pipeline...")
    pockets = create_community_pockets(ont_geojson, fiber_cable_geojson, config)
    olts, _ = place_olts(pockets, fiber_cable_geojson, ont_geojson, config)
    terminals, foscs, _ = place_terminals(ont_geojson, fiber_cable_geojson, olts, config)
    
    # Phase 3b: Refine MST placement (fix long drop cables)
    print()
    print("Refining MST placement (Phase 3b)...")
    try:
        terminals_before = len(terminals)
        mst_count_before = sum(1 for t in terminals if t.get("type") == "MST")
        
        terminals, foscs, new_msts, phase3b_summary = refine_mst_placement(
            terminals,
            foscs,
            ont_geojson,
            fiber_cable_geojson,
            config
        )
        
        terminals_after = len(terminals)
        mst_count_after = sum(1 for t in terminals if t.get("type") == "MST")
        
        print(f"  ✓ Before: {terminals_before} terminals ({mst_count_before} MSTs)")
        print(f"  ✓ After: {terminals_after} terminals ({mst_count_after} MSTs)")
        print(f"  ✓ Added {len(new_msts)} new MSTs")
        print(f"  ✓ Fixed {phase3b_summary.get('long_drop_cables_fixed', 0)} drop cables")
        
        # Verify new MSTs are in terminals list
        new_mst_ids = {m.get("terminal_id") for m in new_msts}
        terminal_ids = {t.get("terminal_id") for t in terminals}
        found = new_mst_ids & terminal_ids
        if len(found) < len(new_mst_ids):
            print(f"  ⚠️  Warning: Only {len(found)}/{len(new_mst_ids)} new MSTs found in terminals list")
    except Exception as e:
        print(f"  ⚠️  Phase 3b error: {e}")
        import traceback
        traceback.print_exc()
    
    # Create drop cables
    print()
    print("Creating drop cables...")
    drop_cables = create_drop_cables_for_onts(ont_geojson, terminals, config=config, tolerance_m=1000.0)
    
    # Size cables (optional - for getting sized cable info)
    print("Sizing cables...")
    sized_cables, _ = size_cables(
        fiber_cable_geojson,
        foscs,
        terminals,
        olts,
        ont_geojson,
        config
    )
    
    # Create visualization (with WGS84 transformation)
    print()
    print("Creating visualization GeoJSON (WGS84)...")
    vis_geojson = create_visualization_geojson(
        fiber_cable_geojson,
        olts,
        ont_geojson,
        foscs,
        terminals,
        drop_cables,
        sized_cables,
        transform_to_wgs84_flag=True
    )
    
    # Coordinate transformation note:
    # Manual UTM to WGS84 conversion may have accuracy issues
    # If cables appear in wrong locations, consider:
    # 1. Installing pyproj: pip3 install pyproj (for accurate transformation)
    # 2. Or keeping coordinates in UTM and setting CRS in viewer
    # Save to file
    output_path = "test_output/network_visualization.geojson"
    import os
    os.makedirs("test_output", exist_ok=True)
    
    # Add CRS information to GeoJSON
    vis_geojson["crs"] = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:EPSG::4326"  # WGS84
        }
    }
    
    with open(output_path, "w") as f:
        json.dump(vis_geojson, f, indent=2)
    
    # Also create a version with original UTM coordinates (for comparison)
    print()
    print("  Creating UTM version (no transformation) for comparison...")
    vis_geojson_utm = create_visualization_geojson(
        fiber_cable_geojson,
        olts,
        ont_geojson,
        foscs,
        terminals,
        drop_cables,
        sized_cables,
        transform_to_wgs84_flag=False
    )
    # Don't transform - keep in UTM
    vis_geojson_utm["crs"] = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:EPSG::32617"  # UTM Zone 17N
        }
    }
    
    utm_output_path = "test_output/network_visualization_utm.geojson"
    with open(utm_output_path, "w") as f:
        json.dump(vis_geojson_utm, f, indent=2)
    
    print(f"  ✓ Also saved UTM version (no transformation) to: {utm_output_path}")
    print("    Use this if WGS84 version shows cables in wrong locations")
    
    print()
    print("=" * 80)
    print("VISUALIZATION COMPLETE")
    print("=" * 80)
    print()
    print(f"✓ Saved visualization to: {output_path}")
    print(f"  Total features: {len(vis_geojson.get('features', []))}")
    print()
    print("Layer breakdown:")
    layer_counts = {}
    for feature in vis_geojson.get("features", []):
        layer = feature.get("properties", {}).get("layer", "unknown")
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
    
    for layer, count in sorted(layer_counts.items()):
        print(f"  {layer}: {count:,}")
    print()
    print("You can view this file in QGIS, Mapbox, or any GeoJSON viewer.")
    print("Layer colors:")
    print("  - Fiber cables: Orange/Yellow/Green (by size)")
    print("  - FOSCs: Red circles")
    print("  - Aerial Terminals: Blue squares")
    print("  - MSTs: Purple triangles")
    print("  - Drop cables: Green lines")
    print("  - ONTs: Yellow dots")
    print("  - OLTs: Magenta stars")
    print()


if __name__ == "__main__":
    main()
