# Video Editor MCP Server (Rust)

> A Model Context Protocol server for intelligent automated video editing with transcript analysis, speaker detection, and automated editing decisions, built in Rust with ffmpeg for video processing.

## Overview

This MCP server provides:
- Video analysis with transcription and speaker identification
- Automatic edit decision list (EDL) generation based on content
- Video rendering with transitions and effects
- Clip extraction based on keywords, speakers, or time ranges
- Automatic caption generation and styling
- Job tracking for long-running operations

**Note**: This server requires ffmpeg and optionally Whisper CLI for full functionality.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-video-editor --mode standalone --port 8019

# Run in STDIO mode (for Claude Code)
./target/release/mcp-video-editor --mode stdio

# Test health
curl http://localhost:8019/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `video_editor/analyze` | Analyze video content without rendering | `video_inputs` (required), `analysis_options` |
| `video_editor/create_edit` | Generate an EDL based on rules | `video_inputs` (required), `editing_rules`, `speaker_mapping` |
| `video_editor/render` | Execute video rendering | `video_inputs` (required), `edit_decision_list`, `output_settings`, `render_options` |
| `video_editor/extract_clips` | Create short clips from video | `video_input` (required), `extraction_criteria`, `output_dir` |
| `video_editor/add_captions` | Add styled captions to video | `video_input` (required), `caption_style`, `languages`, `output_path` |
| `video_editor/get_job_status` | Get status of a rendering job | `job_id` (required) |

### Example Usage

```bash
# Analyze a video
curl -X POST http://localhost:8019/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "video_editor/analyze",
    "arguments": {
      "video_inputs": ["/path/to/video.mp4"],
      "analysis_options": {
        "transcribe": true,
        "identify_speakers": true,
        "detect_scenes": true
      }
    }
  }'

# Create an edit
curl -X POST http://localhost:8019/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "video_editor/create_edit",
    "arguments": {
      "video_inputs": ["/path/to/video1.mp4", "/path/to/video2.mp4"],
      "editing_rules": {
        "switch_on_speaker": true,
        "remove_silence": true
      }
    }
  }'
```

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8019]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_VIDEO_OUTPUT_DIR` | `/app/output` | Output directory for rendered videos |
| `MCP_VIDEO_CACHE_DIR` | `~/.cache/mcp-video-editor` | Cache directory for transcripts |
| `MCP_VIDEO_TEMP_DIR` | `/tmp/video_editor` | Temporary file directory |
| `WHISPER_MODEL` | `medium` | Whisper model size (tiny, base, small, medium, large) |
| `WHISPER_DEVICE` | `cpu` | Device for Whisper (cpu, cuda) |
| `TRANSITION_DURATION` | `0.5` | Default transition duration in seconds |
| `SILENCE_THRESHOLD` | `2.0` | Minimum silence duration to detect |
| `ENABLE_GPU` | `true` | Enable GPU acceleration for encoding |
| `MAX_PARALLEL_JOBS` | `2` | Maximum concurrent render jobs |

### Cache Location

- Linux: `~/.cache/mcp-video-editor/`
- macOS: `~/Library/Caches/mcp-video-editor/`
- Windows: `%LOCALAPPDATA%\mcp-video-editor\`

Cache files:
- `transcripts/` - Cached transcription results
- `diarization/` - Cached speaker diarization results

## Transport Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **standalone** | Full MCP server with HTTP transport | Production, Docker |
| **stdio** | STDIO transport for direct integration | Claude Code, local MCP clients |
| **server** | REST API only (no MCP protocol) | Microservices |
| **client** | MCP proxy to REST backend | Horizontal scaling |

## Dependencies

### Required

- **ffmpeg** - Video/audio processing (must be in PATH)
- **ffprobe** - Media analysis (comes with ffmpeg)

### Optional

- **whisper** - OpenAI Whisper CLI for transcription
  - Install: `pip install openai-whisper`

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "video-editor": {
      "command": "mcp-video-editor",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "video-editor": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-video-editor", "mcp-video-editor", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_video_editor

# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run tests
cargo test

# Run clippy
cargo clippy -- -D warnings

# Format code
cargo fmt
```

## Project Structure

```
tools/mcp/mcp_video_editor/
|-- Cargo.toml          # Package configuration
|-- Cargo.lock          # Dependency lock file
|-- README.md           # This file
+-- src/
    |-- main.rs         # CLI entry point
    |-- server.rs       # MCP tools implementation
    |-- types.rs        # Data types
    |-- jobs.rs         # Job management
    |-- audio.rs        # Audio processing (transcription, diarization)
    +-- video.rs        # Video processing (editing, rendering)
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Testing

```bash
# Run unit tests
cargo test

# Test with output
cargo test -- --nocapture

# Test HTTP endpoints (after starting server)
curl http://localhost:8019/health
curl http://localhost:8019/mcp/tools
```

## Architecture

### Video Processing Pipeline

1. **Analysis** - Extract metadata, transcribe audio, detect scenes
2. **EDL Generation** - Create edit decisions based on content and rules
3. **Rendering** - Execute edits using ffmpeg
4. **Post-processing** - Add captions, effects, transitions

### External Tool Integration

The server uses ffmpeg for all video processing operations:
- `ffmpeg` - Video editing, encoding, effects
- `ffprobe` - Media analysis and metadata extraction
- `whisper` (optional) - Speech-to-text transcription

### Job Management

Long-running operations (rendering) are tracked with job IDs:
- Jobs have status: pending, running, completed, failed
- Progress updates include stage and percentage
- Results are stored with the job for retrieval

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "ffmpeg not found" | ffmpeg not installed | Install ffmpeg and ensure it's in PATH |
| Transcription fails | Whisper not available | Install whisper CLI or disable transcription |
| Slow rendering | No GPU acceleration | Enable GPU or reduce resolution |
| "Job not found" | Job expired | Jobs are kept in memory; check before restart |

## Performance

| Operation | Time (estimate) |
|-----------|-----------------|
| Server startup | ~50ms |
| Video analysis (1 min video) | ~30s (with transcription) |
| Scene detection | ~5s per minute of video |
| Rendering | Depends on source length and settings |

## License

Part of the template-repo project. See repository LICENSE file.
