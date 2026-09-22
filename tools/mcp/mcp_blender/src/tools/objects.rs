//! Constraints, rigging, text, advanced primitives and object relations.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};
use std::collections::HashSet;

use crate::server::{
    BlenderTool, Ctx, ToolError, ToolOutput, check_name, check_names, check_range, enum_prop,
    names_prop, project_prop, vec3_prop,
};
use crate::types::{AdvancedPrimitiveType, AlignX, AlignY, ConstraintType, ParentType};

// ---------------------------------------------------------------------------
// add_constraint
// ---------------------------------------------------------------------------

/// `add_constraint` arguments.
#[derive(Debug, Deserialize)]
pub struct AddConstraintArgs {
    project: String,
    object_name: String,
    constraint_type: ConstraintType,
    #[serde(default)]
    target_object: Option<String>,
    #[serde(default)]
    settings: Map<String, Value>,
}

/// Add an object constraint.
pub struct AddConstraint;

#[async_trait]
impl BlenderTool for AddConstraint {
    type Args = AddConstraintArgs;
    const NAME: &'static str = "add_constraint";
    const DESCRIPTION: &'static str = "Add a constraint to an object.\n\nTypes: TRACK_TO, COPY_LOCATION, COPY_ROTATION, \
COPY_SCALE, LIMIT_LOCATION, LIMIT_ROTATION, LIMIT_SCALE, FOLLOW_PATH (target must be a curve), DAMPED_TRACK, FLOOR, \
CHILD_OF. Most types need target_object. settings: name, influence, track_axis, up_axis, use_x/use_y/use_z, \
min_x/max_x/use_min_x... (limits), use_curve_follow, forward_axis, offset.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_name": { "type": "string", "description": "Object to add the constraint to" },
                "constraint_type": enum_prop(ConstraintType::ALL, None, "Constraint type"),
                "target_object": { "type": "string", "description": "Target object for the constraint" },
                "settings": { "type": "object", "description": "Constraint-specific settings" }
            },
            "required": ["project", "object_name", "constraint_type"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let object_name = check_name("object_name", &args.object_name)?.to_string();
        if let Some(target) = &args.target_object {
            check_name("target_object", target)?;
        }
        let needs_target = !matches!(
            args.constraint_type,
            ConstraintType::LimitLocation
                | ConstraintType::LimitRotation
                | ConstraintType::LimitScale
        );
        if needs_target && args.target_object.is_none() {
            return Err(ToolError::invalid(format!(
                "constraint_type {} requires target_object",
                args.constraint_type
            )));
        }
        let script_args = json!({
            "operation": "add_constraint",
            "project": project.path.to_string_lossy(),
            "object_name": object_name,
            "constraint_type": args.constraint_type,
            "target_object": args.target_object,
            "settings": args.settings,
        });
        let result = ctx
            .operation("advanced_objects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "object": object_name,
            "constraint_type": args.constraint_type,
            "message": format!("Constraint '{}' added to '{object_name}'", args.constraint_type),
            "result": result,
        }))
    }
}

// ---------------------------------------------------------------------------
// create_armature
// ---------------------------------------------------------------------------

/// One bone of an armature.
#[derive(Debug, Deserialize, Serialize)]
pub struct Bone {
    name: String,
    head: [f64; 3],
    tail: [f64; 3],
    #[serde(default, skip_serializing_if = "Option::is_none")]
    parent: Option<String>,
    #[serde(default)]
    connected: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    roll: Option<f64>,
}

/// `create_armature` arguments.
#[derive(Debug, Deserialize)]
pub struct CreateArmatureArgs {
    project: String,
    #[serde(default = "default_armature")]
    name: String,
    #[serde(default)]
    location: Option<[f64; 3]>,
    bones: Vec<Bone>,
}

fn default_armature() -> String {
    "Armature".to_string()
}

/// Check bone names are unique, parents exist and precede their children,
/// and no bone has zero length.
pub fn validate_bones(bones: &[Bone]) -> Result<(), ToolError> {
    check_range("bones count", bones.len(), 1, 1000)?;
    let mut seen = HashSet::new();
    for bone in bones {
        check_name("bones[].name", &bone.name)?;
        if bone.head == bone.tail {
            return Err(ToolError::invalid(format!(
                "bone '{}' has zero length (head == tail)",
                bone.name
            )));
        }
        if let Some(parent) = &bone.parent
            && !seen.contains(parent.as_str())
        {
            return Err(ToolError::invalid(format!(
                "bone '{}' has parent '{}', which must be defined earlier in the list",
                bone.name, parent
            )));
        }
        if !seen.insert(bone.name.as_str()) {
            return Err(ToolError::invalid(format!(
                "duplicate bone name '{}'",
                bone.name
            )));
        }
    }
    Ok(())
}

