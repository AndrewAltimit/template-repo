# Virtual Character MCP Server (Rust)

> A Model Context Protocol server for controlling virtual characters via VRChat OSC and other backends, providing emotion expression, gesture control, and multimedia performance capabilities.

## Overview

This MCP server provides:
- VRChat OSC integration for avatar control (emotions, gestures, movement)
- VRCEmote system (gesture wheel positions 0-8) for predefined animations
- Backend abstraction supporting mock (testing), VRChat Remote, and future platforms
- Audio playback with ElevenLabs expression tag detection
- Event sequencing for choreographed performances
- PAD (Pleasure/Arousal/Dominance) emotion model for smooth interpolation

**Note**: This server was migrated from Python to Rust as part of the mcp-core-rust framework migration.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-virtual-character --mode standalone --port 8025

# Run in STDIO mode (for Claude Code)
./target/release/mcp-virtual-character --mode stdio

# Test health
curl http://localhost:8025/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `set_backend` | Connect to a backend | `backend_type`, `host`, `osc_in_port`, `osc_out_port`, `mcp_port` |
| `send_animation` | Send animation data (emotion/gesture) | `emotion`, `gesture`, `emotion_intensity`, `blendshapes` |
| `send_vrcemote` | Send VRCEmote value (0-8) | `emote` (required) |
| `execute_behavior` | Execute platform behavior | `behavior` (required), `parameters` |
| `reset` | Reset to neutral state | None |
| `get_backend_status` | Get current backend status | None |
| `list_backends` | List available backends | None |
| `play_audio` | Play audio with expression detection | `audio_data`, `format`, `detect_expressions` |
| `create_sequence` | Create an event sequence | `sequence_id` (required), `name`, `description` |
| `add_sequence_event` | Add event to sequence | `sequence_id`, `event_type`, `timestamp`, `data` |
| `play_sequence` | Start playing a sequence | `sequence_id` (required) |
| `pause_sequence` | Pause sequence playback | `sequence_id` (required) |
| `resume_sequence` | Resume paused sequence | `sequence_id` (required) |
| `stop_sequence` | Stop and reset sequence | `sequence_id` (required) |
| `get_sequence_status` | Get sequence playback status | `sequence_id` (required) |
| `panic_reset` | Emergency reset all states | None |

### Emotion Types

| Emotion | VRCEmote | Description |
|---------|----------|-------------|
| `neutral` | 0 (None) | Default calm state |
| `happy` | 4 (Cheer) | Joy, excitement |
| `sad` | 7 (Sadness) | Sorrow, disappointment |
| `angry` | 8 (Die) | Frustration, anger |
| `surprised` | 3 (Point) | Shock, amazement |
| `fearful` | 2 (Clap) | Anxiety, fear |
| `disgusted` | 6 (Backflip) | Revulsion |

### Gesture Types

| Gesture | VRCEmote | Description |
|---------|----------|-------------|
| `wave` | 1 (Wave) | Greeting wave |
| `point` | 3 (Point) | Pointing gesture |
| `clap` | 2 (Clap) | Applause |
| `dance` | 5 (Dance) | Dancing animation |
| `bow` | 7 (Sadness) | Respectful bow |
| `thumbs_up` | 4 (Cheer) | Approval gesture |

## VRCEmote System

The VRCEmote system uses integer values (0-8) corresponding to VRChat gesture wheel positions:

| Value | Name | Typical Use |
|-------|------|-------------|
| 0 | None | Reset to default |
| 1 | Wave | Greetings |
| 2 | Clap | Applause, fear |
| 3 | Point | Direction, surprise |
| 4 | Cheer | Happiness, approval |
| 5 | Dance | Celebration |
| 6 | Backflip | Excitement, disgust |
| 7 | Sadness | Sorrow, bow |
| 8 | Die | Anger, dramatic |

### Toggle Behavior

VRCEmotes use toggle behavior: sending the same value twice turns it off. The server handles this automatically with a configurable timeout (default: 3 seconds) for gesture-based emotes.

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8025]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Default VRChat Configuration

