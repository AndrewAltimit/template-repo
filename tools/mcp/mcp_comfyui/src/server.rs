//! MCP tool implementations for ComfyUI.
//!
//! Every tool deserializes its arguments into a typed `serde` struct, so a
//! missing or mistyped argument becomes a clean `InvalidParameters` error
//! instead of a silent default or a panic. Hand-written `Tool` impls are used
//! (rather than `#[mcp_tool]`) because the schemas need enums, defaults and
//! union types the macro cannot express.
//!
//! Error convention: bad input -> `MCPError::InvalidParameters`; failures of
//! ComfyUI or the filesystem -> a tool result with `isError: true` whose JSON
//! body is `{"success": false, "error": "..."}`.

use std::collections::{HashMap, VecDeque};
use std::fmt::Display;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Map, Value, json};
use tokio::sync::RwLock;
use tracing::info;
use uuid::Uuid;

use crate::client::{ClientError, ComfyUIClient, MODEL_KINDS};
use crate::config::{Config, MAX_GENERATION_TIMEOUT_SECS};
use crate::loras::LoraStore;
use crate::types::{ImageOutput, JobState, JobStatus};
use crate::validate::{
    IMAGE_EXTENSIONS, check_dimension, check_range, decode_base64, encode_base64,
    mime_for_filename, sniff_image, validate_filename, validate_subfolder,
};
use crate::workflows::{
    self, DEFAULT_DENOISE, DEFAULT_FLUX_GUIDANCE, DEFAULT_SIZE, DEFAULT_UPSCALE_MODEL,
    InjectionReport, ModelFamily, SamplingParams, TEMPLATES, TemplateKind, find_template,
    inject_prompts, resolve_seed, template_names, validate_workflow,
};

/// Maximum number of images embedded inline in a single result.
const MAX_INLINE_IMAGES: usize = 8;
/// Maximum number of job records kept in memory.
const MAX_TRACKED_JOBS: usize = 256;

// ============================================================================
// Shared state
// ============================================================================

/// Metadata this server remembers about jobs it submitted.
#[derive(Debug, Clone, serde::Serialize)]
struct JobRecord {
    tool: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    template: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    prompt: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    seed: Option<u64>,
    submitted_at_unix: u64,
}

/// Bounded FIFO of job records (oldest evicted first).
#[derive(Default)]
struct JobTracker {
    order: VecDeque<String>,
    records: HashMap<String, JobRecord>,
}

impl JobTracker {
    fn insert(&mut self, prompt_id: String, record: JobRecord) {
        if self.records.insert(prompt_id.clone(), record).is_none() {
            self.order.push_back(prompt_id);
        }
        while self.order.len() > MAX_TRACKED_JOBS {
            if let Some(old) = self.order.pop_front() {
                self.records.remove(&old);
            }
        }
    }

    fn get(&self, prompt_id: &str) -> Option<&JobRecord> {
        self.records.get(prompt_id)
    }
}

struct State {
    config: Config,
    client: ComfyUIClient,
    loras: LoraStore,
    jobs: RwLock<JobTracker>,
}

type Shared = Arc<State>;

/// ComfyUI MCP server: owns shared state and hands out the tool set.
pub struct ComfyUIServer {
    state: Shared,
}

impl ComfyUIServer {
    /// Create a server configured from the environment.
    pub fn new() -> Self {
        Self::with_config(Config::from_env())
    }

    /// Create a server from an explicit configuration.
    pub fn with_config(config: Config) -> Self {
        Self::with_config_and_poll(config, Duration::from_secs(1))
    }

    /// Create a server with a custom completion polling interval.
    pub fn with_config_and_poll(config: Config, poll_interval: Duration) -> Self {
        let client = ComfyUIClient::new(
            &config.base_url,
            Duration::from_secs(config.request_timeout_secs),
            Uuid::new_v4().to_string(),
        )
        .with_poll_interval(poll_interval);
        let loras = LoraStore::new(config.lora_dir(), config.max_lora_download_bytes);
        info!(
            "ComfyUI MCP configured for {} (generation timeout {}s, LoRA dir {})",
            config.base_url,
            config.generation_timeout_secs,
            loras.dir().display()
        );
        Self {
            state: Arc::new(State {
                config,
                client,
                loras,
                jobs: RwLock::new(JobTracker::default()),
            }),
        }
    }

    /// All tools provided by this server.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let s = || self.state.clone();
        vec![
            Arc::new(GenerateImageTool(s())),
            Arc::new(ListWorkflowsTool),
            Arc::new(GetWorkflowTool),
            Arc::new(ListModelsTool(s())),
            Arc::new(UploadLoraTool(s())),
            Arc::new(ListLorasTool(s())),
            Arc::new(DownloadLoraTool(s())),
            Arc::new(GetObjectInfoTool(s())),
            Arc::new(GetSystemInfoTool(s())),
            Arc::new(ExecuteWorkflowTool(s())),
            Arc::new(GetJobStatusTool(s())),
            Arc::new(CancelJobTool(s())),
            Arc::new(GetQueueTool(s())),
            Arc::new(GetImageTool(s())),
            Arc::new(UploadImageTool(s())),
        ]
    }
}

impl Default for ComfyUIServer {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Helpers
// ============================================================================

/// Deserialize tool arguments (`null` is treated as `{}`).
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

fn invalid(msg: impl Display) -> MCPError {
    MCPError::InvalidParameters(msg.to_string())
}

/// Success result: `body` with `"success": true` prepended.
fn success(body: Value) -> Result<ToolResult> {
    let mut map = Map::new();
    map.insert("success".into(), json!(true));
    if let Value::Object(obj) = body {
        map.extend(obj);
    }
    ToolResult::json(&Value::Object(map))
}

/// Error result (`isError: true`) with a JSON body.
fn failure_with(error: impl Display, extra: Value) -> Result<ToolResult> {
    let mut map = Map::new();
    map.insert("success".into(), json!(false));
    map.insert("error".into(), json!(error.to_string()));
    if let Value::Object(obj) = extra {
        map.extend(obj);
    }
    let mut result = ToolResult::json(&Value::Object(map))?;
    result.is_error = true;
    Ok(result)
}

fn failure(error: impl Display) -> Result<ToolResult> {
    failure_with(error, json!({}))
}

fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Validate a ComfyUI prompt id before it is embedded in a URL path.
fn validate_prompt_id(id: &str) -> Result<&str> {
    if id.is_empty() || id.len() > 128 {
        return Err(invalid("prompt_id/job_id must be 1-128 characters"));
    }
    if !id
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
    {
        return Err(invalid(format!(
            "prompt_id/job_id {id:?} may only contain letters, digits, '-' and '_'"
        )));
    }
    Ok(id)
}

fn pick_prompt_id(job_id: Option<String>, prompt_id: Option<String>) -> Result<String> {
    let id = prompt_id
        .or(job_id)
        .ok_or_else(|| invalid("provide job_id or prompt_id"))?;
    validate_prompt_id(&id)?;
    Ok(id)
}

fn resolve_timeout(requested: Option<u64>, default: u64) -> Result<Duration> {
    let secs = match requested {
        Some(t) => check_range("timeout", t, 1, MAX_GENERATION_TIMEOUT_SECS).map_err(invalid)?,
        None => default,
    };
    Ok(Duration::from_secs(secs))
}

/// Validate an image reference usable by `LoadImage`: `name.png` or
/// `subfolder/name.png` inside ComfyUI's input directory.
fn validate_image_ref(reference: &str) -> Result<()> {
    if let Some((sub, _)) = reference.rsplit_once('/') {
        if sub.is_empty() {
            return Err(invalid(format!(
                "input_image {reference:?} must be relative to ComfyUI's input directory"
            )));
        }
        validate_subfolder(sub).map_err(invalid)?;
    }
    let name = reference.rsplit('/').next().unwrap_or(reference);
    validate_filename(name, IMAGE_EXTENSIONS).map_err(invalid)?;
    Ok(())
}

fn validate_filename_prefix(prefix: &str) -> Result<()> {
    if prefix.is_empty() || prefix.len() > 128 {
        return Err(invalid("filename_prefix must be 1-128 characters"));
    }
    if prefix.starts_with('/') || prefix.contains('\\') || prefix.contains(':') {
        return Err(invalid("filename_prefix must be a relative name"));
    }
    if prefix.split('/').any(|seg| seg.is_empty() || seg == "..") {
        return Err(invalid(
            "filename_prefix must not contain empty or '..' segments",
        ));
    }
    if prefix.chars().any(char::is_control) {
        return Err(invalid("filename_prefix contains control characters"));
    }
    Ok(())
}

fn non_empty_name(field: &str, value: String) -> Result<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(invalid(format!("{field} must not be empty")));
    }
    if trimmed.len() > 512 || trimmed.chars().any(char::is_control) {
        return Err(invalid(format!(
            "{field} is too long or contains control characters"
        )));
    }
    Ok(trimmed.to_string())
}

