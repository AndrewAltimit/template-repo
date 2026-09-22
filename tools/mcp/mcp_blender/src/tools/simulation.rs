//! Camera, animation, modifiers, physics/particles and geometry nodes.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};

use crate::server::{
    BlenderTool, Ctx, ToolError, ToolOutput, check_name, check_range, enum_prop, project_prop,
    vec3_prop,
};
use crate::types::{
    CollisionShape, GeometryNodeSetup, Interpolation, ModifierType, ParticleType, PhysicsType,
    SmokeType, TrackType,
};

/// Free-form, script-specific settings.
type Settings = Map<String, Value>;

// ---------------------------------------------------------------------------
// setup_camera / add_camera_track
// ---------------------------------------------------------------------------

/// `setup_camera` arguments.
#[derive(Debug, Deserialize)]
pub struct SetupCameraArgs {
    project: String,
    #[serde(default)]
    camera_name: Option<String>,
    #[serde(default = "default_cam_location")]
    location: [f64; 3],
    #[serde(default = "default_cam_rotation")]
    rotation: [f64; 3],
    #[serde(default = "default_focal")]
    focal_length: f64,
    #[serde(default = "default_sensor")]
    sensor_width: f64,
    #[serde(default)]
    dof_enabled: bool,
    #[serde(default = "default_focus")]
    focus_distance: f64,
    #[serde(default = "default_aperture")]
    aperture: f64,
    #[serde(default)]
    focus_object: Option<String>,
    #[serde(default = "yes")]
    set_active: bool,
}

fn default_cam_location() -> [f64; 3] {
    [7.0, -6.0, 5.0]
}
fn default_cam_rotation() -> [f64; 3] {
    [1.1, 0.0, 0.8]
}
fn default_focal() -> f64 {
    50.0
}
fn default_sensor() -> f64 {
    36.0
}
fn default_focus() -> f64 {
    10.0
}
fn default_aperture() -> f64 {
    2.8
}
fn yes() -> bool {
    true
}

/// Create or update a camera.
pub struct SetupCamera;

#[async_trait]
impl BlenderTool for SetupCamera {
    type Args = SetupCameraArgs;
    const NAME: &'static str = "setup_camera";
    const DESCRIPTION: &'static str = "Create or update a camera (default name 'Camera') and make it the active scene \
camera. Rotation is Euler XYZ in radians. Depth of field: dof_enabled, focus_distance (or focus_object), aperture \
(f-stop).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "camera_name": { "type": "string", "default": "Camera", "description": "Camera object to create or update" },
                "location": vec3_prop("Camera location", Some(default_cam_location())),
                "rotation": vec3_prop("Euler rotation in radians", Some(default_cam_rotation())),
                "focal_length": { "type": "number", "minimum": 1, "maximum": 5000, "default": 50 },
                "sensor_width": { "type": "number", "minimum": 1, "maximum": 200, "default": 36 },
                "dof_enabled": { "type": "boolean", "default": false },
                "focus_distance": { "type": "number", "minimum": 0, "default": 10 },
                "aperture": { "type": "number", "minimum": 0.1, "maximum": 128, "default": 2.8, "description": "f-stop" },
                "focus_object": { "type": "string", "description": "Object to keep in focus (overrides focus_distance)" },
                "set_active": { "type": "boolean", "default": true, "description": "Make this the scene camera" }
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let camera_name = match &args.camera_name {
            Some(name) => check_name("camera_name", name)?.to_string(),
            None => "Camera".to_string(),
        };
        if let Some(obj) = &args.focus_object {
            check_name("focus_object", obj)?;
        }
        check_range("focal_length", args.focal_length, 1.0, 5000.0)?;
        check_range("sensor_width", args.sensor_width, 1.0, 200.0)?;
        check_range("focus_distance", args.focus_distance, 0.0, 1.0e6)?;
        check_range("aperture", args.aperture, 0.1, 128.0)?;
        let script_args = json!({
            "operation": "setup_camera",
            "project": project.path.to_string_lossy(),
            "camera_name": camera_name,
            "location": args.location,
            "rotation": args.rotation,
            "focal_length": args.focal_length,
            "sensor_width": args.sensor_width,
            "dof_enabled": args.dof_enabled,
            "focus_distance": args.focus_distance,
            "aperture": args.aperture,
            "focus_object": args.focus_object,
            "set_active": args.set_active,
        });
        let result = ctx
            .operation("camera_tools.py", script_args, Some(&project.path))
            .await?;
        Ok(
            json!({ "success": true, "message": format!("Camera '{camera_name}' configured"), "result": result }),
        )
    }
}

