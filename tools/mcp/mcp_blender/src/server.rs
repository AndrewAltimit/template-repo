//! Tool plumbing: shared context, the typed [`BlenderTool`] trait and its
//! adapter onto `mcp_core::Tool`, plus the helpers every tool uses (path
//! confinement, project locking, synchronous operations and async jobs).

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::marker::PhantomData;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::OwnedMutexGuard;
use tracing::warn;
use uuid::Uuid;

use crate::blender::{BlenderExecutor, ExecError, Invocation, Slot, wait_cancelled};
use crate::config::Config;
use crate::jobs::JobManager;
use crate::paths::{self, PathError};

/// Blender refuses names longer than 63 bytes (they are silently truncated,
/// after which lookups by the requested name fail).
pub const MAX_OBJECT_NAME: usize = 63;

/// Error returned by a tool implementation.
#[derive(Debug)]
pub enum ToolError {
    /// Bad arguments: surfaced as an MCP `InvalidParameters` error.
    Invalid(String),
    /// The operation ran and failed: surfaced as an `isError` tool result.
    Failed {
        /// What went wrong.
        message: String,
        /// Tail of Blender's output, when available.
        log_tail: Vec<String>,
    },
}

impl ToolError {
    /// Shorthand for [`ToolError::Invalid`].
    pub fn invalid(message: impl Into<String>) -> Self {
        Self::Invalid(message.into())
    }

    /// Shorthand for a failure without Blender output.
    pub fn failed(message: impl Into<String>) -> Self {
        Self::Failed {
            message: message.into(),
            log_tail: Vec::new(),
        }
    }
}

impl From<ExecError> for ToolError {
    fn from(err: ExecError) -> Self {
        match err {
            ExecError::Failed { message, log_tail } => Self::Failed { message, log_tail },
            other => Self::failed(other.to_string()),
        }
    }
}

impl From<PathError> for ToolError {
    fn from(err: PathError) -> Self {
        Self::Invalid(err.to_string())
    }
}

/// Result type of tool implementations.
pub type ToolOutput = std::result::Result<Value, ToolError>;

/// A tool with typed arguments. Implementations are registered through
/// [`ToolAdapter`], which parses arguments (missing/mistyped fields become
/// `InvalidParameters`, never panics) and renders the result.
#[async_trait]
pub trait BlenderTool: Send + Sync + 'static {
    /// Deserialized arguments.
    type Args: DeserializeOwned + Send;
    /// MCP tool name (stable, part of the public API).
    const NAME: &'static str;
    /// Tool description shown to clients.
    const DESCRIPTION: &'static str;
    /// JSON schema of the arguments.
    fn schema() -> Value;
    /// Execute the tool.
    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput;
}

/// Bridges a [`BlenderTool`] onto `mcp_core::Tool`.
pub struct ToolAdapter<T> {
    ctx: Ctx,
    _tool: PhantomData<fn() -> T>,
}

impl<T: BlenderTool> ToolAdapter<T> {
    /// Adapter bound to the shared context.
    pub fn new(ctx: Ctx) -> Self {
        Self {
            ctx,
            _tool: PhantomData,
        }
    }
}

/// Box a tool for registration.
pub fn tool<T: BlenderTool>(ctx: &Ctx) -> BoxedTool {
    Arc::new(ToolAdapter::<T>::new(ctx.clone()))
}

#[async_trait]
impl<T: BlenderTool> Tool for ToolAdapter<T> {
    fn name(&self) -> &str {
        T::NAME
    }

    fn description(&self) -> &str {
        T::DESCRIPTION
    }

    fn schema(&self) -> Value {
        T::schema()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args = if args.is_null() { json!({}) } else { args };
        let parsed: T::Args = serde_json::from_value(args)
            .map_err(|e| MCPError::InvalidParameters(format!("{}: {}", T::NAME, e)))?;
        match T::run(&self.ctx, parsed).await {
            Ok(value) => ToolResult::json(&value),
            Err(ToolError::Invalid(message)) => Err(MCPError::InvalidParameters(message)),
            Err(ToolError::Failed { message, log_tail }) => {
                warn!("{} failed: {}", T::NAME, message);
                let mut body = json!({ "success": false, "error": message });
                if !log_tail.is_empty() {
                    body["blender_log"] = json!(log_tail);
                }
                Ok(ToolResult {
                    content: vec![Content::json(&body)?],
                    is_error: true,
                })
            },
        }
    }
}

/// Per-project async mutexes so two edits of one `.blend` never interleave
/// (each edit is load -> modify -> save; interleaving would lose changes).
#[derive(Clone, Default)]
pub struct ProjectLocks(Arc<std::sync::Mutex<HashMap<PathBuf, Arc<tokio::sync::Mutex<()>>>>>);

impl ProjectLocks {
    /// Wait for exclusive access to `path`.
    pub async fn lock(&self, path: &Path) -> OwnedMutexGuard<()> {
        let mutex = {
            let mut map = self.0.lock().unwrap_or_else(|p| p.into_inner());
            map.entry(path.to_path_buf()).or_default().clone()
        };
        mutex.lock_owned().await
    }
}

