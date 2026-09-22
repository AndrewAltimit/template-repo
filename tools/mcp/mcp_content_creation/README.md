# Content Creation MCP Server (Rust)

> MCP server for technical content: sandboxed LaTeX compilation, TikZ diagram
> rendering, PDF page previews, and Manim animations.

## Overview

| Tool | What it does |
|------|--------------|
| `compile_latex` | Compile LaTeX (inline or from a project `.tex` file) to PDF, DVI, or PS, with automatic re-runs, BibTeX, and optional PNG page previews |
| `render_tikz` | Render a TikZ snippet as a standalone PDF, PNG, or SVG |
| `preview_pdf` | Render selected pages of an existing PDF to PNG |
| `create_manim_animation` | Render a Manim Community Edition scene to MP4, GIF, WebM, or a last-frame PNG |
| `content_creation_status` | Report configuration and which external tools are installed (with versions) |

The server shells out to `pdflatex`, `latex`, `bibtex`, `dvips`, `pdfinfo`,
`pdftoppm`, `pdf2svg`, and `manim`. The Docker image
(`docker/mcp-content.Dockerfile`) contains all of them; run the server there.

## Quick Start

```bash
# Recommended: in the container (what .mcp.json does for STDIO)
docker compose --profile services run --rm -T mcp-content-creation \
  mcp-content-creation --mode stdio

# Or as an HTTP service on port 8011
docker compose --profile services up -d mcp-content-creation
curl http://localhost:8011/health

# Local build (needs the external tools on PATH to do anything useful)
cargo build --release
./target/release/mcp-content-creation --mode stdio \
  --output-dir ./outputs/mcp-content --project-root .
```

Note: the `mcp-core` default port is 8000; docker compose passes `--port 8011`.

## Tools

All tools return a JSON object with `success` and, on failure, `error`. A
result with `success: false` is also flagged `isError` at the MCP level.
Invalid arguments (wrong types, unknown enum values, missing required fields)
are rejected with an `InvalidParameters` error rather than silently defaulted.
Enum values are case-insensitive.

`output_path` is the host-relative path (e.g. `outputs/mcp-content/latex/...`)
and `container_path` is the path inside the server. Both are always returned
on success, regardless of `response_mode`.

### `compile_latex`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `content` | string | - | Inline LaTeX. Exactly one of `content` / `input_path` is required. |
| `input_path` | string | - | `.tex` file relative to the project root (or absolute inside it / the output dir). Files next to it (`\input` chapters, images, `.bib`) are found automatically. |
| `output_format` | `pdf` \| `dvi` \| `ps` | `pdf` | Alias: `format`. |
| `template` | `article` \| `report` \| `book` \| `beamer` \| `custom` | `custom` | Wraps a fragment in that class with amsmath/amssymb/graphicx. Ignored (with a warning) if the content has `\documentclass`. `custom` = verbatim. |
| `preview_pages` | string | `none` | `none`, `1`, `1,3,5`, `2-4`, `5-`, `all`. PDF only, max 50 pages. Malformed specs are reported as warnings. |
| `preview_dpi` | integer | 150 | Clamped to 36-600. |
| `visual_feedback` | boolean | false | Legacy shortcut for `preview_pages: "1"`. |
| `response_mode` | `minimal` \| `standard` | `standard` | `standard` adds `format`, `compile_time_seconds`, `latex_passes`, `preview_paths`. |

Compilation runs pdflatex (PDF) or latex (DVI; PS additionally runs
`dvips -R2`). The engine re-runs LaTeX when the log asks for it (cross
references, hyperref, ...) or when the document has a table of contents/list of
figures, and runs BibTeX once when the `.aux` file contains `\bibdata`
(at most 4 LaTeX passes). If LaTeX reported errors but still produced output,
the result is `success: true` with the errors in `warnings`. When no output is
produced, `error` contains the `!` error lines with their `l.<n>` source
context.

```json
{"content": "Euler: $e^{i\\pi}+1=0$", "template": "article", "preview_pages": "1"}
```

```json
{
  "success": true,
  "output_path": "outputs/mcp-content/latex/document_1758550000000_7_0.pdf",
  "container_path": "/output/latex/document_1758550000000_7_0.pdf",
  "page_count": 1,
  "file_size_kb": 31.2,
  "format": "pdf",
  "compile_time_seconds": 0.61,
  "latex_passes": 1,
  "preview_paths": ["outputs/mcp-content/previews/document_1758550000000_7_0_page1.png"]
}
```

### `render_tikz`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `tikz_code` | string | required | A `tikzpicture` environment, bare TikZ commands (wrapped automatically), or a full document (used verbatim). |
| `output_format` | `pdf` \| `png` \| `svg` | `pdf` | PNG via `pdftoppm`, SVG via `pdf2svg`. |
| `tikz_libraries` | string[] | - | Added to the always-loaded `arrows.meta, positioning, shapes, calc`. |
| `packages` | string[] | - | Extra `\usepackage`s, e.g. `["pgfplots"]`. |
| `dpi` | integer | 300 | PNG only; clamped to 36-600. |
| `response_mode` | `minimal` \| `standard` | `standard` | `standard` adds `format`, `latex_passes`, and the intermediate `pdf_path` for PNG/SVG. |

Library and package names must match `[A-Za-z0-9][A-Za-z0-9._-]*` so they
cannot inject preamble code.

```json
{"tikz_code": "\\draw[->] (0,0) -- (2,1) node[right] {$v$};", "output_format": "svg"}
```

### `preview_pdf`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `pdf_path` | string | required | Inside the project root or the output directory (e.g. a `container_path` from `compile_latex`). |
| `pages` | string | `1` | Same syntax as `preview_pages`; max 50 pages. |
| `dpi` | integer | 150 | Clamped to 36-600. |
| `response_mode` | `minimal` \| `standard` | `standard` | `standard` adds `pdf_path`, `page_count`, `pages_exported`. |

