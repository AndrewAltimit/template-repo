# Gaea Terrain Analysis

## Overview
This analysis examines official Gaea terrain project files to identify common workflow patterns, node combinations, and property settings used in professional terrain generation.

## Common Node Workflow Patterns

### 1. **Foundation → Erosion → Texturing → Color** (Most Common Pattern)

This is the standard workflow found in nearly all analyzed projects:

#### Example from "High Mountain Peak":
```
Mountain → Erosion2 → Sandstone → TextureBase → SatMap → ColorErosion
```

#### Example from "Mesa":
```
Mountain → Erosion2 → Sandstone → TextureBase + Autolevel → Combine → SatMap
```

### 2. **Specialized Foundation Nodes**

Different foundation nodes are used based on terrain type:

- **Mountain**: Standard terrain foundation (most common)
  - Common settings: Scale (0.5-0.85), Height (2.2-2.96), Bulk: "High"

- **RadialGradient**: Used for volcanic/crater formations
  - Example: "Volcano" - RadialGradient → Erosion2 chain

- **Canyon**: Used for canyon/valley terrains
  - Example: "Canyon River with Sea" - Canyon → Erosion2 → HydroFix

- **MountainSide**: Used for complex cliff faces
  - Example: "Complex Scene - Debris"

### 3. **Erosion Chains**

Multiple erosion passes are common for realistic results:

#### Example from "Volcano" (4 erosion passes):
```
RadialGradient → Erosion2 → Erosion2 → Erosion2 → Fold → Erosion2
```

Key erosion parameters vary by pass:
- Early passes: Higher duration (40-74), lower downcutting (0.05-0.25)
- Later passes: Lower duration (10), varied downcutting (0.01-0.7)

## Key Node Properties and Typical Values

### Erosion2 Node
Most critical node with these common parameter ranges:

```
Duration: 10.0 - 74.0 (higher for initial passes)
Downcutting: 0.018 - 0.697
ErosionScale: 141 - 16897 (varies greatly by terrain scale)
Seed: Random (always different)
SuspendedLoadDischargeAmount: 0.0 - 1.0
SuspendedLoadDischargeAngle: 24.0 (default)
BedLoadDischargeAngle: 15.0 (default)
CoarseSedimentsDischargeAngle: 10.0 - 35.5
Shape: 0.2 (common default)
ShapeSharpness: 0.3 - 0.6
ShapeDetailScale: 0.017 - 0.611
```

### Mountain Node
```
Scale: 0.5 - 0.847
Height: 2.26 - 2.96
Style: "Old" or default
Bulk: "High" (most common)
```

### Sandstone Node
Used for stratified rock formations:
```
Passes: 1 - 4
Iterations: 10 (standard)
Spacing: 0.1 - 0.809
Intensity: 0.5 (default)
Tilt: 0.229 - 0.688
Chaos: 0.056 - 0.323
Chipped: true (common)
Chipping: 0.45 (when chipped)
```

### TextureBase Node
Adds surface detail:
```
Slope: 0.143 - 0.680
Scale: 0.113 - 0.920
Soil: 0.371 - 0.683
Patches: 0.04 - 1.0
Chaos: 0.1 - 1.0
```

### SatMap Node
Color/texture mapping:
```
Library: "Rock", "Sand", "Green" (common options)
LibraryItem: Various IDs (81, 176, 240, 569, etc.)
Enhance: "Autolevel", "Equalize"
Reverse: true/false based on desired look
```

## Advanced Techniques

### 1. **Multi-Layer Stratification**
Complex scenes use multiple Stratify nodes with different parameters:
```
Stratify → Stratify → SlopeBlur + Combine → Sandstone → Stratify
```

### 2. **Height-Based Masking**
Using Height modifiers to restrict effects to elevation ranges:
```
Range: {X: 0.0-0.446, Y: 0.07-0.567}
Falloff: 0.15 (standard)
```

### 3. **Combining Techniques**
- **Combine nodes**: Blend multiple terrain features
- **Ratio**: 0.5-0.684 (controls blend amount)
- **Mode**: "Normal", "Difference"

### 4. **Water Features**
Special nodes for water:
- **Sea**: Adds ocean/lake with coastal erosion
- **HydroFix**: Fixes hydrology issues after erosion
- **Trees**: Can use water masks for placement

### 5. **Color Workflows**

