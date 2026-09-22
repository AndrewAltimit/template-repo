//! ComfyUI workflow (API-format prompt graph) construction and manipulation.
//!
//! Workflows are JSON objects mapping node ids to
//! `{"class_type": ..., "inputs": {...}}`; a link to another node's output is
//! the two-element array `[node_id, output_index]`.
//!
//! Node ids used by the built-in templates:
//!
//! | id | node |
//! |----|------|
//! | 1  | CheckpointLoaderSimple |
//! | 2  | CLIPTextEncode (positive) |
//! | 3  | CLIPTextEncode (negative) |
//! | 4  | KSampler |
//! | 5  | EmptyLatentImage |
//! | 6  | VAEDecode |
//! | 7  | SaveImage |
//! | 8  | LoadImage (img2img / upscale source) |
//! | 9  | VAEEncode |
//! | 10 | LoraLoader |
//! | 11 | ImageScale |
//! | 12 | ControlNetLoader |
//! | 13 | LoadImage (control image) |
//! | 14 | ControlNetApplyAdvanced |
//! | 15 | FluxGuidance |
//! | 16 | UpscaleModelLoader / ImageUpscaleWithModel pair (upscale only) |

use rand::Rng;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value, json};

/// Model family; decides sampler defaults and whether FLUX guidance is used.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ModelFamily {
    /// FLUX.1: CFG 1.0 with a `FluxGuidance` node, negative prompt ignored.
    Flux,
    /// SDXL / IllustriousXL / Pony: classic CFG sampling.
    Sdxl,
}

impl ModelFamily {
    /// Default checkpoint file for this family.
    pub fn default_checkpoint(self) -> &'static str {
        match self {
            ModelFamily::Flux => "flux1-dev-fp8.safetensors",
            ModelFamily::Sdxl => "illustriousXL_smoothftSOLID.safetensors",
        }
    }

    /// Default sampling steps.
    pub fn default_steps(self) -> u32 {
        match self {
            ModelFamily::Flux => 20,
            ModelFamily::Sdxl => 30,
        }
    }

    /// Default KSampler CFG. FLUX-dev must run at 1.0 (guidance comes from
    /// the `FluxGuidance` node instead); see
    /// `docs/integrations/creative-tools/ai-toolkit-comfyui.md`.
    pub fn default_cfg(self) -> f64 {
        match self {
            ModelFamily::Flux => 1.0,
            ModelFamily::Sdxl => 7.0,
        }
    }

    /// Default sampler name.
    pub fn default_sampler(self) -> &'static str {
        match self {
            ModelFamily::Flux => "heunpp2",
            ModelFamily::Sdxl => "dpmpp_2m",
        }
    }

    /// Default scheduler name.
    pub fn default_scheduler(self) -> &'static str {
        match self {
            ModelFamily::Flux => "simple",
            ModelFamily::Sdxl => "karras",
        }
    }

    /// Guess the family from a checkpoint file name.
    pub fn guess_from_checkpoint(name: &str) -> Option<Self> {
        let lower = name.to_ascii_lowercase();
        if lower.contains("flux") {
            Some(ModelFamily::Flux)
        } else if ["xl", "illustrious", "pony"]
            .iter()
            .any(|k| lower.contains(k))
        {
            Some(ModelFamily::Sdxl)
        } else {
            None
        }
    }
}

/// Default FLUX guidance strength.
pub const DEFAULT_FLUX_GUIDANCE: f64 = 3.5;
/// Default image edge length for the built-in templates.
pub const DEFAULT_SIZE: u32 = 1024;
/// Default upscale model.
pub const DEFAULT_UPSCALE_MODEL: &str = "4x-UltraSharp.pth";
/// Default img2img denoise strength.
pub const DEFAULT_DENOISE: f64 = 0.75;

