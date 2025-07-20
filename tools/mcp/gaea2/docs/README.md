# Gaea2 Terrain Generation MCP Server

The Gaea2 MCP Server provides comprehensive tools for creating, validating, optimizing, and executing Gaea2 terrain generation projects.

## Features

- **185 Supported Nodes**: Complete support for all documented Gaea2 nodes
- **Intelligent Validation**: Multi-level validation with automatic error correction
- **Pattern Learning**: Knowledge from 31 real projects (374 nodes, 440 connections)
- **Performance Optimization**: 19x speedup through intelligent caching
- **Professional Templates**: 11 ready-to-use terrain templates
- **CLI Automation**: Run Gaea2 projects programmatically (Windows only)
- **Project Repair**: Fix damaged or corrupted terrain files

## Available Tools

### create_gaea2_project

Create a new Gaea2 terrain project with nodes and connections.

**Parameters:**
- `project_name` (required): Name for the project
- `workflow`: Complete workflow object with nodes and connections
- `nodes`: List of nodes (alternative to workflow)
- `connections`: List of connections (alternative to workflow)
- `output_path`: Path to save the .terrain file
- `auto_validate`: Automatically validate and fix (default: true)

**Example:**
```json
{
  "tool": "create_gaea2_project",
  "arguments": {
    "project_name": "mountain_terrain",
    "nodes": [
      {
        "id": "1",
        "type": "Mountain",
        "properties": {"Height": 0.8, "Scale": 0.5}
      },
      {
        "id": "2",
        "type": "Erosion2",
        "properties": {"Duration": 15}
      }
    ],
    "connections": [
      {
        "from_node": "1",
        "from_port": "Out",
        "to_node": "2",
        "to_port": "In"
      }
    ]
  }
}
```

### create_gaea2_from_template

Create a project from professional templates.

**Available Templates:**
- `basic_terrain` - Simple terrain with erosion
- `detailed_mountain` - Complex mountain with multiple erosion passes
- `volcanic_terrain` - Volcano with lava flows
- `desert_canyon` - Canyon system with sediment
- `modular_portal_terrain` - Modular terrain sections
- `mountain_range` - Mountain range with valleys
- `volcanic_island` - Island with volcanic features
- `canyon_system` - Complex canyon network
- `coastal_cliffs` - Coastal terrain with cliffs
- `arctic_terrain` - Arctic/tundra landscape
- `river_valley` - River valley system

**Example:**
```json
{
  "tool": "create_gaea2_from_template",
  "arguments": {
    "template_name": "mountain_range",
    "project_name": "my_mountains"
  }
}
```

### validate_and_fix_workflow

Validate and automatically fix workflow issues.

**Features:**
- Removes duplicate connections
- Corrects out-of-range property values
- Adds missing required nodes (Export, SatMap)
- Removes orphaned nodes
- Ensures connection validity

**Example:**
```json
{
  "tool": "validate_and_fix_workflow",
  "arguments": {
    "workflow": {
      "nodes": [...],
      "connections": [...]
    },
    "strict_mode": false
  }
}
```

### analyze_workflow_patterns

Analyze workflows for patterns and improvements.

**Analysis Types:**
- `patterns` - Common node sequences and distribution
- `performance` - Performance characteristics
- `quality` - Quality issues and enhancements
- `all` - Complete analysis

**Example:**
```json
{
  "tool": "analyze_workflow_patterns",
  "arguments": {
    "workflow": {...},
    "analysis_type": "all"
  }
}
```

### optimize_gaea2_properties

Optimize node properties for different goals.

**Optimization Modes:**
- `performance` - Faster generation, lower quality
- `quality` - Best quality, slower generation
- `balanced` - Balance between speed and quality

**Example:**
```json
{
  "tool": "optimize_gaea2_properties",
  "arguments": {
    "nodes": [...],
    "optimization_mode": "balanced"
  }
}
```

### suggest_gaea2_nodes

Get intelligent node suggestions based on current workflow.

**Example:**
```json
{
  "tool": "suggest_gaea2_nodes",
  "arguments": {
    "current_nodes": ["Mountain", "Erosion2"],
    "context": "Creating realistic terrain"
  }
}
```

### repair_gaea2_project

Repair damaged or corrupted project files.

**Example:**
```json
{
  "tool": "repair_gaea2_project",
  "arguments": {
    "project_path": "/path/to/damaged.terrain",
    "backup": true
  }
}
```