/// `add_camera_track` arguments.
#[derive(Debug, Deserialize)]
pub struct AddCameraTrackArgs {
    project: String,
    target: String,
    #[serde(default = "default_track")]
    track_type: TrackType,
    #[serde(default)]
    camera_name: Option<String>,
}

fn default_track() -> TrackType {
    TrackType::TrackTo
}

/// Make a camera track an object.
pub struct AddCameraTrack;

#[async_trait]
impl BlenderTool for AddCameraTrack {
    type Args = AddCameraTrackArgs;
    const NAME: &'static str = "add_camera_track";
    const DESCRIPTION: &'static str = "Make a camera (default: the active camera) always point at a target object using \
a TRACK_TO, DAMPED_TRACK or LOCKED_TRACK constraint. Replaces any existing tracking constraint on the camera.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "target": { "type": "string", "description": "Target object name" },
                "track_type": enum_prop(TrackType::ALL, Some("TRACK_TO"), "Constraint type"),
                "camera_name": { "type": "string", "description": "Camera object (default: active camera)" }
            },
            "required": ["project", "target"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let target = check_name("target", &args.target)?.to_string();
        if let Some(cam) = &args.camera_name {
            check_name("camera_name", cam)?;
        }
        let script_args = json!({
            "operation": "add_camera_track",
            "project": project.path.to_string_lossy(),
            "target": target,
            "track_type": args.track_type,
            "camera_name": args.camera_name,
        });
        let result = ctx
            .operation("camera_tools.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "target": target,
            "track_type": args.track_type,
            "camera": result.get("camera"),
            "message": format!("Camera tracking '{}' added to target '{target}'", args.track_type),
        }))
    }
}

// ---------------------------------------------------------------------------
// create_animation
// ---------------------------------------------------------------------------

/// One keyframe.
#[derive(Debug, Deserialize, Serialize)]
pub struct Keyframe {
    frame: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    location: Option<[f64; 3]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    rotation: Option<[f64; 3]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    scale: Option<[f64; 3]>,
}

/// `create_animation` arguments.
#[derive(Debug, Deserialize)]
pub struct CreateAnimationArgs {
    project: String,
    object_name: String,
    keyframes: Vec<Keyframe>,
    #[serde(default = "default_interp")]
    interpolation: Interpolation,
}

fn default_interp() -> Interpolation {
    Interpolation::Bezier
}

/// Keyframe an object's transform.
pub struct CreateAnimation;

#[async_trait]
impl BlenderTool for CreateAnimation {
    type Args = CreateAnimationArgs;
    const NAME: &'static str = "create_animation";
    const DESCRIPTION: &'static str = "Replace an object's animation with transform keyframes. Each keyframe has a frame \
and any of location, rotation (Euler radians) and scale. Interpolation: LINEAR, BEZIER, CONSTANT. The scene end frame \
is extended to include the last keyframe.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Object to animate" },
                "keyframes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "frame": { "type": "integer" },
                            "location": vec3_prop("Location", None),
                            "rotation": vec3_prop("Euler rotation in radians", None),
                            "scale": vec3_prop("Scale", None)
                        },
                        "required": ["frame"]
                    }
                },
                "interpolation": enum_prop(Interpolation::ALL, Some("BEZIER"), "Keyframe interpolation")
            },
            "required": ["project", "object_name", "keyframes"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        check_range("keyframes count", args.keyframes.len(), 1, 100_000)?;
        for kf in &args.keyframes {
            check_range("keyframe frame", kf.frame, -1_000_000, 1_000_000)?;
            if kf.location.is_none() && kf.rotation.is_none() && kf.scale.is_none() {
                return Err(ToolError::invalid(format!(
                    "keyframe at frame {} sets none of location/rotation/scale",
                    kf.frame
                )));
            }
        }
        let count = args.keyframes.len();
        let script_args = json!({
            "operation": "create_animation",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "keyframes": args.keyframes,
            "interpolation": args.interpolation,
        });
        let result = ctx
            .operation("animation.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "keyframes_count": count,
            "frame_range": result.get("frame_range"),
            "message": format!("Animation created with {count} keyframes"),
        }))
    }
}

