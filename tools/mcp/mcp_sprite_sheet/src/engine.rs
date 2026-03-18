//! Core engine: project CRUD, layer ops, drawing, flood fill, transforms, undo.

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::palette;
use crate::types::*;

const MAX_UNDO: usize = 50;

/// Pixel data map type alias
type PixelMap = HashMap<(u32, u32), u8>;

/// Shared project state across all tools
pub type ProjectStore = Arc<RwLock<HashMap<String, SpriteProject>>>;

/// Create a new empty project store
pub fn new_store() -> ProjectStore {
    Arc::new(RwLock::new(HashMap::new()))
}

// ---------------------------------------------------------------------------
// Project management
// ---------------------------------------------------------------------------

#[allow(clippy::too_many_arguments)]
pub fn create_project(
    name: &str,
    width: u32,
    height: u32,
    cell_width: u32,
    cell_height: u32,
    padding: u32,
    margin: u32,
    background_color: [u8; 4],
    palette_preset: Option<&str>,
) -> Result<SpriteProject, String> {
    if width == 0 || height == 0 {
        return Err("Canvas dimensions must be > 0".to_string());
    }
    if cell_width == 0 || cell_height == 0 {
        return Err("Grid cell dimensions must be > 0".to_string());
    }

    let pal = match palette_preset {
        Some(preset) => palette::from_preset(preset)
            .ok_or_else(|| format!("Unknown palette preset: {preset}"))?,
        None => Palette {
            name: "custom".to_string(),
            colors: vec![
                PaletteColor {
                    index: 0,
                    name: "transparent".to_string(),
                    rgba: [0, 0, 0, 0],
                },
                PaletteColor {
                    index: 1,
                    name: "black".to_string(),
                    rgba: [0, 0, 0, 255],
                },
                PaletteColor {
                    index: 2,
                    name: "white".to_string(),
                    rgba: [255, 255, 255, 255],
                },
            ],
            enforce: false,
        },
    };

    Ok(SpriteProject {
        name: name.to_string(),
        canvas: Canvas {
            width,
            height,
            background_color,
        },
        grid: Grid {
            cell_width,
            cell_height,
            padding,
            margin,
        },
        palette: pal,
        layers: Vec::new(),
        sprites: Vec::new(),
        animations: Vec::new(),
        undo_stack: Vec::new(),
        redo_stack: Vec::new(),
    })
}

// ---------------------------------------------------------------------------
// Layer operations
// ---------------------------------------------------------------------------

pub fn add_layer(project: &mut SpriteProject, name: &str, z_order: Option<i32>) -> String {
    let id = uuid::Uuid::new_v4().to_string();
    let z =
        z_order.unwrap_or_else(|| project.layers.iter().map(|l| l.z_order).max().unwrap_or(-1) + 1);
    project.layers.push(Layer {
        id: id.clone(),
        name: name.to_string(),
        visible: true,
        opacity: 255,
        blend_mode: BlendMode::Normal,
        locked: false,
        z_order: z,
        pixels: HashMap::new(),
    });
    id
}

pub fn remove_layer(project: &mut SpriteProject, layer_id: &str) -> Result<(), String> {
    let idx = project
        .layers
        .iter()
        .position(|l| l.id == layer_id)
        .ok_or_else(|| format!("Layer not found: {layer_id}"))?;
    project.layers.remove(idx);
    Ok(())
}

pub fn find_layer<'a>(project: &'a SpriteProject, layer_id: &str) -> Result<&'a Layer, String> {
    project
        .layers
        .iter()
        .find(|l| l.id == layer_id)
        .ok_or_else(|| format!("Layer not found: {layer_id}"))
}

pub fn find_layer_mut<'a>(
    project: &'a mut SpriteProject,
    layer_id: &str,
) -> Result<&'a mut Layer, String> {
    project
        .layers
        .iter_mut()
        .find(|l| l.id == layer_id)
        .ok_or_else(|| format!("Layer not found: {layer_id}"))
}

