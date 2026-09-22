//! Rendering tools. All of them run as async jobs.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::server::{
    BlenderTool, Ctx, ToolError, ToolOutput, check_name, check_range, check_resolution, enum_prop,
    project_prop,
};
use crate::types::{ImageFormat, RenderEngine, VideoFormat};

/// Most frames a single animation/batch job may render.
const MAX_FRAMES: i64 = 100_000;

/// Render settings shared by the render tools (format type varies).
#[derive(Debug, Deserialize, Serialize)]
#[serde(bound(deserialize = "F: Deserialize<'de>"))]
pub struct RenderSettings<F> {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    resolution: Option<[u32; 2]>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    resolution_percentage: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    samples: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    engine: Option<RenderEngine>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    format: Option<F>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    use_gpu: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    denoise: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    film_transparent: Option<bool>,
}

impl<F> Default for RenderSettings<F> {
    fn default() -> Self {
        Self {
            resolution: None,
            resolution_percentage: None,
            samples: None,
            engine: None,
            format: None,
            use_gpu: None,
            denoise: None,
            film_transparent: None,
        }
    }
}

impl<F> RenderSettings<F> {
    fn validate(&self) -> Result<(), ToolError> {
        if let Some(res) = &self.resolution {
            check_resolution(res)?;
        }
        if let Some(pct) = self.resolution_percentage {
            check_range("settings.resolution_percentage", pct, 1, 100)?;
        }
        if let Some(samples) = self.samples {
            check_range("settings.samples", samples, 1, 65536)?;
        }
        Ok(())
    }
}

fn settings_schema(
    formats: &[&str],
    default_format: &str,
    default_engine: &str,
    default_samples: u32,
) -> Value {
    json!({
        "type": "object",
        "description": "Render settings (unset values keep the project's own settings)",
        "properties": {
            "resolution": { "type": "array", "items": { "type": "integer", "minimum": 1, "maximum": 16384 }, "minItems": 2, "maxItems": 2, "description": "[width, height]" },
            "resolution_percentage": { "type": "integer", "minimum": 1, "maximum": 100 },
            "samples": { "type": "integer", "minimum": 1, "default": default_samples },
            "engine": enum_prop(RenderEngine::ALL, Some(default_engine), "CYCLES works everywhere; EEVEE/Workbench need an OpenGL/EGL-capable host"),
            "format": enum_prop(formats, Some(default_format), "Output format"),
            "use_gpu": { "type": "boolean", "default": false, "description": "Cycles: render on the GPU" },
            "denoise": { "type": "boolean", "default": true, "description": "Cycles: denoise the result" },
            "film_transparent": { "type": "boolean", "description": "Transparent background" }
        }
    })
}

fn job_started(job_type: &str, job_id: uuid::Uuid, output_path: &str, extra: Value) -> Value {
    let mut out = json!({
        "success": true,
        "job_id": job_id.to_string(),
        "status": "QUEUED",
        "output_path": output_path,
        "message": format!("{job_type} job queued; poll get_job_status (use wait_seconds) and fetch get_job_result"),
    });
    if let (Some(out), Some(extra)) = (out.as_object_mut(), extra.as_object()) {
        out.extend(extra.clone());
    }
    out
}

/// `render_image` arguments.
#[derive(Debug, Deserialize)]
pub struct RenderImageArgs {
    project: String,
    #[serde(default = "one")]
    frame: i64,
    #[serde(default)]
    settings: RenderSettings<ImageFormat>,
}

fn one() -> i64 {
    1
}

/// Render one frame to an image.
pub struct RenderImage;

#[async_trait]
impl BlenderTool for RenderImage {
    type Args = RenderImageArgs;
    const NAME: &'static str = "render_image";
    const DESCRIPTION: &'static str = "Render a single frame to an image (PNG, JPEG, EXR or TIFF) using the scene's \
active camera. Runs as an async job: returns a job_id immediately; use get_job_status (wait_seconds) and \
get_job_result. The image is written to <output_dir>/renders/<job_id>.<ext>.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "frame": { "type": "integer", "default": 1, "description": "Frame to render" },
                "settings": settings_schema(ImageFormat::ALL, "PNG", "CYCLES", 128)
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        args.settings.validate()?;
        check_range("frame", args.frame, -MAX_FRAMES, MAX_FRAMES * 10)?;
        let format = args.settings.format.unwrap_or(ImageFormat::Png);

        let renders = ctx.config.output_dir.join("renders");
        let output_for = |id: uuid::Uuid| renders.join(format!("{id}.{}", format.extension()));
        let project_path = project.path.to_string_lossy().to_string();
        let frame = args.frame;
        let settings = args.settings;
        let id = ctx.start_job(Self::NAME, "render.py", &project, false, |id| {
            json!({
                "operation": "render_image",
                "project": project_path,
                "frame": frame,
                "settings": settings,
                "output_path": output_for(id).to_string_lossy(),
            })
        });
        let output_path = output_for(id);
        Ok(job_started(
            "Render",
            id,
            &output_path.to_string_lossy(),
            json!({ "frame": args.frame, "format": format }),
        ))
    }
}

