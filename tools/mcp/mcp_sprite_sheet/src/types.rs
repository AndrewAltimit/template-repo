//! Domain types for sprite sheet projects.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A complete sprite sheet project
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpriteProject {
    pub name: String,
    pub canvas: Canvas,
    pub grid: Grid,
    pub palette: Palette,
    pub layers: Vec<Layer>,
    pub sprites: Vec<SpriteDef>,
    pub animations: Vec<AnimationDef>,
    #[serde(skip)]
    pub undo_stack: Vec<UndoSnapshot>,
    #[serde(skip)]
    pub redo_stack: Vec<UndoSnapshot>,
}

/// Canvas dimensions and background
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Canvas {
    pub width: u32,
    pub height: u32,
    pub background_color: [u8; 4],
}

/// Grid configuration for sprite cells
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Grid {
    pub cell_width: u32,
    pub cell_height: u32,
    pub padding: u32,
    pub margin: u32,
}

/// A named color with palette index
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaletteColor {
    pub index: u8,
    pub name: String,
    pub rgba: [u8; 4],
}

/// Palette of indexed colors
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Palette {
    pub name: String,
    pub colors: Vec<PaletteColor>,
    pub enforce: bool,
}

impl Palette {
    /// Look up RGBA by palette index
    pub fn get_color(&self, index: u8) -> Option<[u8; 4]> {
        self.colors
            .iter()
            .find(|c| c.index == index)
            .map(|c| c.rgba)
    }

    /// Check if a palette index is valid
    pub fn is_valid_index(&self, index: u8) -> bool {
        self.colors.iter().any(|c| c.index == index)
    }
}

/// A single drawing layer with sparse pixel storage
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Layer {
    pub id: String,
    pub name: String,
    pub visible: bool,
    pub opacity: u8,
    pub blend_mode: BlendMode,
    pub locked: bool,
    pub z_order: i32,
    /// Sparse pixel data: (x, y) -> palette color index
    pub pixels: HashMap<(u32, u32), u8>,
}

/// Blend modes for layer compositing
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BlendMode {
    #[default]
    Normal,
    Multiply,
    Screen,
    Overlay,
}

/// Sprite region definition on the sheet
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpriteDef {
    pub id: String,
    pub name: String,
    pub grid_x: u32,
    pub grid_y: u32,
    pub width_cells: u32,
    pub height_cells: u32,
    pub anchor_x: u32,
    pub anchor_y: u32,
    pub hitbox: Option<HitboxRect>,
    pub tags: Vec<String>,
}

/// Hitbox rectangle relative to sprite origin
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HitboxRect {
    pub x: u32,
    pub y: u32,
    pub width: u32,
    pub height: u32,
}

/// Animation definition as a sequence of sprite frames
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnimationDef {
    pub id: String,
    pub name: String,
    pub frames: Vec<AnimFrame>,
    pub loop_mode: LoopMode,
    pub tags: Vec<String>,
}

/// A single animation frame referencing a sprite
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnimFrame {
    pub sprite_id: String,
    pub duration_ms: u32,
}

/// Animation loop behavior
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LoopMode {
    #[default]
    Loop,
    Once,
    PingPong,
}

/// Snapshot of a layer's pixel data for undo/redo
#[derive(Debug, Clone)]
pub struct UndoSnapshot {
    pub layer_id: String,
    pub pixels: HashMap<(u32, u32), u8>,
}

/// Overlay options for rendering
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
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

/// Transform operations
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TransformOp {
    FlipH,
    FlipV,
    Rotate90Cw,
    Rotate90Ccw,
    Rotate180,
    Shift,
}
