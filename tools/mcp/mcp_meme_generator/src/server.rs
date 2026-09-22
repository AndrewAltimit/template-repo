//! MCP tool definitions for the meme generator.
//!
//! Tools share one [`AppState`]. The generator (templates + font) is loaded
//! lazily on first use on a blocking thread and can be swapped atomically by
//! `reload_meme_templates`. All rendering, encoding and file I/O runs under
//! `spawn_blocking`.
//!
//! Arguments are parsed into typed structs (`serde`), so a wrong type or a
//! missing required field is a clean `InvalidParameters` error. Domain
//! failures (unknown template, bad area id, ...) are returned as `isError`
//! results with a JSON body `{"success": false, "error": ...}`.

use async_trait::async_trait;
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use mcp_core::prelude::*;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::info;

use crate::fonts;
use crate::generator::{self, MemeGenerator, MemeRequest, OutputFormat};
use crate::templates::TemplateStore;
use crate::upload::{MAX_UPLOAD_BYTES, UploadService, Uploader};

/// Crate version reported by the status tool and the MCP handshake.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Static server configuration.
#[derive(Debug, Clone)]
pub struct ServerConfig {
    /// Directory containing `config/*.json` and template images.
    pub templates_dir: PathBuf,
    /// Where generated memes are written.
    pub output_dir: PathBuf,
    /// Optional explicit caption font.
    pub font_path: Option<PathBuf>,
    /// When false, every upload request is refused (offline / private mode).
    pub uploads_enabled: bool,
    /// Per-attempt upload timeout.
    pub upload_timeout: Duration,
}

/// State shared by all tools.
pub struct AppState {
    config: ServerConfig,
    generator: RwLock<Option<Arc<MemeGenerator>>>,
    uploader: Uploader,
}

type Shared = Arc<AppState>;

impl AppState {
    /// Create state; nothing is loaded until first use.
    pub fn new(config: ServerConfig) -> Shared {
        let uploader = Uploader::new(config.upload_timeout);
        Self::with_uploader(config, uploader)
    }

    /// Create state with a custom uploader (tests).
    pub fn with_uploader(config: ServerConfig, uploader: Uploader) -> Shared {
        Arc::new(Self {
            config,
            generator: RwLock::new(None),
            uploader,
        })
    }

    async fn load(&self) -> Result<Arc<MemeGenerator>> {
        let cfg = self.config.clone();
        let generator = tokio::task::spawn_blocking(move || {
            let font = fonts::load_font(cfg.font_path.as_deref())?;
            let store = TemplateStore::load(&cfg.templates_dir);
            Ok::<_, String>(MemeGenerator::new(store, font, cfg.output_dir))
        })
        .await
        .map_err(|e| MCPError::Internal(format!("generator init task failed: {e}")))?
        .map_err(MCPError::Internal)?;
        info!(
            "Meme generator ready: {} templates, font {}",
            generator.store().len(),
            generator.font_source()
        );
        Ok(Arc::new(generator))
    }

    /// Get the generator, initializing it on first use.
    async fn generator(&self) -> Result<Arc<MemeGenerator>> {
        if let Some(g) = self.generator.read().await.as_ref() {
            return Ok(Arc::clone(g));
        }
        let mut guard = self.generator.write().await;
        if let Some(g) = guard.as_ref() {
            return Ok(Arc::clone(g));
        }
        let g = self.load().await?;
        *guard = Some(Arc::clone(&g));
        Ok(g)
    }

    /// Reload templates and font from disk.
    async fn reload(&self) -> Result<Arc<MemeGenerator>> {
        let g = self.load().await?;
        *self.generator.write().await = Some(Arc::clone(&g));
        Ok(g)
    }
}

/// All tools, ready to register with the MCP server builder.
pub fn build_tools(state: &Shared) -> Vec<BoxedTool> {
    vec![
        Arc::new(GenerateMemeTool(Arc::clone(state))),
        Arc::new(ListMemeTemplatesTool(Arc::clone(state))),
        Arc::new(GetMemeTemplateInfoTool(Arc::clone(state))),
        Arc::new(MemeGeneratorStatusTool(Arc::clone(state))),
        Arc::new(UploadMemeTool(Arc::clone(state))),
        Arc::new(ReloadMemeTemplatesTool(Arc::clone(state))),
    ]
}

