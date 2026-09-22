//! One-click effects modelled on Blender's Object > Quick Effects menu.

use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{Value, json};

use crate::server::{
    BlenderTool, Ctx, ToolOutput, check_names, check_range, enum_prop, names_prop, project_prop,
};
use crate::types::{FurDensity, SmokeStyle};

fn no() -> bool {
    false
}
fn yes() -> bool {
    true
}

/// `quick_smoke` arguments.
#[derive(Debug, Deserialize)]
pub struct QuickSmokeArgs {
    project: String,
    object_names: Vec<String>,
    #[serde(default = "default_style")]
    style: SmokeStyle,
    #[serde(default = "no")]
    show_flows: bool,
    #[serde(default = "default_smoke_res")]
    domain_resolution: u32,
}

fn default_style() -> SmokeStyle {
    SmokeStyle::Smoke
}
fn default_smoke_res() -> u32 {
    32
}

/// Smoke/fire around the given meshes.
pub struct QuickSmoke;

#[async_trait]
impl BlenderTool for QuickSmoke {
    type Args = QuickSmokeArgs;
    const NAME: &'static str = "quick_smoke";
    const DESCRIPTION: &'static str = "Add a smoke/fire simulation in one step: the meshes become flow emitters inside a \
new 'Smoke Domain' with a volume material.\n\nStyles: SMOKE, FIRE, BOTH. Bake with bake_simulation before rendering.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_names": names_prop("Mesh objects to make smoke emitters"),
                "style": enum_prop(SmokeStyle::ALL, Some("SMOKE"), "Emission style"),
                "show_flows": { "type": "boolean", "default": false, "description": "Keep emitters visible (otherwise shown as wireframe)" },
                "domain_resolution": { "type": "integer", "minimum": 8, "maximum": 1024, "default": 32 }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        check_names("object_names", &args.object_names)?;
        check_range("domain_resolution", args.domain_resolution, 8, 1024)?;
        let script_args = json!({
            "operation": "quick_smoke",
            "project": project.path.to_string_lossy(),
            "object_names": args.object_names,
            "style": args.style,
            "show_flows": args.show_flows,
            "domain_resolution": args.domain_resolution,
        });
        let result = ctx
            .operation("quick_effects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "style": args.style,
            "message": format!("Smoke simulation '{}' created", args.style),
            "result": result,
        }))
    }
}

/// `quick_liquid` arguments.
#[derive(Debug, Deserialize)]
pub struct QuickLiquidArgs {
    project: String,
    object_names: Vec<String>,
    #[serde(default = "no")]
    show_flows: bool,
    #[serde(default = "default_liquid_res")]
    domain_resolution: u32,
}

fn default_liquid_res() -> u32 {
    64
}

/// Liquid simulation around the given meshes.
pub struct QuickLiquid;

#[async_trait]
impl BlenderTool for QuickLiquid {
    type Args = QuickLiquidArgs;
    const NAME: &'static str = "quick_liquid";
    const DESCRIPTION: &'static str = "Add a liquid simulation in one step: the meshes become liquid sources inside a new \
'Liquid Domain' with a water-like material. Bake with bake_simulation before rendering.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_names": names_prop("Mesh objects to make liquid sources"),
                "show_flows": { "type": "boolean", "default": false },
                "domain_resolution": { "type": "integer", "minimum": 8, "maximum": 1024, "default": 64 }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        check_names("object_names", &args.object_names)?;
        check_range("domain_resolution", args.domain_resolution, 8, 1024)?;
        let script_args = json!({
            "operation": "quick_liquid",
            "project": project.path.to_string_lossy(),
            "object_names": args.object_names,
            "show_flows": args.show_flows,
            "domain_resolution": args.domain_resolution,
        });
        let result = ctx
            .operation("quick_effects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({ "success": true, "message": "Liquid simulation created", "result": result }))
    }
}

/// `quick_explode` arguments.
#[derive(Debug, Deserialize)]
pub struct QuickExplodeArgs {
    project: String,
    object_names: Vec<String>,
    #[serde(default = "default_pieces")]
    piece_count: u32,
    #[serde(default = "default_start")]
    frame_start: i64,
    #[serde(default = "default_duration")]
    frame_duration: i64,
    #[serde(default = "default_velocity")]
    velocity: f64,
    #[serde(default = "yes")]
    fade: bool,
}

