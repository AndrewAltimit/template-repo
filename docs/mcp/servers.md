# MCP Servers Documentation

This project uses a modular architecture with multiple Model Context Protocol (MCP) servers, each specialized for specific functionality.

## Architecture Overview

The MCP functionality is split across modular servers:

**STDIO Mode (Default - local execution):**
1. **Code Quality MCP Server** - Containerized code formatting and linting tools
2. **Content Creation MCP Server** - Containerized Manim animations and LaTeX compilation
3. **Gemini MCP Server** - Host-only AI integration (requires Docker access)
4. **OpenCode MCP Server** - Containerized AI-powered code generation
5. **Crush MCP Server** - Containerized fast code generation
6. **Meme Generator MCP Server** - Containerized meme creation with visual feedback
7. **ElevenLabs Speech MCP Server** - Containerized text-to-speech synthesis

**HTTP Bridge Mode (Remote servers):**
8. **Gaea2 MCP Server** (Port 8007) - Bridge to remote terrain generation
9. **AI Toolkit MCP Server** (Port 8012) - Bridge to remote AI Toolkit for LoRA training
10. **ComfyUI MCP Server** (Port 8013) - Bridge to remote ComfyUI for image generation

This modular architecture ensures better separation of concerns, easier maintenance, and the ability to scale individual services independently.

## Code Quality MCP Server

The code quality server provides formatting and linting tools for multiple programming languages.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker-compose up -d mcp-code-quality

# Or run locally for development
python -m tools.mcp.code_quality.server

# View logs
docker-compose logs -f mcp-code-quality

# Test health
curl http://localhost:8010/health
```

### Available Tools

- **format_check** - Check code formatting for Python, JavaScript, TypeScript, Go, and Rust
- **lint** - Run static code analysis with configurable linting rules
- **autoformat** - Automatically format code files

### Configuration

See `tools/mcp/code_quality/docs/README.md` for detailed configuration options.

## Content Creation MCP Server

The content creation server provides tools for creating animations and compiling documents.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker-compose up -d mcp-content-creation

# Or run locally for development
python -m tools.mcp.content_creation.server

# View logs
docker-compose logs -f mcp-content-creation

# Test health
curl http://localhost:8011/health
```

### Available Tools

- **create_manim_animation** - Create mathematical and technical animations using Manim
- **compile_latex** - Compile LaTeX documents to PDF, DVI, or PostScript formats
- **render_tikz** - Render TikZ diagrams as standalone images

### Configuration

Output directory is configured via the `MCP_OUTPUT_DIR` environment variable (defaults to `/tmp/mcp-content-output` in container).

See `tools/mcp/content_creation/docs/README.md` for detailed documentation.

## Gemini MCP Server

The Gemini server provides AI assistance through the Gemini CLI. It **must run on the host system** because it requires Docker access.

### Starting the Server

```bash
# Must run on host system (not in container)
python -m tools.mcp.gemini.server

# Or use HTTP mode
python -m tools.mcp.gemini.server --mode http

# Or use the helper script
./tools/mcp/gemini/scripts/start_server.sh

# Test health
curl http://localhost:8006/health
```

### Available Tools

- **consult_gemini** - Get AI assistance for technical questions
- **clear_gemini_history** - Clear conversation history
- **gemini_status** - Get integration status
- **toggle_gemini_auto_consult** - Control auto-consultation

### Container Detection

The server includes automatic container detection and will exit with an error if run in a container:

```bash
# This will fail with a helpful error message
docker-compose run --rm python-ci python -m tools.mcp.gemini.server
```

See `tools/mcp/gemini/docs/README.md` for detailed documentation.

## Gaea2 MCP Server (Port 8007)

The Gaea2 server provides comprehensive terrain generation capabilities.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker-compose up -d mcp-gaea2

# Or run locally for development
python -m tools.mcp.gaea2.server

# For remote server deployment (e.g., on Windows with Gaea2 installed)
# Set GAEA2_REMOTE_URL environment variable to point to the remote server
export GAEA2_REMOTE_URL=http://remote-server:8007

# View logs
docker-compose logs -f mcp-gaea2

