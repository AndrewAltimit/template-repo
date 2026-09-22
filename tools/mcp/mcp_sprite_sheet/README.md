# Sprite Sheet MCP Server (Rust)

> An MCP server for making pixel art and sprite sheets from code. Pixels are stored sparsely as palette indices and rendered with nearest-neighbor scaling.

## Overview

- In-memory projects: canvas, sprite grid, palette, layers, sprites, and animations
- Layers with z-order, visibility, opacity, blend modes (normal/multiply/screen/overlay), and locking
- Drawing primitives that clip to the canvas: batch pixels (with erase), Bresenham lines, rectangles, pixel-art ellipses, and scanline flood fill (contiguous or global)
- Palette presets (pico8, gameboy, nes, snes, endesga32), custom palettes, optional enforcement, and index remapping
- Named sprite regions on the grid with anchors, hitboxes, and tags. Animations with per-frame timing and loop modes
- Transforms: flip, rotate 90/180, and shift (with optional wrap), on a whole layer or a region
- Project-level undo/redo for every mutating tool (50 steps). A failed edit changes nothing
- Rendering to PNG with debug overlays: grid, bounding boxes, anchors, hitboxes, and sprite names
- Export: per-frame PNGs, a horizontal strip, animated GIF, and a texture atlas (PNG + JSON metadata)
- Versioned JSON save/load, returned inline or written to a file
- Image import (PNG/JPEG/WebP/GIF): palette extraction, background removal, and fringe trimming

## Quick Start

```bash
# Build from source
cargo build --release

# STDIO mode (how Claude Code launches it)
./target/release/mcp-sprite-sheet --mode stdio --output /tmp/sprites

# Standalone HTTP mode
./target/release/mcp-sprite-sheet --mode standalone --port 8027
curl http://localhost:8027/health
curl http://localhost:8027/mcp/tools
```

### Configuration

| Flag / env var | Default | Description |
|----------------|---------|-------------|
| `--mode` | `standalone` | `stdio`, `standalone` (HTTP), `server`, `client` (from mcp-core) |
| `--port` | `8000` | HTTP port (the Docker service uses 8027) |
| `--output` / `MCP_SPRITE_OUTPUT_DIR` | `<tmp>/sprites` | Directory for every generated file (created at startup) |
| `--log-level` / `RUST_LOG` | `info` | Log filter. Logs go to stderr |

## Example Session

```jsonc
// 1. A 64x32 sheet of 16x16 cells with the PICO-8 palette
sprite_create_project { "name": "hero", "width": 64, "height": 32, "palette_preset": "pico8" }
sprite_add_layer      { "name": "hero", "layer_name": "body" }            // -> layer_id

// 2. Draw. Pass the layer's ID or its (unique) name as layer_id
sprite_draw_ellipse   { "name": "hero", "layer_id": "body", "cx": 7, "cy": 7, "rx": 5, "ry": 6, "color_index": 8, "filled": true }
sprite_set_pixels     { "name": "hero", "layer_id": "body", "pixels": [[5, 5, 0], [9, 5, 0]] }
sprite_get_pixels     { "name": "hero", "layer_id": "body", "format": "grid",
                        "region": { "x": 0, "y": 0, "width": 16, "height": 16 } }

// 3. Copy frame 0 into cell 1 and change it
sprite_duplicate_layer { "name": "hero", "layer_id": "body", "new_name": "f1" }
sprite_transform      { "name": "hero", "layer_id": "f1", "operation": "shift", "shift_dx": 16 }

// 4. Define the sprites and an animation, then export them
sprite_define_sprite  { "name": "hero", "sprite_name": "idle_0", "grid_x": 0, "grid_y": 0, "anchor_x": 8, "anchor_y": 16 }
sprite_define_sprite  { "name": "hero", "sprite_name": "idle_1", "grid_x": 1, "grid_y": 0, "anchor_x": 8, "anchor_y": 16 }
sprite_define_animation { "name": "hero", "anim_name": "idle", "loop_mode": "ping_pong",
                          "frames": [{ "sprite_id": "idle_0", "duration_ms": 200 }, { "sprite_id": "idle_1" }] }
sprite_render         { "name": "hero", "scale": 8, "overlays": { "grid_lines": true, "sprite_names": true } }
sprite_export_gif     { "name": "hero", "animation_id": "idle", "scale": 4 }
sprite_export_atlas   { "name": "hero", "filename": "hero_sheet" }
sprite_save_project   { "name": "hero", "filename": "hero" }               // writes hero.json
```

## Available Tools (38)

The following apply to every tool:
- `name` is the project name.
- `layer_id`, `sprite_id` and `animation_id` accept an ID or a unique name.
- Integers may also be sent as numeric strings. Nested objects and arrays may also be sent as JSON-encoded strings.
- An out-of-range value is rejected with an error that names the field (for example `pixels[3]: color_index: integer 300 is out of range for u8`). It is never wrapped silently.
- Coordinates may be negative or fall outside the canvas. Drawing is clipped to the canvas.

### Project Management (7)

