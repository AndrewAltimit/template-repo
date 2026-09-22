//! Gaea2 MCP tool implementations.
//!
//! Every tool deserializes its arguments into a typed `*Args` struct first
//! (see [`parse_args`]), so missing or mistyped parameters become clean
//! `InvalidParameters` errors instead of silently falling back to defaults.
//! Paths supplied by clients are confined to the configured directories via
//! [`Gaea2Config::resolve_path`].

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use chrono::Utc;
use mcp_core::prelude::*;
use serde::de::DeserializeOwned;
use serde::Deserialize;
use serde_json::{json, Map, Value};
use tokio::sync::RwLock;

use crate::analysis::{analyze, optimize, recommended_resolution};
use crate::cli::{check_arg_value, Gaea2CLI, RunOptions};
use crate::config::{Gaea2Config, PathKind};
use crate::generation::{build_project, write_project, ProjectOptions};
use crate::input::{parse_connections, parse_nodes};
use crate::repair::repair_project;
use crate::schema::{
    get_default_ports, get_node_category, is_generator_node, is_valid_node_type, property_specs,
    suggest_node_type, suggest_nodes, CATEGORIES, SEED_SPEC,
};
use crate::templates::{all_templates, apply_modifications, get_template, template_names};
use crate::types::{
    AnalysisType, BuildConfig, ExecutionHistoryEntry, ExecutionResult, FileInfo, OptimizationMode,
    Workflow, VALID_RESOLUTIONS,
};
use crate::validation::{ValidateOptions, Validator};

/// Maximum execution history entries kept in memory.
const MAX_HISTORY: usize = 200;
/// Largest file `download_gaea2_project` will return.
const MAX_DOWNLOAD_BYTES: u64 = 25 * 1024 * 1024;
/// Largest project file `repair_gaea2_project` will load.
const MAX_REPAIR_BYTES: u64 = 64 * 1024 * 1024;
/// Upper bound for build timeouts.
const MAX_TIMEOUT_SECS: u64 = 4 * 60 * 60;
/// Resolutions accepted by Gaea.Swarm builds.
const RUN_RESOLUTIONS: &[u32] = &[512, 1024, 2048, 4096, 8192];

/// Gaea2 MCP Server.
pub struct Gaea2Server {
    refs: ServerRefs,
}

/// Shared state for tools.
#[derive(Clone)]
struct ServerRefs {
    config: Arc<Gaea2Config>,
    cli: Option<Arc<Gaea2CLI>>,
    execution_history: Arc<RwLock<Vec<ExecutionHistoryEntry>>>,
}

impl Gaea2Server {
    /// Create a new Gaea2 server instance.
    pub fn new(config: Gaea2Config, max_concurrent_builds: usize) -> Self {
        let cli = config
            .gaea_path
            .clone()
            .map(|p| Arc::new(Gaea2CLI::new(p, max_concurrent_builds)));
        Self {
            refs: ServerRefs {
                config: Arc::new(config),
                cli,
                execution_history: Arc::new(RwLock::new(Vec::new())),
            },
        }
    }

    /// Get the output directory.
    pub fn output_dir(&self) -> String {
        self.refs.config.output_dir.display().to_string()
    }

    /// Get the Gaea2 executable path.
    pub fn gaea_path(&self) -> Option<String> {
        self.refs
            .config
            .gaea_path
            .as_ref()
            .map(|p| p.display().to_string())
    }

    /// Get all tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let r = &self.refs;
        vec![
            Arc::new(CreateProjectTool { refs: r.clone() }),
            Arc::new(CreateFromTemplateTool { refs: r.clone() }),
            Arc::new(ValidateWorkflowTool { refs: r.clone() }),
            Arc::new(SuggestNodesTool),
            Arc::new(OptimizePropertiesTool),
            Arc::new(AnalyzeWorkflowTool),
            Arc::new(RunProjectTool { refs: r.clone() }),
            Arc::new(DownloadProjectTool { refs: r.clone() }),
            Arc::new(ListProjectsTool { refs: r.clone() }),
            Arc::new(ListTemplatesTool),
            Arc::new(AnalyzeExecutionHistoryTool { refs: r.clone() }),
            Arc::new(RepairProjectTool { refs: r.clone() }),
            Arc::new(ValidateRuntimeTool { refs: r.clone() }),
            Arc::new(ListNodesTool),
            Arc::new(StatusTool { refs: r.clone() }),
        ]
    }
}

// =============================================================================
// Helpers
// =============================================================================

/// Deserialize tool arguments into a typed struct (`null` is treated as `{}`).
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

fn invalid(msg: impl Into<String>) -> MCPError {
    MCPError::InvalidParameters(msg.into())
}

/// A structured failure result (`isError: true`) with a JSON body.
fn error_json(value: &Value) -> ToolResult {
    ToolResult::error(serde_json::to_string_pretty(value).unwrap_or_else(|_| value.to_string()))
}

fn workflow_from(nodes: &[Value], connections: Option<&[Value]>) -> Result<Workflow> {
    let nodes = parse_nodes(nodes).map_err(invalid)?;
    let connections = parse_connections(connections.unwrap_or(&[])).map_err(invalid)?;
    Ok(Workflow { nodes, connections })
}

fn require_cli(refs: &ServerRefs) -> Result<&Arc<Gaea2CLI>> {
    refs.cli.as_ref().ok_or_else(|| {
        MCPError::ToolExecutionFailed(
            "Gaea2 CLI not configured - start the server with --gaea-path or GAEA2_PATH pointing at Gaea.Swarm.exe (Windows host with Gaea2 installed)".to_string(),
        )
    })
}

fn timeout_from(secs: u64) -> Result<Duration> {
    if secs == 0 || secs > MAX_TIMEOUT_SECS {
        return Err(invalid(format!(
            "timeout must be between 1 and {MAX_TIMEOUT_SECS} seconds"
        )));
    }
    Ok(Duration::from_secs(secs))
}

/// Accept a resolution given as a number or a numeric string.
fn parse_resolution(v: &Value) -> Result<u32> {
    let r = match v {
        Value::Number(n) => n.as_u64(),
        Value::String(s) => s.trim().parse::<u64>().ok(),
        _ => None,
    };
    match r {
        Some(r) if RUN_RESOLUTIONS.contains(&(r as u32)) && r <= u64::from(u32::MAX) => {
            Ok(r as u32)
        },
        _ => Err(invalid(format!(
            "resolution must be one of {RUN_RESOLUTIONS:?}, got {v}"
        ))),
    }
}

async fn record_history(refs: &ServerRefs, project: &Path, result: &ExecutionResult) {
    let mut history = refs.execution_history.write().await;
    history.push(ExecutionHistoryEntry {
        timestamp: Utc::now().to_rfc3339(),
        project: project.display().to_string(),
        result: result.clone(),
    });
    let excess = history.len().saturating_sub(MAX_HISTORY);
    if excess > 0 {
        history.drain(..excess);
    }
}