#### ColorErosion for Natural Coloring:
```
TransportDistance: 0.5 - 1.445
SedimentDensity: 0.871 - 1.0
Blend: 0.5 - 1.0
ColorHold: 0.5 - 1.0
```

#### Mixer Node for Complex Color Layers:
- Up to 6 ports used
- Height-based masking for each layer
- BlendMode options: "Normal", "Add"

## Best Practices Observed

1. **Progressive Refinement**: Start with large-scale features, add detail progressively
2. **Multiple Erosion Passes**: Use different erosion settings for realism
3. **Modifiers Usage**: Height, Blur, Warp, Influence modifiers fine-tune results
4. **Seed Variation**: Always use different seeds for each node
5. **Resolution Awareness**: Standard working resolution is 1024, baking at 2048

## Common Node Combinations

### Basic Mountain:
```
Mountain → Erosion2 → TextureBase → SatMap
```

### Stratified Cliffs:
```
Foundation → Erosion2 → Sandstone → Erosion2 → TextureBase → SatMap
```

### Complex Terrain:
```
Foundation → Multiple Erosions → Stratify/Sandstone → Combine → TextureBase → SatMap → ColorErosion
```

### Volcanic:
```
RadialGradient → Erosion Chain → Fold → Erosion → TextureBase → SatMap → ColorErosion
```

## Property Setting Guidelines

### For Realistic Mountains:
- Start with Mountain node (Scale: 0.5-0.8, Height: 2.2-3.0)
- First erosion: Duration 40-70, low downcutting
- Second erosion: Duration 10, higher downcutting
- Add Sandstone for rock layers
- TextureBase with moderate chaos (0.5-0.8)

### For Mesas/Buttes:
- Mountain with "Old" style
- Strong initial erosion (high downcutting: 0.6-0.7)
- Sandstone with multiple passes (3-4)
- Combine TextureBase with layer masks

### For Canyons:
- Canyon node as foundation
- Multiple erosion passes with varying scales
- HydroFix for water flow
- Sea node for water bodies

## Conclusion

Gaea workflows follow predictable patterns with foundation → erosion → detail → color as the core structure. Success comes from understanding how to chain nodes effectively and tune parameters for specific terrain types. The key is progressive refinement with multiple passes and careful parameter tuning based on the desired output.

---

## Part 2: Terrain File Format Analysis

### Key Differences Between Generated and Working Files

#### 1. Connection Record Placement
- **Working (Level1.terrain)**: Record objects are placed inside the receiving port (usually "In" port)
- **Generated**: Records are correctly placed in receiving ports

#### 2. Property Naming Conventions
- **Working**: Uses spaces in property names: "Rock Softness", "Snow Line", "Settle Duration"
- **Generated**: Sometimes uses camelCase or different formatting

#### 3. Missing Node Properties
Working files include additional properties our generator misses:
- `PortCount` on Combine nodes (always 2)
- `NodeSize` ("Small", "Standard") on various nodes
- `IsMaskable: true` on most nodes
- `RenderIntentOverride: "Color"` on color-handling Combine nodes

#### 4. Range Property Format
- **Working**: Range has its own $id: `{"$id":"103","X":0.87732744,"Y":1.0}`
- **Generated**: Simple object: `{"X":0.5,"Y":0.5}`

#### 5. ID Allocation Pattern
- **Working**: Non-sequential IDs (183, 668, 427, 281, 294...)
- **Generated**: Sequential IDs (100, 110, 120, 130...)

#### 6. SaveDefinition Structure
Working files may have SaveDefinition at node level with specific format requirements.

#### 7. Critical Missing Elements
- Variables object should be `{"$id":"72"}` not `{}`
- BoundProperties needs proper $id references
- Camera object needs proper structure

### Required Fixes for Gaea2 MCP Server

1. **Property Name Mapping**: Ensure all property names match Gaea2's exact format
2. **Add Missing Node Properties**: Include PortCount, NodeSize, IsMaskable
3. **Fix Range Properties**: Add $id to all Range objects
4. **Non-Sequential ID Generation**: Use more scattered ID pattern
5. **Proper Empty Object Formatting**: Use `{"$id":"XX"}` for empty objects

### API Call Format Discovery

The correct MCP execute format requires:
```json
{
  "tool": "create_gaea2_project",
  "parameters": {
    "project_name": "name",
    "workflow": [/* nodes with connections inline */],
    "auto_validate": true
  }
}
```

NOT the documented format with separate nodes/connections arrays.
