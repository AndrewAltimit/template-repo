# MCP (Model Context Protocol) Servers

This repository contains a modular collection of 21 MCP servers (two of them, Gemini and Codex, disabled) that provide development, content creation and automation tools. Every server is a Rust binary built on the shared [`mcp-core`](../../tools/mcp/mcp_core_rust/README.md) library and can be run independently.

**Each server's `README.md` in `tools/mcp/<crate>/` is the source of truth** for its tools, parameters, ports and environment variables. See also [servers.md](servers.md) (how to start each server) and [tools.md](tools.md) (tool overview).

## Available MCP Servers

### Local Process Servers (STDIO Transport)

These servers run as local processes on the same machine as the client (most of them inside a container via `docker compose run`):

#### 1. Code Quality MCP Server
**Location**: `tools/mcp/mcp_code_quality/`
**Transport**: STDIO (Docker) or HTTP (Port 8010)
**Documentation**: [Code Quality MCP Documentation](../../tools/mcp/mcp_code_quality/README.md)

Runs code quality tools as bounded subprocesses on allow-listed paths (10 tools):
- Format checking and auto-formatting (Python via `ruff format` by default, JS/TS, Go, Rust)
- Linting (ruff, flake8, eslint, golint, clippy) and type checking (ty)
- pytest, bandit, pip-audit and a markdown link checker
- Path allowlist, timeouts, rate limits and an audit log

#### 2. Content Creation MCP Server
**Location**: `tools/mcp/mcp_content_creation/`
**Transport**: STDIO (Docker) or HTTP (Port 8011)
**Documentation**: [Content Creation MCP Documentation](../../tools/mcp/mcp_content_creation/README.md)

Technical content (5 tools):
- Sandboxed LaTeX compilation (PDF, DVI, PS) with BibTeX, re-runs and page previews
- TikZ diagram rendering (PDF, PNG, SVG)
- PDF page previews
- Manim animations (MP4, GIF, WebM, last-frame PNG)

#### 3. ~~Gemini AI Integration MCP Server~~ (DISABLED)
**Location**: `tools/mcp/mcp_gemini/`
**Documentation**: [Gemini MCP Documentation](../../tools/mcp/mcp_gemini/README.md)

**DISABLED**: Google updated its AI principles (Feb 2026) to allow mass surveillance and autonomous weapons use cases. All Gemini integrations are disabled. Use Anthropic models (Claude) instead.

#### 4. OpenCode MCP Server
**Location**: `tools/mcp/mcp_opencode/`
**Transport**: STDIO (Docker) or HTTP (Port 8014)
**Documentation**: [OpenCode MCP Documentation](../../tools/mcp/mcp_opencode/README.md)

Code assistance through an OpenRouter-hosted model (default `qwen/qwen3.7-max`):
- Modes: quick, generate, refactor, review, explain
- Per-call model, temperature and token-limit overrides
- Conversation history management

#### 5. Crush MCP Server
**Location**: `tools/mcp/mcp_crush/`
**Transport**: STDIO (Docker) or HTTP (Port 8015)
**Documentation**: [Crush MCP Documentation](../../tools/mcp/mcp_crush/README.md)

Code generation through the Crush CLI and OpenRouter:
- Modes: quick, generate, explain, convert
- Runs crush locally or in a docker compose service (`CRUSH_EXECUTION`)
- Conversation history management

#### 6. Meme Generator MCP Server
**Location**: `tools/mcp/mcp_meme_generator/`
**Transport**: STDIO (Docker) or HTTP (Port 8016)
**Documentation**: [Meme Generator MCP Documentation](../../tools/mcp/mcp_meme_generator/README.md)

Generate memes with customizable text overlays (6 tools):
- 8 validated templates with usage rules and cultural context
- Auto-fit text with clean outlines
- Inline preview image for AI verification
- Optional upload for sharing (0x0.st, tmpfiles.org, file.io)

#### 7. ElevenLabs Speech MCP Server
**Location**: `tools/mcp/mcp_elevenlabs_speech/`
**Transport**: STDIO (Docker) or HTTP (Port 8018)
**Documentation**: [ElevenLabs MCP Documentation](../../tools/mcp/mcp_elevenlabs_speech/README.md)