pub fn duplicate_layer(project: &mut SpriteProject, layer_id: &str) -> Result<String, String> {
    let source = find_layer(project, layer_id)?.clone();
    let new_id = uuid::Uuid::new_v4().to_string();
    let new_layer = Layer {
        id: new_id.clone(),
        name: format!("{} copy", source.name),
        z_order: source.z_order + 1,
        ..source
    };
    project.layers.push(new_layer);
    Ok(new_id)
}

pub fn merge_layers(
    project: &mut SpriteProject,
    top_id: &str,
    bottom_id: &str,
) -> Result<(), String> {
    let top_idx = project
        .layers
        .iter()
        .position(|l| l.id == top_id)
        .ok_or_else(|| format!("Top layer not found: {top_id}"))?;
    let top = project.layers[top_idx].clone();

    let bottom = find_layer_mut(project, bottom_id)?;

    // Merge top pixels onto bottom (top wins on overlap)
    for (&coord, &color_idx) in &top.pixels {
        bottom.pixels.insert(coord, color_idx);
    }

    // Remove the top layer
    project.layers.remove(top_idx);
    Ok(())
}

pub fn clear_layer(
    project: &mut SpriteProject,
    layer_id: &str,
    region: Option<(u32, u32, u32, u32)>,
) -> Result<(), String> {
    let layer = find_layer_mut(project, layer_id)?;
    if layer.locked {
        return Err("Layer is locked".to_string());
    }
    match region {
        Some((x, y, w, h)) => {
            layer
                .pixels
                .retain(|&(px, py), _| px < x || px >= x + w || py < y || py >= y + h);
        },
        None => {
            layer.pixels.clear();
        },
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Undo / Redo
// ---------------------------------------------------------------------------

fn push_undo(project: &mut SpriteProject, layer_id: &str) {
    if let Ok(layer) = find_layer(project, layer_id) {
        let snapshot = UndoSnapshot {
            layer_id: layer_id.to_string(),
            pixels: layer.pixels.clone(),
        };
        project.undo_stack.push(snapshot);
        if project.undo_stack.len() > MAX_UNDO {
            project.undo_stack.remove(0);
        }
        project.redo_stack.clear();
    }
}

pub fn undo(project: &mut SpriteProject) -> Result<(), String> {
    let snapshot = project
        .undo_stack
        .pop()
        .ok_or_else(|| "Nothing to undo".to_string())?;

    // Save current state to redo
    if let Ok(layer) = find_layer(project, &snapshot.layer_id) {
        let redo = UndoSnapshot {
            layer_id: snapshot.layer_id.clone(),
            pixels: layer.pixels.clone(),
        };
        project.redo_stack.push(redo);
    }

    // Restore snapshot
    if let Ok(layer) = find_layer_mut(project, &snapshot.layer_id) {
        layer.pixels = snapshot.pixels;
    }
    Ok(())
}

pub fn redo(project: &mut SpriteProject) -> Result<(), String> {
    let snapshot = project
        .redo_stack
        .pop()
        .ok_or_else(|| "Nothing to redo".to_string())?;

    // Save current state to undo (no clear of redo this time)
    if let Ok(layer) = find_layer(project, &snapshot.layer_id) {
        let undo_snap = UndoSnapshot {
            layer_id: snapshot.layer_id.clone(),
            pixels: layer.pixels.clone(),
        };
        project.undo_stack.push(undo_snap);
    }

    if let Ok(layer) = find_layer_mut(project, &snapshot.layer_id) {
        layer.pixels = snapshot.pixels;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Drawing operations
// ---------------------------------------------------------------------------

pub fn set_pixels(
    project: &mut SpriteProject,
    layer_id: &str,
    pixels: &[(u32, u32, u8)],
) -> Result<usize, String> {
    push_undo(project, layer_id);
    let w = project.canvas.width;
    let h = project.canvas.height;
    let enforce = project.palette.enforce;
    // Pre-collect valid indices to avoid borrowing palette while layer is mutably borrowed
    let valid_indices: Vec<bool> = if enforce {
        pixels
            .iter()
            .map(|&(_, _, ci)| project.palette.is_valid_index(ci))
            .collect()
    } else {
        vec![true; pixels.len()]
    };
    let layer = find_layer_mut(project, layer_id)?;
    if layer.locked {
        return Err("Layer is locked".to_string());
    }
    let mut count = 0;
    for (i, &(x, y, color_idx)) in pixels.iter().enumerate() {
        if x < w && y < h && valid_indices[i] {
            layer.pixels.insert((x, y), color_idx);
            count += 1;
        }
    }
    Ok(count)
}

/// Bresenham's line algorithm
pub fn draw_line(
    project: &mut SpriteProject,
    layer_id: &str,
    x0: i32,
    y0: i32,
    x1: i32,
    y1: i32,
    color_idx: u8,
) -> Result<usize, String> {
    let points = bresenham_line(x0, y0, x1, y1);
    let pixels: Vec<(u32, u32, u8)> = points
        .into_iter()
        .filter(|&(x, y)| x >= 0 && y >= 0)
        .map(|(x, y)| (x as u32, y as u32, color_idx))
        .collect();
    set_pixels(project, layer_id, &pixels)
}

#[allow(clippy::too_many_arguments)]
pub fn draw_rect(
    project: &mut SpriteProject,
    layer_id: &str,
    x: u32,
    y: u32,
    w: u32,
    h: u32,
    color_idx: u8,
    filled: bool,
) -> Result<usize, String> {
    let mut pixels = Vec::new();
    for py in y..y.saturating_add(h) {
        for px in x..x.saturating_add(w) {
            if filled || px == x || px == x + w - 1 || py == y || py == h + y - 1 {
                pixels.push((px, py, color_idx));
            }
        }
    }
    set_pixels(project, layer_id, &pixels)
}

#[allow(clippy::too_many_arguments)]
pub fn draw_ellipse(
    project: &mut SpriteProject,
    layer_id: &str,
    cx: i32,
    cy: i32,
    rx: i32,
    ry: i32,
    color_idx: u8,
    filled: bool,
) -> Result<usize, String> {
    let points = midpoint_ellipse(cx, cy, rx, ry, filled);
    let pixels: Vec<(u32, u32, u8)> = points
        .into_iter()
        .filter(|&(x, y)| x >= 0 && y >= 0)
        .map(|(x, y)| (x as u32, y as u32, color_idx))
        .collect();
    set_pixels(project, layer_id, &pixels)
}

/// Scanline flood fill
pub fn flood_fill(
    project: &mut SpriteProject,
    layer_id: &str,
    start_x: u32,
    start_y: u32,
    fill_color: u8,
) -> Result<usize, String> {
    push_undo(project, layer_id);
    let w = project.canvas.width;
    let h = project.canvas.height;

    let layer_idx = project
        .layers
        .iter()
        .position(|l| l.id == layer_id)
        .ok_or_else(|| format!("Layer not found: {layer_id}"))?;

    if project.layers[layer_idx].locked {
        return Err("Layer is locked".to_string());
    }

    let target_color = project.layers[layer_idx]
        .pixels
        .get(&(start_x, start_y))
        .copied();

    if target_color == Some(fill_color) {
        return Ok(0);
    }

    let mut stack = vec![(start_x, start_y)];
    let mut filled = 0;

    while let Some((x, y)) = stack.pop() {
        if x >= w || y >= h {
            continue;
        }
        let current = project.layers[layer_idx].pixels.get(&(x, y)).copied();
        if current != target_color {
            continue;
        }

        project.layers[layer_idx].pixels.insert((x, y), fill_color);
        filled += 1;

        if x > 0 {
            stack.push((x - 1, y));
        }
        if x + 1 < w {
            stack.push((x + 1, y));
        }
        if y > 0 {
            stack.push((x, y - 1));
        }
        if y + 1 < h {
            stack.push((x, y + 1));
        }
    }

    Ok(filled)
}

// ---------------------------------------------------------------------------
// Transform operations
// ---------------------------------------------------------------------------

pub fn transform_layer(
    project: &mut SpriteProject,
    layer_id: &str,
    op: TransformOp,
    shift_dx: Option<i32>,
    shift_dy: Option<i32>,
    region: Option<(u32, u32, u32, u32)>,
) -> Result<(), String> {
    push_undo(project, layer_id);
    let w = project.canvas.width;
    let h = project.canvas.height;
    let layer = find_layer_mut(project, layer_id)?;
    if layer.locked {
        return Err("Layer is locked".to_string());
    }

    // Extract pixels to transform (optionally within region)
    let (to_transform, to_keep): (PixelMap, PixelMap) = match region {
        Some((rx, ry, rw, rh)) => {
            let mut inside = HashMap::new();
            let mut outside = HashMap::new();
            for (&(px, py), &ci) in &layer.pixels {
                if px >= rx && px < rx + rw && py >= ry && py < ry + rh {
                    inside.insert((px, py), ci);
                } else {
                    outside.insert((px, py), ci);
                }
            }
            (inside, outside)
        },
        None => (layer.pixels.clone(), HashMap::new()),
    };

    let (bx, by, bw, bh) = match region {
        Some(r) => r,
        None => (0, 0, w, h),
    };

    let transformed: HashMap<(u32, u32), u8> = to_transform
        .iter()
        .filter_map(|(&(px, py), &ci)| {
            let (nx, ny) = match op {
                TransformOp::FlipH => (bx + (bw - 1 - (px - bx)), py),
                TransformOp::FlipV => (px, by + (bh - 1 - (py - by))),
                TransformOp::Rotate180 => (bx + (bw - 1 - (px - bx)), by + (bh - 1 - (py - by))),
                TransformOp::Rotate90Cw => {
                    let rel_x = px - bx;
                    let rel_y = py - by;
                    (bx + (bh - 1 - rel_y), by + rel_x)
                },
                TransformOp::Rotate90Ccw => {
                    let rel_x = px - bx;
                    let rel_y = py - by;
                    (bx + rel_y, by + (bw - 1 - rel_x))
                },
                TransformOp::Shift => {
                    let dx = shift_dx.unwrap_or(0);
                    let dy = shift_dy.unwrap_or(0);
                    let nx = px as i64 + dx as i64;
                    let ny = py as i64 + dy as i64;
                    if nx < 0 || ny < 0 {
                        return None;
                    }
                    (nx as u32, ny as u32)
                },
            };
            if nx < w && ny < h {
                Some(((nx, ny), ci))
            } else {
                None
            }
        })
        .collect();

    let mut result = to_keep;
    result.extend(transformed);
    layer.pixels = result;
    Ok(())
}

// ---------------------------------------------------------------------------
// Palette operations
// ---------------------------------------------------------------------------

/// Swap palette: remap all pixel indices across all layers
pub fn swap_palette(project: &mut SpriteProject, index_map: &HashMap<u8, u8>) {
    for layer in &mut project.layers {
        for ci in layer.pixels.values_mut() {
            if let Some(&new_idx) = index_map.get(ci) {
                *ci = new_idx;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

fn bresenham_line(x0: i32, y0: i32, x1: i32, y1: i32) -> Vec<(i32, i32)> {
    let mut points = Vec::new();
    let dx = (x1 - x0).abs();
    let dy = -(y1 - y0).abs();
    let sx = if x0 < x1 { 1 } else { -1 };
    let sy = if y0 < y1 { 1 } else { -1 };
    let mut err = dx + dy;
    let mut x = x0;
    let mut y = y0;

    loop {
        points.push((x, y));
        if x == x1 && y == y1 {
            break;
        }
        let e2 = 2 * err;
        if e2 >= dy {
            err += dy;
            x += sx;
        }
        if e2 <= dx {
            err += dx;
            y += sy;
        }
    }
    points
}

fn midpoint_ellipse(cx: i32, cy: i32, rx: i32, ry: i32, filled: bool) -> Vec<(i32, i32)> {
    let mut points = Vec::new();
    if rx <= 0 || ry <= 0 {
        return points;
    }

    let mut x = 0i32;
    let mut y = ry;
    let rx2 = (rx as i64) * (rx as i64);
    let ry2 = (ry as i64) * (ry as i64);
    let mut px = 0i64;
    let mut py = 2 * rx2 * (y as i64);

    // Region 1
    let mut p = ry2 - rx2 * (ry as i64) + rx2 / 4;
    while px < py {
        plot_ellipse_points(&mut points, cx, cy, x, y, filled);
        x += 1;
        px += 2 * ry2;
        if p < 0 {
            p += ry2 + px;
        } else {
            y -= 1;
            py -= 2 * rx2;
            p += ry2 + px - py;
        }
    }

    // Region 2
    p = ry2 * ((x as i64) * (x as i64) + (x as i64)) + rx2 * ((y as i64 - 1) * (y as i64 - 1))
        - rx2 * ry2
        + ry2 / 4;
    while y >= 0 {
        plot_ellipse_points(&mut points, cx, cy, x, y, filled);
        y -= 1;
        py -= 2 * rx2;
        if p > 0 {
            p += rx2 - py;
        } else {
            x += 1;
            px += 2 * ry2;
            p += rx2 - py + px;
        }
    }
    points
}

fn plot_ellipse_points(
    points: &mut Vec<(i32, i32)>,
    cx: i32,
    cy: i32,
    x: i32,
    y: i32,
    filled: bool,
) {
    if filled {
        for fx in (cx - x)..=(cx + x) {
            points.push((fx, cy + y));
            points.push((fx, cy - y));
        }
    } else {
        points.push((cx + x, cy + y));
        points.push((cx - x, cy + y));
        points.push((cx + x, cy - y));
        points.push((cx - x, cy - y));
    }
}

// ---------------------------------------------------------------------------
// Image import
// ---------------------------------------------------------------------------

/// Euclidean distance in RGB space (ignoring alpha for matching)
fn color_distance_rgb(a: [u8; 4], b: [u8; 4]) -> u32 {
    let dr = a[0] as i32 - b[0] as i32;
    let dg = a[1] as i32 - b[1] as i32;
    let db = a[2] as i32 - b[2] as i32;
    (dr * dr + dg * dg + db * db) as u32
}

/// Find the nearest opaque palette color index for an RGBA value
pub fn nearest_palette_index(rgba: [u8; 4], palette: &Palette) -> Option<u8> {
    palette
        .colors
        .iter()
        .filter(|c| c.rgba[3] > 0)
        .min_by_key(|c| color_distance_rgb(rgba, c.rgba))
        .map(|c| c.index)
}

/// Extract a palette from an image by frequency (most common colors first, up to max_colors)
pub fn extract_palette_from_image(
    img: &image::RgbaImage,
    max_colors: usize,
    alpha_threshold: u8,
) -> Palette {
    let mut freq: HashMap<[u8; 4], usize> = HashMap::new();
    for pixel in img.pixels() {
        if pixel.0[3] >= alpha_threshold {
            *freq.entry(pixel.0).or_insert(0) += 1;
        }
    }

    let mut colors: Vec<([u8; 4], usize)> = freq.into_iter().collect();
    colors.sort_by(|a, b| b.1.cmp(&a.1));
    colors.truncate(max_colors.min(256));

    let palette_colors: Vec<PaletteColor> = colors
        .iter()
        .enumerate()
        .map(|(i, (rgba, _))| PaletteColor {
            index: i as u8,
            name: format!("color_{i}"),
            rgba: *rgba,
        })
        .collect();

    Palette {
        name: "extracted".to_string(),
        colors: palette_colors,
        enforce: false,
    }
}

/// Map every pixel in an image to the nearest palette color, returning sparse pixel data
pub fn import_image_to_pixels(
    img: &image::RgbaImage,
    palette: &Palette,
    alpha_threshold: u8,
) -> (PixelMap, usize) {
    let mut pixels = HashMap::new();
    let mut count = 0;

    for (x, y, pixel) in img.enumerate_pixels() {
        if pixel.0[3] >= alpha_threshold
            && let Some(idx) = nearest_palette_index(pixel.0, palette)
        {
            pixels.insert((x, y), idx);
            count += 1;
        }
    }

    (pixels, count)
}

/// Perceived luminance (BT.601) of an RGBA color
fn pixel_luma(rgba: [u8; 4]) -> u32 {
    (rgba[0] as u32 * 299 + rgba[1] as u32 * 587 + rgba[2] as u32 * 114) / 1000
}

/// Collect 4-connected filled neighbors for a pixel
fn filled_neighbors(
    x: u32,
    y: u32,
    pixels: &PixelMap,
    canvas_w: u32,
    canvas_h: u32,
) -> (Vec<u8>, bool) {
    let mut neighbors = Vec::new();
    let mut has_empty = false;
    for &(dx, dy) in &[(0i32, -1i32), (0, 1), (-1, 0), (1, 0)] {
        let nx = x as i32 + dx;
        let ny = y as i32 + dy;
        if nx < 0 || ny < 0 || nx >= canvas_w as i32 || ny >= canvas_h as i32 {
            has_empty = true;
            continue;
        }
        match pixels.get(&(nx as u32, ny as u32)) {
            Some(&ci) => neighbors.push(ci),
            None => has_empty = true,
        }
    }
    (neighbors, has_empty)
}

/// Remove border pixels that look like anti-aliasing fringe.
///
/// Uses a two-pronged approach:
/// 1. **Absolute luma**: edge pixels with luminance >= `luma_threshold` are stripped
///    (catches white/near-white fringe).
/// 2. **Relative brightness**: edge pixels that are significantly brighter than their
///    filled neighbors are stripped (catches colored fringe like light teal, beige, etc.).
///
/// `luma_threshold`: absolute luminance cutoff (0-255). Pixels above this on edges are removed.
/// `passes`: number of erosion passes (each pass exposes new edges).
pub fn trim_border_fringe(
    pixels: &mut PixelMap,
    palette: &Palette,
    luma_threshold: u8,
    passes: u32,
    canvas_w: u32,
    canvas_h: u32,
) -> usize {
    let mut total_removed = 0;

    for _ in 0..passes {
        let to_remove: Vec<(u32, u32)> = pixels
            .iter()
            .filter(|&(&(x, y), &ci)| {
                let (neighbor_indices, has_empty) =
                    filled_neighbors(x, y, pixels, canvas_w, canvas_h);

                // Must be an edge pixel (at least one empty/transparent neighbor)
                if !has_empty {
                    return false;
                }

                let Some(rgba) = palette.get_color(ci) else {
                    return false;
                };
                let my_luma = pixel_luma(rgba);

                // Test 1: absolute luma (catches white/near-white fringe)
                if my_luma >= luma_threshold as u32 {
                    return true;
                }

                // Test 2: relative brightness vs filled neighbors
                // If this edge pixel is much brighter than its interior neighbors,
                // it's likely an anti-aliasing blend toward the (white) background.
                if neighbor_indices.is_empty() {
                    // Isolated pixel with no filled neighbors -- likely fringe
                    return true;
                }

                let avg_neighbor_luma: u32 = neighbor_indices
                    .iter()
                    .filter_map(|&ni| palette.get_color(ni))
                    .map(pixel_luma)
                    .sum::<u32>()
                    / neighbor_indices.len() as u32;

                // Edge pixel is significantly brighter than its neighbors.
                // Use the caller's luma_threshold as the delta when it's < 128,
                // otherwise default to 25 luma units.
                let delta = if luma_threshold < 128 {
                    luma_threshold as u32
                } else {
                    25
                };
                my_luma > avg_neighbor_luma + delta
            })
            .map(|(&coord, _)| coord)
            .collect();

        if to_remove.is_empty() {
            break;
        }

        total_removed += to_remove.len();
        for coord in &to_remove {
            pixels.remove(coord);
        }
    }

    total_removed
}

// ---------------------------------------------------------------------------
// Sprite / Animation helpers
// ---------------------------------------------------------------------------

/// Get pixel bounds of a sprite in canvas coordinates
pub fn sprite_pixel_bounds(project: &SpriteProject, sprite: &SpriteDef) -> (u32, u32, u32, u32) {
    let g = &project.grid;
    let px = g.margin + sprite.grid_x * (g.cell_width + g.padding);
    let py = g.margin + sprite.grid_y * (g.cell_height + g.padding);
    let pw = sprite.width_cells * g.cell_width + (sprite.width_cells.saturating_sub(1)) * g.padding;
    let ph =
        sprite.height_cells * g.cell_height + (sprite.height_cells.saturating_sub(1)) * g.padding;
    (px, py, pw, ph)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn test_project() -> SpriteProject {
        create_project("test", 16, 16, 8, 8, 0, 0, [0, 0, 0, 0], Some("pico8")).unwrap()
    }

    #[test]
    fn test_create_project() {
        let p = test_project();
        assert_eq!(p.canvas.width, 16);
        assert_eq!(p.palette.colors.len(), 16);
    }

    #[test]
    fn test_add_remove_layer() {
        let mut p = test_project();
        let id = add_layer(&mut p, "Layer 1", None);
        assert_eq!(p.layers.len(), 1);
        remove_layer(&mut p, &id).unwrap();
        assert_eq!(p.layers.len(), 0);
    }

    #[test]
    fn test_set_pixels() {
        let mut p = test_project();
        let id = add_layer(&mut p, "Layer 1", None);
        let count = set_pixels(&mut p, &id, &[(0, 0, 1), (1, 1, 2), (100, 100, 1)]).unwrap();
        assert_eq!(count, 2); // third pixel out of bounds
        assert_eq!(find_layer(&p, &id).unwrap().pixels.len(), 2);
    }

    #[test]
    fn test_bresenham_line() {
        let pts = bresenham_line(0, 0, 5, 0);
        assert_eq!(pts.len(), 6);
    }

    #[test]
    fn test_flood_fill() {
        let mut p = test_project();
        let id = add_layer(&mut p, "Layer 1", None);
        let filled = flood_fill(&mut p, &id, 0, 0, 1).unwrap();
        // Should fill all 16x16 = 256 pixels (all were None/target)
        assert_eq!(filled, 256);
    }

    #[test]
    fn test_undo_redo() {
        let mut p = test_project();
        let id = add_layer(&mut p, "Layer 1", None);
        set_pixels(&mut p, &id, &[(0, 0, 1)]).unwrap();
        assert_eq!(find_layer(&p, &id).unwrap().pixels.len(), 1);

        undo(&mut p).unwrap();
        assert_eq!(find_layer(&p, &id).unwrap().pixels.len(), 0);

        redo(&mut p).unwrap();
        assert_eq!(find_layer(&p, &id).unwrap().pixels.len(), 1);
    }

    #[test]
    fn test_transform_flip_h() {
        let mut p = test_project();
        let id = add_layer(&mut p, "Layer 1", None);
        set_pixels(&mut p, &id, &[(0, 0, 1)]).unwrap();
        transform_layer(&mut p, &id, TransformOp::FlipH, None, None, None).unwrap();
        let layer = find_layer(&p, &id).unwrap();
        // (0,0) flipped horizontally in 16-wide canvas -> (15,0)
        assert!(layer.pixels.contains_key(&(15, 0)));
        assert!(!layer.pixels.contains_key(&(0, 0)));
    }

    #[test]
    fn test_merge_layers() {
        let mut p = test_project();
        let bottom = add_layer(&mut p, "Bottom", None);
        let top = add_layer(&mut p, "Top", None);
        set_pixels(&mut p, &bottom, &[(0, 0, 1)]).unwrap();
        set_pixels(&mut p, &top, &[(1, 1, 2)]).unwrap();
        merge_layers(&mut p, &top, &bottom).unwrap();
        assert_eq!(p.layers.len(), 1);
        let merged = &p.layers[0];
        assert_eq!(merged.pixels.get(&(0, 0)), Some(&1));
        assert_eq!(merged.pixels.get(&(1, 1)), Some(&2));
    }

    #[test]
    fn test_swap_palette() {
        let mut p = test_project();
        let id = add_layer(&mut p, "Layer 1", None);
        set_pixels(&mut p, &id, &[(0, 0, 1), (1, 1, 2)]).unwrap();
        let mut map = HashMap::new();
        map.insert(1u8, 5u8);
        map.insert(2u8, 6u8);
        swap_palette(&mut p, &map);
        let layer = find_layer(&p, &id).unwrap();
        assert_eq!(layer.pixels.get(&(0, 0)), Some(&5));
        assert_eq!(layer.pixels.get(&(1, 1)), Some(&6));
    }
}
