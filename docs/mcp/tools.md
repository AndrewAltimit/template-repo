# MCP Tools Documentation

This document gives an overview of the tools exposed by this project's MCP (Model Context Protocol) servers, with examples for the most commonly used ones.

**Each server's `tools/mcp/<crate>/README.md` is the source of truth** for tool parameters, defaults and limits. This page summarizes and links; see [MCP Servers Documentation](servers.md) for how to start each server.

## Container-First Design

Most MCP servers run in Docker containers as part of this project's philosophy:

- **Zero local dependencies** - just Docker
- **Consistent execution** - same results on any Linux system
- **Easy deployment** - works identically on self-hosted runners
- **Single maintainer friendly** - no complex setup or coordination needed
- **User permission handling** - containers run as the current user to avoid permission issues

**Exceptions**: Memory Explorer (must see host processes), Desktop Control on Windows, and Gaea2 builds (Windows host with Gaea2) run as native binaries.

## Table of Contents

- [Overview](#overview)
- [Core Tools](#core-tools)
- [AI Integration Tools](#ai-integration-tools)
- [Content Creation Tools](#content-creation-tools)
- [Coordination and Memory Tools](#coordination-and-memory-tools)
- [Remote Services](#remote-services)
- [Custom Tool Development](#custom-tool-development)

## Overview

MCP tools are functions executed by the MCP servers. Every server is a Rust binary built on [`mcp-core`](../../tools/mcp/mcp_core_rust/README.md) and is reachable through the MCP protocol (STDIO or HTTP) or, in HTTP mode, a simple REST API.

### Tool Execution

#### 1. MCP Protocol Interface (`/messages` endpoint)

Used by Claude Code and other MCP clients (JSON-RPC). This is the endpoint configured in `.mcp.json` for HTTP servers:

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
      "arguments": {"arg1": "value1"}
    },
    "id": 1
  }'
```

#### 2. Direct HTTP API (`/mcp/execute` endpoint)

For direct REST tool execution without MCP protocol overhead. Useful for testing:

```bash
curl -X POST http://localhost:<port>/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "tool_name", "arguments": {"arg1": "value1"}}'
```

**STDIO Mode:** servers launched by `.mcp.json` through `docker compose run ... --mode stdio` communicate over stdin/stdout and expose no HTTP port.

### Quick Reference Table

| Server | Primary Mode | HTTP Port | Tools | Description |
|--------|--------------|-----------|-------|-------------|
| Code Quality | STDIO (Docker) | 8010 | 10 | Formatting, linting, type checks, tests, security scans |
| Content Creation | STDIO (Docker) | 8011 | 5 | LaTeX, TikZ, PDF previews, Manim |
| ~~Gemini~~ | Disabled | 8006 | 4 | AI consultation (disabled) |
| OpenCode | STDIO (Docker) | 8014 | 4 | Code assistance via OpenRouter |
| Crush | STDIO (Docker) | 8015 | 4 | Code generation via the Crush CLI |
| Meme Generator | STDIO (Docker) | 8016 | 6 | Meme creation with visual feedback |
| Blender | STDIO (Docker) | 8017 | 42 | 3D content creation, rendering, physics |
| ElevenLabs Speech | STDIO (Docker) | 8018 | 7 | Text-to-speech and sound effects |
| Video Editor | STDIO (Docker) | 8019 | 9 | Automated video editing |
| GitHub Board | STDIO (Docker) | 8022 | 17 | Projects v2 work queue and agent coordination |
| AgentCore Memory | STDIO (Docker) | 8023 | 9 | ChromaDB-backed agent memory |
| Reaction Search | STDIO (Docker) | 8024 | 6 | Reaction image search |
| Virtual Character | HTTP (VRChat host) | 8025 | 18 | VRChat avatar control |
| Desktop Control | Native | 8026 | 23 | Desktop automation (X11 / Windows) |
| Sprite Sheet | STDIO (Docker) | 8027 | 38 | Pixel art and sprite sheets |
| Memory Explorer | Native (STDIO) | 8028 | 15 | Read-only process memory exploration |
| Gaea2 | HTTP (Remote) | 8007 | 15 | Terrain generation (`192.168.0.152`) |
| AI Toolkit | HTTP (Remote) | 8020 | 22 | LoRA training (`192.168.0.222`) |
| ComfyUI | HTTP (Remote) | 8013 | 15 | Image generation (`192.168.0.222`) |
| BioForge | Native (STDIO) | 8030 | 16 | Lab automation on simulated hardware |

**Note**: HTTP ports are only used when a server runs in HTTP mode (`--mode standalone`), e.g. `docker compose up` for development or the remote servers.

## Core Tools

### Code Quality Tools

Full reference: [`tools/mcp/mcp_code_quality/README.md`](../../tools/mcp/mcp_code_quality/README.md).

| Tool | Description |
|------|-------------|
| `format_check` | Check formatting (`language`: python, javascript, typescript, go, rust; Python defaults to `ruff format`, `formatter: "black"` available) |
| `autoformat` | Format files in place |
| `lint` | Static analysis (`linter`: ruff, flake8, eslint, golint, clippy) |
| `type_check` | `ty check` |
| `run_tests` | pytest |
| `security_scan` | bandit |
| `audit_dependencies` | pip-audit |
| `check_markdown_links` | Markdown link checker |
| `get_status` | Configuration and available external tools |
| `get_audit_log` | Recent audit log entries |

**Example:**
```json
{"tool": "lint", "arguments": {"path": "/app/tools/cli", "linter": "ruff"}}
```

**Response:**
```json
{
  "success": true,
  "passed": false,
  "command": "ruff check --no-cache --output-format concise /app/tools/cli",
  "issues": ["tools/cli/x.py:1:8: F401 [*] `os` imported but unused"],
  "issue_count": 1,
  "returncode": 1,
  "duration_ms": 22
}
```

`success` means the tool ran; whether the code passed is reported in `passed` (or `formatted` for `format_check`).

### Running CI/CD Pipeline

While not an MCP tool, the full CI/CD pipeline can be executed via `automation-cli`:

```bash
automation-cli ci run full        # Complete Python pipeline
automation-cli ci run rust-full   # All Rust checks (includes every MCP server crate)
automation-cli ci run format
automation-cli ci run lint-full
automation-cli ci run test
```

## AI Integration Tools

### ~~Gemini Tools~~ (DISABLED)

> **DISABLED**: Google updated its AI principles (Feb 2026) to allow mass surveillance and autonomous weapons use cases. Gemini integrations are disabled; use Anthropic models (Claude) instead.

Tools: `consult_gemini`, `clear_gemini_history`, `gemini_status`, `toggle_gemini_auto_consult`. See `tools/mcp/mcp_gemini/README.md`.

### OpenCode Tools

Full reference: [`tools/mcp/mcp_opencode/README.md`](../../tools/mcp/mcp_opencode/README.md).

| Tool | Description |
|------|-------------|
| `consult_opencode` | Ask the OpenRouter model (`query`, `context`, `mode`, `model`, `temperature`, `max_tokens`, `force`) |
| `opencode_status` | Status, statistics, effective configuration |
| `clear_opencode_history` | Clear conversation history |
| `toggle_opencode_auto_consult` | Set or flip the auto-consult flag |

Modes: `quick` (default), `generate`, `refactor`, `review`, `explain`. The default model is `qwen/qwen3.7-max` (`OPENCODE_MODEL`); `model` overrides it per call. `comparison_mode` is accepted for backward compatibility but has no effect.

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

Full reference: [`tools/mcp/mcp_crush/README.md`](../../tools/mcp/mcp_crush/README.md).

| Tool | Description |
|------|-------------|
| `consult_crush` | Run `crush run` (`query`, `context`, `mode`, `model`, `force`) |
| `crush_status` | Status, statistics, configuration and resolved execution mode |
| `clear_crush_history` | Clear conversation history |
| `toggle_crush_auto_consult` | Set or flip the auto-consult flag |

Modes: `quick` (default), `generate`, `explain`, `convert` (`context` is the required target language). `comparison_mode` is accepted but has no effect.

```json
{
  "tool": "consult_crush",
  "arguments": {"query": "def add(a, b): return a + b", "mode": "convert", "context": "TypeScript"}
}
```

## Content Creation Tools

### Content Creation (LaTeX, TikZ, Manim)

Full reference: [`tools/mcp/mcp_content_creation/README.md`](../../tools/mcp/mcp_content_creation/README.md).

| Tool | Description |
|------|-------------|
| `compile_latex` | Compile inline `content` or a project `input_path` (exactly one) to `pdf`/`dvi`/`ps` (`output_format`, alias `format`); `template`, `preview_pages`, `visual_feedback` |
| `render_tikz` | Render TikZ to `pdf`/`png`/`svg`; `tikz_libraries`, `packages`, `dpi` |
| `preview_pdf` | Render pages of an existing PDF to PNG |
| `create_manim_animation` | Render a Manim scene to `mp4`/`gif`/`webm`/`png`; `quality`: `low`, `medium`, `high`, `production`, `fourk`; `preview: true` renders only the last frame as PNG |
| `content_creation_status` | Configuration and installed external tools |

```json
{
  "tool": "compile_latex",
  "arguments": {"content": "Euler: $e^{i\\pi}+1=0$", "template": "article", "preview_pages": "1"}
}
```

### Meme Generator Tools

Full reference: [`tools/mcp/mcp_meme_generator/README.md`](../../tools/mcp/mcp_meme_generator/README.md).

| Tool | Description |
|------|-------------|
| `generate_meme` | Render captions on a template, save, return a preview, optionally upload |
| `list_meme_templates` | List templates and their text areas |
| `get_meme_template_info` | Template config, usage rules and an example call |
| `meme_generator_status` | Template load errors, font, directories, upload settings |
| `upload_meme` | Upload an existing meme from the output directory |
| `reload_meme_templates` | Re-read templates and font |

```json
{
  "tool": "generate_meme",
  "arguments": {
    "template": "ol_reliable",
    "texts": {"top": "When the code won't compile", "bottom": "print('hello world')"},
    "upload": false
  }
}
```

### ElevenLabs Speech Tools

Full reference: [`tools/mcp/mcp_elevenlabs_speech/README.md`](../../tools/mcp/mcp_elevenlabs_speech/README.md).

| Tool | Description |
|------|-------------|
| `synthesize_speech` | Text-to-speech (audio tags such as `[laughs]` with `eleven_v3`) |
| `generate_sound_effect` | Sound effect from a prompt (0.5-30 s) |
| `list_voices` | Voices on the account |
| `get_user_subscription` | Tier and character usage |
| `get_models` | Available models |
| `list_presets` | Voice-settings presets |
| `clear_cache` | Delete generated audio files |

### Video Editor Tools

Full reference: [`tools/mcp/mcp_video_editor/README.md`](../../tools/mcp/mcp_video_editor/README.md).

| Tool | Description |
|------|-------------|
| `video_editor/analyze` | Media info, transcript, loudness/silences/peaks, scenes, speakers, highlights |
| `video_editor/create_edit` | Generate and save an edit decision list (EDL) |
| `video_editor/render` | Render an EDL with transitions, zoom and PiP |
| `video_editor/extract_clips` | Cut clips by time range and/or transcript keyword |
| `video_editor/add_captions` | Transcribe and burn in or mux captions |
| `video_editor/get_video_info` | ffprobe summary |
| `video_editor/get_job_status` | Job status, progress and result |
| `video_editor/list_jobs` | Recent jobs |
| `video_editor/cancel_job` | Cancel a job |

```json
{
  "tool": "video_editor/extract_clips",
  "arguments": {
    "video_input": "/data/talk.mp4",
    "extraction_criteria": {"time_ranges": [[30, 45]], "keywords": ["pricing"], "padding": 0.5},
    "background": true
  }
}
```

Transcription requires the Whisper CLI (bake it into the image with `VIDEO_EDITOR_WHISPER=true docker compose build mcp-video-editor`). Speaker switching is energy-based (one time-synced video per speaker); there is no ML diarization.

### Blender Tools

Full reference: [`tools/mcp/mcp_blender/README.md`](../../tools/mcp/mcp_blender/README.md).

- **Projects and status**: `create_blender_project`, `list_projects`, `blender_status`, `analyze_scene`, `optimize_scene`
- **Scene building**: `add_primitive_objects`, `add_advanced_primitives`, `create_curve`, `create_text_object`, `delete_objects`, `parent_objects`, `join_objects`, `create_armature`, `add_constraint`
- **Look development**: `apply_material`, `add_texture`, `add_uv_map`, `setup_lighting`, `setup_world_environment`, `setup_camera`, `add_camera_track`, `setup_compositor`
- **Animation, simulation, procedural**: `create_animation`, `add_modifier`, `setup_physics`, `bake_simulation`, `add_particle_system`, `add_smoke_simulation`, `create_geometry_nodes`, `quick_smoke`, `quick_liquid`, `quick_explode`, `quick_fur`
- **Rendering and jobs**: `render_image`, `render_animation`, `batch_render`, `get_job_status`, `get_job_result`, `cancel_job`, `list_jobs`, `import_model`, `export_scene`

Renders and bakes run as background jobs (`QUEUED` -> `RUNNING` -> `COMPLETED`/`FAILED`/`CANCELLED`); `get_job_status` with `wait_seconds` long-polls.

### Sprite Sheet Tools

Full reference: [`tools/mcp/mcp_sprite_sheet/README.md`](../../tools/mcp/mcp_sprite_sheet/README.md). 38 `sprite_*` tools covering projects, layers, drawing, palettes, sprites and animations, transforms, rendering, GIF and texture-atlas export, undo/redo and image import.

## Coordination and Memory Tools

### GitHub Board Tools

Full reference: [`tools/mcp/mcp_github_board/README.md`](../../tools/mcp/mcp_github_board/README.md).

| Tool | Description |
|------|-------------|
| `query_ready_work` | Unblocked, unclaimed TODO issues |
| `claim_work` / `renew_claim` / `release_work` | Claim lifecycle for an agent session |
| `update_status` | Set the board status |
| `add_blocker` / `remove_blocker` | Manage blocking dependencies |
| `mark_discovered_from` | Parent-child relationship |
| `get_issue_details` / `get_dependency_graph` | Issue and dependency information |
| `list_agents` / `get_board_config` | Board configuration |
| `add_to_board` | Add an issue to the board |
| `check_approval` / `find_approved_issues` | Approval checks |
| `release_stale_claims` | Stale-claim janitor (dry run by default) |
| `board_status` | Server and board-manager status |

```json
{"tool": "claim_work", "arguments": {"issue_number": 42, "agent_name": "claude", "session_id": "run-8841"}}
```

The board is configured by `ai-agents-board.yml` (or `BOARD_PROJECT_NUMBER`); `--read-only` hides the mutating tools.

### AgentCore Memory Tools

Full reference: [`tools/mcp/mcp_agentcore_memory/README.md`](../../tools/mcp/mcp_agentcore_memory/README.md). ChromaDB-backed; tools: `store_event`, `list_session_events`, `store_facts`, `search_memories`, `list_memories`, `delete_memories`, `reindex_namespace`, `list_namespaces`, `memory_status`.

### Reaction Search Tools

Full reference: [`tools/mcp/mcp_reaction_search/README.md`](../../tools/mcp/mcp_reaction_search/README.md). Tools: `search_reactions`, `get_reaction`, `list_reactions`, `list_reaction_tags`, `refresh_reactions`, `reaction_search_status`. Falls back to keyword search when the embedding model is unavailable.

```json
{"tool": "search_reactions", "arguments": {"query": "celebrating after fixing a bug", "limit": 3}}
```

## Remote Services

### Gaea2 Tools (Port 8007)

Full reference: [`tools/mcp/mcp_gaea2/README.md`](../../tools/mcp/mcp_gaea2/README.md). Runs on the Windows host at `192.168.0.152:8007`.

- **Projects**: `create_gaea2_project`, `create_gaea2_from_template`, `list_gaea2_projects`, `download_gaea2_project`, `repair_gaea2_project`
- **Validation and analysis**: `validate_and_fix_workflow`, `analyze_workflow_patterns`, `optimize_gaea2_properties`, `suggest_gaea2_nodes`
- **Reference**: `list_gaea2_templates` (11 templates), `list_gaea2_nodes`, `get_gaea2_status`
- **Builds (Windows host with Gaea2)**: `run_gaea2_project`, `validate_gaea2_runtime`, `analyze_execution_history`

`create_*` tools validate first and refuse to write an invalid workflow.

### Virtual Character Tools (Port 8025)

Full reference: [`tools/mcp/mcp_virtual_character/README.md`](../../tools/mcp/mcp_virtual_character/README.md). Best run natively on the VRChat PC.

- **Backends**: `set_backend` (`mock`, `vrchat_remote`), `disconnect_backend`, `list_backends`, `get_backend_status`, `get_avatar_state`
- **Animation**: `send_animation` (emotion, gesture, movement, avatar parameters), `send_vrcemote` (0-8), `execute_behavior`, `reset`
- **Audio**: `play_audio` (ElevenLabs expression tags set the avatar's emotion)
- **Sequences**: `create_sequence`, `add_sequence_event`, `play_sequence`, `pause_sequence`, `resume_sequence`, `stop_sequence`, `get_sequence_status`, `panic_reset`

```json
{"tool": "send_animation", "arguments": {"gesture": "wave", "emotion": "happy"}}
```

### Desktop Control Tools (Port 8026)

Full reference: [`tools/mcp/mcp_desktop_control/README.md`](../../tools/mcp/mcp_desktop_control/README.md). 23 tools: `desktop_status`; windows (`list_windows`, `get_active_window`, `focus_window`, `move_window`, `resize_window`, `minimize_window`, `maximize_window`, `restore_window`, `close_window`); screens (`list_screens`, `get_screen_size`); screenshots (`screenshot_screen`, `screenshot_window`, `screenshot_region`); mouse (`get_mouse_position`, `move_mouse`, `click_mouse`, `drag_mouse`, `scroll_mouse`); keyboard (`type_text`, `send_key`, `send_hotkey`).

### Memory Explorer Tools

Full reference: [`tools/mcp/mcp_memory_explorer/README.md`](../../tools/mcp/mcp_memory_explorer/README.md). Read-only, Windows and Linux: `list_processes`, `attach_process`, `detach_process`, `get_modules`, `get_memory_regions`, `read_memory`, `dump_memory`, `scan_pattern`, `find_value`, `refine_value`, `resolve_pointer`, `watch_address`, `read_watches`, `remove_watch`, `get_status`.

### ComfyUI Tools (Port 8013)

Full reference: [`tools/mcp/mcp_comfyui/README.md`](../../tools/mcp/mcp_comfyui/README.md). MCP at `192.168.0.222:8013`, ComfyUI at `192.168.0.222:8188`.

- **Generation**: `generate_image` (templates `flux_default`, `sdxl_default`, `flux_with_lora`, `img2img`, `upscale`, `controlnet`, or a custom API-format workflow), `execute_workflow`
- **Jobs**: `get_job_status`, `cancel_job`, `get_queue`
- **Images**: `get_image`, `upload_image`
- **Discovery**: `list_workflows`, `get_workflow`, `list_models`, `get_object_info`, `get_system_info`
- **LoRA files**: `upload_lora`, `list_loras`, `download_lora`

**Configuration:**
```bash
COMFYUI_URL=http://192.168.0.222:8188   # or COMFYUI_HOST / COMFYUI_PORT (defaults localhost / 8188)
```

### AI Toolkit Tools (Port 8020)

Full reference: [`tools/mcp/mcp_ai_toolkit/README.md`](../../tools/mcp/mcp_ai_toolkit/README.md). Runs next to AI Toolkit on `192.168.0.222:8020`.

- **Configs**: `create_training_config`, `list_configs`, `get_config`, `validate_config`, `delete_config`
- **Datasets**: `upload_dataset`, `list_datasets`, `get_dataset_info`, `delete_dataset`
- **Training**: `start_training`, `get_training_status`, `get_training_logs`, `stop_training`, `list_training_jobs`, `get_training_info`, `get_training_samples`
- **Models**: `list_exported_models`, `export_model`, `download_model` (chunked via `offset`/`chunk_size`), `delete_model`
- **Utilities**: `get_system_stats`, `list_model_presets`

**Client configuration:**
```json
{"mcpServers": {"ai-toolkit": {"type": "http", "url": "http://192.168.0.222:8020/messages"}}}
```

### BioForge Tools

Full reference: [`tools/mcp/mcp_bioforge/README.md`](../../tools/mcp/mcp_bioforge/README.md). Simulated hardware; not configured in `.mcp.json`. Tools: `dispense`, `aspirate`, `mix`, `move_to`, `home_gantry`, `set_temperature`, `heat_shock`, `incubate`, `capture_plate_image`, `count_colonies`, `list_protocols`, `load_protocol`, `get_system_status`, `request_human_action`, `get_human_action_status`, `emergency_stop`.

## Custom Tool Development

New servers are Rust crates built on `mcp-core`. The [mcp_core_rust README](../../tools/mcp/mcp_core_rust/README.md) documents the `Tool` trait, typed-argument and schema helpers, error mapping and the `mcp-testing` crate. In short:

1. Create `tools/mcp/mcp_<name>/` with a `Cargo.toml` depending on `mcp-core` (path `../mcp_core_rust/crates/mcp-core`).
2. Implement `Tool` for each tool and register them with the server builder in `main.rs`, flattening `MCPServerArgs` for the standard CLI.
3. Add a README (tools, parameters, configuration, limitations), a Dockerfile and a docker compose service, and an entry in `.mcp.json` / `.mcp.json.full`.
4. Pick an unused port (see the table above) and pass it with `--port`.
5. `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test`.

### Tool Guidelines

1. **Errors**: reject malformed arguments with `Invalid params`; return runtime failures as `isError` results with a readable message. Never write to stdout from a tool in STDIO mode.
2. **Input validation**: parse arguments into typed structs; confine file paths to configured directories; bound sizes, counts and timeouts.
3. **Subprocesses**: no shell, argv only, stdin closed, timeouts that kill the child, capped output.
4. **Output**: return a consistent JSON object with `success` and useful metadata.

## API Reference

### Endpoints (`--mode standalone`)

- `POST /messages` (also `/mcp`, `/mcp/rpc`) - MCP protocol endpoint (JSON-RPC)
- `DELETE /messages` - Terminate the session in `Mcp-Session-Id`
- `GET /health` - Health check
- `GET /mcp/tools` - List available tools
- `POST /mcp/execute` - Execute a tool (direct API)
- `GET /.well-known/mcp` - MCP discovery

`--mode server` (REST only) serves `GET /health`, `GET /tools`, `POST /tools/{name}/call` and `POST /execute` instead.

### Errors

| Situation | Result |
|-----------|--------|
| Unknown tool, missing/mistyped arguments | JSON-RPC `-32602 Invalid params` |
| Unknown method | `-32601 Method not found` |
| Tool failure, panic or timeout | Result with `isError: true` and the error text |

## Troubleshooting

1. **Tool not found**: check the tool name against the server's README (`GET /mcp/tools` lists them), and that the server is configured in `.mcp.json`.
2. **Timeout errors**: most servers have a configurable per-call timeout (see the crate README); long jobs (Blender, video editor, AI Toolkit) run in the background and are polled.
3. **Permission errors**: check Docker volume mounts and output directories (`outputs/...`); many containers mount the repository read-only at `/app`.

```bash
docker compose logs -f <service>              # view logs
RUST_LOG=debug mcp-<name> --mode standalone   # verbose logging (stderr)
```
