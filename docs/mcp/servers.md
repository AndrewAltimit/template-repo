# MCP Servers Documentation

This project uses a modular architecture with multiple Model Context Protocol (MCP) servers, each specialized for specific functionality.

## Architecture Overview

The MCP functionality is split across modular servers:

**STDIO Mode (Default - local execution):**
1. **Code Quality MCP Server** - Containerized code formatting and linting tools
2. **Content Creation MCP Server** - Containerized Manim animations and LaTeX compilation
3. **Gemini MCP Server** - Host-only AI integration (requires Docker access)
4. **Codex MCP Server** - Containerized AI-powered code generation and completion
5. **OpenCode MCP Server** - Containerized AI-powered code generation
6. **Crush MCP Server** - Containerized code generation
7. **Meme Generator MCP Server** - Containerized meme creation with visual feedback
8. **ElevenLabs Speech MCP Server** - Containerized text-to-speech synthesis
9. **Video Editor MCP Server** - Containerized AI-powered video editing
10. **Blender MCP Server** - Containerized 3D content creation and rendering
11. **Virtual Character MCP Server** - Containerized AI agent embodiment middleware
12. **Desktop Control MCP Server** - Cross-platform desktop automation (Linux/Windows)
13. **GitHub Board MCP Server** - GitHub Projects v2 board management and agent coordination
14. **AgentCore Memory MCP Server** - Multi-provider AI memory (AWS AgentCore or ChromaDB)
15. **Reaction Search MCP Server** - Semantic search for anime reaction images
16. **Memory Explorer MCP Server** - Process memory exploration for agent integration with legacy software (native binary)

**HTTP Mode (Remote servers):**
17. **Gaea2 MCP Server** (Port 8007) - Remote terrain generation interface
18. **AI Toolkit MCP Server** (Port 8012) - Remote AI Toolkit for LoRA training
19. **ComfyUI MCP Server** (Port 8013) - Remote ComfyUI for image generation

This modular architecture ensures better separation of concerns, easier maintenance, and the ability to scale individual services independently.

## Code Quality MCP Server

The code quality server provides formatting and linting tools for multiple programming languages.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker compose up -d mcp-code-quality

# Or run locally for development
python -m tools.mcp.code_quality.server

# View logs
docker compose logs -f mcp-code-quality

# Test health
curl http://localhost:8010/health
```

### Available Tools

- **format_check** - Check code formatting for Python, JavaScript, TypeScript, Go, and Rust
- **lint** - Run static code analysis with configurable linting rules
- **autoformat** - Automatically format code files

### Configuration

See `tools/mcp/mcp_code_quality/docs/README.md` for detailed configuration options.

## Content Creation MCP Server

The content creation server provides tools for creating animations and compiling documents.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker compose up -d mcp-content-creation

# Or run locally for development
python -m tools.mcp.content_creation.server

# View logs
docker compose logs -f mcp-content-creation

# Test health
curl http://localhost:8011/health
```

### Available Tools

- **create_manim_animation** - Create mathematical and technical animations using Manim
- **compile_latex** - Compile LaTeX documents to PDF, DVI, or PostScript formats
- **render_tikz** - Render TikZ diagrams as standalone images

### Configuration

Output directory is configured via the `MCP_OUTPUT_DIR` environment variable (defaults to `/tmp/mcp-content-output` in container).

See `tools/mcp/mcp_content_creation/docs/README.md` for detailed documentation.

## Gemini MCP Server (Rust)

The Gemini server provides AI assistance through the Gemini CLI. This server has been migrated to Rust for improved performance and lower resource usage.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop) - Recommended
mcp-gemini --mode stdio

# Or standalone HTTP mode for remote access
mcp-gemini --mode standalone --port 8006

# Or use Docker container
docker compose run --rm mcp-gemini mcp-gemini --mode stdio

