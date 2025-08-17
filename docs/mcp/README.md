# MCP (Model Context Protocol) Servers

This repository contains a modular collection of MCP servers that provide various development and content creation tools. Each server is specialized for specific functionality and can be run independently.

## Available MCP Servers

### Local Process Servers (STDIO Transport)

These servers run as local processes on the same machine as the client:

#### 1. Code Quality MCP Server
**Location**: `tools/mcp/code_quality/`
**Transport**: STDIO (local process)
**Documentation**: [Code Quality MCP Documentation](../../tools/mcp/code_quality/docs/README.md)

Provides code formatting and linting tools for multiple languages:
- Format checking (Python, JavaScript, TypeScript, Go, Rust)
- Linting with various tools (flake8, pylint, eslint, etc.)
- Auto-formatting capabilities

#### 2. Content Creation MCP Server
**Location**: `tools/mcp/content_creation/`
**Transport**: STDIO (local process)
**Documentation**: [Content Creation MCP Documentation](../../tools/mcp/content_creation/docs/README.md)

Tools for creating mathematical animations and documents:
- Manim animations (mathematical visualizations)
- LaTeX document compilation (PDF, DVI, PS) with visual feedback
- TikZ diagram rendering
- Preview generation and compression

#### 3. Gemini AI Integration MCP Server
**Location**: `tools/mcp/gemini/`
**Transport**: STDIO (local process, host-only)
**Documentation**: [Gemini MCP Documentation](../../tools/mcp/gemini/docs/README.md)

AI integration for second opinions and code validation:
- Gemini AI consultations with comparison mode
- Conversation history management
- Auto-consultation on uncertainty detection
- Integration status and statistics

**⚠️ Important**: Must run on host system (not in container) due to Docker access requirements

#### 4. OpenCode MCP Server
**Location**: `tools/mcp/opencode/`
**Transport**: STDIO (local) or HTTP (remote)
**Documentation**: [OpenCode MCP Documentation](../../tools/mcp/opencode/README.md)

AI-powered code generation using OpenRouter:
- Code generation, refactoring, and review
- Code explanation and documentation
- Conversation history management
- Auto-consultation features
- Uses Qwen 2.5 Coder model

#### 5. Crush MCP Server
**Location**: `tools/mcp/crush/`
**Transport**: STDIO (local) or HTTP (remote)
**Documentation**: [Crush MCP Documentation](../../tools/mcp/crush/README.md)

Fast code generation using OpenRouter:
- Quick code generation and conversion
- Optimized for speed with smaller models
- Conversation history management
- Auto-consultation features

#### 6. Meme Generator MCP Server
**Location**: `tools/mcp/meme_generator/`
**Transport**: STDIO (local process)
**Documentation**: [Meme Generator MCP Documentation](../../tools/mcp/meme_generator/docs/README.md)

Generate memes with customizable text overlays:
- Template-based meme generation
- Auto-resize text to fit areas
- Visual feedback for AI verification
- Automatic upload for sharing (0x0.st)
- Cultural context documentation
- 7+ built-in templates with more being added

#### 7. ElevenLabs Speech MCP Server
**Location**: `tools/mcp/elevenlabs_speech/`
**Transport**: STDIO (local) or HTTP (Port 8018)
**Documentation**: [ElevenLabs MCP Documentation](../../tools/mcp/elevenlabs_speech/docs/README.md)

Advanced text-to-speech synthesis with emotional control:
- 14+ specialized synthesis tools
- Multi-model support (v2 Pro plan, v3 future)
- Audio tag support (emotions, pauses, sounds, effects)
- Natural speech with hesitations and breathing
- Emotional progression across narratives
- Sound effect generation (up to 22 seconds)
- Voice library with 10+ pre-configured voices
- Automatic upload for sharing (0x0.st)

### Remote/Cross-Machine Servers (HTTP Transport)

These servers use HTTP transport for remote machines or special hardware/software requirements:

#### 1. Gaea2 Terrain Generation MCP Server
**Location**: `tools/mcp/gaea2/`
**Transport**: HTTP (Port 8007)
**Remote Location**: Can run at `192.168.0.152:8007`
**Documentation**: [Gaea2 MCP Documentation](../../tools/mcp/gaea2/docs/README.md) | [Full Documentation Index](../../tools/mcp/gaea2/docs/INDEX.md)