/// Validate (optionally fix) and write a workflow as a new project file.
async fn create_project_file(
    refs: &ServerRefs,
    project_name: &str,
    workflow: Workflow,
    build_config: BuildConfig,
    description: String,
    validate: bool,
    opts: ValidateOptions,
) -> Result<ToolResult> {
    if project_name.trim().is_empty() {
        return Err(invalid("project_name must not be empty"));
    }
    build_config.validate().map_err(invalid)?;

    let (workflow, validation) = if validate {
        let result = Validator::validate_and_fix(&workflow, opts);
        if !result.valid {
            return Ok(error_json(&json!({
                "success": false,
                "error": "Workflow failed validation; no file was written",
                "errors": result.errors,
                "warnings": result.warnings,
                "fixes_applied": result.fixes_applied,
            })));
        }
        let summary = json!({
            "fixes_applied": result.fixes_applied,
            "warnings": result.warnings,
        });
        (result.workflow, Some(summary))
    } else {
        (workflow, None)
    };

    let project = build_project(
        project_name,
        &workflow,
        &build_config,
        &ProjectOptions { description },
    )
    .map_err(invalid)?;

    let output_path = refs.config.generate_output_path(project_name);
    let size = write_project(&output_path, &project)
        .await
        .map_err(MCPError::ToolExecutionFailed)?;

    let mut result = json!({
        "success": true,
        "project_name": project_name,
        "output_path": output_path.display().to_string(),
        "file_size": size,
        "node_count": workflow.nodes.len(),
        "connection_count": workflow.connections.len(),
    });
    if let Some(v) = validation {
        result["validation"] = v;
    }
    ToolResult::json(&result)
}

// =============================================================================
// JSON schema fragments
// =============================================================================

fn node_items_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "id": {"type": ["integer", "string"], "description": "Unique node id (auto-assigned if omitted)"},
            "type": {"type": "string", "description": "Gaea2 node type, e.g. Mountain, Erosion2, SatMap, Export (see list_gaea2_nodes)"},
            "name": {"type": "string"},
            "position": {
                "type": "object",
                "description": "Graph position; omit for automatic layout",
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}}
            },
            "properties": {"type": "object", "description": "Gaea2 node properties (PascalCase names, e.g. {\"Duration\": 0.15})"},
            "ports": {
                "type": "array",
                "description": "Override the default ports: [{name, type: PrimaryIn|In|PrimaryOut|Out}]",
                "items": {"type": "object"}
            },
            "modifiers": {"type": "array", "description": "Node modifiers: [{type, properties?, order?, has_ui?}]", "items": {"type": "object"}},
            "save_definition": {
                "type": "object",
                "description": "For Export nodes: {filename, format (PNG16, PNG64, EXR, RAW16, TIFF...), enabled?, disabled_profiles?}"
            },
            "node_size": {"type": "string"},
            "is_maskable": {"type": "boolean"}
        },
        "required": ["type"]
    })
}

fn connection_items_schema() -> Value {
    json!({
        "type": ["object", "array"],
        "description": "{from_node, to_node, from_port?='Out', to_port?='In'} or [from, to]",
        "properties": {
            "from_node": {"type": ["integer", "string"]},
            "to_node": {"type": ["integer", "string"]},
            "from_port": {"type": "string", "default": "Out"},
            "to_port": {"type": "string", "default": "In"}
        }
    })
}

fn build_config_schema() -> Value {
    json!({
        "type": "object",
        "description": "Optional build settings",
        "properties": {
            "resolution": {"type": "integer", "enum": VALID_RESOLUTIONS, "default": 2048},
            "bake_resolution": {"type": "integer", "enum": VALID_RESOLUTIONS},
            "tile_resolution": {"type": "integer", "enum": VALID_RESOLUTIONS, "default": 1024},
            "number_of_tiles": {"type": "integer", "minimum": 1, "maximum": 64, "default": 3},
            "edge_blending": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.25},
            "build_type": {"type": "string", "default": "Standard"},
            "color_space": {"type": "string", "default": "sRGB"}
        }
    })
}

// =============================================================================
// Tool: create_gaea2_project
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateProjectArgs {
    project_name: String,
    nodes: Vec<Value>,
    #[serde(default)]
    connections: Option<Vec<Value>>,
    #[serde(default)]
    build_config: Option<BuildConfig>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default = "yes")]
    validate: bool,
    #[serde(default = "yes")]
    auto_fix: bool,
    #[serde(default)]
    strict: bool,
}

fn yes() -> bool {
    true
}

struct CreateProjectTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for CreateProjectTool {
    fn name(&self) -> &str {
        "create_gaea2_project"
    }

    fn description(&self) -> &str {
        "Create a Gaea2 .terrain project from nodes and connections. The workflow is validated \
         (and auto-fixed by default) first; if blocking errors remain no file is written and the \
         errors are returned. Returns the path of the written file."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Name for the terrain project (also used in the file name)"},
                "nodes": {"type": "array", "items": node_items_schema()},
                "connections": {"type": "array", "items": connection_items_schema()},
                "build_config": build_config_schema(),
                "description": {"type": "string", "description": "Project description stored in metadata"},
                "validate": {"type": "boolean", "default": true, "description": "Validate before writing (recommended)"},
                "auto_fix": {"type": "boolean", "default": true, "description": "Apply automatic fixes during validation"},
                "strict": {"type": "boolean", "default": false, "description": "Treat unconnected nodes / missing Export as errors"}
            },
            "required": ["project_name", "nodes"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: CreateProjectArgs = parse_args(args)?;
        let workflow = workflow_from(&a.nodes, a.connections.as_deref())?;
        create_project_file(
            &self.refs,
            &a.project_name,
            workflow,
            a.build_config.unwrap_or_default(),
            a.description.unwrap_or_default(),
            a.validate,
            ValidateOptions {
                strict: a.strict,
                auto_fix: a.auto_fix,
            },
        )
        .await
    }
}

// =============================================================================
// Tool: create_gaea2_from_template
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateFromTemplateArgs {
    template_name: String,
    project_name: String,
    #[serde(default)]
    modifications: Option<Map<String, Value>>,
    #[serde(default)]
    build_config: Option<BuildConfig>,
    #[serde(default)]
    description: Option<String>,
}

struct CreateFromTemplateTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for CreateFromTemplateTool {
    fn name(&self) -> &str {
        "create_gaea2_from_template"
    }

