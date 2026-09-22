//! Scene construction, materials, environment, analysis and import/export.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};

use crate::paths;
use crate::server::{
    BlenderTool, Ctx, ToolError, ToolOutput, check_color, check_name, check_names, check_range,
    color_prop, enum_prop, project_prop, resolve_setting_asset, vec3_prop,
};
use crate::types::{
    AnalysisType, CompositorSetup, CurveType, EnvironmentType, ExportFormat, ImportFormat,
    LightingType, MaterialType, OptimizationType, PrimitiveType, ProjectionType, TextureType,
};

/// Free-form, script-specific settings.
pub type Settings = Map<String, Value>;

/// Most objects accepted by one call.
const MAX_OBJECTS: usize = 1000;

// ---------------------------------------------------------------------------
// add_primitive_objects
// ---------------------------------------------------------------------------

/// One primitive to add.
#[derive(Debug, Deserialize, Serialize)]
pub struct PrimitiveSpec {
    #[serde(rename = "type")]
    kind: PrimitiveType,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    location: Option<[f64; 3]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    rotation: Option<[f64; 3]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    scale: Option<[f64; 3]>,
}

/// `add_primitive_objects` arguments.
#[derive(Debug, Deserialize)]
pub struct AddPrimitiveObjectsArgs {
    project: String,
    objects: Vec<PrimitiveSpec>,
}

/// Add mesh primitives.
pub struct AddPrimitiveObjects;

#[async_trait]
impl BlenderTool for AddPrimitiveObjects {
    type Args = AddPrimitiveObjectsArgs;
    const NAME: &'static str = "add_primitive_objects";
    const DESCRIPTION: &'static str = "Add mesh primitives to a project.\n\nTypes: cube, sphere (uv_sphere), cylinder, \
cone, torus, plane, monkey. Rotation is Euler XYZ in radians. Returns the names Blender actually assigned \
(duplicates get suffixes such as 'Cube.001').";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "objects": {
                    "type": "array",
                    "minItems": 1,
                    "description": "Objects to add",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": enum_prop(PrimitiveType::ALL, None, "Primitive type"),
                            "name": { "type": "string", "description": "Object name (defaults to the type)" },
                            "location": vec3_prop("World location", Some([0.0, 0.0, 0.0])),
                            "rotation": vec3_prop("Euler rotation in radians", Some([0.0, 0.0, 0.0])),
                            "scale": vec3_prop("Scale", Some([1.0, 1.0, 1.0]))
                        },
                        "required": ["type"]
                    }
                }
            },
            "required": ["project", "objects"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        if args.objects.is_empty() || args.objects.len() > MAX_OBJECTS {
            return Err(ToolError::invalid(format!(
                "objects must contain 1-{MAX_OBJECTS} entries"
            )));
        }
        for obj in &args.objects {
            if let Some(name) = &obj.name {
                check_name("objects[].name", name)?;
            }
        }
        let count = args.objects.len();
        let script_args = json!({
            "operation": "add_primitives",
            "project": project.path.to_string_lossy(),
            "objects": args.objects,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "objects_added": count,
            "objects": result.get("objects"),
            "message": format!("Added {count} objects to '{}'", project.name),
        }))
    }
}

// ---------------------------------------------------------------------------
// setup_lighting
// ---------------------------------------------------------------------------

/// `setup_lighting` settings.
#[derive(Debug, Default, Deserialize, Serialize)]
pub struct LightingSettings {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    strength: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    color: Option<Vec<f64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    hdri_path: Option<String>,
}

/// `setup_lighting` arguments.
#[derive(Debug, Deserialize)]
pub struct SetupLightingArgs {
    project: String,
    #[serde(rename = "type")]
    kind: LightingType,
    #[serde(default)]
    settings: LightingSettings,
}

/// Replace the scene's lights with a preset rig.
pub struct SetupLighting;

