# MCP Tools Documentation

This document provides detailed information about the containerized MCP (Model Context Protocol) tools in this project.

## Container-First Design

Most MCP tools run in Docker containers as part of this project's philosophy:

- **Zero local dependencies** - just Docker
- **Consistent execution** - same results on any Linux system with Python 3.11
- **Easy deployment** - works identically on self-hosted runners
- **Single maintainer friendly** - no complex setup or coordination needed
- **User permission handling** - containers run as current user to avoid permission issues

**Exception**: The Gemini MCP server runs on the host system due to Docker-in-Docker limitations.

## Table of Contents

- [Overview](#overview)
- [Core Tools](#core-tools)
- [AI Integration Tools](#ai-integration-tools)
- [Content Creation Tools](#content-creation-tools)
- [Remote Services](#remote-services)
- [Custom Tool Development](#custom-tool-development)

## Overview

MCP tools are functions that can be executed through the MCP servers to perform various development and content creation tasks. They are accessible via HTTP API or through the MCP protocol.

**Server Architecture:**

The MCP functionality is distributed across specialized servers:

1. **Code Quality MCP Server** - Formatting and linting tools (STDIO mode)
2. **Content Creation MCP Server** - Manim and LaTeX tools (STDIO mode)
3. **Gemini MCP Server** - AI consultation (STDIO mode, host-only)
4. **Gaea2 MCP Server** (Port 8007) - Terrain generation
5. **Blender MCP Server** (Port 8017) - 3D content creation and rendering
6. **AI Toolkit MCP Server** (Port 8012) - LoRA training bridge
7. **ComfyUI MCP Server** (Port 8013) - Image generation bridge
8. **OpenCode MCP Server** - AI code generation (STDIO mode)
9. **Crush MCP Server** - Fast code generation (STDIO mode)
10. **Meme Generator MCP Server** - Meme creation (STDIO mode)

See [MCP Servers Documentation](servers.md) for detailed information.

### Tool Execution

MCP servers provide two different interfaces for tool execution:

#### 1. MCP Protocol Interface (`/messages` endpoint)
Used by Claude Desktop and MCP-compliant clients for JSON-RPC communication. This is the endpoint configured in `.mcp.json`:

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "http://localhost:<port>/messages"
    }
  }
}
```

**Example JSON-RPC request to `/messages`:**
```bash
curl -X POST http://localhost:<port>/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "tool_name",
      "arguments": {
        "arg1": "value1",
        "arg2": "value2"
      }
    },
    "id": 1
  }'
```

#### 2. Direct HTTP API (`/mcp/execute` endpoint)
For direct REST API tool execution without MCP protocol overhead. Useful for testing and direct integration:

**Example direct API request:**
```bash
curl -X POST http://localhost:<port>/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "tool_name",
    "arguments": {
      "arg1": "value1",
      "arg2": "value2"
    }
  }'
```

**STDIO Mode:**
Servers running in STDIO mode communicate through standard input/output using the MCP protocol and don't expose HTTP endpoints.

### Quick Reference Table

| Server Name | Primary Mode | HTTP Port (Dev) | Description |
|-------------|--------------|-----------------|-------------|
| Code Quality | STDIO (Docker) | 8010 | Code formatting and linting |
| Content Creation | STDIO (Docker) | 8011 | Manim animations and LaTeX |
| Gemini | STDIO (Host) | 8006 | AI consultation (must run on host) |
| Gaea2 | HTTP (Bridge) | 8007 | Terrain generation (remote server) |
| Blender | HTTP (Docker) | 8017 | 3D content creation, rendering, physics |
| AI Toolkit | HTTP (Bridge) | 8012 | LoRA training (remote server) |
| ComfyUI | HTTP (Bridge) | 8013 | Image generation (remote server) |
| OpenCode | STDIO (Docker) | 8014 | AI code generation |
| Crush | STDIO (Docker) | 8015 | Fast code generation |
| Meme Generator | STDIO (Docker) | N/A | Meme creation with visual feedback |

**Note**: The default configuration uses STDIO mode for local servers through Docker Compose. HTTP ports are only used when manually running servers in HTTP mode for development/testing.

## Core Tools

### Code Quality Tools

#### format_check

Check code formatting according to language-specific standards.

**Parameters:**
- `path` (string, required): Path to the file or directory to check
- `language` (string): Programming language (python, javascript, typescript, go, rust)

**Example:**
```json
{
  "tool": "format_check",
  "arguments": {
    "path": "./src",
    "language": "python"
  }
}
```

**Response:**
```json
{
  "success": true,
  "formatted": true,
  "output": "All files formatted correctly",
  "command": "black --check ./src"
}
```

#### lint

Run static code analysis to find potential issues.

**Parameters:**
- `path` (string, required): Path to analyze
- `linter` (string): Linter to use (flake8, pylint, eslint, golint, clippy)
- `config` (string, optional): Path to linting configuration file

**Example:**
```json
{
  "tool": "lint",
  "arguments": {
    "path": "./src",
    "linter": "flake8",
    "config": ".flake8"
  }
}
```

**Response:**
```json
{
  "success": true,
  "passed": false,
  "issues": [
    "src/main.py:10:1: E302 expected 2 blank lines, found 1"
  ],
  "issue_count": 1,
  "command": "flake8 --config .flake8 ./src"
}
```

#### autoformat

Automatically format code files.

**Parameters:**
- `path` (string, required): Path to format
- `language` (string): Programming language

**Example:**
```json
{
  "tool": "autoformat",
  "arguments": {
    "path": "./src",
    "language": "python"
  }
}
```

### Running CI/CD Pipeline

While not a direct MCP tool, the full CI/CD pipeline can be executed via:

```bash
# Run complete CI pipeline
./automation/ci-cd/run-ci.sh full