    fn description(&self) -> &str {
        "Create a Gaea2 project from a pre-built template, optionally overriding node properties \
         (modifications: {\"<node name or id>\": {\"Property\": value}})."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of the template to use",
                    "enum": template_names()
                },
                "project_name": {"type": "string", "description": "Name for the output project"},
                "modifications": {
                    "type": "object",
                    "description": "Property overrides keyed by node name or id, e.g. {\"BaseTerrain\": {\"Height\": 0.9}}. A null value removes a property.",
                    "additionalProperties": {"type": "object"}
                },
                "build_config": build_config_schema(),
                "description": {"type": "string"}
            },
            "required": ["template_name", "project_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: CreateFromTemplateArgs = parse_args(args)?;
        let mut template = get_template(&a.template_name).ok_or_else(|| {
            invalid(format!(
                "Unknown template '{}'. Available: {:?}",
                a.template_name,
                template_names()
            ))
        })?;
        let applied = match &a.modifications {
            Some(m) => apply_modifications(&mut template, m).map_err(invalid)?,
            None => Vec::new(),
        };
        let description = a
            .description
            .unwrap_or_else(|| template.description.clone());
        let workflow = Workflow {
            nodes: template.nodes,
            connections: template.connections,
        };
        let mut result = create_project_file(
            &self.refs,
            &a.project_name,
            workflow,
            a.build_config.unwrap_or_default(),
            description,
            true,
            ValidateOptions::default(),
        )
        .await?;
        if !result.is_error {
            // Annotate the success payload with template details.
            if let Some(Content::Text { text }) = result.content.first_mut() {
                if let Ok(mut v) = serde_json::from_str::<Value>(text) {
                    v["template_name"] = json!(a.template_name);
                    v["modifications_applied"] = json!(applied);
                    *text = serde_json::to_string_pretty(&v).unwrap_or_default();
                }
            }
        }
        Ok(result)
    }
}

// =============================================================================
// Tool: validate_and_fix_workflow
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ValidateArgs {
    nodes: Vec<Value>,
    #[serde(default)]
    connections: Option<Vec<Value>>,
    #[serde(default)]
    strict_mode: bool,
    #[serde(default = "yes")]
    auto_fix: bool,
    #[serde(default)]
    runtime_check: bool,
    #[serde(default = "default_runtime_timeout")]
    runtime_timeout: u64,
}

fn default_runtime_timeout() -> u64 {
    60
}

struct ValidateWorkflowTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for ValidateWorkflowTool {
    fn name(&self) -> &str {
        "validate_and_fix_workflow"
    }

    fn description(&self) -> &str {
        "Validate a Gaea2 workflow (node types, ports, connections, cycles, property types and \
         ranges) and return the auto-fixed workflow. 'errors' are blocking problems that remain \
         after fixing; 'warnings' are non-blocking."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "nodes": {"type": "array", "items": node_items_schema()},
                "connections": {"type": "array", "items": connection_items_schema()},
                "strict_mode": {
                    "type": "boolean",
                    "description": "Treat completeness problems (unconnected nodes, missing Export, empty primary inputs) as errors",
                    "default": false
                },
                "auto_fix": {"type": "boolean", "default": true, "description": "Apply automatic fixes; when false, fixable problems are reported as errors"},
                "runtime_check": {
                    "type": "boolean",
                    "description": "Also build the workflow at 512px through Gaea.Swarm.exe (requires the Windows host with Gaea2)",
                    "default": false
                },
                "runtime_timeout": {"type": "integer", "default": 60, "description": "Timeout in seconds for the runtime check"}
            },
            "required": ["nodes"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: ValidateArgs = parse_args(args)?;
        let workflow = workflow_from(&a.nodes, a.connections.as_deref())?;
        let mut result = Validator::validate_and_fix(
            &workflow,
            ValidateOptions {
                strict: a.strict_mode,
                auto_fix: a.auto_fix,
            },
        );

        let mut runtime = Value::Null;
        if a.runtime_check {
            let timeout = timeout_from(a.runtime_timeout)?;
            if !result.valid {
                runtime = json!({"skipped": "workflow has blocking errors"});
            } else if let Some(cli) = &self.refs.cli {
                let r = runtime_validate_workflow(&self.refs, cli, &result.workflow, timeout).await;
                if !r.success {
                    result.valid = false;
                    result.errors.push(format!(
                        "Runtime validation failed: {}",
                        r.error.clone().unwrap_or_default()
                    ));
                }
                runtime = serde_json::to_value(&r).unwrap_or(Value::Null);
            } else {
                result.valid = false;
                result.errors.push(
                    "Runtime check requested but the Gaea2 CLI is not configured on this server"
                        .to_string(),
                );
            }
        }

        let mut out =
            serde_json::to_value(&result).map_err(|e| MCPError::Internal(e.to_string()))?;
        if !runtime.is_null() {
            out["runtime_check"] = runtime;
        }
        ToolResult::json(&out)
    }
}

/// Generate a temporary project, build it at 512px, and clean up.
async fn runtime_validate_workflow(
    refs: &ServerRefs,
    cli: &Gaea2CLI,
    workflow: &Workflow,
    timeout: Duration,
) -> ExecutionResult {
    let work = refs
        .config
        .output_dir
        .join(".runtime_validation")
        .join(uuid::Uuid::new_v4().simple().to_string());
    let project_path = work.join("validation.terrain");
    let project = match build_project(
        "runtime_validation",
        workflow,
        &BuildConfig::default(),
        &ProjectOptions::default(),
    ) {
        Ok(p) => p,
        Err(e) => return ExecutionResult::failure(e),
    };
    if let Err(e) = write_project(&project_path, &project).await {
        return ExecutionResult::failure(e);
    }
    let opts = RunOptions {
        resolution: 512,
        build_path: work.join("build"),
        timeout,
        ..Default::default()
    };
    let result = cli.run_project(&project_path, &opts).await;
    let _ = tokio::fs::remove_dir_all(&work).await;
    result
}

// =============================================================================
// Tool: suggest_gaea2_nodes
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct SuggestArgs {
    current_nodes: Vec<String>,
    #[serde(default)]
    context: Option<String>,
}

struct SuggestNodesTool;

#[async_trait]
impl Tool for SuggestNodesTool {
    fn name(&self) -> &str {
        "suggest_gaea2_nodes"
    }

    fn description(&self) -> &str {
        "Suggest valid Gaea2 nodes to add next, based on the node types already in the workflow, \
         common chains from reference projects, and an optional terrain description."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "current_nodes": {
                    "type": "array",
                    "description": "Node types currently in the workflow, in the order they were added",
                    "items": {"type": "string"}
                },
                "context": {
                    "type": "string",
                    "description": "Description of the terrain being created (e.g. 'volcanic island', 'desert canyon')"
                }
            },
            "required": ["current_nodes"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: SuggestArgs = parse_args(args)?;
        let unknown: Vec<Value> = a
            .current_nodes
            .iter()
            .filter(|n| !is_valid_node_type(n))
            .map(|n| json!({"type": n, "did_you_mean": suggest_node_type(n)}))
            .collect();
        let details = suggest_nodes(&a.current_nodes, a.context.as_deref());
        let names: Vec<&str> = details.iter().map(|s| s.node).collect();
        let mut result = json!({
            "suggestions": names,
            "details": details,
            "current_node_count": a.current_nodes.len()
        });
        if !unknown.is_empty() {
            result["unknown_node_types"] = json!(unknown);
        }
        ToolResult::json(&result)
    }
}