// ---------------------------------------------------------------------------
// setup_physics / bake_simulation
// ---------------------------------------------------------------------------

/// `setup_physics` settings.
#[derive(Debug, Default, Deserialize, Serialize)]
pub struct PhysicsSettings {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    mass: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    friction: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    bounce: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    collision_shape: Option<CollisionShape>,
    #[serde(flatten)]
    extra: Settings,
}

/// `setup_physics` arguments.
#[derive(Debug, Deserialize)]
pub struct SetupPhysicsArgs {
    project: String,
    object_name: String,
    physics_type: PhysicsType,
    #[serde(default)]
    settings: PhysicsSettings,
}

/// Add physics to an object.
pub struct SetupPhysics;

#[async_trait]
impl BlenderTool for SetupPhysics {
    type Args = SetupPhysicsArgs;
    const NAME: &'static str = "setup_physics";
    const DESCRIPTION: &'static str = "Add physics to a mesh object.\n\nTypes: rigid_body (settings: mass, friction, \
bounce, collision_shape, rigid_body_type ACTIVE/PASSIVE), soft_body (mass, friction), cloth (quality, mass, \
air_damping), fluid (liquid inflow; creates a 'FluidDomain' unless settings.domain names an existing one). Run \
bake_simulation afterwards to cache the simulation.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Mesh object to simulate" },
                "physics_type": enum_prop(PhysicsType::ALL, None, "Type of physics simulation"),
                "settings": {
                    "type": "object",
                    "properties": {
                        "mass": { "type": "number", "minimum": 0, "default": 1.0 },
                        "friction": { "type": "number", "minimum": 0, "default": 0.5 },
                        "bounce": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.0 },
                        "collision_shape": enum_prop(CollisionShape::ALL, Some("convex_hull"), "Rigid-body collision shape"),
                        "rigid_body_type": { "type": "string", "enum": ["ACTIVE", "PASSIVE"], "default": "ACTIVE" }
                    }
                }
            },
            "required": ["project", "object_name", "physics_type"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        for (field, value) in [
            ("settings.mass", args.settings.mass),
            ("settings.friction", args.settings.friction),
        ] {
            if let Some(v) = value {
                check_range(field, v, 0.0, 1.0e6)?;
            }
        }
        if let Some(bounce) = args.settings.bounce {
            check_range("settings.bounce", bounce, 0.0, 1.0)?;
        }
        let script_args = json!({
            "operation": "setup_physics",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "physics_type": args.physics_type,
            "settings": args.settings,
        });
        let result = ctx
            .operation("physics_sim.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "physics_type": args.physics_type,
            "domain": result.get("domain"),
            "message": format!("Physics '{}' applied to '{object_name}'", args.physics_type),
        }))
    }
}

/// `bake_simulation` arguments.
#[derive(Debug, Deserialize)]
pub struct BakeSimulationArgs {
    project: String,
    #[serde(default = "one")]
    start_frame: i64,
    #[serde(default = "default_end")]
    end_frame: i64,
}

fn one() -> i64 {
    1
}
fn default_end() -> i64 {
    250
}

/// Bake simulation caches (async job).
pub struct BakeSimulation;