/// Create an armature with bones.
pub struct CreateArmature;

#[async_trait]
impl BlenderTool for CreateArmature {
    type Args = CreateArmatureArgs;
    const NAME: &'static str = "create_armature";
    const DESCRIPTION: &'static str = "Create an armature (skeleton) for rigging. Bones have head/tail positions \
(armature space), optional parent (defined earlier in the list) and connected flag. Use parent_objects with \
parent_type ARMATURE or BONE to attach meshes.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "name": { "type": "string", "default": "Armature" },
                "location": vec3_prop("Armature location", Some([0.0, 0.0, 0.0])),
                "bones": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": { "type": "string" },
                            "head": vec3_prop("Bone head", None),
                            "tail": vec3_prop("Bone tail", None),
                            "parent": { "type": "string", "description": "Parent bone (must appear earlier)" },
                            "connected": { "type": "boolean", "default": false },
                            "roll": { "type": "number", "default": 0.0 }
                        },
                        "required": ["name", "head", "tail"]
                    }
                }
            },
            "required": ["project", "bones"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let name = check_name("name", &args.name)?.to_string();
        validate_bones(&args.bones)?;
        let script_args = json!({
            "operation": "create_armature",
            "project": project.path.to_string_lossy(),
            "name": name,
            "location": args.location.unwrap_or([0.0, 0.0, 0.0]),
            "bones": args.bones,
        });
        let result = ctx
            .operation("advanced_objects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "armature": result.get("armature").cloned().unwrap_or(json!(name)),
            "message": format!("Armature '{name}' created"),
            "result": result,
        }))
    }
}

// ---------------------------------------------------------------------------
// create_text_object
// ---------------------------------------------------------------------------

/// `create_text_object` arguments.
#[derive(Debug, Deserialize)]
pub struct CreateTextObjectArgs {
    project: String,
    text: String,
    #[serde(default = "default_text_name")]
    name: String,
    #[serde(default)]
    location: Option<[f64; 3]>,
    #[serde(default)]
    rotation: Option<[f64; 3]>,
    #[serde(default = "default_size")]
    size: f64,
    #[serde(default)]
    extrude: f64,
    #[serde(default)]
    bevel_depth: f64,
    #[serde(default = "default_align_x")]
    align_x: AlignX,
    #[serde(default = "default_align_y")]
    align_y: AlignY,
    #[serde(default)]
    font_path: Option<String>,
}

fn default_text_name() -> String {
    "Text".to_string()
}
fn default_size() -> f64 {
    1.0
}
fn default_align_x() -> AlignX {
    AlignX::Left
}
fn default_align_y() -> AlignY {
    AlignY::Top
}

/// Create 3D text.
pub struct CreateTextObject;

