//! Core engine: project CRUD, layer ops, drawing, transforms, palette,
//! sprite/animation definitions, and undo/redo.
//!
//! All functions are synchronous and operate on a `&mut SpriteProject`; the
//! MCP tool layer handles locking and argument parsing. Errors are
//! user-facing `String`s (they are surfaced verbatim as `InvalidParameters`).
//!
//! # Undo model
//!
//! Every mutating operation goes through [`edit`], which snapshots the
//! editable state (canvas, grid, palette, layers, sprites, animations) before
//! running the operation. If the operation fails, the snapshot is restored so
//! failed edits are atomic and leave no history entry. Layer pixel maps are
//! shared via `Arc`, so a snapshot costs O(layers) and only the layers an
//! edit actually touches are deep-copied.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::geometry::{self, MAX_COORD};
use crate::palette;
use crate::types::*;

/// Maximum number of undo steps kept per project.
pub const MAX_UNDO: usize = 50;

/// Soft cap on the number of pixel entries retained by undo history
/// (counting each distinct pixel map once). Oldest steps are evicted first.
pub const MAX_UNDO_PIXELS: usize = 8_000_000;

/// Engine result type; errors are user-facing messages.
pub type EResult<T> = Result<T, String>;

/// Shared project state across all tools.
pub type ProjectStore = Arc<RwLock<HashMap<String, SpriteProject>>>;

