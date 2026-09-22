//! Project save/load (versioned JSON) and atlas metadata export.

use serde_json::{Value, json};
use std::collections::HashSet;
use std::sync::Arc;

use crate::engine::{self, EResult};
use crate::types::*;

/// Maximum size of a project file accepted by `sprite_load_project`.
pub const MAX_PROJECT_FILE_BYTES: u64 = 256 * 1024 * 1024;

/// Serialize a project to its persisted JSON form (current format version).
pub fn to_json(p: &SpriteProject) -> EResult<Value> {
    let mut v = serde_json::to_value(p).map_err(|e| format!("Serialize error: {e}"))?;
    v["format_version"] = json!(FORMAT_VERSION);
    Ok(v)
}

/// Non-fatal issues found (and repaired) while loading a project.
#[derive(Debug, Default)]
pub struct LoadReport {
    pub source_version: u32,
    pub warnings: Vec<String>,
}

/// Parse and validate project JSON, repairing recoverable problems.
///
/// Fatal: unsupported (newer) version, invalid canvas/grid/palette.
/// Repaired with a warning: pixels outside the canvas, duplicate layer IDs,
/// duplicate sprite/animation IDs, animation frames referencing missing
/// sprites.
pub fn from_json(data: Value, rename: Option<&str>) -> EResult<(SpriteProject, LoadReport)> {
    let mut p: SpriteProject = serde_path_to_error::deserialize(data)
        .map_err(|e| format!("Invalid project data at '{}': {}", e.path(), e.inner()))?;
    let mut report = LoadReport {
        source_version: p.format_version,
        warnings: Vec::new(),
    };
    if p.format_version > FORMAT_VERSION {
        return Err(format!(
            "Project format version {} is newer than this server supports ({FORMAT_VERSION})",
            p.format_version
        ));
    }
    if let Some(n) = rename {
        p.name = n.to_string();
    }
    engine::validate_project_name(&p.name)?;
    engine::validate_canvas(p.canvas.width, p.canvas.height)?;
    engine::validate_grid(&p.grid)?;
    engine::validate_palette(&p.palette)?;

    let (cw, ch) = (p.canvas.width, p.canvas.height);
    let mut layer_ids = HashSet::new();
    for layer in &mut p.layers {
        if layer.id.is_empty() || !layer_ids.insert(layer.id.clone()) {
            let new_id = uuid::Uuid::new_v4().to_string();
            report.warnings.push(format!(
                "Layer '{}' had a missing/duplicate id; assigned {new_id}",
                layer.name
            ));
            layer.id = new_id.clone();
            layer_ids.insert(new_id);
        }
        let before = layer.pixels.len();
        if layer.pixels.keys().any(|&(x, y)| x >= cw || y >= ch) {
            let kept: PixelMap = layer
                .pixels
                .iter()
                .filter(|&(&(x, y), _)| x < cw && y < ch)
                .map(|(&k, &v)| (k, v))
                .collect();
            report.warnings.push(format!(
                "Layer '{}': dropped {} pixels outside the {cw}x{ch} canvas",
                layer.name,
                before - kept.len()
            ));
            layer.pixels = Arc::new(kept);
        }
    }

    let mut sprite_ids = HashSet::new();
    for s in &mut p.sprites {
        if s.id.is_empty() || !sprite_ids.insert(s.id.clone()) {
            s.id = uuid::Uuid::new_v4().to_string();
            sprite_ids.insert(s.id.clone());
            report.warnings.push(format!(
                "Sprite '{}' had a missing/duplicate id; reassigned",
                s.name
            ));
        }
    }
    let mut anim_ids = HashSet::new();
    for a in &mut p.animations {
        if a.id.is_empty() || !anim_ids.insert(a.id.clone()) {
            a.id = uuid::Uuid::new_v4().to_string();
            anim_ids.insert(a.id.clone());
            report.warnings.push(format!(
                "Animation '{}' had a missing/duplicate id; reassigned",
                a.name
            ));
        }
        let before = a.frames.len();
        a.frames.retain(|f| sprite_ids.contains(&f.sprite_id));
        if a.frames.len() != before {
            report.warnings.push(format!(
                "Animation '{}': removed {} frames referencing unknown sprites",
                a.name,
                before - a.frames.len()
            ));
        }
    }
    for s in &p.sprites {
        if let Err(e) = engine::validate_sprite(&p, s) {
            report.warnings.push(format!("Sprite '{}': {e}", s.name));
        }
    }
    p.format_version = FORMAT_VERSION;
    p.history = History::default();
    Ok((p, report))
}

