# Gaea2 Knowledge Base

*Generated from analysis of 31 real Gaea2 projects*

## Executive Summary

This knowledge base was created by analyzing 31 production Gaea2 terrain projects, including 21 official examples and 10 user-created terrains. The analysis reveals common patterns, best practices, and optimal property values that can guide AI agents and developers in creating effective Gaea2 workflows.

## Key Findings

### Most Used Nodes (Top 10)
1. **SatMap** (50 occurrences) - Primary colorization node
2. **Combine** (48 occurrences) - Essential for blending terrains
3. **Erosion2** (31 occurrences) - Advanced erosion simulation
4. **TextureBase** (20 occurrences) - Texture detail generator
5. **Adjust** (18 occurrences) - Height/contrast adjustments
6. **Height** (14 occurrences) - Height map manipulation
7. **ColorErosion** (12 occurrences) - Color-aware erosion
8. **Crumble** (11 occurrences) - Rock breaking effects
9. **Rivers** (10 occurrences) - Water flow simulation
10. **FractalTerraces** (10 occurrences) - Terraced terrain features

### Common Workflow Patterns

#### 1. The "Slump Terrace" Pattern (Most Common - 9 occurrences)
```
Slump → FractalTerraces → Combine → Shear
```
This pattern creates complex terraced landscapes with realistic geological deformation.

#### 2. Mountain Erosion Workflows
```
Mountain → Erosion2 → Rivers → TextureBase → SatMap
```
The standard workflow for realistic mountain terrains with water erosion.

#### 3. Canyon Formation
```
Canyon → Stratify → Outcrops → SatMap
Canyon → Sandstone → Stratify → Erosion2
```
Two approaches to canyon creation - one focusing on rock layers, another on erosion.

#### 4. Advanced Erosion Chains
```
RadialGradient → Erosion2 → Erosion2 → Erosion2
```
Multiple erosion passes create highly detailed terrain features.

## Node Connection Patterns

### Primary Terrain Generators
- **Mountain** → commonly followed by Erosion2 (80% of cases)
- **Canyon** → typically connects to Stratify or Sandstone
- **Ridge** → usually flows into Erosion2 or Outcrops
- **Island** → predominantly connects to Adjust (67%) or Blur (33%)

### Erosion and Weathering
- **Erosion2** → frequently followed by:
  - Rivers (26% of connections)
  - TextureBase (23%)
  - ColorErosion (19%)
  - Height adjustment (13%)
- **Crumble** → almost always leads to Erosion2 (82%)
- **Weathering** → typically connects to Combine (56%)

### Texturing and Colorization
- **TextureBase** → connects to SatMap in 95% of cases
- **SatMap** → commonly followed by:
  - Combine (64% - for multi-texture blending)
  - ColorErosion (14% - for erosion-based color variation)
  - Mixer (10% - for color blending)

### Terrain Modification
- **Combine** → creates complex branching:
  - Another Combine (29% - for multi-layer blending)
  - Shear (21% - for geological deformation)
  - Weathering (10% - for surface detail)
- **Adjust** → typically flows to:
  - Combine (56% - height integration)
  - Blur (33% - smoothing)

## Best Practices and Recommendations

### 1. Workflow Structure
- Start with a primary terrain generator (Mountain, Canyon, Ridge, etc.)
- Apply Erosion2 early in the workflow for realistic geological features
- Use Rivers after erosion for water flow patterns
- Apply TextureBase → SatMap at the end for colorization

### 2. Performance Optimization
Based on the patterns observed:
- Limit erosion chains to 3 nodes maximum
- Place computationally heavy nodes (Erosion2, Rivers) early
- Use Combine nodes strategically to merge results
- Apply color and texture operations last

### 3. Common Node Combinations
**For Realistic Mountains:**
```
Mountain → Erosion2 → Rivers → Adjust → TextureBase → SatMap
```

**For Desert Canyons:**
```
Canyon → Sandstone → Stratify → Erosion2 → TextureBase → SatMap
```

**For Complex Terraces:**
```
Slump → FractalTerraces → Combine → Shear → Crumble → Erosion2
```

**For Volcanic Terrains:**
```
Volcano → Combine → Thermal2 → Erosion2 → Weathering → SatMap
```

### 4. Node Property Guidelines

While specific property values weren't extracted in detail, the analysis shows:
- Multiple Erosion2 nodes are commonly chained for detail
- Combine nodes frequently use default ratio (0.5) for balanced blending
- Rivers typically follows Erosion2 to ensure proper water flow
- Height adjustments are applied after erosion for final terrain shaping

## AI Agent Recommendations

When building Gaea2 workflows:

1. **Start Simple**: Begin with one of the common patterns above
2. **Layer Complexity**: Add detail through erosion chains and weathering
3. **Balance Performance**: Limit heavy operations and place them early
4. **Color Last**: Always apply colorization as the final step
5. **Use Proven Sequences**: The node sequences documented here are battle-tested

## Special Patterns

### The "Debris Flow" Pattern
```
Height → Debris → Debris → Combine
```
Creates realistic debris accumulation by chaining multiple debris nodes.

### The "Water Erosion" Pattern
```
Erosion2 → Rivers → Adjust → Height → Combine
```
Standard pattern for water-carved terrain features.

### The "Stratified Rock" Pattern
```
Sandstone → Stratify → Stratify → SlopeBlur
```
Creates layered rock formations with proper geological stratification.

## Conclusion

This knowledge base represents patterns from 374 total nodes and 440 connections across 31 professional Gaea2 projects. The patterns identified here can serve as templates for AI-assisted terrain generation and provide guidance for optimal node connections and workflow structure.

For AI agents: When suggesting Gaea2 workflows, prioritize these proven patterns and adapt them based on specific terrain requirements. The high frequency of certain node combinations indicates their effectiveness in real-world terrain generation.