### run_gaea2_project (Windows only)

Execute a Gaea2 project to generate terrain outputs.

**Parameters:**
- `project_path` (required): Path to .terrain file
- `resolution`: Output resolution (512, 1024, 2048, 4096, 8192)
- `format`: Output format (exr, raw, png, tiff)
- `bake_only`: List of specific nodes to bake
- `timeout`: Execution timeout in seconds

**Example:**
```json
{
  "tool": "run_gaea2_project",
  "arguments": {
    "project_path": "/path/to/project.terrain",
    "resolution": "2048",
    "format": "exr"
  }
}
```

## Running the Server

### HTTP Mode

```bash
python -m tools.mcp.gaea2.server --mode http
```

The server will start on port 8007 by default.

### stdio Mode (for Claude Desktop)

```bash
python -m tools.mcp.gaea2.server --mode stdio
```

### With Gaea2 CLI Support (Windows)

```bash
python -m tools.mcp.gaea2.server --gaea-path "C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe"
```

## Requirements

### For Project Creation/Validation
- Python 3.7+
- No special requirements (works on all platforms)

### For CLI Automation
- Windows OS
- Gaea2 installed
- Valid Gaea2 license

## Docker Support

The Gaea2 MCP Server can run in a container for project creation and validation:

```dockerfile
FROM python:3.11-slim

# Copy server code
COPY tools/mcp/gaea2 /app/gaea2
COPY tools/mcp/core /app/core

# Note: CLI automation requires Windows host with Gaea2
WORKDIR /app
CMD ["python", "-m", "gaea2.server"]
```

## Configuration

### Environment Variables

- `GAEA2_PATH`: Path to Gaea2 executable (for CLI automation)
- `MCP_GAEA2_PORT`: Server port (default: 8007)
- `MCP_GAEA2_OUTPUT_DIR`: Output directory (default: /app/output/gaea2)

## Node Categories

The server supports all 185 Gaea2 nodes across 9 categories:

1. **Terrain** (25 nodes): Mountain, Ridge, Canyon, etc.
2. **Erosion** (18 nodes): Erosion2, Thermal, Rivers, etc.
3. **Color** (13 nodes): SatMap, ColorTerrain, BiomeMapper, etc.
4. **Filters** (35 nodes): Blur, Sharpen, Terrace, etc.
5. **Combiners** (8 nodes): Combine, Blend, Mix, etc.
6. **Data** (28 nodes): Constant, Gradient, Noise, etc.
7. **Utility** (31 nodes): Transform, Warp, Mask, etc.
8. **Output** (11 nodes): Export, Build, Cache, etc.
9. **Modifiers** (16 nodes): Adjust, Clamp, Normalize, etc.

## Common Patterns

Based on analysis of 31 real projects:

1. **Most Common Workflow**: Slump → FractalTerraces → Combine → Shear
2. **Most Used Nodes**: SatMap (47), Combine (38), Erosion2 (29)
3. **Average Complexity**: 12.1 nodes, 14.2 connections

## Performance Tips

1. **Use Templates**: Start with templates for common terrain types
2. **Validate Early**: Use auto_validate to catch issues early
3. **Optimize Properties**: Use optimization tools for better performance
4. **Cache Results**: The server caches validation results for speed
5. **Batch Operations**: Process multiple nodes/connections together

## Error Recovery

All project creation automatically includes:
- ✅ Duplicate connection removal
- ✅ Property value correction
- ✅ Required node addition
- ✅ Orphaned node handling
- ✅ Connection validation
- ✅ Format compatibility

## Testing

Run the test scripts to verify functionality:

```bash
# Test basic functionality
python tools/mcp/gaea2/scripts/test_server.py

# Test project creation
python tools/mcp/gaea2/scripts/test_creation.py

# Test CLI automation (Windows only)
python tools/mcp/gaea2/scripts/test_cli.py
```

## Troubleshooting

### "Gaea2 not found" Error

1. Set `GAEA2_PATH` environment variable
2. Or provide `--gaea-path` command line argument
3. CLI automation only works on Windows with Gaea2 installed

### Project Won't Open in Gaea2

1. Ensure you're using a supported template
2. Check that auto_validate is enabled
3. Try repair_gaea2_project tool

### Performance Issues

1. Use lower resolution for testing
2. Optimize properties with optimize_gaea2_properties
3. Reduce number of heavy nodes (Erosion2, Rivers, etc.)
