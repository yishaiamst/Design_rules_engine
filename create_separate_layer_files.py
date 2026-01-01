#!/usr/bin/env python3
"""
Create separate GeoJSON files for each layer to improve visualization compatibility.
This helps QGIS and other viewers properly render colors and symbols.
"""

import json
import os
from collections import defaultdict

def split_visualization_into_layers(input_file, output_dir="test_output/layers"):
    """Split a large GeoJSON into separate files per layer."""
    print(f"Loading {input_file}...")
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Group features by layer
    layers = defaultdict(list)
    
    for feature in data.get('features', []):
        layer = feature.get('properties', {}).get('layer', 'unknown')
        layers[layer].append(feature)
    
    print(f"\nFound {len(layers)} layers:")
    for layer, features in sorted(layers.items()):
        print(f"  {layer}: {len(features):,} features")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Write separate files for each layer
    print(f"\nWriting separate layer files to {output_dir}/...")
    for layer, features in layers.items():
        filename = f"{layer}.geojson"
        filepath = os.path.join(output_dir, filename)
        
        layer_geojson = {
            "type": "FeatureCollection",
            "crs": data.get("crs", {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:EPSG::32617"}
            }),
            "features": features
        }
        
        with open(filepath, 'w') as f:
            json.dump(layer_geojson, f, indent=2)
        
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  ✓ {filename}: {len(features):,} features ({size_mb:.1f} MB)")
    
    print(f"\n✓ Created {len(layers)} layer files in {output_dir}/")
    return layers

def main():
    print("=" * 80)
    print("SPLITTING VISUALIZATION INTO SEPARATE LAYER FILES")
    print("=" * 80)
    print()
    
    # Split UTM version (more accurate coordinates)
    print("Processing UTM version...")
    split_visualization_into_layers(
        "test_output/network_visualization_utm.geojson",
        "test_output/layers_utm"
    )
    
    print()
    print("=" * 80)
    print("DONE")
    print("=" * 80)
    print()
    print("You can now load individual layer files in QGIS:")
    print("  - terminals.geojson (MSTs and Aerial Terminals)")
    print("  - fosc.geojson (FOSCs)")
    print("  - fiber_cable.geojson (Fiber cables)")
    print("  - drop_cable.geojson (Drop cables)")
    print("  - ont.geojson (ONTs)")
    print("  - olt.geojson (OLTs)")
    print()
    print("This should improve rendering of colors and symbols.")

if __name__ == "__main__":
    main()
