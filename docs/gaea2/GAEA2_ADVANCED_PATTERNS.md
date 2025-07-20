# Gaea2 Advanced Patterns and Node Relationships

## Overview
This document contains advanced patterns, node relationships, and property insights discovered from analyzing 10 production Gaea2 terrain files. These patterns represent real-world best practices that can significantly improve terrain generation quality.

## Core Workflow Patterns

### 1. The Universal Terrain Foundation Pattern
Found in 9 out of 10 projects analyzed:

```
Slump → FractalTerraces → Combine(+Island/Blur) → Shear → [Erosion Chain]
```

**Why this works:**
- Slump creates natural base deformation
- FractalTerraces adds geological stratification
- Combine with Island mask creates variation
- Shear adds realistic tectonic deformation
- Erosion chain finalizes natural weathering

**Property Insights:**
- Slump Scale: 0.15-0.5 (lower = more subtle)
- FractalTerraces Spacing: 0.1-0.37 (controls layer density)
- Combine Ratio: 0.17-0.5 (controls Island influence)
- Shear Strength: 0.025 (consistent across projects)

### 2. The Erosion Progression Pattern
Standard erosion chain with specific ordering:

```
[Terraces/Crumble] → Erosion2 → Rivers → [TextureBase] → [Sea]
```

**Key Insights:**
- Terraces OR Crumble, never both
- Terraces NumTerraces: 10-223 (huge variation)
- Crumble always uses same properties (Duration: 0.5, Strength: 0.87)
- Erosion2 Duration: 1.6-10.3 (performance vs quality)
- Rivers follow Erosion2 in 100% of cases

### 3. The Color Blending Pattern
Consistent approach to terrain colorization:

```
TextureBase → Multiple SatMaps → Combine(Color) → Height Mask → Final Combine
```

**SatMap Usage Patterns:**
- Always 2-3 SatMaps per terrain
- Common combinations:
  - Green + Blue (vegetation + water)
  - Rock + Sand (arid terrain)
  - Sand + Color (desert)
- One SatMap usually has Reverse: true

**Combine Settings:**
- RenderIntentOverride: "Color" (critical!)
- Ratio: 1.0 for primary blend
- Secondary combines use varying ratios

### 4. The Island Mask Pattern
Used for terrain variation:

```
Island → [Adjust(Invert)] → Blur → Combine(as Input2)
```

**Property Patterns:**
- Island Size: 0.11-0.86 (project-specific)
- Often includes Invert modifier
- Blur Radius: 0.016-0.036 (subtle smoothing)
- Adjust may include Multiply: 2.4-2.6

## Node-Specific Insights

### Rivers Node Advanced Usage

**Output Port Usage:**
- "Out" → Primary terrain (always connected)
- "Rivers" → Used for masking (connected to Adjust)
- "Depth" → Rarely used in basic terrains
- "Surface" → Connected for detail enhancement
- "Direction" → Not used in analyzed projects

**Property Correlations:**
- Low Headwaters (3-4) → High Downcutting (0.7+)
- High Headwaters (200+) → Low Downcutting (0.3-)
- RiverValleyWidth correlates with Water amount

### Erosion2 Property Relationships

**Duration vs Detail:**
- Duration < 2.0: Fast preview mode
- Duration 2-5: Balanced quality
- Duration > 5: High quality (up to 10.3 found)

**Consistent Properties:**
- ErosionScale: Always 15620.922
- Shape: Always 0.42
- ShapeSharpness: Always 0.6
- ShapeDetailScale: Always 0.25

### Combine Node Advanced Features

**Multi-Mask Support:**
Multiple mask ports can exist:
```json
"Ports": {
  "$values": [
    {"Name": "In", ...},
    {"Name": "Input2", ...},
    {"Name": "Mask", ...},
    {"Name": "Mask", ...},  // Additional mask
    {"Name": "Mask", ...}   // Third mask
  ]
}
```

**Mode Usage:**
- Default mode for terrain blending
- "Add" mode for Slump+FractalTerraces combo

### SatMap Library Patterns

**Library Selection by Terrain Type:**
- Mountain terrain: Rock → Green combination
- Desert: Sand → Color combination
- Coastal: Blue as primary
- Volcanic: Rock with high LibraryItem numbers

**LibraryItem Insights:**
- Low numbers (1-50): Basic textures
- Mid numbers (50-300): Varied textures
- High numbers (300+): Specialized textures

## Property Value Patterns

### Seed Synchronization
All projects use synchronized seeds across related nodes:
- Variable name format: "{NodeId}_Seed"
- Bound nodes: All generators + modifiers
- Seed range used: 3-64213