Comprehensive terrain generation with Gaea2:
- Intelligent validation and error correction
- Professional terrain templates (11 templates)
- CLI automation (Windows only)
- Project repair and optimization capabilities
- Pattern-based workflow analysis

**Why HTTP**: Requires Windows OS with Gaea2 software installed

#### 2. AI Toolkit MCP Server
**Location**: `tools/mcp/ai_toolkit/`
**Transport**: HTTP (Port 8012)
**Remote Location**: `192.168.0.152:8012`
**Documentation**: [AI Toolkit MCP Documentation](../../tools/mcp/ai_toolkit/README.md)

GPU-accelerated LoRA training management:
- Training configuration management
- Dataset upload with chunked support
- Training job monitoring and control
- Model export and download
- System statistics and logs

**Why HTTP**: Requires NVIDIA GPU and specific ML environment

#### 3. ComfyUI MCP Server
**Location**: `tools/mcp/comfyui/`
**Transport**: HTTP (Port 8013)
**Remote Location**: `192.168.0.152:8013`
**Documentation**: [ComfyUI MCP Documentation](../../tools/mcp/comfyui/README.md)

GPU-accelerated AI image generation:
- Image generation with workflows
- LoRA model management and transfer
- Custom workflow execution
- Model listing and management

**Why HTTP**: Requires NVIDIA GPU and ComfyUI installation

## Configuration and Transport

### Transport Mode Selection

**STDIO Transport**: Used for local processes running on the same machine as the client
- Configured in `.mcp.json` with `command` and `args`
- Client spawns server as child process
- Communication via standard input/output

**HTTP Transport**: Used for remote machines or special environment requirements
- Configured in `.mcp.json` with `type: "http"` and `url`
- Server runs independently as network service
- Communication via HTTP protocol

For detailed configuration and troubleshooting:
- **[MCP Server Modes: STDIO vs HTTP](architecture/stdio-vs-http.md)** - Complete guide for transport modes
- **[MCP Specification](https://modelcontextprotocol.io/specification/2025-06-18)** - Official protocol specification

### Configuration File (.mcp.json)

All MCP servers are configured in the `.mcp.json` file at the project root.

**STDIO servers** (local processes):
```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["-m", "tools.mcp.server_name.server"]
    }
  }
}
```

**HTTP servers** (remote/cross-machine):

```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "http://host:port/messages"
    }
  }
}
```

## Architecture Overview

```
tools/mcp/
├── core/                    # Shared utilities and base classes
│   ├── base_server.py      # Base MCP server class
│   ├── http_bridge.py      # HTTP bridge for remote servers
│   ├── client_registry.py  # Client registry management
│   └── utils.py            # Common utilities
│
# Local Process Servers (STDIO)
├── code_quality/           # Code quality tools (local)
├── content_creation/       # Manim & LaTeX tools (local)
├── gemini/                 # AI integration (local, host-only)
├── opencode/               # AI code generation (local/remote capable)
├── crush/                  # Fast code generation (local/remote capable)
├── meme_generator/         # Meme generation (local)
│
# Remote/Cross-Machine Servers (HTTP)
├── gaea2/                  # Terrain generation (Windows requirement)
├── ai_toolkit/             # LoRA training (GPU requirement)
└── comfyui/                # Image generation (GPU requirement)
```

## Running MCP Servers

### Local Process Servers (STDIO)
Claude Code automatically starts these servers when you use their tools. No manual startup required:
```python
# Just use the tool - Claude handles the rest
result = mcp__code_quality__format_check(path="./src")
```

### Remote/Cross-Machine Servers (HTTP)
These servers must be started independently on their host machines:
```bash
# Start on remote machine
python -m tools.mcp.gaea2.server --mode http       # Windows machine with Gaea2
python -m tools.mcp.ai_toolkit.server --mode http  # GPU machine
python -m tools.mcp.comfyui.server --mode http     # GPU machine
```

### Dual-Mode Servers
Some servers support both STDIO (local) and HTTP (remote) modes:
For Claude Desktop integration:
```bash
python -m tools.mcp.<server_name>.server --mode stdio
```

## Claude Desktop Configuration

Add the desired servers to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "code-quality": {
      "command": "python",
      "args": ["-m", "tools.mcp.code_quality.server", "--mode", "stdio"]
    },
    "content-creation": {
      "command": "python",
      "args": ["-m", "tools.mcp.content_creation.server", "--mode", "stdio"]
    },
    "gemini": {
      "command": "python",
      "args": ["-m", "tools.mcp.gemini.server", "--mode", "stdio"]
    },
    "gaea2": {
      "command": "python",
      "args": ["-m", "tools.mcp.gaea2.server", "--mode", "stdio"]
    },
    "opencode": {
      "command": "python",
      "args": ["-m", "tools.mcp.opencode.server", "--mode", "stdio"]
    },
    "crush": {
      "command": "python",
      "args": ["-m", "tools.mcp.crush.server", "--mode", "stdio"]
    },
    "meme-generator": {
      "command": "python",
      "args": ["-m", "tools.mcp.meme_generator.server", "--mode", "stdio"]
    }
  }
}
```

**Note**: AI Toolkit and ComfyUI servers are bridges to remote services and typically run in HTTP mode.

## Docker Support

Most servers can run in Docker containers. Example compose configuration:

```yaml
version: '3.8'