Text-to-speech and sound effects via the ElevenLabs API (7 tools):
- Every current TTS model; `eleven_v3` supports inline audio tags ([laughs], [whispers], ...)
- Voice names resolved against your account's voices; 10 voice-settings presets
- Sound effects (0.5-30 seconds, optional looping)
- Voice, model and subscription queries
- Audio saved locally (`outputs/elevenlabs_speech`); no automatic upload

#### 8. Video Editor MCP Server
**Location**: `tools/mcp/mcp_video_editor/`
**Transport**: STDIO (Docker) or HTTP (Port 8019)
**Documentation**: [Video Editor MCP Documentation](../../tools/mcp/mcp_video_editor/README.md)

Automated video editing with ffmpeg (9 tools):
- Transcription with the Whisper CLI (optional, baked in with `VIDEO_EDITOR_WHISPER=true`)
- Loudness, silence and peak analysis; scene detection
- Energy-based multi-camera speaker switching (no ML diarization)
- Edit decision lists, rendering with transitions, zoom and picture-in-picture
- Clip extraction by time range or keyword; captions (burned in or muxed)
- Background jobs with progress and cancellation; NVENC encoding when available

#### 9. Blender MCP Server
**Location**: `tools/mcp/mcp_blender/`
**Transport**: STDIO (Docker) or HTTP (Port 8017)
**Documentation**: [Blender MCP Documentation](../../tools/mcp/mcp_blender/README.md)

3D content creation with headless Blender (42 tools):
- Projects from templates, primitives, curves, text, armatures, constraints
- Materials, textures, UVs, lighting, world environments, cameras, compositor
- Animation, modifiers, physics, particles, smoke, geometry-node presets, quick effects
- Rendering (image, animation, batch) and simulation bakes as background jobs
- Import/export of FBX, OBJ, GLTF/GLB, STL, PLY, USD

#### 10. Virtual Character MCP Server
**Location**: `tools/mcp/mcp_virtual_character/`
**Transport**: HTTP (Port 8025, recommended natively on the VRChat PC) or STDIO
**Documentation**: [Virtual Character MCP Documentation](../../tools/mcp/mcp_virtual_character/README.md)

AI agent embodiment in virtual worlds:
- VRChat backend over OSC with VRCEmote toggle tracking and emote auto-clear
- Mock backend for offline development and tests
- Emotions, gestures, movement and custom avatar parameters
- Speech playback with ElevenLabs expression tag detection
- Timed multi-event sequences
- 18 MCP tools for complete avatar control

#### 11. ~~Codex MCP Server~~ (DISABLED)
**Location**: `tools/mcp/mcp_codex/`
**Transport**: STDIO (local) or HTTP (Port 8021)
**Documentation**: [Codex MCP Documentation](../../tools/mcp/mcp_codex/README.md)

**DISABLED**: OpenAI has entered partnerships with governments that conduct mass surveillance and enable autonomous weapons. All Codex/OpenAI integrations are disabled. Use Anthropic models (Claude) instead.

~~AI-powered code assistance via OpenAI Codex~~:
- ~~Code generation, completion, and refactoring~~
- ~~Code explanation and documentation~~
- ~~Conversation history management~~
- ~~Requires ChatGPT Plus subscription for Codex CLI auth~~

#### 12. GitHub Board MCP Server
**Location**: `tools/mcp/mcp_github_board/`
**Transport**: STDIO (Docker) or HTTP (Port 8022)
**Documentation**: [GitHub Board MCP Documentation](../../tools/mcp/mcp_github_board/README.md)

Work queue management for multi-agent coordination (17 tools, wrapping the `board-manager` CLI):
- Query ready work (unblocked, unclaimed issues)
- Claim/renew/release work with conflict prevention; stale-claim cleanup
- Dependency graph management (blockers, parent-child)
- Approval checks and adding issues to the board
- `--read-only` mode; configured by `ai-agents-board.yml`