# Test health (HTTP mode)
curl http://localhost:8006/health
```

### Building from Source

```bash
cd tools/mcp/mcp_gemini
cargo build --release
# Binary at target/release/mcp-gemini
```

### Available Tools

- **consult_gemini** - Get AI assistance for technical questions
- **clear_gemini_history** - Clear conversation history
- **gemini_status** - Get integration status
- **toggle_gemini_auto_consult** - Control auto-consultation

### Configuration

Environment variables:
- `GEMINI_ENABLED` - Enable/disable integration (default: true)
- `GEMINI_AUTO_CONSULT` - Enable auto-consultation (default: true)
- `GEMINI_TIMEOUT` - Timeout in seconds (default: 60)
- `GEMINI_MAX_CONTEXT` - Maximum context length (default: 4000)
- `GEMINI_AUTH_PATH` - Path to auth directory (default: ~/.gemini)
- `GEMINI_YOLO_MODE` - Enable auto-approval mode (default: false)

See `tools/mcp/mcp_gemini/README.md` for detailed documentation.

## Blender MCP Server

The Blender server provides comprehensive 3D content creation and rendering capabilities.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker compose up -d mcp-blender

# Or run locally for development
python -m tools.mcp.blender.server

# View logs
docker compose logs -f mcp-blender

# Test health
curl http://localhost:8016/health
```

### Available Tools

- **create_blender_project** - Create new Blender projects from templates
- **add_primitive_objects** - Add basic 3D shapes to scenes
- **setup_lighting** - Configure scene lighting (three-point, HDRI, etc.)
- **apply_material** - Apply materials to objects
- **render_image** - Render single frames
- **render_animation** - Render animation sequences
- **setup_physics** - Add physics simulations (rigid body, cloth, fluid)
- **create_animation** - Create keyframe animations
- **setup_camera** - Configure camera settings
- **add_modifier** - Add modifiers to objects
- **setup_compositor** - Configure post-processing

See `tools/mcp/mcp_blender/docs/README.md` for detailed documentation.

## Virtual Character MCP Server (Rust)

The Virtual Character server provides AI agent embodiment in virtual worlds through a backend adapter architecture. This server has been migrated to Rust for improved performance and lower resource usage.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop) - Recommended
mcp-virtual-character --mode stdio

# Or standalone HTTP mode for remote access
mcp-virtual-character --mode standalone --port 8025

# Or use Docker container
docker compose run --rm mcp-virtual-character mcp-virtual-character --mode stdio

# Test health (HTTP mode)
curl http://localhost:8025/health
```

### Building from Source

```bash
cd tools/mcp/mcp_virtual_character
cargo build --release
# Binary at target/release/mcp-virtual-character
```

### Available Tools

- **set_backend** - Connect to a backend (mock, vrchat_remote)
- **send_animation** - Send animation data (emotion, gesture, blendshapes)
- **send_vrcemote** - Send VRCEmote value (0-8) for gesture wheel positions
- **execute_behavior** - Execute platform-specific behaviors
- **reset** - Reset to neutral state
- **get_backend_status** - Get current backend status and statistics
- **list_backends** - List available backend adapters
- **play_audio** - Play audio with ElevenLabs expression detection
- **create_sequence** - Create event sequences for choreography
- **add_sequence_event** - Add events to sequences
- **play_sequence** / **pause_sequence** / **resume_sequence** / **stop_sequence** - Sequence control
- **get_sequence_status** - Get sequence playback status
- **panic_reset** - Emergency reset all states

### Architecture

The server uses a backend adapter pattern for cross-platform compatibility:
- **VRChat Remote Backend** - OSC protocol communication with VRCEmote system
- **Mock Backend** - Testing and development without VRChat
- **PAD Emotion Model** - Smooth emotion interpolation (Pleasure/Arousal/Dominance)
- **Toggle Behavior** - Automatic handling of VRCEmote toggle states

### Configuration

Environment variables:
- `VIRTUAL_CHARACTER_HOST` - VRChat host (default: 127.0.0.1)
- `VIRTUAL_CHARACTER_OSC_IN` - OSC receive port (default: 9000)
- `VIRTUAL_CHARACTER_OSC_OUT` - OSC send port (default: 9001)
- `VIRTUAL_CHARACTER_EMOTE_TIMEOUT` - Emote timeout in seconds (default: 3)

See `tools/mcp/mcp_virtual_character/README.md` for detailed documentation.

## Desktop Control MCP Server

The Desktop Control server provides cross-platform desktop automation for Linux and Windows, including window management, screenshots, mouse control, and keyboard automation.

### Starting the Server

```bash
# Start via Docker Compose (recommended - requires X11 access)
docker compose up -d mcp-desktop-control