/// Create a new empty project store.
pub fn new_store() -> ProjectStore {
    Arc::new(RwLock::new(HashMap::new()))
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

/// Validate a project name (used as the store key and in default filenames).
pub fn validate_project_name(name: &str) -> EResult<()> {
    if name.trim().is_empty() {
        return Err("Project name must not be empty".into());
    }
    if name.chars().count() > 128 {
        return Err("Project name must be at most 128 characters".into());
    }
    if name.chars().any(char::is_control) {
        return Err("Project name must not contain control characters".into());
    }
    Ok(())
}

/// Validate canvas dimensions against [`MAX_CANVAS_DIM`] / [`MAX_CANVAS_PIXELS`].
pub fn validate_canvas(width: u32, height: u32) -> EResult<()> {
    if width == 0 || height == 0 {
        return Err("Canvas dimensions must be > 0".into());
    }
    if width > MAX_CANVAS_DIM || height > MAX_CANVAS_DIM {
        return Err(format!(
            "Canvas {width}x{height} exceeds the maximum dimension of {MAX_CANVAS_DIM}"
        ));
    }
    if u64::from(width) * u64::from(height) > MAX_CANVAS_PIXELS {
        return Err(format!(
            "Canvas {width}x{height} exceeds the maximum area of {MAX_CANVAS_PIXELS} pixels"
        ));
    }
    Ok(())
}

/// Validate grid geometry.
pub fn validate_grid(grid: &Grid) -> EResult<()> {
    if grid.cell_width == 0 || grid.cell_height == 0 {
        return Err("Grid cell dimensions must be > 0".into());
    }
    for (label, v) in [
        ("cell_width", grid.cell_width),
        ("cell_height", grid.cell_height),
        ("padding", grid.padding),
        ("margin", grid.margin),
    ] {
        if v > MAX_CANVAS_DIM {
            return Err(format!("Grid {label} {v} exceeds {MAX_CANVAS_DIM}"));
        }
    }
    Ok(())
}

/// Reject coordinates/sizes large enough to risk overflow in raster math.
pub fn check_coord(label: &str, v: i64) -> EResult<()> {
    if v.abs() > MAX_COORD {
        return Err(format!(
            "{label} = {v} is out of range (|value| <= {MAX_COORD})"
        ));
    }
    Ok(())
}

/// Validate a palette: at most 256 colors, unique indices.
pub fn validate_palette(p: &Palette) -> EResult<()> {
    if p.colors.len() > 256 {
        return Err(format!("Palette has {} colors (max 256)", p.colors.len()));
    }
    let mut seen = HashSet::new();
    for c in &p.colors {
        if !seen.insert(c.index) {
            return Err(format!("Duplicate palette index {}", c.index));
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Project management
// ---------------------------------------------------------------------------

/// Default palette for projects created without a preset: transparent,
/// black, white; not enforced.
pub fn default_palette() -> Palette {
    Palette {
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
    }
}

/// Create a new, empty project.
pub fn create_project(
    name: &str,
    width: u32,
    height: u32,
    grid: Grid,
    background_color: [u8; 4],
    palette_preset: Option<&str>,
) -> EResult<SpriteProject> {
    validate_project_name(name)?;
    validate_canvas(width, height)?;
    validate_grid(&grid)?;
    let pal = match palette_preset {
        Some(preset) => palette::from_preset(preset).ok_or_else(|| {
            format!(
                "Unknown palette preset: {preset}. Available: {}",
                palette::preset_names().join(", ")
            )
        })?,
        None => default_palette(),
    };
    Ok(SpriteProject {
        format_version: FORMAT_VERSION,
        name: name.to_string(),
        canvas: Canvas {
            width,
            height,
            background_color,
        },
        grid,
        palette: pal,
        layers: Vec::new(),
        sprites: Vec::new(),
        animations: Vec::new(),
        history: History::default(),
    })
}

/// Total number of stored pixels across all layers.
pub fn total_pixels(p: &SpriteProject) -> usize {
    p.layers.iter().map(|l| l.pixels.len()).sum()
}

/// Number of stored pixels whose color index has no palette entry.
pub fn orphaned_pixels(p: &SpriteProject) -> usize {
    let lut = p.palette.lut();
    p.layers
        .iter()
        .flat_map(|l| l.pixels.values())
        .filter(|&&c| lut[c as usize].is_none())
        .count()
}

/// Resize the canvas, shifting existing content by `(offset_x, offset_y)`.
/// Pixels that end up outside the new canvas are discarded; returns how many.
pub fn resize_canvas(
    p: &mut SpriteProject,
    width: u32,
    height: u32,
    offset_x: i64,
    offset_y: i64,
) -> EResult<usize> {
    validate_canvas(width, height)?;
    check_coord("offset_x", offset_x)?;
    check_coord("offset_y", offset_y)?;
    let mut dropped = 0;
    for layer in &mut p.layers {
        if offset_x == 0
            && offset_y == 0
            && layer.pixels.keys().all(|&(x, y)| x < width && y < height)
        {
            continue;
        }
        let mut next = PixelMap::with_capacity(layer.pixels.len());
        for (&(x, y), &c) in layer.pixels.iter() {
            let nx = i64::from(x) + offset_x;
            let ny = i64::from(y) + offset_y;
            if nx >= 0 && ny >= 0 && nx < i64::from(width) && ny < i64::from(height) {
                next.insert((nx as u32, ny as u32), c);
            } else {
                dropped += 1;
            }
        }
        layer.pixels = Arc::new(next);
    }
    p.canvas.width = width;
    p.canvas.height = height;
    Ok(dropped)
}

// ---------------------------------------------------------------------------
// Undo / Redo
// ---------------------------------------------------------------------------

fn capture(p: &SpriteProject) -> EditableState {
    EditableState {
        canvas: p.canvas.clone(),
        grid: p.grid.clone(),
        palette: p.palette.clone(),
        layers: p.layers.clone(),
        sprites: p.sprites.clone(),
        animations: p.animations.clone(),
    }
}

fn restore(p: &mut SpriteProject, s: EditableState) {
    p.canvas = s.canvas;
    p.grid = s.grid;
    p.palette = s.palette;
    p.layers = s.layers;
    p.sprites = s.sprites;
    p.animations = s.animations;
}

/// Approximate pixel entries retained by history, counting shared maps once.
fn history_pixels(h: &History) -> usize {
    let mut seen: HashSet<*const PixelMap> = HashSet::new();
    h.undo
        .iter()
        .chain(h.redo.iter())
        .flat_map(|s| s.state.layers.iter())
        .filter(|l| seen.insert(Arc::as_ptr(&l.pixels)))
        .map(|l| l.pixels.len())
        .sum()
}

fn enforce_history_budget(h: &mut History) {
    while h.undo.len() > MAX_UNDO {
        h.undo.pop_front();
    }
    while h.undo.len() > 1 && history_pixels(h) > MAX_UNDO_PIXELS {
        h.undo.pop_front();
    }
}

/// Run an undoable edit.
///
/// On success the pre-edit state is pushed to the undo stack and the redo
/// stack is cleared. On failure the project is restored to its pre-edit
/// state (edits are atomic) and no history entry is recorded.
pub fn edit<T>(
    p: &mut SpriteProject,
    label: &str,
    f: impl FnOnce(&mut SpriteProject) -> EResult<T>,
) -> EResult<T> {
    let before = capture(p);
    match f(p) {
        Ok(v) => {
            p.history.undo.push_back(Snapshot {
                label: label.to_string(),
                state: before,
            });
            p.history.redo.clear();
            enforce_history_budget(&mut p.history);
            Ok(v)
        },
        Err(e) => {
            restore(p, before);
            Err(e)
        },
    }
}

/// Undo the most recent edit; returns its label.
pub fn undo(p: &mut SpriteProject) -> EResult<String> {
    let snap = p
        .history
        .undo
        .pop_back()
        .ok_or_else(|| "Nothing to undo".to_string())?;
    let current = capture(p);
    p.history.redo.push(Snapshot {
        label: snap.label.clone(),
        state: current,
    });
    restore(p, snap.state);
    Ok(snap.label)
}

/// Redo the most recently undone edit; returns its label.
pub fn redo(p: &mut SpriteProject) -> EResult<String> {
    let snap = p
        .history
        .redo
        .pop()
        .ok_or_else(|| "Nothing to redo".to_string())?;
    let current = capture(p);
    p.history.undo.push_back(Snapshot {
        label: snap.label.clone(),
        state: current,
    });
    restore(p, snap.state);
    enforce_history_budget(&mut p.history);
    Ok(snap.label)
}

// ---------------------------------------------------------------------------
// Layer operations
// ---------------------------------------------------------------------------

/// Resolve a layer by ID, falling back to a unique exact name match.
pub fn resolve_layer(p: &SpriteProject, key: &str) -> EResult<usize> {
    if let Some(i) = p.layers.iter().position(|l| l.id == key) {
        return Ok(i);
    }
    let by_name: Vec<usize> = p
        .layers
        .iter()
        .enumerate()
        .filter(|(_, l)| l.name == key)
        .map(|(i, _)| i)
        .collect();
    match by_name.as_slice() {
        [i] => Ok(*i),
        [] => {
            let known: Vec<String> = p
                .layers
                .iter()
                .map(|l| format!("{} ({})", l.name, l.id))
                .collect();
            Err(format!(
                "Layer not found: {key}. Known layers: [{}]",
                known.join(", ")
            ))
        },
        _ => Err(format!(
            "Layer name '{key}' is ambiguous ({} layers); use the layer ID",
            by_name.len()
        )),
    }
}

/// Look up a layer by ID or unique name.
pub fn find_layer<'a>(p: &'a SpriteProject, key: &str) -> EResult<&'a Layer> {
    let i = resolve_layer(p, key)?;
    Ok(&p.layers[i])
}

/// Mutable layer lookup that refuses locked layers (for pixel edits).
fn editable_layer<'a>(p: &'a mut SpriteProject, key: &str) -> EResult<&'a mut Layer> {
    let i = resolve_layer(p, key)?;
    let layer = &mut p.layers[i];
    if layer.locked {
        return Err(format!(
            "Layer '{}' is locked; unlock it with sprite_update_layer",
            layer.name
        ));
    }
    Ok(layer)
}

/// Add a new layer; defaults to the top of the stack. Returns the layer ID.
pub fn add_layer(p: &mut SpriteProject, name: &str, z_order: Option<i32>) -> String {
    let id = uuid::Uuid::new_v4().to_string();
    let z = z_order.unwrap_or_else(|| {
        p.layers
            .iter()
            .map(|l| l.z_order)
            .max()
            .map_or(0, |m| m.saturating_add(1))
    });
    p.layers.push(Layer {
        id: id.clone(),
        name: name.to_string(),
        visible: true,
        opacity: 255,
        blend_mode: BlendMode::Normal,
        locked: false,
        z_order: z,
        pixels: Arc::new(PixelMap::new()),
    });
    id
}

/// Remove a layer by ID or name.
pub fn remove_layer(p: &mut SpriteProject, key: &str) -> EResult<Layer> {
    let i = resolve_layer(p, key)?;
    Ok(p.layers.remove(i))
}

