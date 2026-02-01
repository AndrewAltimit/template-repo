//! MCP server implementation for Blender operations.
//!
//! Provides comprehensive 3D content creation tools through headless Blender automation.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::warn;
use uuid::Uuid;

use crate::blender::BlenderExecutor;
use crate::jobs::JobManager;
use crate::types::JobStatus;

/// Blender MCP server
pub struct BlenderServer {
    executor: Arc<RwLock<BlenderExecutor>>,
    jobs: Arc<RwLock<JobManager>>,
}

impl BlenderServer {
    /// Create a new Blender server
    pub fn new() -> Self {
        Self {
            executor: Arc::new(RwLock::new(BlenderExecutor::new())),
            jobs: Arc::new(RwLock::new(JobManager::new())),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            // Project Management
            Arc::new(CreateProjectTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListProjectsTool {
                server: self.clone_refs(),
            }),
            // Scene Building
            Arc::new(AddPrimitiveObjectsTool {
                server: self.clone_refs(),
            }),
            Arc::new(SetupLightingTool {
                server: self.clone_refs(),
            }),
            // Materials
            Arc::new(ApplyMaterialTool {
                server: self.clone_refs(),
            }),
            // Rendering
            Arc::new(RenderImageTool {
                server: self.clone_refs(),
            }),
            Arc::new(RenderAnimationTool {
                server: self.clone_refs(),
            }),
            // Physics
            Arc::new(SetupPhysicsTool {
                server: self.clone_refs(),
            }),
            Arc::new(BakeSimulationTool {
                server: self.clone_refs(),
            }),
            // Animation
            Arc::new(CreateAnimationTool {
                server: self.clone_refs(),
            }),
            // Geometry Nodes
            Arc::new(CreateGeometryNodesTool {
                server: self.clone_refs(),
            }),
            // Job Management
            Arc::new(GetJobStatusTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetJobResultTool {
                server: self.clone_refs(),
            }),
            Arc::new(CancelJobTool {
                server: self.clone_refs(),
            }),
            // Asset Management
            Arc::new(ImportModelTool {
                server: self.clone_refs(),
            }),
            Arc::new(ExportSceneTool {
                server: self.clone_refs(),
            }),
            // Camera Tools
            Arc::new(SetupCameraTool {
                server: self.clone_refs(),
            }),
            Arc::new(AddCameraTrackTool {
                server: self.clone_refs(),
            }),
            // Modifier Tools
            Arc::new(AddModifierTool {
                server: self.clone_refs(),
            }),
            // Particle Tools
            Arc::new(AddParticleSystemTool {
                server: self.clone_refs(),
            }),
            Arc::new(AddSmokeSimulationTool {
                server: self.clone_refs(),
            }),
            // Texture Tools
            Arc::new(AddTextureTool {
                server: self.clone_refs(),
            }),
            Arc::new(AddUvMapTool {
                server: self.clone_refs(),
            }),
            // Compositing Tools
            Arc::new(SetupCompositorTool {
                server: self.clone_refs(),
            }),
            Arc::new(BatchRenderTool {
                server: self.clone_refs(),
            }),
            // Scene Tools
            Arc::new(DeleteObjectsTool {
                server: self.clone_refs(),
            }),
            Arc::new(AnalyzeSceneTool {
                server: self.clone_refs(),
            }),
            Arc::new(OptimizeSceneTool {
                server: self.clone_refs(),
            }),
            Arc::new(CreateCurveTool {
                server: self.clone_refs(),
            }),
            // Environment Tools
            Arc::new(SetupWorldEnvironmentTool {
                server: self.clone_refs(),
            }),
            // Status
            Arc::new(BlenderStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            executor: self.executor.clone(),
            jobs: self.jobs.clone(),
        }
    }
}

impl Default for BlenderServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    executor: Arc<RwLock<BlenderExecutor>>,
    jobs: Arc<RwLock<JobManager>>,
}

impl ServerRefs {
    /// Execute a Blender script synchronously
    async fn execute_script(&self, script: &str, args: Value) -> Result<Value> {
        let job_id = Uuid::new_v4();
        let executor = self.executor.read().await;
        executor.execute_script(script, args, job_id).await
    }

    /// Execute a Blender script asynchronously (for long operations)
    async fn execute_script_async(&self, script: &str, args: Value, job_id: Uuid) -> Result<()> {
        let executor = self.executor.read().await;
        let jobs = self.jobs.read().await;

        // Mark job as running
        jobs.update_status(job_id, JobStatus::Running, Some("Started"))
            .await;

        // Clone for the spawn
        let executor_clone = executor.clone();
        let jobs_clone = jobs.clone();
        let script = script.to_string();

        tokio::spawn(async move {
            match executor_clone.execute_script(&script, args, job_id).await {
                Ok(result) => {
                    jobs_clone
                        .complete_job(job_id, result, None)
                        .await;
                }
                Err(e) => {
                    jobs_clone.fail_job(job_id, &e.to_string()).await;
                }
            }
        });

        Ok(())
    }

    /// Validate project path
    async fn validate_project_path(&self, project: &str) -> Result<String> {
        let executor = self.executor.read().await;
        let path = executor.validate_project_path(project)?;
        Ok(path.to_string_lossy().to_string())
    }

    /// Validate asset path
    async fn validate_asset_path(&self, asset_path: &str) -> Result<String> {
        let executor = self.executor.read().await;
        let path = executor.validate_path(asset_path, &executor.assets_dir())?;
        Ok(path.to_string_lossy().to_string())
    }
}