/// Shared state handed to every tool.
#[derive(Clone)]
pub struct Ctx {
    /// Server configuration.
    pub config: Arc<Config>,
    /// Blender process runner.
    pub exec: BlenderExecutor,
    /// Async job registry.
    pub jobs: JobManager,
    locks: ProjectLocks,
}

/// A resolved, existing project file.
#[derive(Debug, Clone)]
pub struct Project {
    /// Absolute path of the `.blend` file.
    pub path: PathBuf,
    /// Path relative to the projects directory (what clients should send).
    pub name: String,
}

impl Ctx {
    /// Context for `config`.
    pub fn new(config: Config) -> Self {
        let config = Arc::new(config);
        Self {
            exec: BlenderExecutor::new(config.clone()),
            jobs: JobManager::new(config.job_retention),
            locks: ProjectLocks::default(),
            config,
        }
    }

    /// Resolve a client project reference (`name`, `name.blend`, `sub/name`
    /// or the full path the server reported) to an existing `.blend` file.
    pub fn project(&self, project: &str) -> std::result::Result<Project, ToolError> {
        let path = paths::resolve_under(
            &self.config.projects_dir,
            &paths::with_blend_extension(project),
        )?;
        if !path.is_file() {
            return Err(ToolError::invalid(format!(
                "Project '{}' not found in {} (use list_projects or create_blender_project)",
                project.trim(),
                self.config.projects_dir.display()
            )));
        }
        Ok(Project {
            name: self.relative_project_name(&path),
            path,
        })
    }

    fn relative_project_name(&self, path: &Path) -> String {
        path.strip_prefix(&self.config.projects_dir)
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/")
    }

    /// Resolve an existing input file inside the assets directory.
    pub fn asset(&self, field: &str, asset: &str) -> std::result::Result<PathBuf, ToolError> {
        let path = paths::resolve_under(&self.config.assets_dir, asset)
            .map_err(|e| ToolError::invalid(format!("{field}: {e}")))?;
        if !path.is_file() {
            return Err(ToolError::invalid(format!(
                "{field}: '{}' not found in the assets directory {} (copy input files there first)",
                asset.trim(),
                self.config.assets_dir.display()
            )));
        }
        Ok(path)
    }

    /// Run a script synchronously. When `project` is given the project is
    /// locked for the duration (use for every operation that saves it).
    pub async fn operation(&self, script: &str, args: Value, project: Option<&Path>) -> ToolOutput {
        let _guard = match project {
            Some(path) => Some(self.locks.lock(path).await),
            None => None,
        };
        let _permit = self.exec.acquire(Slot::Operation).await?;
        let result = self
            .exec
            .run(Invocation {
                script,
                args: &args,
                id: Uuid::new_v4(),
                timeout: self.config.operation_timeout,
                cancel: None,
                progress: None,
            })
            .await?;
        Ok(result)
    }

    /// Queue a long-running script as a background job and return its id.
    ///
    /// The job waits for a job slot (cancellable while queued), optionally
    /// locks the project (for jobs that save it, e.g. bakes), reports
    /// progress from the script's status file and records the outcome.
    /// `build_args` receives the job id so outputs can be named after it.
    pub fn start_job(
        &self,
        job_type: &str,
        script: &'static str,
        project: &Project,
        lock_project: bool,
        build_args: impl FnOnce(Uuid) -> Value,
    ) -> Uuid {
        let (id, cancel) = self.jobs.create(job_type, Some(project.name.clone()));
        let args = build_args(id);
        let ctx = self.clone();
        let project_path = project.path.clone();
        tokio::spawn(async move {
            let mut queued_cancel = Some(cancel.clone());
            let permit = tokio::select! {
                permit = ctx.exec.acquire(Slot::Job) => permit,
                _ = wait_cancelled(&mut queued_cancel) => return,
            };
            let _permit = match permit {
                Ok(p) => p,
                Err(e) => {
                    ctx.jobs.fail(id, &e.to_string());
                    return;
                },
            };
            let _guard = if lock_project {
                Some(ctx.locks.lock(&project_path).await)
            } else {
                None
            };
            if !ctx.jobs.mark_running(id) {
                return; // cancelled while waiting
            }
            let jobs = ctx.jobs.clone();
            let progress =
                move |percent: u8, message: &str| jobs.update_progress(id, percent, Some(message));
            let outcome = ctx
                .exec
                .run(Invocation {
                    script,
                    args: &args,
                    id,
                    timeout: ctx.config.job_timeout,
                    cancel: Some(cancel),
                    progress: Some(&progress),
                })
                .await;
            match outcome {
                Ok(result) => {
                    let output = result
                        .get("output_path")
                        .and_then(Value::as_str)
                        .map(str::to_string);
                    ctx.jobs.complete(id, result, output);
                },
                Err(ExecError::Cancelled) => {},
                Err(e) => {
                    ctx.jobs.fail(id, &e.to_string());
                },
            }
        });
        id
    }
}