// =============================================================================
// Tool: optimize_gaea2_properties
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct OptimizeArgs {
    nodes: Vec<Value>,
    #[serde(default)]
    mode: OptimizationMode,
}

struct OptimizePropertiesTool;

#[async_trait]
impl Tool for OptimizePropertiesTool {
    fn name(&self) -> &str {
        "optimize_gaea2_properties"
    }

    fn description(&self) -> &str {
        "Tune the build-cost-driving properties (erosion/snow durations, thermal/flow iterations) \
         for fast previews (performance), final renders (quality), or fill in sensible defaults \
         (balanced). Returns the modified nodes and every change made."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "nodes": {"type": "array", "items": node_items_schema()},
                "mode": {
                    "type": "string",
                    "description": "performance: lower expensive values; quality: raise them; balanced: only fill missing values",
                    "enum": ["performance", "quality", "balanced"],
                    "default": "balanced"
                }
            },
            "required": ["nodes"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: OptimizeArgs = parse_args(args)?;
        let mut nodes = parse_nodes(&a.nodes).map_err(invalid)?;
        let changes = optimize(&mut nodes, a.mode);
        let summary: Vec<String> = changes
            .iter()
            .map(|c| {
                format!(
                    "{}: {} {} -> {} ({})",
                    c.node_name,
                    c.property,
                    c.old
                        .as_ref()
                        .map_or("unset".to_string(), |v| v.to_string()),
                    c.new,
                    c.reason
                )
            })
            .collect();
        ToolResult::json(&json!({
            "success": true,
            "mode": a.mode,
            "optimizations_applied": summary,
            "changes": changes,
            "recommended_build_resolution": recommended_resolution(a.mode),
            "optimized_nodes": nodes
        }))
    }
}

// =============================================================================
// Tool: analyze_workflow_patterns
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AnalyzeArgs {
    nodes: Vec<Value>,
    #[serde(default)]
    connections: Option<Vec<Value>>,
    #[serde(default)]
    analysis_type: AnalysisType,
    #[serde(default)]
    workflow_type: Option<String>,
}

struct AnalyzeWorkflowTool;

#[async_trait]
impl Tool for AnalyzeWorkflowTool {
    fn name(&self) -> &str {
        "analyze_workflow_patterns"
    }

    fn description(&self) -> &str {
        "Analyze a workflow: known node chains from reference projects (patterns), relative \
         build cost and heavy nodes (performance), structural/quality issues such as dead ends \
         or a missing Export (quality), plus terrain-type specific suggestions."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "nodes": {"type": "array", "items": node_items_schema()},
                "connections": {"type": "array", "items": connection_items_schema()},
                "analysis_type": {
                    "type": "string",
                    "enum": ["patterns", "performance", "quality", "all"],
                    "default": "all"
                },
                "workflow_type": {
                    "type": "string",
                    "description": "Expected terrain type for context-specific suggestions",
                    "enum": ["mountain", "alpine", "volcanic", "canyon", "coastal", "arctic", "desert", "river", "general"]
                }
            },
            "required": ["nodes"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: AnalyzeArgs = parse_args(args)?;
        let workflow = workflow_from(&a.nodes, a.connections.as_deref())?;
        let report = analyze(
            &workflow,
            a.analysis_type,
            a.workflow_type.as_deref().unwrap_or("general"),
        );
        ToolResult::json(&report)
    }
}

// =============================================================================
// Tool: run_gaea2_project
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RunArgs {
    project_path: String,
    #[serde(default)]
    resolution: Option<Value>,
    #[serde(default)]
    build_path: Option<String>,
    #[serde(default)]
    profile: Option<String>,
    #[serde(default)]
    seed: Option<u64>,
    #[serde(default)]
    region: Option<String>,
    #[serde(default)]
    target_node: Option<String>,
    #[serde(default)]
    variables: Option<Map<String, Value>>,
    #[serde(default)]
    ignore_cache: bool,
    #[serde(default)]
    verbose: bool,
    #[serde(default = "default_run_timeout")]
    timeout: u64,
}

fn default_run_timeout() -> u64 {
    300
}

struct RunProjectTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for RunProjectTool {
    fn name(&self) -> &str {
        "run_gaea2_project"
    }

    fn description(&self) -> &str {
        "Build a .terrain project with Gaea.Swarm.exe and list the generated files (requires the \
         Windows host with Gaea2; the process is killed if it exceeds the timeout)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to the .terrain file (relative paths resolve against the output directory)"},
                "resolution": {
                    "type": ["string", "integer"],
                    "description": "Build resolution",
                    "enum": ["512", "1024", "2048", "4096", "8192", 512, 1024, 2048, 4096, 8192],
                    "default": "1024"
                },
                "build_path": {"type": "string", "description": "Output directory (default: output_<project> next to the project)"},
                "profile": {"type": "string", "description": "Build profile name"},
                "seed": {"type": "integer", "minimum": 0, "description": "Mutation seed for variations"},
                "region": {"type": "string", "description": "Region to build (for tiled builds)"},
                "target_node": {"type": "string", "description": "Specific node to build (by ID or name)"},
                "variables": {
                    "type": "object",
                    "description": "Automation variable overrides; values must be strings, numbers or booleans",
                    "additionalProperties": {"type": ["string", "number", "boolean"]}
                },
                "ignore_cache": {"type": "boolean", "default": false},
                "verbose": {"type": "boolean", "default": false},
                "timeout": {"type": "integer", "description": "Maximum build time in seconds", "default": 300, "minimum": 1, "maximum": MAX_TIMEOUT_SECS}
            },
            "required": ["project_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let cli = require_cli(&self.refs)?;
        let a: RunArgs = parse_args(args)?;
        let config = &self.refs.config;

        let project = config
            .resolve_path(&a.project_path, PathKind::ExistingFile)
            .map_err(invalid)?;
        if !project
            .extension()
            .is_some_and(|e| e.eq_ignore_ascii_case("terrain"))
        {
            return Err(invalid("project_path must point to a .terrain file"));
        }
        let resolution = match &a.resolution {
            None | Some(Value::Null) => 1024,
            Some(v) => parse_resolution(v)?,
        };
        let build_path = match &a.build_path {
            Some(p) => config.resolve_path(p, PathKind::NewDir).map_err(invalid)?,
            None => default_build_dir(&project),
        };
        for (label, value) in [
            ("profile", &a.profile),
            ("region", &a.region),
            ("target_node", &a.target_node),
        ] {
            if let Some(v) = value {
                check_arg_value(label, v).map_err(invalid)?;
            }
        }
        let mut variables = BTreeMap::new();
        for (k, v) in a.variables.unwrap_or_default() {
            check_arg_value("variable name", &k).map_err(invalid)?;
            if k.contains(':') {
                return Err(invalid(format!("variable name '{k}' must not contain ':'")));
            }
            let value = match v {
                Value::String(s) => s,
                Value::Number(n) => n.to_string(),
                Value::Bool(b) => b.to_string(),
                other => {
                    return Err(invalid(format!(
                        "variable '{k}' must be a string, number or boolean, got {other}"
                    )))
                },
            };
            if value.chars().any(char::is_control) {
                return Err(invalid(format!(
                    "variable '{k}' contains control characters"
                )));
            }
            variables.insert(k, value);
        }

        let opts = RunOptions {
            resolution,
            build_path,
            profile: a.profile,
            region: a.region,
            seed: a.seed,
            target_node: a.target_node,
            variables,
            ignore_cache: a.ignore_cache,
            verbose: a.verbose,
            timeout: timeout_from(a.timeout)?,
        };
        let result = cli.run_project(&project, &opts).await;
        record_history(&self.refs, &project, &result).await;
        ToolResult::json(&result)
    }
}