# Test health
curl http://localhost:8007/health
```

### Available Tools

#### Terrain Generation Tools
- **create_gaea2_project** - Create custom terrain projects with automatic validation
- **create_gaea2_from_template** - Use professional workflow templates
- **validate_and_fix_workflow** - Comprehensive validation and automatic repair
- **analyze_workflow_patterns** - Pattern-based analysis using real project knowledge
- **optimize_gaea2_properties** - Optimize for performance or quality
- **suggest_gaea2_nodes** - Get intelligent node suggestions
- **repair_gaea2_project** - Repair damaged project files

#### CLI Automation (when running on Windows with Gaea2)
- **run_gaea2_project** - Execute terrain generation via CLI
- **analyze_execution_history** - Learn from previous runs

### Configuration

- For containerized deployment: Works out of the box
- For Windows deployment with CLI features: Set `GAEA2_PATH` environment variable
- See `tools/mcp/gaea2/docs/README.md` for complete documentation

## AI Toolkit MCP Server (Port 8012)

The AI Toolkit server provides a bridge to remote AI Toolkit for LoRA training operations.

### Starting the Server

```bash
# Start via Docker Compose (if configured)
docker-compose up -d mcp-ai-toolkit

# Or run locally as bridge
python -m tools.mcp.ai_toolkit.server

# Test health
curl http://localhost:8012/health
```

### Available Tools

- **create_training_config** - Create new training configurations
- **upload_dataset** - Upload images for dataset creation (supports chunked upload for large files)
- **start_training** - Start LoRA training jobs
- **get_training_status** - Monitor training progress
- **export_model** - Export trained models
- **download_model** - Download trained models
- **list_configs**, **list_datasets**, **list_training_jobs**, **list_exported_models** - List resources
- **get_system_stats** - Get system statistics
- **get_training_logs** - Get training logs

### Configuration

- **Remote Bridge**: Connects to AI Toolkit at `192.168.0.152:8012`
- **Dataset Paths**: Use absolute paths starting with `/ai-toolkit/datasets/`
- **Chunked Upload**: Automatically used for files >100MB

See `tools/mcp/ai_toolkit/docs/README.md` and `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md` for detailed documentation.

## ComfyUI MCP Server (Port 8013)

The ComfyUI server provides a bridge to remote ComfyUI for AI image generation.

### Starting the Server

```bash
# Start via Docker Compose (if configured)
docker-compose up -d mcp-comfyui

# Or run locally as bridge
python -m tools.mcp.comfyui.server

# Test health
curl http://localhost:8013/health
```

### Available Tools

- **generate_image** - Generate images using ComfyUI workflows
- **list_workflows** - List available workflows
- **get_workflow** - Get specific workflow details
- **list_models** - List available models (checkpoints, LoRAs, etc.)
- **execute_workflow** - Execute custom workflows
- **transfer_lora** - Transfer LoRA models from AI Toolkit

### Configuration

- **Remote Bridge**: Connects to ComfyUI at `192.168.0.152:8013`
- **FLUX Support**: Different workflows for FLUX models (cfg=1.0, special nodes)
- **LoRA Transfer**: Automatic transfer from AI Toolkit to ComfyUI

See `tools/mcp/comfyui/docs/README.md` and `docs/integrations/creative-tools/lora-transfer.md` for detailed documentation.

## OpenCode MCP Server

The OpenCode server provides AI-powered code generation using OpenRouter API.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop)
python -m tools.mcp.opencode.server --mode stdio

# Or HTTP mode for remote access
python -m tools.mcp.opencode.server --mode http

# Or use the helper script
./tools/utilities/run_opencode.sh

# Test health (HTTP mode)
curl http://localhost:8014/health
```

### Available Tools

- **consult_opencode** - Generate, refactor, review, or explain code
  - Modes: `generate`, `refactor`, `review`, `explain`
  - Supports comparison with previous Claude responses
- **clear_opencode_history** - Clear conversation history
- **opencode_status** - Get integration status and statistics
- **toggle_opencode_auto_consult** - Control auto-consultation on uncertainty

### Configuration

- **Model**: Uses Qwen 2.5 Coder via OpenRouter
- **API Key**: Requires `OPENROUTER_API_KEY` environment variable
- **Modes**: Supports both STDIO (local) and HTTP (remote) modes