/// Fully resolved sampling parameters shared by the templates.
#[derive(Debug, Clone, PartialEq)]
pub struct SamplingParams {
    /// Model family.
    pub family: ModelFamily,
    /// Positive prompt.
    pub prompt: String,
    /// Negative prompt (ignored by FLUX, but still wired as required).
    pub negative_prompt: String,
    /// Concrete seed (already resolved from `-1`).
    pub seed: u64,
    /// Sampling steps.
    pub steps: u32,
    /// KSampler CFG.
    pub cfg: f64,
    /// FLUX guidance (only used for [`ModelFamily::Flux`]).
    pub guidance: f64,
    /// Sampler name.
    pub sampler: String,
    /// Scheduler name.
    pub scheduler: String,
    /// Checkpoint file name.
    pub checkpoint: String,
    /// Optional LoRA `(file name, strength)`.
    pub lora: Option<(String, f64)>,
    /// Images per batch.
    pub batch_size: u32,
    /// Denoise strength (1.0 for text-to-image).
    pub denoise: f64,
    /// SaveImage filename prefix.
    pub filename_prefix: String,
}

impl SamplingParams {
    /// Family defaults with the given prompt and a random seed.
    pub fn defaults(family: ModelFamily, prompt: &str) -> Self {
        Self {
            family,
            prompt: prompt.to_string(),
            negative_prompt: String::new(),
            seed: random_seed(),
            steps: family.default_steps(),
            cfg: family.default_cfg(),
            guidance: DEFAULT_FLUX_GUIDANCE,
            sampler: family.default_sampler().to_string(),
            scheduler: family.default_scheduler().to_string(),
            checkpoint: family.default_checkpoint().to_string(),
            lora: None,
            batch_size: 1,
            denoise: 1.0,
            filename_prefix: "ComfyUI".to_string(),
        }
    }
}

/// A random seed in ComfyUI's accepted range (kept below 2^53 so it
/// round-trips exactly through JSON consumers that use f64).
pub fn random_seed() -> u64 {
    rand::thread_rng().gen_range(0..(1u64 << 53))
}

/// Resolve a user seed: `None` or `-1` means random; other negatives are invalid.
pub fn resolve_seed(seed: Option<i64>) -> Result<u64, String> {
    match seed {
        None | Some(-1) => Ok(random_seed()),
        Some(s) if s < 0 => Err(format!("seed must be >= 0, or -1 for random (got {s})")),
        Some(s) => Ok(s as u64),
    }
}

/// Model/CLIP/positive/negative link refs produced by [`base_graph`].
struct BaseGraph {
    nodes: Map<String, Value>,
    model: Value,
    positive: Value,
    negative: Value,
}

/// Checkpoint, optional LoRA, prompt encoders and (for FLUX) guidance.
fn base_graph(p: &SamplingParams) -> BaseGraph {
    let mut nodes = Map::new();
    nodes.insert(
        "1".into(),
        json!({"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": p.checkpoint}}),
    );

    let (model, clip) = match &p.lora {
        Some((name, strength)) => {
            nodes.insert(
                "10".into(),
                json!({
                    "class_type": "LoraLoader",
                    "inputs": {
                        "lora_name": name,
                        "strength_model": strength,
                        "strength_clip": strength,
                        "model": ["1", 0],
                        "clip": ["1", 1]
                    }
                }),
            );
            (json!(["10", 0]), json!(["10", 1]))
        },
        None => (json!(["1", 0]), json!(["1", 1])),
    };

    nodes.insert(
        "2".into(),
        json!({"class_type": "CLIPTextEncode", "inputs": {"text": p.prompt, "clip": clip}}),
    );
    nodes.insert(
        "3".into(),
        json!({"class_type": "CLIPTextEncode", "inputs": {"text": p.negative_prompt, "clip": clip}}),
    );

    let positive = if p.family == ModelFamily::Flux {
        nodes.insert(
            "15".into(),
            json!({
                "class_type": "FluxGuidance",
                "inputs": {"guidance": p.guidance, "conditioning": ["2", 0]}
            }),
        );
        json!(["15", 0])
    } else {
        json!(["2", 0])
    };

    BaseGraph {
        nodes,
        model,
        positive,
        negative: json!(["3", 0]),
    }
}

fn sampler_node(p: &SamplingParams, g: &BaseGraph, latent: Value) -> Value {
    json!({
        "class_type": "KSampler",
        "inputs": {
            "seed": p.seed,
            "steps": p.steps,
            "cfg": p.cfg,
            "sampler_name": p.sampler,
            "scheduler": p.scheduler,
            "denoise": p.denoise,
            "model": g.model,
            "positive": g.positive,
            "negative": g.negative,
            "latent_image": latent
        }
    })
}