fn default_build_dir(project: &Path) -> PathBuf {
    let stem = project
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| "project".to_string());
    project
        .parent()
        .unwrap_or(Path::new("."))
        .join(format!("output_{stem}"))
}

// =============================================================================
// Tool: download_gaea2_project
// =============================================================================

#[derive(Deserialize, Default, Clone, Copy, PartialEq)]
#[serde(rename_all = "lowercase")]
enum Encoding {
    #[default]
    Base64,
    Raw,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct DownloadArgs {
    project_path: String,
    #[serde(default)]
    encoding: Encoding,
}

struct DownloadProjectTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for DownloadProjectTool {
    fn name(&self) -> &str {
        "download_gaea2_project"
    }

    fn description(&self) -> &str {
        "Return the contents of a project (or build output) file from the server's output \
         directory, base64-encoded or as raw text. Limited to files under the allowed directories \
         and 25 MB."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to the file (relative paths resolve against the output directory)"},
                "encoding": {
                    "type": "string",
                    "description": "raw returns UTF-8 text (fails for binary files)",
                    "enum": ["base64", "raw"],
                    "default": "base64"
                }
            },
            "required": ["project_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: DownloadArgs = parse_args(args)?;
        let path = self
            .refs
            .config
            .resolve_path(&a.project_path, PathKind::ExistingFile)
            .map_err(invalid)?;
        let meta = tokio::fs::metadata(&path)
            .await
            .map_err(|e| MCPError::ToolExecutionFailed(format!("Failed to stat file: {e}")))?;
        if meta.len() > MAX_DOWNLOAD_BYTES {
            return Err(invalid(format!(
                "file is {} bytes; the download limit is {MAX_DOWNLOAD_BYTES} bytes",
                meta.len()
            )));
        }
        let content = tokio::fs::read(&path)
            .await
            .map_err(|e| MCPError::ToolExecutionFailed(format!("Failed to read file: {e}")))?;
        let filename = path.file_name().map(|n| n.to_string_lossy().to_string());

        let result = match a.encoding {
            Encoding::Raw => {
                let text = String::from_utf8(content)
                    .map_err(|_| invalid("file is not valid UTF-8; use encoding=base64"))?;
                json!({
                    "success": true,
                    "filename": filename,
                    "path": path.display().to_string(),
                    "size": text.len(),
                    "encoding": "raw",
                    "content": text
                })
            },
            Encoding::Base64 => {
                let encoded =
                    base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &content);
                json!({
                    "success": true,
                    "filename": filename,
                    "path": path.display().to_string(),
                    "size": content.len(),
                    "encoding": "base64",
                    "content_base64": encoded
                })
            },
        };
        ToolResult::json(&result)
    }
}

// =============================================================================
// Tool: list_gaea2_projects
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ListProjectsArgs {
    #[serde(default)]
    directory: Option<String>,
}

struct ListProjectsTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for ListProjectsTool {
    fn name(&self) -> &str {
        "list_gaea2_projects"
    }

    fn description(&self) -> &str {
        "List .terrain project files (newest first) in the output directory or an allowed sub-directory"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to list (defaults to the output directory; must be inside the allowed directories)"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: ListProjectsArgs = parse_args(args)?;
        let directory = match &a.directory {
            Some(d) => self
                .refs
                .config
                .resolve_path(d, PathKind::ExistingDir)
                .map_err(invalid)?,
            None => self.refs.config.output_dir.clone(),
        };

        let mut entries = tokio::fs::read_dir(&directory).await.map_err(|e| {
            MCPError::ToolExecutionFailed(format!("Failed to read {}: {e}", directory.display()))
        })?;
        let mut files = Vec::new();
        while let Ok(Some(entry)) = entries.next_entry().await {
            let path = entry.path();
            let is_terrain = path
                .extension()
                .is_some_and(|e| e.eq_ignore_ascii_case("terrain"));
            if !is_terrain {
                continue;
            }
            let Ok(metadata) = entry.metadata().await else {
                continue;
            };
            if !metadata.is_file() {
                continue;
            }
            let modified = metadata
                .modified()
                .ok()
                .map(|t| chrono::DateTime::<Utc>::from(t).to_rfc3339())
                .unwrap_or_default();
            files.push(FileInfo {
                filename: entry.file_name().to_string_lossy().to_string(),
                path: path.display().to_string(),
                size: metadata.len(),
                modified,
            });
        }
        files.sort_by(|a, b| b.modified.cmp(&a.modified));

        ToolResult::json(&json!({
            "directory": directory.display().to_string(),
            "count": files.len(),
            "files": files
        }))
    }
}

// =============================================================================
// Tool: list_gaea2_templates
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ListTemplatesArgs {
    #[serde(default)]
    include_workflow: bool,
}

struct ListTemplatesTool;

#[async_trait]
impl Tool for ListTemplatesTool {
    fn name(&self) -> &str {
        "list_gaea2_templates"
    }

    fn description(&self) -> &str {
        "List the pre-built Gaea2 templates. With include_workflow=true the full nodes and \
         connections are returned, ready to edit and pass to create_gaea2_project."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "include_workflow": {"type": "boolean", "default": false, "description": "Include each template's nodes and connections"}
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: ListTemplatesArgs = parse_args(args)?;
        let templates: Vec<Value> = all_templates()
            .iter()
            .map(|t| {
                let mut v = json!({
                    "name": t.name,
                    "description": t.description,
                    "node_count": t.nodes.len(),
                    "connection_count": t.connections.len(),
                    "node_types": t.nodes.iter().map(|n| n.node_type.as_str()).collect::<Vec<_>>()
                });
                if a.include_workflow {
                    v["nodes"] = json!(t.nodes);
                    v["connections"] = json!(t.connections);
                }
                v
            })
            .collect();
        ToolResult::json(&json!({"count": templates.len(), "templates": templates}))
    }
}

// =============================================================================
// Tool: analyze_execution_history
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct HistoryArgs {
    #[serde(default = "default_limit")]
    limit: usize,
    #[serde(default)]
    failures_only: bool,
}

fn default_limit() -> usize {
    10
}

struct AnalyzeExecutionHistoryTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for AnalyzeExecutionHistoryTool {
    fn name(&self) -> &str {
        "analyze_execution_history"
    }

    fn description(&self) -> &str {
        "Summarize recent run_gaea2_project builds (success rate, timing, timeouts) for debugging. \
         History is in-memory and keeps the last 200 builds."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of entries to return", "default": 10, "minimum": 1, "maximum": MAX_HISTORY},
                "failures_only": {"type": "boolean", "default": false}
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: HistoryArgs = parse_args(args)?;
        let limit = a.limit.clamp(1, MAX_HISTORY);
        let history = self.refs.execution_history.read().await;

        let total = history.len();
        let successes = history.iter().filter(|e| e.result.success).count();
        let timeouts = history.iter().filter(|e| e.result.timed_out).count();
        let times: Vec<f64> = history
            .iter()
            .filter(|e| e.result.success)
            .filter_map(|e| e.result.execution_time)
            .collect();
        let avg_time = if times.is_empty() {
            None
        } else {
            Some(times.iter().sum::<f64>() / times.len() as f64)
        };
        let recent: Vec<&ExecutionHistoryEntry> = history
            .iter()
            .rev()
            .filter(|e| !a.failures_only || !e.result.success)
            .take(limit)
            .collect();

        ToolResult::json(&json!({
            "total_count": total,
            "success_count": successes,
            "failure_count": total - successes,
            "timeout_count": timeouts,
            "success_rate": if total == 0 { Value::Null } else { json!(successes as f64 / total as f64) },
            "average_successful_execution_time": avg_time,
            "recent_executions": recent
        }))
    }
}

// =============================================================================
// Tool: repair_gaea2_project
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RepairArgs {
    project_path: String,
    #[serde(default = "yes")]
    create_backup: bool,
    #[serde(default)]
    dry_run: bool,
}

struct RepairProjectTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for RepairProjectTool {
    fn name(&self) -> &str {
        "repair_gaea2_project"
    }

    fn description(&self) -> &str {
        "Analyze a .terrain file and repair structural problems in place: invalid or dangling \
         connection records, mismatched node keys/ids, misspelled node types, duplicate $id \
         values and broken parent references. Unfixable problems (cycles, unknown types) are \
         reported. Use dry_run=true to only analyze. The file is only rewritten when repairs \
         were made."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to the .terrain file (relative paths resolve against the output directory)"},
                "create_backup": {"type": "boolean", "description": "Write a timestamped backup before modifying the file", "default": true},
                "dry_run": {"type": "boolean", "description": "Only report problems; do not modify the file", "default": false}
            },
            "required": ["project_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: RepairArgs = parse_args(args)?;
        let path = self
            .refs
            .config
            .resolve_path(&a.project_path, PathKind::ExistingFile)
            .map_err(invalid)?;
        let meta = tokio::fs::metadata(&path)
            .await
            .map_err(|e| MCPError::ToolExecutionFailed(format!("Failed to stat file: {e}")))?;
        if meta.len() > MAX_REPAIR_BYTES {
            return Err(invalid(format!(
                "file is {} bytes; the repair limit is {MAX_REPAIR_BYTES} bytes",
                meta.len()
            )));
        }
        let content = tokio::fs::read_to_string(&path)
            .await
            .map_err(|e| MCPError::ToolExecutionFailed(format!("Failed to read file: {e}")))?;
        // Tolerate a UTF-8 BOM, which some Windows tools add.
        let content = content.trim_start_matches('\u{feff}');
        let mut project: Value = serde_json::from_str(content).map_err(|e| {
            invalid(format!(
                "{} is not valid JSON ({e}); it cannot be repaired automatically",
                path.display()
            ))
        })?;

        let report = repair_project(&mut project).map_err(invalid)?;
        let changed = !report.repairs_applied.is_empty();

        let mut backup_path = None;
        let written = changed && !a.dry_run;
        if written {
            if a.create_backup {
                let backup = path.with_extension(format!(
                    "terrain.{}.bak",
                    Utc::now().format("%Y%m%d_%H%M%S")
                ));
                tokio::fs::copy(&path, &backup).await.map_err(|e| {
                    MCPError::ToolExecutionFailed(format!("Failed to create backup: {e}"))
                })?;
                backup_path = Some(backup.display().to_string());
            }
            write_project(&path, &project)
                .await
                .map_err(MCPError::ToolExecutionFailed)?;
        }

        ToolResult::json(&json!({
            "success": report.unresolved.is_empty(),
            "project_path": path.display().to_string(),
            "dry_run": a.dry_run,
            "modified": written,
            "backup_path": backup_path,
            "issues_found": report.issues_found,
            "repairs_applied": report.repairs_applied,
            "unresolved": report.unresolved,
            "node_count": report.node_count,
            "connection_count": report.connection_count
        }))
    }
}

// =============================================================================
// Tool: validate_gaea2_runtime
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RuntimeArgs {
    project_path: String,
    #[serde(default = "default_validate_timeout")]
    timeout: u64,
}

fn default_validate_timeout() -> u64 {
    30
}

struct ValidateRuntimeTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for ValidateRuntimeTool {
    fn name(&self) -> &str {
        "validate_gaea2_runtime"
    }

    fn description(&self) -> &str {
        "Validate a .terrain file by building it at 512px with Gaea.Swarm.exe into a temporary \
         directory (removed afterwards). Requires the Windows host with Gaea2."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to the .terrain file to validate"},
                "timeout": {"type": "integer", "description": "Maximum time to wait for validation in seconds", "default": 30, "minimum": 1, "maximum": MAX_TIMEOUT_SECS}
            },
            "required": ["project_path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let cli = require_cli(&self.refs)?;
        let a: RuntimeArgs = parse_args(args)?;
        let path = self
            .refs
            .config
            .resolve_path(&a.project_path, PathKind::ExistingFile)
            .map_err(invalid)?;
        let work = self
            .refs
            .config
            .output_dir
            .join(".runtime_validation")
            .join(uuid::Uuid::new_v4().simple().to_string());
        let opts = RunOptions {
            resolution: 512,
            build_path: work.clone(),
            timeout: timeout_from(a.timeout)?,
            ..Default::default()
        };
        let result = cli.run_project(&path, &opts).await;
        let _ = tokio::fs::remove_dir_all(&work).await;
        record_history(&self.refs, &path, &result).await;

        ToolResult::json(&json!({
            "success": result.success,
            "project_path": path.display().to_string(),
            "validation_type": "runtime",
            "execution_time": result.execution_time,
            "timed_out": result.timed_out,
            "exit_code": result.exit_code,
            "error": result.error,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "output_file_count": result.file_count
        }))
    }
}

// =============================================================================
// Tool: list_gaea2_nodes (new)
// =============================================================================

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ListNodesArgs {
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    node_type: Option<String>,
}

struct ListNodesTool;

#[async_trait]
impl Tool for ListNodesTool {
    fn name(&self) -> &str {
        "list_gaea2_nodes"
    }