#### 13. AgentCore Memory MCP Server
**Location**: `tools/mcp/mcp_agentcore_memory/`
**Transport**: STDIO (Docker) or HTTP (Port 8023)
**Documentation**: [AgentCore Memory MCP Documentation](../../tools/mcp/mcp_agentcore_memory/README.md)

ChromaDB-backed memory for AI agents (despite the name, no AWS AgentCore):
- Short-term session events
- Long-term fact storage in hierarchical namespaces, deduplicated
- Semantic search with locally computed embeddings (all-MiniLM-L6-v2)
- Browse, delete and re-index stored facts
- Secret sanitization before storage

#### 14. Reaction Search MCP Server
**Location**: `tools/mcp/mcp_reaction_search/`
**Transport**: STDIO (Docker) or HTTP (Port 8024)
**Documentation**: [Reaction Search MCP Documentation](../../tools/mcp/mcp_reaction_search/README.md)

Semantic search for reaction images:
- Natural language search ranked by ONNX sentence embeddings (fastembed) plus keyword/tag boosts
- Keyword-search fallback when the embedding model is unavailable
- Auto-fetches the reaction config from GitHub, with on-disk and stale-cache fallback
- Tag-based filtering, catalog listing and browsing

#### 15. Desktop Control MCP Server
**Location**: `tools/mcp/mcp_desktop_control/`
**Transport**: STDIO (native) or HTTP (Port 8026)
**Documentation**: [Desktop Control MCP Documentation](../../tools/mcp/mcp_desktop_control/README.md)

Cross-platform desktop automation (23 tools):
- Window management (list, focus, move, resize, minimize, maximize, restore, close)
- Multi-monitor layout and screenshots (screen, window, region; optional inline image)
- Mouse control (move, click, drag, scroll) and keyboard automation (text, keys, hotkeys)
- Linux: pure-Rust X11 backend (`x11rb`, XTEST, RandR)
- Windows: native Win32 backend (`SendInput`, per-monitor DPI awareness)

#### 16. Sprite Sheet MCP Server
**Location**: `tools/mcp/mcp_sprite_sheet/`
**Transport**: STDIO (Docker) or HTTP (Port 8027)
**Documentation**: [Sprite Sheet MCP Documentation](../../tools/mcp/mcp_sprite_sheet/README.md)

Programmatic pixel art and sprite sheet creation:
- Projects with versioned JSON save/load
- Layer system with blend modes and compositing
- Drawing primitives (pixels, lines, rectangles, ellipses, flood fill)
- Palette presets, custom palettes and color swapping
- Sprite and animation definitions; transforms (flip, rotate, shift)
- PNG rendering, animated GIF and texture-atlas (PNG + JSON) export
- Image import and edge cleanup
- Undo/redo for every edit
- 38 specialized tools

#### 17. Memory Explorer MCP Server
**Location**: `tools/mcp/mcp_memory_explorer/`
**Transport**: STDIO (native binary, not containerized) or HTTP (Port 8028)
**Documentation**: [Memory Explorer MCP Documentation](../../tools/mcp/mcp_memory_explorer/README.md)

Read-only process memory exploration for agent integration with legacy software (Windows and Linux for memory operations):
- Process listing, attachment (by name or pid), module and memory-region enumeration
- Typed memory reads (bytes, 8-64 bit integers, floats, vectors, matrices, strings, wide strings, pointers)
- Hex dump with ASCII representation
- Byte pattern scanning with wildcard support
- Value search with refinement ("next scan")
- Pointer chain resolution for stable addresses
- Address watch list for monitoring changes

#### 18. BioForge MCP Server (simulated hardware)
**Location**: `tools/mcp/mcp_bioforge/`
**Transport**: STDIO (native binary) or HTTP (Port 8030 by convention); not configured in `.mcp.json`
**Documentation**: [BioForge MCP Documentation](../../tools/mcp/mcp_bioforge/README.md)

MCP front end for the [BioForge](../../packages/bioforge/README.md) lab-automation platform (16 tools):
- Liquid handling, thermal control, gantry motion and plate imaging against simulated drivers
- Real safety enforcement, protocol validation, e-stop latch, human-in-the-loop gates and audit log

### Remote/Cross-Machine Servers (HTTP Transport)

