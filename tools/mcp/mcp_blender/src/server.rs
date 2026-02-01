//! MCP server implementation for Blender operations.
//!
//! Provides comprehensive 3D content creation tools through headless Blender automation.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::sync::Arc;
use tokio::sync::RwLock;
// tracing macros are used in the blender.rs module
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
            // Quick Effects (one-click simulations)
            Arc::new(QuickSmokeTool {
                server: self.clone_refs(),
            }),
            Arc::new(QuickLiquidTool {
                server: self.clone_refs(),
            }),
            Arc::new(QuickExplodeTool {
                server: self.clone_refs(),
            }),
            Arc::new(QuickFurTool {
                server: self.clone_refs(),
            }),
            // Advanced Objects
            Arc::new(AddConstraintTool {
                server: self.clone_refs(),
            }),
            Arc::new(CreateArmatureTool {
                server: self.clone_refs(),
            }),
            Arc::new(CreateTextObjectTool {
                server: self.clone_refs(),
            }),
            Arc::new(AddAdvancedPrimitivesTool {
                server: self.clone_refs(),
            }),
            Arc::new(ParentObjectsTool {
                server: self.clone_refs(),
            }),
            Arc::new(JoinObjectsTool {
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
                    jobs_clone.complete_job(job_id, result, None).await;
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

        // Validate project name to prevent path traversal
        // Reject names containing path separators or parent directory references
        if name.contains('/') || name.contains('\\') || name.contains("..") {
            return Err(MCPError::InvalidParameters(
                "Project name cannot contain path separators or '..'".to_string(),
            ));
        }

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let lighting_type = args
            .get("type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'type' parameter".to_string()))?;
        let mut settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Validate hdri_path if present to prevent directory traversal
        if let Some(hdri_path) = settings.get("hdri_path").and_then(|v| v.as_str()) {
            let validated_path = self.server.validate_asset_path(hdri_path).await?;
            settings["hdri_path"] = json!(validated_path);
        }

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let start_frame = args
            .get("start_frame")
            .and_then(|v| v.as_i64())
            .unwrap_or(1);
        let end_frame = args
            .get("end_frame")
            .and_then(|v| v.as_i64())
            .unwrap_or(250);
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Create job
        let jobs = self.server.jobs.read().await;
        let job_id = jobs.create_job("render_animation").await;

        // Get output path
        let executor = self.server.executor.read().await;
        let output_path = executor
            .output_dir()
            .join("animations")
            .join(job_id.to_string());

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let start_frame = args
            .get("start_frame")
            .and_then(|v| v.as_i64())
            .unwrap_or(1);
        let end_frame = args
            .get("end_frame")
            .and_then(|v| v.as_i64())
            .unwrap_or(250);

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
        let output_path = executor.output_dir().join(format!(
            "{}.{}",
            project_stem,
            export_format.to_lowercase()
        ));

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
        let mut settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Validate image_path if present (for IMAGE texture type) to prevent directory traversal
        if texture_type == "IMAGE" {
            if let Some(image_path) = settings.get("image_path").and_then(|v| v.as_str()) {
                let validated_path = self.server.validate_asset_path(image_path).await?;
                settings["image_path"] = json!(validated_path);
            }
        }

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'name' parameter".to_string()))?;
        let points = args
            .get("points")
            .cloned()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'points' parameter".to_string()))?;
        let cyclic = args
            .get("cyclic")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let environment_type = args
            .get("environment_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'environment_type' parameter".to_string())
            })?;
        let mut settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        // Validate hdri_path if present (for HDRI environment type) to prevent directory traversal
        if environment_type == "HDRI" {
            if let Some(hdri_path) = settings.get("hdri_path").and_then(|v| v.as_str()) {
                let validated_path = self.server.validate_asset_path(hdri_path).await?;
                settings["hdri_path"] = json!(validated_path);
            }
        }

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
            "scripts_dir": executor.scripts_dir().to_string_lossy(),
            "projects_dir": executor.projects_dir().to_string_lossy(),
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

// ============================================================================
// Tool: quick_smoke
// ============================================================================

