//! Domain types for sprite sheet projects, plus the on-disk (JSON) format.
//!
//! # Persistence format
//!
//! Projects serialize to JSON with a top-level `format_version`
//! ([`FORMAT_VERSION`]). Layer pixels are written as a sorted array of
//! `[x, y, color_index]` triples. The loader also accepts the legacy map form
//! (`{"x,y": color_index}`) and treats a missing `format_version` as version 1.
//! Undo/redo history is runtime-only and never persisted.

use serde::de::{self, Deserializer};
use serde::ser::{SerializeSeq, Serializer};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;

/// Current project file format version written by `sprite_save_project`.
pub const FORMAT_VERSION: u32 = 2;

/// Maximum canvas width or height in pixels.
pub const MAX_CANVAS_DIM: u32 = 4096;

/// Maximum canvas area in pixels (e.g. 2048x2048, 4096x1024).
///
/// Pixels are stored sparsely in hash maps, so a fully painted canvas costs
/// roughly 20 bytes per pixel per layer; this bound keeps worst-case memory
/// for a flood fill of an empty canvas in the low hundreds of MB.
pub const MAX_CANVAS_PIXELS: u64 = 2048 * 2048;

/// Sparse pixel storage: `(x, y)` -> palette color index.
pub type PixelMap = HashMap<(u32, u32), u8>;

/// A complete sprite sheet project.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpriteProject {
    /// File format version (see [`FORMAT_VERSION`]). Missing = legacy v1.
    #[serde(default = "legacy_format_version")]
    pub format_version: u32,
    pub name: String,
    pub canvas: Canvas,
    pub grid: Grid,
    pub palette: Palette,
    #[serde(default)]
    pub layers: Vec<Layer>,
    #[serde(default)]
    pub sprites: Vec<SpriteDef>,
    #[serde(default)]
    pub animations: Vec<AnimationDef>,
    /// Runtime-only undo/redo history.
    #[serde(skip)]
    pub history: History,
}

fn legacy_format_version() -> u32 {
    1
}

/// Canvas dimensions and background.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Canvas {
    pub width: u32,
    pub height: u32,
    #[serde(default)]
    pub background_color: [u8; 4],
}

/// Grid configuration for sprite cells.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Grid {
    pub cell_width: u32,
    pub cell_height: u32,
    #[serde(default)]
    pub padding: u32,
    #[serde(default)]
    pub margin: u32,
}

/// A named color with palette index.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PaletteColor {
    pub index: u8,
    #[serde(default)]
    pub name: String,
    pub rgba: [u8; 4],
}

/// Palette of indexed colors.
///
/// When `enforce` is true, drawing with an index that is not in the palette is
/// rejected. When false, any index may be drawn, but indices without a
/// palette entry render as fully transparent.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Palette {
    #[serde(default = "custom_name")]
    pub name: String,
    #[serde(default)]
    pub colors: Vec<PaletteColor>,
    #[serde(default)]
    pub enforce: bool,
}

fn custom_name() -> String {
    "custom".to_string()
}

impl Palette {
    /// Look up RGBA by palette index (linear scan; use [`Palette::lut`] in hot loops).
    #[cfg(test)]
    pub fn get_color(&self, index: u8) -> Option<[u8; 4]> {
        self.colors
            .iter()
            .find(|c| c.index == index)
            .map(|c| c.rgba)
    }

    /// Check if a palette index is defined.
    pub fn is_valid_index(&self, index: u8) -> bool {
        self.colors.iter().any(|c| c.index == index)
    }

    /// Dense index -> RGBA lookup table (O(1) per pixel while compositing).
    pub fn lut(&self) -> [Option<[u8; 4]>; 256] {
        let mut lut = [None; 256];
        for c in &self.colors {
            lut[c.index as usize] = Some(c.rgba);
        }
        lut
    }
}

/// A single drawing layer with sparse pixel storage.
///
/// Pixels live behind an [`Arc`] so undo snapshots are copy-on-write: taking
/// a snapshot clones pointers, and only layers that are subsequently modified
/// (via [`Layer::pixels_mut`]) pay for a deep copy.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Layer {
    pub id: String,
    pub name: String,
    #[serde(default = "default_true")]
    pub visible: bool,
    #[serde(default = "default_opacity")]
    pub opacity: u8,
    #[serde(default)]
    pub blend_mode: BlendMode,
    #[serde(default)]
    pub locked: bool,
    #[serde(default)]
    pub z_order: i32,
    #[serde(default, with = "pixel_serde")]
    pub pixels: Arc<PixelMap>,
}

