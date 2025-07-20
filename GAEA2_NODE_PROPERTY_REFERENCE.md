# Gaea2 Node Property Reference

Based on empirical analysis of 37 reference terrain files, this document provides the definitive property reference for all Gaea2 nodes found in working projects.

## Critical Implementation Notes

1. **No properties with spaces** - All properties use CamelCase (e.g., `RiverValleyWidth` not `River Valley Width`)
2. **Erosion redirect** - Always use `Erosion2`. Plain `Erosion` doesn't exist in reference files
3. **Mountain X,Y properties** - Valid at root level (found in 5/7 Mountain node instances)
4. **Groups/Notes structure** - Must have `{"$id": "XX", "$values": []}`

## Most Common Nodes (by usage frequency)

### 1. Erosion2 (30 files)
**Type**: `QuadSpinner.Gaea.Nodes.Erosion2, Gaea.Nodes`

**Properties**:
- `BedLoadDischargeAmount`: float
- `BedLoadDischargeAngle`: float
- `CoarseSedimentsDischargeAmount`: float
- `CoarseSedimentsDischargeAngle`: float
- `Downcutting`: float (0.0-1.0)
- `Duration`: float (0.0-1.0)
- `ErosionScale`: float (typically 1000-10000)
- `Seed`: int
- `Shape`: float
- `ShapeDetailScale`: float
- `ShapeSharpness`: float
- `SuspendedLoadDischargeAmount`: float
- `SuspendedLoadDischargeAngle`: float

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut
- `Mask`: In
- `Deposits`: Out
- `Flow`: Out
- `Wear`: Out

**Structural**:
- `IsMaskable`: true

### 2. SatMap (29 files)
**Type**: `QuadSpinner.Gaea.Nodes.SatMap, Gaea.Nodes`

**Properties**:
- `Complex`: bool
- `Intensity`: float
- `Light`: float
- `Scale`: float
- `Seed`: int
- `Shadow`: float
- `SoilComplexity`: int

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut

**Structural**:
- `NodeSize`: "Small"

### 3. Combine (24 files)
**Type**: `QuadSpinner.Gaea.Nodes.Combine, Gaea.Nodes`

**Properties**:
- `BlendRatio`: float (0.0-1.0)
- `Clamp`: bool
- `Method`: enum ["Add", "Average", "Difference", "Max", "Min", "Multiply", "Screen", "Subtract"]
- `Power`: float
- `UseGammaCorrection`: bool

**Ports**:
- `In1`: PrimaryIn, Required
- `In2`: PrimaryIn, Required
- `Out`: PrimaryOut
- `Mask`: In

**Structural**:
- `NodeSize`: "Compact" or "Small"
- `IsMaskable`: true

### 4. TextureBase (23 files)
**Type**: `QuadSpinner.Gaea.Nodes.TextureBase, Gaea.Nodes`

**Properties**:
- `Intensity`: float
- `Scale`: float
- `Seed`: int

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut

### 5. Rivers (11 files)
**Type**: `QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes`

**Properties**:
- `Depth`: float
- `Downcutting`: float
- `Headwaters`: int
- `RenderSurface`: bool
- `RiverValleyWidth`: enum ["zero", "plus2", "plus4"]
- `Seed`: int
- `Water`: bool
- `Width`: float

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut
- `Mask`: In
- `Headwaters`: In
- `Depth`: Out
- `Direction`: Out
- `Rivers`: Out
- `Surface`: Out

**Structural**:
- `NodeSize`: "Standard"
- `IsMaskable`: true

### 6. Mountain (7 files)
**Type**: `QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes`

**Properties**:
- `Bulk`: float
- `Height`: float (0.0-1.0)
- `ReduceDetails`: float
- `Scale`: float
- `Seed`: int
- `Style`: enum
- `X`: float (Valid at root level!)
- `Y`: float (Valid at root level!)

**Ports**:
- `Out`: PrimaryOut

### 7. FractalTerraces (11 files)
**Type**: `QuadSpinner.Gaea.Nodes.FractalTerraces, Gaea.Nodes`

