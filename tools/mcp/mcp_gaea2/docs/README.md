# Gaea2 MCP (Model Context Protocol) Server

A comprehensive, intelligent terrain generation toolkit for Gaea2, providing programmatic control over terrain creation with advanced validation, error recovery, and pattern-based intelligence.

## 🚀 Overview

The Gaea2 MCP server enables programmatic creation and manipulation of Gaea2 terrain projects through the Model Context Protocol. It includes intelligent validation, automatic error recovery, pattern-based suggestions, and support for Gaea2 nodes.

### Key Features

- **Intelligent Validation**: Multi-level validation with automatic error correction
- **Pattern Intelligence**: Learning from 31 real projects (374 nodes, 440 connections)
- **Professional Templates**: 11 ready-to-use workflow templates
- **CLI Automation**: Run Gaea2 projects programmatically (Windows only)
- **Auto-Fix Capabilities**: Automatic detection and correction of common issues
- **Performance Optimization**: 19x speedup through intelligent caching
- **HTTP Transport**: Uses HTTP transport for cross-machine communication

## 🔌 Transport Mode: HTTP Only

**Why HTTP Transport?**
The Gaea2 server uses HTTP transport (not STDIO) because it must run on a Windows machine with Gaea2 software installed. This is a hardware/software constraint - most development environments run on Linux/Mac, but Gaea2 requires Windows.

## ⚠️ Important Requirements

**This server MUST run on a Windows host system where Gaea2 is installed!**

The server requires direct access to the Gaea2 executable (`Gaea.Swarm.exe`) for CLI automation and validation features. This Windows requirement is why the server uses HTTP transport for remote access from other machines.

## 📋 Prerequisites

1. **Windows OS** (Windows 10/11)
2. **Gaea2 installed** (Community or Professional edition)
3. **Python 3.8+** with required packages:
   ```bash
   pip install aiohttp aiofiles
   ```

## 🔧 Configuration

### Environment Variables

- `GAEA2_PATH`: Path to Gaea.Swarm.exe (auto-detected if not set)
- `GAEA2_MCP_PORT`: Server port (default: 8007)
- `GAEA2_MCP_HOST`: Server host (default: localhost)
- `GAEA2_LOG_LEVEL`: Logging level (default: INFO)
- `GAEA2_CACHE_ENABLED`: Enable performance cache (default: true)
- `GAEA2_AUTO_VALIDATE`: Auto-validate all projects (default: true)

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

**Important**: The URL must point to the `/messages` endpoint for MCP protocol compliance.

### Local Development Configuration

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

## 🚦 Running the Server

### HTTP Mode (Recommended)

```bash
# Default port 8007
python -m tools.mcp.gaea2.server --mode http

# Custom port
python -m tools.mcp.gaea2.server --mode http --port 8008

# Specify Gaea2 path
python -m tools.mcp.gaea2.server --mode http --gaea-path "D:\Gaea\Gaea.Swarm.exe"
```

### Remote Access Setup

```bash
# Start server accessible from network
python -m tools.mcp.gaea2.server --mode http --host 0.0.0.0

# Access from another machine
curl -X POST http://192.168.0.152:8007/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "create_gaea2_from_template", ...}'
```

## 🛠️ Available MCP Tools

### 1. create_gaea2_project
Create custom Gaea2 terrain projects with automatic validation and error correction.

```python
result = await create_gaea2_project(
    project_name="Alpine Valley",
    nodes=[
        {"type": "Mountain", "properties": {"Scale": 1.5}},
        {"type": "Erosion2", "properties": {"Duration": 0.07}}
    ],
    connections=[{"from_node": 0, "to_node": 1}],
    auto_validate=True  # Default: True
)
```

**Automatic features included:**
- ✅ Validates all node types and properties
- ✅ Fixes invalid property values to valid ranges
- ✅ Adds missing Export node if not present
- ✅ Adds SatMap/ColorMap node if no coloring exists
- ✅ Repairs invalid or duplicate connections
- ✅ Ensures Gaea2-compatible file format