| Tool | Description |
|------|-------------|
| `sprite_create_project` | New project: `width`, `height` (max 4096 per side and 4,194,304 px in total), `cell_width`/`cell_height` (default 16), `padding`, `margin`, `background_color` (RGB or RGBA), `palette_preset`, and `overwrite` (default true) |
| `sprite_save_project` | Returns versioned JSON (`project_data`). With `filename`, also writes `<filename>.json` to the output directory. Set `include_data=false` to leave the inline JSON out |
| `sprite_load_project` | Loads from inline `project_data` or from a `file` path (relative paths resolve against the output directory). `name` loads it under a new name. Recoverable problems are fixed and reported as `warnings` |
| `sprite_project_status` | Canvas, grid (columns/rows), palette, counts, pixels whose color is undefined, and the next undo/redo labels |
| `sprite_list_projects` | Every loaded project, plus the output directory |
| `sprite_delete_project` | Removes a project from memory. Cannot be undone |
| `sprite_resize_canvas` | New `width`/`height`. `offset_x`/`offset_y` shift the content. Pixels that fall outside the new canvas are dropped and counted |

### Layers (7)

| Tool | Description |
|------|-------------|
| `sprite_add_layer` | Adds `layer_name` at `z_order` (default: on top) |
| `sprite_remove_layer` | Removes a layer |
| `sprite_update_layer` | Changes `layer_name`, `visible`, `opacity` (0-255), `blend_mode`, `locked`, or `z_order` |
| `sprite_duplicate_layer` | Copies a layer directly above the source. Takes an optional `new_name` |
| `sprite_merge_layers` | Merges `top_layer_id` onto `bottom_layer_id` and removes the top layer. Warns if the top layer's opacity or blend mode is lost |
| `sprite_clear_layer` | Clears the whole layer or a `region`. Returns how many pixels were cleared |
| `sprite_list_layers` | Lists layers bottom to top, with their properties and pixel counts |

### Drawing (6)

| Tool | Description |
|------|-------------|
| `sprite_set_pixels` | `pixels` as `{x, y, color_index}` or `[x, y, color_index]`. `erase` takes `[x, y]` points to clear first. Reports pixels skipped for being out of bounds or having an invalid color |
| `sprite_draw_line` | Bresenham line from (`x0`,`y0`) to (`x1`,`y1`), both ends included |
| `sprite_draw_rect` | `x`, `y`, `width`, `height`, and `filled` |
| `sprite_draw_ellipse` | Center (`cx`,`cy`) and radii (`rx`,`ry`). The result spans exactly `2r+1` pixels. The outline is closed and 1px wide with no gaps. A zero radius draws a line |
| `sprite_flood_fill` | Scanline fill from (`x`,`y`). Only this layer counts, and empty cells count as a color. `contiguous=false` replaces that color everywhere on the layer |
| `sprite_get_pixels` | Reads pixels back as `list` (`[x, y, c]` triples, up to 20,000) or as a `grid` of hex rows (the region must be 64x64 or smaller) |

### Palette (3)

| Tool | Description |
|------|-------------|
| `sprite_set_palette` | Takes a `preset` or a `colors` list `[{index, name?, rgba}]` with unique indices. Optional `enforce` and `palette_name`. Reports how many pixels now have an undefined color |
| `sprite_swap_palette` | `index_map` `{"old": new}`. All mappings apply at once, so swaps work |
| `sprite_get_palette` | Returns the colors, whether the palette is enforced, and the available presets |

### Sprites & Animations (6)

| Tool | Description |
|------|-------------|
| `sprite_define_sprite` | A grid region (`grid_x`, `grid_y`, `width_cells`, `height_cells`) with `anchor_x`/`anchor_y`, `hitbox`, and `tags`. It must fit on the canvas. Reusing a name updates that sprite |
| `sprite_remove_sprite` | Removes a sprite and its frames from animations. Reports which animations were affected |
| `sprite_list_sprites` | Lists sprites with their pixel bounds, anchor, hitbox, and tags |
| `sprite_define_animation` | `anim_name` and `frames` `[{sprite_id, duration_ms?}]`, plus `loop_mode` (`loop`/`once`/`ping_pong`) and `tags`. Every frame must reference an existing sprite. Reusing a name replaces that animation |
| `sprite_list_animations` | Lists animations with their frames (sprite name and duration) and total duration |
| `sprite_remove_animation` | Removes an animation |

### Transform (1)

| Tool | Description |
|------|-------------|
| `sprite_transform` | `flip_h`, `flip_v`, `rotate_90_cw`, `rotate_90_ccw`, `rotate_180`, or `shift` (`shift_dx`/`shift_dy`, plus `wrap`). Works on a whole layer or an optional `region`. Reports moved and dropped pixels |

### Render & Export (5)

Every file lands in the output directory. `filename` must be a plain file name: a path separator, `..` or drive prefix is rejected. When a name is not given, the server builds one from the project and sprite names, with unsafe characters replaced. Images are also returned inline (base64) unless `inline=false` or the image is larger than 4 MB.