#[async_trait]
impl BlenderTool for SetupLighting {
    type Args = SetupLightingArgs;
    const NAME: &'static str = "setup_lighting";
    const DESCRIPTION: &'static str = "Replace ALL existing lights with a lighting rig.\n\nTypes: three_point, studio \
(four soft boxes), hdri (world environment from settings.hdri_path, a file in the assets directory), sun, area. \
settings.strength scales the preset energies; settings.color tints the lights.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "type": enum_prop(LightingType::ALL, None, "Lighting rig"),
                "settings": {
                    "type": "object",
                    "properties": {
                        "strength": { "type": "number", "minimum": 0, "default": 1.0 },
                        "color": color_prop("Light color", &[1.0, 1.0, 1.0]),
                        "hdri_path": { "type": "string", "description": "HDRI file relative to the assets directory (hdri type)" }
                    }
                }
            },
            "required": ["project", "type"]
        })
    }

    async fn run(ctx: &Ctx, mut args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        if let Some(strength) = args.settings.strength {
            check_range("settings.strength", strength, 0.0, 1.0e6)?;
        }
        if let Some(color) = &args.settings.color {
            check_color("settings.color", color)?;
        }
        match (&args.settings.hdri_path, args.kind) {
            (Some(path), _) => {
                let resolved = ctx.asset("settings.hdri_path", path)?;
                args.settings.hdri_path = Some(resolved.to_string_lossy().to_string());
            },
            (None, LightingType::Hdri) => {
                return Err(ToolError::invalid(
                    "settings.hdri_path is required for hdri lighting",
                ));
            },
            (None, _) => {},
        }
        let script_args = json!({
            "operation": "setup_lighting",
            "project": project.path.to_string_lossy(),
            "lighting_type": args.kind,
            "settings": args.settings,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "lighting_type": args.kind,
            "message": format!("Lighting setup '{}' applied", args.kind),
            "result": result,
        }))
    }
}

// ---------------------------------------------------------------------------
// apply_material
// ---------------------------------------------------------------------------

/// Material description.
#[derive(Debug, Deserialize, Serialize)]
pub struct MaterialSpec {
    #[serde(rename = "type", default = "default_material")]
    kind: MaterialType,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    base_color: Option<Vec<f64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    metallic: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    roughness: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    emission_strength: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    ior: Option<f64>,
}

impl Default for MaterialSpec {
    fn default() -> Self {
        Self {
            kind: default_material(),
            name: None,
            base_color: None,
            metallic: None,
            roughness: None,
            emission_strength: None,
            ior: None,
        }
    }
}

fn default_material() -> MaterialType {
    MaterialType::Principled
}

/// `apply_material` arguments.
#[derive(Debug, Deserialize)]
pub struct ApplyMaterialArgs {
    project: String,
    object_name: String,
    #[serde(default)]
    material: MaterialSpec,
}

/// Create and assign a material.
pub struct ApplyMaterial;

#[async_trait]
impl BlenderTool for ApplyMaterial {
    type Args = ApplyMaterialArgs;
    const NAME: &'static str = "apply_material";
    const DESCRIPTION: &'static str = "Create a material and assign it to an object's first material slot.\n\n\
Types: principled (PBR), emission, glass, metal, plastic (with clear coat), wood (procedural). base_color accepts \
RGB or RGBA in 0-1. add_texture can afterwards wire textures into principled/metal/plastic/wood materials.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Object to apply the material to" },
                "material": {
                    "type": "object",
                    "properties": {
                        "type": enum_prop(MaterialType::ALL, Some("principled"), "Material preset"),
                        "name": { "type": "string", "description": "Material name (default '<object>_<type>')" },
                        "base_color": color_prop("Base color RGB(A), 0-1", &[0.8, 0.8, 0.8, 1.0]),
                        "metallic": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.0 },
                        "roughness": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5 },
                        "emission_strength": { "type": "number", "minimum": 0, "default": 0.0, "description": "Emission strength (emission type defaults to 1)" },
                        "ior": { "type": "number", "minimum": 1, "default": 1.45, "description": "Index of refraction (glass)" }
                    }
                }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        let m = &args.material;
        if let Some(name) = &m.name {
            check_name("material.name", name)?;
        }
        if let Some(color) = &m.base_color {
            check_color("material.base_color", color)?;
        }
        for (field, value) in [
            ("material.metallic", m.metallic),
            ("material.roughness", m.roughness),
        ] {
            if let Some(v) = value {
                check_range(field, v, 0.0, 1.0)?;
            }
        }
        if let Some(v) = m.emission_strength {
            check_range("material.emission_strength", v, 0.0, 1.0e6)?;
        }
        if let Some(v) = m.ior {
            check_range("material.ior", v, 1.0, 5.0)?;
        }
        let material_type = m.kind;
        let script_args = json!({
            "operation": "apply_material",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "material": args.material,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "material_type": material_type,
            "material": result.get("material"),
            "message": format!("Material applied to '{object_name}'"),
        }))
    }
}