/// Deserialize tool arguments; `null`/absent arguments count as `{}`.
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

/// An `isError` result with a JSON body, so clients get structure either way.
fn error_result(body: Value) -> ToolResult {
    let text = serde_json::to_string_pretty(&body).unwrap_or_else(|_| body.to_string());
    ToolResult::error(text)
}

fn fail(message: impl std::fmt::Display) -> ToolResult {
    error_result(json!({"success": false, "error": message.to_string()}))
}

fn join_err(e: tokio::task::JoinError) -> MCPError {
    MCPError::Internal(format!("background task failed: {e}"))
}

fn kb(bytes: usize) -> f64 {
    (bytes as f64 / 1024.0 * 10.0).round() / 10.0
}

// ============================================================================
// generate_meme
// ============================================================================

#[derive(Debug, Deserialize)]
struct GenerateArgs {
    template: String,
    texts: BTreeMap<String, String>,
    #[serde(default)]
    font_size_override: Option<BTreeMap<String, i32>>,
    #[serde(default)]
    auto_resize: Option<bool>,
    #[serde(default)]
    upload: Option<bool>,
    #[serde(default)]
    upload_service: Option<UploadService>,
    #[serde(default)]
    output_format: Option<OutputFormat>,
    #[serde(default)]
    visual_feedback: Option<bool>,
}

struct GenerateMemeTool(Shared);

#[async_trait]
impl Tool for GenerateMemeTool {
    fn name(&self) -> &str {
        "generate_meme"
    }