| Tool | Description |
|------|-------------|
| `sprite_render` | Renders the whole sheet or a `region` at `scale` 1-64, with optional `overlays` (`grid_lines`, `bounding_boxes`, `anchors`, `hitboxes`, `sprite_names`) |
| `sprite_render_sprite` | Renders one sprite, with optional scale and overlays |
| `sprite_render_animation_frames` | Writes `<project>_<anim>_NNN.png` for each frame and returns the timing. `strip=true` also writes a horizontal strip |
| `sprite_export_gif` | Animated GIF that follows the durations and loop mode (`ping_pong` plays forward, then backward) |
| `sprite_export_atlas` | Writes `<filename>.png` and `<filename>.json`. The JSON holds each sprite's frame rectangle, anchor, normalized pivot, hitbox and tags, plus the animations. Coordinates are scaled |

### Undo (1)

| Tool | Description |
|------|-------------|
| `sprite_undo` | Undoes (or redoes with `redo: true`) up to `steps` edits and returns their labels. Covers every mutating tool |

### Import & Cleanup (2)

| Tool | Description |
|------|-------------|
| `sprite_import_image` | Creates a project from an image. Options: `max_width`/`max_height` (nearest-neighbor downscale), `palette_preset` or `max_colors` for extraction, `background_color` plus `bg_tolerance`, `alpha_threshold`, `trim_fringe` settings, and `cell_width`/`cell_height` |
| `sprite_trim_edges` | Strips bright anti-aliasing fringe from one layer or from every unlocked layer (`luma_threshold`, `passes` 1-10) |

## Palette Presets

| Preset | Colors | Style |
|--------|--------|-------|
| `pico8` | 16 | PICO-8 fantasy console palette |
| `gameboy` | 4 | Game Boy 4-shade green |
| `nes` | 24 | NES-inspired subset |
| `snes` | 32 | SNES-inspired, with skin tones and a transparent entry (index 31) |
| `endesga32` | 32 | ENDESGA 32 |

A project created without a preset starts with `[0 transparent, 1 black, 2 white]`, and that palette is not enforced. Presets and explicit color lists are enforced by default. That means drawing an undefined index is an error for primitives and a counted skip for `sprite_set_pixels`. When a palette is not enforced, any index can be drawn, but indices with no palette entry render transparent.

## Project File Format

`sprite_save_project` writes JSON with `"format_version": 2`. Each layer's `pixels` field is a sorted array of `[x, y, color_index]` triples. The loader also reads:
- older files that have no `format_version`
- the legacy `{"x,y": index}` pixel map

Files from a newer format version are rejected. Undo history is never saved.

## Architecture

- `engine.rs`: project, layer, drawing, transform, palette, sprite and animation operations, plus the undo model. Each edit runs through `engine::edit`, which snapshots the editable state first. On error it restores that snapshot, so edits are atomic. Pixel maps sit behind `Arc`, which makes a snapshot O(layers): only layers that actually change get copied.
- `geometry.rs`: pure raster algorithms that clip to the canvas. A huge rectangle or radius cannot hang the server.
- `render.rs` / `font.rs`: compositing (a palette lookup table and f32 W3C blend math), overlays drawn after scaling, a built-in 3x5 label font, and PNG/GIF encoding.
- `persist.rs`: versioned save/load with validation and repair, and the atlas metadata.
- `args.rs`: typed argument parsing that accepts loosely typed input. Errors name the JSON path.
- `files.rs`: filename validation and atomic writes (a temp file, then rename).
- PNG/GIF encoding and image decoding run on the blocking thread pool. The project lock is released before files are written.

## Limits

| Limit | Value |
|-------|-------|
| Canvas | 4096 px per side, 4,194,304 px area |
| Render output | 16384 px per side, 64 Mpx total, scale 1-64 |
| Undo | 50 steps per project, and history keeps at most about 8M pixel entries |
| Import source | 16384 px per side, 512 MB decoder allocation |
| Project file load | 256 MB |
| `sprite_get_pixels` | 20,000 pixels (list), 64x64 (grid) |
| Drawing coordinates / sizes | absolute value at most 1,048,576 (then clipped to the canvas) |

## Known Limitations

- Projects live in memory. Save them with `sprite_save_project` before the server stops.
- Pixels are palette indices. A merge copies indices, so the top layer's opacity and blend mode are not baked in (the tool warns). Blend modes only apply when rendering.
- Flood fill only looks at the target layer, not at the composited image.
- An ellipse is described by a center and radii, so its size is always odd (`2r+1`).
- A GIF has 1-bit transparency and 10 ms timing resolution. Many viewers slow down any frame shorter than 20 ms.
- `sprite_trim_edges` and import fringe trimming also remove isolated single pixels. They are meant for imported art, not hand-placed pixels.
- In Docker, only `/home` is mounted (read-only) for `sprite_import_image`, and files are written to `/output`, which maps to `./outputs/mcp-sprites` on the host.

## Docker

```bash
docker compose --profile services build mcp-sprite-sheet
docker compose --profile services up mcp-sprite-sheet            # HTTP on 8027
docker compose --profile services run --rm -T mcp-sprite-sheet \
  mcp-sprite-sheet --mode stdio --output /output                 # STDIO (as in .mcp.json)
```

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline, uses temp directories only
cargo build --release
# or from the repo root: automation-cli ci run sprite-full
```