# Individual stages
./automation/ci-cd/run-ci.sh format
./automation/ci-cd/run-ci.sh lint-basic
./automation/ci-cd/run-ci.sh lint-full
./automation/ci-cd/run-ci.sh security
./automation/ci-cd/run-ci.sh test
```

These scripts leverage the containerized Python CI environment.

## AI Integration Tools

### Gemini Tools

#### consult_gemini

Get AI assistance from Google's Gemini model for technical questions, code review, and suggestions.

**Parameters:**
- `query` (string, required): The question or code to consult about
- `context` (string, optional): Additional context
- `comparison_mode` (boolean): Compare with previous Claude response
- `force` (boolean): Force consultation even if disabled

**Example:**
```json
{
  "tool": "consult_gemini",
  "arguments": {
    "query": "How can I optimize this function?",
    "context": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
    "comparison_mode": true
  }
}
```

#### clear_gemini_history

Clear Gemini's conversation history.

#### gemini_status

Get integration status and statistics.

#### toggle_gemini_auto_consult

Toggle automatic consultation on uncertainty detection.

### OpenCode Tools

#### consult_opencode

AI-powered code generation using Qwen 2.5 Coder.

**Parameters:**
- `query` (string, required): The coding question or task
- `mode` (string): generate, refactor, review, or explain
- `context` (string, optional): Existing code or context
- `comparison_mode` (boolean): Compare with previous response

**Example:**
```json
{
  "tool": "consult_opencode",
  "arguments": {
    "query": "Create a REST API endpoint for user authentication",
    "mode": "generate",
    "context": "Using FastAPI and JWT"
  }
}
```

### Crush Tools

#### consult_crush

Fast code generation optimized for speed.

**Parameters:**
- `query` (string, required): The coding question or task
- `mode` (string): generate, explain, convert, or quick
- `context` (string, optional): Target language for conversion
- `comparison_mode` (boolean): Compare with previous response

**Example:**
```json
{
  "tool": "consult_crush",
  "arguments": {
    "query": "def add(a, b): return a + b",
    "mode": "convert",
    "context": "TypeScript"
  }
}
```

## Content Creation Tools

### Content Creation Tools

#### create_manim_animation

Create mathematical and technical animations using Manim.

**Parameters:**
- `script` (string, required): Manim Python script
- `output_format` (string): Output format (mp4, gif, png, webm)
- `quality` (string): Rendering quality (low, medium, high, fourk)
- `preview` (boolean): Generate preview frame only

**Example:**
```json
{
  "tool": "create_manim_animation",
  "arguments": {
    "script": "from manim import *\n\nclass Example(Scene):\n    def construct(self):\n        text = Text('Hello!')\n        self.play(Write(text))",
    "output_format": "mp4",
    "quality": "medium",
    "preview": false
  }
}
```

#### compile_latex

Compile LaTeX documents with visual feedback.

**Parameters:**
- `content` (string, required): LaTeX document content
- `format` (string): Output format (pdf, dvi, ps)
- `template` (string): Document template (article, report, book, beamer, custom)
- `visual_feedback` (boolean): Return PNG preview image

**Example:**
```json
{
  "tool": "compile_latex",
  "arguments": {
    "content": "\\section{Introduction}\\nContent here",
    "format": "pdf",
    "template": "article",
    "visual_feedback": true
  }
}
```

#### render_tikz

Render TikZ diagrams as standalone images.

**Parameters:**
- `tikz_code` (string, required): TikZ code
- `output_format` (string): Output format (pdf, png, svg)

### Meme Generator Tools

#### generate_meme

Generate memes from templates with text overlays.

**Parameters:**
- `template` (string, required): Template ID
- `texts` (object, required): Text for each area
- `font_size_override` (object, optional): Custom font sizes
- `auto_resize` (boolean): Auto-adjust font size
- `upload` (boolean): Upload to get shareable URL

**Example:**
```json
{
  "tool": "generate_meme",
  "arguments": {
    "template": "drake",
    "texts": {
      "reject": "Writing documentation",
      "prefer": "Generated docs"
    },
    "upload": true
  }
}
```

## Remote Services

### Gaea2 Tools (Port 8007)

#### Terrain Generation
- `create_gaea2_project`: Create custom terrain projects
- `create_gaea2_from_template`: Use professional templates
- `validate_and_fix_workflow`: Validate and repair workflows
- `analyze_workflow_patterns`: Pattern-based analysis
- `optimize_gaea2_properties`: Optimize for performance/quality
- `suggest_gaea2_nodes`: Get intelligent node suggestions
- `repair_gaea2_project`: Repair damaged projects
- `run_gaea2_project`: CLI automation (Windows only)

**Features:**
- Professional templates
- Automatic error correction
- Performance optimization

### Blender Tools (Port 8017)

#### 3D Content Creation
- `create_blender_project`: Create new projects from templates
- `add_primitive_objects`: Add cubes, spheres, cylinders, etc.
- `setup_lighting`: Professional lighting setups (three-point, studio, HDRI)
- `apply_material`: Apply PBR materials and textures
- `import_model`: Import 3D models (FBX, OBJ, GLTF, STL, USD)
- `export_model`: Export to various formats

#### Rendering
- `render_frame`: Single frame rendering (Cycles/Eevee)
- `render_animation`: Animation sequence rendering
- `get_render_status`: Monitor rendering progress
- `cancel_render`: Stop ongoing render jobs

#### Physics & Simulation
- `setup_physics_simulation`: Configure rigid body, soft body, cloth
- `add_fluid_simulation`: Fluid dynamics setup
- `add_particle_system`: Particle effects and systems
- `run_simulation`: Execute physics simulation

#### Animation
- `create_keyframe_animation`: Keyframe-based animation
- `setup_armature`: Rigging and bone systems
- `add_animation_constraint`: Animation constraints
- `create_shape_keys`: Deformation shape keys

#### Geometry Nodes
- `create_geometry_nodes`: Procedural geometry generation
- `create_scatter_system`: Object scattering/distribution
- `create_array_modifier`: Array and grid layouts

**Features:**
- GPU-accelerated rendering with NVIDIA CUDA
- Headless Blender for server operations
- Asynchronous job system for long operations
- Professional templates (studio, animation, VFX, architectural)
- Full Docker support with GPU passthrough

### ComfyUI Tools (Port 8013)

#### Image Generation
- `generate_image`: Generate images using workflows
- `list_workflows`: List available workflows
- `get_workflow`: Get workflow details
- `list_models`: List available models
- `execute_workflow`: Execute custom workflows
- `transfer_lora`: Transfer LoRA from AI Toolkit

**Configuration:**
```bash
COMFYUI_SERVER_URL=http://192.168.0.152:8013
```

### AI Toolkit Tools (Port 8012)

#### LoRA Training
- `create_training_config`: Configure training
- `upload_dataset`: Upload images (chunked for >100MB)
- `start_training`: Begin training job
- `get_training_status`: Monitor progress
- `stop_training`: Stop training
- `export_model`: Export trained model
- `download_model`: Download model
- `list_configs`, `list_datasets`, `list_training_jobs`: List resources
- `get_system_stats`: System statistics
- `get_training_logs`: Training logs

**Configuration:**
```bash
AI_TOOLKIT_SERVER_URL=http://192.168.0.152:8012
```

## Custom Tool Development

### Creating a New MCP Server

1. **Create a new directory under `tools/mcp/`:**
```bash
mkdir tools/mcp/my_server
```

2. **Create server.py inheriting from BaseMCPServer:**
```python
# tools/mcp/my_server/server.py
from ..core.base_server import BaseMCPServer
from ..core.utils import setup_logging

class MyMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="My MCP Server",
            version="1.0.0",
            port=8020  # Choose an unused port
        )
        self.logger = setup_logging("MyMCP")

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "my_tool": {
                "description": "My custom tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "Parameter 1"
                        }
                    },
                    "required": ["param1"]
                }
            }
        }

    async def my_tool(self, param1: str) -> Dict[str, Any]:
        """Tool implementation"""
        return {
            "success": True,
            "result": f"Processed: {param1}"
        }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["http", "stdio"], default="http")
    args = parser.parse_args()

    server = MyMCPServer()
    server.run(mode=args.mode)

if __name__ == "__main__":
    main()
```

3. **Add to .mcp.json configuration:**
```json
{
  "mcpServers": {
    "my-server": {
      "type": "http",
      "url": "http://localhost:8020/messages"
    }
  }
}
```

4. **Create documentation:**
```bash
mkdir tools/mcp/my_server/docs
echo "# My MCP Server" > tools/mcp/my_server/docs/README.md
```

5. **Add test script:**
```python
# tools/mcp/my_server/scripts/test_server.py
import asyncio
import aiohttp

async def test_server():
    async with aiohttp.ClientSession() as session:
        # Test health endpoint
        async with session.get("http://localhost:8020/health") as resp:
            assert resp.status == 200

        # Test tool execution
        async with session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "my_tool",
                "arguments": {"param1": "test"}
            }
        ) as resp:
            result = await resp.json()
            assert result["success"] is True

