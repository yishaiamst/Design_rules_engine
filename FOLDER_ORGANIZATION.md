# Folder Organization Guide

## Structure

```
project_root/
├── test_inputs/              # Original input files (reference - DO NOT MODIFY)
│   └── small_area/
│       ├── ONT.geojson
│       └── fiber cable.geojson
│
├── test_output/              # Generated results (can be regenerated)
│   ├── small_area_design_fresh/    # Fresh run results
│   ├── small_area_design_final/    # Previous results
│   └── ...
│
└── phases/                   # Design generation phases
    └── phase3e_connect_isolated_cables.py
```

## Principles

### 1. Input Files (test_inputs/)
- **Purpose**: Original, unprocessed GeoJSON files
- **Location**: `test_inputs/small_area/`
- **Rule**: **NEVER MODIFY** - These are reference files
- **Usage**: Always use these as starting point for fresh tests

### 2. Output Files (test_output/)
- **Purpose**: Generated design results
- **Location**: `test_output/small_area_design_*/`
- **Rule**: Can be regenerated anytime
- **Usage**: Contains all generated layers, summaries, and reports

### 3. Why This Matters

**Problem**: Using already-processed results as input:
- ❌ Results may have artifacts from previous runs
- ❌ Hard to verify if issues are from input or algorithm
- ❌ Can't reproduce exact starting conditions

**Solution**: Use fresh inputs:
- ✅ Always start from original data
- ✅ Reproducible results
- ✅ Clear separation of inputs vs outputs
- ✅ Easy to reference original state

## Usage

### Running Fresh Test

```python
from generate_design import generate_design

# Use original input files
result = generate_design(
    ont_geojson_path="test_inputs/small_area/ONT.geojson",
    fiber_cable_geojson_path="test_inputs/small_area/fiber cable.geojson",
    output_dir="test_output/small_area_design_fresh"
)
```

### Command Line

```bash
python generate_design.py \
  --onts test_inputs/small_area/ONT.geojson \
  --cables "test_inputs/small_area/fiber cable.geojson" \
  --output test_output/small_area_design_fresh
```

## File Naming

- **Inputs**: Use descriptive names (e.g., `small_area`, `full_area`)
- **Outputs**: Use descriptive names with version (e.g., `small_area_design_fresh`, `small_area_design_v2`)

## Best Practices

1. **Always use inputs from `test_inputs/`** for testing
2. **Save outputs to `test_output/`** with descriptive folder names
3. **Document** what each input/output folder contains
4. **Version** output folders if making significant changes
5. **Keep inputs clean** - don't modify reference files
