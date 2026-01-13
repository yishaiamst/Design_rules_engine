# Test Inputs

This folder contains the original, unprocessed input GeoJSON files for testing.

## Structure

```
test_inputs/
  small_area/
    - ONT.geojson          # Original ONT points
    - fiber cable.geojson  # Original fiber cable infrastructure
```

## Usage

These files are the **starting point** for design generation. They should NOT be modified.

When running tests:
1. Use files from `test_inputs/` as input
2. Output results to `test_output/` folder
3. Keep inputs separate from outputs for reference

## Example

```python
from generate_design import generate_design

# Use original input files
result = generate_design(
    ont_geojson_path="test_inputs/small_area/ONT.geojson",
    fiber_cable_geojson_path="test_inputs/small_area/fiber cable.geojson",
    output_dir="test_output/small_area_design_fresh"
)
```