fn decode_and_save(nodes: &mut Map<String, Value>, prefix: &str) {
    nodes.insert(
        "6".into(),
        json!({"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}}),
    );
    nodes.insert(
        "7".into(),
        json!({"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["6", 0]}}),
    );
}

/// Text-to-image workflow.
pub fn text_to_image(p: &SamplingParams, width: u32, height: u32) -> Value {
    let mut g = base_graph(p);
    g.nodes.insert(
        "5".into(),
        json!({
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": p.batch_size}
        }),
    );
    let sampler = sampler_node(p, &g, json!(["5", 0]));
    g.nodes.insert("4".into(), sampler);
    decode_and_save(&mut g.nodes, &p.filename_prefix);
    Value::Object(g.nodes)
}

/// Image-to-image workflow. `input_image` is a file name in ComfyUI's input
/// directory (see the `upload_image` tool). When `resize` is given the source
/// is rescaled before encoding.
pub fn image_to_image(p: &SamplingParams, input_image: &str, resize: Option<(u32, u32)>) -> Value {
    let mut g = base_graph(p);
    g.nodes.insert(
        "8".into(),
        json!({"class_type": "LoadImage", "inputs": {"image": input_image}}),
    );
    let pixels = match resize {
        Some((w, h)) => {
            g.nodes.insert(
                "11".into(),
                json!({
                    "class_type": "ImageScale",
                    "inputs": {
                        "upscale_method": "bicubic",
                        "width": w,
                        "height": h,
                        "crop": "center",
                        "image": ["8", 0]
                    }
                }),
            );
            json!(["11", 0])
        },
        None => json!(["8", 0]),
    };
    g.nodes.insert(
        "9".into(),
        json!({"class_type": "VAEEncode", "inputs": {"pixels": pixels, "vae": ["1", 2]}}),
    );
    let latent = if p.batch_size > 1 {
        g.nodes.insert(
            "5".into(),
            json!({
                "class_type": "RepeatLatentBatch",
                "inputs": {"samples": ["9", 0], "amount": p.batch_size}
            }),
        );
        json!(["5", 0])
    } else {
        json!(["9", 0])
    };
    let sampler = sampler_node(p, &g, latent);
    g.nodes.insert("4".into(), sampler);
    decode_and_save(&mut g.nodes, &p.filename_prefix);
    Value::Object(g.nodes)
}

/// ControlNet-guided text-to-image. `controlnet_name` must match the model
/// family of the checkpoint (e.g. an SDXL ControlNet for SDXL checkpoints).
pub fn controlnet(
    p: &SamplingParams,
    control_image: &str,
    controlnet_name: &str,
    strength: f64,
    width: u32,
    height: u32,
) -> Value {
    let mut g = base_graph(p);
    g.nodes.insert(
        "12".into(),
        json!({"class_type": "ControlNetLoader", "inputs": {"control_net_name": controlnet_name}}),
    );
    g.nodes.insert(
        "13".into(),
        json!({"class_type": "LoadImage", "inputs": {"image": control_image}}),
    );
    // ControlNetApplyAdvanced outputs (positive, negative); the legacy
    // ControlNetApply node has a single output and cannot feed both.
    g.nodes.insert(
        "14".into(),
        json!({
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "strength": strength,
                "start_percent": 0.0,
                "end_percent": 1.0,
                "positive": g.positive,
                "negative": g.negative,
                "control_net": ["12", 0],
                "image": ["13", 0]
            }
        }),
    );
    g.positive = json!(["14", 0]);
    g.negative = json!(["14", 1]);
    g.nodes.insert(
        "5".into(),
        json!({
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": p.batch_size}
        }),
    );
    let sampler = sampler_node(p, &g, json!(["5", 0]));
    g.nodes.insert("4".into(), sampler);
    decode_and_save(&mut g.nodes, &p.filename_prefix);
    Value::Object(g.nodes)
}

/// Model-based upscaling of an image in ComfyUI's input directory.
pub fn upscale(input_image: &str, upscale_model: &str, filename_prefix: &str) -> Value {
    json!({
        "16": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": upscale_model}},
        "8": {"class_type": "LoadImage", "inputs": {"image": input_image}},
        "17": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {"upscale_model": ["16", 0], "image": ["8", 0]}
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["17", 0]}
        }
    })
}

/// Kind of built-in template.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TemplateKind {
    /// Text-to-image.
    TextToImage,
    /// Image-to-image (needs an input image).
    ImageToImage,
    /// ControlNet (needs a control image and a ControlNet model).
    ControlNet,
    /// Upscale (needs an input image).
    Upscale,
}