These servers use HTTP transport for remote machines or special hardware/software requirements:

#### 1. Gaea2 Terrain Generation MCP Server
**Location**: `tools/mcp/mcp_gaea2/`
**Transport**: HTTP (Port 8007)
**Remote Location**: `192.168.0.152:8007`
**Documentation**: [Gaea2 MCP Documentation](../../tools/mcp/mcp_gaea2/README.md) | [Full Documentation Index](../../tools/mcp/mcp_gaea2/docs/INDEX.md)

Terrain generation with Gaea2 (15 tools):
- Validation with auto-fix; invalid workflows are never written
- 11 terrain templates
- Build automation through `Gaea.Swarm.exe` (Windows host only)
- In-place project repair, analysis and property optimization
- Node reference lookup (`list_gaea2_nodes`)

**Why HTTP**: Builds require Windows with Gaea2 installed

#### 2. AI Toolkit MCP Server
**Location**: `tools/mcp/mcp_ai_toolkit/`
**Transport**: HTTP (Port 8020)
**Remote Location**: `192.168.0.222:8020`
**Documentation**: [AI Toolkit MCP Documentation](../../tools/mcp/mcp_ai_toolkit/README.md)

GPU LoRA training management (22 tools):
- Training configuration creation, validation and model presets
- Dataset upload and caption coverage checks
- Training job control, progress, logs and sample images
- Model export and (chunked) download
- System and GPU statistics

**Why HTTP**: Requires NVIDIA GPU and the AI Toolkit environment

#### 3. ComfyUI MCP Server
**Location**: `tools/mcp/mcp_comfyui/`
**Transport**: HTTP (Port 8013; ComfyUI itself on 8188)
**Remote Location**: `192.168.0.222:8013`
**Documentation**: [ComfyUI MCP Documentation](../../tools/mcp/mcp_comfyui/README.md)

GPU image generation (15 tools):
- FLUX/SDXL text-to-image, img2img, upscaling and ControlNet templates
- Arbitrary API-format workflow execution with job tracking and cancellation
- Image upload/download and model listing
- LoRA file management on the GPU host

**Why HTTP**: Requires NVIDIA GPU and ComfyUI installation

## Configuration and Transport

### Transport Mode Selection

**STDIO Transport**: Used for local processes running on the same machine as the client
- Configured in `.mcp.json` with `command` and `args`
- Client spawns the server as a child process (here usually `docker compose run --rm -T <service> <binary> --mode stdio`)
- Communication via standard input/output

**HTTP Transport**: Used for remote machines or special environment requirements
- Configured in `.mcp.json` with `type: "http"` and `url`
- Server runs independently as a network service (`--mode standalone --port <port>`)
- Communication via HTTP (MCP Streamable HTTP, JSON responses)

For detailed configuration and troubleshooting:
- **[MCP Server Modes: STDIO vs HTTP](architecture/stdio-vs-http.md)** - Complete guide for transport modes
- **[MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25)** - Official protocol specification (`mcp-core` negotiates 2025-11-25, 2025-06-18, 2025-03-26 and 2024-11-05)

### Configuration File (.mcp.json)

All MCP servers are configured in the `.mcp.json` file at the project root.

**STDIO servers** (local processes, containerized):
```json
{
  "mcpServers": {
    "code-quality": {
      "command": "docker",
      "args": ["compose", "-f", "./docker-compose.yml", "--profile", "services",
               "run", "--rm", "-T", "mcp-code-quality", "mcp-code-quality", "--mode", "stdio"]
    }
  }
}
```

**HTTP servers** (remote/cross-machine):

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

### Configuration Strategy

This repository provides two MCP configuration files to optimize context window usage:

**`.mcp.json` (Default - Essential Services)**
- Prevents context window overload in Claude Code
- Contains: Code Quality, Content Creation, Blender, AI agents (OpenCode, Crush; Gemini and Codex disabled), GitHub Board, AgentCore Memory, Reaction Search, Sprite Sheet
- Best for: Day-to-day development, code review, refactoring