# Or run locally for development
python -m mcp_desktop_control.server --mode http

# View logs
docker compose logs -f mcp-desktop-control

# Test health
curl http://localhost:8025/health
```

### Available Tools

**Window Management:**
- **list_windows** - List all windows with optional title filter
- **get_active_window** - Get the currently focused window
- **focus_window** - Bring a window to the foreground
- **move_window** - Move a window to specific position
- **resize_window** - Resize a window
- **minimize_window** - Minimize a window
- **maximize_window** - Maximize a window
- **restore_window** - Restore a minimized/maximized window
- **close_window** - Close a window

**Screenshots:**
- **screenshot_screen** - Capture entire screen (saves to `outputs/desktop-control/`)
- **screenshot_window** - Capture a specific window
- **screenshot_region** - Capture a screen region

**Mouse Control:**
- **get_mouse_position** - Get current cursor position
- **move_mouse** - Move cursor to position (absolute or relative)
- **click_mouse** - Click at position (left/right/middle, single/double)
- **drag_mouse** - Drag from start to end position
- **scroll_mouse** - Scroll wheel (vertical or horizontal)

**Keyboard Control:**
- **type_text** - Type text string with optional interval
- **send_key** - Send single key with optional modifiers
- **send_hotkey** - Send key combination (e.g., Ctrl+C)

### Platform Support

| Platform | Backend | Tools |
|----------|---------|-------|
| Linux | X11 | xdotool, wmctrl, scrot, mss, pyautogui |
| Windows | Win32 | pywinauto, pywin32, mss, pyautogui |

### Configuration

- **Port**: 8025 (HTTP mode)
- **Output Directory**: `outputs/desktop-control/` (configurable via `DESKTOP_CONTROL_OUTPUT_DIR`)
- **Docker**: Requires X11 socket access and `network_mode: host`

See `tools/mcp/mcp_desktop_control/docs/README.md` for detailed documentation.

## Gaea2 MCP Server (Port 8007)

The Gaea2 server provides comprehensive terrain generation capabilities.

### Starting the Server

```bash
# Start via Docker Compose (recommended for container-first approach)
docker compose up -d mcp-gaea2

# Or run locally for development
python -m tools.mcp.gaea2.server

# For remote server deployment (e.g., on Windows with Gaea2 installed)
# Set GAEA2_REMOTE_URL environment variable to point to the remote server
export GAEA2_REMOTE_URL=http://remote-server:8007

# View logs
docker compose logs -f mcp-gaea2

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
- See `tools/mcp/mcp_gaea2/docs/README.md` for complete documentation

## AI Toolkit MCP Server (Port 8012)

The AI Toolkit server provides an interface to remote AI Toolkit for LoRA training operations.

### Starting the Server

```bash
# Start via Docker Compose (if configured)
docker compose up -d mcp-ai-toolkit

# Or run locally as proxy
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

- **Remote Connection**: Connects to AI Toolkit at `192.168.0.222:8012`
- **Dataset Paths**: Use absolute paths starting with `/ai-toolkit/datasets/`
- **Chunked Upload**: Automatically used for files >100MB

See `tools/mcp/mcp_ai_toolkit/docs/README.md` and `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md` for detailed documentation.

## ComfyUI MCP Server (Port 8013)

The ComfyUI server provides an interface to remote ComfyUI for AI image generation.

### Starting the Server

```bash
# Start via Docker Compose (if configured)
docker compose up -d mcp-comfyui

# Or run locally as proxy
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

- **Remote Connection**: Connects to ComfyUI at `192.168.0.222:8013`
- **FLUX Support**: Different workflows for FLUX models (cfg=1.0, special nodes)
- **LoRA Transfer**: Automatic transfer from AI Toolkit to ComfyUI

See `tools/mcp/mcp_comfyui/docs/README.md` and `docs/integrations/creative-tools/lora-transfer.md` for detailed documentation.

