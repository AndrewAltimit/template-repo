# Content Creation MCP Server

> A Model Context Protocol server for creating mathematical animations with Manim, compiling LaTeX documents, and rendering TikZ diagrams.

## Validation Status

| Component | Status | Description |
|-----------|--------|-------------|
| LaTeX Compilation | Validated | PDF, DVI, PostScript output formats |
| TikZ Rendering | Validated | PDF, PNG, SVG output |
| Manim Animations | Validated | MP4, GIF, PNG, WebM output |
| Preview Generation | Validated | PNG previews with configurable DPI |

**Scope**: This server provides document and animation creation. It requires a complete LaTeX installation (TeXLive) and Manim with FFmpeg. The Docker container includes all dependencies.

## Quick Start

```bash
# Using docker compose (recommended)
docker compose up -d mcp-content-creation

# Or run directly
python -m mcp_content_creation.server --mode http

# Test health
curl http://localhost:8011/health
```

## Available Tools

| Tool | Description | Output Formats |
|------|-------------|----------------|
| `create_manim_animation` | Create mathematical animations | mp4, gif, png, webm |
| `compile_latex` | Compile LaTeX documents | pdf, dvi, ps |
| `render_tikz` | Render TikZ diagrams | pdf, png, svg |
| `preview_pdf` | Generate PNG previews from PDF | png |

### Tool Parameters

#### create_manim_animation

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `script` | Yes | - | Python script containing Manim scene |
| `output_format` | No | mp4 | Output format (mp4, gif, png, webm) |

#### compile_latex

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `content` | No* | - | LaTeX document content |
| `input_path` | No* | - | Path to .tex file |
| `output_format` | No | pdf | Output format (pdf, dvi, ps) |
| `template` | No | custom | Document template (article, report, book, beamer) |
| `preview_pages` | No | none | Pages to preview (none, 1, 1-5, all) |
| `preview_dpi` | No | 150 | Preview resolution |

*Either `content` or `input_path` required

#### render_tikz

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `tikz_code` | Yes | - | TikZ code for the diagram |
| `output_format` | No | pdf | Output format (pdf, png, svg) |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MCP_CONTENT_PORT` | `8011` | Server listen port |
| `MCP_CONTENT_OUTPUT_DIR` | `/app/output` | Output directory |
| `MCP_CONTENT_LOG_LEVEL` | `INFO` | Logging level |

## Volume Mounts

```yaml
volumes:
  - ./outputs/mcp-content:/output           # Generated outputs
  - ./documents:/app/documents:ro           # Input documents (read-only)
```

## Output Directory Structure

**Host paths** (returned in responses):
```
outputs/mcp-content/
+-- manim/          # Manim animations
+-- latex/          # LaTeX documents
+-- previews/       # PNG previews
```

## Requirements

### For LaTeX

| Tool | Purpose |
|------|---------|
| `pdflatex` | PDF compilation |
| `latex` | DVI compilation |
| `dvips` | PostScript conversion |
| `pdftoppm` | PDF to PNG previews |
| `pdf2svg` | PDF to SVG conversion |

### For Manim

| Tool | Purpose |
|------|---------|
| `manim` | Animation library |
| `ffmpeg` | Video rendering |
| Python 3.7+ | Runtime |

## Docker Support

```bash
# Start the server
docker compose up -d mcp-content-creation

# View logs
docker compose logs -f mcp-content-creation

# Rebuild after changes
docker compose build mcp-content-creation
```

## Testing

```bash
# Test the server
python tools/mcp/mcp_content_creation/scripts/test_server.py

# Health check
curl -s http://localhost:8011/health | jq
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| LaTeX compilation fails | Missing packages | Add `\usepackage` in container |
| Manim render timeout | Complex scene | Simplify animation or increase timeout |
| Preview not generated | pdftoppm missing | Use Docker container |
| TikZ render fails | Missing TikZ libraries | Add to preamble |

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Two-pass compilation | Slower for large docs | Unavoidable for references |
| No incremental render | Full re-render each time | Cache outputs client-side |
| Memory for large docs | May fail in container | Increase container memory |

## Performance

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| LaTeX simple doc | 2-5s | Two-pass compilation |
| LaTeX large doc | 10-30s | Depends on complexity |
| TikZ diagram | 1-3s | Single compilation |
| Manim animation | 10-60s | Scene complexity dependent |

## License

Part of the template-repo project. See repository LICENSE file.