**`.mcp.json.full` (Complete - All Services)**
- Access to the full set of specialized MCP servers
- Additional: Meme Generator, ElevenLabs, Memory Explorer, remote services (Gaea2, AI Toolkit, ComfyUI, Virtual Character)
- Best for: Creating media, 3D content, terrain, or working with remote GPU services

**Switching Between Configurations:**

```bash
# Enable all services temporarily
mv .mcp.json .mcp.json.essential
mv .mcp.json.full .mcp.json
# Restart Claude Code

# Restore essential services
mv .mcp.json .mcp.json.full
mv .mcp.json.essential .mcp.json
# Restart Claude Code
```

**Recommendation**: Start with `.mcp.json` (essential) and only switch when you need specialized tools.

## Architecture Overview

```
tools/mcp/
├── mcp_core_rust/          # Shared Rust library: mcp-core (protocol, transports, Tool trait) + mcp-testing
│
# Local Process Servers (STDIO)
├── mcp_code_quality/       # Code quality tools
├── mcp_content_creation/   # LaTeX, TikZ & Manim tools
├── mcp_gemini/             # Gemini AI integration (DISABLED)
├── mcp_codex/              # Codex AI code generation (DISABLED - OpenAI security risk)
├── mcp_opencode/           # OpenCode (OpenRouter) code assistance
├── mcp_crush/              # Crush code generation
├── mcp_meme_generator/     # Meme generation
├── mcp_elevenlabs_speech/  # Text-to-speech synthesis
├── mcp_video_editor/       # Automated video editing
├── mcp_blender/            # 3D content creation
├── mcp_virtual_character/  # AI agent embodiment (VRChat)
├── mcp_github_board/       # GitHub Projects board management
├── mcp_agentcore_memory/   # ChromaDB-backed agent memory
├── mcp_reaction_search/    # Reaction image search
├── mcp_desktop_control/    # Desktop automation (native)
├── mcp_sprite_sheet/       # Pixel art and sprite sheets
├── mcp_memory_explorer/    # Process memory exploration (native)
├── mcp_bioforge/           # BioForge lab automation (simulated hardware)
│
# Remote/Cross-Machine Servers (HTTP)
├── mcp_gaea2/              # Terrain generation (Windows requirement)
├── mcp_ai_toolkit/         # LoRA training (GPU requirement)
└── mcp_comfyui/            # Image generation (GPU requirement)
```

## Running MCP Servers

### Local Process Servers (STDIO)
Claude Code automatically starts these servers (from `.mcp.json`) when you use their tools. No manual startup required:
```python
# Just use the tool - Claude handles the rest
result = mcp__code_quality__format_check(path="./src")
```

### Remote/Cross-Machine Servers (HTTP)
These servers must be started independently on their host machines:
```bash
# Windows machine with Gaea2 (or automation/launchers/windows/start-gaea2-mcp.bat)
mcp-gaea2 --mode standalone --port 8007 --gaea-path "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"

# GPU machine: both are started by their container entrypoints
docker compose --profile ai-services up -d mcp-ai-toolkit mcp-comfyui
```

### Dual-Mode Servers
Every server supports both STDIO and HTTP:
```bash
docker compose --profile services run --rm -T mcp-<name> mcp-<name> --mode stdio   # STDIO in the container
docker compose --profile services up -d mcp-<name>                                 # HTTP in the container
mcp-<name> --mode standalone --port <port>                                          # native binary
```

## Claude Desktop Configuration