/// Duplicate a layer (pixels and properties) directly above the source.
pub fn duplicate_layer(
    p: &mut SpriteProject,
    key: &str,
    new_name: Option<&str>,
) -> EResult<String> {
    let src = find_layer(p, key)?.clone();
    let id = uuid::Uuid::new_v4().to_string();
    let name = new_name.map_or_else(|| format!("{} copy", src.name), str::to_string);
    let z = src.z_order.saturating_add(1);
    // Keep the copy directly above the source by bumping layers at/above z.
    for l in &mut p.layers {
        if l.z_order >= z {
            l.z_order = l.z_order.saturating_add(1);
        }
    }
    p.layers.push(Layer {
        id: id.clone(),
        name,
        z_order: z,
        locked: false,
        ..src
    });
    Ok(id)
}

/// Result of [`merge_layers`].
#[derive(Debug, Default)]
pub struct MergeReport {
    pub pixels_merged: usize,
    pub warnings: Vec<String>,
}

/// Merge `top` onto `bottom` (top pixels overwrite), then remove `top`.
///
/// Pixels are palette indices, so the top layer's opacity and blend mode
/// cannot be baked in; a warning is returned when they would have mattered.
pub fn merge_layers(p: &mut SpriteProject, top: &str, bottom: &str) -> EResult<MergeReport> {
    let ti = resolve_layer(p, top)?;
    let bi = resolve_layer(p, bottom)?;
    if ti == bi {
        return Err("Cannot merge a layer into itself".into());
    }
    if p.layers[bi].locked {
        return Err(format!("Layer '{}' is locked", p.layers[bi].name));
    }
    let mut report = MergeReport::default();
    let top_layer = p.layers[ti].clone();
    if !top_layer.visible {
        report
            .warnings
            .push("Top layer was hidden; its pixels were merged anyway".into());
    }
    if top_layer.opacity < 255 || top_layer.blend_mode != BlendMode::Normal {
        report.warnings.push(
            "Top layer opacity/blend mode cannot be baked into indexed pixels; \
             its pixels were copied as fully opaque normal-blend"
                .into(),
        );
    }
    let dst = p.layers[bi].pixels_mut();
    for (&coord, &c) in top_layer.pixels.iter() {
        dst.insert(coord, c);
    }
    report.pixels_merged = top_layer.pixels.len();
    p.layers.remove(ti);
    Ok(report)
}

/// Clear all pixels (or a region) of a layer; returns the number cleared.
pub fn clear_layer(p: &mut SpriteProject, key: &str, region: Option<Region>) -> EResult<usize> {
    let (cw, ch) = (p.canvas.width, p.canvas.height);
    let layer = editable_layer(p, key)?;
    let before = layer.pixels.len();
    match region {
        None => layer.pixels = Arc::new(PixelMap::new()),
        Some(r) => {
            r.check()?;
            if let Some((x0, y0, x1, y1)) = geometry::clip_rect(r.x, r.y, r.width, r.height, cw, ch)
            {
                layer
                    .pixels_mut()
                    .retain(|&(px, py), _| px < x0 || px >= x1 || py < y0 || py >= y1);
            }
        },
    }
    Ok(before - layer.pixels.len())
}

// ---------------------------------------------------------------------------
// Drawing operations
// ---------------------------------------------------------------------------

/// A rectangle in canvas coordinates (may extend past the canvas).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Region {
    pub x: i64,
    pub y: i64,
    pub width: i64,
    pub height: i64,
}

impl Region {
    /// Validate magnitudes and positive size.
    pub fn check(&self) -> EResult<()> {
        check_coord("x", self.x)?;
        check_coord("y", self.y)?;
        check_coord("width", self.width)?;
        check_coord("height", self.height)?;
        if self.width <= 0 || self.height <= 0 {
            return Err("region width and height must be > 0".into());
        }
        Ok(())
    }
}

/// Outcome of a painting operation.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct PaintReport {
    /// Pixels written to the layer.
    pub painted: usize,
    /// Requested pixels that fell outside the canvas (skipped).
    pub out_of_bounds: usize,
    /// Pixels skipped because the palette is enforced and the index is undefined.
    pub invalid_color: usize,
}

fn check_color(p: &SpriteProject, color: u8) -> EResult<()> {
    if p.palette.enforce && !p.palette.is_valid_index(color) {
        let valid: Vec<String> = p
            .palette
            .colors
            .iter()
            .map(|c| c.index.to_string())
            .collect();
        return Err(format!(
            "Color index {color} is not in the enforced palette '{}' (valid: {})",
            p.palette.name,
            valid.join(", ")
        ));
    }
    Ok(())
}

fn paint_points(
    p: &mut SpriteProject,
    key: &str,
    points: &[(u32, u32)],
    color: u8,
) -> EResult<usize> {
    check_color(p, color)?;
    let layer = editable_layer(p, key)?;
    let px = layer.pixels_mut();
    px.reserve(points.len());
    for &pt in points {
        px.insert(pt, color);
    }
    Ok(points.len())
}

/// Set individual pixels. Out-of-canvas pixels and (with an enforced
/// palette) undefined colors are skipped and counted, not fatal.
pub fn set_pixels(
    p: &mut SpriteProject,
    key: &str,
    pixels: &[(i64, i64, u8)],
) -> EResult<PaintReport> {
    let (w, h) = (i64::from(p.canvas.width), i64::from(p.canvas.height));
    let lut = p.palette.lut();
    let enforce = p.palette.enforce;
    let layer = editable_layer(p, key)?;
    let mut rep = PaintReport::default();
    let map = layer.pixels_mut();
    for &(x, y, c) in pixels {
        if x < 0 || y < 0 || x >= w || y >= h {
            rep.out_of_bounds += 1;
        } else if enforce && lut[c as usize].is_none() {
            rep.invalid_color += 1;
        } else {
            map.insert((x as u32, y as u32), c);
            rep.painted += 1;
        }
    }
    Ok(rep)
}

/// Erase individual pixels; returns how many existed and were removed.
pub fn erase_pixels(p: &mut SpriteProject, key: &str, coords: &[(i64, i64)]) -> EResult<usize> {
    let layer = editable_layer(p, key)?;
    let map = layer.pixels_mut();
    let mut n = 0;
    for &(x, y) in coords {
        if x >= 0 && y >= 0 && x <= i64::from(u32::MAX) && y <= i64::from(u32::MAX) {
            n += usize::from(map.remove(&(x as u32, y as u32)).is_some());
        }
    }
    Ok(n)
}