#[async_trait]
impl BlenderTool for CreateTextObject {
    type Args = CreateTextObjectArgs;
    const NAME: &'static str = "create_text_object";
    const DESCRIPTION: &'static str = "Create a 3D text object with optional extrusion and bevel. font_path is a \
.ttf/.otf file in the assets directory (Blender's built-in font otherwise).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "text": { "type": "string", "description": "Text content" },
                "name": { "type": "string", "default": "Text" },
                "location": vec3_prop("Location", Some([0.0, 0.0, 0.0])),
                "rotation": vec3_prop("Euler rotation in radians", Some([0.0, 0.0, 0.0])),
                "size": { "type": "number", "exclusiveMinimum": 0, "default": 1.0 },
                "extrude": { "type": "number", "minimum": 0, "default": 0.0 },
                "bevel_depth": { "type": "number", "minimum": 0, "default": 0.0 },
                "align_x": enum_prop(AlignX::ALL, Some("LEFT"), "Horizontal alignment"),
                "align_y": enum_prop(AlignY::ALL, Some("TOP"), "Vertical alignment"),
                "font_path": { "type": "string", "description": "Font file relative to the assets directory" }
            },
            "required": ["project", "text"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let name = check_name("name", &args.name)?.to_string();
        if args.text.is_empty() || args.text.len() > 10_000 {
            return Err(ToolError::invalid("text must be 1-10000 bytes"));
        }
        check_range("size", args.size, 1.0e-6, 1.0e6)?;
        check_range("extrude", args.extrude, 0.0, 1.0e4)?;
        check_range("bevel_depth", args.bevel_depth, 0.0, 1.0e4)?;
        let font = match &args.font_path {
            Some(path) => Some(ctx.asset("font_path", path)?.to_string_lossy().to_string()),
            None => None,
        };
        let script_args = json!({
            "operation": "create_text_object",
            "project": project.path.to_string_lossy(),
            "text": args.text,
            "name": name,
            "location": args.location.unwrap_or([0.0, 0.0, 0.0]),
            "rotation": args.rotation.unwrap_or([0.0, 0.0, 0.0]),
            "size": args.size,
            "extrude": args.extrude,
            "bevel_depth": args.bevel_depth,
            "align_x": args.align_x,
            "align_y": args.align_y,
            "font_path": font,
        });
        let result = ctx
            .operation("advanced_objects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "text": args.text,
            "object": result.get("object"),
            "message": "Text object created",
        }))
    }
}

// ---------------------------------------------------------------------------
// add_advanced_primitives
// ---------------------------------------------------------------------------

/// One advanced primitive; extra keys (size, radius, subdivisions,
/// empty_type, metaball_type, ...) are passed through to the script.
#[derive(Debug, Deserialize, Serialize)]
pub struct AdvancedPrimitive {
    #[serde(rename = "type")]
    kind: AdvancedPrimitiveType,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    location: Option<[f64; 3]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    rotation: Option<[f64; 3]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    scale: Option<[f64; 3]>,
    #[serde(flatten)]
    extra: Map<String, Value>,
}

/// `add_advanced_primitives` arguments.
#[derive(Debug, Deserialize)]
pub struct AddAdvancedPrimitivesArgs {
    project: String,
    objects: Vec<AdvancedPrimitive>,
}

/// Add grids, circles, empties, curves and metaballs.
pub struct AddAdvancedPrimitives;

#[async_trait]
impl BlenderTool for AddAdvancedPrimitives {
    type Args = AddAdvancedPrimitivesArgs;
    const NAME: &'static str = "add_advanced_primitives";
    const DESCRIPTION: &'static str = "Add non-basic primitives.\n\nTypes: grid (x_subdivisions, y_subdivisions, size), \
circle (vertices, radius, fill_type), ico_sphere (subdivisions, radius), empty (empty_type, display_size), \
bezier_curve, nurbs_curve, nurbs_circle, metaball (metaball_type BALL/CAPSULE/PLANE/ELLIPSOID/CUBE).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "objects": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": enum_prop(AdvancedPrimitiveType::ALL, None, "Primitive type"),
                            "name": { "type": "string" },
                            "location": vec3_prop("Location", None),
                            "rotation": vec3_prop("Euler rotation in radians", None),
                            "scale": vec3_prop("Scale", None)
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
        check_range("objects count", args.objects.len(), 1, 1000)?;
        for obj in &args.objects {
            if let Some(name) = &obj.name {
                check_name("objects[].name", name)?;
            }
        }
        let count = args.objects.len();
        let script_args = json!({
            "operation": "add_advanced_primitives",
            "project": project.path.to_string_lossy(),
            "objects": args.objects,
        });
        let result = ctx
            .operation("advanced_objects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "objects_added": count,
            "objects": result.get("objects_created"),
            "message": format!("Added {count} advanced primitives"),
        }))
    }
}

// ---------------------------------------------------------------------------
// parent_objects / join_objects
// ---------------------------------------------------------------------------

/// `parent_objects` arguments.
#[derive(Debug, Deserialize)]
pub struct ParentObjectsArgs {
    project: String,
    parent_name: String,
    children: Vec<String>,
    #[serde(default = "yes")]
    keep_transform: bool,
    #[serde(default = "default_parent_type")]
    parent_type: ParentType,
    #[serde(default)]
    bone_name: Option<String>,
}

fn yes() -> bool {
    true
}
fn default_parent_type() -> ParentType {
    ParentType::Object
}