## Codex MCP Server (Rust)

The Codex server provides AI-powered code generation and completion using OpenAI's Codex CLI. This server has been migrated to Rust for improved performance and lower resource usage.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop) - Recommended
mcp-codex --mode stdio

# Or standalone HTTP mode for remote access
mcp-codex --mode standalone --port 8021

# Or use the Docker container (with auth mounted from host)
# Note: :rw mount is required for Codex session files and history
docker compose run --rm -v ~/.codex:/home/user/.codex:rw mcp-codex mcp-codex --mode stdio

# Or use the helper script
./tools/cli/agents/run_codex.sh

# Test health (HTTP mode)
curl http://localhost:8021/health
```

### Building from Source

```bash
cd tools/mcp/mcp_codex
cargo build --release
# Binary at target/release/mcp-codex
```

### Available Tools

- **consult_codex** - Generate, complete, refactor, or explain code
  - Modes: `generate`, `complete`, `refactor`, `explain`, `quick`
  - Supports comparison with previous Claude responses
- **clear_codex_history** - Clear conversation history
- **codex_status** - Get integration status and statistics
- **toggle_codex_auto_consult** - Control auto-consultation on uncertainty

### Configuration

Environment variables:
- `CODEX_ENABLED` - Enable/disable integration (default: true)
- `CODEX_AUTO_CONSULT` - Enable auto-consultation (default: true)
- `CODEX_AUTH_PATH` - Path to auth file (default: ~/.codex/auth.json)
- `CODEX_TIMEOUT` - Timeout in seconds (default: 300)
- `CODEX_MAX_CONTEXT` - Maximum context length (default: 8000)
- `CODEX_BYPASS_SANDBOX` - Bypass sandbox (default: false, only use in containers)

**Authentication**: Requires running `codex auth` first (creates `~/.codex/auth.json`)

## OpenCode MCP Server (Rust)

The OpenCode server provides AI-powered code assistance using OpenRouter API. This server has been migrated to Rust for improved performance and lower resource usage.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop) - Recommended
mcp-opencode --mode stdio

# Or standalone HTTP mode for remote access
mcp-opencode --mode standalone --port 8014

# Or use Docker container
docker compose run --rm mcp-opencode mcp-opencode --mode stdio

# Test health (HTTP mode)
curl http://localhost:8014/health
```

### Building from Source

```bash
cd tools/mcp/mcp_opencode
cargo build --release
# Binary at target/release/mcp-opencode
```

### Available Tools

- **consult_opencode** - Generate, refactor, review, or explain code
  - Modes: `generate`, `refactor`, `review`, `explain`, `quick`
  - Supports comparison with previous Claude responses
- **clear_opencode_history** - Clear conversation history
- **opencode_status** - Get integration status and statistics
- **toggle_opencode_auto_consult** - Control auto-consultation on uncertainty

### Configuration

Environment variables:
- `OPENCODE_ENABLED` - Enable/disable integration (default: true)
- `OPENCODE_AUTO_CONSULT` - Enable auto-consultation (default: true)
- `OPENROUTER_API_KEY` - OpenRouter API key (required)
- `OPENCODE_MODEL` - Model to use (default: qwen/qwen-2.5-coder-32b-instruct)
- `OPENCODE_TIMEOUT` - Timeout in seconds (default: 300)
- `OPENCODE_MAX_PROMPT` - Maximum prompt length (default: 8000)

See `tools/mcp/mcp_opencode/README.md` and `docs/integrations/ai-services/ai-code-agents.md` for detailed documentation.

## Crush MCP Server (Rust)

The Crush server provides code generation using the Crush CLI via OpenRouter API. This server has been migrated to Rust for improved performance and lower resource usage.

### Starting the Server

```bash
# Run in STDIO mode (for local Claude Desktop) - Recommended
mcp-crush --mode stdio

# Or standalone HTTP mode for remote access
mcp-crush --mode standalone --port 8015

# Or use Docker container
docker compose run --rm mcp-crush mcp-crush --mode stdio

# Test health (HTTP mode)
curl http://localhost:8015/health
```

### Building from Source

```bash
cd tools/mcp/mcp_crush
cargo build --release
# Binary at target/release/mcp-crush
```