// ---------------------------------------------------------------------------
// add_texture
// ---------------------------------------------------------------------------

/// `add_texture` arguments.
#[derive(Debug, Deserialize)]
pub struct AddTextureArgs {
    project: String,
    object_name: String,
    texture_type: TextureType,
    #[serde(default)]
    settings: Settings,
}

/// Wire a texture node into a material.
pub struct AddTexture;

#[async_trait]
impl BlenderTool for AddTexture {
    type Args = AddTextureArgs;
    const NAME: &'static str = "add_texture";
    const DESCRIPTION: &'static str = "Add a texture node to the object's first material and connect it to its \
Principled BSDF (a principled material is created if the object has none).\n\nTypes: IMAGE (settings.image_path, a \
file in the assets directory), NOISE, VORONOI, MUSGRAVE (Noise in Blender 4.1+), WAVE, MAGIC, BRICK, CHECKER, \
GRADIENT. settings: scale, detail, distortion, color1/color2 (brick), target (BSDF input, e.g. 'Base Color', \
'Roughness').";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Object name" },
                "texture_type": enum_prop(TextureType::ALL, None, "Texture type"),
                "settings": {
                    "type": "object",
                    "description": "Texture settings",
                    "properties": {
                        "image_path": { "type": "string", "description": "Image relative to the assets directory (IMAGE)" },
                        "scale": { "type": "number", "default": 5.0 },
                        "target": { "type": "string", "description": "Principled BSDF input to drive" }
                    }
                }
            },
            "required": ["project", "object_name", "texture_type"]
        })
    }

    async fn run(ctx: &Ctx, mut args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        if args.texture_type == TextureType::Image && !args.settings.contains_key("image_path") {
            return Err(ToolError::invalid(
                "settings.image_path is required for IMAGE textures",
            ));
        }
        resolve_setting_asset(ctx, &mut args.settings, "image_path")?;
        let script_args = json!({
            "operation": "add_texture",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "texture_type": args.texture_type,
            "settings": args.settings,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "texture_type": args.texture_type,
            "message": format!("Texture '{}' added to '{object_name}'", args.texture_type),
            "result": result,
        }))
    }
}

// ---------------------------------------------------------------------------
// add_uv_map
// ---------------------------------------------------------------------------

/// `add_uv_map` arguments.
#[derive(Debug, Deserialize)]
pub struct AddUvMapArgs {
    project: String,
    object_name: String,
    #[serde(default = "default_projection")]
    projection_type: ProjectionType,
}

fn default_projection() -> ProjectionType {
    ProjectionType::SmartProject
}

/// UV-unwrap a mesh.
pub struct AddUvMap;

#[async_trait]
impl BlenderTool for AddUvMap {
    type Args = AddUvMapArgs;
    const NAME: &'static str = "add_uv_map";
    const DESCRIPTION: &'static str = "UV-unwrap a mesh object.\n\nProjections: SMART_PROJECT, CUBE_PROJECT, \
CYLINDER_PROJECT, SPHERE_PROJECT, PROJECT_FROM_VIEW (headless: falls back to a cube projection).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Mesh object name" },
                "projection_type": enum_prop(ProjectionType::ALL, Some("SMART_PROJECT"), "Projection method")
            },
            "required": ["project", "object_name"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        let script_args = json!({
            "operation": "add_uv_map",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "projection_type": args.projection_type,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "projection_type": args.projection_type,
            "uv_layers": result.get("uv_layers"),
            "message": format!("UV mapping '{}' added to '{object_name}'", args.projection_type),
        }))
    }
}