    fn description(&self) -> &str {
        r#"Generate a meme by drawing captions onto a template image.

Call list_meme_templates first to pick a template, and get_meme_template_info to see its text area ids, usage rules and examples. Text is word-wrapped and (by default) shrunk to fit each area; explicit "\n" forces a line break. The file is saved to the server's output directory, a preview image is returned inline so you can check the result, and (by default) it is uploaded to a free host for a shareable URL (0x0.st, falling back to tmpfiles.org, then file.io).

Unknown template or area ids are errors (the message lists valid ids). Overflowing text, text over a template's recommended max_chars, and characters the font cannot draw are reported in "warnings"; if the upload fails the meme is still saved and "upload_error" explains why.

Example: {"template": "ol_reliable", "texts": {"top": "When the code won't compile", "bottom": "print('hello world')"}}"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "description": "Template id from list_meme_templates (e.g. 'ol_reliable', 'community_fire')"
                },
                "texts": {
                    "type": "object",
                    "description": "Caption per text area id, e.g. {\"top\": \"When...\", \"bottom\": \"Solution\"}. Areas you omit stay blank.",
                    "additionalProperties": {"type": "string", "maxLength": crate::render::MAX_TEXT_CHARS}
                },
                "font_size_override": {
                    "type": "object",
                    "description": "Fixed font size in px per area id (6-300), bypassing auto-fit for that area, e.g. {\"top\": 30}",
                    "additionalProperties": {"type": "integer", "minimum": 6, "maximum": 300}
                },
                "auto_resize": {
                    "type": "boolean",
                    "default": true,
                    "description": "Pick the largest font size (between the area's min and max) that fits. When false, the area's default size is used."
                },
                "upload": {
                    "type": "boolean",
                    "default": true,
                    "description": "Upload the meme to a public, no-auth host for a shareable URL. Uploaded images are publicly accessible."
                },
                "upload_service": {
                    "type": "string",
                    "enum": ["auto", "0x0st", "tmpfiles", "fileio"],
                    "default": "auto",
                    "description": "Upload host; 'auto' tries 0x0st, tmpfiles, fileio in order"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["png", "jpeg"],
                    "default": "png",
                    "description": "Saved file format. jpeg is several times smaller for photo templates."
                },
                "visual_feedback": {
                    "type": "boolean",
                    "default": true,
                    "description": "Return a downscaled JPEG preview (max 512px) as MCP image content"
                }
            },
            "required": ["template", "texts"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: GenerateArgs = parse_args(args)?;
        let state = &self.0;
        let upload = args.upload.unwrap_or(true);
        let service = args.upload_service.unwrap_or_default();
        let format = args.output_format.unwrap_or_default();
        let want_preview = args.visual_feedback.unwrap_or(true);
        let request = MemeRequest {
            template: args.template,
            texts: args.texts,
            font_size_override: args.font_size_override.unwrap_or_default(),
            auto_resize: args.auto_resize.unwrap_or(true),
        };

        let generator = state.generator().await?;
        let outcome = tokio::task::spawn_blocking(move || {
            let meme = generator.render(&request)?;
            let encoded = generator::encode(&meme.image, format)?;
            let path = generator.save(&meme.template, &encoded)?;
            let preview = if want_preview {
                Some(generator::preview(&meme.image)?)
            } else {
                None
            };
            Ok::<_, generator::MemeError>((
                meme.template,
                meme.areas,
                meme.warnings,
                encoded,
                path,
                preview,
            ))
        })
        .await
        .map_err(join_err)?;

        let (template, areas, warnings, encoded, path, preview) = match outcome {
            Ok(v) => v,
            Err(e) => return Ok(fail(e)),
        };

        let mut response = json!({
            "success": true,
            "template_used": template,
            "output_path": path.display().to_string(),
            "format": encoded.format,
            "width": encoded.width,
            "height": encoded.height,
            "size_kb": kb(encoded.bytes.len()),
            "areas": areas,
            "warnings": warnings,
        });

        if upload && !state.config.uploads_enabled {
            response["upload_skipped"] = json!(
                "Uploads are disabled on this server (--disable-upload / MCP_MEME_DISABLE_UPLOAD)"
            );
        } else if upload {
            let file_name = path
                .file_name()
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_else(|| format!("meme.{}", format.extension()));
            let result = state
                .uploader
                .upload(&encoded.bytes, &file_name, format.mime(), service)
                .await;
            if result.success {
                response["share_url"] = json!(result.url);
                if let Some(embed) = &result.embed_url {
                    response["embed_url"] = json!(embed);
                    response["markdown"] = json!(format!("![Meme]({embed})"));
                }
                response["upload_service"] = json!(result.service);
                response["upload_note"] = json!(result.note);
            } else {
                response["upload_error"] = json!(result.error);
            }
        }

        let mut content = Vec::new();
        if let Some(p) = preview {
            response["visual_feedback"] = json!({
                "format": "jpeg",
                "encoding": "base64",
                "delivered_as": "image content block",
                "width": p.width,
                "height": p.height,
                "size_kb": kb(p.bytes.len()),
            });
            content.push(Content::json(&response)?);
            content.push(Content::Image {
                data: BASE64.encode(&p.bytes),
                mime_type: p.format.mime().to_string(),
            });
        } else {
            content.push(Content::json(&response)?);
        }
        Ok(ToolResult::with_content(content))
    }
}

// ============================================================================
// list_meme_templates
// ============================================================================

struct ListMemeTemplatesTool(Shared);

#[async_trait]
impl Tool for ListMemeTemplatesTool {
    fn name(&self) -> &str {
        "list_meme_templates"
    }

    fn description(&self) -> &str {
        "List available meme templates: id, name, description, text area ids and image size. Use get_meme_template_info for usage rules and examples."
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let g = self.0.generator().await?;
        let templates = g.store().summaries();
        let mut response = json!({
            "success": true,
            "count": templates.len(),
            "templates": templates,
        });
        if !g.store().errors.is_empty() {
            response["load_errors"] = json!(g.store().errors);
        }
        ToolResult::json(&response)
    }
}

// ============================================================================
// get_meme_template_info
// ============================================================================

#[derive(Debug, Deserialize)]
struct TemplateInfoArgs {
    template_id: String,
}

struct GetMemeTemplateInfoTool(Shared);

#[async_trait]
impl Tool for GetMemeTemplateInfoTool {
    fn name(&self) -> &str {
        "get_meme_template_info"
    }

