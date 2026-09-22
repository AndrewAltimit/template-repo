# Meme Generator MCP Server (Rust)

> MCP server that draws captions onto meme templates, saves the result, returns an inline preview image, and optionally uploads it to a free image host for a shareable URL.

## Features

- **Auto-fit text**: word-wraps and picks the largest font size (per area min/max) whose block fits the area both horizontally and vertically, using real glyph advances and kerning. It avoids splitting words when a smaller size fits them whole, and splits over-long words rather than letting them overflow. Explicit `\n` forces a line break.
- **Clean outlines**: each line is rasterized once and the outline is a round, anti-aliased dilation of the glyph mask.
- **Validated templates**: every template config is checked against its image at load time (colors, font ranges, geometry, file name, image readability). Broken templates are skipped and reported through `meme_generator_status` / `list_meme_templates` instead of failing later.
- **Honest results**: unknown template or area ids are errors that list the valid ids. Overflowing text, text over the recommended `max_chars`, and characters the font cannot draw come back as `warnings`. Upload failures are reported in `upload_error`, including why each host failed.
- **Visual feedback**: a downscaled JPEG preview (longest side 512px) is returned as an MCP image content block, so the agent can see the result.
- **Uploads** to 0x0.st, tmpfiles.org or file.io. Each attempt has a timeout and fails over to the next host. Uploads can be disabled server-wide.
- All rendering and file I/O runs on blocking threads, so it never stalls the async runtime.

## Quick Start

```bash
cd tools/mcp/mcp_meme_generator
cargo build --release

# STDIO mode (what .mcp.json uses, via docker compose)
./target/release/mcp-meme-generator --mode stdio

# HTTP mode
./target/release/mcp-meme-generator --mode standalone --port 8016
curl http://localhost:8016/health
curl http://localhost:8016/mcp/tools
```

Through Docker (container-first):

```bash
docker compose --profile services run --rm -T mcp-meme-generator mcp-meme-generator --mode stdio
docker compose --profile services up -d mcp-meme-generator   # HTTP on :8016
```

In the container, memes are written to `/output`, which is bind-mounted to `./outputs/mcp-memes` on the host. The `output_path` values the tools return are **container** paths.

## Tools

| Tool | Description |
|------|-------------|
| `generate_meme` | Render captions on a template, save the file, return a preview, and optionally upload it |
| `list_meme_templates` | List templates (id, name, description, text area ids, image size), sorted by id |
| `get_meme_template_info` | Full template config (areas, usage rules, context, examples), image size, and a ready-to-use example call |
| `meme_generator_status` | Version, template count, load errors and warnings, font in use, directories, upload settings |
| `upload_meme` | Upload an already-generated meme from the output directory |
| `reload_meme_templates` | Re-read templates and font from disk |

### `generate_meme`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `template` | string | **required** | Template id |
| `texts` | object<string,string> | **required** | Caption per area id (max 500 chars each). Areas you leave out stay blank. Unknown ids are an error. |
| `font_size_override` | object<string,int> | `{}` | Fixed size (6-300 px) per area. Skips auto-fit for that area. |
| `auto_resize` | bool | `true` | Auto-fit between the area's `min_font_size` and `max_font_size`. When false, `default_font_size` is used. |
| `upload` | bool | `true` | Upload to a public host. **Uploaded images are public.** |
| `upload_service` | `auto` \| `0x0st` \| `tmpfiles` \| `fileio` | `auto` | Host. `auto` tries them in that order. |
| `output_format` | `png` \| `jpeg` | `png` | Saved file format. JPEG is several times smaller for photo templates. |
| `visual_feedback` | bool | `true` | Return the preview as image content |

Example:

```json
{
  "template": "ol_reliable",
  "texts": {"top": "When the code won't compile", "bottom": "print('hello world')"},
  "upload": false
}
```

Response (first content block is JSON text, second is `image/jpeg` preview):

```json
{
  "success": true,
  "template_used": "ol_reliable",
  "output_path": "/output/meme_ol_reliable_20260922_101500_123_0.png",
  "format": "png",
  "width": 960,
  "height": 1444,
  "size_kb": 1480.2,
  "areas": [
    {"id": "top", "font_size": 40.0, "lines": 2, "fits": true},
    {"id": "bottom", "font_size": 58.0, "lines": 1, "fits": true}
  ],
  "warnings": [],
  "share_url": "https://0x0.st/abcd.png",
  "embed_url": "https://0x0.st/abcd.png",
  "markdown": "![Meme](https://0x0.st/abcd.png)",
  "upload_service": "0x0.st",
  "upload_note": "Retention depends on file size (30 days up to 1 year)",
  "visual_feedback": {"format": "jpeg", "encoding": "base64", "delivered_as": "image content block", "width": 340, "height": 512, "size_kb": 38.1}
}
```

The upload fields (`share_url`, `embed_url`, `markdown`, `upload_service`, `upload_note`) only appear when an upload succeeds. When it fails, `upload_error` explains why and the meme is still saved. When the server has uploads disabled, `upload_skipped` says so. Domain errors (unknown template or area, oversized text, bad override) return an `isError` result with `{"success": false, "error": "..."}`. Malformed arguments (wrong types, missing required fields, unknown enum values) return an MCP invalid-parameters error.

### `upload_meme`

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | **required** | File name in the output directory, or the `output_path` from `generate_meme` |
| `service` | string | `auto` | Same values as `upload_service` |

Only `.png/.jpg/.jpeg/.webp/.gif` files up to 20 MB **inside the output directory** can be uploaded. The path is canonicalized, and anything that resolves outside the directory (`..`, other absolute paths, symlinks) is rejected.