/// Metadata for a built-in workflow template.
#[derive(Debug, Clone, Serialize)]
pub struct WorkflowTemplate {
    /// Template name (accepted by `get_workflow` and `generate_image.workflow`).
    pub name: &'static str,
    /// What it does.
    pub description: &'static str,
    /// Model type: `flux`, `sdxl`, `any` or `upscale`.
    pub model_type: &'static str,
    /// Extra `generate_image` parameters this template needs.
    pub requires: &'static [&'static str],
    /// Template kind.
    #[serde(skip)]
    pub kind: TemplateKind,
    /// Fixed family, if the template implies one.
    #[serde(skip)]
    pub family: Option<ModelFamily>,
}

/// All built-in templates.
pub const TEMPLATES: &[WorkflowTemplate] = &[
    WorkflowTemplate {
        name: "flux_default",
        description: "FLUX.1-dev text-to-image (cfg 1.0 + FluxGuidance, heunpp2/simple)",
        model_type: "flux",
        requires: &[],
        kind: TemplateKind::TextToImage,
        family: Some(ModelFamily::Flux),
    },
    WorkflowTemplate {
        name: "sdxl_default",
        description: "SDXL/IllustriousXL text-to-image (cfg 7, dpmpp_2m/karras)",
        model_type: "sdxl",
        requires: &[],
        kind: TemplateKind::TextToImage,
        family: Some(ModelFamily::Sdxl),
    },
    WorkflowTemplate {
        name: "flux_with_lora",
        description: "FLUX text-to-image with a LoRA applied to model and CLIP",
        model_type: "flux",
        requires: &["lora_name"],
        kind: TemplateKind::TextToImage,
        family: Some(ModelFamily::Flux),
    },
    WorkflowTemplate {
        name: "img2img",
        description: "Transform an uploaded image with a text prompt (denoise controls strength)",
        model_type: "any",
        requires: &["input_image or input_image_data"],
        kind: TemplateKind::ImageToImage,
        family: None,
    },
    WorkflowTemplate {
        name: "upscale",
        description: "Upscale an uploaded image with an upscale model (default 4x-UltraSharp)",
        model_type: "upscale",
        requires: &["input_image or input_image_data"],
        kind: TemplateKind::Upscale,
        family: None,
    },
    WorkflowTemplate {
        name: "controlnet",
        description: "ControlNet-guided generation from an uploaded control image",
        model_type: "any",
        requires: &["input_image or input_image_data", "controlnet_name"],
        kind: TemplateKind::ControlNet,
        family: None,
    },
];

/// Look up a template by name. `flux` and `sdxl` are accepted as aliases for
/// `flux_default` / `sdxl_default`.
pub fn find_template(name: &str) -> Option<&'static WorkflowTemplate> {
    let canonical = match name {
        "flux" => "flux_default",
        "sdxl" => "sdxl_default",
        other => other,
    };
    TEMPLATES.iter().find(|t| t.name == canonical)
}

/// Names accepted by [`find_template`], for error messages.
pub fn template_names() -> String {
    TEMPLATES
        .iter()
        .map(|t| t.name)
        .chain(["flux", "sdxl"])
        .collect::<Vec<_>>()
        .join(", ")
}

/// Build a template with sample parameters (placeholder image names).
pub fn sample_workflow(name: &str) -> Option<Value> {
    let template = find_template(name)?;
    let family = template.family.unwrap_or(ModelFamily::Flux);
    let mut p = SamplingParams::defaults(family, "A beautiful landscape");
    Some(match (template.kind, template.name) {
        (TemplateKind::TextToImage, "flux_with_lora") => {
            p.lora = Some(("your_lora.safetensors".to_string(), 1.0));
            text_to_image(&p, DEFAULT_SIZE, DEFAULT_SIZE)
        },
        (TemplateKind::TextToImage, _) => text_to_image(&p, DEFAULT_SIZE, DEFAULT_SIZE),
        (TemplateKind::ImageToImage, _) => {
            p.denoise = DEFAULT_DENOISE;
            p.filename_prefix = "ComfyUI_img2img".to_string();
            image_to_image(&p, "example.png", None)
        },
        (TemplateKind::ControlNet, _) => {
            p.filename_prefix = "ComfyUI_controlnet".to_string();
            controlnet(
                &p,
                "example.png",
                "your_flux_controlnet.safetensors",
                1.0,
                DEFAULT_SIZE,
                DEFAULT_SIZE,
            )
        },
        (TemplateKind::Upscale, _) => {
            upscale("example.png", DEFAULT_UPSCALE_MODEL, "ComfyUI_upscaled")
        },
    })
}