#[async_trait]
impl BlenderTool for BakeSimulation {
    type Args = BakeSimulationArgs;
    const NAME: &'static str = "bake_simulation";
    const DESCRIPTION: &'static str = "Bake every simulation cache in the project (rigid body, soft body, cloth, \
particles and fluid domains) for the frame range, then save the project. Runs as an async job; the project is locked \
against other edits while baking. Use get_job_status (wait_seconds) to follow it.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "start_frame": { "type": "integer", "default": 1 },
                "end_frame": { "type": "integer", "default": 250 }
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        if args.end_frame < args.start_frame {
            return Err(ToolError::invalid(format!(
                "end_frame ({}) must be >= start_frame ({})",
                args.end_frame, args.start_frame
            )));
        }
        check_range(
            "frame count",
            args.end_frame - args.start_frame + 1,
            1,
            100_000,
        )?;
        let project_path = project.path.to_string_lossy().to_string();
        let (start, end) = (args.start_frame, args.end_frame);
        let id = ctx.start_job(Self::NAME, "physics_sim.py", &project, true, |_| {
            json!({
                "operation": "bake_simulation",
                "project": project_path,
                "start_frame": start,
                "end_frame": end,
            })
        });
        Ok(json!({
            "success": true,
            "job_id": id.to_string(),
            "status": "QUEUED",
            "message": format!("Baking simulation frames {start}-{end}; poll get_job_status"),
        }))
    }
}

// ---------------------------------------------------------------------------
// add_modifier
// ---------------------------------------------------------------------------

/// `add_modifier` arguments.
#[derive(Debug, Deserialize)]
pub struct AddModifierArgs {
    project: String,
    object_name: String,
    modifier_type: ModifierType,
    #[serde(default)]
    settings: Settings,
}

/// Add a mesh modifier.
pub struct AddModifier;

#[async_trait]
impl BlenderTool for AddModifier {
    type Args = AddModifierArgs;
    const NAME: &'static str = "add_modifier";
    const DESCRIPTION: &'static str = "Add a modifier to a mesh object.\n\nTypes and settings: SUBSURF (levels, \
render_levels), ARRAY (count, relative_offset [x,y,z]), MIRROR (use_axis [bool,bool,bool], use_bisect), SOLIDIFY \
(thickness, offset), BEVEL (width, segments, limit_method, angle_limit), DECIMATE (decimate_type, ratio), REMESH \
(mode, voxel_size), SMOOTH (factor, iterations), WAVE (height, width_wave, speed, offset), DISPLACE (strength, \
mid_level). Returns the modifier name.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Mesh object name" },
                "modifier_type": enum_prop(ModifierType::ALL, None, "Modifier type"),
                "settings": { "type": "object", "description": "Modifier-specific settings" }
            },
            "required": ["project", "object_name", "modifier_type"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        let script_args = json!({
            "operation": "add_modifier",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "modifier_type": args.modifier_type,
            "settings": args.settings,
        });
        let result = ctx
            .operation("modifiers.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "modifier_type": args.modifier_type,
            "modifier": result.get("modifier"),
            "message": format!("Modifier '{}' added to '{object_name}'", args.modifier_type),
        }))
    }
}

// ---------------------------------------------------------------------------
// add_particle_system / add_smoke_simulation
// ---------------------------------------------------------------------------

/// `add_particle_system` arguments.
#[derive(Debug, Deserialize)]
pub struct AddParticleSystemArgs {
    project: String,
    object_name: String,
    #[serde(default = "default_particle")]
    particle_type: ParticleType,
    #[serde(default = "default_count")]
    count: u32,
    #[serde(default)]
    settings: Settings,
}

fn default_particle() -> ParticleType {
    ParticleType::Emitter
}
fn default_count() -> u32 {
    1000
}

/// Add an emitter or hair particle system.
pub struct AddParticleSystem;

#[async_trait]
impl BlenderTool for AddParticleSystem {
    type Args = AddParticleSystemArgs;
    const NAME: &'static str = "add_particle_system";
    const DESCRIPTION: &'static str = "Add a particle system to a mesh.\n\nemitter settings: frame_start, frame_end, \
lifetime, emit_from, physics_type (NEWTONIAN/FLUID/NO), velocity, gravity, size, render_type (HALO, OBJECT with \
render_object, ...). hair settings: length, segments, use_children, children_count.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Emitter mesh object" },
                "particle_type": enum_prop(ParticleType::ALL, Some("emitter"), "Particle system kind"),
                "count": { "type": "integer", "minimum": 1, "maximum": 10_000_000, "default": 1000 },
                "settings": { "type": "object", "description": "Particle-specific settings" }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        check_range("count", args.count, 1, 10_000_000)?;
        let script_args = json!({
            "operation": "add_particle_system",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "particle_type": args.particle_type,
            "count": args.count,
            "settings": args.settings,
        });
        let result = ctx
            .operation("particles.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "particle_type": args.particle_type,
            "count": args.count,
            "message": format!("Particle system added to '{object_name}'"),
            "result": result,
        }))
    }
}