### Available Tools

- **consult_crush** - Code generation, explanation, and conversion
  - Modes: `generate`, `explain`, `convert`, `quick`
- **clear_crush_history** - Clear conversation history
- **crush_status** - Get integration status and statistics
- **toggle_crush_auto_consult** - Control auto-consultation

### Configuration

Environment variables:
- `CRUSH_ENABLED` - Enable/disable integration (default: true)
- `CRUSH_AUTO_CONSULT` - Enable auto-consultation (default: true)
- `OPENROUTER_API_KEY` - OpenRouter API key (required)
- `CRUSH_TIMEOUT` - Timeout in seconds (default: 300)
- `CRUSH_MAX_PROMPT` - Maximum prompt length (default: 4000)
- `CRUSH_DOCKER_SERVICE` - Docker service name (default: openrouter-agents)

See `tools/mcp/mcp_crush/README.md` and `docs/integrations/ai-services/ai-code-agents.md` for detailed documentation.

## Meme Generator MCP Server

The Meme Generator server creates memes from templates with customizable text overlays and visual feedback. It runs in STDIO mode through Docker Compose for local use.

### Starting the Server

```bash
# The server is configured in .mcp.json and runs automatically through Claude Desktop
# It uses docker compose in STDIO mode

# For manual testing or development:
docker compose run --rm -T mcp-meme-generator python -m tools.mcp.meme_generator.server --mode stdio

# View container logs
docker compose logs -f mcp-meme-generator
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
docker compose up -d mcp-elevenlabs-speech

# Or run locally
python -m tools.mcp.elevenlabs_speech.server --mode http

# View logs
docker compose logs -f mcp-elevenlabs-speech

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

## Video Editor MCP Server

The Video Editor server provides AI-powered video editing capabilities with automatic transcription, speaker diarization, and intelligent scene detection.

### Starting the Server

```bash
# The server is configured in .mcp.json and runs automatically through Claude Desktop
# It uses STDIO mode for seamless integration

# For HTTP mode (testing/development):
docker compose up -d mcp-video-editor

# Or run locally
python -m tools.mcp.video_editor.server --mode http

# View logs
docker compose logs -f mcp-video-editor

# Test health
curl http://localhost:8019/health
```

### Available Tools

- **process_video** - Main processing endpoint with multiple operations
  - Transcription with Whisper
  - Speaker diarization with pyannote
  - Scene detection and analysis
  - Caption generation (SRT/VTT/TXT)
- **compose_videos** - Combine multiple videos with transitions
- **extract_clips** - Extract clips based on keywords or speakers
- **generate_captions** - Create multi-language captions
- **analyze_audio** - Audio analysis and processing
- **apply_video_filter** - Apply visual filters and effects
- **create_montage** - Create montages from multiple clips
- **generate_highlights** - Auto-generate highlight reels
- **job_status** - Check async job status
- **get_job_result** - Retrieve completed job results

### Features

- **AI-Powered Processing**: Automatic transcription and speaker identification
- **Scene Detection**: Intelligent scene boundary detection
- **Multi-Language Support**: Caption generation in multiple languages
- **GPU Acceleration**: CUDA support for faster processing
- **Async Job Processing**: Long operations handled asynchronously
- **Smart Editing**: Extract clips by keywords, speakers, or time ranges
- **Audio Processing**: Advanced audio analysis and enhancement
- **Transition Effects**: Professional transitions for video composition

### Configuration

Add to `.env`:
```bash
# Optional - Hugging Face for models
HUGGINGFACE_TOKEN=your_token_here

# Optional - GPU selection for multi-GPU systems
GPU_DEVICE=0  # Select specific GPU (0, 1, 2, etc.)
```

### GPU Support

The server supports GPU acceleration when available:
- Automatic CUDA detection
- Configurable GPU device selection via `GPU_DEVICE` env var
- Falls back to CPU if GPU unavailable

See `tools/mcp/video_editor/docs/README.md` for detailed documentation.

## GitHub Board MCP Server

The GitHub Board server provides GitHub Projects v2 board management for multi-agent coordination.

### Starting the Server

```bash
# STDIO mode (configured in .mcp.json)
python -m mcp_github_board.server