Add the desired servers to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "code-quality": {
      "command": "docker",
      "args": ["compose", "-f", "/path/to/repo/docker-compose.yml", "--profile", "services",
               "run", "--rm", "-T", "mcp-code-quality", "mcp-code-quality", "--mode", "stdio"]
    },
    "memory-explorer": {
      "command": "/path/to/repo/tools/mcp/mcp_memory_explorer/target/release/mcp-memory-explorer",
      "args": ["--mode", "stdio"]
    },
    "comfyui": {
      "type": "http",
      "url": "http://192.168.0.222:8013/messages"
    }
  }
}
```

## Docker Support

Each containerized server has a service in `docker-compose.yml` (built from `docker/*.Dockerfile`), mostly in the `services` profile:

| Service | Profile(s) | Port | Output on host |
|---------|-----------|------|----------------|
| `mcp-code-quality` | services | 8010 | - (repo mounted read-only) |
| `mcp-content-creation` | services | 8011 | `outputs/mcp-content` |
| `mcp-opencode` / `mcp-crush` | services | 8014 / 8015 | - |
| `mcp-meme-generator` | services | 8016 | `outputs/mcp-memes` |
| `mcp-blender` | services, gpu | 8017 | `outputs/blender/` |
| `mcp-elevenlabs-speech` | services | 8018 | `outputs/elevenlabs_speech` |
| `mcp-video-editor` | services, gpu | 8019 | `outputs/video-editor` |
| `mcp-github-board` | services | 8022 | - |
| `mcp-agentcore-memory` | services, memory | 8023 | ChromaDB volume (`chromadb` service, profile `memory-chromadb`) |
| `mcp-reaction-search` | services | 8024 | cache volume |
| `mcp-virtual-character` | services | 8025 (+ 9001/udp) | - |
| `mcp-desktop-control` | services, desktop | 8026 (host network) | `outputs/desktop-control` |
| `mcp-sprite-sheet` | services | 8027 | `outputs/mcp-sprites` |
| `mcp-gaea2` | services | 8007 | `outputs/mcp-gaea2` |
| `mcp-ai-toolkit` | ai-services, gpu | 8020 (+ UI 8675) | named volumes |
| `mcp-comfyui` | ai-services, gpu | 8013 (+ ComfyUI 8188) | `comfyui/` |

Memory Explorer and BioForge have no compose service; the Gemini and Codex services are disabled.

## Development

### Creating a New MCP Server

1. Create a new crate under `tools/mcp/mcp_<name>/` depending on `mcp-core` (`../mcp_core_rust/crates/mcp-core`)
2. Implement the `Tool` trait for each tool and register them with `MCPServer::builder`
3. Write a `README.md` covering tools, parameters, configuration and limitations
4. Add a Dockerfile, a docker compose service and a `.mcp.json` entry
5. Add unit tests (`mcp-testing` provides helpers)

See the [mcp_core_rust README](../../tools/mcp/mcp_core_rust/README.md) for the full guide.

### Testing

Each server has offline unit tests:
```bash
cd tools/mcp/<crate>
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

Test all Rust crates (including every MCP server):
```bash
automation-cli ci run rust-full
```

## Common Issues

### Server Modes and Ports

**STDIO Mode (Default - no ports exposed):** every server launched from `.mcp.json` via `docker compose run`, plus the native Memory Explorer.

**HTTP Mode (Remote servers):**
- Gaea2: 8007 (remote at 192.168.0.152)
- AI Toolkit: 8020 (remote at 192.168.0.222)
- ComfyUI: 8013 (remote at 192.168.0.222)

**Development Ports (when running servers in HTTP mode):**
- Code Quality: 8010, Content Creation: 8011
- OpenCode: 8014, Crush: 8015, Meme Generator: 8016, Blender: 8017, ElevenLabs: 8018, Video Editor: 8019
- GitHub Board: 8022, AgentCore Memory: 8023, Reaction Search: 8024
- Virtual Character: 8025, Memory Explorer: 8028
- Desktop Control: 8026, Sprite Sheet: 8027, BioForge: 8030

The shared `mcp-core` default port is 8000; always pass `--port` when running a binary by hand.

### Container Restrictions
- **Memory Explorer**: Native only (must see host processes)
- **Desktop Control**: Container needs the host X11 socket; Windows runs natively
- **Gaea2 builds**: Require a Windows host with Gaea2 installed
- **AI Toolkit/ComfyUI**: Run on the GPU host next to the software they control
- **Virtual Character**: Audio playback needs the VRChat PC; the container handles animation/movement only

### Missing Dependencies
Each server has specific requirements. Check the server's README for installation instructions.

## Contributing

This is a single-maintainer project; external contributions are not accepted. When changing MCP servers:

1. Follow the modular structure
2. Keep the crate README accurate (it is the source of truth)
3. Include tests
4. Update this overview if adding new servers

## License

See repository LICENSE file.
