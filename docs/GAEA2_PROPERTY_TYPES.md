# Gaea2 Property Types Documentation

## Overview

This document outlines the correct data types for Gaea2 node properties. Using the wrong type (e.g., float instead of int) can cause Gaea2 to fail when loading terrain files.

## Property Type Rules

### Integer Properties

The following properties **MUST** be integers:

#### Common Properties
- **Seed** - Random seed values (0-999999)
- **Octaves** - Number of noise octaves (1-16)

#### Node-Specific Integer Properties

**Erosion Node:**
- `FeatureScale` - Size in meters (50-10000)

**Rivers Node:**
- `Headwaters` - Number of river sources (10-1000)

**Surface Nodes:**
- `Stratify.Layers` - Number of rock layers (2-50)
- `FractalTerraces.Levels` - Number of terrace levels (2-20)
- `Terraces.Terraces` - Number of terraces (2-50)
- `Steps.Steps` - Number of steps (2-20)

**Vegetation Nodes:**
- `Trees.Count` - Number of trees in thousands (10-10000)
- `Shrubs.Count` - Number of shrubs in thousands (10-10000)

**Other Nodes:**
- `Grid.GridSmallCount` - Small grid divisions (1-50)
- `Grid.GridLargeCount` - Large grid divisions (1-20)
- `Pixelate.PixelSize` - Pixel size (2-128)
- `Aperture.Vertices` - Number of aperture sides (3-12)

### Float Properties

Most other properties should be floats, including:

#### Range 0.0 to 1.0 (Percentages/Ratios)
- Scale factors (except world scale)
- Height values
- Strength/Intensity values
- Coverage percentages
- Blend ratios
- Most mask values

#### Unbounded Floats
- X/Y positions
- World scale values
- Rotation angles

### Boolean Properties
- `AggressiveMode`
- `Deterministic`
- `ClampOutput`
- `ReduceDetails`

### String Properties
- `Style` (enum values like "Basic", "Alpine", etc.)
- `Mode` (blend modes like "Add", "Max", etc.)
- `PortalName` (portal identifiers)

### Enum Properties
Properties with specific allowed values:
- `Mountain.Style`: "Basic", "Eroded", "Old", "Alpine", "Strata"
- `Mountain.Bulk`: "Low", "Medium", "High"
- `Combine.Mode`: "Blend", "Add", "Screen", "Subtract", etc. (25 modes)

## Common Errors

### Error: "Input string '2000.0' is not a valid integer"
**Cause:** FeatureScale was set as 2000.0 (float) instead of 2000 (int)
**Fix:** Ensure FeatureScale is an integer value

### Prevention

The MCP tool now includes:
1. **Type validation** in `gaea2_schema_v2.py`
2. **Automatic type correction** in `_ensure_property_types()`
3. **Knowledge graph constraints** that output correct types
4. **Property definitions** with explicit type specifications

## Implementation Details

### Schema Definition Example
```python
"FeatureScale": {
    "type": "int",  # Must be "int", not "float"
    "default": 2000,
    "range": {"min": 50, "max": 10000},
    "description": "Size of erosion features in meters",
}
```

### Type Correction Code
```python
if expected_type == "int" and isinstance(prop_value, float):
    corrected[prop_name] = int(round(prop_value))
```

### Knowledge Graph Integration
The knowledge graph now rounds values for integer properties:
```python
if constraint.property_b in ["FeatureScale", "Layers", "Levels", ...]:
    suggested_value = int(round(suggested_value))
```

## Testing

Always validate generated terrain files before use:
1. Check that integer properties have no decimal points
2. Verify enum values match allowed options exactly
3. Ensure boolean values are true/false (not 1/0)

## Updates

This document reflects the fixes applied after discovering the FeatureScale type error. All integer properties are now properly typed in:
- `gaea2_schema_v2.py` - Property definitions
- `gaea2_knowledge_graph.py` - Constraint calculations
- `mcp_server.py` - Type enforcement during project creation
