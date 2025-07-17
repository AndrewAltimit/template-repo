# Gaea2 MCP Server

A standalone HTTP server that provides Model Context Protocol (MCP) tools for Gaea2 terrain generation, including CLI automation capabilities.

## Overview

The Gaea2 MCP Server runs on Windows hosts where Gaea2 is installed and provides:

- All existing Gaea2 project creation and manipulation features
- CLI automation for running Gaea2 projects programmatically
- Verbose logging and execution history
- Real-time terrain generation feedback

**Important**: This server MUST run on the Windows host system, not in a container, as it needs direct access to the Gaea2 executable.

## Features

### Core Capabilities

1. **Project Management**
   - Create Gaea2 projects with automatic validation
   - Repair damaged project files
   - Validate and fix workflows
   - Create projects from professional templates

2. **CLI Automation** (NEW!)
   - Run Gaea2 projects from command line
   - Pass variables to control terrain generation
   - Capture verbose output and parse results
   - Track execution history for debugging

3. **Intelligent Assistance**
   - Pattern-based workflow analysis
   - Node suggestions based on context
   - Property optimization for performance/quality
   - Learning from 31 real-world projects

## Installation

### Prerequisites

1. **Windows OS** (Windows 10/11 recommended)
2. **Gaea2 installed** (Community or Professional edition)
3. **Python 3.8+** installed and in PATH
4. **Required Python packages**:
   ```bash
   pip install aiohttp aiofiles
   ```

### Setup

1. **Clone or download the repository** containing the MCP tools

2. **Set the GAEA2_PATH environment variable** to your Gaea.Swarm.exe location:

   **Command Prompt:**
   ```cmd
   set GAEA2_PATH=C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe
   ```

   **PowerShell:**
   ```powershell
   $env:GAEA2_PATH = "C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe"
   ```

   **Permanent (System Environment Variable):**
   - Right-click "This PC" → Properties → Advanced System Settings
   - Click "Environment Variables"
   - Add new System variable: `GAEA2_PATH` = path to Gaea.Swarm.exe

3. **Start the server** using one of the provided scripts:

   **Batch script:**
   ```cmd
   scripts\start-gaea2-mcp.bat
   ```

   **PowerShell script:**
   ```powershell
   .\scripts\start-gaea2-mcp.ps1
   ```

   **Direct Python:**
   ```bash
   python tools/mcp/gaea2_mcp_server.py
   ```

The server will start on `http://localhost:8007`

## Usage

### Testing the Server

Run the test suite to verify everything is working:

```bash
python scripts/test-gaea2-mcp-server.py
```

### API Endpoints

- `GET /health` - Health check and server status
- `GET /mcp/tools` - List available tools
- `POST /mcp/execute` - Execute a tool

### Example: Create and Run a Terrain

```python
import requests
import json

# Server URL
GAEA2_URL = "http://localhost:8007"

# 1. Create a mountain terrain project
workflow = [
    {
        "id": "mountain_1",
        "type": "Mountain",
        "position": {"x": 0, "y": 0},
        "properties": {
            "seed": 42,
            "scale": 1.0,
            "height": 1.0
        }
    },
    {
        "id": "erosion_1",
        "type": "Erosion",
        "position": {"x": 200, "y": 0},
        "properties": {
            "iterations": 20,
            "downcutting": 0.3
        },
        "inputs": {
            "input": {"node": "mountain_1", "output": "output"}
        }
    },
    {
        "id": "export_1",
        "type": "Export",
        "position": {"x": 400, "y": 0},
        "properties": {
            "format": "png",
            "filename": "my_terrain"
        },
        "inputs": {
            "input": {"node": "erosion_1", "output": "output"}
        }
    }
]

# Create project
response = requests.post(f"{GAEA2_URL}/mcp/execute", json={
    "tool": "create_gaea2_project",
    "parameters": {
        "project_name": "mountain_terrain",
        "workflow": workflow,
        "auto_validate": True
    }
})

project = response.json()["project"]

# Save project to file
with open("mountain_terrain.terrain", "w") as f:
    json.dump(project, f, indent=2)

# 2. Run the project with CLI automation
response = requests.post(f"{GAEA2_URL}/mcp/execute", json={
    "tool": "run_gaea2_project",
    "parameters": {
        "project_path": "mountain_terrain.terrain",
        "verbose": True,
        "variables": {
            "erosion_strength": 0.5,
            "detail_level": 2
        }
    }
})

result = response.json()
print(f"Success: {result['success']}")
print(f"Command: {result['command']}")

if result.get("parsed_output"):
    output = result["parsed_output"]
    print(f"Nodes processed: {output['nodes_processed']}")
    print(f"Exports: {output['exports']}")
```

### Available Tools

1. **create_gaea2_project** - Create terrain with automatic validation
2. **run_gaea2_project** - Execute terrain generation via CLI
3. **validate_and_fix_workflow** - Comprehensive validation and repair
4. **analyze_execution_history** - Learn from previous runs
5. **create_gaea2_from_template** - Use professional templates
6. **analyze_workflow_patterns** - Analyze terrain patterns
7. **suggest_gaea2_nodes** - Get intelligent suggestions
8. **repair_gaea2_project** - Fix damaged projects
9. **optimize_gaea2_properties** - Optimize for performance/quality

## CLI Automation Details

### Gaea2 Command Line Arguments

The server uses Gaea's Build Swarm (`Gaea.Swarm.exe`) with these options:

- `-filename <path>` - Path to .terrain file
- `-verbose` - Enable detailed logging
- `-ignorecache` - Force full rebuild
- `-seed <int>` - Set random seed
- `-v key=value` - Pass variables

### Variable Passing

You can control terrain generation by passing variables:

```python
"variables": {
    "mountain_height": 1.5,
    "erosion_iterations": 30,
    "snow_coverage": 0.7
}
```

These map to variable nodes in your Gaea2 workflow.

### Parsing Output

With verbose mode enabled, the server parses:
- Nodes being processed
- Errors and warnings
- Timing information
- Export locations

## Troubleshooting

### "Gaea2 executable not found"
- Verify GAEA2_PATH is set correctly
- Check that Gaea.Swarm.exe exists at that location
- Try using the full path including the .exe extension

### "Server must run on host system"
- Don't try to run this in Docker/container
- Run directly on Windows where Gaea2 is installed

### "Python not found"
- Install Python 3.8+ from python.org
- Make sure to check "Add Python to PATH" during installation

### Connection refused
- Check if server is running on port 8007
- Try `netstat -an | findstr 8007` to verify
- Check Windows Firewall settings

## Architecture Notes

The Gaea2 MCP Server:
- Runs as a standalone HTTP server (port 8007)
- Does NOT run in containers
- Requires direct access to Gaea2 executable
- Maintains execution history in memory
- Uses async Python for performance

This follows the same pattern as the Gemini MCP server, which also must run on the host for Docker access.