// ---------------------------------------------------------------------------
// Validation helpers shared by the tool modules
// ---------------------------------------------------------------------------

/// Validate a Blender object/datablock name.
pub fn check_name<'a>(field: &str, name: &'a str) -> std::result::Result<&'a str, ToolError> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err(ToolError::invalid(format!("{field} must not be empty")));
    }
    if trimmed.len() > MAX_OBJECT_NAME {
        return Err(ToolError::invalid(format!(
            "{field} '{trimmed}' is longer than Blender's {MAX_OBJECT_NAME}-byte name limit"
        )));
    }
    if trimmed.contains('\0') {
        return Err(ToolError::invalid(format!("{field} contains a NUL byte")));
    }
    Ok(trimmed)
}

/// Validate a non-empty list of object names.
pub fn check_names(field: &str, names: &[String]) -> std::result::Result<(), ToolError> {
    if names.is_empty() {
        return Err(ToolError::invalid(format!(
            "{field} must contain at least one name"
        )));
    }
    if names.len() > 1000 {
        return Err(ToolError::invalid(format!(
            "{field} has more than 1000 entries"
        )));
    }
    for name in names {
        check_name(field, name)?;
    }
    Ok(())
}

/// Validate that `value` lies in `[min, max]`.
pub fn check_range<T: PartialOrd + std::fmt::Display + Copy>(
    field: &str,
    value: T,
    min: T,
    max: T,
) -> std::result::Result<T, ToolError> {
    if value < min || value > max {
        return Err(ToolError::invalid(format!(
            "{field} must be between {min} and {max}, got {value}"
        )));
    }
    Ok(value)
}

/// Validate an RGB/RGBA color (3-4 non-negative components).
pub fn check_color(field: &str, color: &[f64]) -> std::result::Result<(), ToolError> {
    if !(3..=4).contains(&color.len()) || color.iter().any(|c| !c.is_finite() || *c < 0.0) {
        return Err(ToolError::invalid(format!(
            "{field} must be [r, g, b] or [r, g, b, a] with non-negative values"
        )));
    }
    Ok(())
}

/// Validate a render resolution.
pub fn check_resolution(resolution: &[u32; 2]) -> std::result::Result<(), ToolError> {
    for (axis, value) in ["width", "height"].iter().zip(resolution) {
        check_range(&format!("resolution {axis}"), *value, 1, 16384)?;
    }
    Ok(())
}

/// Replace a string path inside a free-form settings object with its
/// validated absolute asset path.
pub fn resolve_setting_asset(
    ctx: &Ctx,
    settings: &mut serde_json::Map<String, Value>,
    key: &str,
) -> std::result::Result<(), ToolError> {
    match settings.get(key) {
        None | Some(Value::Null) => Ok(()),
        Some(Value::String(raw)) => {
            let resolved = ctx.asset(&format!("settings.{key}"), raw)?;
            settings.insert(key.to_string(), json!(resolved.to_string_lossy()));
            Ok(())
        },
        Some(_) => Err(ToolError::invalid(format!(
            "settings.{key} must be a string"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Schema helpers
// ---------------------------------------------------------------------------

/// `project` property.
pub fn project_prop() -> Value {
    json!({
        "type": "string",
        "description": "Project file name inside the projects directory (e.g. 'scene' or 'scene.blend'; the full path returned by create_blender_project also works)"
    })
}

/// A string property constrained to `values`.
pub fn enum_prop(values: &[&str], default: Option<&str>, description: &str) -> Value {
    let mut prop = json!({ "type": "string", "enum": values, "description": description });
    if let Some(default) = default {
        prop["default"] = json!(default);
    }
    prop
}

/// A 3-component vector property.
pub fn vec3_prop(description: &str, default: Option<[f64; 3]>) -> Value {
    let mut prop = json!({
        "type": "array",
        "items": { "type": "number" },
        "minItems": 3,
        "maxItems": 3,
        "description": description
    });
    if let Some(default) = default {
        prop["default"] = json!(default);
    }
    prop
}

/// An array-of-strings property.
pub fn names_prop(description: &str) -> Value {
    json!({ "type": "array", "items": { "type": "string" }, "minItems": 1, "description": description })
}

/// A color property.
pub fn color_prop(description: &str, default: &[f64]) -> Value {
    json!({
        "type": "array",
        "items": { "type": "number", "minimum": 0 },
        "minItems": 3,
        "maxItems": 4,
        "default": default,
        "description": description
    })
}

/// Blender server wiring: builds the context and the tool list.
pub struct BlenderServer {
    ctx: Ctx,
}

impl BlenderServer {
    /// Server using `config`.
    pub fn new(config: Config) -> Self {
        let problems = config.ensure_dirs();
        for problem in problems {
            warn!("Could not create working directory {}", problem);
        }
        Self {
            ctx: Ctx::new(config),
        }
    }

    /// Every tool, in registration order.
    pub fn tools(&self) -> Vec<BoxedTool> {
        crate::tools::all(&self.ctx)
    }
}