    fn description(&self) -> &str {
        "Get a template's full configuration: text areas (position, size, font range, recommended text, max_chars, usage), usage rules, cultural context, examples, image size, and a ready-to-use generate_meme example call."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "string",
                    "description": "Template id from list_meme_templates (e.g. 'ol_reliable')"
                }
            },
            "required": ["template_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: TemplateInfoArgs = parse_args(args)?;
        let g = self.0.generator().await?;
        let Some(t) = g.store().get(&args.template_id) else {
            return Ok(error_result(json!({
                "success": false,
                "error": format!("Template '{}' not found", args.template_id),
                "available_templates": g.store().ids(),
            })));
        };
        let example_texts: BTreeMap<String, String> = match t.config.examples.first() {
            Some(ex) => ex.texts.clone(),
            None => t
                .config
                .text_areas
                .iter()
                .map(|a| {
                    let text = a
                        .recommended_text
                        .clone()
                        .filter(|s| !s.is_empty())
                        .unwrap_or_else(|| a.id.to_uppercase());
                    (a.id.clone(), text)
                })
                .collect(),
        };
        ToolResult::json(&json!({
            "success": true,
            "id": t.id,
            "image_size": [t.width, t.height],
            "template": t.config,
            "example_call": {
                "tool": "generate_meme",
                "arguments": {"template": t.id, "texts": example_texts}
            }
        }))
    }
}

// ============================================================================
// meme_generator_status
// ============================================================================

struct MemeGeneratorStatusTool(Shared);

#[async_trait]
impl Tool for MemeGeneratorStatusTool {
    fn name(&self) -> &str {
        "meme_generator_status"
    }

    fn description(&self) -> &str {
        "Get server status: version, template count, template load errors/warnings, caption font, directories, and whether uploads are enabled."
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let state = &self.0;
        let cfg = &state.config;
        let mut response = json!({
            "server": "meme-generator",
            "version": VERSION,
            "templates_dir": cfg.templates_dir.display().to_string(),
            "output_dir": cfg.output_dir.display().to_string(),
            "uploads_enabled": cfg.uploads_enabled,
            "upload_timeout_secs": cfg.upload_timeout.as_secs_f32(),
        });
        match state.generator().await {
            Ok(g) => {
                response["initialized"] = json!(true);
                response["template_count"] = json!(g.store().len());
                response["templates"] = json!(g.store().ids());
                response["font"] = json!(g.font_source());
                response["load_errors"] = json!(g.store().errors);
                response["load_warnings"] = json!(g.store().warnings);
            },
            Err(e) => {
                response["initialized"] = json!(false);
                response["error"] = json!(e.to_string());
            },
        }
        ToolResult::json(&response)
    }
}

// ============================================================================
// reload_meme_templates
// ============================================================================

struct ReloadMemeTemplatesTool(Shared);

#[async_trait]
impl Tool for ReloadMemeTemplatesTool {
    fn name(&self) -> &str {
        "reload_meme_templates"
    }

    fn description(&self) -> &str {
        "Re-read templates (and the caption font) from disk, e.g. after adding or editing a template config. Returns the new template list and any load errors."
    }

    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {}})
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let g = match self.0.reload().await {
            Ok(g) => g,
            Err(e) => return Ok(fail(e)),
        };
        ToolResult::json(&json!({
            "success": true,
            "template_count": g.store().len(),
            "templates": g.store().ids(),
            "load_errors": g.store().errors,
            "load_warnings": g.store().warnings,
        }))
    }
}

// ============================================================================
// upload_meme
// ============================================================================

#[derive(Debug, Deserialize)]
struct UploadArgs {
    path: String,
    #[serde(default)]
    service: Option<UploadService>,
}

/// Extensions `upload_meme` accepts, with their MIME types.
const UPLOADABLE: &[(&str, &str)] = &[
    ("png", "image/png"),
    ("jpg", "image/jpeg"),
    ("jpeg", "image/jpeg"),
    ("webp", "image/webp"),
    ("gif", "image/gif"),
];