// ---------------------------------------------------------------------------
// delete_objects
// ---------------------------------------------------------------------------

/// `delete_objects` arguments.
#[derive(Debug, Deserialize)]
pub struct DeleteObjectsArgs {
    project: String,
    #[serde(default)]
    names: Vec<String>,
    #[serde(default)]
    type_pattern: Option<String>,
    #[serde(default)]
    name_pattern: Option<String>,
}

/// Delete objects by name, type or name pattern.
pub struct DeleteObjects;

#[async_trait]
impl BlenderTool for DeleteObjects {
    type Args = DeleteObjectsArgs;
    const NAME: &'static str = "delete_objects";
    const DESCRIPTION: &'static str = "Delete objects by exact name, by object type (type_pattern, a glob over Blender \
types such as MESH, LIGHT, CAMERA, CURVE, EMPTY, e.g. 'LIGHT' or 'CURVE*') and/or by name glob (name_pattern, e.g. \
'Cube*'). At least one criterion is required. Returns the deleted names and names that were not found.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "names": { "type": "array", "items": { "type": "string" }, "description": "Exact object names to delete" },
                "type_pattern": { "type": "string", "description": "Glob over object types (MESH, LIGHT, CAMERA, ...)" },
                "name_pattern": { "type": "string", "description": "Glob over object names, e.g. 'Debris*'" }
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let type_pattern = args
            .type_pattern
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty());
        let name_pattern = args
            .name_pattern
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty());
        if args.names.is_empty() && type_pattern.is_none() && name_pattern.is_none() {
            return Err(ToolError::invalid(
                "Nothing to delete: supply names, type_pattern and/or name_pattern",
            ));
        }
        if !args.names.is_empty() {
            check_names("names", &args.names)?;
        }
        let script_args = json!({
            "operation": "delete_objects",
            "project": project.path.to_string_lossy(),
            "names": args.names,
            "type_pattern": type_pattern,
            "name_pattern": name_pattern,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        let deleted = result.get("deleted_objects").cloned().unwrap_or(json!([]));
        let count = deleted.as_array().map_or(0, Vec::len);
        Ok(json!({
            "success": true,
            "deleted_objects": deleted,
            "not_found": result.get("not_found"),
            "message": format!("Deleted {count} objects"),
        }))
    }
}

// ---------------------------------------------------------------------------
// create_curve
// ---------------------------------------------------------------------------

/// `create_curve` arguments.
#[derive(Debug, Deserialize)]
pub struct CreateCurveArgs {
    project: String,
    name: String,
    points: Vec<[f64; 3]>,
    #[serde(default)]
    cyclic: bool,
    #[serde(default)]
    curve_type: Option<CurveType>,
    #[serde(default)]
    bevel_depth: Option<f64>,
    #[serde(default)]
    resolution: Option<u32>,
}

/// Create a curve object from control points.
pub struct CreateCurve;