fn default_true() -> bool {
    true
}

fn default_opacity() -> u8 {
    255
}

impl Layer {
    /// Mutable access to the pixel map (clones it first if shared with history).
    pub fn pixels_mut(&mut self) -> &mut PixelMap {
        Arc::make_mut(&mut self.pixels)
    }
}

/// Blend modes for layer compositing.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BlendMode {
    #[default]
    Normal,
    Multiply,
    Screen,
    Overlay,
}

/// Sprite region definition on the sheet (in grid cells).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SpriteDef {
    pub id: String,
    pub name: String,
    pub grid_x: u32,
    pub grid_y: u32,
    #[serde(default = "default_one")]
    pub width_cells: u32,
    #[serde(default = "default_one")]
    pub height_cells: u32,
    /// Anchor/pivot relative to the sprite's top-left pixel.
    #[serde(default)]
    pub anchor_x: u32,
    #[serde(default)]
    pub anchor_y: u32,
    #[serde(default)]
    pub hitbox: Option<HitboxRect>,
    #[serde(default)]
    pub tags: Vec<String>,
}

fn default_one() -> u32 {
    1
}

/// Hitbox rectangle relative to sprite origin.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HitboxRect {
    pub x: u32,
    pub y: u32,
    pub width: u32,
    pub height: u32,
}

/// Animation definition as a sequence of sprite frames.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AnimationDef {
    pub id: String,
    pub name: String,
    pub frames: Vec<AnimFrame>,
    #[serde(default)]
    pub loop_mode: LoopMode,
    #[serde(default)]
    pub tags: Vec<String>,
}

impl AnimationDef {
    /// Total playback duration of one pass through the frames.
    pub fn total_duration_ms(&self) -> u64 {
        self.frames.iter().map(|f| u64::from(f.duration_ms)).sum()
    }
}

/// A single animation frame referencing a sprite by ID.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AnimFrame {
    pub sprite_id: String,
    #[serde(default = "default_duration")]
    pub duration_ms: u32,
}

fn default_duration() -> u32 {
    100
}

/// Animation loop behavior.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LoopMode {
    #[default]
    Loop,
    Once,
    PingPong,
}

/// Everything an undoable edit can change.
#[derive(Debug, Clone)]
pub struct EditableState {
    pub canvas: Canvas,
    pub grid: Grid,
    pub palette: Palette,
    pub layers: Vec<Layer>,
    pub sprites: Vec<SpriteDef>,
    pub animations: Vec<AnimationDef>,
}

/// One undo/redo step: the state before (undo) or after (redo) an edit.
#[derive(Debug, Clone)]
pub struct Snapshot {
    /// Human-readable description of the edit (e.g. "draw_line").
    pub label: String,
    pub state: EditableState,
}

/// Runtime undo/redo stacks.
#[derive(Debug, Clone, Default)]
pub struct History {
    pub undo: VecDeque<Snapshot>,
    pub redo: Vec<Snapshot>,
}

/// Overlay options for rendering.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct OverlayOptions {
    #[serde(default)]
    pub grid_lines: bool,
    #[serde(default)]
    pub bounding_boxes: bool,
    #[serde(default)]
    pub anchors: bool,
    #[serde(default)]
    pub hitboxes: bool,
    #[serde(default)]
    pub sprite_names: bool,
}

impl OverlayOptions {
    /// True when at least one overlay is requested.
    pub fn any(&self) -> bool {
        self.grid_lines || self.bounding_boxes || self.anchors || self.hitboxes || self.sprite_names
    }
}

/// Transform operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TransformOp {
    FlipH,
    FlipV,
    #[serde(rename = "rotate_90_cw")]
    Rotate90Cw,
    #[serde(rename = "rotate_90_ccw")]
    Rotate90Ccw,
    #[serde(rename = "rotate_180")]
    Rotate180,
    Shift,
}

/// Serde support for [`Layer::pixels`].
///
/// Serializes as a sorted array of `[x, y, color_index]`. Deserializes from
/// that form or from the legacy `{"x,y": color_index}` map.
mod pixel_serde {
    use super::*;

