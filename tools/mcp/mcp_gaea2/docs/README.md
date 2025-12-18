# Gaea2 MCP Server

> **A Model Context Protocol server for programmatic terrain generation with Gaea2, featuring intelligent validation, pattern-based suggestions, and professional workflow templates**

## Overview

The Gaea2 MCP server enables programmatic creation of terrain projects through the Model Context Protocol. It provides intelligent validation, automatic error recovery, and pattern-based workflow suggestions derived from analysis of production Gaea2 projects.

**Requirements**: This server must run on a Windows host with Gaea2 installed. It uses HTTP transport for cross-machine communication since most development environments run on Linux/Mac.

## Implementation Status

| Component | Status | Description |
|-----------|--------|-------------|
| Project Generation | Validated | Creates .terrain files compatible with Gaea2 2.2.6.0 |
| Structural Validation | Enabled | Automatic node/connection validation and repair |
| Runtime CLI Validation | Disabled by default | Optional validation via Gaea.Swarm.exe |
| Template System | 11 templates | Professional workflow templates from YAML definitions |
| Pattern Intelligence | Implemented | Suggestions based on 31 analyzed projects |
| CLI Automation | Windows only | Build automation via Gaea.Swarm.exe |

## Quick Start

### Server Setup

```bash
# Start server on Windows host
python -m mcp_gaea2.server --mode http --port 8007

# With custom Gaea2 path
python -m mcp_gaea2.server --mode http --gaea-path "D:\Gaea\Gaea.Swarm.exe"

# Enable runtime CLI validation (optional)
python -m mcp_gaea2.server --mode http --enforce-file-validation
```

### Client Configuration

Add to `.mcp.json`:

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

### Basic Usage

```python
import requests

# Create terrain from template (recommended)
response = requests.post('http://192.168.0.152:8007/mcp/execute', json={
    'tool': 'create_gaea2_from_template',
    'parameters': {
        'template_name': 'volcanic_terrain',
        'project_name': 'volcano_test'
    }
})

# Create custom terrain
response = requests.post('http://192.168.0.152:8007/mcp/execute', json={
    'tool': 'create_gaea2_project',
    'parameters': {
        'project_name': 'custom_terrain',
        'workflow': {
            'nodes': [
                {'id': '1', 'type': 'Mountain', 'properties': {'Scale': 1.5}},
                {'id': '2', 'type': 'Erosion2'},
                {'id': '3', 'type': 'Export'}
            ],
            'connections': [
                {'from_node': '1', 'to_node': '2'},
                {'from_node': '2', 'to_node': '3'}
            ]
        }
    }
})
```

## Available Tools

### Project Creation

| Tool | Description | Reliability |
|------|-------------|-------------|
| `create_gaea2_from_template` | Create from professional templates | High |
| `create_gaea2_project` | Create with custom node/connection spec | Medium |

### Validation and Repair

| Tool | Description |
|------|-------------|
| `validate_and_fix_workflow` | Comprehensive validation with automatic repair |
| `repair_gaea2_project` | Repair damaged project files |
| `validate_gaea2_runtime` | Runtime validation via Gaea2 CLI (optional) |

### Analysis and Suggestions

| Tool | Description |
|------|-------------|
| `analyze_workflow_patterns` | Pattern-based workflow analysis |
| `suggest_gaea2_nodes` | Intelligent node suggestions |
| `optimize_gaea2_properties` | Performance/quality optimization |

### CLI Automation (Windows)

| Tool | Description |
|------|-------------|
| `run_gaea2_project` | Execute terrain build via CLI |
| `analyze_execution_history` | Debug CLI execution history |

### File Management

| Tool | Description |
|------|-------------|
| `list_gaea2_projects` | List available terrain files |
| `download_gaea2_project` | Download terrain with metadata |

## Templates

Available workflow templates derived from production projects:

| Template | Description |
|----------|-------------|
| `basic_terrain` | Simple terrain with erosion and coloring |
| `detailed_mountain` | Mountain with rivers, snow, and strata |
| `volcanic_terrain` | Volcanic landscape with lava features |
| `desert_canyon` | Desert canyon with stratification |
| `mountain_range` | Multiple peaks with varied erosion |
| `volcanic_island` | Island with volcanic and coastal features |
| `canyon_system` | Complex canyon network |
| `coastal_cliffs` | Coastal terrain with cliff formations |
| `river_valley` | Valley with water features |
| `modular_portal_terrain` | Modular terrain for portal worlds |

Templates are the most reliable method for terrain creation. Custom projects require careful attention to node specifications and property formats.

## Validation System

### Structural Validation (Default)

Automatically applied to all created projects:

- Node type and property validation
- Connection compatibility verification
- Missing node detection (adds Export if absent)
- Property range clamping
- Duplicate connection removal
- Orphan node connection

### Runtime CLI Validation (Optional)

Runtime validation using Gaea.Swarm.exe is disabled by default due to reliability issues with the CLI subprocess. Enable with `--enforce-file-validation` flag or `runtime_validate=True` parameter.

**Note**: Files that fail CLI validation may still open correctly in the Gaea2 GUI. The structural validation is sufficient for most use cases.

## Node Support

The server supports 184 Gaea2 node types across 9 categories:

| Category | Count | Description |
|----------|-------|-------------|
| Primitive | 24 | Noise generators and basic patterns |
| Terrain | 14 | Primary terrain generators |
| Modify | 41 | Terrain modification tools |
| Surface | 21 | Surface detail and texture |
| Simulate | 25 | Natural process simulation |
| Derive | 13 | Analysis and mask generation |
| Colorize | 13 | Color and texture operations |
| Output | 13 | Export and integration |
| Utility | 20 | Helper and utility nodes |

## Pattern Intelligence

Analysis of 31 production Gaea2 projects provides:

- **Common Workflow**: Slump -> FractalTerraces -> Combine -> Shear (9 occurrences)
- **Most Used Nodes**: SatMap (47), Combine (38), Erosion2 (29)
- **Average Complexity**: 12.1 nodes, 14.2 connections per project

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GAEA2_PATH` | Auto-detected | Path to Gaea.Swarm.exe |
| `GAEA2_MCP_PORT` | 8007 | Server port |
| `GAEA2_MCP_HOST` | localhost | Server host |
| `GAEA2_LOG_LEVEL` | INFO | Logging level |
| `GAEA2_AUTO_VALIDATE` | true | Auto-validate projects |

### Command Line Arguments

```bash
python -m mcp_gaea2.server [OPTIONS]

Options:
  --mode http              Transport mode (http only)
  --port PORT              Server port (default: 8007)
  --host HOST              Server host (default: localhost)
  --gaea-path PATH         Path to Gaea.Swarm.exe
  --output-dir DIR         Output directory for terrain files
  --enforce-file-validation  Enable runtime CLI validation
```

## Troubleshooting

### Server Issues

| Issue | Solution |
|-------|----------|
| "Gaea2 not found" | Set `GAEA2_PATH` to Gaea.Swarm.exe location |
| "Cannot run in container" | Server must run on Windows host |
| Connection refused | Verify server is running and port is accessible |

### Generation Issues

| Issue | Solution |
|-------|----------|
| Template works, custom fails | Use templates when possible; review property formats |
| Invalid connections | Check port names (In, Out, Input2, Mask) |
| Properties ignored | Use space-separated names ("Rock Softness" not "RockSoftness") |

### Format Requirements

- **Property names**: Space-separated ("Rock Softness", not "RockSoftness")
- **Range properties**: Must include $id: `{"$id": "103", "X": 0.5, "Y": 1.0}`
- **Node IDs**: Non-sequential recommended (183, 668, 427)
- **Combine nodes**: Require `PortCount: 2` property

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](GAEA2_API_REFERENCE.md) | Complete API documentation |
| [Examples](GAEA2_EXAMPLES.md) | Code examples and patterns |
| [Quick Reference](GAEA2_QUICK_REFERENCE.md) | Quick reference guide |
| [Knowledge Base](GAEA2_KNOWLEDGE_BASE.md) | Pattern intelligence data |
| [Connection Architecture](CONNECTION_ARCHITECTURE.md) | Connection system internals |
| [Node Properties](GAEA2_NODE_PROPERTIES_EXTENDED.md) | Complete property documentation |
| [Template Reference](GAEA2_TEMPLATE_REFERENCE.md) | Template specifications |
| [Node Reference](GAEA2_NODE_REFERENCE.md) | Node type reference |

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Quick server connectivity test
python scripts/test_server.py

# Test template generation
python scripts/test_gaea2_templates.py
```

## Architecture

```
mcp_gaea2/
├── server.py              # MCP server implementation
├── generation/
│   ├── project_generator.py  # Core terrain generation
│   ├── generator.py          # Generator wrapper
│   └── templates.py          # Template system
├── validation/
│   ├── validator.py          # Structural validation
│   └── gaea2_file_validator.py  # Runtime CLI validation
├── schema/
│   ├── nodes.yaml            # Node definitions
│   └── schema_loader.py      # YAML schema loading
└── templates/
    └── templates.yaml        # Template definitions
```

---

*Pattern intelligence derived from analysis of 31 production Gaea2 projects containing 374 nodes and 440 connections.*