/// Upload base64 image data to ComfyUI's input dir; returns the reference
/// (`subfolder/name` or `name`) to use in `LoadImage`.
async fn upload_image_data(
    state: &State,
    data_b64: &str,
    filename: Option<&str>,
    subfolder: &str,
    overwrite: bool,
) -> std::result::Result<(String, Value), String> {
    let data = decode_base64(data_b64)?;
    let (ext, mime) = sniff_image(&data)
        .ok_or_else(|| "data is not a PNG, JPEG, WebP, GIF or BMP image".to_string())?;
    let generated;
    let filename = match filename {
        Some(name) => name,
        None => {
            generated = format!("mcp_{}.{ext}", Uuid::new_v4().simple());
            &generated
        },
    };
    let response = state
        .client
        .upload_image(filename, &data, mime, subfolder, overwrite)
        .await
        .map_err(|e| e.to_string())?;
    let name = response["name"].as_str().unwrap_or(filename);
    let sub = response
        .get("subfolder")
        .and_then(Value::as_str)
        .unwrap_or("");
    let reference = if sub.is_empty() {
        name.to_string()
    } else {
        format!("{sub}/{name}")
    };
    Ok((reference, response))
}

/// Fetch images for inline return. Failures become warnings.
async fn fetch_inline_images(
    state: &State,
    images: &[ImageOutput],
    warnings: &mut Vec<String>,
) -> Vec<Content> {
    let mut contents = Vec::new();
    if images.len() > MAX_INLINE_IMAGES {
        warnings.push(format!(
            "only the first {MAX_INLINE_IMAGES} of {} images are embedded; use get_image for the rest",
            images.len()
        ));
    }
    for img in images.iter().take(MAX_INLINE_IMAGES) {
        match state
            .client
            .view(
                &img.filename,
                &img.subfolder,
                &img.output_type,
                state.config.max_image_bytes,
            )
            .await
        {
            Ok((bytes, content_type)) => contents.push(Content::Image {
                data: encode_base64(&bytes),
                mime_type: image_mime(content_type.as_deref(), &img.filename),
            }),
            Err(e) => warnings.push(format!("could not embed {}: {e}", img.filename)),
        }
    }
    contents
}

fn image_mime(content_type: Option<&str>, filename: &str) -> String {
    match content_type {
        Some(ct) if ct.starts_with("image/") => ct.split(';').next().unwrap_or(ct).to_string(),
        _ => mime_for_filename(filename).to_string(),
    }
}

/// Build the result for a job state: success for completed/queued/running,
/// `isError` for failed/interrupted/timeout/unknown.
async fn job_result(
    state: &State,
    prompt_id: &str,
    job: JobState,
    include_images: bool,
    mut body: Map<String, Value>,
    mut warnings: Vec<String>,
) -> Result<ToolResult> {
    body.insert("job_id".into(), json!(prompt_id));
    body.insert("prompt_id".into(), json!(prompt_id));
    body.insert("status".into(), json!(job.status));
    if let Some(pos) = job.queue_position {
        body.insert("queue_position".into(), json!(pos));
    }
    body.insert("images".into(), json!(job.images));

    let images = if include_images && job.status == JobStatus::Completed {
        fetch_inline_images(state, &job.images, &mut warnings).await
    } else {
        Vec::new()
    };
    if !warnings.is_empty() {
        body.insert("warnings".into(), json!(warnings));
    }

    let error = match job.status {
        JobStatus::Completed | JobStatus::Queued | JobStatus::Running => None,
        JobStatus::Timeout => Some(format!(
            "{}; the job keeps running in ComfyUI -- poll get_job_status with job_id {prompt_id:?} \
             or cancel it with cancel_job",
            job.error.as_deref().unwrap_or("generation timed out")
        )),
        JobStatus::Unknown => Some(format!(
            "prompt {prompt_id:?} is not in ComfyUI's queue or history (ComfyUI may have restarted \
             or its history was cleared)"
        )),
        JobStatus::Failed | JobStatus::Interrupted => Some(
            job.error
                .clone()
                .unwrap_or_else(|| format!("job {:?}", job.status)),
        ),
    };

    match error {
        None => {
            let mut map = Map::new();
            map.insert("success".into(), json!(true));
            map.extend(body);
            let mut content = vec![Content::json(&Value::Object(map))?];
            content.extend(images);
            Ok(ToolResult::with_content(content))
        },
        Some(err) => failure_with(err, Value::Object(body)),
    }
}

async fn record_job(state: &State, prompt_id: &str, record: JobRecord) {
    state
        .jobs
        .write()
        .await
        .insert(prompt_id.to_string(), record);
}

async fn wait_or_report(
    state: &State,
    prompt_id: &str,
    wait: bool,
    timeout: Duration,
    include_images: bool,
    body: Map<String, Value>,
    warnings: Vec<String>,
) -> Result<ToolResult> {
    let job = if wait {
        match state.client.wait_for_completion(prompt_id, timeout).await {
            Ok(job) => job,
            Err(e) => {
                let mut body = body;
                body.insert("job_id".into(), json!(prompt_id));
                body.insert("prompt_id".into(), json!(prompt_id));
                return failure_with(
                    format!("lost contact with ComfyUI while waiting: {e}"),
                    Value::Object(body),
                );
            },
        }
    } else {
        JobState::bare(JobStatus::Queued)
    };
    job_result(state, prompt_id, job, include_images, body, warnings).await
}

fn client_failure(e: ClientError) -> Result<ToolResult> {
    failure(e)
}

// ============================================================================
// generate_image
// ============================================================================

fn default_true() -> bool {
    true
}