**Properties**:
- `Deviation`: float
- `Iterations`: int
- `Levels`: int
- `RandomLevel`: float
- `RandomSlope`: float
- `Seed`: int
- `UseHeight`: bool

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut
- `Mask`: In

**Structural**:
- `IsMaskable`: true

### 8. Adjust (14 files)
**Type**: `QuadSpinner.Gaea.Nodes.Adjust, Gaea.Nodes`

**Properties**:
- `ClampHigh`: float
- `ClampLow`: float
- `Contrast`: float
- `Exposure`: float
- `Gamma`: float
- `Invert`: bool
- `PowerGamma`: float
- `ShiftHigh`: float
- `ShiftLow`: float

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut

### 9. Height (12 files)
**Type**: `QuadSpinner.Gaea.Nodes.Height, Gaea.Nodes`

**Properties**:
- `BlurIterations`: int
- `Cutoff`: float
- `CutoffHigh`: float
- `CutoffLow`: float
- `Falloff`: float
- `Invert`: bool
- `Method`: enum ["Linear", "Smooth", "Scurve", "Steep"]
- `SoftClip`: bool

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut

### 10. Slump (10 files)
**Type**: `QuadSpinner.Gaea.Nodes.Slump, Gaea.Nodes`

**Properties**:
- `Amount`: float
- `Iterations`: int
- `MaxIterations`: int
- `MicroIterations`: int
- `Seed`: int
- `SettlingIterations`: int
- `SettlingStrength`: float
- `Strength`: float

**Ports**:
- `In`: PrimaryIn, Required
- `Out`: PrimaryOut
- `Mask`: In

**Structural**:
- `IsMaskable`: true

## High Priority Missing Nodes

These nodes appear frequently in reference files but are not currently supported:

1. **ColorErosion** (15 files) - Critical for terrain coloring
   - Type: `QuadSpinner.Gaea.Nodes.ColorErosion, Gaea.Nodes`

2. **Sandstone** (8 files)
   - Type: `QuadSpinner.Gaea.Nodes.Sandstone, Gaea.Nodes`

3. **Weathering** (7 files)
   - Type: `QuadSpinner.Gaea.Nodes.Weathering, Gaea.Nodes`

4. **Outcrops** (7 files)
   - Type: `QuadSpinner.Gaea.Nodes.Outcrops, Gaea.Nodes`

5. **Terraces** (6 files)
   - Type: `QuadSpinner.Gaea.Nodes.Terraces, Gaea.Nodes`

## Node Structure Requirements

### Basic Node Structure
```json
{
  "$type": "QuadSpinner.Gaea.Graph.GaeaNode, Gaea",
  "$id": "unique_id",
  "Class": "QuadSpinner.Gaea.Nodes.NodeType, Gaea.Nodes",
  "Version": "1.3.0.0",
  "Id": "NodeName",
  "Name": "DisplayName",
  "NodeSize": "Standard",  // After Name property
  "Ports": { /* port definitions */ },
  "IsMaskable": true,  // After Ports if applicable
  "X": 123,  // Valid for Mountain nodes
  "Y": 456,  // Valid for Mountain nodes
  "Properties": {
    // Node-specific properties
  },
  "SaveDefinition": {
    "$type": "...",
    "$id": "unique_id"
  },
  "SnapIns": {
    "$id": "unique_id",
    "$values": []
  }
}
```

### Property Name Rules
1. No spaces in property names
2. Use CamelCase (e.g., `RiverValleyWidth`)
3. Properties appear in specific order within nodes
4. Range objects have their own `$id` values

### Port Configuration
- Primary ports: `PrimaryIn, Required` or `PrimaryOut`
- Mask ports: Always type `In`
- Secondary outputs: Type `Out`

## Validation Checklist

When implementing or fixing nodes:

- [ ] Use `Erosion2` instead of `Erosion`
- [ ] No spaces in property names
- [ ] Groups/Notes have `$values` arrays
- [ ] No duplicate `$id` values
- [ ] Mountain nodes can have X,Y at root
- [ ] Properties match empirical schema
- [ ] Port types match reference files
- [ ] NodeSize placement after Name
- [ ] IsMaskable placement after Ports
