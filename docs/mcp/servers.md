# MCP Servers Documentation

This project uses a modular architecture of Model Context Protocol (MCP) servers, each specialized for one area. Every server is a Rust binary built on the shared [`mcp-core`](../../tools/mcp/mcp_core_rust/README.md) library and lives in `tools/mcp/<crate>/`.

**Each crate's `README.md` is the source of truth** for its tools, parameters, environment variables and limitations. This page is an index: how to start each server, which tools it exposes, and where to read more.

## Architecture Overview

| # | Server | Crate | Typical launch | HTTP port | Tools |
|---|--------|-------|----------------|-----------|-------|
| 1 | Code Quality | `mcp_code_quality` | STDIO via docker compose (`.mcp.json`) | 8010 | 10 |
| 2 | Content Creation | `mcp_content_creation` | STDIO via docker compose (`.mcp.json`) | 8011 | 5 |
| 3 | ~~Gemini~~ (disabled) | `mcp_gemini` | - | 8006 | 4 |
| 4 | ~~Codex~~ (disabled) | `mcp_codex` | - | 8021 | 4 |
| 5 | OpenCode | `mcp_opencode` | STDIO via docker compose (`.mcp.json`) | 8014 | 4 |
| 6 | Crush | `mcp_crush` | STDIO via docker compose (`.mcp.json`) | 8015 | 4 |
| 7 | Meme Generator | `mcp_meme_generator` | STDIO via docker compose (`.mcp.json.full`) | 8016 | 6 |
| 8 | ElevenLabs Speech | `mcp_elevenlabs_speech` | STDIO via docker compose (`.mcp.json.full`) | 8018 | 7 |
| 9 | Video Editor | `mcp_video_editor` | STDIO via docker compose (not in `.mcp.json`) | 8019 | 9 |
| 10 | Blender | `mcp_blender` | STDIO via docker compose (`.mcp.json`) | 8017 | 42 |
| 11 | Virtual Character | `mcp_virtual_character` | HTTP on the VRChat host (`.mcp.json.full`) | 8025 | 18 |
| 12 | Desktop Control | `mcp_desktop_control` | Native binary, STDIO or HTTP (not in `.mcp.json`) | 8026 | 23 |
| 13 | GitHub Board | `mcp_github_board` | STDIO via docker compose (`.mcp.json`) | 8022 | 17 |
| 14 | AgentCore Memory | `mcp_agentcore_memory` | STDIO via docker compose (`.mcp.json`) | 8023 | 9 |
| 15 | Reaction Search | `mcp_reaction_search` | STDIO via docker compose (`.mcp.json`) | 8024 | 6 |
| 16 | Sprite Sheet | `mcp_sprite_sheet` | STDIO via docker compose (`.mcp.json`) | 8027 | 38 |
| 17 | Memory Explorer | `mcp_memory_explorer` | Native binary, STDIO (`.mcp.json.full`) | 8028 | 15 |
| 18 | Gaea2 | `mcp_gaea2` | HTTP, `192.168.0.152:8007` (`.mcp.json.full`) | 8007 | 15 |
| 19 | AI Toolkit | `mcp_ai_toolkit` | HTTP, `192.168.0.222:8020` (`.mcp.json.full`) | 8020 | 22 |
| 20 | ComfyUI | `mcp_comfyui` | HTTP, `192.168.0.222:8013` (`.mcp.json.full`) | 8013 | 15 |
| 21 | BioForge (simulated hardware) | `mcp_bioforge` | Native binary, STDIO (not configured) | 8030 (convention) | 16 |