/// Validate that `workflow` is an API-format prompt graph.
///
/// Detects the UI/editor format (`{"nodes": [...], "links": [...]}`), which
/// ComfyUI's `/prompt` endpoint rejects with an unhelpful error.
pub fn validate_workflow(workflow: &Value) -> Result<(), String> {
    let obj = workflow
        .as_object()
        .ok_or_else(|| "workflow must be a JSON object of {node_id: node}".to_string())?;
    if obj.is_empty() {
        return Err("workflow is empty".to_string());
    }
    if obj.get("nodes").is_some_and(Value::is_array) {
        return Err(
            "workflow is in ComfyUI's UI format (has a 'nodes' array); export it with \
                    'Save (API Format)' / 'Export (API)' instead"
                .to_string(),
        );
    }
    for (id, node) in obj {
        let class_type = node
            .get("class_type")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty());
        if class_type.is_none() {
            return Err(format!(
                "workflow node {id:?} is missing a string 'class_type'"
            ));
        }
        if let Some(inputs) = node.get("inputs")
            && !inputs.is_object()
        {
            return Err(format!("workflow node {id:?} has non-object 'inputs'"));
        }
    }
    Ok(())
}

/// Which nodes received the injected prompts.
#[derive(Debug, Default, Clone, PartialEq, Serialize)]
pub struct InjectionReport {
    /// Node ids that received the positive prompt.
    pub positive_nodes: Vec<String>,
    /// Node ids that received the negative prompt.
    pub negative_nodes: Vec<String>,
    /// How targets were found: `sampler_links` or `heuristic`.
    pub method: &'static str,
}

/// Text inputs on the various CLIPTextEncode* nodes.
const TEXT_INPUTS: &[&str] = &["text", "text_g", "text_l", "clip_l", "t5xxl"];

fn is_text_encoder(node: &Value) -> bool {
    node.get("class_type")
        .and_then(Value::as_str)
        .is_some_and(|c| c.starts_with("CLIPTextEncode"))
        && node
            .get("inputs")
            .and_then(Value::as_object)
            .is_some_and(|i| {
                TEXT_INPUTS
                    .iter()
                    .any(|k| i.get(*k).is_some_and(Value::is_string))
            })
}

fn link_target(link: &Value) -> Option<&str> {
    let arr = link.as_array()?;
    if arr.len() != 2 {
        return None;
    }
    arr[0].as_str()
}

/// Follow a conditioning link back to the text encoder that produced it,
/// passing through conditioning modifiers (FluxGuidance, ControlNetApply*,
/// ConditioningSetArea, ...). `role` is `positive` or `negative`.
fn resolve_encoder(workflow: &Map<String, Value>, link: &Value, role: &str) -> Option<String> {
    let mut current = link_target(link)?.to_string();
    for _ in 0..32 {
        let node = workflow.get(&current)?;
        if is_text_encoder(node) {
            return Some(current);
        }
        let inputs = node.get("inputs")?.as_object()?;
        let next = inputs
            .get("conditioning")
            .and_then(link_target)
            .or_else(|| inputs.get(role).and_then(link_target))?;
        current = next.to_string();
    }
    None
}

fn set_text(node: &mut Value, text: &str) {
    if let Some(inputs) = node.get_mut("inputs").and_then(Value::as_object_mut) {
        for key in TEXT_INPUTS {
            if inputs.get(*key).is_some_and(Value::is_string) {
                inputs.insert((*key).to_string(), json!(text));
            }
        }
    }
}

