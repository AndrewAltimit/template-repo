# Reaction Search MCP Server (Rust)

> A Model Context Protocol server for semantic search of anime reaction images, built in Rust with ONNX-based embeddings for fast similarity matching.

## Overview

This MCP server provides:
- Natural language search for reaction images using semantic similarity
- Sentence embeddings via ONNX (AllMiniLM-L6-v2, 384 dimensions)
- Tag-based filtering and categorization
- GitHub-hosted configuration with local caching (1-week TTL)
- Lazy initialization for fast startup

**Note**: This was the first MCP server migrated from Python to Rust as a pilot for the mcp-core-rust framework.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-reaction-search --mode standalone --port 8024

# Run in STDIO mode (for Claude Code)
./target/release/mcp-reaction-search --mode stdio

# Test health
curl http://localhost:8024/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `search_reactions` | Search for reactions using natural language | `query` (required), `limit`, `tags`, `min_similarity` |
| `get_reaction` | Get a specific reaction by ID | `reaction_id` (required) |
| `list_reaction_tags` | List all available tags with counts | None |
| `refresh_reactions` | Force refresh config from GitHub | None |
| `reaction_search_status` | Get server status and cache info | None |

### Example Searches

```
"celebrating after fixing a bug"     -> felix, aqua_happy
"confused about the error message"   -> confused, miku_confused
"annoyed at the failing tests"       -> kagami_annoyed, nao_annoyed
"deep in thought while debugging"    -> thinking_foxgirl, hifumi_studious
```

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8024]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Cache Location

- Linux: `~/.cache/mcp-reaction-search/`
- macOS: `~/Library/Caches/mcp-reaction-search/`
- Windows: `%LOCALAPPDATA%\mcp-reaction-search\`

Cache files:
- `reactions.yaml` - Cached reaction configuration
- `cache_metadata.json` - Cache timestamp and TTL info

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
docker compose up -d mcp-reaction-search

# View logs
docker compose logs -f mcp-reaction-search

# Test health
curl http://localhost:8024/health
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "reaction-search": {
      "command": "mcp-reaction-search",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "reaction-search": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-reaction-search", "mcp-reaction-search", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_reaction_search

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
tools/mcp/mcp_reaction_search/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── engine.rs       # Semantic search engine
    ├── config.rs       # GitHub config loading
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
curl http://localhost:8024/health
curl http://localhost:8024/mcp/tools

# Test search
curl -X POST http://localhost:8024/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "search_reactions", "arguments": {"query": "happy coding", "limit": 3}}'
```

## Architecture

### Semantic Search

The search engine uses:
1. **AllMiniLM-L6-v2** - Fast sentence transformer (384 dimensions)
2. **ONNX Runtime** - Cross-platform inference via fastembed
3. **Cosine Similarity** - For ranking results
4. **Tag Filtering** - Optional category-based filtering

### Lazy Initialization

The embedding model loads on first search request to minimize startup time. Status endpoint shows initialization state.

### Configuration Source

Reactions are loaded from GitHub:
```
https://raw.githubusercontent.com/AndrewAltimit/Media/main/reaction/config.yaml
```

Cached locally with 1-week TTL. Use `refresh_reactions` to force update.

## Response Format

### Search Results

```json
{
  "success": true,
  "query": "happy coding",
  "count": 3,
  "results": [
    {
      "id": "miku_typing",
      "url": "https://raw.githubusercontent.com/.../miku_typing.webp",
      "description": "Miku happily typing on keyboard",
      "tags": ["happy", "typing", "working"],
      "similarity": 0.85,
      "markdown": "![miku_typing](https://...)"
    }
  ]
}
```

### Tag Categories

Tags are automatically categorized:
- **emotions**: happy, sad, angry, confused, excited, annoyed, smug, shocked, nervous, bored, content
- **actions**: typing, thinking, working, gaming, drinking, waving, cheering, crying, laughing, studying
- **other**: character-specific tags

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Slow first search | Model loading | Normal - model loads lazily on first use |
| "Failed to load config" | Network/GitHub issue | Check network; config will use cache if available |
| Empty results | Query too specific | Use broader terms; check `min_similarity` |
| Stale reactions | Cache not refreshed | Call `refresh_reactions` tool |

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [fastembed](https://github.com/Anush008/fastembed-rs) - ONNX sentence embeddings
- [ndarray](https://github.com/rust-ndarray/ndarray) - Linear algebra
- [tokio](https://tokio.rs/) - Async runtime
- [reqwest](https://github.com/seanmonstar/reqwest) - HTTP client

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~50ms (model loads lazily) |
| First search | ~2-3s (includes model loading) |
| Subsequent searches | ~10-50ms |
| Config refresh | ~500ms (network dependent) |

## License

Part of the template-repo project. See repository LICENSE file.