#[derive(Debug, Default, Deserialize)]
struct GenerateImageArgs {
    prompt: String,
    negative_prompt: Option<String>,
    workflow: Option<Value>,
    model_family: Option<ModelFamily>,
    width: Option<u32>,
    height: Option<u32>,
    seed: Option<i64>,
    steps: Option<u32>,
    cfg_scale: Option<f64>,
    guidance: Option<f64>,
    sampler_name: Option<String>,
    scheduler: Option<String>,
    checkpoint: Option<String>,
    lora_name: Option<String>,
    lora_strength: Option<f64>,
    batch_size: Option<u32>,
    denoise: Option<f64>,
    input_image: Option<String>,
    input_image_data: Option<String>,
    upscale_model: Option<String>,
    controlnet_name: Option<String>,
    control_strength: Option<f64>,
    filename_prefix: Option<String>,
    timeout: Option<u64>,
    #[serde(default = "default_true")]
    wait: bool,
    #[serde(default)]
    include_images: bool,
}

/// A fully built generation request.
#[derive(Debug)]
struct Plan {
    workflow: Value,
    template: String,
    seed: Option<u64>,
    family: Option<ModelFamily>,
    injection: Option<InjectionReport>,
    warnings: Vec<String>,
}

/// Build the workflow for `generate_image`. `input_image` is the resolved
/// LoadImage reference (after any upload). Pure, so it is unit-testable.
fn plan_generation(args: &GenerateImageArgs, input_image: Option<&str>) -> Result<Plan> {
    let mut warnings = Vec::new();

    let template = match &args.workflow {
        Some(Value::Object(_)) => {
            if input_image.is_some() {
                return Err(invalid(
                    "input_image/input_image_data are not used with custom workflows; upload with                      upload_image and reference the returned name in your LoadImage node",
                ));
            }
            let custom = args.workflow.clone().unwrap_or_default();
            validate_workflow(&custom).map_err(invalid)?;
            let mut custom = custom;
            if args.prompt.trim().is_empty() {
                return Err(invalid("prompt must not be empty"));
            }
            let report = inject_prompts(&mut custom, &args.prompt, args.negative_prompt.as_deref());
            if report.positive_nodes.is_empty() {
                warnings.push(
                    "no CLIPTextEncode node found; the prompt was not injected into the custom workflow"
                        .to_string(),
                );
            }
            let ignored: Vec<&str> = [
                ("width", args.width.is_some()),
                ("height", args.height.is_some()),
                ("seed", args.seed.is_some()),
                ("steps", args.steps.is_some()),
                ("cfg_scale", args.cfg_scale.is_some()),
                ("lora_name", args.lora_name.is_some()),
                ("checkpoint", args.checkpoint.is_some()),
            ]
            .iter()
            .filter(|(_, set)| *set)
            .map(|(n, _)| *n)
            .collect();
            if !ignored.is_empty() {
                warnings.push(format!(
                    "ignored for custom workflows (edit the workflow instead): {}",
                    ignored.join(", ")
                ));
            }
            return Ok(Plan {
                workflow: custom,
                template: "custom".into(),
                seed: None,
                family: None,
                injection: Some(report),
                warnings,
            });
        },
        Some(Value::String(name)) => find_template(name).ok_or_else(|| {
            invalid(format!(
                "unknown workflow template {name:?}; available: {}",
                template_names()
            ))
        })?,
        Some(Value::Null) | None => if input_image.is_some() {
            find_template("img2img")
        } else {
            let sdxl = args.model_family == Some(ModelFamily::Sdxl)
                || (args.model_family.is_none()
                    && args
                        .checkpoint
                        .as_deref()
                        .and_then(ModelFamily::guess_from_checkpoint)
                        == Some(ModelFamily::Sdxl));
            find_template(if sdxl { "sdxl_default" } else { "flux_default" })
        }
        .ok_or_else(|| invalid("built-in template missing"))?,
        Some(_) => {
            return Err(invalid(
                "workflow must be a template name (string) or an API-format workflow (object)",
            ));
        },
    };

    let needs_input = template.kind != TemplateKind::TextToImage;
    let image = match (needs_input, input_image) {
        (true, Some(img)) => img,
        (true, None) => {
            return Err(invalid(format!(
                "template {:?} needs input_image (a file in ComfyUI's input directory, see \
                 upload_image) or input_image_data (base64)",
                template.name
            )));
        },
        (false, Some(_)) => {
            return Err(invalid(format!(
                "template {:?} does not take an input image; use img2img, upscale or controlnet",
                template.name
            )));
        },
        (false, None) => "",
    };

    let prefix_default = match template.kind {
        TemplateKind::TextToImage => "ComfyUI",
        TemplateKind::ImageToImage => "ComfyUI_img2img",
        TemplateKind::ControlNet => "ComfyUI_controlnet",
        TemplateKind::Upscale => "ComfyUI_upscaled",
    };
    let filename_prefix = args
        .filename_prefix
        .clone()
        .unwrap_or_else(|| prefix_default.to_string());
    validate_filename_prefix(&filename_prefix)?;

    if template.kind == TemplateKind::Upscale {
        let model = match &args.upscale_model {
            Some(m) => non_empty_name("upscale_model", m.clone())?,
            None => DEFAULT_UPSCALE_MODEL.to_string(),
        };
        return Ok(Plan {
            workflow: workflows::upscale(image, &model, &filename_prefix),
            template: template.name.to_string(),
            seed: None,
            family: None,
            injection: None,
            warnings,
        });
    }

    if args.prompt.trim().is_empty() {
        return Err(invalid("prompt must not be empty"));
    }

    let family = template
        .family
        .or(args.model_family)
        .or_else(|| {
            args.checkpoint
                .as_deref()
                .and_then(ModelFamily::guess_from_checkpoint)
        })
        .unwrap_or(ModelFamily::Flux);

    let mut p = SamplingParams::defaults(family, &args.prompt);
    p.negative_prompt = args.negative_prompt.clone().unwrap_or_default();
    p.seed = resolve_seed(args.seed).map_err(invalid)?;
    if let Some(steps) = args.steps {
        p.steps = check_range("steps", steps, 1, 200).map_err(invalid)?;
    }
    if let Some(cfg) = args.cfg_scale {
        p.cfg = check_range("cfg_scale", cfg, 0.0, 30.0).map_err(invalid)?;
    }
    p.guidance = check_range(
        "guidance",
        args.guidance.unwrap_or(DEFAULT_FLUX_GUIDANCE),
        0.0,
        100.0,
    )
    .map_err(invalid)?;
    if let Some(s) = &args.sampler_name {
        p.sampler = non_empty_name("sampler_name", s.clone())?;
    }
    if let Some(s) = &args.scheduler {
        p.scheduler = non_empty_name("scheduler", s.clone())?;
    }
    if let Some(c) = &args.checkpoint {
        p.checkpoint = non_empty_name("checkpoint", c.clone())?;
    }
    if let Some(batch) = args.batch_size {
        p.batch_size = check_range("batch_size", batch, 1, 16).map_err(invalid)?;
    }
    let lora_strength = check_range(
        "lora_strength",
        args.lora_strength.unwrap_or(1.0),
        -10.0,
        10.0,
    )
    .map_err(invalid)?;
    p.lora = match &args.lora_name {
        Some(name) => Some((non_empty_name("lora_name", name.clone())?, lora_strength)),
        None if template.name == "flux_with_lora" => {
            return Err(invalid("template \"flux_with_lora\" requires lora_name"));
        },
        None => None,
    };
    p.filename_prefix = filename_prefix;
    if family == ModelFamily::Flux && args.cfg_scale.is_some_and(|c| c > 2.0) {
        warnings.push(
            "FLUX-dev expects cfg_scale 1.0 (use 'guidance' for prompt strength); high CFG \
             usually produces burned images"
                .to_string(),
        );
    }

    let dims = |default: u32| -> Result<(u32, u32)> {
        Ok((
            check_dimension("width", args.width.unwrap_or(default)).map_err(invalid)?,
            check_dimension("height", args.height.unwrap_or(default)).map_err(invalid)?,
        ))
    };

    let workflow = match template.kind {
        TemplateKind::TextToImage => {
            let (w, h) = dims(DEFAULT_SIZE)?;
            workflows::text_to_image(&p, w, h)
        },
        TemplateKind::ImageToImage => {
            p.denoise = args.denoise.unwrap_or(DEFAULT_DENOISE);
            if !(p.denoise > 0.0 && p.denoise <= 1.0) {
                return Err(invalid(format!(
                    "denoise must be in (0, 1] (got {})",
                    p.denoise
                )));
            }
            let resize = match (args.width, args.height) {
                (None, None) => None,
                (Some(_), Some(_)) => Some(dims(DEFAULT_SIZE)?),
                _ => {
                    return Err(invalid(
                        "img2img resizing needs both width and height (or neither)",
                    ));
                },
            };
            workflows::image_to_image(&p, image, resize)
        },
        TemplateKind::ControlNet => {
            let name = args
                .controlnet_name
                .clone()
                .ok_or_else(|| invalid("template \"controlnet\" requires controlnet_name"))?;
            let name = non_empty_name("controlnet_name", name)?;
            let strength = check_range(
                "control_strength",
                args.control_strength.unwrap_or(1.0),
                0.0,
                10.0,
            )
            .map_err(invalid)?;
            let (w, h) = dims(DEFAULT_SIZE)?;
            workflows::controlnet(&p, image, &name, strength, w, h)
        },
        TemplateKind::Upscale => {
            return Err(MCPError::Internal("upscale is planned earlier".into()));
        },
    };

    Ok(Plan {
        workflow,
        template: template.name.to_string(),
        seed: Some(p.seed),
        family: Some(family),
        injection: None,
        warnings,
    })
}