/// Parent objects to another object (or armature bone).
pub struct ParentObjects;

#[async_trait]
impl BlenderTool for ParentObjects {
    type Args = ParentObjectsArgs;
    const NAME: &'static str = "parent_objects";
    const DESCRIPTION: &'static str = "Parent objects to a parent object. parent_type OBJECT (default), ARMATURE, or BONE \
(requires bone_name on an armature parent). keep_transform keeps children where they are. Missing children are \
reported in not_found.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "parent_name": { "type": "string", "description": "Name of parent object" },
                "children": names_prop("Names of child objects"),
                "keep_transform": { "type": "boolean", "default": true },
                "parent_type": enum_prop(ParentType::ALL, Some("OBJECT"), "Parenting mode"),
                "bone_name": { "type": "string", "description": "Bone name if parent_type is BONE" }
            },
            "required": ["project", "parent_name", "children"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        let parent = check_name("parent_name", &args.parent_name)?.to_string();
        check_names("children", &args.children)?;
        if args.children.iter().any(|c| c.trim() == parent) {
            return Err(ToolError::invalid("an object cannot be its own parent"));
        }
        if args.parent_type == ParentType::Bone && args.bone_name.is_none() {
            return Err(ToolError::invalid(
                "bone_name is required when parent_type is BONE",
            ));
        }
        if let Some(bone) = &args.bone_name {
            check_name("bone_name", bone)?;
        }
        let script_args = json!({
            "operation": "parent_objects",
            "project": project.path.to_string_lossy(),
            "parent_name": parent,
            "children": args.children,
            "keep_transform": args.keep_transform,
            "parent_type": args.parent_type,
            "bone_name": args.bone_name,
        });
        let result = ctx
            .operation("advanced_objects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "parent": parent,
            "children_parented": result.get("children_parented"),
            "not_found": result.get("not_found"),
            "message": format!("Objects parented to '{parent}'"),
        }))
    }
}

/// `join_objects` arguments.
#[derive(Debug, Deserialize)]
pub struct JoinObjectsArgs {
    project: String,
    object_names: Vec<String>,
    target_name: String,
}

/// Join meshes into one.
pub struct JoinObjects;

#[async_trait]
impl BlenderTool for JoinObjects {
    type Args = JoinObjectsArgs;
    const NAME: &'static str = "join_objects";
    const DESCRIPTION: &'static str = "Join mesh objects into one. target_name is the mesh that receives the geometry \
(it is included automatically); the other objects are removed.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "object_names": names_prop("Names of mesh objects to join"),
                "target_name": { "type": "string", "description": "Mesh that receives the joined geometry" }
            },
            "required": ["project", "object_names", "target_name"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        check_names("object_names", &args.object_names)?;
        let target = check_name("target_name", &args.target_name)?.to_string();
        let mut names = args.object_names.clone();
        if !names.iter().any(|n| n.trim() == target) {
            names.push(target.clone());
        }
        if names.len() < 2 {
            return Err(ToolError::invalid(
                "join_objects needs at least two distinct objects",
            ));
        }
        let script_args = json!({
            "operation": "join_objects",
            "project": project.path.to_string_lossy(),
            "object_names": names,
            "target_name": target,
        });
        let result = ctx
            .operation("advanced_objects.py", script_args, Some(&project.path))
            .await?;
        Ok(json!({
            "success": true,
            "result_object": target,
            "message": format!("Objects joined into '{target}'"),
            "result": result,
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bone(name: &str, parent: Option<&str>) -> Bone {
        Bone {
            name: name.into(),
            head: [0.0, 0.0, 0.0],
            tail: [0.0, 0.0, 1.0],
            parent: parent.map(Into::into),
            connected: false,
            roll: None,
        }
    }

    #[test]
    fn bones_valid_chain() {
        assert!(validate_bones(&[bone("root", None), bone("spine", Some("root"))]).is_ok());
    }

    #[test]
    fn bones_reject_forward_parent_duplicates_and_zero_length() {
        assert!(validate_bones(&[bone("spine", Some("root")), bone("root", None)]).is_err());
        assert!(validate_bones(&[bone("a", None), bone("a", None)]).is_err());
        let mut flat = bone("flat", None);
        flat.tail = flat.head;
        assert!(validate_bones(&[flat]).is_err());
        assert!(validate_bones(&[]).is_err());
    }
}