### Scale Relationships
Discovered scale hierarchies:
1. Primary generator: 0.15-1.0
2. Detail nodes: 0.1-0.3
3. Texture nodes: 0.15 (consistent)

### Performance vs Quality Settings

**Erosion2 Performance Tiers:**
- Fast: Duration 0.5-1.0
- Balanced: Duration 1.5-3.0
- Quality: Duration 5.0-10.0

**Rivers Performance:**
- Headwaters < 10: Fast
- Headwaters 10-100: Balanced
- Headwaters > 100: Quality

## Advanced Node Combinations

### 1. Volcanic Terrain Specialty
```
Volcano → MountainSide → Combine → Standard Chain
```
- Only found in Level1
- Volcano Surface: "Eroded"
- MountainSide Detail: 0.25

### 2. Multi-Stage Erosion
```
Erosion2 → Terraces → Erosion2 → Rivers
```
- Creates complex erosion patterns
- Terraces acts as erosion modifier

### 3. Height-Based Compositing
```
Height(Range) → Combine(Mask) → Weathering
```
- Height Range.Y controls cutoff
- Falloff: 0.006-0.3 (sharp to gradual)

### 4. Final Touch Patterns
Last nodes in chain:
- Weathering (Level7-8)
- Perlin (Level10)
- Dusting (Level10)

These add final surface detail without major changes.

## Connection Validation Rules

### Port Compatibility Matrix
Based on analysis, these connections are valid:

| From Node | From Port | To Node | To Port |
|-----------|-----------|---------|---------|
| Any Terrain | Out | Erosion/Modify | In |
| Erosion2 | Out | Rivers | In |
| Rivers | Rivers | Adjust | In |
| Rivers | Out | TextureBase | In |
| TextureBase | Out | SatMap | In |
| SatMap | Out | Combine | In/Input2 |
| Height | Out | Combine | Mask |
| Any | Out | Any | Mask |

### Invalid Connections to Avoid
- Rivers → Rivers (no chaining)
- SatMap → Erosion (color before terrain)
- Combine → Primary generators

## Workflow Optimization Insights

### Node Ordering for Performance
1. Generators first
2. Major modifications (Erosion2)
3. Water systems (Rivers, Sea)
4. Detail additions
5. Texturing
6. Color operations
7. Final compositing

### Caching Opportunities
Nodes that benefit from caching:
- Erosion2 (expensive)
- Rivers (moderate)
- TextureBase (cheap but frequent)

### Memory Optimization
High memory nodes to watch:
- Erosion2 with high Duration
- Rivers with high Headwaters
- Multiple Combine chains

## State and UI Patterns

### Locked Nodes
Always lock final output nodes:
- Prevents accidental modification
- Usually last Combine or Weathering

### Selected vs Locked
- SelectedNode: Current UI selection
- LockedNode: Viewport lock (usually same as final)

### Save Definitions
Common on:
- Rivers (water mask export)
- Final Combine (main output)
- Format: Always "EXR"

## Variable Automation Patterns

### Common Variable Uses
1. **Global Seed**: Synchronize randomization
2. **Scale Factor**: Uniform terrain scaling
3. **Erosion Strength**: Global weathering control

### Binding Patterns
- Bind similar operations (all Seeds)
- Don't bind artistic choices (Heights, Scales)
- Keep performance settings separate

## Undocumented Features

### 1. Modifier Stacking
Some nodes have multiple modifiers:
```json
"Modifiers": {
  "$values": [
    {"$type": "...Invert", ...},
    {"$type": "...Clamp", ...}
  ]
}
```

### 2. Draw Node Stroke Data
Draw nodes contain stroke arrays:
```json
"stroke_data": [
  {"x": 0.5, "y": 0.5, "pressure": 1.0},
  ...
]
```

### 3. Group Color Codes
Groups use specific color names:
- "Brass" (default)
- "Steel"
- "Copper"

## Best Practices Summary

1. **Always start with Slump**: Provides best base deformation
2. **Use synchronized seeds**: Ensures reproducible results
3. **Apply RenderIntentOverride**: Critical for color combines
4. **Lock final nodes**: Prevents accidental changes
5. **Order by computation cost**: Expensive nodes early
6. **Use Height masks**: Better than direct connections
7. **Combine SatMaps**: Richer textures than single maps
8. **Save water masks**: Rivers output for post-processing
9. **Set appropriate NodeSize**: Improves UI clarity
10. **Document with groups**: Organize complex workflows