### 2. create_gaea2_from_template
Create projects using professional workflow templates (most reliable method).

Available templates:
- `basic_terrain` - Simple terrain with erosion and coloring
- `detailed_mountain` - Advanced mountain with rivers, snow, and strata
- `volcanic_terrain` - Volcanic landscape with lava and ash
- `desert_canyon` - Desert canyon with stratification
- `modular_portal_terrain` - Modular terrain for portal worlds
- `mountain_range` - Mountain range with varied peaks
- `volcanic_island` - Volcanic island with coastal features
- `canyon_system` - Complex canyon network
- `coastal_cliffs` - Coastal terrain with cliff formations
- `river_valley` - River valley with water features

**Note**: The `arctic_terrain` template is currently corrupted and will fail validation.

### 3. validate_and_fix_workflow
Comprehensive validation and automatic repair of Gaea2 workflows.

### 4. analyze_workflow_patterns
Analyze workflows to get intelligent suggestions based on real project patterns.

### 5. optimize_gaea2_properties
Optimize node properties for performance or quality.

### 6. suggest_gaea2_nodes
Get intelligent node suggestions based on terrain type and context.

### 7. repair_gaea2_project
Repair damaged or corrupted Gaea2 project files.

### 8. run_gaea2_project
Run a Gaea2 project via CLI to generate terrain (Windows only).

### 9. analyze_execution_history
Analyze the history of Gaea2 CLI executions for debugging.

### 10. download_gaea2_project
Download previously created terrain files with optional metadata extraction.

### 11. list_gaea2_projects
List all terrain files in the output directory.

## 📊 Node Categories & Support

### Supported Node Categories

1. **🟢 Primitive (24 nodes)** - Noise generators and basic patterns
2. **🟢 Terrain (14 nodes)** - Primary terrain generators
3. **🔵 Modify (41 nodes)** - Terrain modification tools
4. **🟡 Surface (21 nodes)** - Surface detail and texture
5. **🟠 Simulate (25 nodes)** - Natural process simulation
6. **⚪ Derive (13 nodes)** - Analysis and mask generation
7. **🟣 Colorize (13 nodes)** - Color and texture operations
8. **🔴 Output (13 nodes)** - Export and integration nodes
9. **⚫ Utility (20 nodes)** - Helper and utility nodes

## 🧠 Intelligence Features

### Pattern-Based Knowledge

The system has analyzed 31 real Gaea2 projects to extract common patterns:

- **Most Common Workflow**: Slump → FractalTerraces → Combine → Shear (9 occurrences)
- **Most Used Nodes**: SatMap (47), Combine (38), Erosion2 (29)
- **Average Complexity**: 12.1 nodes, 14.2 connections per project

### Validation Levels

1. **Structure Validation** - Ensures valid Gaea2 project format
2. **Node Validation** - Validates node types and configurations
3. **Property Validation** - Type checking and range validation
4. **Connection Validation** - Ensures compatible connections
5. **Pattern Validation** - Checks against known good patterns

### Automatic Error Recovery

All projects created with `create_gaea2_project` automatically include:
- Remove duplicate connections
- Fix out-of-range property values
- Add missing required nodes (Export, SatMap)
- Connect orphaned nodes intelligently
- Optimize workflow order
- Validate node property types
- Ensure connection compatibility
- Performance optimization for heavy nodes

## 🔍 File Validation System

The Gaea2 MCP server includes an automated validation system to test if generated terrain files actually open in Gaea2.

### Validation Features

- **Automated Testing**: Uses `Gaea.Swarm.exe --validate` to check if files open
- **Real-time Monitoring**: Reads stdout/stderr as Gaea2 runs
- **Smart Detection**: Identifies success and failure patterns
- **Timeout Handling**: Prevents hanging on problematic files
- **Batch Processing**: Test multiple files efficiently

### How It Works

