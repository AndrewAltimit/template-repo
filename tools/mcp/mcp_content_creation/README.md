# Content Creation MCP Server (Rust)

> A Model Context Protocol server for content creation, built in Rust. Provides LaTeX compilation, TikZ diagram rendering, PDF previews, and Manim animation support.

## Overview

This MCP server provides:
- LaTeX document compilation to PDF, DVI, PS formats
- TikZ diagram rendering to PDF, PNG, SVG
- PDF page previews with configurable DPI
- Manim mathematical animation creation
- Path traversal protection for file operations
- Container-to-host path mapping for Docker environments

**Note**: Migrated from Python to Rust for improved performance.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-content-creation --mode standalone --port 8011

# Run in STDIO mode (for Claude Code)
./target/release/mcp-content-creation --mode stdio

# Test health
curl http://localhost:8011/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `compile_latex` | Compile LaTeX documents | `content` or `input_path`, `output_format`, `template`, `preview_pages`, `preview_dpi` |
| `render_tikz` | Render TikZ diagrams | `tikz_code` (required), `output_format`, `response_mode` |
| `preview_pdf` | Generate PDF page previews | `pdf_path` (required), `pages`, `dpi`, `response_mode` |
| `create_manim_animation` | Create Manim animations | `script` (required), `output_format` |
| `content_creation_status` | Get server status | None |

### Example: Compile LaTeX

```json
{
  "tool": "compile_latex",
  "arguments": {
    "content": "\\documentclass{article}\n\\begin{document}\nHello, World!\n\\end{document}",
    "output_format": "pdf",
    "preview_pages": "1"
  }
}
```

### Example: Render TikZ

```json
{
  "tool": "render_tikz",
  "arguments": {
    "tikz_code": "\\begin{tikzpicture}\n\\draw (0,0) circle (1cm);\n\\end{tikzpicture}",
    "output_format": "png"
  }
}
```

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8011]
--output-dir <PATH>   Output directory for generated content [default: /app/output]
--project-root <PATH> Project root for resolving paths [default: /app]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_OUTPUT_DIR` | Output directory | `/app/output` |
| `MCP_PROJECT_ROOT` | Project root for path resolution | `/app` |
| `MCP_HOST_PROJECT_ROOT` | Host project root (for container path mapping) | |

## Prerequisites

The server requires these external tools to be installed:

| Tool | Package | Purpose |
|------|---------|---------|
| `pdflatex` | texlive-latex-base | LaTeX to PDF compilation |
| `latex` | texlive-latex-base | LaTeX to DVI compilation |
| `dvips` | texlive-base-bin | DVI to PS conversion |
| `pdfinfo` | poppler-utils | PDF metadata extraction |
| `pdftoppm` | poppler-utils | PDF to PNG conversion |
| `pdf2svg` | pdf2svg | PDF to SVG conversion |
| `manim` | manim (pip) | Mathematical animations |

### Install on Debian/Ubuntu

```bash
apt-get install texlive-latex-base texlive-latex-extra \
  poppler-utils pdf2svg
pip install manim
```

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
docker compose up -d mcp-content-creation

# View logs
docker compose logs -f mcp-content-creation

# Test health
curl http://localhost:8011/health
```

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "content-creation": {
      "command": "mcp-content-creation",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_content_creation

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
tools/mcp/mcp_content_creation/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── engine.rs       # Content creation engine
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
curl http://localhost:8011/health
curl http://localhost:8011/mcp/tools

# Test LaTeX compilation
curl -X POST http://localhost:8011/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "compile_latex",
    "arguments": {
      "content": "\\documentclass{article}\\begin{document}Hello\\end{document}",
      "output_format": "pdf"
    }
  }'
```

## Response Format

### compile_latex Response

```json
{
  "success": true,
  "output_path": "outputs/mcp-content/latex/document_1706445678_1234.pdf",
  "container_path": "/app/output/latex/document_1706445678_1234.pdf",
  "page_count": 1,
  "file_size_kb": 12.5,
  "format": "pdf",
  "compile_time_seconds": 1.23,
  "preview_paths": ["outputs/mcp-content/previews/document_page1.png"]
}
```

### render_tikz Response

```json
{
  "success": true,
  "output_path": "outputs/mcp-content/latex/document.png",
  "container_path": "/app/output/latex/document.png",
  "format": "png"
}
```

## Security

- Path traversal protection for relative input paths
- LaTeX compiled with `-no-shell-escape` to prevent RCE via `\write18`
- Input validation on all parameters

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "pdflatex not found" | LaTeX not installed | Install texlive-latex-base |
| "pdftoppm not found" | Poppler not installed | Install poppler-utils |
| "Path traversal detected" | Suspicious relative path | Use absolute path or valid relative path |
| LaTeX errors | Invalid LaTeX content | Check LaTeX syntax |

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime with process support
- [tempfile](https://github.com/Stebalien/tempfile) - Temp file/directory handling
- [regex](https://github.com/rust-lang/regex) - Pattern matching

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~50ms |
| LaTeX compilation | 1-5s (depends on document) |
| PDF preview | ~100ms per page |
| TikZ render | 1-3s |

## License

Part of the template-repo project. See repository LICENSE file.