/// Bresenham line (clipped).
pub fn draw_line(
    p: &mut SpriteProject,
    key: &str,
    from: (i64, i64),
    to: (i64, i64),
    color: u8,
) -> EResult<PaintReport> {
    for (l, v) in [("x0", from.0), ("y0", from.1), ("x1", to.0), ("y1", to.1)] {
        check_coord(l, v)?;
    }
    let (pts, clipped) =
        geometry::line(from.0, from.1, to.0, to.1, p.canvas.width, p.canvas.height);
    let painted = paint_points(p, key, &pts, color)?;
    Ok(PaintReport {
        painted,
        out_of_bounds: clipped,
        invalid_color: 0,
    })
}

/// Rectangle, outline or filled (clipped).
pub fn draw_rect(
    p: &mut SpriteProject,
    key: &str,
    r: Region,
    color: u8,
    filled: bool,
) -> EResult<usize> {
    r.check()?;
    let pts = geometry::rect(
        r.x,
        r.y,
        r.width,
        r.height,
        filled,
        p.canvas.width,
        p.canvas.height,
    );
    paint_points(p, key, &pts, color)
}

/// Ellipse centered at `center` with radii `(rx, ry)`, outline or filled (clipped).
pub fn draw_ellipse(
    p: &mut SpriteProject,
    key: &str,
    center: (i64, i64),
    radii: (i64, i64),
    color: u8,
    filled: bool,
) -> EResult<usize> {
    check_coord("cx", center.0)?;
    check_coord("cy", center.1)?;
    check_coord("rx", radii.0)?;
    check_coord("ry", radii.1)?;
    if radii.0 < 0 || radii.1 < 0 {
        return Err("Ellipse radii must be >= 0".into());
    }
    let pts = geometry::ellipse(
        center.0,
        center.1,
        radii.0,
        radii.1,
        filled,
        p.canvas.width,
        p.canvas.height,
    );
    paint_points(p, key, &pts, color)
}

/// Flood fill from `(x, y)`.
///
/// With `contiguous = true` (the default) fills the 4-connected region of the
/// start pixel's color (empty counts as a color); otherwise replaces every
/// pixel on the layer with that color. Returns the number of pixels changed.
pub fn flood_fill(
    p: &mut SpriteProject,
    key: &str,
    x: i64,
    y: i64,
    color: u8,
    contiguous: bool,
) -> EResult<usize> {
    let (cw, ch) = (p.canvas.width, p.canvas.height);
    if x < 0 || y < 0 || x >= i64::from(cw) || y >= i64::from(ch) {
        return Err(format!(
            "Fill start ({x}, {y}) is outside the {cw}x{ch} canvas"
        ));
    }
    check_color(p, color)?;
    let (x, y) = (x as u32, y as u32);
    let layer = editable_layer(p, key)?;
    let target = layer.pixels.get(&(x, y)).copied();
    if target == Some(color) {
        return Ok(0);
    }
    let cells: Vec<(u32, u32)> = if contiguous {
        let px = &layer.pixels;
        geometry::flood_region(cw, ch, x, y, |a, b| px.get(&(a, b)).copied())
    } else {
        match target {
            Some(t) => layer
                .pixels
                .iter()
                .filter(|&(_, &c)| c == t)
                .map(|(&k, _)| k)
                .collect(),
            None => (0..ch)
                .flat_map(|yy| (0..cw).map(move |xx| (xx, yy)))
                .filter(|k| !layer.pixels.contains_key(k))
                .collect(),
        }
    };
    let map = layer.pixels_mut();
    map.reserve(cells.len());
    for &c in &cells {
        map.insert(c, color);
    }
    Ok(cells.len())
}

// ---------------------------------------------------------------------------
// Transform operations
// ---------------------------------------------------------------------------

/// Outcome of [`transform_layer`].
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct TransformReport {
    /// Pixels that were transformed.
    pub moved: usize,
    /// Pixels discarded because they landed outside the canvas.
    pub dropped: usize,
}

/// Apply a flip/rotate/shift to a layer, optionally constrained to a region.
///
/// Rotations of a non-square region keep the region's top-left corner fixed,
/// so the rotated block is `height x width`. Pixels landing outside the
/// canvas are dropped (reported). With `wrap`, a shift wraps around the
/// region (or canvas) instead of dropping pixels.
pub fn transform_layer(
    p: &mut SpriteProject,
    key: &str,
    op: TransformOp,
    shift: (i64, i64),
    region: Option<Region>,
    wrap: bool,
) -> EResult<TransformReport> {
    let (cw, ch) = (p.canvas.width, p.canvas.height);
    check_coord("shift_dx", shift.0)?;
    check_coord("shift_dy", shift.1)?;
    let (bx, by, bx1, by1) = match region {
        Some(r) => {
            r.check()?;
            geometry::clip_rect(r.x, r.y, r.width, r.height, cw, ch)
                .ok_or_else(|| "Transform region lies entirely outside the canvas".to_string())?
        },
        None => (0, 0, cw, ch),
    };
    let (bx, by) = (i64::from(bx), i64::from(by));
    let (bw, bh) = (i64::from(bx1) - bx, i64::from(by1) - by);
    let layer = editable_layer(p, key)?;

    let mut keep = PixelMap::with_capacity(layer.pixels.len());
    let mut inside = Vec::new();
    for (&(x, y), &c) in layer.pixels.iter() {
        let (xi, yi) = (i64::from(x), i64::from(y));
        if xi >= bx && xi < bx + bw && yi >= by && yi < by + bh {
            inside.push((xi - bx, yi - by, c));
        } else {
            keep.insert((x, y), c);
        }
    }
    let mut report = TransformReport::default();
    for (rx, ry, c) in inside {
        let (nx, ny) = match op {
            TransformOp::FlipH => (bw - 1 - rx, ry),
            TransformOp::FlipV => (rx, bh - 1 - ry),
            TransformOp::Rotate180 => (bw - 1 - rx, bh - 1 - ry),
            TransformOp::Rotate90Cw => (bh - 1 - ry, rx),
            TransformOp::Rotate90Ccw => (ry, bw - 1 - rx),
            TransformOp::Shift => {
                let (mut nx, mut ny) = (rx + shift.0, ry + shift.1);
                if wrap {
                    nx = nx.rem_euclid(bw);
                    ny = ny.rem_euclid(bh);
                }
                (nx, ny)
            },
        };
        let (ax, ay) = (bx + nx, by + ny);
        if ax >= 0 && ay >= 0 && ax < i64::from(cw) && ay < i64::from(ch) {
            keep.insert((ax as u32, ay as u32), c);
            report.moved += 1;
        } else {
            report.dropped += 1;
        }
    }
    layer.pixels = Arc::new(keep);
    Ok(report)
}