/// Build atlas metadata describing every sprite and animation.
///
/// Coordinates are in output-image pixels (multiplied by `scale`).
pub fn atlas_json(p: &SpriteProject, image_file: &str, scale: u32) -> Value {
    let s = scale.max(1);
    let by_id: std::collections::HashMap<&str, &str> = p
        .sprites
        .iter()
        .map(|sp| (sp.id.as_str(), sp.name.as_str()))
        .collect();
    let frames: Vec<Value> = p
        .sprites
        .iter()
        .map(|sp| {
            let (x, y, w, h) = engine::sprite_pixel_bounds(p, sp);
            let mut f = json!({
                "id": sp.id,
                "name": sp.name,
                "frame": { "x": x * s, "y": y * s, "w": w * s, "h": h * s },
                "anchor": { "x": sp.anchor_x * s, "y": sp.anchor_y * s },
                "pivot": {
                    "x": if w > 0 { f64::from(sp.anchor_x) / f64::from(w) } else { 0.0 },
                    "y": if h > 0 { f64::from(sp.anchor_y) / f64::from(h) } else { 0.0 }
                },
                "tags": sp.tags,
            });
            if let Some(hb) = &sp.hitbox {
                f["hitbox"] = json!({
                    "x": hb.x * s, "y": hb.y * s, "w": hb.width * s, "h": hb.height * s
                });
            }
            f
        })
        .collect();
    let animations: Vec<Value> = p
        .animations
        .iter()
        .map(|a| {
            json!({
                "id": a.id,
                "name": a.name,
                "loop_mode": a.loop_mode,
                "total_duration_ms": a.total_duration_ms(),
                "tags": a.tags,
                "frames": a.frames.iter().map(|f| json!({
                    "sprite": by_id.get(f.sprite_id.as_str()).copied().unwrap_or(""),
                    "sprite_id": f.sprite_id,
                    "duration_ms": f.duration_ms,
                })).collect::<Vec<_>>(),
            })
        })
        .collect();
    json!({
        "meta": {
            "app": "mcp-sprite-sheet",
            "version": env!("CARGO_PKG_VERSION"),
            "project": p.name,
            "image": image_file,
            "size": { "w": p.canvas.width * s, "h": p.canvas.height * s },
            "scale": s,
            "grid": {
                "cell_width": p.grid.cell_width,
                "cell_height": p.grid.cell_height,
                "padding": p.grid.padding,
                "margin": p.grid.margin
            }
        },
        "frames": frames,
        "animations": animations,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn project() -> SpriteProject {
        let grid = Grid {
            cell_width: 8,
            cell_height: 8,
            padding: 0,
            margin: 0,
        };
        let mut p = engine::create_project("p", 16, 16, grid, [0; 4], Some("pico8")).unwrap();
        let id = engine::add_layer(&mut p, "base", None);
        engine::set_pixels(&mut p, &id, &[(0, 0, 1), (15, 15, 2)]).unwrap();
        let (sid, _) = engine::define_sprite(
            &mut p,
            SpriteDef {
                id: String::new(),
                name: "idle".into(),
                grid_x: 1,
                grid_y: 0,
                width_cells: 1,
                height_cells: 1,
                anchor_x: 4,
                anchor_y: 8,
                hitbox: None,
                tags: vec![],
            },
        )
        .unwrap();
        engine::define_animation(
            &mut p,
            "blink",
            vec![AnimFrame {
                sprite_id: sid,
                duration_ms: 120,
            }],
            LoopMode::PingPong,
            vec!["ui".into()],
        )
        .unwrap();
        p
    }

    #[test]
    fn save_with_pixels_roundtrips() {
        // Regression: HashMap<(u32,u32),u8> used to fail to serialize
        // ("key must be a string"), so any project with pixels could not be saved.
        let p = project();
        let v = to_json(&p).unwrap();
        assert_eq!(v["format_version"], json!(FORMAT_VERSION));
        let text = serde_json::to_string(&v).unwrap();
        let (back, rep) = from_json(serde_json::from_str(&text).unwrap(), None).unwrap();
        assert!(rep.warnings.is_empty(), "{:?}", rep.warnings);
        assert_eq!(*back.layers[0].pixels, *p.layers[0].pixels);
        assert_eq!(back.sprites, p.sprites);
        assert_eq!(back.animations, p.animations);
    }

    #[test]
    fn load_legacy_v1_without_version() {
        let v = json!({
            "name": "old",
            "canvas": {"width": 4, "height": 4, "background_color": [0,0,0,0]},
            "grid": {"cell_width": 4, "cell_height": 4, "padding": 0, "margin": 0},
            "palette": {"name": "c", "colors": [{"index": 1, "name": "k", "rgba": [0,0,0,255]}], "enforce": false},
            "layers": [{"id": "a", "name": "a", "visible": true, "opacity": 255,
                        "blend_mode": "normal", "locked": false, "z_order": 0, "pixels": {}}],
            "sprites": [],
            "animations": []
        });
        let (p, rep) = from_json(v, Some("renamed")).unwrap();
        assert_eq!(rep.source_version, 1);
        assert_eq!(p.format_version, FORMAT_VERSION);
        assert_eq!(p.name, "renamed");
    }

    #[test]
    fn load_repairs_and_rejects() {
        let mut v = to_json(&project()).unwrap();
        v["layers"][0]["pixels"] = json!([[0, 0, 1], [99, 99, 1]]);
        v["animations"][0]["frames"] = json!([{"sprite_id": "ghost", "duration_ms": 10}]);
        let (p, rep) = from_json(v.clone(), None).unwrap();
        assert_eq!(p.layers[0].pixels.len(), 1);
        assert_eq!(rep.warnings.len(), 2, "{:?}", rep.warnings);

        let mut newer = v.clone();
        newer["format_version"] = json!(FORMAT_VERSION + 1);
        assert!(from_json(newer, None).unwrap_err().contains("newer"));

        let mut huge = v.clone();
        huge["canvas"]["width"] = json!(1_000_000);
        assert!(from_json(huge, None).is_err());

        let mut bad = v;
        bad["layers"][0]["opacity"] = json!("lots");
        let e = from_json(bad, None).unwrap_err();
        assert!(e.contains("layers[0].opacity"), "{e}");
    }

    #[test]
    fn atlas_contains_frames_and_animations() {
        let p = project();
        let a = atlas_json(&p, "p.png", 2);
        assert_eq!(a["meta"]["size"]["w"], json!(32));
        assert_eq!(a["frames"][0]["frame"]["x"], json!(16));
        assert_eq!(a["frames"][0]["pivot"]["y"], json!(1.0));
        assert_eq!(a["animations"][0]["frames"][0]["sprite"], json!("idle"));
        assert_eq!(a["animations"][0]["loop_mode"], json!("ping_pong"));
    }
}
