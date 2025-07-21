# Gaea Reference Projects Analysis Report

## Overview

This report analyzes 10 Gaea reference terrain files (Level1.terrain through Level10.terrain) to understand structure, patterns, and test-worthy scenarios.

## Summary Statistics

- **Total Projects**: 10
- **Average Nodes per Project**: 19.3
- **Average Connections per Project**: 23.1
- **Total Unique Node Types**: 22
- **Most Complex Project**: Level9.terrain (22 nodes, 27 connections)

## Key Findings

### 1. Most Common Node Types

| Node Type | Count | Usage |
|-----------|-------|-------|
| Combine | 31 | Merging terrains and masks |
| SatMap | 31 | Color/texture mapping |
| Adjust | 15 | Value adjustments |
| Height | 12 | Height-based masking |
| Shear | 10 | Terrain deformation |
| TextureBase | 10 | Base texture generation |
| Crumble | 10 | Rock breaking effects |
| Erosion2 | 10 | Advanced erosion |
| Rivers | 9 | River generation |
| FractalTerraces | 9 | Terraced terrain |

### 2. Common Workflow Patterns

The most common workflow chain observed across projects:
```
Slump → FractalTerraces → Combine → Shear → Crumble → Erosion2 → Rivers → Sea/TextureBase
```

### 3. Connection Patterns

| Source → Target | Frequency | Common Ports |
|-----------------|-----------|--------------|
| TextureBase → SatMap | 31 | Out → In |
| SatMap → Combine | 27 | Out → Input2 (17), Out → In (10) |
| Rivers → Adjust | 9 | Rivers → In |
| Height → Combine | 10 | Out → Mask |
| Sea → Combine | Multiple | Water → Mask |

### 4. Special Node Characteristics

#### Nodes with Multiple Output Ports:
- **Rivers**: Out, Rivers, Depth, Surface, Direction
- **Sea**: Out, Water, Depth, Shore, Surface
- **Erosion2**: Out, Flow, Wear, Deposits
- **Crumble**: Out, Wear
- **FractalTerraces/Stratify**: Out, Layers

#### Nodes with Complex Properties:
- **Height**: Range property (object with X,Y values)
- **Rivers**: SaveDefinition for export
- **Combine**: Multiple mask inputs, RenderIntentOverride
- **SatMap**: Library/LibraryItem selection, Range objects

### 5. Unique/Rare Nodes

These nodes appear in only 1-2 projects and represent special cases:
- Volcano (Level1 only)
- MountainSide (Level1 only)
- Sea (Level1 only)
- Stratify (Level1 only)
- Perlin (Level10 only)
- Dusting (Level10 only)

### 6. Property Patterns

Common property configurations by node type:

**Adjust**:
- Multiply, Equalize, Invert, Clamp, Shaper
- NodeSize variations

**Combine**:
- PortCount (2-3)
- Ratio (0-1)
- Mode (Add, etc.)
- Clamp settings
- RenderIntentOverride for color workflows

**Rivers**:
- Water, Width, Depth, Downcutting
- Headwaters count
- RenderSurface boolean
- Seed values

## Test-Worthy Scenarios

### 1. Basic Connection Tests
- Single input/output connections
- Multi-port connections (Rivers→Adjust using Rivers port)
- Mask connections (Height→Combine mask port)
- Special output ports (Sea Water→Combine mask)

### 2. Complex Workflow Tests
- Long chains (6+ nodes)
- Parallel paths merging in Combine
- Multiple masks on single node
- Circular references (none found - good!)

### 3. Property Value Tests
- Range objects (Height, SatMap)
- NodeSize variations (Small, Standard)
- SaveDefinition on export nodes
- Special render intents (Color mode)

### 4. Edge Cases
- Nodes with no inputs (generators like Volcano, Island)
- Nodes with 3+ inputs (Combine with dual masks)
- Property inheritance through Variables
- Locked nodes (IsLocked property)

### 5. Automation Tests
- Variable bindings (Level2 has Seed variable)
- Property automation
- Cross-node parameter linking

## File Structure Patterns

All reference files follow this structure:
```json
{
  "$id": "1",
  "Assets": {
    "$values": [{
      "Terrain": {
        "Id": "[GUID]",
        "Metadata": {...},
        "Nodes": {
          "[node_id]": {
            "$type": "QuadSpinner.Gaea.Nodes.[NodeType], Gaea.Nodes",
            "Properties": "...",
            "Ports": {
              "$values": [
                {
                  "Name": "[port_name]",
                  "Type": "[port_type]",
                  "Record": { // Connection info
                    "From": "[source_id]",
                    "To": "[target_id]",
                    "FromPort": "[port]",
                    "ToPort": "[port]"
                  }
                }
              ]
            }
          }
        },
        "Automation": {
          "Variables": {},
          "Bindings": {}
        }
      }
    }]
  }
}
```

## Recommendations for Testing

1. **Create test cases for each connection pattern** identified above
2. **Test all node types** with focus on multi-port nodes
3. **Validate property ranges** especially for Range objects
4. **Test workflow complexity** up to 25+ nodes
5. **Verify special ports** (Rivers, Sea, etc.) connect properly
6. **Test automation features** with variable bindings
7. **Validate file format** matches reference structure exactly

## Conclusion

The reference projects show consistent patterns that can guide both implementation and testing. The most critical aspects are:
- Proper connection handling with correct port names
- Support for multiple output ports on specialized nodes
- Complex property types (Range objects, SaveDefinition)
- Maintain exact file structure for Gaea compatibility