/// Resolve `requested` (a file name or path) to a canonical file inside
/// `output_dir`. Anything that escapes the directory (`..`, absolute paths
/// elsewhere, symlinks pointing out) is rejected.
pub fn resolve_output_file(
    output_dir: &Path,
    requested: &str,
) -> std::result::Result<PathBuf, String> {
    let requested = requested.trim();
    if requested.is_empty() {
        return Err("path is empty".into());
    }
    let root = output_dir.canonicalize().map_err(|e| {
        format!(
            "output directory {} is not accessible: {e}",
            output_dir.display()
        )
    })?;
    let candidate = Path::new(requested);
    let joined = if candidate.is_absolute() {
        candidate.to_path_buf()
    } else {
        root.join(candidate)
    };
    let resolved = joined
        .canonicalize()
        .map_err(|_| format!("file not found: {requested}"))?;
    if !resolved.starts_with(&root) {
        return Err(format!(
            "only files inside the output directory ({}) can be uploaded",
            root.display()
        ));
    }
    if !resolved.is_file() {
        return Err(format!("not a file: {requested}"));
    }
    Ok(resolved)
}

fn mime_for(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?.to_ascii_lowercase();
    UPLOADABLE
        .iter()
        .find(|(e, _)| *e == ext)
        .map(|(_, mime)| *mime)
}

struct UploadMemeTool(Shared);

#[async_trait]
impl Tool for UploadMemeTool {
    fn name(&self) -> &str {
        "upload_meme"
    }