// ---------------------------------------------------------------------------
// Palette operations
// ---------------------------------------------------------------------------

/// Replace the palette; returns the number of stored pixels that now reference
/// an undefined index (they render transparent).
pub fn set_palette(p: &mut SpriteProject, palette: Palette) -> EResult<usize> {
    validate_palette(&palette)?;
    p.palette = palette;
    Ok(orphaned_pixels(p))
}

/// Remap pixel indices across all layers (locked layers included, since this
/// is a palette-level operation). Returns the number of pixels changed.
pub fn swap_palette(p: &mut SpriteProject, index_map: &HashMap<u8, u8>) -> usize {
    let mut changed = 0;
    for layer in &mut p.layers {
        if !layer.pixels.values().any(|c| index_map.contains_key(c)) {
            continue;
        }
        for c in layer.pixels_mut().values_mut() {
            if let Some(&n) = index_map.get(c) {
                if n != *c {
                    changed += 1;
                }
                *c = n;
            }
        }
    }
    changed
}

// ---------------------------------------------------------------------------
// Sprites and animations
// ---------------------------------------------------------------------------

/// Pixel bounds `(x, y, w, h)` of a sprite in canvas coordinates.
///
/// Computed in u64 and saturated so hostile grid values cannot overflow.
pub fn sprite_pixel_bounds(p: &SpriteProject, s: &SpriteDef) -> (u32, u32, u32, u32) {
    let g = &p.grid;
    let sat = |v: u64| u32::try_from(v).unwrap_or(u32::MAX);
    let (cw, chh, pad, m) = (
        u64::from(g.cell_width),
        u64::from(g.cell_height),
        u64::from(g.padding),
        u64::from(g.margin),
    );
    let x = m + u64::from(s.grid_x) * (cw + pad);
    let y = m + u64::from(s.grid_y) * (chh + pad);
    let wc = u64::from(s.width_cells);
    let hc = u64::from(s.height_cells);
    let w = wc * cw + wc.saturating_sub(1) * pad;
    let h = hc * chh + hc.saturating_sub(1) * pad;
    (sat(x), sat(y), sat(w), sat(h))
}