/// `render_animation` arguments.
#[derive(Debug, Deserialize)]
pub struct RenderAnimationArgs {
    project: String,
    #[serde(default = "one")]
    start_frame: i64,
    #[serde(default = "default_end")]
    end_frame: i64,
    #[serde(default)]
    settings: RenderSettings<VideoFormat>,
}

fn default_end() -> i64 {
    250
}

/// Render a frame range to a video or image sequence.
pub struct RenderAnimation;

#[async_trait]
impl BlenderTool for RenderAnimation {
    type Args = RenderAnimationArgs;
    const NAME: &'static str = "render_animation";
    const DESCRIPTION: &'static str = "Render a frame range to a video (MP4/H.264, AVI, MOV, MKV, WEBM/VP9) or a PNG \
sequence (FRAMES). Runs as an async job with per-frame progress; use get_job_status (wait_seconds) and get_job_result. \
Output goes to <output_dir>/animations/<id>.<ext> (or that directory for FRAMES).";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "start_frame": { "type": "integer", "default": 1 },
                "end_frame": { "type": "integer", "default": 250 },
                "settings": settings_schema(VideoFormat::ALL, "MP4", "BLENDER_EEVEE", 64)
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        args.settings.validate()?;
        if args.end_frame < args.start_frame {
            return Err(ToolError::invalid(format!(
                "end_frame ({}) must be >= start_frame ({})",
                args.end_frame, args.start_frame
            )));
        }
        let frames = args.end_frame - args.start_frame + 1;
        check_range("frame count", frames, 1, MAX_FRAMES)?;
        let format = args.settings.format.unwrap_or(VideoFormat::Mp4);

        let animations = ctx.config.output_dir.join("animations");
        let project_path = project.path.to_string_lossy().to_string();
        let (start, end, settings) = (args.start_frame, args.end_frame, args.settings);
        let id = ctx.start_job(Self::NAME, "render.py", &project, false, |id| {
            json!({
                "operation": "render_animation",
                "project": project_path,
                "start_frame": start,
                "end_frame": end,
                "settings": settings,
                "output_path": animations.join(id.to_string()).to_string_lossy(),
            })
        });
        let base = animations
            .join(id.to_string())
            .to_string_lossy()
            .to_string();
        let output_path = if format == VideoFormat::Frames {
            base
        } else {
            format!("{base}.{}", format.as_str().to_ascii_lowercase())
        };
        Ok(job_started(
            "Animation render",
            id,
            &output_path,
            json!({ "frames": frames, "format": format }),
        ))
    }
}

/// `batch_render` arguments.
#[derive(Debug, Deserialize)]
pub struct BatchRenderArgs {
    project: String,
    #[serde(default)]
    frames: Option<Vec<i64>>,
    #[serde(default)]
    cameras: Vec<String>,
    #[serde(default)]
    layers: Vec<String>,
    #[serde(default)]
    settings: RenderSettings<ImageFormat>,
}

/// Render every combination of frames, cameras and view layers.
pub struct BatchRender;

#[async_trait]
impl BlenderTool for BatchRender {
    type Args = BatchRenderArgs;
    const NAME: &'static str = "batch_render";
    const DESCRIPTION: &'static str = "Render every combination of frames x cameras x view layers as separate images \
(named <camera>[_<layer>]_frame_NNNN.<ext>) into <output_dir>/batch/<id>/. Defaults: frame 1, the active camera, \
all enabled view layers composited. Runs as an async job; get_job_result lists output_files.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "project": project_prop(),
                "frames": { "type": "array", "items": { "type": "integer" }, "default": [1], "description": "Frames to render" },
                "cameras": { "type": "array", "items": { "type": "string" }, "description": "Camera objects to render from (default: active camera)" },
                "layers": { "type": "array", "items": { "type": "string" }, "description": "View layers to render one at a time (default: all together)" },
                "settings": settings_schema(ImageFormat::ALL, "PNG", "CYCLES", 128)
            },
            "required": ["project"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let project = ctx.project(&args.project)?;
        args.settings.validate()?;
        let frames = args.frames.unwrap_or_else(|| vec![1]);
        if frames.is_empty() {
            return Err(ToolError::invalid("frames must not be empty"));
        }
        for camera in &args.cameras {
            check_name("cameras", camera)?;
        }
        for layer in &args.layers {
            check_name("layers", layer)?;
        }
        let total = frames.len() as i64
            * args.cameras.len().max(1) as i64
            * args.layers.len().max(1) as i64;
        check_range("total images (frames x cameras x layers)", total, 1, 10_000)?;

        let batch = ctx.config.output_dir.join("batch");
        let project_path = project.path.to_string_lossy().to_string();
        let (cameras, layers, settings) = (args.cameras, args.layers, args.settings);
        let id = ctx.start_job(Self::NAME, "render.py", &project, false, |id| {
            json!({
                "operation": "batch_render",
                "project": project_path,
                "frames": frames,
                "cameras": cameras,
                "layers": layers,
                "settings": settings,
                "output_dir": batch.join(id.to_string()).to_string_lossy(),
            })
        });
        let output_dir = batch.join(id.to_string());
        Ok(job_started(
            "Batch render",
            id,
            &output_dir.to_string_lossy(),
            json!({ "images": total }),
        ))
    }
}