See `tools/mcp/opencode/README.md` and `docs/integrations/ai-services/opencode-crush.md` for detailed documentation.

## Crush MCP Server

The Crush server provides fast code generation using OpenRouter API with optimized models.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop)
python -m tools.mcp.crush.server --mode stdio

# Or HTTP mode for remote access
python -m tools.mcp.crush.server --mode http

# Or use the helper script
./tools/utilities/run_crush.sh

# Test health (HTTP mode)
curl http://localhost:8015/health
```

### Available Tools

- **consult_crush** - Quick code generation and conversion
  - Modes: `generate`, `explain`, `convert`, `quick`
  - Optimized for speed with smaller models
- **clear_crush_history** - Clear conversation history
- **crush_status** - Get integration status and statistics
- **toggle_crush_auto_consult** - Control auto-consultation

### Configuration

- **Model**: Uses optimized models via OpenRouter for speed
- **API Key**: Requires `OPENROUTER_API_KEY` environment variable
- **Modes**: Supports both STDIO (local) and HTTP (remote) modes

See `tools/mcp/crush/README.md` and `docs/integrations/ai-services/opencode-crush.md` for detailed documentation.

## Meme Generator MCP Server

The Meme Generator server creates memes from templates with customizable text overlays and visual feedback. It runs in STDIO mode through Docker Compose for local use.

### Starting the Server

```bash
# The server is configured in .mcp.json and runs automatically through Claude Desktop
# It uses docker-compose in STDIO mode

# For manual testing or development:
docker-compose run --rm -T mcp-meme-generator python -m tools.mcp.meme_generator.server --mode stdio

# View container logs
docker-compose logs -f mcp-meme-generator
```

### Available Tools

- **generate_meme** - Generate memes from templates with text overlays
  - Auto-resize text to fit areas
  - Visual feedback for AI verification
  - Automatic upload to 0x0.st for sharing
- **list_meme_templates** - List all available templates
- **get_meme_template_info** - Get detailed template information
- **test_minimal** - Minimal test tool
- **test_fake_meme** - Test without creating images

### Features

- **7+ Built-in Templates**: Including "Ol' Reliable", Drake, Distracted Boyfriend, etc.
- **Cultural Documentation**: Each template includes usage rules and context
- **Visual Feedback**: Base64-encoded preview for AI agents
- **Auto Upload**: Generates shareable URLs via 0x0.st
- **Text Auto-Resize**: Automatically adjusts font size to fit

See `tools/mcp/meme_generator/docs/README.md` and `tools/mcp/meme_generator/docs/MEME_USAGE_GUIDE.md` for detailed documentation.

## ElevenLabs Speech MCP Server

The ElevenLabs Speech server provides advanced text-to-speech synthesis with emotional control, audio tags, and sound effects.

### Starting the Server

```bash
# The server is configured in .mcp.json and runs automatically through Claude Desktop
# It uses STDIO mode for seamless integration

# For HTTP mode (testing/development):
docker-compose up -d mcp-elevenlabs-speech

# Or run locally
python -m tools.mcp.elevenlabs_speech.server --mode http

# View logs
docker-compose logs -f mcp-elevenlabs-speech

# Test health
curl http://localhost:8018/health
```

### Available Tools

- **synthesize_speech_v3** - Main synthesis with audio tag support
  - Supports emotions, pauses, sounds, effects
  - Model-aware processing (v2 vs v3)
  - Automatic upload to 0x0.st
- **synthesize_emotional** - Add emotional context with intensity control
- **synthesize_dialogue** - Multi-character dialogue generation
- **generate_sound_effect** - Create sound effects (up to 22 seconds)
- **synthesize_natural_speech** - Natural speech with hesitations and breathing
- **synthesize_emotional_progression** - Emotional transitions in narratives
- **optimize_text_for_synthesis** - Improve text quality for synthesis
- **list_available_voices** - List all available voices
- **parse_audio_tags** - Parse and validate audio tags
- **suggest_audio_tags** - Get tag suggestions for text

### Features

- **14+ Synthesis Tools**: Comprehensive speech generation capabilities
- **Multi-Model Support**: v2 (Pro plan) and v3 (future compatibility)
- **Audio Tag System**: Emotions, pauses, sounds, effects
- **Voice Library**: 10+ pre-configured voices
- **Local Caching**: Organized output structure
- **Auto Upload**: Shareable URLs via 0x0.st
- **Metadata Tracking**: Complete synthesis information in JSON

### Configuration

Add to `.env`:
```bash
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_DEFAULT_MODEL=eleven_multilingual_v2
ELEVENLABS_DEFAULT_VOICE=Rachel
```

See `tools/mcp/elevenlabs_speech/docs/README.md` for detailed documentation.

## Unified Testing

Test all servers at once:

```bash
# Test all running servers
python automation/testing/test_all_servers.py

