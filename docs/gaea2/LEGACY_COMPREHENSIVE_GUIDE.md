# Gaea 2 MCP Tools - Comprehensive Guide

This guide provides detailed information about the Gaea 2 terrain generation tools in our MCP server, based on deep analysis of the official Gaea 2 documentation.

## Overview

The Gaea 2 MCP tools allow you to programmatically create terrain project files (.terrain format) that can be opened in Gaea 2. Our implementation is based on analysis of 185 documented nodes across 9 categories, providing accurate node types, properties, and validation.

## Available Tools

### 1. create_gaea2_project

Create custom Gaea 2 terrain projects with full control over nodes and connections.

**Parameters:**
- `project_name` (string): Name of the project
- `nodes` (array): List of nodes with their properties
- `connections` (array): List of connections between nodes
- `resolution` (int): Project resolution (default: 2048)
- `world_size` (int): World size in meters (default: 5000)
- `output_path` (string, optional): Custom output path

### 2. validate_gaea2_project

Validate Gaea 2 project files with comprehensive checking including:
- Node type validation (185 documented node types)
- Property type and range validation
- Connection compatibility checking
- Project structure validation

**Parameters:**
- `project_file` (string, optional): Path to .terrain file
- `project_data` (object, optional): Project data structure

### 3. create_gaea2_from_template

Create projects using professionally designed workflow templates.

**Available Templates:**
- `basic_terrain`: Simple terrain with erosion (4 nodes)
- `detailed_mountain`: Advanced mountain with dual peaks, rivers, and snow (7 nodes)
- `volcanic_terrain`: Volcanic landscape with thermal weathering (6 nodes)
- `desert_canyon`: Desert canyon with stratification and sand (6 nodes)

**Parameters:**
- `template_name` (string): Name of the template
- `project_name` (string, optional): Custom project name
- `start_position` (object, optional): Starting position for nodes

### 4. list_gaea2_templates

List all available workflow templates with details.

## Node Categories

Our tools support all 185 documented Gaea 2 nodes organized into 9 categories:

### 🟢 Primitive (24 nodes)
Noise generators and basic shapes: Cellular, Perlin, Voronoi, Noise, Gabor, etc.

### 🟢 Terrain (14 nodes)
Terrain generators: Mountain, Canyon, Island, Volcano, Ridge, Crater, etc.

### 🔵 Modify (41 nodes)
Terrain modifiers: Warp, Blur, Transform, Curve, Clamp, SlopeWarp, etc.

### 🟡 Surface (21 nodes)
Surface detail: Outcrops, Stratify, FractalTerraces, Craggy, Bomber, etc.

### 🟠 Simulate (25 nodes)
Natural processes: Erosion, Rivers, Snow, Thermal, Glacier, Debris, etc.

### ⚪ Derive (13 nodes)
Analysis maps: FlowMap, Slope, Curvature, Normals, Occlusion, etc.

### 🟣 Colorize (13 nodes)
Color operations: SatMap, CLUTer, Splat, Weathering, HSL, etc.

### 🔴 Output (13 nodes)
Export nodes: Mesher, Export, Unity, Unreal, Cartography, etc.

### ⚫ Utility (20 nodes)
Helper nodes: Combine, Mask, Math, Layers, Route, Gate, etc.

## Property Validation

Properties are validated with proper types and ranges based on documentation:

### Common Properties
- **Seed** (int): 0-999999, randomization seed
- **Scale** (float): 0.01-10.0, perceptual scale
- **Height** (float): 0.0-1.0, height/intensity
- **Strength** (float): 0.0-2.0, effect strength

### Node-Specific Properties

**Mountain Node:**
- Scale: 0.1-5.0 (default: 1.0)
- Height: 0.0-1.0 (default: 0.7)
- Style: enum ["Basic", "Eroded", "Old", "Alpine", "Strata"]
- Bulk: enum ["Low", "Medium", "High"]

**Erosion Node:**
- Duration: 0.0-1.0 (default: 0.04)
- RockSoftness: 0.0-1.0 (default: 0.4)
- Strength: 0.0-2.0 (default: 0.5)
- FeatureScale: 50-10000 meters (default: 2000)

**Combine Node:**
- Mode: 24 blend modes (Blend, Add, Max, Min, Overlay, etc.)
- Ratio: 0.0-1.0 (default: 0.5)

## Port System

Nodes use typed ports with compatibility rules:

### Port Types
- **heightfield**: Primary terrain or mask data
- **color**: RGB color data
- **mask**: Grayscale mask data
- **data**: Analysis data (flow, wear, deposits)
- **vector**: Vector field data

### Compatibility Rules
- Heightfields can connect to heightfield or mask inputs
- Colors only connect to color inputs
- Masks are interchangeable with heightfields
- Data maps can be used as masks

## Example: Creating Professional Terrain