/// Resolve a sprite by ID, falling back to a unique name match.
pub fn resolve_sprite(p: &SpriteProject, key: &str) -> EResult<usize> {
    if let Some(i) = p.sprites.iter().position(|s| s.id == key) {
        return Ok(i);
    }
    let matches: Vec<usize> = p
        .sprites
        .iter()
        .enumerate()
        .filter(|(_, s)| s.name == key)
        .map(|(i, _)| i)
        .collect();
    match matches.as_slice() {
        [i] => Ok(*i),
        [] => Err(format!(
            "Sprite not found: {key}. Known sprites: [{}]",
            p.sprites
                .iter()
                .map(|s| s.name.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )),
        _ => Err(format!(
            "Sprite name '{key}' is ambiguous; use the sprite ID"
        )),
    }
}

/// Resolve an animation by ID, falling back to a unique name match.
pub fn resolve_animation(p: &SpriteProject, key: &str) -> EResult<usize> {
    if let Some(i) = p.animations.iter().position(|a| a.id == key) {
        return Ok(i);
    }
    let matches: Vec<usize> = p
        .animations
        .iter()
        .enumerate()
        .filter(|(_, a)| a.name == key)
        .map(|(i, _)| i)
        .collect();
    match matches.as_slice() {
        [i] => Ok(*i),
        [] => Err(format!(
            "Animation not found: {key}. Known animations: [{}]",
            p.animations
                .iter()
                .map(|a| a.name.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )),
        _ => Err(format!(
            "Animation name '{key}' is ambiguous; use the animation ID"
        )),
    }
}

/// Validate that a sprite definition lies within the canvas.
pub fn validate_sprite(p: &SpriteProject, s: &SpriteDef) -> EResult<()> {
    if s.name.trim().is_empty() {
        return Err("Sprite name must not be empty".into());
    }
    if s.width_cells == 0 || s.height_cells == 0 {
        return Err("Sprite width_cells and height_cells must be >= 1".into());
    }
    let (x, y, w, h) = sprite_pixel_bounds(p, s);
    let fits = u64::from(x) + u64::from(w) <= u64::from(p.canvas.width)
        && u64::from(y) + u64::from(h) <= u64::from(p.canvas.height);
    if !fits {
        return Err(format!(
            "Sprite '{}' covers pixels ({x},{y}) {w}x{h}, which extends past the {}x{} canvas",
            s.name, p.canvas.width, p.canvas.height
        ));
    }
    if s.anchor_x > w || s.anchor_y > h {
        return Err(format!(
            "Anchor ({}, {}) lies outside the {w}x{h} sprite",
            s.anchor_x, s.anchor_y
        ));
    }
    Ok(())
}

/// Define a sprite, or update the existing sprite with the same name
/// (keeping its ID). Returns `(id, updated)`.
pub fn define_sprite(p: &mut SpriteProject, mut def: SpriteDef) -> EResult<(String, bool)> {
    validate_sprite(p, &def)?;
    if let Some(existing) = p.sprites.iter_mut().find(|s| s.name == def.name) {
        def.id = existing.id.clone();
        *existing = def;
        return Ok((existing.id.clone(), true));
    }
    def.id = uuid::Uuid::new_v4().to_string();
    let id = def.id.clone();
    p.sprites.push(def);
    Ok((id, false))
}

/// Remove a sprite. Frames referencing it are removed from animations;
/// returns the names of affected animations.
pub fn remove_sprite(p: &mut SpriteProject, key: &str) -> EResult<(SpriteDef, Vec<String>)> {
    let i = resolve_sprite(p, key)?;
    let removed = p.sprites.remove(i);
    let mut affected = Vec::new();
    for a in &mut p.animations {
        let before = a.frames.len();
        a.frames.retain(|f| f.sprite_id != removed.id);
        if a.frames.len() != before {
            affected.push(a.name.clone());
        }
    }
    Ok((removed, affected))
}

/// Define an animation (or update the one with the same name, keeping its ID).
///
/// Frame `sprite_id`s may be sprite IDs or unique sprite names; they are
/// normalized to IDs. Returns `(id, updated)`.
pub fn define_animation(
    p: &mut SpriteProject,
    name: &str,
    frames: Vec<AnimFrame>,
    loop_mode: LoopMode,
    tags: Vec<String>,
) -> EResult<(String, bool)> {
    if name.trim().is_empty() {
        return Err("Animation name must not be empty".into());
    }
    if frames.is_empty() {
        return Err("An animation needs at least one frame".into());
    }
    let mut resolved = Vec::with_capacity(frames.len());
    for (i, f) in frames.into_iter().enumerate() {
        let si = resolve_sprite(p, &f.sprite_id).map_err(|e| format!("frames[{i}]: {e}"))?;
        if f.duration_ms == 0 {
            return Err(format!("frames[{i}]: duration_ms must be > 0"));
        }
        resolved.push(AnimFrame {
            sprite_id: p.sprites[si].id.clone(),
            duration_ms: f.duration_ms,
        });
    }
    if let Some(a) = p.animations.iter_mut().find(|a| a.name == name) {
        a.frames = resolved;
        a.loop_mode = loop_mode;
        a.tags = tags;
        return Ok((a.id.clone(), true));
    }
    let id = uuid::Uuid::new_v4().to_string();
    p.animations.push(AnimationDef {
        id: id.clone(),
        name: name.to_string(),
        frames: resolved,
        loop_mode,
        tags,
    });
    Ok((id, false))
}

/// Remove an animation by ID or name.
pub fn remove_animation(p: &mut SpriteProject, key: &str) -> EResult<AnimationDef> {
    let i = resolve_animation(p, key)?;
    Ok(p.animations.remove(i))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn grid(cw: u32, ch: u32) -> Grid {
        Grid {
            cell_width: cw,
            cell_height: ch,
            padding: 0,
            margin: 0,
        }
    }

    fn project() -> SpriteProject {
        create_project("test", 16, 16, grid(8, 8), [0, 0, 0, 0], Some("pico8")).unwrap()
    }

    fn px(p: &SpriteProject, id: &str) -> PixelMap {
        (*find_layer(p, id).unwrap().pixels).clone()
    }

    #[test]
    fn create_project_validates() {
        assert!(create_project("", 8, 8, grid(8, 8), [0; 4], None).is_err());
        assert!(create_project("a", 0, 8, grid(8, 8), [0; 4], None).is_err());
        assert!(create_project("a", 100_000, 8, grid(8, 8), [0; 4], None).is_err());
        assert!(create_project("a", 4096, 4096, grid(8, 8), [0; 4], None).is_err());
        assert!(create_project("a", 8, 8, grid(0, 8), [0; 4], None).is_err());
        let e = create_project("a", 8, 8, grid(8, 8), [0; 4], Some("nope")).unwrap_err();
        assert!(e.contains("pico8"), "{e}");
        let p = project();
        assert_eq!(p.palette.colors.len(), 16);
        assert_eq!(p.format_version, FORMAT_VERSION);
    }

    #[test]
    fn layer_resolution_by_id_and_name() {
        let mut p = project();
        let id = add_layer(&mut p, "base", None);
        assert_eq!(resolve_layer(&p, &id).unwrap(), 0);
        assert_eq!(resolve_layer(&p, "base").unwrap(), 0);
        add_layer(&mut p, "base", None);
        assert!(resolve_layer(&p, "base").unwrap_err().contains("ambiguous"));
        assert!(resolve_layer(&p, "zzz").unwrap_err().contains("not found"));
    }

    #[test]
    fn add_layer_z_order_defaults_to_top() {
        let mut p = project();
        add_layer(&mut p, "a", Some(i32::MAX));
        add_layer(&mut p, "b", None); // must not overflow
        assert_eq!(p.layers[1].z_order, i32::MAX);
    }

    #[test]
    fn set_pixels_reports_skips() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        let rep = set_pixels(
            &mut p,
            &id,
            &[(0, 0, 1), (1, 1, 2), (100, 0, 1), (-1, 0, 1), (2, 2, 99)],
        )
        .unwrap();
        assert_eq!(rep.painted, 2);
        assert_eq!(rep.out_of_bounds, 2);
        assert_eq!(rep.invalid_color, 1);
    }

    #[test]
    fn primitives_reject_invalid_color_when_enforced() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        let e = draw_line(&mut p, &id, (0, 0), (3, 0), 200).unwrap_err();
        assert!(e.contains("200"), "{e}");
        assert!(flood_fill(&mut p, &id, 0, 0, 200, true).is_err());
    }

    #[test]
    fn locked_layer_rejects_edits() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        p.layers[0].locked = true;
        assert!(
            set_pixels(&mut p, &id, &[(0, 0, 1)])
                .unwrap_err()
                .contains("locked")
        );
        assert!(flood_fill(&mut p, &id, 0, 0, 1, true).is_err());
        assert!(clear_layer(&mut p, &id, None).is_err());
    }

    #[test]
    fn flood_fill_basic_contiguous_and_global() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        assert_eq!(flood_fill(&mut p, &id, 0, 0, 1, true).unwrap(), 256);
        // Same color again is a no-op.
        assert_eq!(flood_fill(&mut p, &id, 5, 5, 1, true).unwrap(), 0);
        // Draw a wall of color 2, then fill left side with 3.
        draw_line(&mut p, &id, (8, 0), (8, 15), 2).unwrap();
        assert_eq!(flood_fill(&mut p, &id, 0, 0, 3, true).unwrap(), 8 * 16);
        // Global replace of color 1 (right side) with 4.
        assert_eq!(flood_fill(&mut p, &id, 15, 0, 4, false).unwrap(), 7 * 16);
    }

    #[test]
    fn flood_fill_out_of_bounds_is_error() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        assert!(flood_fill(&mut p, &id, 16, 0, 1, true).is_err());
        assert!(flood_fill(&mut p, &id, -1, 0, 1, true).is_err());
    }

    #[test]
    fn huge_primitives_are_clipped_or_rejected() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        let r = Region {
            x: -1000,
            y: -1000,
            width: 1_000_000,
            height: 1_000_000,
        };
        assert_eq!(draw_rect(&mut p, &id, r, 1, true).unwrap(), 256);
        assert!(draw_line(&mut p, &id, (0, 0), (i64::MAX, 0), 1).is_err());
        assert!(draw_ellipse(&mut p, &id, (0, 0), (-1, 3), 1, false).is_err());
    }

    #[test]
    fn undo_redo_roundtrip_and_labels() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        edit(&mut p, "set_pixels", |p| set_pixels(p, &id, &[(0, 0, 1)])).unwrap();
        edit(&mut p, "draw_rect", |p| {
            draw_rect(
                p,
                &id,
                Region {
                    x: 0,
                    y: 0,
                    width: 2,
                    height: 2,
                },
                2,
                true,
            )
        })
        .unwrap();
        assert_eq!(px(&p, &id).len(), 4);
        assert_eq!(undo(&mut p).unwrap(), "draw_rect");
        assert_eq!(px(&p, &id).len(), 1);
        assert_eq!(undo(&mut p).unwrap(), "set_pixels");
        assert!(px(&p, &id).is_empty());
        assert!(undo(&mut p).is_err());
        assert_eq!(redo(&mut p).unwrap(), "set_pixels");
        assert_eq!(redo(&mut p).unwrap(), "draw_rect");
        assert_eq!(px(&p, &id).len(), 4);
        assert!(redo(&mut p).is_err());
    }

    #[test]
    fn failed_edit_is_atomic_and_not_recorded() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        edit(&mut p, "a", |p| set_pixels(p, &id, &[(0, 0, 1)])).unwrap();
        let err = edit(&mut p, "bad", |p| {
            set_pixels(p, &id, &[(1, 1, 1)])?;
            Err::<(), _>("boom".to_string())
        });
        assert!(err.is_err());
        assert_eq!(px(&p, &id).len(), 1, "partial edit rolled back");
        assert_eq!(p.history.undo.len(), 1);
    }

    #[test]
    fn new_edit_clears_redo() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        edit(&mut p, "a", |p| set_pixels(p, &id, &[(0, 0, 1)])).unwrap();
        undo(&mut p).unwrap();
        assert_eq!(p.history.redo.len(), 1);
        edit(&mut p, "b", |p| set_pixels(p, &id, &[(1, 0, 1)])).unwrap();
        assert!(p.history.redo.is_empty());
    }

    #[test]
    fn undo_restores_structural_changes() {
        let mut p = project();
        let a = add_layer(&mut p, "a", None);
        let b = add_layer(&mut p, "b", None);
        set_pixels(&mut p, &a, &[(0, 0, 1)]).unwrap();
        set_pixels(&mut p, &b, &[(0, 0, 2), (1, 1, 2)]).unwrap();
        edit(&mut p, "merge", |p| merge_layers(p, &b, &a)).unwrap();
        assert_eq!(p.layers.len(), 1);
        undo(&mut p).unwrap();
        assert_eq!(p.layers.len(), 2);
        assert_eq!(px(&p, &a).len(), 1);
        assert_eq!(px(&p, &b).len(), 2);
        edit(&mut p, "remove", |p| remove_layer(p, &a).map(|_| ())).unwrap();
        undo(&mut p).unwrap();
        assert!(find_layer(&p, &a).is_ok());
    }

    #[test]
    fn undo_history_is_bounded() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        for i in 0..(MAX_UNDO + 10) {
            edit(&mut p, "px", |p| {
                set_pixels(p, &id, &[((i % 16) as i64, 0, 1)])
            })
            .unwrap();
        }
        assert_eq!(p.history.undo.len(), MAX_UNDO);
    }

    #[test]
    fn snapshots_share_untouched_layers() {
        let mut p = project();
        let a = add_layer(&mut p, "a", None);
        let b = add_layer(&mut p, "b", None);
        set_pixels(&mut p, &a, &[(0, 0, 1)]).unwrap();
        edit(&mut p, "b", |p| set_pixels(p, &b, &[(0, 0, 1)])).unwrap();
        let snap = &p.history.undo[0].state;
        // Layer a was not touched: the snapshot shares its pixel map.
        assert!(Arc::ptr_eq(&snap.layers[0].pixels, &p.layers[0].pixels));
        assert!(!Arc::ptr_eq(&snap.layers[1].pixels, &p.layers[1].pixels));
    }

    #[test]
    fn merge_same_layer_is_rejected() {
        let mut p = project();
        let a = add_layer(&mut p, "a", None);
        assert!(merge_layers(&mut p, &a, &a).is_err());
        assert_eq!(p.layers.len(), 1);
    }

    #[test]
    fn merge_warns_about_opacity() {
        let mut p = project();
        let a = add_layer(&mut p, "a", None);
        let b = add_layer(&mut p, "b", None);
        p.layers[1].opacity = 100;
        let rep = merge_layers(&mut p, &b, &a).unwrap();
        assert_eq!(rep.warnings.len(), 1);
    }

    #[test]
    fn duplicate_layer_stays_directly_above() {
        let mut p = project();
        let a = add_layer(&mut p, "a", None); // z 0
        let b = add_layer(&mut p, "b", None); // z 1
        let c = duplicate_layer(&mut p, &a, None).unwrap();
        let z = |id: &str| find_layer(&p, id).unwrap().z_order;
        assert!(z(&a) < z(&c) && z(&c) < z(&b));
        assert_eq!(find_layer(&p, &c).unwrap().name, "a copy");
    }

    #[test]
    fn clear_layer_region_counts() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        flood_fill(&mut p, &id, 0, 0, 1, true).unwrap();
        let r = Region {
            x: -2,
            y: -2,
            width: 4,
            height: 4,
        };
        assert_eq!(clear_layer(&mut p, &id, Some(r)).unwrap(), 4);
        assert_eq!(clear_layer(&mut p, &id, None).unwrap(), 252);
    }

    #[test]
    fn transform_flip_rotate_region() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(0, 0, 1)]).unwrap();
        transform_layer(&mut p, &id, TransformOp::FlipH, (0, 0), None, false).unwrap();
        assert!(px(&p, &id).contains_key(&(15, 0)));
        transform_layer(&mut p, &id, TransformOp::FlipV, (0, 0), None, false).unwrap();
        assert!(px(&p, &id).contains_key(&(15, 15)));
        transform_layer(&mut p, &id, TransformOp::Rotate180, (0, 0), None, false).unwrap();
        assert!(px(&p, &id).contains_key(&(0, 0)));
        // Rotate CW in a 4x2 region at (2,2): top-left (2,2) -> (2+1, 2).
        set_pixels(&mut p, &id, &[(2, 2, 3)]).unwrap();
        let r = Region {
            x: 2,
            y: 2,
            width: 4,
            height: 2,
        };
        transform_layer(&mut p, &id, TransformOp::Rotate90Cw, (0, 0), Some(r), false).unwrap();
        let m = px(&p, &id);
        assert_eq!(m.get(&(3, 2)), Some(&3));
        assert_eq!(m.get(&(0, 0)), Some(&1), "outside region untouched");
    }

    #[test]
    fn transform_rotate_cw_then_ccw_is_identity() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(1, 2, 1), (5, 3, 2), (15, 15, 3)]).unwrap();
        let before = px(&p, &id);
        transform_layer(&mut p, &id, TransformOp::Rotate90Cw, (0, 0), None, false).unwrap();
        transform_layer(&mut p, &id, TransformOp::Rotate90Ccw, (0, 0), None, false).unwrap();
        assert_eq!(px(&p, &id), before);
    }

    #[test]
    fn transform_shift_drop_and_wrap() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(15, 0, 1), (0, 0, 2)]).unwrap();
        let rep = transform_layer(&mut p, &id, TransformOp::Shift, (1, 0), None, false).unwrap();
        assert_eq!(rep.dropped, 1);
        assert_eq!(px(&p, &id).get(&(1, 0)), Some(&2));
        transform_layer(&mut p, &id, TransformOp::Shift, (-2, 0), None, true).unwrap();
        assert_eq!(px(&p, &id).get(&(15, 0)), Some(&2));
    }

    #[test]
    fn resize_canvas_offsets_and_crops() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(0, 0, 1), (15, 15, 2)]).unwrap();
        let dropped = resize_canvas(&mut p, 8, 8, 1, 1).unwrap();
        assert_eq!(dropped, 1);
        assert_eq!(px(&p, &id).get(&(1, 1)), Some(&1));
        assert_eq!(p.canvas.width, 8);
        assert!(resize_canvas(&mut p, 0, 8, 0, 0).is_err());
    }

    #[test]
    fn swap_palette_counts_changes() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(0, 0, 1), (1, 1, 2), (2, 2, 3)]).unwrap();
        let map: HashMap<u8, u8> = [(1, 5), (2, 6), (3, 3)].into_iter().collect();
        assert_eq!(swap_palette(&mut p, &map), 2);
        let m = px(&p, &id);
        assert_eq!(m.get(&(0, 0)), Some(&5));
        assert_eq!(m.get(&(1, 1)), Some(&6));
    }

    #[test]
    fn set_palette_reports_orphans_and_rejects_duplicates() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(0, 0, 1), (1, 1, 15)]).unwrap();
        let gb = palette::gameboy();
        assert_eq!(set_palette(&mut p, gb).unwrap(), 1);
        let mut dup = palette::gameboy();
        dup.colors[1].index = 0;
        assert!(set_palette(&mut p, dup).is_err());
    }

    fn sprite(name: &str, gx: u32, gy: u32) -> SpriteDef {
        SpriteDef {
            id: String::new(),
            name: name.into(),
            grid_x: gx,
            grid_y: gy,
            width_cells: 1,
            height_cells: 1,
            anchor_x: 0,
            anchor_y: 0,
            hitbox: None,
            tags: vec![],
        }
    }

    #[test]
    fn sprite_bounds_and_validation() {
        let mut p = project();
        p.grid.padding = 1;
        p.grid.margin = 2;
        let s = sprite("a", 1, 0);
        assert_eq!(sprite_pixel_bounds(&p, &s), (11, 2, 8, 8));
        // Out of the 16x16 canvas.
        assert!(define_sprite(&mut p, sprite("b", 5, 0)).is_err());
        let mut z = sprite("z", 0, 0);
        z.width_cells = 0;
        assert!(define_sprite(&mut p, z).is_err());
        // Overflowing grid coordinates do not panic.
        assert!(define_sprite(&mut p, sprite("o", u32::MAX, u32::MAX)).is_err());
    }

    #[test]
    fn define_sprite_upserts_by_name() {
        let mut p = project();
        let (id1, up1) = define_sprite(&mut p, sprite("idle", 0, 0)).unwrap();
        let (id2, up2) = define_sprite(&mut p, sprite("idle", 1, 1)).unwrap();
        assert!(!up1 && up2);
        assert_eq!(id1, id2);
        assert_eq!(p.sprites.len(), 1);
        assert_eq!(p.sprites[0].grid_x, 1);
    }

    #[test]
    fn animation_validation_and_sprite_removal() {
        let mut p = project();
        let (a, _) = define_sprite(&mut p, sprite("f0", 0, 0)).unwrap();
        define_sprite(&mut p, sprite("f1", 1, 0)).unwrap();
        let frames = vec![
            AnimFrame {
                sprite_id: a.clone(),
                duration_ms: 100,
            },
            AnimFrame {
                sprite_id: "f1".into(), // by name
                duration_ms: 50,
            },
        ];
        let (anim, _) = define_animation(&mut p, "walk", frames, LoopMode::Loop, vec![]).unwrap();
        assert_eq!(p.animations[0].frames[1].sprite_id, p.sprites[1].id);
        assert!(define_animation(&mut p, "x", vec![], LoopMode::Loop, vec![]).is_err());
        let bad = vec![AnimFrame {
            sprite_id: "ghost".into(),
            duration_ms: 10,
        }];
        let e = define_animation(&mut p, "x", bad, LoopMode::Loop, vec![]).unwrap_err();
        assert!(e.contains("frames[0]"), "{e}");
        let (_, affected) = remove_sprite(&mut p, "f0").unwrap();
        assert_eq!(affected, vec!["walk".to_string()]);
        assert_eq!(p.animations[0].frames.len(), 1);
        remove_animation(&mut p, &anim).unwrap();
        assert!(p.animations.is_empty());
    }

    #[test]
    fn erase_pixels_counts_existing() {
        let mut p = project();
        let id = add_layer(&mut p, "l", None);
        set_pixels(&mut p, &id, &[(0, 0, 1), (1, 0, 1)]).unwrap();
        assert_eq!(
            erase_pixels(&mut p, &id, &[(0, 0), (5, 5), (-1, 0)]).unwrap(),
            1
        );
    }
}