// ============================================================================
// Tool: create_blender_project
// ============================================================================

struct CreateProjectTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateProjectTool {
    fn name(&self) -> &str {
        "create_blender_project"
    }

    fn description(&self) -> &str {
        r#"Create a new Blender project from template.

Available templates: empty, basic_scene, studio_lighting, lit_empty, procedural,
animation, physics, architectural, product, vfx, game_asset, sculpting"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Project name"
                },
                "template": {
                    "type": "string",
                    "enum": ["empty", "basic_scene", "studio_lighting", "lit_empty",
                             "procedural", "animation", "physics", "architectural",
                             "product", "vfx", "game_asset", "sculpting"],
                    "default": "basic_scene",
                    "description": "Template to use"
                },
                "settings": {
                    "type": "object",
                    "description": "Project settings",
                    "properties": {
                        "resolution": {
                            "type": "array",
                            "items": { "type": "integer" },
                            "default": [1920, 1080]
                        },
                        "fps": { "type": "integer", "default": 24 },
                        "engine": {
                            "type": "string",
                            "enum": ["CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"],
                            "default": "CYCLES"
                        }
                    }
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;

        let template = args
            .get("template")
            .and_then(|v| v.as_str())
            .unwrap_or("basic_scene");
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let executor = self.server.executor.read().await;
        let project_path = executor.projects_dir().join(format!("{}.blend", name));

        let script_args = json!({
            "operation": "create_project",
            "project_path": project_path.to_string_lossy(),
            "template": template,
            "settings": settings
        });

        let result = self
            .server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "project_path": format!("{}.blend", name),
            "full_path": project_path.to_string_lossy(),
            "template": template,
            "message": format!("Project '{}' created successfully", name),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: list_projects
// ============================================================================

struct ListProjectsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListProjectsTool {
    fn name(&self) -> &str {
        "list_projects"
    }

    fn description(&self) -> &str {
        "List available Blender projects."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let executor = self.server.executor.read().await;
        let projects = executor.list_projects().await?;

        let response = json!({
            "success": true,
            "projects": projects,
            "count": projects.len()
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_primitive_objects
// ============================================================================

struct AddPrimitiveObjectsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddPrimitiveObjectsTool {
    fn name(&self) -> &str {
        "add_primitive_objects"
    }

    fn description(&self) -> &str {
        r#"Add primitive objects to the scene.

Object types: cube, sphere, cylinder, cone, torus, plane, monkey"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "objects": {
                    "type": "array",
                    "description": "List of objects to add",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["cube", "sphere", "cylinder", "cone", "torus", "plane", "monkey"]
                            },
                            "name": { "type": "string" },
                            "location": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] },
                            "rotation": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] },
                            "scale": { "type": "array", "items": { "type": "number" }, "default": [1, 1, 1] }
                        },
                        "required": ["type"]
                    }
                }
            },
            "required": ["project", "objects"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let objects = args.get("objects").cloned().unwrap_or(json!([]));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_primitives",
            "project": project_path,
            "objects": objects
        });

        let result = self
            .server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let count = objects.as_array().map(|a| a.len()).unwrap_or(0);
        let response = json!({
            "success": true,
            "objects_added": count,
            "message": format!("Added {} objects to scene", count),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: setup_lighting
// ============================================================================

struct SetupLightingTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SetupLightingTool {
    fn name(&self) -> &str {
        "setup_lighting"
    }

    fn description(&self) -> &str {
        r#"Configure scene lighting.

Lighting types: three_point, studio, hdri, sun, area"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "type": {
                    "type": "string",
                    "enum": ["three_point", "studio", "hdri", "sun", "area"],
                    "description": "Lighting setup type"
                },
                "settings": {
                    "type": "object",
                    "properties": {
                        "strength": { "type": "number", "default": 1.0 },
                        "color": { "type": "array", "items": { "type": "number" }, "default": [1, 1, 1] },
                        "hdri_path": { "type": "string", "description": "Path to HDRI file (for hdri type)" }
                    }
                }
            },
            "required": ["project", "type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let lighting_type = args
            .get("type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'type' parameter".to_string()))?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "setup_lighting",
            "project": project_path,
            "lighting_type": lighting_type,
            "settings": settings
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "lighting_type": lighting_type,
            "message": format!("Lighting setup '{}' applied", lighting_type)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: apply_material
// ============================================================================

struct ApplyMaterialTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ApplyMaterialTool {
    fn name(&self) -> &str {
        "apply_material"
    }

    fn description(&self) -> &str {
        r#"Apply materials to objects.

Material types: principled, emission, glass, metal, plastic, wood"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object to apply material to" },
                "material": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["principled", "emission", "glass", "metal", "plastic", "wood"],
                            "default": "principled"
                        },
                        "base_color": { "type": "array", "items": { "type": "number" }, "default": [0.8, 0.8, 0.8, 1.0] },
                        "metallic": { "type": "number", "default": 0.0 },
                        "roughness": { "type": "number", "default": 0.5 },
                        "emission_strength": { "type": "number", "default": 0.0 }
                    }
                }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let material = args.get("material").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;
        let material_type = material
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or("principled");

        let script_args = json!({
            "operation": "apply_material",
            "project": project_path,
            "object_name": object_name,
            "material": material
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "material_type": material_type,
            "message": format!("Material applied to '{}'", object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: render_image
// ============================================================================

struct RenderImageTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RenderImageTool {
    fn name(&self) -> &str {
        "render_image"
    }

    fn description(&self) -> &str {
        r#"Render a single frame.

This is an async operation. Use get_job_status to check progress."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "frame": { "type": "integer", "default": 1 },
                "settings": {
                    "type": "object",
                    "properties": {
                        "resolution": { "type": "array", "items": { "type": "integer" }, "default": [1920, 1080] },
                        "samples": { "type": "integer", "default": 128 },
                        "engine": { "type": "string", "enum": ["CYCLES", "BLENDER_EEVEE"], "default": "CYCLES" },
                        "format": { "type": "string", "enum": ["PNG", "JPEG", "EXR", "TIFF"], "default": "PNG" }
                    }
                }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let frame = args.get("frame").and_then(|v| v.as_i64()).unwrap_or(1);
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Create job
        let jobs = self.server.jobs.read().await;
        let job_id = jobs.create_job("render_image").await;

        // Get output path
        let executor = self.server.executor.read().await;
        let output_path = executor
            .output_dir()
            .join("renders")
            .join(format!("{}.png", job_id));

        let script_args = json!({
            "operation": "render_image",
            "project": project_path,
            "frame": frame,
            "settings": settings,
            "output_path": output_path.to_string_lossy()
        });

        // Execute asynchronously
        self.server
            .execute_script_async("render.py", script_args, job_id)
            .await?;

        let response = json!({
            "success": true,
            "job_id": job_id.to_string(),
            "status": "QUEUED",
            "message": "Render job started",
            "check_status": format!("/jobs/{}/status", job_id)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: render_animation
// ============================================================================

struct RenderAnimationTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RenderAnimationTool {
    fn name(&self) -> &str {
        "render_animation"
    }

    fn description(&self) -> &str {
        r#"Render an animation sequence.

This is an async operation. Use get_job_status to check progress."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "start_frame": { "type": "integer", "default": 1 },
                "end_frame": { "type": "integer", "default": 250 },
                "settings": {
                    "type": "object",
                    "properties": {
                        "resolution": { "type": "array", "items": { "type": "integer" }, "default": [1920, 1080] },
                        "samples": { "type": "integer", "default": 64 },
                        "engine": { "type": "string", "enum": ["CYCLES", "BLENDER_EEVEE"], "default": "BLENDER_EEVEE" },
                        "format": { "type": "string", "enum": ["MP4", "AVI", "MOV", "FRAMES"], "default": "MP4" }
                    }
                }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let start_frame = args
            .get("start_frame")
            .and_then(|v| v.as_i64())
            .unwrap_or(1);
        let end_frame = args.get("end_frame").and_then(|v| v.as_i64()).unwrap_or(250);
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Create job
        let jobs = self.server.jobs.read().await;
        let job_id = jobs.create_job("render_animation").await;

        // Get output path
        let executor = self.server.executor.read().await;
        let output_path = executor.output_dir().join("animations").join(job_id.to_string());

        let script_args = json!({
            "operation": "render_animation",
            "project": project_path,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "settings": settings,
            "output_path": format!("{}/", output_path.to_string_lossy())
        });

        // Execute asynchronously
        self.server
            .execute_script_async("render.py", script_args, job_id)
            .await?;

        let response = json!({
            "success": true,
            "job_id": job_id.to_string(),
            "status": "QUEUED",
            "frames": end_frame - start_frame + 1,
            "message": "Animation render job started",
            "check_status": format!("/jobs/{}/status", job_id)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: setup_physics
// ============================================================================

struct SetupPhysicsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SetupPhysicsTool {
    fn name(&self) -> &str {
        "setup_physics"
    }

    fn description(&self) -> &str {
        r#"Setup physics simulation for objects.

Physics types: rigid_body, soft_body, cloth, fluid"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object to apply physics to" },
                "physics_type": {
                    "type": "string",
                    "enum": ["rigid_body", "soft_body", "cloth", "fluid"],
                    "description": "Type of physics simulation"
                },
                "settings": {
                    "type": "object",
                    "properties": {
                        "mass": { "type": "number", "default": 1.0 },
                        "friction": { "type": "number", "default": 0.5 },
                        "bounce": { "type": "number", "default": 0.0 },
                        "collision_shape": {
                            "type": "string",
                            "enum": ["box", "sphere", "convex_hull", "mesh"],
                            "default": "convex_hull"
                        }
                    }
                }
            },
            "required": ["project", "object_name", "physics_type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let physics_type = args
            .get("physics_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'physics_type' parameter".to_string())
            })?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "setup_physics",
            "project": project_path,
            "object_name": object_name,
            "physics_type": physics_type,
            "settings": settings
        });

        self.server
            .execute_script("physics_sim.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "physics_type": physics_type,
            "message": format!("Physics '{}' applied to '{}'", physics_type, object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: bake_simulation
// ============================================================================

struct BakeSimulationTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for BakeSimulationTool {
    fn name(&self) -> &str {
        "bake_simulation"
    }

    fn description(&self) -> &str {
        r#"Bake physics simulation to keyframes.

This is an async operation. Use get_job_status to check progress."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "start_frame": { "type": "integer", "default": 1 },
                "end_frame": { "type": "integer", "default": 250 }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let start_frame = args
            .get("start_frame")
            .and_then(|v| v.as_i64())
            .unwrap_or(1);
        let end_frame = args.get("end_frame").and_then(|v| v.as_i64()).unwrap_or(250);

        let project_path = self.server.validate_project_path(project).await?;

        // Create job
        let jobs = self.server.jobs.read().await;
        let job_id = jobs.create_job("bake_simulation").await;

        let script_args = json!({
            "operation": "bake_simulation",
            "project": project_path,
            "start_frame": start_frame,
            "end_frame": end_frame
        });

        // Execute asynchronously
        self.server
            .execute_script_async("physics_sim.py", script_args, job_id)
            .await?;

        let response = json!({
            "success": true,
            "job_id": job_id.to_string(),
            "status": "RUNNING",
            "message": format!("Baking simulation frames {}-{}", start_frame, end_frame)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: create_animation
// ============================================================================

struct CreateAnimationTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateAnimationTool {
    fn name(&self) -> &str {
        "create_animation"
    }

    fn description(&self) -> &str {
        r#"Create keyframe animation.

Interpolation types: LINEAR, BEZIER, CONSTANT"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object to animate" },
                "keyframes": {
                    "type": "array",
                    "description": "List of keyframes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "frame": { "type": "integer" },
                            "location": { "type": "array", "items": { "type": "number" } },
                            "rotation": { "type": "array", "items": { "type": "number" } },
                            "scale": { "type": "array", "items": { "type": "number" } }
                        },
                        "required": ["frame"]
                    }
                },
                "interpolation": {
                    "type": "string",
                    "enum": ["LINEAR", "BEZIER", "CONSTANT"],
                    "default": "BEZIER"
                }
            },
            "required": ["project", "object_name", "keyframes"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let keyframes = args.get("keyframes").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'keyframes' parameter".to_string())
        })?;
        let interpolation = args
            .get("interpolation")
            .and_then(|v| v.as_str())
            .unwrap_or("BEZIER");

        let project_path = self.server.validate_project_path(project).await?;
        let keyframe_count = keyframes.as_array().map(|a| a.len()).unwrap_or(0);

        let script_args = json!({
            "operation": "create_animation",
            "project": project_path,
            "object_name": object_name,
            "keyframes": keyframes,
            "interpolation": interpolation
        });

        self.server
            .execute_script("animation.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "keyframes_count": keyframe_count,
            "message": format!("Animation created with {} keyframes", keyframe_count)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: create_geometry_nodes
// ============================================================================

struct CreateGeometryNodesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateGeometryNodesTool {
    fn name(&self) -> &str {
        "create_geometry_nodes"
    }

    fn description(&self) -> &str {
        r#"Create procedural geometry with nodes.

Node setups: scatter, array, grid, curve, spiral, volume, wave_deform, twist,
noise_displace, extrude, voronoi_scatter, mesh_to_points, crystal_scatter,
crystal_cluster, custom, proximity_mask, blur_attribute, map_range_displacement,
edge_crease_detection, organic_mutation"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object to apply geometry nodes to" },
                "node_setup": {
                    "type": "string",
                    "enum": ["scatter", "array", "grid", "curve", "spiral", "volume",
                             "wave_deform", "twist", "noise_displace", "extrude",
                             "voronoi_scatter", "mesh_to_points", "crystal_scatter",
                             "crystal_cluster", "custom", "proximity_mask", "blur_attribute",
                             "map_range_displacement", "edge_crease_detection", "organic_mutation"],
                    "description": "Type of geometry node setup"
                },
                "parameters": {
                    "type": "object",
                    "description": "Setup-specific parameters"
                }
            },
            "required": ["project", "object_name", "node_setup"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let node_setup = args
            .get("node_setup")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'node_setup' parameter".to_string())
            })?;
        let parameters = args.get("parameters").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "create_geometry_nodes",
            "project": project_path,
            "object_name": object_name,
            "node_setup": node_setup,
            "parameters": parameters
        });

        self.server
            .execute_script("geometry_nodes.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "node_setup": node_setup,
            "message": format!("Geometry nodes '{}' applied to '{}'", node_setup, object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_job_status
// ============================================================================

struct GetJobStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetJobStatusTool {
    fn name(&self) -> &str {
        "get_job_status"
    }

    fn description(&self) -> &str {
        "Get status of a rendering job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": { "type": "string", "description": "Job ID to check" }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id_str = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        let job_id = Uuid::parse_str(job_id_str)
            .map_err(|_| MCPError::InvalidParameters("Invalid job_id format".to_string()))?;

        let jobs = self.server.jobs.read().await;
        let job = jobs.get_job(job_id).await;

        match job {
            Some(j) => {
                let response = json!({
                    "job_id": job_id.to_string(),
                    "status": j.status.to_string(),
                    "progress": j.progress,
                    "message": j.message,
                    "created_at": j.created_at.to_rfc3339(),
                    "updated_at": j.updated_at.map(|t| t.to_rfc3339())
                });
                ToolResult::json(&response)
            }
            None => {
                let response = json!({ "error": format!("Job {} not found", job_id) });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: get_job_result
// ============================================================================

struct GetJobResultTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetJobResultTool {
    fn name(&self) -> &str {
        "get_job_result"
    }

    fn description(&self) -> &str {
        "Get result of a completed job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": { "type": "string", "description": "Job ID to retrieve" }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id_str = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        let job_id = Uuid::parse_str(job_id_str)
            .map_err(|_| MCPError::InvalidParameters("Invalid job_id format".to_string()))?;

        let jobs = self.server.jobs.read().await;
        let job = jobs.get_job(job_id).await;

        match job {
            Some(j) => {
                if j.status != JobStatus::Completed {
                    let response = json!({
                        "error": format!("Job {} not completed", job_id),
                        "status": j.status.to_string()
                    });
                    return ToolResult::json(&response);
                }

                let response = json!({
                    "job_id": job_id.to_string(),
                    "status": "COMPLETED",
                    "result": j.result,
                    "output_path": j.output_path
                });
                ToolResult::json(&response)
            }
            None => {
                let response = json!({ "error": format!("Job {} not found", job_id) });
                ToolResult::json(&response)
            }
        }
    }
}

// ============================================================================
// Tool: cancel_job
// ============================================================================

struct CancelJobTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CancelJobTool {
    fn name(&self) -> &str {
        "cancel_job"
    }

    fn description(&self) -> &str {
        "Cancel a running job."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": { "type": "string", "description": "Job ID to cancel" }
            },
            "required": ["job_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let job_id_str = args
            .get("job_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'job_id' parameter".to_string()))?;

        let job_id = Uuid::parse_str(job_id_str)
            .map_err(|_| MCPError::InvalidParameters("Invalid job_id format".to_string()))?;

        let jobs = self.server.jobs.read().await;
        let success = jobs.cancel_job(job_id).await;

        if success {
            // Also try to kill the Blender process
            let executor = self.server.executor.read().await;
            executor.kill_process(job_id).await;

            let response = json!({
                "success": true,
                "message": format!("Job {} cancelled", job_id)
            });
            ToolResult::json(&response)
        } else {
            let response = json!({ "error": format!("Could not cancel job {}", job_id) });
            ToolResult::json(&response)
        }
    }
}

// ============================================================================
// Tool: import_model
// ============================================================================

struct ImportModelTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ImportModelTool {
    fn name(&self) -> &str {
        "import_model"
    }

    fn description(&self) -> &str {
        r#"Import 3D model into project.

Supported formats: FBX, OBJ, GLTF, STL, PLY"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "model_path": { "type": "string", "description": "Path to model file" },
                "format": {
                    "type": "string",
                    "enum": ["FBX", "OBJ", "GLTF", "STL", "PLY"],
                    "description": "Model format (auto-detected if not specified)"
                },
                "location": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] }
            },
            "required": ["project", "model_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let model_path = args
            .get("model_path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'model_path' parameter".to_string())
            })?;
        let location = args.get("location").cloned().unwrap_or(json!([0, 0, 0]));

        let project_path = self.server.validate_project_path(project).await?;
        let validated_model_path = self.server.validate_asset_path(model_path).await?;

        let executor = self.server.executor.read().await;
        let file_format = args
            .get("format")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .or_else(|| executor.detect_format(model_path))
            .unwrap_or_else(|| "AUTO".to_string());

        let script_args = json!({
            "operation": "import_model",
            "project": project_path,
            "model_path": validated_model_path,
            "format": file_format,
            "location": location
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "model_path": model_path,
            "format": file_format,
            "message": format!("Model imported from '{}'", model_path)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: export_scene
// ============================================================================

struct ExportSceneTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ExportSceneTool {
    fn name(&self) -> &str {
        "export_scene"
    }

    fn description(&self) -> &str {
        r#"Export scene to various formats.

Supported formats: FBX, OBJ, GLTF, STL, USD"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "format": {
                    "type": "string",
                    "enum": ["FBX", "OBJ", "GLTF", "STL", "USD"],
                    "description": "Export format"
                },
                "selected_only": { "type": "boolean", "default": false }
            },
            "required": ["project", "format"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let export_format = args
            .get("format")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'format' parameter".to_string()))?;
        let selected_only = args
            .get("selected_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let project_path = self.server.validate_project_path(project).await?;

        // Generate output path
        let executor = self.server.executor.read().await;
        let project_stem = std::path::Path::new(&project_path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("export");
        let output_path = executor
            .output_dir()
            .join(format!("{}.{}", project_stem, export_format.to_lowercase()));

        let script_args = json!({
            "operation": "export_scene",
            "project": project_path,
            "format": export_format,
            "output_path": output_path.to_string_lossy(),
            "selected_only": selected_only
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "output_path": output_path.to_string_lossy(),
            "format": export_format,
            "message": format!("Scene exported to '{}'", output_path.display())
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: setup_camera
// ============================================================================

struct SetupCameraTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SetupCameraTool {
    fn name(&self) -> &str {
        "setup_camera"
    }

    fn description(&self) -> &str {
        "Configure camera position and settings."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "location": { "type": "array", "items": { "type": "number" }, "default": [7, -6, 5] },
                "rotation": { "type": "array", "items": { "type": "number" }, "default": [1.1, 0, 0.8] },
                "focal_length": { "type": "number", "default": 50 },
                "sensor_width": { "type": "number", "default": 36 },
                "dof_enabled": { "type": "boolean", "default": false },
                "focus_distance": { "type": "number", "default": 10 },
                "aperture": { "type": "number", "default": 2.8 }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "setup_camera",
            "project": project_path,
            "location": args.get("location").cloned().unwrap_or(json!([7, -6, 5])),
            "rotation": args.get("rotation").cloned().unwrap_or(json!([1.1, 0, 0.8])),
            "focal_length": args.get("focal_length").and_then(|v| v.as_f64()).unwrap_or(50.0),
            "sensor_width": args.get("sensor_width").and_then(|v| v.as_f64()).unwrap_or(36.0),
            "dof_enabled": args.get("dof_enabled").and_then(|v| v.as_bool()).unwrap_or(false),
            "focus_distance": args.get("focus_distance").and_then(|v| v.as_f64()).unwrap_or(10.0),
            "aperture": args.get("aperture").and_then(|v| v.as_f64()).unwrap_or(2.8)
        });

        self.server
            .execute_script("camera_tools.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "message": "Camera configured"
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_camera_track
// ============================================================================

struct AddCameraTrackTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddCameraTrackTool {
    fn name(&self) -> &str {
        "add_camera_track"
    }

    fn description(&self) -> &str {
        r#"Add camera tracking constraint.

Track types: TRACK_TO, DAMPED_TRACK, LOCKED_TRACK"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "target": { "type": "string", "description": "Target object name" },
                "track_type": {
                    "type": "string",
                    "enum": ["TRACK_TO", "DAMPED_TRACK", "LOCKED_TRACK"],
                    "default": "TRACK_TO"
                }
            },
            "required": ["project", "target"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let target = args
            .get("target")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'target' parameter".to_string()))?;
        let track_type = args
            .get("track_type")
            .and_then(|v| v.as_str())
            .unwrap_or("TRACK_TO");

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_camera_track",
            "project": project_path,
            "target": target,
            "track_type": track_type
        });

        self.server
            .execute_script("camera_tools.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "target": target,
            "track_type": track_type,
            "message": format!("Camera tracking '{}' added to target '{}'", track_type, target)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_modifier
// ============================================================================

struct AddModifierTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddModifierTool {
    fn name(&self) -> &str {
        "add_modifier"
    }

    fn description(&self) -> &str {
        r#"Add a modifier to an object.

Modifier types: SUBSURF, ARRAY, MIRROR, SOLIDIFY, BEVEL, DECIMATE, REMESH, SMOOTH, WAVE, DISPLACE"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object name" },
                "modifier_type": {
                    "type": "string",
                    "enum": ["SUBSURF", "ARRAY", "MIRROR", "SOLIDIFY", "BEVEL",
                             "DECIMATE", "REMESH", "SMOOTH", "WAVE", "DISPLACE"]
                },
                "settings": { "type": "object", "description": "Modifier-specific settings" }
            },
            "required": ["project", "object_name", "modifier_type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let modifier_type = args
            .get("modifier_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'modifier_type' parameter".to_string())
            })?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_modifier",
            "project": project_path,
            "object_name": object_name,
            "modifier_type": modifier_type,
            "settings": settings
        });

        self.server
            .execute_script("modifiers.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "modifier_type": modifier_type,
            "message": format!("Modifier '{}' added to '{}'", modifier_type, object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_particle_system
// ============================================================================

struct AddParticleSystemTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddParticleSystemTool {
    fn name(&self) -> &str {
        "add_particle_system"
    }

    fn description(&self) -> &str {
        r#"Add a particle system to an object.

Particle types: emitter, hair"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object name" },
                "particle_type": {
                    "type": "string",
                    "enum": ["emitter", "hair"],
                    "default": "emitter"
                },
                "count": { "type": "integer", "default": 1000 },
                "settings": { "type": "object", "description": "Particle-specific settings" }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let particle_type = args
            .get("particle_type")
            .and_then(|v| v.as_str())
            .unwrap_or("emitter");
        let count = args.get("count").and_then(|v| v.as_i64()).unwrap_or(1000);
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_particle_system",
            "project": project_path,
            "object_name": object_name,
            "particle_type": particle_type,
            "count": count,
            "settings": settings
        });

        self.server
            .execute_script("particles.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "particle_type": particle_type,
            "count": count,
            "message": format!("Particle system added to '{}'", object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_smoke_simulation
// ============================================================================

struct AddSmokeSimulationTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddSmokeSimulationTool {
    fn name(&self) -> &str {
        "add_smoke_simulation"
    }

    fn description(&self) -> &str {
        r#"Add smoke/fire simulation to an object.

Smoke types: smoke, fire, both"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object name" },
                "smoke_type": {
                    "type": "string",
                    "enum": ["smoke", "fire", "both"],
                    "default": "smoke"
                },
                "settings": { "type": "object", "description": "Simulation settings" }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let smoke_type = args
            .get("smoke_type")
            .and_then(|v| v.as_str())
            .unwrap_or("smoke");
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_smoke_simulation",
            "project": project_path,
            "object_name": object_name,
            "smoke_type": smoke_type,
            "settings": settings
        });

        self.server
            .execute_script("particles.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "smoke_type": smoke_type,
            "message": format!("Smoke simulation added to '{}'", object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_texture
// ============================================================================

struct AddTextureTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddTextureTool {
    fn name(&self) -> &str {
        "add_texture"
    }

    fn description(&self) -> &str {
        r#"Add a texture to an object.

Texture types: IMAGE, NOISE, VORONOI, MUSGRAVE, WAVE, MAGIC, BRICK, CHECKER"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object name" },
                "texture_type": {
                    "type": "string",
                    "enum": ["IMAGE", "NOISE", "VORONOI", "MUSGRAVE", "WAVE", "MAGIC", "BRICK", "CHECKER"]
                },
                "settings": { "type": "object", "description": "Texture settings" }
            },
            "required": ["project", "object_name", "texture_type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let texture_type = args
            .get("texture_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'texture_type' parameter".to_string())
            })?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_texture",
            "project": project_path,
            "object_name": object_name,
            "texture_type": texture_type,
            "settings": settings
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "texture_type": texture_type,
            "message": format!("Texture '{}' added to '{}'", texture_type, object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_uv_map
// ============================================================================

struct AddUvMapTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddUvMapTool {
    fn name(&self) -> &str {
        "add_uv_map"
    }

    fn description(&self) -> &str {
        r#"Add UV mapping to an object.

Projection types: SMART_PROJECT, CUBE_PROJECT, CYLINDER_PROJECT, SPHERE_PROJECT, PROJECT_FROM_VIEW"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object name" },
                "projection_type": {
                    "type": "string",
                    "enum": ["SMART_PROJECT", "CUBE_PROJECT", "CYLINDER_PROJECT",
                             "SPHERE_PROJECT", "PROJECT_FROM_VIEW"],
                    "default": "SMART_PROJECT"
                }
            },
            "required": ["project", "object_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let projection_type = args
            .get("projection_type")
            .and_then(|v| v.as_str())
            .unwrap_or("SMART_PROJECT");

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_uv_map",
            "project": project_path,
            "object_name": object_name,
            "projection_type": projection_type
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "projection_type": projection_type,
            "message": format!("UV mapping '{}' added to '{}'", projection_type, object_name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: setup_compositor
// ============================================================================

struct SetupCompositorTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SetupCompositorTool {
    fn name(&self) -> &str {
        "setup_compositor"
    }

    fn description(&self) -> &str {
        r#"Setup compositor nodes for post-processing.

Setups: BASIC, DENOISING, COLOR_GRADING, GLARE, FOG_GLOW, LENS_DISTORTION, VIGNETTE"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "setup": {
                    "type": "string",
                    "enum": ["BASIC", "DENOISING", "COLOR_GRADING", "GLARE",
                             "FOG_GLOW", "LENS_DISTORTION", "VIGNETTE"]
                },
                "settings": { "type": "object", "description": "Compositor settings" }
            },
            "required": ["project", "setup"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let setup = args
            .get("setup")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'setup' parameter".to_string()))?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "setup_compositor",
            "project": project_path,
            "setup": setup,
            "settings": settings
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "setup": setup,
            "message": format!("Compositor '{}' setup applied", setup)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: batch_render
// ============================================================================

struct BatchRenderTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for BatchRenderTool {
    fn name(&self) -> &str {
        "batch_render"
    }

    fn description(&self) -> &str {
        "Render multiple frames, cameras, or render layers in batch."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "frames": { "type": "array", "items": { "type": "integer" }, "description": "List of frames to render" },
                "cameras": { "type": "array", "items": { "type": "string" }, "description": "List of cameras to render from" },
                "layers": { "type": "array", "items": { "type": "string" }, "description": "List of render layers" },
                "settings": { "type": "object", "description": "Render settings" }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let frames = args.get("frames").cloned().unwrap_or(json!([1]));
        let cameras = args.get("cameras").cloned().unwrap_or(json!([]));
        let layers = args.get("layers").cloned().unwrap_or(json!([]));
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Create job
        let jobs = self.server.jobs.read().await;
        let job_id = jobs.create_job("batch_render").await;

        let executor = self.server.executor.read().await;
        let output_dir = executor.output_dir().join("batch").join(job_id.to_string());

        let script_args = json!({
            "operation": "batch_render",
            "project": project_path,
            "frames": frames,
            "cameras": cameras,
            "layers": layers,
            "settings": settings,
            "output_dir": output_dir.to_string_lossy()
        });

        // Execute asynchronously
        self.server
            .execute_script_async("render.py", script_args, job_id)
            .await?;

        let response = json!({
            "success": true,
            "job_id": job_id.to_string(),
            "status": "QUEUED",
            "message": "Batch render job started"
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: delete_objects
// ============================================================================

struct DeleteObjectsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DeleteObjectsTool {
    fn name(&self) -> &str {
        "delete_objects"
    }

    fn description(&self) -> &str {
        "Delete objects from the scene by name or type pattern."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "names": { "type": "array", "items": { "type": "string" }, "description": "Object names to delete" },
                "type_pattern": { "type": "string", "description": "Object type pattern to match" }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let names = args.get("names").cloned().unwrap_or(json!([]));
        let type_pattern = args.get("type_pattern").and_then(|v| v.as_str());

        let project_path = self.server.validate_project_path(project).await?;

        let mut script_args = json!({
            "operation": "delete_objects",
            "project": project_path,
            "names": names
        });

        if let Some(pattern) = type_pattern {
            script_args["type_pattern"] = json!(pattern);
        }

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "message": "Objects deleted"
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: analyze_scene
// ============================================================================

struct AnalyzeSceneTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AnalyzeSceneTool {
    fn name(&self) -> &str {
        "analyze_scene"
    }

    fn description(&self) -> &str {
        r#"Analyze scene for statistics and potential issues.

Analysis types: BASIC, DETAILED, PERFORMANCE, MEMORY"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "analysis_type": {
                    "type": "string",
                    "enum": ["BASIC", "DETAILED", "PERFORMANCE", "MEMORY"],
                    "default": "BASIC"
                }
            },
            "required": ["project"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let analysis_type = args
            .get("analysis_type")
            .and_then(|v| v.as_str())
            .unwrap_or("BASIC");

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "analyze_scene",
            "project": project_path,
            "analysis_type": analysis_type
        });

        let result = self
            .server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "analysis_type": analysis_type,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: optimize_scene
// ============================================================================

struct OptimizeSceneTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for OptimizeSceneTool {
    fn name(&self) -> &str {
        "optimize_scene"
    }

    fn description(&self) -> &str {
        r#"Optimize scene for better performance.

Optimization types: MESH_CLEANUP, TEXTURE_OPTIMIZATION, MODIFIER_APPLY, INSTANCE_OPTIMIZATION, MATERIAL_CLEANUP"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "optimization_type": {
                    "type": "string",
                    "enum": ["MESH_CLEANUP", "TEXTURE_OPTIMIZATION", "MODIFIER_APPLY",
                             "INSTANCE_OPTIMIZATION", "MATERIAL_CLEANUP"]
                },
                "settings": { "type": "object", "description": "Optimization settings" }
            },
            "required": ["project", "optimization_type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let optimization_type = args
            .get("optimization_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'optimization_type' parameter".to_string())
            })?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "optimize_scene",
            "project": project_path,
            "optimization_type": optimization_type,
            "settings": settings
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "optimization_type": optimization_type,
            "message": format!("Optimization '{}' applied", optimization_type)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: create_curve
// ============================================================================

struct CreateCurveTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateCurveTool {
    fn name(&self) -> &str {
        "create_curve"
    }

    fn description(&self) -> &str {
        "Create a Bezier curve from control points."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "name": { "type": "string", "description": "Curve name" },
                "points": {
                    "type": "array",
                    "description": "Control points",
                    "items": {
                        "type": "array",
                        "items": { "type": "number" }
                    }
                },
                "cyclic": { "type": "boolean", "default": false }
            },
            "required": ["project", "name", "points"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;
        let points = args
            .get("points")
            .cloned()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'points' parameter".to_string()))?;
        let cyclic = args.get("cyclic").and_then(|v| v.as_bool()).unwrap_or(false);

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "create_curve",
            "project": project_path,
            "name": name,
            "points": points,
            "cyclic": cyclic
        });

        self.server
            .execute_script("scene_builder.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "name": name,
            "message": format!("Curve '{}' created", name)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: setup_world_environment
// ============================================================================

struct SetupWorldEnvironmentTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SetupWorldEnvironmentTool {
    fn name(&self) -> &str {
        "setup_world_environment"
    }

    fn description(&self) -> &str {
        r#"Setup world environment.

Environment types: HDRI, SKY_TEXTURE, GRADIENT, COLOR, VOLUMETRIC"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "environment_type": {
                    "type": "string",
                    "enum": ["HDRI", "SKY_TEXTURE", "GRADIENT", "COLOR", "VOLUMETRIC"]
                },
                "settings": { "type": "object", "description": "Environment settings" }
            },
            "required": ["project", "environment_type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'project' parameter".to_string()))?;
        let environment_type = args
            .get("environment_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'environment_type' parameter".to_string())
            })?;
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "setup_world_environment",
            "project": project_path,
            "environment_type": environment_type,
            "settings": settings
        });

        self.server
            .execute_script("environment.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "environment_type": environment_type,
            "message": format!("Environment '{}' configured", environment_type)
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: blender_status
// ============================================================================

struct BlenderStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for BlenderStatusTool {
    fn name(&self) -> &str {
        "blender_status"
    }

    fn description(&self) -> &str {
        "Get Blender server status and configuration."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let executor = self.server.executor.read().await;
        let jobs = self.server.jobs.read().await;

        let blender_path = {
            // Check if Blender is available
            match executor.ensure_initialized().await {
                Ok(path) => Some(path.to_string_lossy().to_string()),
                Err(_) => None,
            }
        };

        let all_jobs = jobs.list_jobs().await;
        let running_jobs = all_jobs
            .iter()
            .filter(|j| j.status == JobStatus::Running)
            .count();
        let queued_jobs = all_jobs
            .iter()
            .filter(|j| j.status == JobStatus::Queued)
            .count();

        let response = json!({
            "server": "blender",
            "version": "2.0.0",
            "blender_available": blender_path.is_some(),
            "blender_path": blender_path,
            "base_dir": executor.base_dir().to_string_lossy(),
            "scripts_dir": executor.projects_dir().to_string_lossy(),
            "output_dir": executor.output_dir().to_string_lossy(),
            "jobs": {
                "running": running_jobs,
                "queued": queued_jobs,
                "total": all_jobs.len()
            }
        });
        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = BlenderServer::new();
        let tools = server.tools();
        assert!(tools.len() >= 30);
    }

    #[test]
    fn test_tool_names() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        // Core tools
        assert!(names.contains(&"create_blender_project"));
        assert!(names.contains(&"list_projects"));
        assert!(names.contains(&"add_primitive_objects"));
        assert!(names.contains(&"setup_lighting"));
        assert!(names.contains(&"apply_material"));
        assert!(names.contains(&"render_image"));
        assert!(names.contains(&"render_animation"));
        assert!(names.contains(&"setup_physics"));
        assert!(names.contains(&"bake_simulation"));
        assert!(names.contains(&"create_animation"));
        assert!(names.contains(&"create_geometry_nodes"));

        // Job tools
        assert!(names.contains(&"get_job_status"));
        assert!(names.contains(&"get_job_result"));
        assert!(names.contains(&"cancel_job"));

        // Asset tools
        assert!(names.contains(&"import_model"));
        assert!(names.contains(&"export_scene"));

        // Extended tools
        assert!(names.contains(&"setup_camera"));
        assert!(names.contains(&"add_modifier"));
        assert!(names.contains(&"add_particle_system"));
        assert!(names.contains(&"setup_compositor"));
        assert!(names.contains(&"setup_world_environment"));

        // Status
        assert!(names.contains(&"blender_status"));
    }
}