struct GenerateImageTool(Shared);

#[async_trait]
impl Tool for GenerateImageTool {
    fn name(&self) -> &str {
        "generate_image"
    }

    fn description(&self) -> &str {
        "Generate images with ComfyUI. Uses a built-in template (flux_default, sdxl_default, \
         flux_with_lora, img2img, upscale, controlnet) or a custom API-format workflow into which \
         the prompt is injected. Waits for completion by default and returns output file \
         references (optionally the images themselves via include_images)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Positive text prompt"},
                "negative_prompt": {"type": "string", "description": "Negative prompt (ignored by FLUX models). For custom workflows the existing negative text is kept unless this is set."},
                "workflow": {
                    "type": ["string", "object"],
                    "description": "Template name (flux_default|flux, sdxl_default|sdxl, flux_with_lora, img2img, upscale, controlnet) or a complete API-format workflow object. Default: flux_default (sdxl_default when model_family=sdxl; img2img when an input image is given)."
                },
                "model_family": {"type": "string", "enum": ["flux", "sdxl"], "description": "Sampling defaults for img2img/controlnet or the default template"},
                "width": {"type": "integer", "minimum": 64, "maximum": 8192, "description": "Image width, multiple of 8 (default 1024; img2img: resize target)"},
                "height": {"type": "integer", "minimum": 64, "maximum": 8192, "description": "Image height, multiple of 8 (default 1024; img2img: resize target)"},
                "seed": {"type": "integer", "minimum": -1, "default": -1, "description": "Seed; -1 for random. The seed used is returned."},
                "steps": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Sampling steps (default: flux 20, sdxl 30)"},
                "cfg_scale": {"type": "number", "minimum": 0, "maximum": 30, "description": "KSampler CFG (default: flux 1.0, sdxl 7.0)"},
                "guidance": {"type": "number", "minimum": 0, "maximum": 100, "default": 3.5, "description": "FLUX guidance strength (FLUX only)"},
                "sampler_name": {"type": "string", "description": "Sampler (default: flux heunpp2, sdxl dpmpp_2m)"},
                "scheduler": {"type": "string", "description": "Scheduler (default: flux simple, sdxl karras)"},
                "checkpoint": {"type": "string", "description": "Checkpoint file (see list_models type=checkpoint)"},
                "lora_name": {"type": "string", "description": "LoRA file to apply (see list_models type=lora)"},
                "lora_strength": {"type": "number", "minimum": -10, "maximum": 10, "default": 1.0, "description": "LoRA strength for model and CLIP"},
                "batch_size": {"type": "integer", "minimum": 1, "maximum": 16, "default": 1, "description": "Images per run"},
                "denoise": {"type": "number", "exclusiveMinimum": 0, "maximum": 1, "default": 0.75, "description": "img2img denoise strength"},
                "input_image": {"type": "string", "description": "Image in ComfyUI's input directory ('name.png' or 'subfolder/name.png'), e.g. from upload_image. Required for img2img/upscale/controlnet."},
                "input_image_data": {"type": "string", "description": "Base64 image (data URLs accepted) uploaded automatically and used as input_image"},
                "upscale_model": {"type": "string", "default": "4x-UltraSharp.pth", "description": "Upscale model (upscale template)"},
                "controlnet_name": {"type": "string", "description": "ControlNet model matching the checkpoint family (controlnet template; required)"},
                "control_strength": {"type": "number", "minimum": 0, "maximum": 10, "default": 1.0, "description": "ControlNet strength"},
                "filename_prefix": {"type": "string", "description": "SaveImage filename prefix (may include a subfolder)"},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 7200, "description": "Seconds to wait for completion (default COMFYUI_GENERATION_TIMEOUT, 300)"},
                "wait": {"type": "boolean", "default": true, "description": "Wait for completion; false returns immediately with job_id for get_job_status"},
                "include_images": {"type": "boolean", "default": false, "description": "Embed the generated images (base64) in the result"}
            },
            "required": ["prompt"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let args: GenerateImageArgs = parse_args(args)?;
        let timeout = resolve_timeout(args.timeout, state.config.generation_timeout_secs)?;

        if args.input_image.is_some() && args.input_image_data.is_some() {
            return Err(invalid(
                "pass either input_image or input_image_data, not both",
            ));
        }
        if let Some(reference) = &args.input_image {
            validate_image_ref(reference)?;
        }
        // Validate everything we can before uploading anything.
        let placeholder = (args.input_image_data.is_some()).then_some("pending.png");
        let precheck = plan_generation(&args, args.input_image.as_deref().or(placeholder))?;

        let mut body = Map::new();
        let input_image = match &args.input_image_data {
            Some(data) => match upload_image_data(state, data, None, "", false).await {
                Ok((reference, _)) => {
                    body.insert("input_image".into(), json!(reference));
                    Some(reference)
                },
                Err(e) => return failure(format!("failed to upload input image: {e}")),
            },
            None => args.input_image.clone(),
        };
        let plan = if input_image.as_deref() == args.input_image.as_deref() {
            precheck
        } else {
            plan_generation(&args, input_image.as_deref())?
        };

        let prompt_id = match state.client.queue_prompt(&plan.workflow).await {
            Ok(id) => id,
            Err(e) => return client_failure(e),
        };
        record_job(
            state,
            &prompt_id,
            JobRecord {
                tool: "generate_image",
                template: Some(plan.template.clone()),
                prompt: Some(args.prompt.clone()),
                seed: plan.seed,
                submitted_at_unix: now_unix(),
            },
        )
        .await;

        body.insert("template".into(), json!(plan.template));
        if let Some(seed) = plan.seed {
            body.insert("seed".into(), json!(seed));
        }
        if let Some(family) = plan.family {
            body.insert("model_family".into(), json!(family));
        }
        if let Some(report) = &plan.injection {
            body.insert("prompt_injection".into(), json!(report));
        }
        wait_or_report(
            state,
            &prompt_id,
            args.wait,
            timeout,
            args.include_images,
            body,
            plan.warnings,
        )
        .await
    }
}