# HTTP mode for remote access
python -m mcp_github_board.server --http --port 8022
```

### Available Tools

| Tool | Description |
|------|-------------|
| `query_ready_work` | Get unblocked, unclaimed TODO issues |
| `claim_work` | Claim an issue for implementation |
| `renew_claim` | Renew active claims for long-running tasks |
| `release_work` | Release claim on an issue |
| `update_status` | Update issue status on the board |
| `add_blocker` | Add blocking dependencies between issues |
| `mark_discovered_from` | Mark parent-child issue relationships |
| `get_issue_details` | Get full details for a specific issue |
| `get_dependency_graph` | Get dependency graph for an issue |
| `list_agents` | List enabled agents for the board |
| `get_board_config` | Get current board configuration |

See `tools/mcp/mcp_github_board/docs/README.md` for detailed documentation.

## AgentCore Memory MCP Server

The AgentCore Memory server provides multi-provider AI memory with support for AWS Bedrock AgentCore or ChromaDB.

### Starting the Server

```bash
# STDIO mode (configured in .mcp.json)
python -m mcp_agentcore_memory.server

# HTTP mode for remote access
python -m mcp_agentcore_memory.server --http --port 8023
```

### Available Tools

| Tool | Description |
|------|-------------|
| `store_event` | Store short-term memory events (rate-limited for AgentCore) |
| `store_facts` | Store facts for long-term retention |
| `search_memories` | Semantic search across memories |
| `list_session_events` | List events from a specific session |
| `list_namespaces` | List available predefined namespaces |
| `memory_status` | Get memory provider status and info |

### Environment Variables

```bash
MEMORY_PROVIDER=chromadb  # or "agentcore" for AWS
CHROMADB_PATH=./data/chromadb  # For local ChromaDB
```

See `tools/mcp/mcp_agentcore_memory/docs/README.md` for detailed documentation.

## Reaction Search MCP Server

The Reaction Search server provides semantic search for anime reaction images using fastembed (ONNX-based embeddings). This is a Rust implementation for high performance.

### Starting the Server

```bash
# HTTP mode (standalone - default)
mcp-reaction-search --mode standalone --port 8024

# REST-only mode (no MCP protocol)
mcp-reaction-search --mode server --port 8024

# Docker
docker compose --profile services up -d mcp-reaction-search
```

### Available Tools

| Tool | Description |
|------|-------------|
| `search_reactions` | Natural language search for reaction images |
| `get_reaction` | Get a specific reaction by ID |
| `list_reaction_tags` | Browse available tags and counts |
| `refresh_reactions` | Refresh the reaction cache from GitHub |
| `reaction_search_status` | Get server status and initialization state |

### Usage Example

```python
# Search with natural language
search_reactions(query="celebrating after fixing a bug", limit=3)
search_reactions(query="confused about an error message", limit=3)

# Get specific reaction
get_reaction(reaction_id="miku_typing")
```

Source code: `tools/mcp/mcp_reaction_search/`

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
      "command": "mcp-opencode",
      "args": ["--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    },
    "crush": {
      "command": "mcp-crush",
      "args": ["--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    },
    "meme-generator": {
      "command": "docker compose",
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
2. The actual `.mcp.json` uses `docker compose run` commands to start servers in STDIO mode within containers.
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
docker compose down mcp-code-quality
```

### Container Permission Issues

```bash
./automation/setup/runner/fix-runner-permissions.sh
```

### Gemini Server Issues

1. **"Cannot run in container" error** - Run on host system
2. **Gemini CLI not found** - Install with `npm install -g @google/gemini-cli@0.29.5`

### Gaea2 Windows CLI Features

1. **Set GAEA2_PATH** environment variable to Gaea.Swarm.exe location
2. **Ensure Windows host** for CLI automation features

## Development Notes

- Each server extends `BaseMCPServer` from `tools/mcp/core/`
- Servers can run standalone or via Docker Compose
- All servers provide consistent JSON API responses
- Use the modular architecture to add new specialized servers
- Follow the container-first philosophy except where technically impossible (Gemini)