Preview files are named `{pdf-stem}_{unique}_page{n}.png` in
`<output>/previews/`, so repeated or concurrent previews never overwrite each
other.

### `create_manim_animation`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `script` | string | required | Python defining at least one top-level `Scene` subclass (usually `from manim import *`). |
| `output_format` | `mp4` \| `gif` \| `webm` \| `png` | `mp4` | `png` saves the last frame (`manim -s`). |
| `scene_name` | string | first Scene subclass | Must be defined in the script. When several scenes exist and none is named, the first is rendered and a warning lists the others. |
| `quality` | `low` \| `medium` \| `high` \| `production` \| `fourk` | `low` | 480p15 / 720p30 / 1080p60 / 1440p60 / 2160p60. Short forms `l m h p k` accepted. |
| `preview` | boolean | false | Render only the last frame as PNG (quick sanity check). |

Each render runs in its own temporary media directory; only the final file is
copied to `<output>/manim/{Scene}_{unique}.{ext}`, so intermediate
`partial_movie_files` do not accumulate and a stale file from an earlier run
can never be returned. On failure the tail of Manim's output (usually the
Python traceback) is returned in `error`.

### `content_creation_status`

No parameters. Returns version, directories, timeouts, concurrency limit,
`dependencies` (name, command, `available`, version or install hint), and
`missing_dependencies`.

## Configuration

| Flag | Env var | Default | Purpose |
|------|---------|---------|---------|
| `--mode` | - | `standalone` | `standalone` (HTTP), `stdio`, `server`, `client` (from mcp-core) |
| `--port` | - | `8000` | HTTP port (compose uses 8011) |
| `--log-level` | `RUST_LOG` overrides | `info` | Logs go to stderr |
| `--output-dir` | `MCP_OUTPUT_DIR` | `/app/output` | Generated files: `latex/`, `previews/`, `manim/` |
| `--project-root` | `MCP_PROJECT_ROOT` | `/app` | Input files must be here (or in the output dir) |
| `--host-project-root` | `MCP_HOST_PROJECT_ROOT` | - | Host path of the project root; absolute host paths under it are accepted as inputs |
| `--host-output-dir` | `MCP_HOST_OUTPUT_DIR` | `outputs/mcp-content` | How `--output-dir` appears on the host, used for `output_path` |
| `--latex-timeout-secs` | `MCP_LATEX_TIMEOUT_SECS` | `120` | Deadline per LaTeX/BibTeX/dvips/poppler/pdf2svg process (1-3600) |
| `--manim-timeout-secs` | `MCP_MANIM_TIMEOUT_SECS` | `600` | Deadline per Manim render (1-7200) |
| `--max-concurrent-jobs` | `MCP_MAX_CONCURRENT_JOBS` | `2` | Compile/render jobs allowed at once; extra calls queue (1-64) |

In docker compose the repo is mounted read-only at `/app` and
`./outputs/mcp-content` at `/output`.

## Security

LaTeX input is treated as untrusted:

- Each compilation runs in a fresh temporary directory.
- `-no-shell-escape` and `shell_escape=f` disable `\write18`.
- kpathsea paranoid mode (`openin_any=p`, `openout_any=p`, `TEXMFOUTPUT`
  unset) blocks reading or writing absolute paths, `..`, and dotfiles, so
  `\input{/etc/passwd}` or `\openout` to arbitrary locations fail.
- `dvips -R2` disables backtick shell commands in `\special`.
- `input_path`/`pdf_path` are canonicalized and must resolve inside the project
  root or output directory (symlinks and `..` cannot escape).
- TikZ library/package names are validated; DPI and page counts are bounded;
  inline LaTeX is limited to 2 MiB and Manim scripts to 1 MiB.
- Every subprocess has a deadline, stdin closed, and captured output capped at
  64 KiB per stream. On Unix the whole process group is killed on timeout.

**Manim scripts are arbitrary Python** and run with the server's privileges.
The timeout and a temporary working directory are the only protections inside
the server; the container (non-root user, read-only project mount) is the real
sandbox. Do not expose this server to untrusted callers outside a container.

## Limitations

- Engines: pdflatex/latex only (no XeLaTeX/LuaLaTeX); bibliographies via BibTeX
  only (biblatex with `backend=biber` produces a warning, not a bibliography).
- Relative paths in `\graphicspath` or `\input{../x}` that climb above the
  source file's directory do not resolve (paranoid mode and the temp-dir build).
- Page previews and `compile_latex` page counts are available for PDF output only.
- A LaTeX loop that writes a huge log can still fill the temp filesystem before
  the timeout fires.
- Output files are never cleaned up by the server; prune `outputs/mcp-content`
  as needed.

## Development

```bash
cd tools/mcp/mcp_content_creation
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline; external tools are replaced by missing binaries
cargo build --release
```

Unit tests cover argument parsing, path policy, page specs, log parsing, TikZ
document assembly, Manim scene detection/output discovery, subprocess timeouts
(Unix), and tool-level error paths. They do not need LaTeX or Manim installed.

### Project structure

```
src/
  main.rs     CLI / env configuration, server startup
  server.rs   MCP tool definitions (schemas, typed argument parsing)
  engine.rs   Orchestration of LaTeX, poppler, pdf2svg, Manim jobs
  latex.rs    Pure LaTeX helpers: templates, TikZ docs, log parsing, page specs
  manim.rs    Pure Manim helpers: scene detection, CLI args, output discovery
  paths.rs    Input path policy, host path mapping, unique output names
  process.rs  Subprocess runner with timeouts and bounded output capture
  types.rs    Argument/result types and case-insensitive enums
```