// ============================================================================
// execute_workflow
// ============================================================================

#[derive(Debug, Deserialize)]
struct ExecuteWorkflowArgs {
    workflow: Value,
    #[serde(default)]
    wait: bool,
    timeout: Option<u64>,
    #[serde(default)]
    include_images: bool,
}

struct ExecuteWorkflowTool(Shared);

#[async_trait]
impl Tool for ExecuteWorkflowTool {
    fn name(&self) -> &str {
        "execute_workflow"
    }

    fn description(&self) -> &str {
        "Queue a complete API-format ComfyUI workflow as-is. Non-blocking by default (returns \
         job_id for get_job_status); set wait=true to block until it finishes."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "workflow": {"type": "object", "description": "API-format workflow ({node_id: {class_type, inputs}}); export with 'Save (API Format)'"},
                "wait": {"type": "boolean", "default": false, "description": "Wait for completion"},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 7200, "description": "Seconds to wait when wait=true (default COMFYUI_GENERATION_TIMEOUT)"},
                "include_images": {"type": "boolean", "default": false, "description": "Embed output images when wait=true"}
            },
            "required": ["workflow"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let args: ExecuteWorkflowArgs = parse_args(args)?;
        validate_workflow(&args.workflow).map_err(invalid)?;
        let timeout = resolve_timeout(args.timeout, state.config.generation_timeout_secs)?;

        let prompt_id = match state.client.queue_prompt(&args.workflow).await {
            Ok(id) => id,
            Err(e) => return client_failure(e),
        };
        record_job(
            state,
            &prompt_id,
            JobRecord {
                tool: "execute_workflow",
                template: None,
                prompt: None,
                seed: None,
                submitted_at_unix: now_unix(),
            },
        )
        .await;

        let mut body = Map::new();
        if !args.wait {
            body.insert("message".into(), json!("Workflow queued for execution"));
        }
        wait_or_report(
            state,
            &prompt_id,
            args.wait,
            timeout,
            args.include_images,
            body,
            Vec::new(),
        )
        .await
    }
}

// ============================================================================
// get_job_status / cancel_job / get_queue
// ============================================================================

#[derive(Debug, Deserialize)]
struct JobStatusArgs {
    job_id: Option<String>,
    prompt_id: Option<String>,
    #[serde(default)]
    wait: bool,
    timeout: Option<u64>,
    #[serde(default)]
    include_images: bool,
}

struct GetJobStatusTool(Shared);

#[async_trait]
impl Tool for GetJobStatusTool {
    fn name(&self) -> &str {
        "get_job_status"
    }

    fn description(&self) -> &str {
        "Get the status (queued/running/completed/failed/interrupted) and output images of a \
         ComfyUI job, optionally waiting for it to finish"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "job_id returned by generate_image/execute_workflow"},
                "prompt_id": {"type": "string", "description": "ComfyUI prompt id (same value as job_id)"},
                "wait": {"type": "boolean", "default": false, "description": "Block until the job finishes or timeout elapses"},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 7200, "description": "Seconds to wait when wait=true"},
                "include_images": {"type": "boolean", "default": false, "description": "Embed output images if completed"}
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let args: JobStatusArgs = parse_args(args)?;
        let prompt_id = pick_prompt_id(args.job_id, args.prompt_id)?;
        let timeout = resolve_timeout(args.timeout, state.config.generation_timeout_secs)?;

        let job = if args.wait {
            state.client.wait_for_completion(&prompt_id, timeout).await
        } else {
            state.client.job_state(&prompt_id).await
        };
        let job = match job {
            Ok(job) => job,
            Err(e) => return client_failure(e),
        };
        let mut body = Map::new();
        if let Some(record) = state.jobs.read().await.get(&prompt_id) {
            body.insert("submitted".into(), json!(record));
        }
        job_result(
            state,
            &prompt_id,
            job,
            args.include_images,
            body,
            Vec::new(),
        )
        .await
    }
}

#[derive(Debug, Deserialize)]
struct CancelJobArgs {
    job_id: Option<String>,
    prompt_id: Option<String>,
}

struct CancelJobTool(Shared);

#[async_trait]
impl Tool for CancelJobTool {
    fn name(&self) -> &str {
        "cancel_job"
    }

    fn description(&self) -> &str {
        "Cancel a ComfyUI job: removes it from the queue if pending, interrupts it if running"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "job_id returned by generate_image/execute_workflow"},
                "prompt_id": {"type": "string", "description": "ComfyUI prompt id (same value as job_id)"}
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let args: CancelJobArgs = parse_args(args)?;
        let prompt_id = pick_prompt_id(args.job_id, args.prompt_id)?;

        let job = match state.client.job_state(&prompt_id).await {
            Ok(job) => job,
            Err(e) => return client_failure(e),
        };
        let action = match job.status {
            JobStatus::Queued => state
                .client
                .delete_from_queue(&prompt_id)
                .await
                .map(|_| "removed_from_queue"),
            JobStatus::Running => state
                .client
                .interrupt(&prompt_id)
                .await
                .map(|_| "interrupted"),
            JobStatus::Unknown => {
                return failure(format!(
                    "prompt {prompt_id:?} is not in ComfyUI's queue or history"
                ));
            },
            _ => {
                return success(json!({
                    "job_id": prompt_id,
                    "cancelled": false,
                    "status": job.status,
                    "message": "job already finished; nothing to cancel"
                }));
            },
        };
        match action {
            Ok(action) => success(json!({
                "job_id": prompt_id,
                "cancelled": true,
                "action": action,
                "previous_status": job.status
            })),
            Err(e) => client_failure(e),
        }
    }
}

struct GetQueueTool(Shared);

#[async_trait]
impl Tool for GetQueueTool {
    fn name(&self) -> &str {
        "get_queue"
    }

    fn description(&self) -> &str {
        "Show ComfyUI's execution queue (running and pending prompt ids)"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.0.client.queue().await {
            Ok(q) => success(json!({
                "running_count": q.running.len(),
                "pending_count": q.pending.len(),
                "running": q.running,
                "pending": q.pending
            })),
            Err(e) => client_failure(e),
        }
    }
}

// ============================================================================
// get_image / upload_image
// ============================================================================