/// `add_smoke_simulation` arguments.
#[derive(Debug, Deserialize)]
pub struct AddSmokeSimulationArgs {
    project: String,
    object_name: String,
    #[serde(default = "default_smoke")]
    smoke_type: SmokeType,
    #[serde(default)]
    settings: Settings,
}

fn default_smoke() -> SmokeType {
    SmokeType::Smoke
}

/// Make an object a smoke/fire emitter inside a new gas domain.
pub struct AddSmokeSimulation;

#[async_trait]
impl BlenderTool for AddSmokeSimulation {
    type Args = AddSmokeSimulationArgs;
    const NAME: &'static str = "add_smoke_simulation";
    const DESCRIPTION: &'static str = "Make a mesh a smoke/fire emitter and create a gas domain around it (named \
'<object>_SmokeDomain').\n\nsettings: density, temperature, fuel, color, resolution (domain, default 32), domain_size \
[x,y,z], domain_location [x,y,z], use_noise. Bake with bake_simulation. See also quick_smoke.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Emitter mesh object" },
                "smoke_type": enum_prop(SmokeType::ALL, Some("smoke"), "Emission type"),
                "settings": { "type": "object", "description": "Simulation settings" }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        if let Some(res) = args.settings.get("resolution") {
            let res = res
                .as_u64()
                .ok_or_else(|| ToolError::invalid("settings.resolution must be an integer"))?;
            check_range("settings.resolution", res, 8, 1024)?;
        }
        let script_args = json!({
            "operation": "add_smoke_simulation",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "smoke_type": args.smoke_type,
            "settings": args.settings,
        });
        let result = ctx
            .operation("particles.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "smoke_type": args.smoke_type,
            "domain": result.get("domain"),
            "message": format!("Smoke simulation added to '{object_name}'"),
        }))
    }
}

// ---------------------------------------------------------------------------
// create_geometry_nodes
// ---------------------------------------------------------------------------

/// `create_geometry_nodes` arguments.
#[derive(Debug, Deserialize)]
pub struct CreateGeometryNodesArgs {
    project: String,
    object_name: String,
    node_setup: GeometryNodeSetup,
    #[serde(default)]
    parameters: Settings,
}

/// Add a procedural geometry-node modifier.
pub struct CreateGeometryNodes;

#[async_trait]
impl BlenderTool for CreateGeometryNodes {
    type Args = CreateGeometryNodesArgs;
    const NAME: &'static str = "create_geometry_nodes";
    const DESCRIPTION: &'static str = "Add a procedural geometry-nodes modifier to an object (a suitable base mesh is \
created when the object does not exist).\n\nSetups: scatter, array, grid, curve, spiral, volume, wave_deform, twist, \
noise_displace, extrude, voronoi_scatter, mesh_to_points, crystal_scatter, crystal_cluster, custom, proximity_mask, \
blur_attribute, map_range_displacement, edge_crease_detection, organic_mutation. parameters are setup-specific (e.g. \
count, seed, scale, angle, amplitude, apply_crystal_material).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Object to apply geometry nodes to (created if missing)" },
                "node_setup": enum_prop(GeometryNodeSetup::ALL, None, "Type of geometry node setup"),
                "parameters": { "type": "object", "description": "Setup-specific parameters" }
            },
            "required": ["project", "object_name", "node_setup"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        let script_args = json!({
            "operation": "create_geometry_nodes",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "node_setup": args.node_setup,
            "parameters": args.parameters,
        });
        let result = ctx
            .operation("geometry_nodes.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "node_setup": args.node_setup,
            "modifier": result.get("modifier"),
            "node_group": result.get("node_group"),
            "message": format!("Geometry nodes '{}' applied to '{object_name}'", args.node_setup),
        }))
    }
}