if __name__ == "__main__":
    asyncio.run(test_server())
```

### Tool Guidelines

1. **Error Handling:**
   - Always return structured responses
   - Include error details in response
   - Use try-except blocks
   - Log errors for debugging

2. **Async Operations:**
   - Use `async/await` for I/O operations
   - Handle timeouts appropriately
   - Consider concurrent execution
   - Mock subprocess calls in tests

3. **Input Validation:**
   - Validate all parameters
   - Provide helpful error messages
   - Use type hints (Python 3.11 features)
   - Sanitize file paths

4. **Output Format:**
   - Return consistent structure
   - Include success status
   - Provide meaningful metadata
   - Use proper JSON serialization

### Testing Tools

```python
# tests/test_custom_tool.py
import pytest
from tools.mcp.custom_tools import my_custom_tool

@pytest.mark.asyncio
async def test_my_custom_tool():
    result = await my_custom_tool("test", 42)

    assert result["success"] is True
    assert result["result"] is not None
    assert result["metadata"]["param1"] == "test"
    assert result["metadata"]["param2"] == 42
```

## Best Practices

### Performance

1. **Caching:**
   - Cache expensive operations
   - Use Redis for distributed caching
   - Set appropriate TTL values

2. **Concurrency:**
   - Use asyncio for I/O-bound operations
   - Implement rate limiting
   - Handle concurrent requests properly

### Security

1. **Input Sanitization:**
   - Validate all user inputs
   - Escape special characters
   - Limit resource usage

2. **Authentication:**
   - Implement API key authentication
   - Use secure communication (HTTPS)
   - Log access attempts

### Monitoring

1. **Logging:**
   - Log all tool executions
   - Include timing information
   - Track error rates

2. **Metrics:**
   - Monitor tool usage
   - Track response times
   - Alert on failures

## Troubleshooting

### Common Issues

1. **Tool not found:**
   - Check tool registration in MCP server
   - Verify configuration file
   - Restart MCP server

2. **Timeout errors:**
   - Increase timeout in configuration
   - Optimize tool performance
   - Check network connectivity

3. **Permission errors:**
   - Verify file permissions
   - Check Docker volume mounts
   - Review security settings

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
docker-compose up mcp-server
```

View logs:

```bash
docker-compose logs -f mcp-server
```

## API Reference

### Endpoints

- `GET /` - Server information
- `GET /health` - Health check
- `GET /mcp/tools` - List available tools
- `POST /mcp/execute` - Execute a tool (direct API)
- `POST /messages` - MCP protocol endpoint (JSON-RPC)
- `GET /tools/{tool_name}` - Get tool details

### Response Format

```json
{
  "success": true,
  "result": {
    // Tool-specific results
  },
  "error": null,
  "metadata": {
    "tool": "tool_name",
    "execution_time": 1.23,
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

### Error Codes

- `400` - Bad Request (invalid parameters)
- `404` - Tool not found
- `500` - Internal server error
- `503` - Service unavailable