#[derive(Debug, Clone, Copy, Deserialize, serde::Serialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
enum StorageType {
    Output,
    Input,
    Temp,
}

impl StorageType {
    fn as_str(self) -> &'static str {
        match self {
            StorageType::Output => "output",
            StorageType::Input => "input",
            StorageType::Temp => "temp",
        }
    }
}

fn default_output() -> StorageType {
    StorageType::Output
}

#[derive(Debug, Deserialize)]
struct GetImageArgs {
    filename: String,
    #[serde(default)]
    subfolder: String,
    #[serde(rename = "type", default = "default_output")]
    storage: StorageType,
}

struct GetImageTool(Shared);

#[async_trait]
impl Tool for GetImageTool {
    fn name(&self) -> &str {
        "get_image"
    }

    fn description(&self) -> &str {
        "Fetch an image from ComfyUI (output/input/temp) and return it as MCP image content"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Image file name (from a job's images list)"},
                "subfolder": {"type": "string", "default": "", "description": "Subfolder, as reported in the job's images list"},
                "type": {"type": "string", "enum": ["output", "input", "temp"], "default": "output", "description": "Storage area"}
            },
            "required": ["filename"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let args: GetImageArgs = parse_args(args)?;
        validate_filename(&args.filename, IMAGE_EXTENSIONS).map_err(invalid)?;
        validate_subfolder(&args.subfolder).map_err(invalid)?;

        match state
            .client
            .view(
                &args.filename,
                &args.subfolder,
                args.storage.as_str(),
                state.config.max_image_bytes,
            )
            .await
        {
            Ok((bytes, content_type)) => {
                let meta = json!({
                    "success": true,
                    "filename": args.filename,
                    "subfolder": args.subfolder,
                    "type": args.storage,
                    "size": bytes.len()
                });
                Ok(ToolResult::with_content(vec![
                    Content::json(&meta)?,
                    Content::Image {
                        data: encode_base64(&bytes),
                        mime_type: image_mime(content_type.as_deref(), &args.filename),
                    },
                ]))
            },
            Err(e) => client_failure(e),
        }
    }
}

#[derive(Debug, Deserialize)]
struct UploadImageArgs {
    filename: String,
    data: String,
    #[serde(default)]
    subfolder: String,
    #[serde(default)]
    overwrite: bool,
}

struct UploadImageTool(Shared);

#[async_trait]
impl Tool for UploadImageTool {
    fn name(&self) -> &str {
        "upload_image"
    }

    fn description(&self) -> &str {
        "Upload an image (base64) into ComfyUI's input directory for use by img2img, upscale, \
         controlnet or LoadImage nodes; returns the reference to pass as input_image"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Target file name (png, jpg, jpeg, webp, gif, bmp)"},
                "data": {"type": "string", "description": "Base64 image data (data URLs accepted)"},
                "subfolder": {"type": "string", "default": "", "description": "Optional subfolder inside the input directory"},
                "overwrite": {"type": "boolean", "default": false, "description": "Replace an existing file; otherwise ComfyUI picks a unique name"}
            },
            "required": ["filename", "data"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let args: UploadImageArgs = parse_args(args)?;
        validate_filename(&args.filename, IMAGE_EXTENSIONS).map_err(invalid)?;
        validate_subfolder(&args.subfolder).map_err(invalid)?;

        match upload_image_data(
            state,
            &args.data,
            Some(&args.filename),
            &args.subfolder,
            args.overwrite,
        )
        .await
        {
            Ok((reference, response)) => success(json!({
                "name": response["name"],
                "subfolder": response.get("subfolder").cloned().unwrap_or(json!("")),
                "type": response.get("type").cloned().unwrap_or(json!("input")),
                "input_image": reference
            })),
            Err(e) => failure(e),
        }
    }
}

// ============================================================================
// list_workflows / get_workflow
// ============================================================================

struct ListWorkflowsTool;

#[async_trait]
impl Tool for ListWorkflowsTool {
    fn name(&self) -> &str {
        "list_workflows"
    }

    fn description(&self) -> &str {
        "List the built-in ComfyUI workflow templates usable with generate_image"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        success(json!({"workflows": TEMPLATES}))
    }
}

#[derive(Debug, Deserialize)]
struct GetWorkflowArgs {
    #[serde(default = "default_workflow_name")]
    name: String,
}

fn default_workflow_name() -> String {
    "flux_default".to_string()
}

struct GetWorkflowTool;

#[async_trait]
impl Tool for GetWorkflowTool {
    fn name(&self) -> &str {
        "get_workflow"
    }

    fn description(&self) -> &str {
        "Get a built-in template as an API-format workflow with sample parameters (a starting \
         point for execute_workflow)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": TEMPLATES.iter().map(|t| t.name).collect::<Vec<_>>(),
                    "description": "Template name"
                }
            },
            "required": ["name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: GetWorkflowArgs = parse_args(args)?;
        let (Some(template), Some(workflow)) = (
            find_template(&args.name),
            workflows::sample_workflow(&args.name),
        ) else {
            return failure(format!(
                "Workflow not found: {}. Available: {}",
                args.name,
                template_names()
            ));
        };
        success(json!({
            "name": template.name,
            "description": template.description,
            "model_type": template.model_type,
            "requires": template.requires,
            "workflow": workflow
        }))
    }
}

// ============================================================================
// list_models / get_object_info / get_system_info
// ============================================================================

#[derive(Debug, Deserialize)]
struct ListModelsArgs {
    #[serde(rename = "type", alias = "model_type", default = "default_model_kind")]
    kind: String,
}

fn default_model_kind() -> String {
    "checkpoint".to_string()
}

struct ListModelsTool(Shared);

#[async_trait]
impl Tool for ListModelsTool {
    fn name(&self) -> &str {
        "list_models"
    }

    fn description(&self) -> &str {
        "List model files ComfyUI can load, by type"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": MODEL_KINDS.iter().map(|m| m.0).collect::<Vec<_>>(),
                    "default": "checkpoint",
                    "description": "Model type to list (alias: model_type)"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: ListModelsArgs = parse_args(args)?;
        if !MODEL_KINDS.iter().any(|m| m.0 == args.kind) {
            return Err(invalid(format!(
                "unknown model type {:?}; expected one of: {}",
                args.kind,
                MODEL_KINDS
                    .iter()
                    .map(|m| m.0)
                    .collect::<Vec<_>>()
                    .join(", ")
            )));
        }
        match self.0.client.models(&args.kind).await {
            Ok(models) => success(json!({
                "type": args.kind,
                "count": models.len(),
                "models": models
            })),
            Err(e) => client_failure(e),
        }
    }
}

#[derive(Debug, Deserialize)]
struct ObjectInfoArgs {
    node_class: Option<String>,
    #[serde(default)]
    full: bool,
}

struct GetObjectInfoTool(Shared);

#[async_trait]
impl Tool for GetObjectInfoTool {
    fn name(&self) -> &str {
        "get_object_info"
    }