HTTP ports are what docker compose (or the crate's documented convention) passes with `--port`; the shared `mcp-core` default is 8000, so always pass `--port` when running a binary by hand.

### Common CLI and endpoints

All servers share the `mcp-core` flags: `--mode stdio|standalone|server|client`, `--port`, `--log-level` (logs go to stderr), `--backend-url` (client mode). In `standalone` mode every server exposes:

| Endpoint | Purpose |
|----------|---------|
| `POST /messages` (also `/mcp`, `/mcp/rpc`) | MCP JSON-RPC (Streamable HTTP, JSON responses) |
| `GET /health` | Health check |
| `GET /mcp/tools` | List tools (simple REST API) |
| `POST /mcp/execute` | Run a tool: `{"tool": "...", "arguments": {...}}` |
| `GET /.well-known/mcp` | Discovery |

Invalid arguments are rejected with a JSON-RPC `Invalid params` error; runtime failures come back as tool results with `isError: true`. See [mcp_core_rust](../../tools/mcp/mcp_core_rust/README.md) for protocol details.

## Code Quality MCP Server

Runs formatters, linters, tests and security scanners as bounded subprocesses on paths inside an allowlist (no shell, hard timeouts, capped output, rate limits, audit log).

```bash
docker compose --profile services run --rm -T mcp-code-quality mcp-code-quality --mode stdio   # as .mcp.json
docker compose --profile services up -d mcp-code-quality                                       # HTTP on 8010
curl http://localhost:8010/health
```

| Tool | Description |
|------|-------------|
| `format_check` | Check formatting (Python defaults to `ruff format`; `formatter: "black"` available; prettier, gofmt, cargo fmt/rustfmt) |
| `autoformat` | Format files in place (fails on the read-only `/app` mount) |
| `lint` | ruff, flake8, eslint, golint or clippy |
| `type_check` | `ty check` |
| `run_tests` | pytest with pattern/markers/coverage options |
| `security_scan` | bandit |
| `audit_dependencies` | pip-audit on a requirements file |
| `check_markdown_links` | Repository `md-link-checker` |
| `get_status` | Configuration, allowlist, and which external tools are available |
| `get_audit_log` | Recent audit log entries |

The container image has no Go or Rust toolchain, so gofmt/golint/cargo tools report `tool_not_found` there. Details: [`tools/mcp/mcp_code_quality/README.md`](../../tools/mcp/mcp_code_quality/README.md).

## Content Creation MCP Server

Sandboxed LaTeX compilation, TikZ rendering, PDF previews and Manim animations.

```bash
docker compose --profile services run --rm -T mcp-content-creation mcp-content-creation --mode stdio   # as .mcp.json
docker compose --profile services up -d mcp-content-creation                                           # HTTP on 8011
```

| Tool | Description |
|------|-------------|
| `compile_latex` | Compile inline `content` or a project `input_path` to PDF/DVI/PS (`output_format`, alias `format`), with re-runs, BibTeX and optional page previews |
| `render_tikz` | Render TikZ to PDF/PNG/SVG; `tikz_libraries`, `packages`, `dpi` |
| `preview_pdf` | Render selected pages of an existing PDF to PNG |
| `create_manim_animation` | Render a Manim scene to MP4/GIF/WebM/PNG; `quality` is `low`/`medium`/`high`/`production`/`fourk`; `preview` renders only the last frame as PNG |
| `content_creation_status` | Configuration and installed external tools |

Output goes to `/output` in the container, bind-mounted to `outputs/mcp-content` on the host (`--output-dir` / `MCP_OUTPUT_DIR`). Details: [`tools/mcp/mcp_content_creation/README.md`](../../tools/mcp/mcp_content_creation/README.md).

## ~~Gemini MCP Server (Rust)~~ -- DISABLED

> **DISABLED**: Google updated its AI principles (Feb 2026) to allow mass surveillance and autonomous weapons use cases. All Gemini integrations are disabled. Use Anthropic models (Claude) instead.

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

## ~~Codex MCP Server (Rust)~~ -- DISABLED

> **DISABLED**: OpenAI has entered partnerships with governments that conduct mass surveillance and enable autonomous weapons. All Codex/OpenAI integrations are disabled. Use Anthropic models (Claude) instead. See the [main README](../../README.md#ai-agents) for details.

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

## OpenCode MCP Server

Consults an OpenRouter-hosted model (one chat-completion request per call; it does not run the `opencode` CLI).

```bash
docker compose --profile services run --rm -T mcp-opencode mcp-opencode --mode stdio   # as .mcp.json
mcp-opencode --mode standalone --port 8014
```

| Tool | Description |
|------|-------------|
| `consult_opencode` | Ask the model: `query`, `context`, `mode` (`quick`, `generate`, `refactor`, `review`, `explain`), per-call `model`, `temperature`, `max_tokens`, `force`. `comparison_mode` is accepted but has no effect |
| `opencode_status` | Status, statistics and effective configuration |
| `clear_opencode_history` | Clear conversation history |
| `toggle_opencode_auto_consult` | Set or flip the advisory auto-consult flag |

Key environment: `OPENROUTER_API_KEY` (required), `OPENCODE_MODEL` (default `qwen/qwen3.7-max`), `OPENCODE_TIMEOUT` (300), `OPENCODE_MAX_PROMPT` (32000), `OPENCODE_MAX_TOKENS` (4096). Details: [`tools/mcp/mcp_opencode/README.md`](../../tools/mcp/mcp_opencode/README.md) and `docs/integrations/ai-services/ai-code-agents.md`.

## Crush MCP Server

Runs the Crush CLI (`crush run`) through OpenRouter, with the prompt on stdin, a scratch working directory and a hard timeout.

```bash
docker compose --profile services run --rm -T mcp-crush mcp-crush --mode stdio   # as .mcp.json
mcp-crush --mode standalone --port 8015
```

| Tool | Description |
|------|-------------|
| `consult_crush` | Ask crush: `query`, `context`, `mode` (`quick`, `generate`, `explain`, `convert` - `convert` requires the target language in `context`), per-call `model`, `force`. `comparison_mode` is accepted but has no effect |
| `crush_status` | Status, statistics and effective configuration, including the resolved execution mode |
| `clear_crush_history` | Clear conversation history |
| `toggle_crush_auto_consult` | Set or flip the advisory auto-consult flag |

Key environment: `OPENROUTER_API_KEY` (required), `CRUSH_MODEL` (default `qwen/qwen3.7-max`), `CRUSH_EXECUTION` (`auto` / `local` / `docker`; the image uses `local`), `CRUSH_DOCKER_SERVICE` (default `mcp-crush`), `CRUSH_TIMEOUT` (300), `CRUSH_MAX_PROMPT` (32000). Details: [`tools/mcp/mcp_crush/README.md`](../../tools/mcp/mcp_crush/README.md).

## Meme Generator MCP Server

Draws auto-fitted captions onto templates, returns an inline preview image, and optionally uploads the result (0x0.st, tmpfiles.org or file.io).

```bash
docker compose --profile services run --rm -T mcp-meme-generator mcp-meme-generator --mode stdio   # as .mcp.json.full
docker compose --profile services up -d mcp-meme-generator                                         # HTTP on 8016
```

| Tool | Description |
|------|-------------|
| `generate_meme` | Render captions on a template, save, preview, optionally upload |
| `list_meme_templates` | List templates with their text area ids |
| `get_meme_template_info` | Full template config, usage rules and an example call |
| `meme_generator_status` | Version, template load errors/warnings, font, directories, upload settings |
| `upload_meme` | Upload an already generated meme from the output directory |
| `reload_meme_templates` | Re-read templates and font from disk |

Templates (8): `afraid_to_ask_andy`, `community_fire`, `handshake_office`, `millionaire`, `npc_wojak`, `ol_reliable`, `one_does_not_simply`, `sweating_jordan_peele`. Output goes to `outputs/mcp-memes`. Details: [`tools/mcp/mcp_meme_generator/README.md`](../../tools/mcp/mcp_meme_generator/README.md).

## ElevenLabs Speech MCP Server

Text-to-speech and sound effects through the ElevenLabs API; audio is saved locally and the tools return the file path.

```bash
docker compose --profile services run --rm -T mcp-elevenlabs-speech mcp-elevenlabs-speech --mode stdio   # as .mcp.json.full
docker compose --profile services up -d mcp-elevenlabs-speech                                            # HTTP on 8018
```

| Tool | Description |
|------|-------------|
| `synthesize_speech` | TTS with any current model (`eleven_v3` supports inline audio tags such as `[laughs]`), voice names or IDs, presets and voice settings |
| `generate_sound_effect` | Sound effect from a prompt (0.5-30 s, optional loop) |
| `list_voices` | Voices on your account, with search/category filters |
| `get_user_subscription` | Tier and character usage |
| `get_models` | Available models and their limits |
| `list_presets` | The 10 voice-settings presets (no API key needed) |
| `clear_cache` | Delete audio files this server generated (no API key needed) |

```bash
# .env
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_DEFAULT_MODEL=eleven_v3        # crate default; compose defaults to eleven_multilingual_v2
ELEVENLABS_DEFAULT_VOICE=george           # ElevenLabs is retiring premade voices; prefer a voice you own
```

Audio is written to `outputs/elevenlabs_speech` (container `/output`). There is no automatic upload. Details: [`tools/mcp/mcp_elevenlabs_speech/README.md`](../../tools/mcp/mcp_elevenlabs_speech/README.md).

## Video Editor MCP Server

Automated editing with ffmpeg: probing, loudness/silence analysis, Whisper transcription (when the CLI is installed), scene detection, energy-based multi-camera speaker switching, EDLs, rendering with transitions/zoom/PiP, clips and captions.

```bash
docker compose --profile services run --rm -T mcp-video-editor mcp-video-editor --mode stdio
docker compose --profile services up -d mcp-video-editor                        # HTTP on 8019
VIDEO_EDITOR_WHISPER=true docker compose build mcp-video-editor                 # bake in the Whisper CLI
```

| Tool | Description |
|------|-------------|
| `video_editor/analyze` | Media info, transcript, loudness/silences/peaks, scenes, speakers, highlights, suggestions |
| `video_editor/create_edit` | Generate and save an EDL without rendering |
| `video_editor/render` | Render a given or auto-generated EDL |
| `video_editor/extract_clips` | Cut clips by time range and/or transcript keyword |
| `video_editor/add_captions` | Transcribe and burn in (or mux) captions |
| `video_editor/get_video_info` | ffprobe summary |
| `video_editor/get_job_status` | Status, progress and result of a job |
| `video_editor/list_jobs` | Recent jobs, optionally filtered by status |
| `video_editor/cancel_job` | Cancel a job (kills ffmpeg/whisper) |

Heavy tools accept `background: true` and return a `job_id` to poll. Key environment: `MCP_VIDEO_OUTPUT_DIR` (container `/output`, host `outputs/video-editor`), `WHISPER_MODEL` (medium), `WHISPER_DEVICE` (`cpu` or `cuda`), `ENABLE_GPU` (NVENC). There is no ML speaker diarization. Details: [`tools/mcp/mcp_video_editor/README.md`](../../tools/mcp/mcp_video_editor/README.md).

## Blender MCP Server

Headless Blender (4.2+, image ships 4.5.1 LTS). Each call runs a Python script in `blender --background`; renders and bakes run as background jobs with progress and real cancellation.

```bash
docker compose --profile services run --rm -T mcp-blender mcp-blender --mode stdio   # as .mcp.json
docker compose --profile services up -d mcp-blender                                  # HTTP on 8017
curl http://localhost:8017/health
```

| Area | Tools |
|------|-------|
| Projects and status | `create_blender_project`, `list_projects`, `blender_status`, `analyze_scene`, `optimize_scene` |
| Scene building | `add_primitive_objects`, `add_advanced_primitives`, `create_curve`, `create_text_object`, `delete_objects`, `parent_objects`, `join_objects`, `create_armature`, `add_constraint` |
| Look development | `apply_material`, `add_texture`, `add_uv_map`, `setup_lighting`, `setup_world_environment`, `setup_camera`, `add_camera_track`, `setup_compositor` |
| Animation, simulation, procedural | `create_animation`, `add_modifier`, `setup_physics`, `bake_simulation` (job), `add_particle_system`, `add_smoke_simulation`, `create_geometry_nodes`, `quick_smoke`, `quick_liquid`, `quick_explode`, `quick_fur` |
| Rendering and jobs | `render_image` (job), `render_animation` (job), `batch_render` (job), `get_job_status` (`wait_seconds` long-polls up to 300 s), `get_job_result`, `cancel_job`, `list_jobs`, `import_model`, `export_scene` |

Job states: `QUEUED` -> `RUNNING` -> `COMPLETED` / `FAILED`, or `CANCELLED`. Jobs are kept in memory (lost on restart). Details: [`tools/mcp/mcp_blender/README.md`](../../tools/mcp/mcp_blender/README.md).

## Virtual Character MCP Server

Drives a virtual character (emotions, gestures, movement, avatar parameters, speech playback with ElevenLabs expression tags, timed sequences). The production backend controls a VRChat avatar over OSC; a `mock` backend runs offline.

```bash
mcp-virtual-character --mode standalone --port 8025       # recommended: natively on the VRChat PC
mcp-virtual-character --mode stdio
docker compose --profile services up -d mcp-virtual-character   # animation/movement only (no audio playback)
```

| Tool | Description |
|------|-------------|
| `set_backend` | Connect `mock` or `vrchat_remote` (replaces the current backend) |
| `disconnect_backend` | Disconnect, stop playback, release ports |
| `list_backends` | Available backends and which is active |
| `get_backend_status` | Connection, health and statistics |
| `get_avatar_state` | World/avatar id, current emotion/gesture, avatar parameters received from VRChat |
| `send_animation` | Emotion, gesture, movement and avatar parameters in one call |
| `send_vrcemote` | Direct VRCEmote value 0-8 (vrchat_remote only) |
| `execute_behavior` | `greet`, `dance`, `sit`, `stand`, `jump`, `crouch` |
| `reset` | Clear emotes and movement |
| `play_audio` | Play speech (file, URL or base64); expression tags set the emotion |
| `create_sequence` / `add_sequence_event` | Build a timed sequence |
| `play_sequence` / `pause_sequence` / `resume_sequence` / `stop_sequence` | Playback control |
| `get_sequence_status` | Position, executed/failed events, last error |
| `panic_reset` | Stop and discard sequences and reset the avatar |

Key environment: `VIRTUAL_CHARACTER_HOST` (127.0.0.1), `VIRTUAL_CHARACTER_OSC_IN` (9000), `VIRTUAL_CHARACTER_OSC_OUT` (9001; the compose service publishes `9001/udp` for VRChat's replies), `VIRTUAL_CHARACTER_EMOTE_TIMEOUT` (default 10 s, 0 = never), `VIRTUAL_CHARACTER_AUDIO_PLAYBACK` (`auto`/`local`/`none`). Details: [`tools/mcp/mcp_virtual_character/README.md`](../../tools/mcp/mcp_virtual_character/README.md).

## Desktop Control MCP Server

Desktop automation with native backends for Linux/X11 (pure-Rust `x11rb`, XTEST, RandR) and Windows (Win32 `SendInput`, per-monitor DPI awareness). macOS is not supported; Wayland only through XWayland.

```bash
mcp-desktop-control --mode stdio
mcp-desktop-control --mode standalone --port 8026
docker compose --profile desktop up -d mcp-desktop-control     # Linux; needs the host X socket
curl http://localhost:8026/health
```

| Area | Tools |
|------|-------|
| Status | `desktop_status` |
| Windows | `list_windows`, `get_active_window`, `focus_window`, `move_window`, `resize_window`, `minimize_window`, `maximize_window`, `restore_window`, `close_window` |
| Screens | `list_screens`, `get_screen_size` |
| Screenshots | `screenshot_screen`, `screenshot_window`, `screenshot_region` (optional inline image and downscaling) |
| Mouse | `get_mouse_position`, `move_mouse`, `click_mouse`, `drag_mouse`, `scroll_mouse` |
| Keyboard | `type_text`, `send_key`, `send_hotkey` |

| Platform | Backend |
|----------|---------|
| Linux | X11 via `x11rb` (XTEST input, RandR monitors, EWMH/ICCCM window management); no X11 command-line tools needed |
| Windows | Win32 (`SendInput`, DWM frame bounds, `PrintWindow` screenshots) |

Screenshots go to `DESKTOP_CONTROL_OUTPUT_DIR` (compose: `/output` = `outputs/desktop-control`). The HTTP transport has no authentication; prefer STDIO. Details: [`tools/mcp/mcp_desktop_control/README.md`](../../tools/mcp/mcp_desktop_control/README.md).

## GitHub Board MCP Server

A validated MCP front end for the [`board-manager`](../../tools/rust/board-manager/README.md) CLI: ready-work queue, claims, status, dependencies, approvals and stale-claim cleanup for multi-agent coordination.

```bash
docker compose --profile services run --rm -T mcp-github-board mcp-github-board --mode stdio   # as .mcp.json
mcp-github-board --mode standalone            # HTTP, default port 8022
mcp-github-board --mode stdio --read-only --timeout-secs 120
```

| Tool | Mutates | Description |
|------|---------|-------------|
| `query_ready_work` | no | Unblocked, unclaimed TODO issues (label filters, `approved_only`) |
| `claim_work` | yes | Claim an issue for an agent session |
| `renew_claim` | yes | Renew an active claim |
| `release_work` | yes | Release a claim (`completed`, `pr_created`, `blocked`, `abandoned`, `error`) |
| `update_status` | yes | Set Todo / In Progress / Blocked / Done / Abandoned |
| `add_blocker` | yes | Add a blocking dependency |
| `remove_blocker` | yes | Remove a blocking dependency |
| `mark_discovered_from` | yes | Record a parent-child relationship |
| `get_issue_details` | no | Status, assignee, labels and board metadata |
| `get_dependency_graph` | no | Blockers, blocked issues, parent and children |
| `list_agents` | no | Enabled agents for the board |
| `get_board_config` | no | Board configuration |
| `add_to_board` | yes | Add an issue to the board with status/priority/type/size |
| `check_approval` | no | Check whether an issue is approved for an agent |
| `find_approved_issues` | no | Find approved issues |
| `release_stale_claims` | yes | Janitor for stale claims (`dry_run` defaults to true) |
| `board_status` | no | Server version, read-only mode, board-manager path/version, token variables set |

Configuration:
- Token: `GITHUB_PROJECTS_TOKEN` (preferred; classic PAT with `project` and `repo` scopes), `GITHUB_TOKEN` or `GH_TOKEN`.
- Board: `ai-agents-board.yml` (found in the working directory or a parent), `BOARD_CONFIG_PATH`, `--board-config`, or `BOARD_PROJECT_NUMBER` / `BOARD_REPOSITORY` / `BOARD_OWNER`. `GITHUB_PROJECT_NUMBER` is not read by anything.
- Flags: `--read-only` (`GITHUB_BOARD_READ_ONLY`) registers only non-mutating tools; `--timeout-secs` (`GITHUB_BOARD_TIMEOUT_SECS`, default 300); `--board-manager` (`BOARD_MANAGER_PATH`).

Details: [`tools/mcp/mcp_github_board/README.md`](../../tools/mcp/mcp_github_board/README.md).

## AgentCore Memory MCP Server

Persistent agent memory backed by a self-hosted ChromaDB (0.4.x through 1.x). Despite the name, it does not use AWS Bedrock AgentCore. Embeddings are computed locally with all-MiniLM-L6-v2; content is sanitized for secrets before storage.

```bash
docker compose --profile memory-chromadb up -d chromadb
docker compose --profile memory run --rm -T mcp-agentcore-memory mcp-agentcore-memory --mode stdio   # as .mcp.json
mcp-agentcore-memory --mode standalone --port 8023
```

| Tool | Description |
|------|-------------|
| `store_event` | Store a short-term session event |
| `list_session_events` | List a session's events, newest first |
| `store_facts` | Store long-term facts in a namespace (deduplicated) |
| `search_memories` | Semantic search within one namespace |
| `list_memories` | Browse a namespace without a query |
| `delete_memories` | Delete facts by id |
| `reindex_namespace` | Re-embed every fact in a namespace |
| `list_namespaces` | Predefined namespaces, optionally with stored ones and counts |
| `memory_status` | Connectivity, ChromaDB version, embedder, cache stats |

Search results are cached in an in-process LRU/TTL cache (1000 entries, 5 minutes) that is invalidated on writes and deletes. Key environment: `CHROMADB_URL` or `CHROMADB_HOST`/`CHROMADB_PORT`, `CHROMADB_COLLECTION` (`agent_memory`), `MEMORY_EMBEDDER` (`fastembed` or `hash`). Details: [`tools/mcp/mcp_agentcore_memory/README.md`](../../tools/mcp/mcp_agentcore_memory/README.md).

## Reaction Search MCP Server

Semantic search over the anime reaction image catalog (all-MiniLM-L6-v2 via fastembed, plus BM25 keyword/tag boosts). If the embedding model is unavailable (offline, still downloading), searches fall back to keyword ranking and report `search_mode: "lexical"`.

```bash
docker compose --profile services run --rm -T mcp-reaction-search --mode stdio   # as .mcp.json
mcp-reaction-search --mode standalone --port 8024
```

| Tool | Description |
|------|-------------|
| `search_reactions` | Natural-language search (`query`, `limit`, `tags`, `exclude`, `min_similarity`) |
| `get_reaction` | Look up a reaction by id (with suggestions for unknown ids) |
| `list_reactions` | Compact catalog listing, optionally filtered by tags |
| `list_reaction_tags` | Tag counts, by frequency and category |
| `refresh_reactions` | Re-fetch the catalog from GitHub (and retry a failed model load) |
| `reaction_search_status` | Initialization, model and cache state |

```python
search_reactions(query="celebrating after fixing a bug", limit=3)
get_reaction(reaction_id="miku_typing")
```

Details: [`tools/mcp/mcp_reaction_search/README.md`](../../tools/mcp/mcp_reaction_search/README.md).

## Sprite Sheet MCP Server

Pixel art and sprite sheets from code: palette-indexed layers, drawing primitives, sprites and animations, undo for every edit, PNG/GIF/atlas export and versioned save/load.

```bash
docker compose --profile services run --rm -T mcp-sprite-sheet mcp-sprite-sheet --mode stdio --output /output   # as .mcp.json
mcp-sprite-sheet --mode standalone --port 8027
```

| Area | Tools |
|------|-------|
| Project (7) | `sprite_create_project`, `sprite_save_project`, `sprite_load_project`, `sprite_project_status`, `sprite_list_projects`, `sprite_delete_project`, `sprite_resize_canvas` |
| Layers (7) | `sprite_add_layer`, `sprite_remove_layer`, `sprite_update_layer`, `sprite_duplicate_layer`, `sprite_merge_layers`, `sprite_clear_layer`, `sprite_list_layers` |
| Drawing (6) | `sprite_set_pixels`, `sprite_draw_line`, `sprite_draw_rect`, `sprite_draw_ellipse`, `sprite_flood_fill`, `sprite_get_pixels` |
| Palette (3) | `sprite_set_palette`, `sprite_swap_palette`, `sprite_get_palette` |
| Sprites and animations (6) | `sprite_define_sprite`, `sprite_remove_sprite`, `sprite_list_sprites`, `sprite_define_animation`, `sprite_list_animations`, `sprite_remove_animation` |
| Transform (1) | `sprite_transform` |
| Render and export (5) | `sprite_render`, `sprite_render_sprite`, `sprite_render_animation_frames`, `sprite_export_gif`, `sprite_export_atlas` |
| Undo (1) | `sprite_undo` (undo/redo, 50 steps, covers every mutating tool) |
| Import and cleanup (2) | `sprite_import_image`, `sprite_trim_edges` |

Output directory: `--output` / `MCP_SPRITE_OUTPUT_DIR` (compose: `/output` = `outputs/mcp-sprites`). Details: [`tools/mcp/mcp_sprite_sheet/README.md`](../../tools/mcp/mcp_sprite_sheet/README.md).

## Memory Explorer MCP Server

Read-only process memory exploration for agent integration with legacy software. A native binary (documented exception to container-first): it must see host processes.

```bash
cd tools/mcp/mcp_memory_explorer && cargo build --release
./target/release/mcp-memory-explorer --mode stdio
./target/release/mcp-memory-explorer --mode standalone      # HTTP, default port 8028
```

| Tool | Description |
|------|-------------|
| `list_processes` | Running processes, optional name filter |
| `attach_process` | Attach read-only by name; `pid` picks one of several same-named processes |
| `detach_process` | Detach and clear watches and scan candidates |
| `get_modules` | Loaded modules with base/end addresses and sizes |
| `get_memory_regions` | Committed regions with protection, kind and owning module |
| `read_memory` | Read and decode a typed value |
| `dump_memory` | Hex + ASCII dump |
| `scan_pattern` | Signature scan with `??` wildcards |
| `find_value` | Search typed values (default scope: all writable memory) |
| `refine_value` | Narrow previous `find_value` matches (`equal`, `changed`, `unchanged`, `increased`, `decreased`) |
| `resolve_pointer` | Follow a pointer chain (Cheat Engine semantics) |
| `watch_address` / `read_watches` / `remove_watch` | Monitor addresses for changes |
| `get_status` | Attached process, bitness, watches, candidates, platform support |

Types: `bytes`, `int8`/`int16`/`int32`/`int64`, `uint8`/`uint16`/`uint32`/`uint64`, `float`, `double`, `string`, `wstring`, `pointer`, `vector3`, `vector4`, `matrix4x4`. Addresses accept module-relative forms such as `Game.exe+0x1234`.

| Platform | Support |
|----------|---------|
| Windows | Full (`ReadProcessMemory`, `VirtualQueryEx`, Toolhelp); opened with read-only access rights (not `PROCESS_ALL_ACCESS`), so same-user processes work without administrator rights |
| Linux | Full (`/proc/<pid>/mem`, `/proc/<pid>/maps`); requires ptrace access (same user with `kernel.yama.ptrace_scope=0`, or `CAP_SYS_PTRACE`) |
| macOS / other | `list_processes` only |

Details: [`tools/mcp/mcp_memory_explorer/README.md`](../../tools/mcp/mcp_memory_explorer/README.md).

## Gaea2 MCP Server (Port 8007)

Creates, validates, analyzes, repairs and (on Windows with Gaea2 installed) builds `.terrain` projects. Production runs on the dedicated Windows host at `192.168.0.152:8007`.

```bash
# Windows host (or automation/launchers/windows/start-gaea2-mcp.bat)
mcp-gaea2 --mode standalone --port 8007 --gaea-path "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"

# Container: everything except the build tools
docker compose --profile services up -d mcp-gaea2      # outputs in ./outputs/mcp-gaea2
curl http://localhost:8007/health
```

| Tool | Description |
|------|-------------|
| `create_gaea2_project` | Validate (auto-fix) and write a project; invalid workflows are rejected, never written |
| `create_gaea2_from_template` | Write a project from one of 11 templates, with property overrides |
| `validate_and_fix_workflow` | Validate and return the fixed workflow with errors, warnings and fixes |
| `suggest_gaea2_nodes` | Next-node suggestions |
| `optimize_gaea2_properties` | Tune build-cost properties (`performance`, `quality`, `balanced`) |
| `analyze_workflow_patterns` | Patterns, relative cost and quality issues |
| `list_gaea2_templates` | List templates (optionally with workflows) |
| `list_gaea2_nodes` | Node types by category, or ports/properties of one type |
| `list_gaea2_projects` | `.terrain` files, newest first |
| `download_gaea2_project` | Return a project file (max 25 MB) |
| `repair_gaea2_project` | Repair a `.terrain` file in place (dry run and backups) |
| `run_gaea2_project` | Build with `Gaea.Swarm.exe` (Windows host only) |
| `validate_gaea2_runtime` | 512px test build (Windows host only) |
| `analyze_execution_history` | Build history summary |
| `get_gaea2_status` | CLI availability, directories, counts |

Configuration: `--gaea-path` / `GAEA2_PATH`, `--output-dir` / `GAEA2_OUTPUT_DIR`, `--allowed-dirs` / `GAEA2_ALLOWED_DIRS` (client paths are confined to these), `--max-concurrent-builds`. Details: [`tools/mcp/mcp_gaea2/README.md`](../../tools/mcp/mcp_gaea2/README.md).

## AI Toolkit MCP Server (Port 8020)

LoRA training with ostris/ai-toolkit. Runs on the GPU machine next to AI Toolkit (compose service `mcp-ai-toolkit`, reached at `192.168.0.222:8020`).

```bash
AI_TOOLKIT_PATH=/ai-toolkit mcp-ai-toolkit --mode standalone --port 8020
mcp-ai-toolkit --mode client --port 8020 --backend-url http://192.168.0.222:8020   # local proxy
```

| Area | Tools |
|------|-------|
| Configs | `create_training_config`, `list_configs`, `get_config`, `validate_config`, `delete_config` |
| Datasets | `upload_dataset`, `list_datasets`, `get_dataset_info`, `delete_dataset` |
| Training | `start_training`, `get_training_status`, `get_training_logs`, `stop_training`, `list_training_jobs`, `get_training_info`, `get_training_samples` |
| Models | `list_exported_models`, `export_model`, `download_model` (whole file up to 100 MB, or chunked with `offset`/`chunk_size` and a final `sha256`), `delete_model` |
| Utilities | `get_system_stats`, `list_model_presets` |

Environment: `AI_TOOLKIT_PATH` (`/ai-toolkit`), `AI_TOOLKIT_CONFIGS_PATH` (default `$AI_TOOLKIT_PATH/config`; compose sets `/ai-toolkit/configs` to match its volume), `AI_TOOLKIT_DATASETS_PATH`, `AI_TOOLKIT_OUTPUTS_PATH`, `AI_TOOLKIT_PYTHON`, `HF_TOKEN`. The HTTP transport has no authentication; keep it on a trusted network. Details: [`tools/mcp/mcp_ai_toolkit/README.md`](../../tools/mcp/mcp_ai_toolkit/README.md).

## ComfyUI MCP Server (Port 8013)

Drives ComfyUI: text-to-image (FLUX / SDXL), img2img, upscaling, ControlNet, arbitrary API-format workflows, job tracking and LoRA file management. The binary is built into the ComfyUI image on the GPU host: MCP at `192.168.0.222:8013`, ComfyUI at `192.168.0.222:8188`.

```bash
mcp-comfyui --mode standalone --port 8013                                   # as in the container
COMFYUI_URL=http://192.168.0.222:8188 mcp-comfyui --mode stdio              # against the remote ComfyUI
```

| Tool | Description |
|------|-------------|
| `generate_image` | Run a template (`flux_default`, `sdxl_default`, `flux_with_lora`, `img2img`, `upscale`, `controlnet`) or custom workflow and wait for outputs |
| `execute_workflow` | Queue an API-format workflow as-is |
| `get_job_status` | Status and outputs of a job, optionally waiting |
| `cancel_job` | Dequeue or interrupt a job |
| `get_queue` | Running and pending prompt ids |
| `get_image` | Fetch an output/input/temp image as MCP image content |
| `upload_image` | Put a base64 image into ComfyUI's input directory |
| `list_workflows` | Built-in templates and what they need |
| `get_workflow` | A template as API-format JSON |
| `list_models` | Model files ComfyUI can load, by type |
| `get_object_info` | Node introspection |
| `get_system_info` | ComfyUI versions, RAM, GPUs |
| `upload_lora` | Write a base64 LoRA (and metadata) atomically |
| `list_loras` | LoRA files on disk |
| `download_lora` | Read a LoRA as base64 (size-capped) |

Environment: `COMFYUI_URL` (full base URL, takes precedence), or `COMFYUI_HOST` (`localhost`) and `COMFYUI_PORT` (`8188`); `COMFYUI_PATH` (`/comfyui`). The LoRA tools act on the filesystem of the machine running the server. Details: [`tools/mcp/mcp_comfyui/README.md`](../../tools/mcp/mcp_comfyui/README.md).

## BioForge MCP Server (Rust, simulated hardware)

MCP front end for the [BioForge](../../packages/bioforge/README.md) lab-automation platform: liquid handling, thermal control, gantry motion, plate imaging, protocol validation, human-in-the-loop gates and emergency stop. It runs against **simulated drivers** (every response includes `"simulated": true`), while safety enforcement, protocol validation, the e-stop latch, human gates and the audit log are real. It is not configured in `.mcp.json` or docker compose.

```bash
cd tools/mcp/mcp_bioforge && cargo build --release && cd ../../..
./tools/mcp/mcp_bioforge/target/release/mcp-bioforge --mode stdio --config-dir packages/bioforge/config
```

Tools (16): `dispense`, `aspirate`, `mix`, `move_to`, `home_gantry`, `set_temperature`, `heat_shock`, `incubate`, `capture_plate_image`, `count_colonies`, `list_protocols`, `load_protocol`, `get_system_status`, `request_human_action`, `get_human_action_status`, `emergency_stop`. CI: `automation-cli ci run bio-full`. Details: [`tools/mcp/mcp_bioforge/README.md`](../../tools/mcp/mcp_bioforge/README.md).

## Testing

Each crate has offline unit tests:

```bash
cd tools/mcp/<crate>
cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

`automation-cli ci run rust-full` runs these checks for every MCP crate. For a running HTTP server, `curl http://localhost:<port>/health` and `curl http://localhost:<port>/mcp/tools` are the quickest smoke tests.

## Configuration

The servers are configured in `.mcp.json` (essential set) and `.mcp.json.full` (all servers). Local servers run in STDIO mode through `docker compose run`:

```json
{
  "mcpServers": {
    "code-quality": {
      "command": "docker",
      "args": ["compose", "-f", "./docker-compose.yml", "--profile", "services",
               "run", "--rm", "-T", "mcp-code-quality", "mcp-code-quality", "--mode", "stdio"]
    },
    "gaea2": {
      "type": "http",
      "url": "http://192.168.0.152:8007/messages"
    }
  }
}
```

Remote servers (Gaea2, AI Toolkit, ComfyUI, and Virtual Character in `.mcp.json.full`) use HTTP with the `/messages` endpoint. For direct tool calls during development, use `POST /mcp/execute`. See the actual `.mcp.json` files for the precise configuration.

## Troubleshooting

### Port Already in Use

```bash
sudo lsof -i :8010                    # find the process using a port
docker compose down mcp-code-quality  # stop a specific container
```

### Container Permission Issues

```bash
./automation/setup/runner/fix-runner-permissions.sh
```

### Gaea2 Build Tools

`run_gaea2_project` and `validate_gaea2_runtime` need `--gaea-path` / `GAEA2_PATH` pointing at `Gaea.Swarm.exe` on a Windows host. The container reports "Gaea2 CLI not configured" for them.

## Development Notes

- Every server implements the `Tool` trait from `mcp-core` ([`tools/mcp/mcp_core_rust`](../../tools/mcp/mcp_core_rust/README.md)); `mcp-core` provides the STDIO/HTTP/REST transports.
- Servers can run standalone or via Docker Compose.
- Follow the container-first philosophy except where technically impossible (Memory Explorer, Desktop Control on Windows, Gaea2 builds).
