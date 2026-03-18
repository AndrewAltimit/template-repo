# Sprite Sheet MCP Server (Rust)

> A Model Context Protocol server for programmatic pixel art and sprite sheet creation, built in Rust with palette-indexed sparse pixel storage and nearest-neighbor rendering.

## Overview

This MCP server provides:
- Full sprite sheet project management (create, save, load)
- Layer system with blend modes, opacity, and z-ordering
- Drawing primitives (batch pixels, lines, rectangles, ellipses, flood fill)
- Palette management with 5 built-in presets (pico8, gameboy, nes, snes, endesga32)
- Sprite region and animation sequence definitions with anchors, hitboxes, and frame timing
- Transform operations (flip, rotate, shift)
- PNG rendering with nearest-neighbor scaling and debug overlays (grid, bounding boxes, anchors, hitboxes)
- Undo/redo via layer snapshots
- Image import: convert reference images to editable sprite projects with auto-palette extraction, background color removal, and anti-aliasing fringe trimming
- Edge cleanup tool for progressive fringe removal on existing projects

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-sprite-sheet --mode standalone --port 8027

# Run in STDIO mode (for Claude Code)
./target/release/mcp-sprite-sheet --mode stdio

# Specify output directory
./target/release/mcp-sprite-sheet --mode stdio --output /tmp/sprites

# Test health
curl http://localhost:8027/health
```

## Available Tools (31)

### Project Management (4)

| Tool | Description |
|------|-------------|
| `sprite_create_project` | Create a new project with canvas size, grid config, and optional palette preset |
| `sprite_save_project` | Serialize project to JSON for persistence |
| `sprite_load_project` | Load project from JSON data |
| `sprite_project_status` | Get project summary (dimensions, layers, sprites, animations, palette) |

### Layers (7)

| Tool | Description |
|------|-------------|
| `sprite_add_layer` | Add a new layer at optional z-order |
| `sprite_remove_layer` | Remove a layer by ID |
| `sprite_update_layer` | Update properties (name, visibility, opacity, blend mode, locked, z-order) |
| `sprite_duplicate_layer` | Duplicate a layer with all pixel data |
| `sprite_merge_layers` | Merge top layer onto bottom layer |
| `sprite_clear_layer` | Clear all pixels or a rectangular region |
| `sprite_list_layers` | List all layers with properties |

### Drawing (5)

| Tool | Description |
|------|-------------|
| `sprite_set_pixels` | Batch set pixels (array of {x, y, color_index}) |
| `sprite_draw_line` | Bresenham line between two points |
| `sprite_draw_rect` | Rectangle (outline or filled) |
| `sprite_draw_ellipse` | Ellipse (outline or filled) |
| `sprite_flood_fill` | Scanline flood fill from a starting point |

### Palette (3)

| Tool | Description |
|------|-------------|
| `sprite_set_palette` | Set palette from preset or explicit color list |
| `sprite_swap_palette` | Remap palette indices across all layers |
| `sprite_get_palette` | Return current palette with all colors |

### Sprites & Animations (5)

| Tool | Description |
|------|-------------|
| `sprite_define_sprite` | Define a named sprite region with anchor, hitbox, and tags |
| `sprite_remove_sprite` | Remove a sprite definition |
| `sprite_list_sprites` | List all sprite definitions |
| `sprite_define_animation` | Define animation as frame sequence with timing |
| `sprite_list_animations` | List all animations |

### Transform (1)

| Tool | Description |
|------|-------------|
| `sprite_transform` | flip_h, flip_v, rotate_90_cw, rotate_90_ccw, rotate_180, shift |

### Render (3)

| Tool | Description |
|------|-------------|
| `sprite_render` | Render full sheet or region as PNG with optional overlays and scaling |
| `sprite_render_sprite` | Render a single sprite as standalone PNG |
| `sprite_render_animation_frames` | Render all animation frames as individual PNGs with timing metadata |

### Import & Cleanup (2)

| Tool | Description |
|------|-------------|
| `sprite_import_image` | Import reference image (PNG/JPEG/WebP/GIF) as editable sprite project with auto-palette extraction, background removal, and fringe trimming |
| `sprite_trim_edges` | Remove anti-aliasing fringe from sprite edges using luminance and relative brightness tests |

### Undo (1)

| Tool | Description |
|------|-------------|
| `sprite_undo` | Undo last drawing operation, or redo with `redo: true` |

## Palette Presets

| Preset | Colors | Style |
|--------|--------|-------|
| `pico8` | 16 | PICO-8 fantasy console palette |
| `gameboy` | 4 | Game Boy 4-shade green |
| `nes` | 24 | NES-inspired subset |
| `snes` | 32 | SNES-inspired with skin tones |
| `endesga32` | 32 | ENDESGA 32-color pixel art palette |

## Architecture

- **Sparse pixel storage**: `HashMap<(u32, u32), u8>` mapping coordinates to palette indices
- **Palette-indexed**: colors stored as indices, enabling palette swaps and enforcement
- **In-memory project store**: `Arc<RwLock<HashMap<String, SpriteProject>>>` shared across tools
- **Nearest-neighbor scaling**: preserves pixel art crispness at any zoom level
- **Layer compositing**: alpha-over blending with Normal, Multiply, Screen, Overlay modes

## Docker

```bash
# Build
docker compose --profile services build mcp-sprite-sheet

# Run standalone
docker compose --profile services up mcp-sprite-sheet

# STDIO mode (Claude Code)
docker compose --profile services run --rm -T mcp-sprite-sheet mcp-sprite-sheet --mode stdio --output /output
```

Port 8027. Output volume: `./outputs/mcp-sprites:/output`. Read-only `/home` mount for image imports.