```python
# Create a detailed mountain landscape
{
    "tool": "create_gaea2_project",
    "arguments": {
        "project_name": "Alpine Valley",
        "nodes": [
            {
                "id": 100,
                "type": "Mountain",
                "name": "MainPeak",
                "position": {"x": 24000, "y": 26000},
                "properties": {
                    "Scale": 1.8,
                    "Height": 0.9,
                    "Style": "Alpine",
                    "Bulk": "High",
                    "Seed": 12345
                }
            },
            {
                "id": 101,
                "type": "Mountain",
                "name": "SecondaryRidge",
                "position": {"x": 23500, "y": 26500},
                "properties": {
                    "Scale": 1.2,
                    "Height": 0.6,
                    "Style": "Rocky",
                    "Bulk": "Medium",
                    "Seed": 54321
                }
            },
            {
                "id": 102,
                "type": "Combine",
                "name": "MergeTerrain",
                "position": {"x": 24500, "y": 26250},
                "properties": {
                    "Mode": "Max",
                    "Ratio": 0.75
                }
            },
            {
                "id": 103,
                "type": "Erosion",
                "name": "ValleyErosion",
                "position": {"x": 25000, "y": 26250},
                "properties": {
                    "Duration": 0.06,
                    "RockSoftness": 0.4,
                    "Strength": 0.7,
                    "Downcutting": 0.5,
                    "FeatureScale": 1500
                }
            },
            {
                "id": 104,
                "type": "Rivers",
                "name": "AlpineStreams",
                "position": {"x": 25500, "y": 26250},
                "properties": {
                    "Water": 0.4,
                    "Width": 0.6,
                    "Depth": 0.5,
                    "Headwaters": 200
                }
            },
            {
                "id": 105,
                "type": "Snow",
                "name": "SnowAccumulation",
                "position": {"x": 26000, "y": 26250},
                "properties": {
                    "Coverage": 0.7,
                    "Altitude": 0.65,
                    "Thickness": 0.4
                }
            },
            {
                "id": 106,
                "type": "Outcrops",
                "name": "RockExposure",
                "position": {"x": 26500, "y": 26250},
                "properties": {
                    "Scale": 0.3,
                    "Coverage": 0.4,
                    "Height": 0.2
                }
            },
            {
                "id": 107,
                "type": "SatMap",
                "name": "AlpineColors",
                "position": {"x": 27000, "y": 26250},
                "properties": {
                    "Library": "Mountain",
                    "LibraryItem": "Swiss Alps",
                    "Enhance": 0.8
                }
            }
        ],
        "connections": [
            {"from_node": 100, "to_node": 102, "to_port": "Input1"},
            {"from_node": 101, "to_node": 102, "to_port": "Input2"},
            {"from_node": 102, "to_node": 103},
            {"from_node": 103, "to_node": 104},
            {"from_node": 104, "to_node": 105},
            {"from_node": 105, "to_node": 106},
            {"from_node": 106, "to_node": 107}
        ],
        "resolution": 4096,
        "world_size": 10000
    }
}
```

## Validation Features

The validation tool provides comprehensive checking:

### What's Validated
1. **Node Types**: Checks against 185 documented nodes
2. **Properties**: Type checking (float, int, bool, enum, string)
3. **Value Ranges**: Warns if values are outside recommended ranges
4. **Connections**: Validates port compatibility
5. **Project Structure**: Ensures proper JSON structure

### Example Validation Output
```json
{
    "valid": true,
    "errors": [],
    "warnings": [
        "Property 'Height' value 1.5 outside recommended range [0.0, 1.0]",
        "Unknown property 'CustomProp' for node type Mountain"
    ],
    "suggestions": [
        "Add an Erosion node for more realistic terrain",
        "Consider adding color nodes for texturing"
    ],
    "node_count": 8,
    "connection_count": 7,
    "node_types": ["Mountain", "Combine", "Erosion", "Rivers", "Snow", "SatMap"]
}
```

## Best Practices

### 1. Node Organization
- Place generators (Mountain, Island) first
- Follow with modifiers (Erosion, Rivers)
- End with colorization (SatMap, Splat)

### 2. Property Values
- Start with default values
- Use documented ranges
- Test extreme values carefully

### 3. Connections
- Connect compatible port types
- Use Combine for merging terrains
- Data outputs can feed masks

### 4. Performance
- Higher resolutions = longer processing
- Complex erosion needs more time
- Use templates for quick starts

## Workflow Templates

### Basic Terrain
Perfect for quick prototypes:
- Mountain → Erosion → TextureBase → SatMap

### Detailed Mountain
Professional mountain landscape:
- Dual Mountains → Combine → Erosion → Rivers → Snow → SatMap

### Volcanic Terrain
Island volcano with weathering:
- Volcano + Island → Combine → Erosion → Thermal → SatMap

### Desert Canyon
Stratified canyon landscape:
- Canyon → Stratify → FractalTerraces → Erosion → Sand → SatMap

## Troubleshooting

### Common Issues

**"Unknown node type" warning**
- Check spelling and capitalization
- Verify node exists in Gaea 2
- Tool continues despite warnings

**Property validation warnings**
- Values outside recommended ranges
- May still work but check results
- Use suggested ranges for best results

**Connection errors**
- Verify port names (In, Out, Input1, etc.)
- Check port type compatibility
- Ensure nodes exist before connecting

## Advanced Features

### Custom Properties
While we validate against known properties, the tool allows custom properties for experimentation.

### Multiple Outputs
Some nodes have multiple outputs:
- Erosion: Out, Wear, Flow, Deposits
- Combine: Out, Separation

### Selective Processing
Some nodes support mask inputs for localized effects.

## Integration with Gaea 2

1. **Create** terrain file with MCP tools
2. **Copy** from Docker container:
   ```bash
   docker cp mcp-server:/app/output/gaea2/. ./output/gaea2/
   ```
3. **Open** in Gaea 2
4. **Build** to generate final terrain

## Future Enhancements

Based on our analysis, future updates may include:
- Auto-layout algorithms for node positioning
- Preset library expansion
- Batch project generation
- Integration with Gaea 2 CLI

---

This comprehensive guide is based on analysis of the official Gaea 2 documentation and represents the most accurate implementation possible without direct Gaea 2 integration.
