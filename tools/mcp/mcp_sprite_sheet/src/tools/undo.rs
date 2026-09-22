//! Undo/redo tool.

use serde::Deserialize;
use serde_json::json;

use super::{get_mut, invalid, ok_json, sprite_tool};
use crate::args;
use crate::engine;

#[derive(Deserialize)]
pub struct UndoArgs {
    name: String,
    #[serde(default, deserialize_with = "args::opt_bool")]
    redo: Option<bool>,
    #[serde(default, deserialize_with = "args::opt_int")]
    steps: Option<u32>,
}

sprite_tool! {
    UndoTool {
        name: "sprite_undo",
        description: "Undo the last edit (or redo with redo=true). Covers every mutating tool: \
            drawing, layer, palette, sprite/animation, transform, trim, and canvas-resize \
            operations. History holds up to 50 steps per project, is kept in memory only, and \
            starts empty after create/load/import.",
        schema: json!({
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Project name" },
                "redo": { "type": "boolean", "default": false, "description": "Redo instead of undo" },
                "steps": { "type": "integer", "minimum": 1, "maximum": 50, "default": 1, "description": "Number of steps to undo/redo" }
            },
            "required": ["name"]
        }),
        execute: |ctx, a: UndoArgs| {
            let is_redo = a.redo.unwrap_or(false);
            let steps = a.steps.unwrap_or(1).clamp(1, engine::MAX_UNDO as u32);
            let mut store = ctx.store.write().await;
            let p = get_mut(&mut store, &a.name)?;
            let mut labels = Vec::new();
            for _ in 0..steps {
                let r = if is_redo { engine::redo(p) } else { engine::undo(p) };
                match r {
                    Ok(label) => labels.push(label),
                    Err(e) if labels.is_empty() => return Err(invalid(e)),
                    Err(_) => break,
                }
            }
            ok_json(json!({
                "success": true,
                "action": if is_redo { "redo" } else { "undo" },
                "operations": labels,
                "undo_depth": p.history.undo.len(),
                "redo_depth": p.history.redo.len()
            }))
        }
    }
}
