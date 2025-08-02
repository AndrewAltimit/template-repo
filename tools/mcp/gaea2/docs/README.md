# Gaea2 Terrain Generation MCP Server

The Gaea2 MCP Server provides comprehensive tools for programmatic terrain generation with Gaea2, including project creation, validation, optimization, and CLI automation.

## Features

- **Complete Node Support**: All 185 documented Gaea2 nodes across 9 categories
- **Intelligent Validation**: Multi-level validation with automatic error correction
- **Pattern Intelligence**: Learning from 31 real projects (374 nodes, 440 connections)
- **Professional Templates**: Ready-to-use workflows for common terrain types
- **CLI Automation**: Run Gaea2 projects programmatically (Windows only)
- **Auto-Fix Capabilities**: Automatic detection and correction of common issues
- **HTTP Streamable Transport**: Supports remote server deployment with full MCP protocol compliance

## Important Requirements

⚠️ **This server MUST run on a Windows host system where Gaea2 is installed!**

The server requires direct access to the Gaea2 executable for CLI automation and cannot run inside a container.

## Configuration

### Claude Code Configuration (.mcp.json)

Configure the Gaea2 server in your `.mcp.json` file:

```json
{
  "mcpServers": {
    "gaea2": {
      "type": "http",
      "url": "http://192.168.0.152:8007/messages"
    }
  }
}
```

**Important**: The URL must point to the `/messages` endpoint, not `/mcp`.

### Local Configuration

For local development:

```json
{
  "mcpServers": {
    "gaea2": {
      "type": "http",
      "url": "http://localhost:8007/messages"
    }
  }
}
```

### Running the Server

1. **On Windows with Gaea2 installed:**
   ```bash
   python -m tools.mcp.gaea2.server --mode http
   ```

2. **The server will automatically detect Gaea2 at common installation paths:**
   - `C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe`
   - `C:\Program Files (x86)\QuadSpinner\Gaea\Gaea.Swarm.exe`

3. **Or specify a custom path:**
   ```bash
   python -m tools.mcp.gaea2.server --mode http --gaea-path "D:\Gaea\Gaea.Swarm.exe"
   ```

### Connection Troubleshooting

If Claude Code shows "Status: ✘ failed", check:

1. **Server is running** - Verify the server is accessible at the configured URL
2. **Correct endpoint** - Must use `/messages` not `/mcp`
3. **OAuth flow** - The server implements simplified OAuth for local use
4. **Session management** - Server generates session IDs automatically