    pub fn serialize<S: Serializer>(pixels: &Arc<PixelMap>, s: S) -> Result<S::Ok, S::Error> {
        let mut sorted: Vec<(&(u32, u32), &u8)> = pixels.iter().collect();
        sorted.sort_unstable_by_key(|(k, _)| (k.1, k.0));
        let mut seq = s.serialize_seq(Some(sorted.len()))?;
        for (&(x, y), &c) in sorted {
            seq.serialize_element(&[x, y, u32::from(c)])?;
        }
        seq.end()
    }

    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Repr {
        Triples(Vec<[u32; 3]>),
        Map(HashMap<String, u32>),
    }

    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> Result<Arc<PixelMap>, D::Error> {
        let repr = Repr::deserialize(d).map_err(|_| {
            de::Error::custom(
                "layer pixels must be an array of [x, y, color_index] triples \
                 or a map of \"x,y\" -> color_index",
            )
        })?;
        let mut map = PixelMap::new();
        match repr {
            Repr::Triples(v) => {
                map.reserve(v.len());
                for [x, y, c] in v {
                    let c = u8::try_from(c).map_err(|_| {
                        de::Error::custom(format!("pixel ({x},{y}): color index {c} > 255"))
                    })?;
                    map.insert((x, y), c);
                }
            },
            Repr::Map(m) => {
                map.reserve(m.len());
                for (k, c) in m {
                    let (xs, ys) = k.split_once(',').ok_or_else(|| {
                        de::Error::custom(format!("pixel key '{k}' is not of the form \"x,y\""))
                    })?;
                    let x: u32 = xs.trim().parse().map_err(|_| {
                        de::Error::custom(format!("pixel key '{k}': bad x coordinate"))
                    })?;
                    let y: u32 = ys.trim().parse().map_err(|_| {
                        de::Error::custom(format!("pixel key '{k}': bad y coordinate"))
                    })?;
                    let c = u8::try_from(c).map_err(|_| {
                        de::Error::custom(format!("pixel ({x},{y}): color index {c} > 255"))
                    })?;
                    map.insert((x, y), c);
                }
            },
        }
        Ok(Arc::new(map))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn layer_with(pixels: &[((u32, u32), u8)]) -> Layer {
        Layer {
            id: "l".into(),
            name: "l".into(),
            visible: true,
            opacity: 255,
            blend_mode: BlendMode::Normal,
            locked: false,
            z_order: 0,
            pixels: Arc::new(pixels.iter().copied().collect()),
        }
    }

    #[test]
    fn pixels_serialize_as_sorted_triples() {
        let l = layer_with(&[((3, 1), 2), ((0, 0), 1), ((1, 0), 5)]);
        let v = serde_json::to_value(&l).unwrap();
        assert_eq!(v["pixels"], json!([[0, 0, 1], [1, 0, 5], [3, 1, 2]]));
    }

    #[test]
    fn pixels_roundtrip() {
        let l = layer_with(&[((7, 9), 4), ((0, 0), 255)]);
        let s = serde_json::to_string(&l).unwrap();
        let back: Layer = serde_json::from_str(&s).unwrap();
        assert_eq!(*back.pixels, *l.pixels);
    }

    #[test]
    fn pixels_accept_legacy_map_form() {
        let v = json!({"id": "a", "name": "a", "pixels": {"1,2": 3, "0,0": 1}});
        let l: Layer = serde_json::from_value(v).unwrap();
        assert_eq!(l.pixels.get(&(1, 2)), Some(&3));
        assert!(l.visible);
        assert_eq!(l.opacity, 255);
    }

    #[test]
    fn pixels_reject_bad_color() {
        let v = json!({"id": "a", "name": "a", "pixels": [[0, 0, 300]]});
        let err = serde_json::from_value::<Layer>(v).unwrap_err().to_string();
        assert!(err.contains("255"), "{err}");
    }

    #[test]
    fn transform_op_names() {
        let op: TransformOp = serde_json::from_value(json!("rotate_90_cw")).unwrap();
        assert_eq!(op, TransformOp::Rotate90Cw);
        let op: TransformOp = serde_json::from_value(json!("flip_h")).unwrap();
        assert_eq!(op, TransformOp::FlipH);
    }

    #[test]
    fn palette_lut_matches_get_color() {
        let p = Palette {
            name: "x".into(),
            colors: vec![PaletteColor {
                index: 9,
                name: "n".into(),
                rgba: [1, 2, 3, 4],
            }],
            enforce: true,
        };
        let lut = p.lut();
        assert_eq!(lut[9], p.get_color(9));
        assert_eq!(lut[0], None);
    }
}