fn numeric_order(ids: &mut [String]) {
    ids.sort_by_key(|id| (id.parse::<u64>().unwrap_or(u64::MAX), id.clone()));
}

/// Inject prompts into a custom workflow's text-encoder nodes.
///
/// Targets are found by following every node's `positive`/`negative` inputs
/// (KSampler, KSamplerAdvanced, SamplerCustom, ...) back to their
/// `CLIPTextEncode*` source. If the graph has no such links, falls back to a
/// heuristic: encoders whose current text looks like a negative prompt get
/// the negative, the first remaining encoder (by numeric id) gets the
/// positive, the next one the negative.
///
/// The negative text is only replaced when `negative` is `Some`, so a custom
/// workflow keeps its own negative prompt unless the caller overrides it.
pub fn inject_prompts(
    workflow: &mut Value,
    prompt: &str,
    negative: Option<&str>,
) -> InjectionReport {
    let mut report = InjectionReport {
        method: "sampler_links",
        ..Default::default()
    };
    let Some(obj) = workflow.as_object_mut() else {
        return report;
    };

    let mut positive = Vec::new();
    let mut negative_ids = Vec::new();
    for node in obj.values() {
        let Some(inputs) = node.get("inputs").and_then(Value::as_object) else {
            continue;
        };
        for (role, out) in [("positive", &mut positive), ("negative", &mut negative_ids)] {
            if let Some(link) = inputs.get(role)
                && let Some(id) = resolve_encoder(obj, link, role)
                && !out.contains(&id)
            {
                out.push(id);
            }
        }
    }
    // A node wired as both (rare, e.g. shared empty conditioning) stays positive.
    negative_ids.retain(|id| !positive.contains(id));

    if positive.is_empty() && negative_ids.is_empty() {
        report.method = "heuristic";
        let mut encoders: Vec<String> = obj
            .iter()
            .filter(|(_, n)| is_text_encoder(n))
            .map(|(id, _)| id.clone())
            .collect();
        numeric_order(&mut encoders);
        let looks_negative = |id: &String| {
            let node = &obj[id];
            let text = TEXT_INPUTS
                .iter()
                .find_map(|k| node["inputs"].get(*k).and_then(Value::as_str))
                .unwrap_or("")
                .to_lowercase();
            [
                "negative",
                "worst quality",
                "low quality",
                "bad anatomy",
                "blurry",
            ]
            .iter()
            .any(|k| text.contains(k))
        };
        let (neg, rest): (Vec<String>, Vec<String>) =
            encoders.into_iter().partition(looks_negative);
        let mut rest = rest.into_iter();
        if let Some(first) = rest.next() {
            positive.push(first);
        }
        negative_ids = neg;
        if negative_ids.is_empty()
            && let Some(second) = rest.next()
        {
            negative_ids.push(second);
        }
    }

    for id in &positive {
        if let Some(node) = obj.get_mut(id) {
            set_text(node, prompt);
        }
    }
    report.positive_nodes = positive;
    if let Some(neg) = negative {
        for id in &negative_ids {
            if let Some(node) = obj.get_mut(id) {
                set_text(node, neg);
            }
        }
        report.negative_nodes = negative_ids;
    }
    numeric_order(&mut report.positive_nodes);
    numeric_order(&mut report.negative_nodes);
    report
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params(family: ModelFamily) -> SamplingParams {
        let mut p = SamplingParams::defaults(family, "a cat");
        p.seed = 42;
        p
    }

    fn assert_links_resolve(wf: &Value) {
        let obj = wf.as_object().unwrap();
        for (id, node) in obj {
            for (input, value) in node["inputs"].as_object().unwrap() {
                if let Some(arr) = value.as_array()
                    && arr.len() == 2
                    && let Some(target) = arr[0].as_str()
                {
                    assert!(
                        obj.contains_key(target),
                        "node {id} input {input} links to missing node {target}"
                    );
                }
            }
        }
        validate_workflow(wf).unwrap();
    }

    #[test]
    fn flux_txt2img_uses_guidance_and_cfg_one() {
        let wf = text_to_image(&params(ModelFamily::Flux), 1024, 768);
        assert_links_resolve(&wf);
        assert_eq!(wf["15"]["class_type"], "FluxGuidance");
        assert_eq!(wf["15"]["inputs"]["guidance"], 3.5);
        assert_eq!(wf["4"]["inputs"]["positive"], json!(["15", 0]));
        assert_eq!(wf["4"]["inputs"]["cfg"], 1.0);
        assert_eq!(wf["4"]["inputs"]["seed"], 42);
        assert_eq!(wf["5"]["inputs"]["width"], 1024);
        assert_eq!(wf["5"]["inputs"]["height"], 768);
        assert_eq!(wf["1"]["inputs"]["ckpt_name"], "flux1-dev-fp8.safetensors");
    }

    #[test]
    fn sdxl_txt2img_has_no_guidance() {
        let wf = text_to_image(&params(ModelFamily::Sdxl), 1024, 1024);
        assert_links_resolve(&wf);
        assert!(wf.get("15").is_none());
        assert_eq!(wf["4"]["inputs"]["positive"], json!(["2", 0]));
        assert_eq!(wf["4"]["inputs"]["cfg"], 7.0);
        assert_eq!(wf["4"]["inputs"]["sampler_name"], "dpmpp_2m");
    }

    #[test]
    fn lora_rewires_model_and_clip() {
        let mut p = params(ModelFamily::Flux);
        p.lora = Some(("style.safetensors".into(), 0.8));
        let wf = text_to_image(&p, 512, 512);
        assert_links_resolve(&wf);
        assert_eq!(wf["10"]["inputs"]["lora_name"], "style.safetensors");
        assert_eq!(wf["4"]["inputs"]["model"], json!(["10", 0]));
        assert_eq!(wf["2"]["inputs"]["clip"], json!(["10", 1]));
        assert_eq!(wf["3"]["inputs"]["clip"], json!(["10", 1]));
    }

    #[test]
    fn img2img_graph() {
        let mut p = params(ModelFamily::Sdxl);
        p.denoise = 0.6;
        let wf = image_to_image(&p, "in.png", None);
        assert_links_resolve(&wf);
        assert_eq!(wf["8"]["inputs"]["image"], "in.png");
        assert!(wf["8"]["inputs"].get("upload").is_none());
        assert_eq!(wf["9"]["inputs"]["pixels"], json!(["8", 0]));
        assert_eq!(wf["4"]["inputs"]["latent_image"], json!(["9", 0]));
        assert_eq!(wf["4"]["inputs"]["denoise"], 0.6);

        let wf = image_to_image(&p, "in.png", Some((768, 512)));
        assert_links_resolve(&wf);
        assert_eq!(wf["9"]["inputs"]["pixels"], json!(["11", 0]));

        p.batch_size = 3;
        let wf = image_to_image(&p, "in.png", None);
        assert_links_resolve(&wf);
        assert_eq!(wf["4"]["inputs"]["latent_image"], json!(["5", 0]));
        assert_eq!(wf["5"]["inputs"]["amount"], 3);
    }

    #[test]
    fn controlnet_uses_advanced_apply_for_both_conditionings() {
        let wf = controlnet(
            &params(ModelFamily::Flux),
            "c.png",
            "cn.safetensors",
            0.7,
            1024,
            1024,
        );
        assert_links_resolve(&wf);
        assert_eq!(wf["14"]["class_type"], "ControlNetApplyAdvanced");
        assert_eq!(wf["14"]["inputs"]["positive"], json!(["15", 0]));
        assert_eq!(wf["4"]["inputs"]["positive"], json!(["14", 0]));
        assert_eq!(wf["4"]["inputs"]["negative"], json!(["14", 1]));
    }

    #[test]
    fn upscale_graph() {
        let wf = upscale("in.png", "4x.pth", "up");
        assert_links_resolve(&wf);
        assert_eq!(wf["7"]["inputs"]["images"], json!(["17", 0]));
    }

    #[test]
    fn every_template_has_a_valid_sample() {
        for t in TEMPLATES {
            let wf = sample_workflow(t.name).unwrap();
            assert_links_resolve(&wf);
        }
        assert!(sample_workflow("flux").is_some());
        assert!(sample_workflow("nope").is_none());
        assert!(template_names().contains("controlnet"));
    }

    #[test]
    fn seeds() {
        assert_eq!(resolve_seed(Some(7)).unwrap(), 7);
        assert!(resolve_seed(Some(-1)).unwrap() < (1 << 53));
        assert!(resolve_seed(None).is_ok());
        assert!(resolve_seed(Some(-5)).is_err());
    }

    #[test]
    fn family_guess() {
        assert_eq!(
            ModelFamily::guess_from_checkpoint("flux1-schnell.safetensors"),
            Some(ModelFamily::Flux)
        );
        assert_eq!(
            ModelFamily::guess_from_checkpoint("ponyDiffusionV6XL.safetensors"),
            Some(ModelFamily::Sdxl)
        );
        assert_eq!(ModelFamily::guess_from_checkpoint("v1-5-pruned.ckpt"), None);
    }

    #[test]
    fn validate_rejects_bad_shapes() {
        assert!(validate_workflow(&json!("flux")).is_err());
        assert!(validate_workflow(&json!({})).is_err());
        let ui = json!({"nodes": [], "links": []});
        assert!(validate_workflow(&ui).unwrap_err().contains("API Format"));
        assert!(validate_workflow(&json!({"1": {"inputs": {}}})).is_err());
        assert!(validate_workflow(&json!({"1": {"class_type": "X", "inputs": 3}})).is_err());
        assert!(validate_workflow(&json!({"1": {"class_type": "X", "inputs": {}}})).is_ok());
    }

    #[test]
    fn inject_follows_sampler_links_through_guidance() {
        // Node ids chosen so lexicographic order would pick the wrong node.
        let mut wf = json!({
            "10": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative", "clip": ["1", 1]}},
            "9":  {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive, bad lighting", "clip": ["1", 1]}},
            "15": {"class_type": "FluxGuidance", "inputs": {"guidance": 3.5, "conditioning": ["9", 0]}},
            "4":  {"class_type": "KSampler", "inputs": {"positive": ["15", 0], "negative": ["10", 0]}}
        });
        let report = inject_prompts(&mut wf, "a dog", Some("ugly"));
        assert_eq!(report.method, "sampler_links");
        assert_eq!(report.positive_nodes, ["9"]);
        assert_eq!(report.negative_nodes, ["10"]);
        assert_eq!(wf["9"]["inputs"]["text"], "a dog");
        assert_eq!(wf["10"]["inputs"]["text"], "ugly");
    }

    #[test]
    fn inject_keeps_negative_when_not_given() {
        let mut wf = text_to_image(&params(ModelFamily::Sdxl), 512, 512);
        wf["3"]["inputs"]["text"] = json!("keep me");
        let report = inject_prompts(&mut wf, "new", None);
        assert_eq!(report.positive_nodes, ["2"]);
        assert!(report.negative_nodes.is_empty());
        assert_eq!(wf["2"]["inputs"]["text"], "new");
        assert_eq!(wf["3"]["inputs"]["text"], "keep me");
    }

    #[test]
    fn inject_through_controlnet_roles() {
        let mut wf = controlnet(&params(ModelFamily::Sdxl), "c.png", "cn", 1.0, 512, 512);
        let report = inject_prompts(&mut wf, "pos", Some("neg"));
        assert_eq!(report.positive_nodes, ["2"]);
        assert_eq!(report.negative_nodes, ["3"]);
    }

    #[test]
    fn inject_heuristic_without_sampler() {
        let mut wf = json!({
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "worst quality, blurry"}},
            "11": {"class_type": "CLIPTextEncode", "inputs": {"text": "something"}},
            "3": {"class_type": "CLIPTextEncodeSDXL", "inputs": {"text_g": "a", "text_l": "b"}}
        });
        let report = inject_prompts(&mut wf, "pos", Some("neg"));
        assert_eq!(report.method, "heuristic");
        assert_eq!(report.positive_nodes, ["3"]);
        assert_eq!(report.negative_nodes, ["2"]);
        assert_eq!(wf["3"]["inputs"]["text_g"], "pos");
        assert_eq!(wf["3"]["inputs"]["text_l"], "pos");
        assert_eq!(wf["2"]["inputs"]["text"], "neg");
        assert_eq!(wf["11"]["inputs"]["text"], "something");
    }

    #[test]
    fn inject_on_non_object_is_noop() {
        let mut wf = json!([1, 2]);
        let report = inject_prompts(&mut wf, "x", Some("y"));
        assert!(report.positive_nodes.is_empty());
    }
}