For detailed HTTP transport configuration, see [MCP Server Modes Documentation](../../../../docs/mcp/STDIO_VS_HTTP_MODES.md#http-mode-technical-implementation).

## Available Tools

### create_gaea2_project

Create a custom Gaea2 terrain project with automatic validation.

**Parameters:**
- `project_name` (required): Name for the terrain project
- `workflow`: Workflow dictionary containing nodes and connections
- `nodes`: List of node definitions (alternative to workflow)
- `connections`: List of connection definitions (alternative to workflow)
- `variables`: Project variables for automation
- `auto_validate`: Automatically validate and fix issues (default: true)
- `property_mode`: Property generation mode (default: "smart")
  - Options: smart, essential, full

**Example:**
```json
{
  "tool": "create_gaea2_project",
  "parameters": {
    "project_name": "mountain_terrain",
    "nodes": [
      {"id": "01", "type": "Mountain", "properties": {"Height": 0.5}},
      {"id": "02", "type": "Erosion2", "properties": {"Duration": 0.3}}
    ],
    "connections": [
      {"source": "01", "target": "02", "sourcePort": "Out", "targetPort": "In"}
    ]
  }
}
```

### create_gaea2_from_template

Create a Gaea2 project from professional templates (most reliable method).

**Parameters:**
- `template_name` (required): Name of the template to use
  - Options: basic_terrain, detailed_mountain, volcanic_terrain, desert_canyon, modular_portal_terrain, mountain_range, volcanic_island, canyon_system, coastal_cliffs, arctic_terrain, river_valley
- `project_name` (required): Name for the terrain project
- `variables`: Override template variables

**Example:**
```json
{
  "tool": "create_gaea2_from_template",
  "parameters": {
    "template_name": "mountain_range",
    "project_name": "my_mountains"
  }
}
```

### validate_and_fix_workflow

Validate and automatically fix issues in a Gaea2 workflow.

**Parameters:**
- `workflow` (required): Workflow to validate
- `fix_errors`: Automatically fix detected errors (default: true)
- `add_missing_nodes`: Add required nodes if missing (default: true)
- `optimize_connections`: Optimize connection routing (default: true)
- `property_mode`: Property generation mode for fixes (default: "smart")

**Example:**
```json
{
  "tool": "validate_and_fix_workflow",
  "parameters": {
    "workflow": {
      "nodes": [...],
      "connections": [...]
    }
  }
}
```

### analyze_workflow_patterns

Get pattern-based suggestions from 31 real-world projects.

**Parameters:**
- `workflow` (required): Current workflow to analyze
- `suggestion_type`: Type of suggestions (default: "all")
  - Options: all, connections, nodes, properties, patterns

**Example:**
```json
{
  "tool": "analyze_workflow_patterns",
  "parameters": {
    "workflow": {...},
    "suggestion_type": "connections"
  }
}
```

### optimize_gaea2_properties

Optimize node properties for performance or quality.

**Parameters:**
- `workflow` (required): Workflow to optimize
- `optimization_mode`: Optimization target (default: "balanced")
  - Options: performance, quality, balanced
- `target_nodes`: Specific nodes to optimize (optional)

**Example:**
```json
{
  "tool": "optimize_gaea2_properties",
  "parameters": {
    "workflow": {...},
    "optimization_mode": "performance"
  }
}
```

### suggest_gaea2_nodes

Get intelligent node suggestions based on context.

**Parameters:**
- `current_nodes` (required): List of current node types
- `target_output`: Desired output type (optional)
  - Options: heightfield, mask, color, water
- `complexity_level`: Desired complexity (default: "medium")
  - Options: simple, medium, complex

**Example:**
```json
{
  "tool": "suggest_gaea2_nodes",
  "parameters": {
    "current_nodes": ["Mountain", "Erosion"],
    "target_output": "mask"
  }
}
```

### repair_gaea2_project

Repair a damaged or corrupted Gaea2 project file.

**Parameters:**
- `project_path` (required): Path to the damaged project file
- `output_path`: Where to save repaired project (optional)
- `backup_original`: Create backup before repair (default: true)

**Example:**
```json
{
  "tool": "repair_gaea2_project",
  "parameters": {
    "project_path": "damaged_terrain.terrain",
    "backup_original": true
  }
}
```

### run_gaea2_project

Run a Gaea2 project via CLI (Windows only).

**Parameters:**
- `project_path` (required): Path to the .terrain file
- `output_dir`: Output directory for builds (optional)
- `variables`: Variables to pass to the project
- `resolution`: Build resolution (default: "512")
  - Options: 512, 1024, 2048, 4096, 8192
- `format`: Output format (default: "png")
  - Options: png, tiff, exr, raw

**Example:**
```json
{
  "tool": "run_gaea2_project",
  "parameters": {
    "project_path": "mountain.terrain",
    "resolution": "2048",
    "variables": {"Height": 0.8, "Erosion": 0.3}
  }
}
```

### validate_gaea2_project

Validate a Gaea2 project file structure and format.

**Parameters:**
- `project_path` (required): Path to the .terrain file
- `detailed`: Return detailed validation report (default: true)

**Example:**
```json
{
  "tool": "validate_gaea2_project",
  "parameters": {
    "project_path": "my_terrain.terrain"
  }
}
```

### analyze_execution_history

Analyze the history of Gaea2 CLI executions.

**Parameters:**
- `limit`: Number of recent executions to analyze (default: 10)
- `include_output`: Include full output logs (default: false)

**Example:**
```json
{
  "tool": "analyze_execution_history",
  "parameters": {
    "limit": 5,
    "include_output": true
  }
}
```

## Running the Server

### Prerequisites

1. **Windows OS** (Windows 10/11)
2. **Gaea2 installed** (Community or Professional edition)
3. **Python 3.8+** with required packages:
   ```bash
   pip install aiohttp aiofiles
   ```

### Setting up Gaea2 Path

Set the `GAEA2_PATH` environment variable to your Gaea.Swarm.exe location:

```powershell
# PowerShell
$env:GAEA2_PATH = "C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe"

# Or permanently in System Environment Variables
```

### HTTP Mode

```bash
# Default port 8007
python -m tools.mcp.gaea2.server --mode http

# Custom port
python -m tools.mcp.gaea2.server --mode http --port 8008
```

### stdio Mode (for Claude Desktop)

```bash
python -m tools.mcp.gaea2.server --mode stdio
```

## Configuration

### Environment Variables

- `GAEA2_PATH`: Path to Gaea.Swarm.exe (required for CLI features)
- `GAEA2_MCP_PORT`: Server port (default: 8007)
- `GAEA2_MCP_HOST`: Server host (default: localhost)
- `GAEA2_LOG_LEVEL`: Logging level (default: INFO)
- `GAEA2_CACHE_ENABLED`: Enable performance cache (default: true)
- `GAEA2_AUTO_VALIDATE`: Auto-validate all projects (default: true)

## Remote Access

The server can be accessed remotely if configured:

```bash
# Start server accessible from network
python -m tools.mcp.gaea2.server --mode http --host 0.0.0.0

# Access from another machine
curl -X POST http://192.168.0.152:8007/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "create_gaea2_from_template", ...}'
```

## Testing

Run the test script to verify the server is working:

```bash
python tools/mcp/gaea2/scripts/test_server.py
```

The test script will:
1. Check server health
2. List available tools
3. Test template creation
4. Test validation features
5. Test pattern analysis
6. Verify error handling

## Common Patterns

Based on analysis of 31 real projects:

- **Most common workflow**: Slump → FractalTerraces → Combine → Shear
- **Most used nodes**: SatMap (47), Combine (38), Erosion2 (29)
- **Average complexity**: 12.1 nodes, 14.2 connections

## Property Limitations

Some nodes must have limited properties to ensure file compatibility:

- **Snow**: Max 3 properties (Duration, SnowLine, Melt)
- **Beach**: Max 2 properties (Width, Slope)
- **Lakes**: Max 2 properties (Count, Size)

The `property_mode="smart"` setting handles this automatically.

## Error Handling

The server provides comprehensive error handling:

- **Validation errors**: Detailed reports with fix suggestions
- **Missing dependencies**: Clear messages about required tools
- **Format issues**: Automatic correction where possible
- **Connection errors**: Port compatibility checking
- **File corruption**: Automatic repair capabilities

## Performance Considerations

- **Caching**: 19x speedup through intelligent caching
- **Validation**: Automatic validation adds minimal overhead
- **Templates**: Fastest method for project creation
- **CLI execution**: Performance depends on project complexity

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
- name: Generate Terrain
  run: |
    # Start server
    python -m tools.mcp.gaea2.server --mode http &
    sleep 2

    # Create terrain
    curl -X POST http://localhost:8007/mcp/execute \
      -d '{"tool": "create_gaea2_from_template",
           "parameters": {"template_name": "mountain_range",
                         "project_name": "ci_terrain"}}'
```

## Troubleshooting

### "Gaea2 not found" Error

1. Install Gaea2 from QuadSpinner
2. Set `GAEA2_PATH` environment variable
3. Verify path is correct

### "Cannot run in container" Error

The server must run on Windows host with Gaea2 installed. It cannot run in Docker.

### Template Creation Works but Custom Fails

Use templates when possible - they're the most reliable method. Custom creation is being refined.

### Connection Issues

Ensure ports are named correctly:
- Standard nodes: "In", "Out"
- Combine nodes: "In", "Input2", "Mask"
- Special nodes have unique ports (check schema)

## Additional Documentation

For comprehensive documentation, see:
- `/docs/gaea2/INDEX.md` - Complete documentation index
- `/docs/gaea2/README.md` - Main Gaea2 MCP documentation
- `/docs/gaea2/GAEA2_API_REFERENCE.md` - Complete API reference
- `/docs/gaea2/GAEA2_EXAMPLES.md` - Usage examples and patterns
- `/docs/gaea2/GAEA2_MCP_SERVER.md` - Standalone server guide