    fn description(&self) -> &str {
        "Inspect ComfyUI nodes. With node_class: that node's inputs/outputs. Without: a summary \
         of available node classes (full=true returns the complete, very large dump)."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "node_class": {"type": "string", "description": "Node class to describe, e.g. KSampler"},
                "full": {"type": "boolean", "default": false, "description": "Return the complete object_info dump (can be several MB)"}
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: ObjectInfoArgs = parse_args(args)?;
        if let Some(class) = &args.node_class {
            let class = non_empty_name("node_class", class.clone())?;
            return match self.0.client.object_info(Some(&class)).await {
                Ok(info) => success(json!({"node_class": class, "info": info})),
                Err(e) => client_failure(e),
            };
        }
        let info = match self.0.client.object_info(None).await {
            Ok(info) => info,
            Err(e) => return client_failure(e),
        };
        if args.full {
            return ToolResult::json(&info);
        }
        success(summarize_object_info(&info))
    }
}

/// Compact overview of `/object_info`: sorted class names and per-category counts.
fn summarize_object_info(info: &Value) -> Value {
    let Some(nodes) = info.as_object() else {
        return json!({"node_count": 0, "node_classes": [], "categories": {}});
    };
    let mut classes: Vec<&String> = nodes.keys().collect();
    classes.sort();
    let mut categories: std::collections::BTreeMap<String, usize> = Default::default();
    for node in nodes.values() {
        let cat = node
            .get("category")
            .and_then(Value::as_str)
            .unwrap_or("uncategorized");
        let top = cat.split('/').next().unwrap_or(cat).to_string();
        *categories.entry(top).or_default() += 1;
    }
    json!({
        "node_count": nodes.len(),
        "node_classes": classes,
        "categories": categories,
        "hint": "pass node_class for a node's inputs, or full=true for the raw dump"
    })
}

struct GetSystemInfoTool(Shared);

#[async_trait]
impl Tool for GetSystemInfoTool {
    fn name(&self) -> &str {
        "get_system_info"
    }

    fn description(&self) -> &str {
        "Get ComfyUI system stats (versions, RAM, GPU devices and VRAM) and the configured endpoint"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.0.client.system_stats().await {
            Ok(stats) => {
                let mut body = Map::new();
                body.insert("comfyui_url".into(), json!(self.0.client.base_url()));
                if let Value::Object(obj) = stats {
                    body.extend(obj);
                }
                success(Value::Object(body))
            },
            Err(e) => client_failure(e),
        }
    }
}

// ============================================================================
// LoRA management (local filesystem)
// ============================================================================

#[derive(Debug, Deserialize)]
struct UploadLoraArgs {
    filename: String,
    data: String,
    metadata: Option<Value>,
    #[serde(default = "default_true")]
    overwrite: bool,
}

struct UploadLoraTool(Shared);

#[async_trait]
impl Tool for UploadLoraTool {
    fn name(&self) -> &str {
        "upload_lora"
    }

    fn description(&self) -> &str {
        "Store a base64-encoded LoRA in ComfyUI's models/loras directory (written atomically), \
         with optional JSON metadata saved alongside"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Bare file name ending in .safetensors, .ckpt or .pt"},
                "data": {"type": "string", "description": "Base64-encoded LoRA file"},
                "metadata": {"type": "object", "description": "Optional metadata written to <name>.json"},
                "overwrite": {"type": "boolean", "default": true, "description": "Replace an existing file with the same name"}
            },
            "required": ["filename", "data"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: UploadLoraArgs = parse_args(args)?;
        validate_filename(&args.filename, crate::validate::LORA_EXTENSIONS).map_err(invalid)?;
        let data = decode_base64(&args.data).map_err(invalid)?;
        match self
            .0
            .loras
            .upload(
                &args.filename,
                &data,
                args.metadata.as_ref(),
                args.overwrite,
            )
            .await
        {
            Ok(up) => success(json!({
                "filename": args.filename,
                "path": up.path.to_string_lossy(),
                "size": up.size,
                "replaced": up.replaced,
                "metadata_path": up.metadata_path.map(|p| p.to_string_lossy().into_owned())
            })),
            Err(e) => failure(e),
        }
    }
}

struct ListLorasTool(Shared);

#[async_trait]
impl Tool for ListLorasTool {
    fn name(&self) -> &str {
        "list_loras"
    }

    fn description(&self) -> &str {
        "List LoRA files in ComfyUI's models/loras directory (name, size, metadata presence)"
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        match self.0.loras.list().await {
            Ok(loras) => success(json!({
                "directory": self.0.loras.dir().to_string_lossy(),
                "count": loras.len(),
                "loras": loras
            })),
            Err(e) => failure(e),
        }
    }
}

#[derive(Debug, Deserialize)]
struct DownloadLoraArgs {
    filename: String,
    #[serde(default = "default_encoding")]
    encoding: String,
}

fn default_encoding() -> String {
    "base64".to_string()
}

struct DownloadLoraTool(Shared);

#[async_trait]
impl Tool for DownloadLoraTool {
    fn name(&self) -> &str {
        "download_lora"
    }