    fn description(&self) -> &str {
        "Upload a previously generated meme (e.g. one made with upload=false, or after an upload failure) to a public no-auth host. Only image files inside the server's output directory can be uploaded; pass the file name or the output_path returned by generate_meme."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File name inside the output directory, or the absolute output_path from generate_meme"
                },
                "service": {
                    "type": "string",
                    "enum": ["auto", "0x0st", "tmpfiles", "fileio"],
                    "default": "auto",
                    "description": "Upload host; 'auto' tries each in order"
                }
            },
            "required": ["path"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let args: UploadArgs = parse_args(args)?;
        let state = &self.0;
        if !state.config.uploads_enabled {
            return Ok(fail(
                "Uploads are disabled on this server (--disable-upload / MCP_MEME_DISABLE_UPLOAD)",
            ));
        }
        let output_dir = state.config.output_dir.clone();
        let requested = args.path.clone();
        let read = tokio::task::spawn_blocking(move || {
            let path = resolve_output_file(&output_dir, &requested)?;
            let mime = mime_for(&path).ok_or_else(|| {
                let exts: Vec<&str> = UPLOADABLE.iter().map(|(e, _)| *e).collect();
                format!("unsupported file type; expected one of {exts:?}")
            })?;
            let size = std::fs::metadata(&path).map_err(|e| e.to_string())?.len();
            if size > MAX_UPLOAD_BYTES {
                return Err(format!(
                    "file is {size} bytes; the limit is {MAX_UPLOAD_BYTES}"
                ));
            }
            let bytes = std::fs::read(&path).map_err(|e| format!("cannot read file: {e}"))?;
            Ok((path, mime, bytes))
        })
        .await
        .map_err(join_err)?;
        let (path, mime, bytes) = match read {
            Ok(v) => v,
            Err(e) => return Ok(fail(e)),
        };

        let file_name = path
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "meme".into());
        let result = state
            .uploader
            .upload(&bytes, &file_name, mime, args.service.unwrap_or_default())
            .await;
        if !result.success {
            return Ok(error_result(json!({
                "success": false,
                "path": path.display().to_string(),
                "error": result.error,
            })));
        }
        let mut response = serde_json::to_value(&result)
            .map_err(|e| MCPError::SerializationError(e.to_string()))?;
        response["path"] = json!(path.display().to_string());
        if let Some(embed) = &result.embed_url {
            response["markdown"] = json!(format!("![Meme]({embed})"));
        }
        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::templates::tests::shipped_templates_dir;
    use crate::upload::Endpoints;
    use tokio::io::AsyncWriteExt;
    use tokio::net::TcpListener;

    fn config(output_dir: PathBuf, uploads_enabled: bool) -> ServerConfig {
        ServerConfig {
            templates_dir: shipped_templates_dir(),
            output_dir,
            font_path: None,
            uploads_enabled,
            upload_timeout: Duration::from_secs(5),
        }
    }

    fn state(output_dir: PathBuf) -> Shared {
        AppState::new(config(output_dir, false))
    }

    fn find<'a>(tools: &'a [BoxedTool], name: &str) -> &'a BoxedTool {
        tools.iter().find(|t| t.name() == name).unwrap()
    }

    fn body(result: &ToolResult) -> Value {
        match &result.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            other => panic!("expected text, got {other:?}"),
        }
    }

    #[test]
    fn registers_all_tools_with_object_schemas() {
        let s = state(PathBuf::from("unused"));
        let tools = build_tools(&s);
        let mut names: Vec<&str> = tools.iter().map(|t| t.name()).collect();
        names.sort_unstable();
        assert_eq!(
            names,
            vec![
                "generate_meme",
                "get_meme_template_info",
                "list_meme_templates",
                "meme_generator_status",
                "reload_meme_templates",
                "upload_meme",
            ]
        );
        for t in &tools {
            assert_eq!(t.schema()["type"], "object", "{}", t.name());
        }
        let gen_schema = find(&tools, "generate_meme").schema();
        assert_eq!(gen_schema["required"], json!(["template", "texts"]));
    }

    #[tokio::test]
    async fn generate_saves_file_and_returns_preview_image() {
        let dir = tempfile::tempdir().unwrap();
        let s = state(dir.path().to_path_buf());
        let tools = build_tools(&s);
        let result = find(&tools, "generate_meme")
            .execute(json!({
                "template": "ol_reliable",
                "texts": {"top": "When the code won't compile", "bottom": "print('hello')"},
                "upload": false
            }))
            .await
            .unwrap();
        assert!(!result.is_error);
        let b = body(&result);
        assert_eq!(b["success"], true);
        assert_eq!(b["format"], "png");
        assert_eq!(b["areas"].as_array().unwrap().len(), 2);
        let path = PathBuf::from(b["output_path"].as_str().unwrap());
        assert!(
            path.starts_with(dir.path().canonicalize().unwrap()) || path.starts_with(dir.path())
        );
        let saved = image::open(&path).unwrap();
        assert_eq!((saved.width(), saved.height()), (960, 1444));
        assert!(b.get("upload_error").is_none());
        match &result.content[1] {
            Content::Image { mime_type, data } => {
                assert_eq!(mime_type, "image/jpeg");
                let bytes = BASE64.decode(data).unwrap();
                assert!(image::load_from_memory(&bytes).is_ok());
            },
            other => panic!("expected image content, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn generate_jpeg_without_preview() {
        let dir = tempfile::tempdir().unwrap();
        let s = state(dir.path().to_path_buf());
        let tools = build_tools(&s);
        let result = find(&tools, "generate_meme")
            .execute(json!({
                "template": "one_does_not_simply",
                "texts": {"top": "ONE DOES NOT SIMPLY", "bottom": "SHIP ON FRIDAY"},
                "upload": false,
                "output_format": "jpeg",
                "visual_feedback": false
            }))
            .await
            .unwrap();
        assert_eq!(result.content.len(), 1);
        let b = body(&result);
        assert!(b["output_path"].as_str().unwrap().ends_with(".jpg"));
        assert!(b.get("visual_feedback").is_none());
    }

    #[tokio::test]
    async fn generate_reports_disabled_uploads() {
        let dir = tempfile::tempdir().unwrap();
        let s = state(dir.path().to_path_buf());
        let tools = build_tools(&s);
        let result = find(&tools, "generate_meme")
            .execute(json!({"template": "ol_reliable", "texts": {"top": "x"}}))
            .await
            .unwrap();
        let b = body(&result);
        assert_eq!(b["success"], true);
        assert!(b["upload_skipped"].as_str().unwrap().contains("disabled"));
    }

    #[tokio::test]
    async fn generate_domain_errors_are_tool_errors() {
        let dir = tempfile::tempdir().unwrap();
        let s = state(dir.path().to_path_buf());
        let tools = build_tools(&s);
        let tool = find(&tools, "generate_meme");

        let r = tool
            .execute(json!({"template": "drake", "texts": {"top": "x"}, "upload": false}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(body(&r)["error"].as_str().unwrap().contains("not found"));

        let r = tool
            .execute(json!({"template": "ol_reliable", "texts": {"left": "x"}, "upload": false}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(
            body(&r)["error"]
                .as_str()
                .unwrap()
                .contains("Unknown text area")
        );
        // Nothing was saved for failed requests.
        assert_eq!(
            std::fs::read_dir(dir.path())
                .map(|d| d.count())
                .unwrap_or(0),
            0
        );
    }

    #[tokio::test]
    async fn generate_bad_argument_types_are_invalid_parameters() {
        let s = state(PathBuf::from("unused"));
        let tools = build_tools(&s);
        let tool = find(&tools, "generate_meme");
        for args in [
            json!({}),
            json!({"template": "ol_reliable"}),
            json!({"template": 5, "texts": {}}),
            json!({"template": "ol_reliable", "texts": {"top": 5}}),
            json!({"template": "ol_reliable", "texts": {}, "upload_service": "imgur"}),
            json!({"template": "ol_reliable", "texts": {}, "output_format": "gif"}),
        ] {
            let err = tool.execute(args.clone()).await.unwrap_err();
            assert!(
                matches!(err, MCPError::InvalidParameters(_)),
                "{args}: {err:?}"
            );
        }
    }

    #[tokio::test]
    async fn list_and_info_tools() {
        let s = state(PathBuf::from("unused"));
        let tools = build_tools(&s);
        let list = body(
            &find(&tools, "list_meme_templates")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(list["count"], 8);
        let ids: Vec<&str> = list["templates"]
            .as_array()
            .unwrap()
            .iter()
            .map(|t| t["id"].as_str().unwrap())
            .collect();
        let mut sorted = ids.clone();
        sorted.sort_unstable();
        assert_eq!(ids, sorted, "list must be deterministic");

        let info_tool = find(&tools, "get_meme_template_info");
        let info = body(
            &info_tool
                .execute(json!({"template_id": "handshake_office"}))
                .await
                .unwrap(),
        );
        assert_eq!(info["image_size"], json!([521, 496]));
        assert_eq!(info["example_call"]["tool"], "generate_meme");
        assert!(info["example_call"]["arguments"]["texts"]["left"].is_string());

        let missing = info_tool
            .execute(json!({"template_id": "nope"}))
            .await
            .unwrap();
        assert!(missing.is_error);
        assert!(body(&missing)["available_templates"].is_array());
        assert!(matches!(
            info_tool.execute(json!({})).await.unwrap_err(),
            MCPError::InvalidParameters(_)
        ));
    }

    #[tokio::test]
    async fn status_and_reload() {
        let s = state(PathBuf::from("unused"));
        let tools = build_tools(&s);
        let status = body(
            &find(&tools, "meme_generator_status")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(status["version"], VERSION);
        assert_eq!(status["initialized"], true);
        assert_eq!(status["template_count"], 8);
        assert_eq!(status["uploads_enabled"], false);

        let reload = body(
            &find(&tools, "reload_meme_templates")
                .execute(json!({}))
                .await
                .unwrap(),
        );
        assert_eq!(reload["template_count"], 8);
    }

    #[test]
    fn resolve_output_file_blocks_escapes() {
        let root = tempfile::tempdir().unwrap();
        let out = root.path().join("out");
        std::fs::create_dir_all(&out).unwrap();
        std::fs::write(out.join("meme.png"), b"x").unwrap();
        std::fs::write(root.path().join("secret.png"), b"x").unwrap();

        assert!(resolve_output_file(&out, "meme.png").is_ok());
        let abs = out.join("meme.png");
        assert!(resolve_output_file(&out, abs.to_str().unwrap()).is_ok());

        let err = resolve_output_file(&out, "../secret.png").unwrap_err();
        assert!(err.contains("only files inside"), "{err}");
        let outside = root.path().join("secret.png");
        assert!(resolve_output_file(&out, outside.to_str().unwrap()).is_err());
        assert!(
            resolve_output_file(&out, "missing.png")
                .unwrap_err()
                .contains("not found")
        );
        assert!(resolve_output_file(&out, "").is_err());
        assert!(
            resolve_output_file(&out, ".")
                .unwrap_err()
                .contains("not a file")
        );
    }

    #[test]
    fn mime_detection() {
        assert_eq!(mime_for(Path::new("a.PNG")), Some("image/png"));
        assert_eq!(mime_for(Path::new("a.jpg")), Some("image/jpeg"));
        assert_eq!(mime_for(Path::new("a.txt")), None);
        assert_eq!(mime_for(Path::new("noext")), None);
    }

    #[tokio::test]
    async fn upload_tool_rejects_when_disabled_and_validates_paths() {
        let dir = tempfile::tempdir().unwrap();
        let s = state(dir.path().to_path_buf());
        let tools = build_tools(&s);
        let r = find(&tools, "upload_meme")
            .execute(json!({"path": "x.png"}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(body(&r)["error"].as_str().unwrap().contains("disabled"));

        let s = AppState::new(config(dir.path().to_path_buf(), true));
        let tools = build_tools(&s);
        std::fs::write(dir.path().join("notes.txt"), b"x").unwrap();
        let r = find(&tools, "upload_meme")
            .execute(json!({"path": "notes.txt"}))
            .await
            .unwrap();
        assert!(r.is_error);
        assert!(
            body(&r)["error"]
                .as_str()
                .unwrap()
                .contains("unsupported file type")
        );
        let r = find(&tools, "upload_meme")
            .execute(json!({"path": "../../etc/passwd"}))
            .await
            .unwrap();
        assert!(r.is_error);
    }

    /// Serve one canned 0x0.st-style response.
    async fn one_shot(body: &'static str) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            while let Ok((mut sock, _)) = listener.accept().await {
                tokio::spawn(async move {
                    use tokio::io::AsyncReadExt;
                    let mut buf = vec![0u8; 1 << 20];
                    // Read until the client has sent its request (best effort).
                    let _ = tokio::time::timeout(Duration::from_millis(500), async {
                        let mut total = Vec::new();
                        loop {
                            let n = sock.read(&mut buf).await.unwrap_or(0);
                            if n == 0 {
                                break;
                            }
                            total.extend_from_slice(&buf[..n]);
                            if total.windows(4).any(|w| w == b"--\r\n") {
                                break;
                            }
                        }
                    })
                    .await;
                    let reply = format!(
                        "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                        body.len()
                    );
                    let _ = sock.write_all(reply.as_bytes()).await;
                });
            }
        });
        format!("http://{addr}")
    }

    #[tokio::test]
    async fn generate_with_upload_returns_share_and_markdown() {
        let dir = tempfile::tempdir().unwrap();
        let base = one_shot("https://0x0.st/Xy.png\n").await;
        let uploader = Uploader::with_endpoints(
            Duration::from_secs(5),
            Endpoints {
                zero_x_zero: base.clone(),
                tmpfiles: base.clone(),
                fileio: base,
            },
        );
        let s = AppState::with_uploader(config(dir.path().to_path_buf(), true), uploader);
        let tools = build_tools(&s);
        let r = find(&tools, "generate_meme")
            .execute(json!({
                "template": "ol_reliable",
                "texts": {"top": "x"},
                "upload_service": "0x0st",
                "visual_feedback": false
            }))
            .await
            .unwrap();
        let b = body(&r);
        assert_eq!(b["share_url"], "https://0x0.st/Xy.png");
        assert_eq!(b["embed_url"], "https://0x0.st/Xy.png");
        assert_eq!(b["markdown"], "![Meme](https://0x0.st/Xy.png)");
        assert_eq!(b["upload_service"], "0x0.st");

        // And the standalone upload tool can re-upload the saved file.
        let path = b["output_path"].as_str().unwrap().to_string();
        let r = find(&tools, "upload_meme")
            .execute(json!({"path": path, "service": "0x0st"}))
            .await
            .unwrap();
        assert!(!r.is_error, "{r:?}");
        assert_eq!(body(&r)["url"], "https://0x0.st/Xy.png");
    }
}
