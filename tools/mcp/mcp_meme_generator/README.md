# Meme Generator MCP Server (Rust)

> A Model Context Protocol server for meme generation with text overlays, built in Rust with high-performance image processing and automatic text sizing.

## Overview

This MCP server provides:
- Meme generation from templates with customizable text overlays
- Automatic font size adjustment to fit text in designated areas
- Text stroke/outline effects for readability
- Multiple upload service support (0x0.st, tmpfiles.org, file.io)
- Visual feedback thumbnails for immediate preview
- Lazy initialization for fast startup

**Note**: Migrated from Python to Rust for improved performance and smaller binary size.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-meme-generator --mode standalone --port 8016

# Run in STDIO mode (for Claude Code)
./target/release/mcp-meme-generator --mode stdio

# Specify custom templates directory
./target/release/mcp-meme-generator --templates /path/to/templates --output /tmp/memes

# Test health
curl http://localhost:8016/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `generate_meme` | Generate a meme with text overlays | `template` (required), `texts` (required), `font_size_override`, `auto_resize`, `upload` |
| `list_meme_templates` | List all available templates | None |
| `get_meme_template_info` | Get detailed template configuration | `template_id` (required) |
| `meme_generator_status` | Get server status and template count | None |

### Example Usage

```json
{
  "tool": "generate_meme",
  "arguments": {
    "template": "ol_reliable",
    "texts": {
      "top": "When the code won't compile",
      "bottom": "print('hello world')"
    },
    "upload": true
  }
}
```

### Available Templates

| Template | Text Areas | Description |
|----------|------------|-------------|
| `ol_reliable` | top, bottom | SpongeBob's trusted spatula |
| `community_fire` | top, bottom | "This is fine" burning room |
| `afraid_to_ask_andy` | top, bottom | Parks & Rec Andy meme |
| `sweating_jordan_peele` | top | Sweating nervously |
| `one_does_not_simply` | top, bottom | Boromir LOTR meme |
| `handshake_office` | left, right, bottom | Epic handshake |
| `npc_wojak` | top | NPC/Wojak reaction |
| `millionaire` | top, bottom | Who Wants to Be a Millionaire |

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8016]
--templates <PATH>    Path to templates directory
--output <PATH>       Output directory for generated memes [default: /tmp/memes]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_OUTPUT_DIR` | Override output directory | `/tmp/memes` |

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
docker compose up -d mcp-meme-generator

# View logs
docker compose logs -f mcp-meme-generator

# Test health
curl http://localhost:8016/health
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "meme-generator": {
      "command": "mcp-meme-generator",
      "args": ["--mode", "stdio", "--templates", "/path/to/templates"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_meme_generator

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
tools/mcp/mcp_meme_generator/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
├── assets/
│   └── DejaVuSans-Bold.ttf  # Fallback font
├── templates/          # Meme templates
│   ├── config/         # Template JSON configs
│   └── *.jpg           # Template images
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── generator.rs    # Meme generation engine
    ├── upload.rs       # Upload service handlers
    └── types.rs        # Data types
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
curl http://localhost:8016/health
curl http://localhost:8016/mcp/tools

# Test meme generation
curl -X POST http://localhost:8016/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "generate_meme",
    "arguments": {
      "template": "ol_reliable",
      "texts": {"top": "When debugging fails", "bottom": "console.log()"},
      "upload": false
    }
  }'
```

## Template Format

Templates are defined as JSON files in `templates/config/`:

```json
{
  "name": "Template Name",
  "template_file": "template.jpg",
  "description": "Template description",
  "text_areas": [
    {
      "id": "top",
      "position": {"x": 200, "y": 50},
      "width": 400,
      "height": 100,
      "default_font_size": 40,
      "max_font_size": 60,
      "min_font_size": 20,
      "text_align": "center",
      "text_color": "white",
      "stroke_color": "black",
      "stroke_width": 2
    }
  ],
  "usage_rules": ["Usage guideline 1", "Usage guideline 2"],
  "examples": [
    {"top": "Example text", "bottom": "More text"}
  ]
}
```

## Response Format

### Generate Meme Response

```json
{
  "success": true,
  "template_used": "ol_reliable",
  "output_path": "/tmp/memes/meme_ol_reliable_1706445678.png",
  "size_kb": 125.5,
  "share_url": "https://0x0.st/abcd.png",
  "embed_url": "https://0x0.st/abcd.png",
  "upload_service": "0x0.st",
  "visual_feedback": {
    "format": "webp",
    "encoding": "base64",
    "data": "...",
    "size_kb": 2.3
  }
}
```

## Upload Services

| Service | Retention | Notes |
|---------|-----------|-------|
| 0x0.st | 365 days for <512KB | Primary, best retention |
| tmpfiles.org | 1 hour inactive / 30 days max | Fallback |
| file.io | Configurable | Last resort |

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Template not found" | Invalid template ID | Use `list_meme_templates` to see available templates |
| "Font not found" | Missing system font | Uses embedded fallback font automatically |
| Upload fails | Service issues | Tries multiple services automatically |
| Empty output | No text provided | Ensure `texts` contains valid area IDs |

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [image](https://github.com/image-rs/image) - Image processing
- [imageproc](https://github.com/image-rs/imageproc) - Drawing operations
- [ab_glyph](https://github.com/alexheretic/ab-glyph) - Font loading
- [tokio](https://tokio.rs/) - Async runtime
- [reqwest](https://github.com/seanmonstar/reqwest) - HTTP client

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~50ms (lazy init) |
| First meme | ~100-200ms (font loading) |
| Subsequent memes | ~30-80ms |
| Upload | ~500ms-2s (network dependent) |

## License

Part of the template-repo project. See repository LICENSE file.