- **VRChat Host**: 127.0.0.1
- **VRChat Receive Port**: 9000 (OSC messages to VRChat)
- **VRChat Send Port**: 9001 (OSC messages from VRChat)
- **Emote Timeout**: 3 seconds

## Transport Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **standalone** | Full MCP server with HTTP transport | Production, Docker |
| **stdio** | STDIO transport for direct integration | Claude Code, local MCP clients |
| **server** | REST API only (no MCP protocol) | Microservices |
| **client** | MCP proxy to REST backend | Horizontal scaling |

## Docker Support

### Using docker-compose

```bash
# Start the MCP server
docker compose up -d mcp-virtual-character

# View logs
docker compose logs -f mcp-virtual-character

# Test health
curl http://localhost:8025/health
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "virtual-character": {
      "command": "mcp-virtual-character",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "virtual-character": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-virtual-character", "mcp-virtual-character", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_virtual_character

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
tools/mcp/mcp_virtual_character/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── lib.rs          # Library exports
    ├── server.rs       # MCP tools implementation
    ├── types.rs        # Data types and models
    ├── constants.rs    # VRCEmote mappings and defaults
    └── backends/
        ├── mod.rs      # Backend module exports
        ├── adapter.rs  # Backend trait definition
        ├── mock.rs     # Mock backend for testing
        └── vrchat.rs   # VRChat OSC backend
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
curl http://localhost:8025/health
curl http://localhost:8025/mcp/tools

# Test VRCEmote
curl -X POST http://localhost:8025/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "send_vrcemote", "arguments": {"emote": 4}}'
```

## Architecture

### Backend Abstraction

The server uses a backend adapter pattern:

```
VirtualCharacterServer
    |
    +-- BackendAdapter (trait)
            |
            +-- MockBackend (testing)
            +-- VRChatRemoteBackend (production)
            +-- (future backends)
```

### OSC Communication

VRChat uses OSC (Open Sound Control) for avatar parameter control:

- **Input addresses**: `/avatar/parameters/VRCEmote`, `/input/Vertical`, `/input/Horizontal`
- **Output addresses**: `/avatar/change`, `/avatar/parameters/*`

### ElevenLabs Integration

The audio playback system detects ElevenLabs expression tags in audio metadata:
- `<happy>`, `<sad>`, `<angry>`, `<fearful>`, `<surprised>`, `<disgusted>`
- Automatically maps to appropriate VRCEmote values

## Response Format

### Animation Response

```json
{
  "success": true,
  "message": "Animation sent: emotion=happy, gesture=wave"
}
```

### Backend Status

```json
{
  "backend": "vrchat_remote",
  "connected": true,
  "capabilities": {
    "audio": true,
    "animation": true,
    "video_capture": false,
    "bidirectional": true
  },
  "statistics": {
    "frames_sent": 150,
    "audio_sent": 10,
    "errors": 0
  }
}
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Not connected" error | Backend not initialized | Call `set_backend` first |
| VRCEmote not triggering | Toggle state mismatch | Wait for timeout or call twice |
| OSC not reaching VRChat | Wrong port configuration | Check VRChat OSC settings |
| Emotion stuck | Timeout not elapsed | Wait 3 seconds or send different emotion |

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [rosc](https://github.com/klingtnet/rosc) - OSC protocol implementation
- [tokio](https://tokio.rs/) - Async runtime
- [serde](https://serde.rs/) - Serialization
- [tracing](https://tracing.rs/) - Logging

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~20ms |
| VRCEmote send | ~1ms |
| OSC round-trip | ~5-10ms |
| Sequence event | ~1ms |

## Related Documentation

- [Virtual Character System Guide](../../../docs/integrations/ai-services/Virtual_Character_System_Guide.tex)
- [ElevenLabs Integration](../mcp_elevenlabs_speech/docs/README.md)
- [VRChat OSC Documentation](https://docs.vrchat.com/docs/osc-overview)

## License

Part of the template-repo project. See repository LICENSE file.