#[async_trait]
impl BlenderTool for CreateCurve {
    type Args = CreateCurveArgs;
    const NAME: &'static str = "create_curve";
    const DESCRIPTION: &'static str = "Create a 3D curve object from control points ([x, y, z] each). curve_type: \
BEZIER (default, auto handles), NURBS or POLY. bevel_depth > 0 gives the curve thickness so it renders. Useful as a \
FOLLOW_PATH constraint target.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "name": { "type": "string", "description": "Curve name" },
                "points": {
                    "type": "array",
                    "minItems": 2,
                    "description": "Control points",
                    "items": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 }
                },
                "cyclic": { "type": "boolean", "default": false, "description": "Close the curve" },
                "curve_type": enum_prop(CurveType::ALL, Some("BEZIER"), "Spline type"),
                "bevel_depth": { "type": "number", "minimum": 0, "default": 0.0 },
                "resolution": { "type": "integer", "minimum": 1, "maximum": 64, "default": 12 }
            },
            "required": ["project", "name", "points"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let name = check_name("name", &args.name)?.to_string();
        check_range("points count", args.points.len(), 2, 10_000)?;
        if let Some(depth) = args.bevel_depth {
            check_range("bevel_depth", depth, 0.0, 1000.0)?;
        }
        if let Some(res) = args.resolution {
            check_range("resolution", res, 1, 64)?;
        }
        let script_args = json!({
            "operation": "create_curve",
            "project": project.path.to_string_lossy(),
            "name": name,
            "points": args.points,
            "cyclic": args.cyclic,
            "curve_type": args.curve_type.unwrap_or(CurveType::Bezier),
            "bevel_depth": args.bevel_depth.unwrap_or(0.0),
            "resolution": args.resolution.unwrap_or(12),
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "name": result.get("curve").cloned().unwrap_or(json!(name)),
            "points": args.points.len(),
            "message": format!("Curve '{name}' created"),
        }))
    }
}

// ---------------------------------------------------------------------------
// setup_world_environment
// ---------------------------------------------------------------------------

/// `setup_world_environment` arguments.
#[derive(Debug, Deserialize)]
pub struct SetupWorldEnvironmentArgs {
    project: String,
    environment_type: EnvironmentType,
    #[serde(default)]
    settings: Settings,
}

/// Configure the world shader.
pub struct SetupWorldEnvironment;

#[async_trait]
impl BlenderTool for SetupWorldEnvironment {
    type Args = SetupWorldEnvironmentArgs;
    const NAME: &'static str = "setup_world_environment";
    const DESCRIPTION: &'static str = "Replace the world (background/ambient) shader.\n\nTypes: HDRI (settings.hdri_path \
in the assets directory, optional rotation [x,y,z]), SKY_TEXTURE (sun_direction [x,y,z], turbidity, ground_albedo), \
GRADIENT (color_top, color_bottom), COLOR (color), VOLUMETRIC (volume_density, volume_anisotropy). All accept strength.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "environment_type": enum_prop(EnvironmentType::ALL, None, "Environment type"),
                "settings": {
                    "type": "object",
                    "description": "Environment settings",
                    "properties": {
                        "strength": { "type": "number", "minimum": 0, "default": 1.0 },
                        "hdri_path": { "type": "string", "description": "HDRI relative to the assets directory (HDRI)" }
                    }
                }
            },
            "required": ["project", "environment_type"]
        })
    }

    async fn run(ctx: &Ctx, mut args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        if args.environment_type == EnvironmentType::Hdri
            && !args.settings.contains_key("hdri_path")
        {
            return Err(ToolError::invalid(
                "settings.hdri_path is required for HDRI environments",
            ));
        }
        resolve_setting_asset(ctx, &mut args.settings, "hdri_path")?;
        let script_args = json!({
            "operation": "setup_world_environment",
            "project": project.path.to_string_lossy(),
            "environment_type": args.environment_type,
            "settings": args.settings,
        });
        ctx.operation("environment.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "environment_type": args.environment_type,
            "message": format!("Environment '{}' configured", args.environment_type),
        }))
    }
}

// ---------------------------------------------------------------------------
// setup_compositor
// ---------------------------------------------------------------------------

/// `setup_compositor` arguments.
#[derive(Debug, Deserialize)]
pub struct SetupCompositorArgs {
    project: String,
    setup: CompositorSetup,
    #[serde(default)]
    settings: Settings,
}

/// Configure post-processing nodes.
pub struct SetupCompositor;