1. **Real-time Monitoring**: Reads Gaea2 output in real-time
2. **Success Detection**: Looks for patterns like "Opening [filename]", "Loading devices"
3. **Error Detection**: Fails immediately on "corrupt", "failed to load", "missing data"
4. **Smart Confirmation**: Waits 3 seconds after success detection to ensure no errors
5. **Process Control**: Kills Gaea2 after determining result

## 📈 Performance

- **Caching System**: 19x speedup for repeated operations
- **In-Memory Cache**: Fast access with TTL support
- **Disk Persistence**: Optional cache persistence
- **Optimized Validation**: Efficient pattern matching
- **Average Project Size**: 12.1 nodes, 14.2 connections
- **Validation Speed**: <100ms for average projects
- **Auto-Fix Success Rate**: 85% of common issues

## 🧪 Testing

Run the test scripts to verify the server is working:

```bash
# Quick connectivity test
python tools/mcp/gaea2/scripts/test_server.py

# Test improved validation
python tools/mcp/gaea2/scripts/test_improved_validation.py

# Test all templates
python tools/mcp/gaea2/scripts/test_gaea2_templates.py
```

## 🔧 Troubleshooting

### Common Issues

#### "Gaea2 not found" Error
1. Install Gaea2 from QuadSpinner
2. Set `GAEA2_PATH` environment variable
3. Verify path points to `Gaea.Swarm.exe`

#### "Cannot run in container" Error
The server must run on Windows host with Gaea2 installed. Docker containers are not supported.

#### Connection Issues
Ensure ports are named correctly:
- Standard nodes: "In", "Out"
- Combine nodes: "In", "Input2", "Mask"
- Rivers: "Rivers" output port
- Sea: "Water", "Shore", "Depth" output ports

#### Template Creation Works but Custom Fails
Use templates when possible - they're the most reliable method. Custom creation requires careful attention to property formats and node specifications.

### Known Format Requirements

1. **Property Name Format**: Use spaces not camelCase
   - ✅ `"Rock Softness": 0.3`
   - ❌ `"RockSoftness": 0.3`

2. **Missing Node Properties**:
   - `PortCount: 2` on Combine nodes
   - `NodeSize: "Small"` or `"Standard"`
   - `IsMaskable: true` on most nodes

3. **Range Property Format**:
   - ✅ `{"$id": "103", "X": 0.5, "Y": 1.0}`
   - ❌ `{"X": 0.5, "Y": 1.0}`

4. **ID Pattern**: Use non-sequential IDs (183, 668, 427) not sequential (100, 110, 120)

## 📚 Additional Documentation

- [API Reference](GAEA2_API_REFERENCE.md) - Complete API documentation
- [Examples](GAEA2_EXAMPLES.md) - Code examples and usage patterns
- [Quick Reference](GAEA2_QUICK_REFERENCE.md) - Quick reference guide
- [Knowledge Base](GAEA2_KNOWLEDGE_BASE.md) - Patterns from real projects
- [Advanced Patterns](GAEA2_ADVANCED_PATTERNS.md) - Advanced workflow patterns
- [Connection Architecture](CONNECTION_ARCHITECTURE.md) - Deep dive into connection system
- [Node Properties](GAEA2_NODE_PROPERTIES_EXTENDED.md) - Complete property documentation
- [Validation Guide](VALIDATION_GUIDE.md) - File validation system guide
- [Changelog](CHANGELOG.md) - Version history and updates

## 🔗 Integration Examples

### CI/CD Pipeline Integration

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

### Python Client Example

```python
import requests
import json

# Create terrain from template
response = requests.post('http://192.168.0.152:8007/mcp/execute', json={
    'tool': 'create_gaea2_from_template',
    'parameters': {
        'template_name': 'volcanic_terrain',
        'project_name': 'volcano_test'
    }
})

result = response.json()
if result['success']:
    print(f"Created terrain: {result['output_path']}")
```

---

*Built with intelligence from analyzing 31 real Gaea2 projects containing 374 nodes and 440 connections.*