fn default_pieces() -> u32 {
    100
}
fn default_start() -> i64 {
    1
}
fn default_duration() -> i64 {
    50
}
fn default_velocity() -> f64 {
    1.0
}

/// Shatter meshes with a particle-driven explode modifier.
pub struct QuickExplode;

#[async_trait]
impl BlenderTool for QuickExplode {
    type Args = QuickExplodeArgs;
    const NAME: &'static str = "quick_explode";
    const DESCRIPTION: &'static str = "Make meshes explode: adds a particle system plus Explode modifier (pieces fly \
apart starting at frame_start over frame_duration frames, optionally fading out). Objects that already have a \
particle system are skipped.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_names": names_prop("Mesh objects to explode"),
                "piece_count": { "type": "integer", "minimum": 1, "maximum": 100000, "default": 100 },
                "frame_start": { "type": "integer", "default": 1 },
                "frame_duration": { "type": "integer", "minimum": 1, "default": 50 },
                "velocity": { "type": "number", "minimum": 0, "default": 1.0 },
                "fade": { "type": "boolean", "default": true }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        check_names("object_names", &args.object_names)?;
        check_range("piece_count", args.piece_count, 1, 100_000)?;
        check_range("frame_duration", args.frame_duration, 1, 100_000)?;
        check_range("velocity", args.velocity, 0.0, 1000.0)?;
        let script_args = json!({
            "operation": "quick_explode",
            "project": project.path.to_string_lossy(),
            "object_names": args.object_names,
            "piece_count": args.piece_count,
            "frame_start": args.frame_start,
            "frame_duration": args.frame_duration,
            "velocity": args.velocity,
            "fade": args.fade,
        });
        let result = ctx
            .operation("quick_effects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "pieces": args.piece_count,
            "message": "Explosion effect created",
            "result": result,
        }))
    }
}

/// `quick_fur` arguments.
#[derive(Debug, Deserialize)]
pub struct QuickFurArgs {
    project: String,
    object_names: Vec<String>,
    #[serde(default = "default_density")]
    density: FurDensity,
    #[serde(default = "default_length")]
    length: f64,
    #[serde(default = "default_radius")]
    radius: f64,
    #[serde(default = "yes")]
    use_noise: bool,
    #[serde(default = "yes")]
    use_frizz: bool,
}

fn default_density() -> FurDensity {
    FurDensity::Medium
}
fn default_length() -> f64 {
    0.1
}
fn default_radius() -> f64 {
    0.001
}

/// Procedural fur (hair curves + geometry nodes).
pub struct QuickFur;

#[async_trait]
impl BlenderTool for QuickFur {
    type Args = QuickFurArgs;
    const NAME: &'static str = "quick_fur";
    const DESCRIPTION: &'static str = "Grow procedural fur on meshes: creates a hair-curves object per mesh ('<mesh>_Fur', \
parented to it) driven by geometry nodes. density: LOW (1k strands), MEDIUM (10k), HIGH (100k) per object; length and \
radius in scene units; use_noise adds clumpy displacement and use_frizz random jitter toward the tips.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_names": names_prop("Mesh objects to add fur to"),
                "density": enum_prop(FurDensity::ALL, Some("MEDIUM"), "Strand count"),
                "length": { "type": "number", "exclusiveMinimum": 0, "default": 0.1 },
                "radius": { "type": "number", "exclusiveMinimum": 0, "default": 0.001 },
                "use_noise": { "type": "boolean", "default": true },
                "use_frizz": { "type": "boolean", "default": true }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        check_names("object_names", &args.object_names)?;
        check_range("length", args.length, 1.0e-6, 1000.0)?;
        check_range("radius", args.radius, 1.0e-7, 10.0)?;
        let script_args = json!({
            "operation": "quick_fur",
            "project": project.path.to_string_lossy(),
            "object_names": args.object_names,
            "density": args.density,
            "length": args.length,
            "radius": args.radius,
            "use_noise": args.use_noise,
            "use_frizz": args.use_frizz,
        });
        let result = ctx
            .operation("quick_effects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "density": args.density,
            "message": "Fur system created",
            "result": result,
        }))
    }
}