#[async_trait]
impl BlenderTool for SetupCompositor {
    type Args = SetupCompositorArgs;
    const NAME: &'static str = "setup_compositor";
    const DESCRIPTION: &'static str = "Replace the compositor node tree with a post-processing preset.\n\nSetups: BASIC, \
DENOISING, COLOR_GRADING, GLARE (settings.threshold, strength, glare_type), FOG_GLOW, LENS_DISTORTION (distort, \
dispersion), VIGNETTE (size, softness).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "setup": enum_prop(CompositorSetup::ALL, None, "Compositor preset"),
                "settings": { "type": "object", "description": "Preset settings" }
            },
            "required": ["project", "setup"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let script_args = json!({
            "operation": "setup_compositor",
            "project": project.path.to_string_lossy(),
            "setup": args.setup,
            "settings": args.settings,
        });
        ctx.operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "setup": args.setup,
            "message": format!("Compositor '{}' setup applied", args.setup),
        }))
    }
}

// ---------------------------------------------------------------------------
// analyze_scene
// ---------------------------------------------------------------------------

/// `analyze_scene` arguments.
#[derive(Debug, Deserialize)]
pub struct AnalyzeSceneArgs {
    project: String,
    #[serde(default = "default_analysis")]
    analysis_type: AnalysisType,
}

fn default_analysis() -> AnalysisType {
    AnalysisType::Basic
}

/// Report scene statistics.
pub struct AnalyzeScene;

#[async_trait]
impl BlenderTool for AnalyzeScene {
    type Args = AnalyzeSceneArgs;
    const NAME: &'static str = "analyze_scene";
    const DESCRIPTION: &'static str = "Analyze a project: object list (name, type, location), counts per type, \
vertex/face/triangle totals, materials, render engine, resolution, frame range and active camera. DETAILED adds \
datablock counts, PERFORMANCE adds warnings, MEMORY adds a mesh memory estimate. Read-only.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "analysis_type": enum_prop(AnalysisType::ALL, Some("BASIC"), "Level of detail")
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let script_args = json!({
            "operation": "analyze_scene",
            "project": project.path.to_string_lossy(),
            "analysis_type": args.analysis_type,
        });
        // Read-only: no project lock needed.
        let result = ctx.operation("scene_builder.py", script_args, None).await?;
        Ok(json!({ "success": true, "analysis_type": args.analysis_type, "result": result }))
    }
}

// ---------------------------------------------------------------------------
// optimize_scene
// ---------------------------------------------------------------------------

/// `optimize_scene` arguments.
#[derive(Debug, Deserialize)]
pub struct OptimizeSceneArgs {
    project: String,
    optimization_type: OptimizationType,
    #[serde(default)]
    settings: Settings,
}

/// Run an optimization pass.
pub struct OptimizeScene;

#[async_trait]
impl BlenderTool for OptimizeScene {
    type Args = OptimizeSceneArgs;
    const NAME: &'static str = "optimize_scene";
    const DESCRIPTION: &'static str = "Run one optimization pass and report what changed.\n\nMESH_CLEANUP (merge \
vertices closer than settings.merge_threshold, drop loose vertices), TEXTURE_OPTIMIZATION (downscale images above \
settings.max_size, default 2048), MODIFIER_APPLY (apply all mesh modifiers - destructive), INSTANCE_OPTIMIZATION \
(identical unmodified meshes share one mesh datablock), MATERIAL_CLEANUP (remove unused materials and images).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "optimization_type": enum_prop(OptimizationType::ALL, None, "Optimization pass"),
                "settings": {
                    "type": "object",
                    "properties": {
                        "merge_threshold": { "type": "number", "minimum": 0, "default": 0.0001 },
                        "max_size": { "type": "integer", "minimum": 1, "default": 2048 }
                    }
                }
            },
            "required": ["project", "optimization_type"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let script_args = json!({
            "operation": "optimize_scene",
            "project": project.path.to_string_lossy(),
            "optimization_type": args.optimization_type,
            "settings": args.settings,
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "optimization_type": args.optimization_type,
            "message": format!("Optimization '{}' applied", args.optimization_type),
            "result": result,
        }))
    }
}

// ---------------------------------------------------------------------------
// import_model / export_scene
// ---------------------------------------------------------------------------