    fn description(&self) -> &str {
        "Download a LoRA from ComfyUI's models/loras directory as base64 (size-capped by \
         COMFYUI_MAX_LORA_DOWNLOAD_BYTES)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "LoRA file name (see list_loras)"},
                "encoding": {"type": "string", "enum": ["base64"], "default": "base64", "description": "Response encoding (only base64)"}
            },
            "required": ["filename"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: DownloadLoraArgs = parse_args(args)?;
        if args.encoding != "base64" {
            return Err(invalid(format!(
                "unsupported encoding {:?}; only \"base64\" is supported",
                args.encoding
            )));
        }
        match self.0.loras.download(&args.filename).await {
            Ok(data) => success(json!({
                "filename": args.filename,
                "encoding": "base64",
                "size": data.len(),
                "data": encode_base64(&data)
            })),
            Err(e) => failure(e),
        }
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn gen_args(v: Value) -> GenerateImageArgs {
        serde_json::from_value(v).unwrap()
    }

    #[test]
    fn plan_default_is_flux_txt2img() {
        let plan = plan_generation(&gen_args(json!({"prompt": "a cat", "seed": 5})), None).unwrap();
        assert_eq!(plan.template, "flux_default");
        assert_eq!(plan.seed, Some(5));
        assert_eq!(plan.workflow["4"]["inputs"]["cfg"], 1.0);
        assert_eq!(plan.workflow["5"]["inputs"]["width"], 1024);
        assert!(plan.warnings.is_empty());
    }

    #[test]
    fn plan_sdxl_selection() {
        let p =
            plan_generation(&gen_args(json!({"prompt": "x", "workflow": "sdxl"})), None).unwrap();
        assert_eq!(p.template, "sdxl_default");
        let p = plan_generation(
            &gen_args(json!({"prompt": "x", "model_family": "sdxl"})),
            None,
        )
        .unwrap();
        assert_eq!(p.template, "sdxl_default");
        let p = plan_generation(
            &gen_args(json!({"prompt": "x", "checkpoint": "juggernautXL.safetensors"})),
            None,
        )
        .unwrap();
        assert_eq!(p.template, "sdxl_default");
        assert_eq!(
            p.workflow["1"]["inputs"]["ckpt_name"],
            "juggernautXL.safetensors"
        );
    }

    #[test]
    fn plan_overrides_and_lora() {
        let p = plan_generation(
            &gen_args(json!({
                "prompt": "x", "workflow": "flux_with_lora", "lora_name": "s.safetensors",
                "lora_strength": 0.5, "width": 768, "height": 512, "steps": 8,
                "sampler_name": "euler", "scheduler": "normal", "batch_size": 2
            })),
            None,
        )
        .unwrap();
        let wf = &p.workflow;
        assert_eq!(wf["10"]["inputs"]["strength_model"], 0.5);
        assert_eq!(wf["5"]["inputs"]["width"], 768);
        assert_eq!(wf["5"]["inputs"]["batch_size"], 2);
        assert_eq!(wf["4"]["inputs"]["steps"], 8);
        assert_eq!(wf["4"]["inputs"]["sampler_name"], "euler");
    }

    #[test]
    fn plan_rejects_bad_input() {
        let cases = [
            json!({"prompt": "x", "workflow": "flux_with_lora"}),
            json!({"prompt": "x", "workflow": "nope"}),
            json!({"prompt": "x", "workflow": 5}),
            json!({"prompt": "x", "width": 1001}),
            json!({"prompt": "x", "steps": 0}),
            json!({"prompt": "x", "seed": -2}),
            json!({"prompt": "x", "cfg_scale": 99.0}),
            json!({"prompt": "   "}),
            json!({"prompt": "x", "workflow": "img2img"}),
            json!({"prompt": "x", "filename_prefix": "../escape"}),
            json!({"prompt": "x", "workflow": {"nodes": [], "links": []}}),
        ];
        for case in cases {
            assert!(
                plan_generation(&gen_args(case.clone()), None).is_err(),
                "should reject {case}"
            );
        }
        // Input image given to a text-to-image template.
        assert!(
            plan_generation(
                &gen_args(json!({"prompt": "x", "workflow": "flux"})),
                Some("a.png")
            )
            .is_err()
        );
        // controlnet without controlnet_name.
        assert!(
            plan_generation(
                &gen_args(json!({"prompt": "x", "workflow": "controlnet"})),
                Some("a.png")
            )
            .is_err()
        );
        // img2img with only one dimension.
        assert!(
            plan_generation(
                &gen_args(json!({"prompt": "x", "width": 512})),
                Some("a.png")
            )
            .is_err()
        );
    }

    #[test]
    fn plan_input_image_templates() {
        let p = plan_generation(
            &gen_args(json!({"prompt": "x", "denoise": 0.4})),
            Some("in.png"),
        )
        .unwrap();
        assert_eq!(p.template, "img2img");
        assert_eq!(p.workflow["8"]["inputs"]["image"], "in.png");
        assert_eq!(p.workflow["4"]["inputs"]["denoise"], 0.4);

        let p = plan_generation(
            &gen_args(json!({"prompt": "", "workflow": "upscale"})),
            Some("in.png"),
        )
        .unwrap();
        assert_eq!(p.template, "upscale");
        assert_eq!(
            p.workflow["16"]["inputs"]["model_name"],
            "4x-UltraSharp.pth"
        );
        assert_eq!(p.seed, None);

        let p = plan_generation(
            &gen_args(json!({
                "prompt": "x", "workflow": "controlnet", "controlnet_name": "cn.safetensors",
                "model_family": "sdxl", "control_strength": 0.6
            })),
            Some("edges.png"),
        )
        .unwrap();
        assert_eq!(p.family, Some(ModelFamily::Sdxl));
        assert_eq!(p.workflow["14"]["inputs"]["strength"], 0.6);
        assert_eq!(p.workflow["13"]["inputs"]["image"], "edges.png");
    }

    #[test]
    fn plan_custom_workflow_injects_and_warns() {
        let custom = workflows::sample_workflow("sdxl_default").unwrap();
        let p = plan_generation(
            &gen_args(json!({"prompt": "new prompt", "workflow": custom, "width": 512})),
            None,
        )
        .unwrap();
        assert_eq!(p.template, "custom");
        assert_eq!(p.workflow["2"]["inputs"]["text"], "new prompt");
        assert_eq!(p.injection.unwrap().positive_nodes, ["2"]);
        assert!(p.warnings[0].contains("width"));

        let p = plan_generation(
            &gen_args(
                json!({"prompt": "x", "workflow": {"1": {"class_type": "Foo", "inputs": {}}}}),
            ),
            None,
        )
        .unwrap();
        assert!(p.warnings[0].contains("not injected"));
    }

    #[test]
    fn flux_high_cfg_warns() {
        let p = plan_generation(&gen_args(json!({"prompt": "x", "cfg_scale": 7.0})), None).unwrap();
        assert!(p.warnings.iter().any(|w| w.contains("FLUX")));
    }

    #[test]
    fn prompt_id_validation() {
        assert!(validate_prompt_id("0b6f1c9e-1234-4abc-9def-000000000000").is_ok());
        assert!(validate_prompt_id("../object_info").is_err());
        assert!(validate_prompt_id("a?b").is_err());
        assert!(validate_prompt_id("").is_err());
        assert!(pick_prompt_id(None, None).is_err());
        assert_eq!(
            pick_prompt_id(Some("a".into()), Some("b".into())).unwrap(),
            "b"
        );
    }

    #[test]
    fn image_refs_and_prefixes() {
        assert!(validate_image_ref("in.png").is_ok());
        assert!(validate_image_ref("sub/in.png").is_ok());
        assert!(validate_image_ref("../in.png").is_err());
        assert!(validate_image_ref("/in.png").is_err());
        assert!(validate_image_ref("in.txt").is_err());
        assert!(validate_filename_prefix("ComfyUI").is_ok());
        assert!(validate_filename_prefix("runs/cats").is_ok());
        assert!(validate_filename_prefix("/abs").is_err());
        assert!(validate_filename_prefix("a/../b").is_err());
    }

    #[test]
    fn job_tracker_is_bounded() {
        let mut t = JobTracker::default();
        for i in 0..(MAX_TRACKED_JOBS + 10) {
            t.insert(
                format!("p{i}"),
                JobRecord {
                    tool: "x",
                    template: None,
                    prompt: None,
                    seed: None,
                    submitted_at_unix: 0,
                },
            );
        }
        assert_eq!(t.records.len(), MAX_TRACKED_JOBS);
        assert!(t.get("p0").is_none());
        assert!(t.get(&format!("p{}", MAX_TRACKED_JOBS + 9)).is_some());
    }

    #[test]
    fn object_info_summary() {
        let s = summarize_object_info(&json!({
            "KSampler": {"category": "sampling"},
            "CheckpointLoaderSimple": {"category": "loaders"},
            "LoraLoader": {"category": "loaders/lora"}
        }));
        assert_eq!(s["node_count"], 3);
        assert_eq!(s["node_classes"][0], "CheckpointLoaderSimple");
        assert_eq!(s["categories"]["loaders"], 2);
    }

    #[test]
    fn tool_set_is_complete_and_schemas_are_objects() {
        let server = ComfyUIServer::with_config(Config::default());
        let tools = server.tools();
        let mut names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        names.sort();
        assert_eq!(
            names,
            [
                "cancel_job",
                "download_lora",
                "execute_workflow",
                "generate_image",
                "get_image",
                "get_job_status",
                "get_object_info",
                "get_queue",
                "get_system_info",
                "get_workflow",
                "list_loras",
                "list_models",
                "list_workflows",
                "upload_image",
                "upload_lora"
            ]
        );
        for tool in &tools {
            let schema = tool.schema();
            assert_eq!(schema["type"], "object", "{}", tool.name());
            assert!(schema["properties"].is_object(), "{}", tool.name());
            assert!(!tool.description().is_empty());
        }
    }
}