struct QuickSmokeTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for QuickSmokeTool {
    fn name(&self) -> &str {
        "quick_smoke"
    }

    fn description(&self) -> &str {
        r#"Add smoke/fire simulation with one click.

Creates a fluid domain around selected objects configured as smoke emitters.
Styles: SMOKE, FIRE, BOTH"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_names": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Names of mesh objects to make smoke emitters"
                },
                "style": {
                    "type": "string",
                    "enum": ["SMOKE", "FIRE", "BOTH"],
                    "default": "SMOKE"
                },
                "show_flows": { "type": "boolean", "default": false },
                "domain_resolution": { "type": "integer", "default": 32 }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let object_names = args.get("object_names").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'object_names' parameter".to_string())
        })?;
        let style = args
            .get("style")
            .and_then(|v| v.as_str())
            .unwrap_or("SMOKE");
        let show_flows = args
            .get("show_flows")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let resolution = args
            .get("domain_resolution")
            .and_then(|v| v.as_i64())
            .unwrap_or(32);

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "quick_smoke",
            "project": project_path,
            "object_names": object_names,
            "style": style,
            "show_flows": show_flows,
            "domain_resolution": resolution
        });

        let result = self
            .server
            .execute_script("quick_effects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "style": style,
            "message": format!("Smoke simulation '{}' created", style),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: quick_liquid
// ============================================================================

struct QuickLiquidTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for QuickLiquidTool {
    fn name(&self) -> &str {
        "quick_liquid"
    }

    fn description(&self) -> &str {
        r#"Add liquid simulation with one click.

Creates a fluid domain with selected objects as liquid sources."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_names": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Names of mesh objects to make liquid sources"
                },
                "show_flows": { "type": "boolean", "default": false },
                "domain_resolution": { "type": "integer", "default": 64 }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let object_names = args.get("object_names").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'object_names' parameter".to_string())
        })?;
        let show_flows = args
            .get("show_flows")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let resolution = args
            .get("domain_resolution")
            .and_then(|v| v.as_i64())
            .unwrap_or(64);

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "quick_liquid",
            "project": project_path,
            "object_names": object_names,
            "show_flows": show_flows,
            "domain_resolution": resolution
        });

        let result = self
            .server
            .execute_script("quick_effects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "message": "Liquid simulation created",
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: quick_explode
// ============================================================================

struct QuickExplodeTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for QuickExplodeTool {
    fn name(&self) -> &str {
        "quick_explode"
    }

    fn description(&self) -> &str {
        r#"Add explosion effect to objects.

Creates particle system with explode modifier for destruction effects."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_names": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Names of mesh objects to explode"
                },
                "piece_count": { "type": "integer", "default": 100 },
                "frame_start": { "type": "integer", "default": 1 },
                "frame_duration": { "type": "integer", "default": 50 },
                "velocity": { "type": "number", "default": 1.0 },
                "fade": { "type": "boolean", "default": true }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let object_names = args.get("object_names").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'object_names' parameter".to_string())
        })?;
        let piece_count = args
            .get("piece_count")
            .and_then(|v| v.as_i64())
            .unwrap_or(100);
        let frame_start = args
            .get("frame_start")
            .and_then(|v| v.as_i64())
            .unwrap_or(1);
        let frame_duration = args
            .get("frame_duration")
            .and_then(|v| v.as_i64())
            .unwrap_or(50);
        let velocity = args.get("velocity").and_then(|v| v.as_f64()).unwrap_or(1.0);
        let fade = args.get("fade").and_then(|v| v.as_bool()).unwrap_or(true);

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "quick_explode",
            "project": project_path,
            "object_names": object_names,
            "piece_count": piece_count,
            "frame_start": frame_start,
            "frame_duration": frame_duration,
            "velocity": velocity,
            "fade": fade
        });

        let result = self
            .server
            .execute_script("quick_effects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "pieces": piece_count,
            "message": "Explosion effect created",
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: quick_fur
// ============================================================================

struct QuickFurTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for QuickFurTool {
    fn name(&self) -> &str {
        "quick_fur"
    }

    fn description(&self) -> &str {
        r#"Add fur/hair to objects using geometry nodes.

Density levels: LOW (1000), MEDIUM (10000), HIGH (100000)"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_names": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Names of mesh objects to add fur"
                },
                "density": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH"],
                    "default": "MEDIUM"
                },
                "length": { "type": "number", "default": 0.1 },
                "radius": { "type": "number", "default": 0.001 },
                "use_noise": { "type": "boolean", "default": true },
                "use_frizz": { "type": "boolean", "default": true }
            },
            "required": ["project", "object_names"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let object_names = args.get("object_names").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'object_names' parameter".to_string())
        })?;
        let density = args
            .get("density")
            .and_then(|v| v.as_str())
            .unwrap_or("MEDIUM");
        let length = args.get("length").and_then(|v| v.as_f64()).unwrap_or(0.1);
        let radius = args.get("radius").and_then(|v| v.as_f64()).unwrap_or(0.001);
        let use_noise = args
            .get("use_noise")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        let use_frizz = args
            .get("use_frizz")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "quick_fur",
            "project": project_path,
            "object_names": object_names,
            "density": density,
            "length": length,
            "radius": radius,
            "use_noise": use_noise,
            "use_frizz": use_frizz
        });

        let result = self
            .server
            .execute_script("quick_effects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "density": density,
            "message": "Fur system created",
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_constraint
// ============================================================================

struct AddConstraintTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddConstraintTool {
    fn name(&self) -> &str {
        "add_constraint"
    }

    fn description(&self) -> &str {
        r#"Add constraint to an object.

Constraint types: TRACK_TO, COPY_LOCATION, COPY_ROTATION, COPY_SCALE,
LIMIT_LOCATION, LIMIT_ROTATION, LIMIT_SCALE, FOLLOW_PATH, DAMPED_TRACK, FLOOR"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_name": { "type": "string", "description": "Object to add constraint to" },
                "constraint_type": {
                    "type": "string",
                    "enum": ["TRACK_TO", "COPY_LOCATION", "COPY_ROTATION", "COPY_SCALE",
                             "LIMIT_LOCATION", "LIMIT_ROTATION", "LIMIT_SCALE",
                             "FOLLOW_PATH", "DAMPED_TRACK", "FLOOR", "CHILD_OF"]
                },
                "target_object": { "type": "string", "description": "Target object for constraint" },
                "settings": { "type": "object", "description": "Constraint-specific settings" }
            },
            "required": ["project", "object_name", "constraint_type"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let object_name = args
            .get("object_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'object_name' parameter".to_string())
            })?;
        let constraint_type = args
            .get("constraint_type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'constraint_type' parameter".to_string())
            })?;
        let target_object = args.get("target_object").and_then(|v| v.as_str());
        let settings = args.get("settings").cloned().unwrap_or(json!({}));

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_constraint",
            "project": project_path,
            "object_name": object_name,
            "constraint_type": constraint_type,
            "target_object": target_object,
            "settings": settings
        });

        let result = self
            .server
            .execute_script("advanced_objects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "object": object_name,
            "constraint_type": constraint_type,
            "message": format!("Constraint '{}' added to '{}'", constraint_type, object_name),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: create_armature
// ============================================================================

struct CreateArmatureTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateArmatureTool {
    fn name(&self) -> &str {
        "create_armature"
    }

    fn description(&self) -> &str {
        r#"Create an armature with bones for rigging.

Bones are defined with head/tail positions and optional parent relationships."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "name": { "type": "string", "default": "Armature" },
                "location": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] },
                "bones": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": { "type": "string" },
                            "head": { "type": "array", "items": { "type": "number" } },
                            "tail": { "type": "array", "items": { "type": "number" } },
                            "parent": { "type": "string" },
                            "connected": { "type": "boolean", "default": false }
                        },
                        "required": ["name", "head", "tail"]
                    }
                }
            },
            "required": ["project", "bones"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let name = args
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("Armature");
        let location = args.get("location").cloned().unwrap_or(json!([0, 0, 0]));
        let bones = args
            .get("bones")
            .cloned()
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'bones' parameter".to_string()))?;

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "create_armature",
            "project": project_path,
            "name": name,
            "location": location,
            "bones": bones
        });

        let result = self
            .server
            .execute_script("advanced_objects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "armature": name,
            "message": format!("Armature '{}' created", name),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: create_text_object
// ============================================================================

struct CreateTextObjectTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CreateTextObjectTool {
    fn name(&self) -> &str {
        "create_text_object"
    }

    fn description(&self) -> &str {
        r#"Create a 3D text object.

Supports extrusion, bevel, and custom fonts."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "text": { "type": "string", "description": "Text content" },
                "name": { "type": "string", "default": "Text" },
                "location": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] },
                "rotation": { "type": "array", "items": { "type": "number" }, "default": [0, 0, 0] },
                "size": { "type": "number", "default": 1.0 },
                "extrude": { "type": "number", "default": 0.0 },
                "bevel_depth": { "type": "number", "default": 0.0 },
                "align_x": {
                    "type": "string",
                    "enum": ["CENTER", "LEFT", "RIGHT", "JUSTIFY", "FLUSH"],
                    "default": "LEFT"
                },
                "align_y": {
                    "type": "string",
                    "enum": ["TOP", "CENTER", "BOTTOM"],
                    "default": "TOP"
                },
                "font_path": { "type": "string", "description": "Path to custom font file" }
            },
            "required": ["project", "text"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let text = args
            .get("text")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'text' parameter".to_string()))?;

        let project_path = self.server.validate_project_path(project).await?;

        // Validate font_path if present to prevent directory traversal
        let validated_font_path =
            if let Some(font_path) = args.get("font_path").and_then(|v| v.as_str()) {
                Some(self.server.validate_asset_path(font_path).await?)
            } else {
                None
            };

        let script_args = json!({
            "operation": "create_text_object",
            "project": project_path,
            "text": text,
            "name": args.get("name").and_then(|v| v.as_str()).unwrap_or("Text"),
            "location": args.get("location").cloned().unwrap_or(json!([0, 0, 0])),
            "rotation": args.get("rotation").cloned().unwrap_or(json!([0, 0, 0])),
            "size": args.get("size").and_then(|v| v.as_f64()).unwrap_or(1.0),
            "extrude": args.get("extrude").and_then(|v| v.as_f64()).unwrap_or(0.0),
            "bevel_depth": args.get("bevel_depth").and_then(|v| v.as_f64()).unwrap_or(0.0),
            "align_x": args.get("align_x").and_then(|v| v.as_str()).unwrap_or("LEFT"),
            "align_y": args.get("align_y").and_then(|v| v.as_str()).unwrap_or("TOP"),
            "font_path": validated_font_path
        });

        let result = self
            .server
            .execute_script("advanced_objects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "text": text,
            "message": "Text object created",
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_advanced_primitives
// ============================================================================

struct AddAdvancedPrimitivesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddAdvancedPrimitivesTool {
    fn name(&self) -> &str {
        "add_advanced_primitives"
    }

    fn description(&self) -> &str {
        r#"Add advanced primitive objects.

Types: grid, circle, ico_sphere, empty, bezier_curve, nurbs_curve, metaball"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "objects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["grid", "circle", "ico_sphere", "empty",
                                         "bezier_curve", "nurbs_curve", "nurbs_circle", "metaball"]
                            },
                            "name": { "type": "string" },
                            "location": { "type": "array", "items": { "type": "number" } },
                            "rotation": { "type": "array", "items": { "type": "number" } },
                            "scale": { "type": "array", "items": { "type": "number" } }
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
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let objects = args.get("objects").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'objects' parameter".to_string())
        })?;

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "add_advanced_primitives",
            "project": project_path,
            "objects": objects
        });

        let result = self
            .server
            .execute_script("advanced_objects.py", script_args)
            .await?;

        let count = objects.as_array().map(|a| a.len()).unwrap_or(0);
        let response = json!({
            "success": true,
            "objects_added": count,
            "message": format!("Added {} advanced primitives", count),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: parent_objects
// ============================================================================

struct ParentObjectsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ParentObjectsTool {
    fn name(&self) -> &str {
        "parent_objects"
    }

    fn description(&self) -> &str {
        "Set parent-child relationships between objects."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "parent_name": { "type": "string", "description": "Name of parent object" },
                "children": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Names of child objects"
                },
                "keep_transform": { "type": "boolean", "default": true },
                "parent_type": {
                    "type": "string",
                    "enum": ["OBJECT", "ARMATURE", "BONE"],
                    "default": "OBJECT"
                },
                "bone_name": { "type": "string", "description": "Bone name if parent_type is BONE" }
            },
            "required": ["project", "parent_name", "children"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let parent_name = args
            .get("parent_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'parent_name' parameter".to_string())
            })?;
        let children = args.get("children").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'children' parameter".to_string())
        })?;

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "parent_objects",
            "project": project_path,
            "parent_name": parent_name,
            "children": children,
            "keep_transform": args.get("keep_transform").and_then(|v| v.as_bool()).unwrap_or(true),
            "parent_type": args.get("parent_type").and_then(|v| v.as_str()).unwrap_or("OBJECT"),
            "bone_name": args.get("bone_name").and_then(|v| v.as_str())
        });

        let result = self
            .server
            .execute_script("advanced_objects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "parent": parent_name,
            "message": format!("Objects parented to '{}'", parent_name),
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: join_objects
// ============================================================================

struct JoinObjectsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for JoinObjectsTool {
    fn name(&self) -> &str {
        "join_objects"
    }

    fn description(&self) -> &str {
        "Join multiple mesh objects into one."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": { "type": "string", "description": "Project file path" },
                "object_names": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "Names of objects to join"
                },
                "target_name": { "type": "string", "description": "Name of target object (will contain result)" }
            },
            "required": ["project", "object_names", "target_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let project = args
            .get("project")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'project' parameter".to_string())
            })?;
        let object_names = args.get("object_names").cloned().ok_or_else(|| {
            MCPError::InvalidParameters("Missing 'object_names' parameter".to_string())
        })?;
        let target_name = args
            .get("target_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'target_name' parameter".to_string())
            })?;

        let project_path = self.server.validate_project_path(project).await?;

        let script_args = json!({
            "operation": "join_objects",
            "project": project_path,
            "object_names": object_names,
            "target_name": target_name
        });

        let result = self
            .server
            .execute_script("advanced_objects.py", script_args)
            .await?;

        let response = json!({
            "success": true,
            "result_object": target_name,
            "message": format!("Objects joined into '{}'", target_name),
            "result": result
        });
        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ========== Server Creation Tests ==========

    #[test]
    fn test_server_creation() {
        let server = BlenderServer::new();
        let tools = server.tools();
        assert!(
            tools.len() >= 40,
            "Expected at least 40 tools, got {}",
            tools.len()
        );
    }

    #[test]
    fn test_server_has_job_manager() {
        let server = BlenderServer::new();
        // Server should be properly initialized with job manager and executor
        assert!(server.tools().len() > 0);
    }

    // ========== Complete Tool List Tests ==========

    #[test]
    fn test_all_core_tools_present() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        // Core project tools
        assert!(
            names.contains(&"create_blender_project"),
            "Missing create_blender_project"
        );
        assert!(names.contains(&"list_projects"), "Missing list_projects");

        // Scene manipulation tools
        assert!(
            names.contains(&"add_primitive_objects"),
            "Missing add_primitive_objects"
        );
        assert!(names.contains(&"setup_lighting"), "Missing setup_lighting");
        assert!(names.contains(&"apply_material"), "Missing apply_material");
        assert!(names.contains(&"delete_objects"), "Missing delete_objects");

        // Rendering tools
        assert!(names.contains(&"render_image"), "Missing render_image");
        assert!(
            names.contains(&"render_animation"),
            "Missing render_animation"
        );
        assert!(names.contains(&"batch_render"), "Missing batch_render");

        // Physics tools
        assert!(names.contains(&"setup_physics"), "Missing setup_physics");
        assert!(
            names.contains(&"bake_simulation"),
            "Missing bake_simulation"
        );

        // Animation tools
        assert!(
            names.contains(&"create_animation"),
            "Missing create_animation"
        );
        assert!(
            names.contains(&"create_geometry_nodes"),
            "Missing create_geometry_nodes"
        );

        // Job management tools
        assert!(names.contains(&"get_job_status"), "Missing get_job_status");
        assert!(names.contains(&"get_job_result"), "Missing get_job_result");
        assert!(names.contains(&"cancel_job"), "Missing cancel_job");

        // Import/Export tools
        assert!(names.contains(&"import_model"), "Missing import_model");
        assert!(names.contains(&"export_scene"), "Missing export_scene");

        // Camera tools
        assert!(names.contains(&"setup_camera"), "Missing setup_camera");
        assert!(
            names.contains(&"add_camera_track"),
            "Missing add_camera_track"
        );

        // Modifier and effects tools
        assert!(names.contains(&"add_modifier"), "Missing add_modifier");
        assert!(
            names.contains(&"add_particle_system"),
            "Missing add_particle_system"
        );
        assert!(
            names.contains(&"add_smoke_simulation"),
            "Missing add_smoke_simulation"
        );

        // Texture tools
        assert!(names.contains(&"add_texture"), "Missing add_texture");
        assert!(names.contains(&"add_uv_map"), "Missing add_uv_map");

        // Compositing tools
        assert!(
            names.contains(&"setup_compositor"),
            "Missing setup_compositor"
        );

        // Environment tools
        assert!(
            names.contains(&"setup_world_environment"),
            "Missing setup_world_environment"
        );

        // Scene analysis tools
        assert!(names.contains(&"analyze_scene"), "Missing analyze_scene");
        assert!(names.contains(&"optimize_scene"), "Missing optimize_scene");
        assert!(names.contains(&"create_curve"), "Missing create_curve");

        // Status tool
        assert!(names.contains(&"blender_status"), "Missing blender_status");
    }

    #[test]
    fn test_quick_effects_tools_present() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"quick_smoke"), "Missing quick_smoke");
        assert!(names.contains(&"quick_liquid"), "Missing quick_liquid");
        assert!(names.contains(&"quick_explode"), "Missing quick_explode");
        assert!(names.contains(&"quick_fur"), "Missing quick_fur");
    }

    #[test]
    fn test_advanced_object_tools_present() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"add_constraint"), "Missing add_constraint");
        assert!(
            names.contains(&"create_armature"),
            "Missing create_armature"
        );
        assert!(
            names.contains(&"create_text_object"),
            "Missing create_text_object"
        );
        assert!(
            names.contains(&"add_advanced_primitives"),
            "Missing add_advanced_primitives"
        );
        assert!(names.contains(&"parent_objects"), "Missing parent_objects");
        assert!(names.contains(&"join_objects"), "Missing join_objects");
    }

    // ========== Tool Schema Tests ==========

    #[test]
    fn test_all_tools_have_descriptions() {
        let server = BlenderServer::new();
        let tools = server.tools();

        for tool in &tools {
            assert!(
                !tool.description().is_empty(),
                "Tool '{}' has empty description",
                tool.name()
            );
        }
    }

    #[test]
    fn test_all_tools_have_valid_schemas() {
        let server = BlenderServer::new();
        let tools = server.tools();

        for tool in &tools {
            let schema = tool.schema();
            // Schema should be a valid JSON object
            assert!(
                schema.is_object(),
                "Tool '{}' schema is not an object",
                tool.name()
            );

            let obj = schema.as_object().unwrap();
            // Should have a "type" field
            assert!(
                obj.contains_key("type"),
                "Tool '{}' schema missing 'type' field",
                tool.name()
            );
        }
    }

    #[test]
    fn test_create_project_schema() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let create_project = tools
            .iter()
            .find(|t| t.name() == "create_blender_project")
            .unwrap();

        let schema = create_project.schema();
        let obj = schema.as_object().unwrap();

        // Check required fields
        assert!(obj.contains_key("properties"));
        let props = obj.get("properties").unwrap().as_object().unwrap();
        assert!(props.contains_key("name"), "Missing 'name' property");
    }

    #[test]
    fn test_render_image_schema() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let render_image = tools.iter().find(|t| t.name() == "render_image").unwrap();

        let schema = render_image.schema();
        let obj = schema.as_object().unwrap();

        assert!(obj.contains_key("properties"));
        let props = obj.get("properties").unwrap().as_object().unwrap();
        assert!(props.contains_key("project"), "Missing 'project' property");
    }

    #[test]
    fn test_quick_smoke_schema() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let quick_smoke = tools.iter().find(|t| t.name() == "quick_smoke").unwrap();

        let schema = quick_smoke.schema();
        let obj = schema.as_object().unwrap();

        assert!(obj.contains_key("properties"));
        let props = obj.get("properties").unwrap().as_object().unwrap();
        assert!(props.contains_key("project"), "Missing 'project' property");
        assert!(
            props.contains_key("object_names"),
            "Missing 'object_names' property"
        );
        assert!(props.contains_key("style"), "Missing 'style' property");
    }

    #[test]
    fn test_add_constraint_schema() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let add_constraint = tools.iter().find(|t| t.name() == "add_constraint").unwrap();

        let schema = add_constraint.schema();
        let obj = schema.as_object().unwrap();

        assert!(obj.contains_key("properties"));
        let props = obj.get("properties").unwrap().as_object().unwrap();
        assert!(props.contains_key("project"), "Missing 'project' property");
        assert!(
            props.contains_key("object_name"),
            "Missing 'object_name' property"
        );
        assert!(
            props.contains_key("constraint_type"),
            "Missing 'constraint_type' property"
        );
    }

    // ========== Tool Count Tests ==========

    #[test]
    fn test_minimum_tool_count() {
        let server = BlenderServer::new();
        let tools = server.tools();

        // We should have at least 41 tools (all Python tools + new additions)
        assert!(
            tools.len() >= 41,
            "Expected at least 41 tools, got {}",
            tools.len()
        );
    }

    #[test]
    fn test_exact_tool_count() {
        let server = BlenderServer::new();
        let tools = server.tools();

        // Current tool count should be 41
        // Update this if tools are added/removed
        assert_eq!(
            tools.len(),
            41,
            "Tool count changed. Expected 41, got {}. Update test if intentional.",
            tools.len()
        );
    }

    // ========== Tool Name Uniqueness Tests ==========

    #[test]
    fn test_no_duplicate_tool_names() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        let mut seen = std::collections::HashSet::new();
        for name in &names {
            assert!(seen.insert(*name), "Duplicate tool name found: {}", name);
        }
    }

    // ========== Tool Description Quality Tests ==========

    #[test]
    fn test_tool_descriptions_not_too_short() {
        let server = BlenderServer::new();
        let tools = server.tools();

        for tool in &tools {
            assert!(
                tool.description().len() >= 10,
                "Tool '{}' has too short description: '{}'",
                tool.name(),
                tool.description()
            );
        }
    }

    // ========== Categories Test ==========

    #[test]
    fn test_tools_cover_all_categories() {
        let server = BlenderServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        // Verify we have tools in each major category
        // Project management
        assert!(names.iter().any(|n| n.contains("project")));

        // Rendering
        assert!(names.iter().any(|n| n.contains("render")));

        // Physics
        assert!(
            names
                .iter()
                .any(|n| n.contains("physics") || n.contains("simulation"))
        );

        // Animation
        assert!(names.iter().any(|n| n.contains("animation")));

        // Materials
        assert!(names.iter().any(|n| n.contains("material")));

        // Camera
        assert!(names.iter().any(|n| n.contains("camera")));

        // Import/Export
        assert!(
            names
                .iter()
                .any(|n| n.contains("import") || n.contains("export"))
        );

        // Quick effects
        assert!(names.iter().any(|n| n.starts_with("quick_")));

        // Advanced objects
        assert!(
            names
                .iter()
                .any(|n| n.contains("armature") || n.contains("constraint"))
        );
    }
}