    fn description(&self) -> &str {
        "List valid Gaea2 node types by category, or describe one node type: its category, \
         default input/output ports, and known properties with types, ranges and options."
    }

    fn schema(&self) -> Value {
        let cats: Vec<&str> = CATEGORIES.iter().map(|(c, _)| *c).collect();
        json!({
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Only list this category", "enum": cats},
                "node_type": {"type": "string", "description": "Describe a single node type in detail"}
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a: ListNodesArgs = parse_args(args)?;
        if let Some(t) = a.node_type {
            if !is_valid_node_type(&t) {
                return Err(invalid(format!(
                    "'{t}' is not a Gaea2 node type{}",
                    suggest_node_type(&t)
                        .map(|s| format!(" (did you mean '{s}'?)"))
                        .unwrap_or_default()
                )));
            }
            let ports = get_default_ports(&t);
            let port_list = |dir: crate::schema::PortDirection| -> Vec<Value> {
                ports
                    .iter()
                    .filter(|(_, ty)| crate::schema::port_direction(ty) == Some(dir))
                    .map(|(n, ty)| json!({"name": n, "type": ty}))
                    .collect()
            };
            let mut props: Vec<Value> = property_specs(&t)
                .unwrap_or_default()
                .iter()
                .map(|s| json!(s))
                .collect();
            if is_generator_node(&t) {
                props.push(json!(SEED_SPEC));
            }
            return ToolResult::json(&json!({
                "node_type": t,
                "category": get_node_category(&t),
                "is_generator": is_generator_node(&t),
                "inputs": port_list(crate::schema::PortDirection::Input),
                "outputs": port_list(crate::schema::PortDirection::Output),
                "known_properties": props,
                "property_schema_known": property_specs(&t).is_some()
            }));
        }

        let mut categories = serde_json::Map::new();
        for (name, nodes) in CATEGORIES {
            if let Some(c) = &a.category {
                if !c.eq_ignore_ascii_case(name) {
                    continue;
                }
            }
            categories.insert((*name).to_string(), json!(nodes));
        }
        if categories.is_empty() {
            return Err(invalid(format!(
                "unknown category {:?}; valid: {:?}",
                a.category,
                CATEGORIES.iter().map(|(c, _)| *c).collect::<Vec<_>>()
            )));
        }
        let total: usize = categories
            .values()
            .map(|v| v.as_array().map_or(0, Vec::len))
            .sum();
        ToolResult::json(&json!({"total": total, "categories": categories}))
    }
}

// =============================================================================
// Tool: get_gaea2_status (new)
// =============================================================================

struct StatusTool {
    refs: ServerRefs,
}

#[async_trait]
impl Tool for StatusTool {
    fn name(&self) -> &str {
        "get_gaea2_status"
    }

    fn description(&self) -> &str {
        "Report server capabilities: whether Gaea.Swarm CLI automation is available, the output \
         and allowed directories, and template/node counts."
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let c = &self.refs.config;
        let history = self.refs.execution_history.read().await.len();
        ToolResult::json(&json!({
            "server_version": env!("CARGO_PKG_VERSION"),
            "gaea_file_version": crate::generation::GAEA_VERSION,
            "cli_available": c.has_cli(),
            "gaea_path": c.gaea_path.as_ref().map(|p| p.display().to_string()),
            "output_dir": c.output_dir.display().to_string(),
            "allowed_dirs": c.allowed_roots().iter().map(|p| p.display().to_string()).collect::<Vec<_>>(),
            "template_count": all_templates().len(),
            "node_type_count": crate::schema::VALID_NODE_TYPES.len(),
            "executions_recorded": history
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn server(dir: &Path) -> Gaea2Server {
        Gaea2Server::new(
            Gaea2Config::new(None, dir.to_string_lossy().to_string(), None),
            1,
        )
    }

    fn tool(s: &Gaea2Server, name: &str) -> BoxedTool {
        s.tools().into_iter().find(|t| t.name() == name).unwrap()
    }

    fn body(r: &ToolResult) -> Value {
        match &r.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn tool_names_are_stable_and_unique() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let names: Vec<String> = s.tools().iter().map(|t| t.name().to_string()).collect();
        for expected in [
            "create_gaea2_project",
            "create_gaea2_from_template",
            "validate_and_fix_workflow",
            "suggest_gaea2_nodes",
            "optimize_gaea2_properties",
            "analyze_workflow_patterns",
            "run_gaea2_project",
            "download_gaea2_project",
            "list_gaea2_projects",
            "list_gaea2_templates",
            "analyze_execution_history",
            "repair_gaea2_project",
            "validate_gaea2_runtime",
            "list_gaea2_nodes",
            "get_gaea2_status",
        ] {
            assert!(names.iter().any(|n| n == expected), "missing {expected}");
        }
        let unique: std::collections::HashSet<_> = names.iter().collect();
        assert_eq!(unique.len(), names.len());
        for t in s.tools() {
            assert_eq!(t.schema()["type"], "object", "{}", t.name());
        }
    }

    #[tokio::test]
    async fn create_project_writes_valid_file() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let r = tool(&s, "create_gaea2_project")
            .execute(json!({
                "project_name": "../my terrain",
                "nodes": [
                    {"id": "1", "type": "mountain"},
                    {"id": 2, "type": "Erosion2", "properties": {"Duration": 9}},
                    {"id": 3, "type": "Export", "save_definition": {"filename": "h", "format": "PNG16"}}
                ],
                "connections": [[1, 2], {"from": 2, "to": 3}]
            }))
            .await
            .unwrap();
        assert!(!r.is_error);
        let b = body(&r);
        let path = PathBuf::from(b["output_path"].as_str().unwrap());
        assert!(path.starts_with(
            std::fs::canonicalize(dir.path())
                .map(crate::config::simplify)
                .unwrap()
        ));
        assert!(!path.to_string_lossy().contains(".."));
        assert!(b["validation"]["fixes_applied"].as_array().unwrap().len() >= 2);
        let written: Value =
            serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        let nodes = crate::generation::nodes_of(&written).unwrap();
        assert_eq!(
            nodes["1"]["$type"],
            "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes"
        );
        assert_eq!(nodes["2"]["Duration"], 2.0);
    }

    #[tokio::test]
    async fn create_project_refuses_invalid_workflow() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let r = tool(&s, "create_gaea2_project")
            .execute(json!({
                "project_name": "bad",
                "nodes": [{"id": 1, "type": "Mountain"}, {"id": 2, "type": "Blur"}],
                "connections": [{"from_node": 1, "to_node": 2, "to_port": "Nope"}]
            }))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(!body(&r)["errors"].as_array().unwrap().is_empty());
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 0);
    }

    #[tokio::test]
    async fn typed_args_reject_bad_input() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let t = tool(&s, "create_gaea2_project");
        assert!(matches!(
            t.execute(json!({"nodes": []})).await,
            Err(MCPError::InvalidParameters(_))
        ));
        assert!(t
            .execute(json!({"project_name": "x", "nodes": "Mountain"}))
            .await
            .is_err());
        let o = tool(&s, "optimize_gaea2_properties");
        assert!(o
            .execute(json!({"nodes": [], "mode": "turbo"}))
            .await
            .is_err());
    }

    #[tokio::test]
    async fn template_creation_with_modifications() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let t = tool(&s, "create_gaea2_from_template");
        let r = t
            .execute(json!({
                "template_name": "basic_terrain",
                "project_name": "tpl",
                "modifications": {"BaseTerrain": {"Height": 0.95}}
            }))
            .await
            .unwrap();
        assert!(!r.is_error);
        let b = body(&r);
        assert_eq!(b["template_name"], "basic_terrain");
        let written: Value = serde_json::from_str(
            &std::fs::read_to_string(b["output_path"].as_str().unwrap()).unwrap(),
        )
        .unwrap();
        let nodes = crate::generation::nodes_of(&written).unwrap();
        assert_eq!(nodes["100"]["Height"], 0.95);
        assert_eq!(nodes["102"]["SaveDefinition"]["Filename"], "heightmap");

        assert!(t
            .execute(json!({"template_name": "nope", "project_name": "x"}))
            .await
            .is_err());
    }

    #[tokio::test]
    async fn path_sandbox_is_enforced() {
        let root = tempfile::tempdir().unwrap();
        let out = root.path().join("out");
        let s = server(&out);
        std::fs::write(root.path().join("secret.txt"), "top secret").unwrap();
        let secret = root.path().join("secret.txt").to_string_lossy().to_string();
        for (name, args) in [
            ("download_gaea2_project", json!({"project_path": secret})),
            ("repair_gaea2_project", json!({"project_path": secret})),
            (
                "list_gaea2_projects",
                json!({"directory": root.path().to_string_lossy()}),
            ),
            (
                "download_gaea2_project",
                json!({"project_path": "../secret.txt"}),
            ),
        ] {
            let r = tool(&s, name).execute(args).await;
            assert!(r.is_err(), "{name} escaped the sandbox");
        }
    }

    #[tokio::test]
    async fn download_list_and_repair_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let r = tool(&s, "create_gaea2_from_template")
            .execute(json!({"template_name": "river_valley", "project_name": "rv"}))
            .await
            .unwrap();
        let path = body(&r)["output_path"].as_str().unwrap().to_string();
        let fname = PathBuf::from(&path)
            .file_name()
            .unwrap()
            .to_string_lossy()
            .to_string();

        let list = body(
            &tool(&s, "list_gaea2_projects")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(list["count"], 1);

        let dl = body(
            &tool(&s, "download_gaea2_project")
                .execute(json!({"project_path": fname, "encoding": "raw"}))
                .await
                .unwrap(),
        );
        assert!(dl["content"].as_str().unwrap().contains("QuadSpinner"));

        // A clean file is not rewritten.
        let rep = body(
            &tool(&s, "repair_gaea2_project")
                .execute(json!({"project_path": path}))
                .await
                .unwrap(),
        );
        assert_eq!(rep["modified"], false);
        assert_eq!(rep["success"], true);

        // Corrupt a record and repair it.
        let mut v: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        let ports = v["Assets"]["$values"][0]["Terrain"]["Nodes"]["101"]["Ports"]["$values"]
            .as_array_mut()
            .unwrap();
        let input = ports.iter_mut().find(|p| p["Name"] == "In").unwrap();
        input["Record"]["From"] = json!(4242);
        std::fs::write(&path, serde_json::to_string(&v).unwrap()).unwrap();

        let dry = body(
            &tool(&s, "repair_gaea2_project")
                .execute(json!({"project_path": path, "dry_run": true}))
                .await
                .unwrap(),
        );
        assert_eq!(dry["modified"], false);
        assert_eq!(dry["repairs_applied"].as_array().unwrap().len(), 1);

        let rep = body(
            &tool(&s, "repair_gaea2_project")
                .execute(json!({"project_path": path}))
                .await
                .unwrap(),
        );
        assert_eq!(rep["modified"], true);
        assert!(PathBuf::from(rep["backup_path"].as_str().unwrap()).exists());
        let again = body(
            &tool(&s, "repair_gaea2_project")
                .execute(json!({"project_path": path, "dry_run": true}))
                .await
                .unwrap(),
        );
        assert!(again["issues_found"].as_array().unwrap().is_empty());
    }

    #[tokio::test]
    async fn cli_tools_fail_cleanly_without_gaea() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        for name in ["run_gaea2_project", "validate_gaea2_runtime"] {
            let r = tool(&s, name)
                .execute(json!({"project_path": "x.terrain"}))
                .await;
            assert!(matches!(r, Err(MCPError::ToolExecutionFailed(_))), "{name}");
        }
        let v = body(
            &tool(&s, "validate_and_fix_workflow")
                .execute(json!({"nodes": [{"type": "Mountain"}], "runtime_check": true}))
                .await
                .unwrap(),
        );
        assert_eq!(v["valid"], false);
    }