services:
  mcp-code-quality:
    build:
      context: .
      dockerfile: docker/mcp-code-quality.Dockerfile
    ports:
      - "8010:8010"
    volumes:
      - ./output:/app/output

  mcp-content-creation:
    build:
      context: .
      dockerfile: docker/mcp-content.Dockerfile
    ports:
      - "8011:8011"
    volumes:
      - ./output:/app/output

  mcp-gaea2:
    build:
      context: .
      dockerfile: docker/mcp-gaea2.Dockerfile
    ports:
      - "8007:8007"
    environment:
      - GAEA2_REMOTE_URL=${GAEA2_REMOTE_URL:-http://localhost:8007}

  mcp-meme-generator:
    build:
      context: .
      dockerfile: docker/mcp-meme.Dockerfile
    volumes:
      - ./output:/app/output
    # Runs in STDIO mode - no ports exposed

  # OpenRouter-based agents container
  openrouter-agents:
    build:
      context: .
      dockerfile: docker/openrouter-agents.Dockerfile
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

  # Note: Gemini must run on host (Docker access required)
  # Note: Gaea2 CLI features require Windows host
  # Note: AI Toolkit and ComfyUI are bridges to remote services
```

## Development

### Creating a New MCP Server

1. Create a new directory under `tools/mcp/`
2. Inherit from `BaseMCPServer` in `core/base_server.py`
3. Implement the `get_tools()` method
4. Add tool implementation methods
5. Create documentation in `docs/README.md`
6. Add tests in `scripts/test_server.py`

### Testing

Each server includes test scripts:
```bash
python tools/mcp/<server_name>/scripts/test_server.py
```

Test all servers:
```bash
python automation/testing/test_all_servers.py
```


## Common Issues

### Server Modes and Ports

**STDIO Mode (Default - no ports exposed):**
- Code Quality (via Docker Compose)
- Content Creation (via Docker Compose)
- Gemini (host-only, requires Docker access)
- OpenCode (via Docker Compose)
- Crush (via Docker Compose)
- Meme Generator (via Docker Compose)

**HTTP Bridge Mode (Remote servers):**
- Gaea2: 8007 (remote at 192.168.0.152)
- AI Toolkit: 8012 (remote at 192.168.0.152)
- ComfyUI: 8013 (remote at 192.168.0.152)

**Development Ports (when running servers in HTTP mode):**
- Code Quality: 8010
- Content Creation: 8011
- Gemini: 8006
- OpenCode: 8014
- Crush: 8015

### Container Restrictions
- **Gemini**: Cannot run in container (needs Docker access)
- **Gaea2 CLI**: Requires Windows host with Gaea2 installed
- **AI Toolkit/ComfyUI**: Bridges to remote services, require network access
- **OpenCode/Crush**: Can run in STDIO mode locally or HTTP mode in containers

### Missing Dependencies
Each server has specific requirements. Check the server's documentation for installation instructions.

## Contributing

When contributing to MCP servers:

1. Follow the modular structure
2. Add comprehensive documentation
3. Include test scripts
4. Update this overview if adding new servers
5. Ensure backward compatibility when possible

## License

See repository LICENSE file.