/// `import_model` arguments.
#[derive(Debug, Deserialize)]
pub struct ImportModelArgs {
    project: String,
    model_path: String,
    #[serde(default)]
    format: Option<ImportFormat>,
    #[serde(default)]
    location: Option<[f64; 3]>,
}

/// Import a model file from the assets directory.
pub struct ImportModel;

#[async_trait]
impl BlenderTool for ImportModel {
    type Args = ImportModelArgs;
    const NAME: &'static str = "import_model";
    const DESCRIPTION: &'static str = "Import a 3D model into a project. model_path is relative to the assets \
directory. Formats: FBX, OBJ, GLTF, GLB, STL, PLY, USD (auto-detected from the extension when omitted). Top-level \
imported objects are moved to location. Returns the imported object names.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "model_path": { "type": "string", "description": "Model file relative to the assets directory" },
                "format": enum_prop(ImportFormat::ALL, None, "Model format (auto-detected if not specified)"),
                "location": vec3_prop("Where to place the imported objects", Some([0.0, 0.0, 0.0]))
            },
            "required": ["project", "model_path"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let model = ctx.asset("model_path", &args.model_path)?;
        let format = match args.format {
            Some(f) => f,
            None => model
                .extension()
                .and_then(|e| e.to_str())
                .and_then(ImportFormat::from_extension)
                .ok_or_else(|| {
                    ToolError::invalid(format!(
                        "Cannot detect the format of '{}'; pass format (one of {})",
                        args.model_path,
                        ImportFormat::ALL.join(", ")
                    ))
                })?,
        };
        let script_args = json!({
            "operation": "import_model",
            "project": project.path.to_string_lossy(),
            "model_path": model.to_string_lossy(),
            "format": format,
            "location": args.location.unwrap_or([0.0, 0.0, 0.0]),
        });
        let result = ctx
            .operation("scene_builder.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "model_path": args.model_path,
            "format": format,
            "imported_objects": result.get("imported_objects"),
            "message": format!("Model imported from '{}'", args.model_path),
        }))
    }
}

/// `export_scene` arguments.
#[derive(Debug, Deserialize)]
pub struct ExportSceneArgs {
    project: String,
    format: ExportFormat,
    #[serde(default)]
    selected_only: bool,
    #[serde(default)]
    filename: Option<String>,
}

/// Export the scene to a model file.
pub struct ExportScene;

#[async_trait]
impl BlenderTool for ExportScene {
    type Args = ExportSceneArgs;
    const NAME: &'static str = "export_scene";
    const DESCRIPTION: &'static str = "Export a project to FBX, OBJ, GLTF (separate .gltf + .bin), GLB, STL, PLY or USD. \
The file is written to <output_dir>/exports/<filename or project name>.<ext>, overwriting an existing export of the \
same name.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "format": enum_prop(ExportFormat::ALL, None, "Export format"),
                "selected_only": { "type": "boolean", "default": false, "description": "Export only the objects selected in the saved file" },
                "filename": { "type": "string", "description": "Output file name without extension (default: project name)" }
            },
            "required": ["project", "format"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let stem = match &args.filename {
            Some(name) => paths::validate_file_name(name)?.to_string(),
            None => project
                .path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("export")
                .to_string(),
        };
        let exports = ctx.config.output_dir.join("exports");
        let output_path =
            paths::resolve_under(&exports, &format!("{stem}.{}", args.format.extension()))?;
        let script_args = json!({
            "operation": "export_scene",
            "project": project.path.to_string_lossy(),
            "format": args.format,
            "output_path": output_path.to_string_lossy(),
            "selected_only": args.selected_only,
        });
        // Export only reads the project.
        let result = ctx.operation("scene_builder.py", script_args, None).await?;
        Ok(json!({
            "success": true,
            "output_path": output_path.to_string_lossy(),
            "format": args.format,
            "bytes": result.get("bytes"),
            "message": format!("Scene exported to '{}'", output_path.display()),
        }))
    }
}