# Quick connectivity test only
python automation/testing/test_all_servers.py --quick

# Test individual servers
python tools/mcp/code_quality/scripts/test_server.py
python tools/mcp/content_creation/scripts/test_server.py
python tools/mcp/gaea2/scripts/test_server.py
python tools/mcp/gemini/scripts/test_server.py
```

## Configuration

The modular servers are configured in `.mcp.json`:

```json
{
  "mcpServers": {
    "code-quality": {
      "type": "http",
      "url": "http://localhost:8010/messages"
    },
    "content-creation": {
      "type": "http",
      "url": "http://localhost:8011/messages"
    },
    "gemini": {
      "type": "http",
      "url": "http://localhost:8006/messages"
    },
    "gaea2": {
      "type": "http",
      "url": "${GAEA2_REMOTE_URL:-http://localhost:8007}/messages"
    },
    "ai-toolkit": {
      "type": "http",
      "url": "http://localhost:8012/messages"
    },
    "comfyui": {
      "type": "http",
      "url": "http://localhost:8013/messages"
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
      "command": "docker-compose",
      "args": [
        "-f", "./docker-compose.yml", "--profile", "services",
        "run", "--rm", "-T", "mcp-meme-generator",
        "python", "-m", "tools.mcp.meme_generator.server",
        "--mode", "stdio"
      ]
    }
  }
}
```

**Important Notes**:
1. Most servers in the actual `.mcp.json` configuration use **STDIO mode through Docker Compose**, not HTTP mode. The configuration above shows a simplified example.
2. The actual `.mcp.json` uses `docker-compose run` commands to start servers in STDIO mode within containers.
3. Remote servers (Gaea2, AI Toolkit, ComfyUI) use HTTP mode with the `/messages` endpoint.
4. The `/messages` endpoint is for MCP protocol (JSON-RPC) communication. For direct HTTP API tool execution during development, use the `/mcp/execute` endpoint instead.

See the actual `.mcp.json` file for the precise configuration used by Claude Desktop.

## Client Usage

Use the MCPClient from `tools.mcp.core` to interact with MCP servers:

```python
from tools.mcp.core import MCPClient

# Target a specific server by name
client = MCPClient(server_name="gaea2")

# Or use a server URL directly
client = MCPClient(base_url="http://localhost:8007")

# Execute tools
result = client.execute_tool("tool_name", {"arg": "value"})
```

For complete examples, see the test scripts in `tools/mcp/*/scripts/test_server.py`

## Troubleshooting

### Port Already in Use

```bash
# Find process using a port (e.g., 8010)
sudo lsof -i :8010

# Stop specific container
docker-compose down mcp-code-quality
```

### Container Permission Issues

```bash
./automation/setup/runner/fix-runner-permissions.sh
```

### Gemini Server Issues

1. **"Cannot run in container" error** - Run on host system
2. **Gemini CLI not found** - Install with `npm install -g @google/gemini-cli`

### Gaea2 Windows CLI Features

1. **Set GAEA2_PATH** environment variable to Gaea.Swarm.exe location
2. **Ensure Windows host** for CLI automation features

## Development Notes

- Each server extends `BaseMCPServer` from `tools/mcp/core/`
- Servers can run standalone or via Docker Compose
- All servers provide consistent JSON API responses
- Use the modular architecture to add new specialized servers
- Follow the container-first philosophy except where technically impossible (Gemini)