### `get_meme_template_info`

`template_id` (required). If the id is unknown, the result is an error that includes `available_templates`.

## Templates

| Id | Text areas | Description |
|----|------------|-------------|
| `afraid_to_ask_andy` | top, bottom | Andy (Parks and Rec): "afraid to ask" |
| `community_fire` | expectation, chaos1, chaos2, chaos3, chaos4 | Troy walks in with pizza to an apartment on fire |
| `handshake_office` | left, right | The Office handshake: disproportionate praise |
| `millionaire` | question, a, b, c, d | Who Wants to Be a Millionaire question screen |
| `npc_wojak` | claim, challenge | NPC claim gets a simple challenge |
| `ol_reliable` | top, bottom | SpongeBob's trusty spatula (bottom goes on the box label) |
| `one_does_not_simply` | top, bottom | Boromir: "one does not simply..." |
| `sweating_jordan_peele` | top, bottom | Nervous sweating |

### Adding a template

1. Put the image in `templates/` (`.jpg/.jpeg/.png/.webp`; the real format is sniffed from the file content, not the extension).
2. Add `templates/config/<id>.json`. The id may only contain `[A-Za-z0-9_-]`. The format is described by `templates/config/template_schema.json`:

```json
{
  "name": "Template Name",
  "template_file": "template.jpg",
  "description": "What it is and when to use it",
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
      "stroke_width": 2,
      "max_chars": 40
    }
  ],
  "usage_rules": ["..."],
  "examples": [{"top": "Example text", "explanation": "Why it works"}]
}
```

`position` is the **center** of the area. Colors can be named (`white`, `black`, `red`, `green`, `lime`, `blue`, `yellow`, `orange`, `purple`, `pink`, `cyan`, `magenta`, `gray`, `brown`) or hex `#RGB` / `#RRGGBB` / `#RRGGBBAA`. `stroke_width` is 0-16 px and font sizes are 6-300 px.

3. Call `reload_meme_templates`, then check `load_errors` and `load_warnings`.
4. To eyeball every example of every template:

```bash
MEME_EXAMPLES_OUT=/tmp/meme-examples cargo test render_examples -- --ignored
```

## Configuration

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `--mode` | | `standalone` | `standalone` (HTTP + MCP), `stdio`, `server` (REST only), `client` (proxy) |
| `--port` | | `8000` | HTTP port (docker-compose passes `8016`) |
| `--log-level` | `RUST_LOG` overrides | `info` | Log level (logs go to stderr) |
| `--templates` | `MCP_MEME_TEMPLATES_DIR` | auto | Templates dir. Auto-detection tries, in order: `<exe dir>/templates`, `./templates`, `tools/mcp/mcp_meme_generator/templates`, then the crate's source dir. |
| `--output` | `MCP_OUTPUT_DIR` | `<system temp>/memes` | Where memes are saved |
| `--font` | `MCP_MEME_FONT` | auto | Caption font file. Auto-detection uses Liberation Sans Bold if installed (it is in the Docker image), else the embedded DejaVu Sans Bold. An explicit font that fails to load is an error. |
| `--disable-upload` | `MCP_MEME_DISABLE_UPLOAD` | off | Refuse all uploads (private / offline mode) |
| `--upload-timeout` | `MCP_MEME_UPLOAD_TIMEOUT` | `30` | Per-attempt upload timeout in seconds (1-300). The connect timeout is 10 s. |

## Upload services

| Service | Embeddable `embed_url` | Retention |
|---------|------------------------|-----------|
| 0x0.st | yes | 30 days to 1 year, depending on file size |
| tmpfiles.org | yes (`https://tmpfiles.org/dl/...`) | about 60 minutes |
| file.io | **no**: the link is a download page that is deleted after the first download | one download |

These are third-party, no-auth services, and their availability and policies change. With `auto`, the error message lists what each host returned. For a long-lived link, generate with `upload: false` and use `output_format: "jpeg"` to keep files small, then host the file yourself.

## HTTP endpoints (standalone mode)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List tools |
| `/mcp/execute` | POST | Execute a tool: `{"tool": "...", "arguments": {...}}` |
| `/messages` | POST | MCP JSON-RPC |
| `/.well-known/mcp` | GET | MCP discovery |

```bash
curl -X POST http://localhost:8016/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "generate_meme", "arguments": {"template": "ol_reliable", "texts": {"top": "When debugging fails", "bottom": "console.log()"}, "upload": false}}'
```

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # fully offline; upload tests use a local mock HTTP server
cargo build --release
```

Source layout:

```
src/
  main.rs       CLI, config resolution, server startup
  server.rs     MCP tools, typed argument parsing, lazy/reloadable state
  generator.rs  request validation, rendering pipeline, encoding, saving
  render.rs     text measuring, wrapping, fitting, outline rasterization (pure)
  templates.rs  template discovery and validation
  fonts.rs      font resolution (explicit, system, embedded)
  upload.rs     upload client, host response parsers
  types.rs      template config and result types
assets/DejaVuSans-Bold.ttf   embedded fallback font
templates/                   images + config/*.json
```

## Limitations

- One font per render. There is no per-glyph fallback, so characters the font lacks (emoji, CJK with the default fonts) show up as boxes and are reported in `warnings`.
- Templates are drawn as RGB. Transparency in template PNGs is dropped.
- Output looks slightly different depending on the font in use: Liberation Sans Bold in Docker, embedded DejaVu Sans Bold elsewhere. Use `--font` for identical output everywhere.
- Upload hosts are best-effort public services. Do not upload anything sensitive.