    #[tokio::test]
    async fn info_tools() {
        let dir = tempfile::tempdir().unwrap();
        let s = server(dir.path());
        let n = body(
            &tool(&s, "list_gaea2_nodes")
                .execute(json!({"node_type": "Erosion2"}))
                .await
                .unwrap(),
        );
        assert_eq!(n["category"], "Simulate");
        assert!(n["outputs"].as_array().unwrap().len() >= 4);
        assert!(tool(&s, "list_gaea2_nodes")
            .execute(json!({"node_type": "Erosoin2"}))
            .await
            .is_err());
        let all = body(
            &tool(&s, "list_gaea2_nodes")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert!(all["total"].as_u64().unwrap() > 150);

        let t = body(
            &tool(&s, "list_gaea2_templates")
                .execute(json!({"include_workflow": true}))
                .await
                .unwrap(),
        );
        assert_eq!(t["count"], 11);
        assert!(t["templates"][0]["nodes"].is_array());

        let st = body(
            &tool(&s, "get_gaea2_status")
                .execute(Value::Null)
                .await
                .unwrap(),
        );
        assert_eq!(st["cli_available"], false);

        let h = body(
            &tool(&s, "analyze_execution_history")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(h["total_count"], 0);
        assert!(h["success_rate"].is_null());

        let sug = body(
            &tool(&s, "suggest_gaea2_nodes")
                .execute(json!({"current_nodes": ["Mountain", "Mountian"]}))
                .await
                .unwrap(),
        );
        assert_eq!(sug["unknown_node_types"][0]["did_you_mean"], "Mountain");
    }

    #[test]
    fn resolution_parsing() {
        assert_eq!(parse_resolution(&json!("2048")).unwrap(), 2048);
        assert_eq!(parse_resolution(&json!(512)).unwrap(), 512);
        assert!(parse_resolution(&json!(1000)).is_err());
        assert!(parse_resolution(&json!(true)).is_err());
    }
}
