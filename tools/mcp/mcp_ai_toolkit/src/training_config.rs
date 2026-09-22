//! Building and validating AI Toolkit training configs.
//!
//! [`build_config`] turns the typed `create_training_config` arguments into a
//! [`TrainingConfig`] with model-aware defaults; [`validate_config_yaml`]
//! statically checks any config YAML (including hand-written ones) before a
//! training run is started. Both are pure functions over the filesystem layout
//! so they can be unit tested without a GPU.

use serde::Deserialize;
use std::path::{Component, Path, PathBuf};

use crate::config::{AIToolkitPaths, validate_name, validate_path};
use crate::datasets::scan_dataset;
use crate::types::*;

/// Supported optimizers (validated in addition to the JSON-schema enum).
pub const OPTIMIZERS: &[&str] = &["adamw", "adamw8bit", "prodigy", "lion", "adafactor"];
/// Supported noise schedulers.
pub const SCHEDULERS: &[&str] = &["ddpm", "ddim", "flowmatch", "euler", "euler_a"];

/// Typed arguments of the `create_training_config` tool.
#[derive(Debug, Clone, Default, Deserialize)]
pub struct CreateConfigArgs {
    pub name: String,
    pub dataset_path: String,
    pub preset: Option<String>,
    pub model_name: Option<String>,
    pub resolution: Option<Resolution>,
    pub steps: Option<u32>,
    pub batch_size: Option<u32>,
    pub rank: Option<u32>,
    pub alpha: Option<u32>,
    pub lr: Option<f64>,
    pub optimizer: Option<String>,
    pub noise_scheduler: Option<String>,
    pub trigger_word: Option<String>,
    pub prompts: Option<Vec<String>>,
    pub is_flux: Option<bool>,
    pub is_xl: Option<bool>,
    pub is_v3: Option<bool>,
    pub quantize: Option<bool>,
    pub gradient_checkpointing: Option<bool>,
    pub cache_latents: Option<bool>,
    pub caption_dropout_rate: Option<f32>,
    pub save_every: Option<u32>,
    pub sample_every: Option<u32>,
    pub disable_sampling: Option<bool>,
    pub low_vram: Option<bool>,
    pub overwrite: Option<bool>,
}

/// Model architecture flags derived from arguments / model name.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Arch {
    pub is_flux: bool,
    pub is_xl: bool,
    pub is_v3: bool,
}

impl Arch {
    /// Flow-matching architectures (Flux, SD3).
    pub fn is_flow(self) -> bool {
        self.is_flux || self.is_v3
    }
}

/// Guess the architecture from a Hugging Face model id or path.
///
/// Explicit flags always win; this is only the fallback. Detection is
/// mutually exclusive in priority order Flux > SD3 > SDXL.
pub fn detect_arch(model_name: &str) -> Arch {
    let lower = model_name.to_ascii_lowercase();
    let is_flux = lower.contains("flux");
    let is_v3 = !is_flux
        && (lower.contains("stable-diffusion-3")
            || lower.contains("sd3")
            || lower.contains("sd-3")
            || lower.contains("sd_3"));
    let is_xl = !is_flux && !is_v3 && lower.contains("xl");
    Arch {
        is_flux,
        is_xl,
        is_v3,
    }
}

/// Result of [`build_config`].
#[derive(Debug)]
pub struct BuiltConfig {
    pub config: TrainingConfig,
    pub dataset_folder: PathBuf,
    pub arch: Arch,
    pub warnings: Vec<String>,
}

/// Resolve the `dataset_path` argument to a folder.
///
/// - a bare name (`my_dataset`) -> `<datasets>/my_dataset`
/// - an absolute path -> used as-is (must not contain `..`)
/// - a relative path with separators -> relative to the AI Toolkit checkout
pub fn resolve_dataset_path(paths: &AIToolkitPaths, raw: &str) -> Result<PathBuf, String> {
    let raw = raw.trim();
    if raw.is_empty() {
        return Err("dataset_path must not be empty".into());
    }
    let normalized = raw.replace('\\', "/");
    let as_path = Path::new(&normalized);
    if as_path.is_absolute() || normalized.starts_with('/') {
        if as_path.components().any(|c| c == Component::ParentDir) {
            return Err("dataset_path must not contain '..' components".into());
        }
        return Ok(PathBuf::from(raw));
    }
    if !normalized.contains('/') {
        return paths
            .dataset_dir(&normalized)
            .map_err(|e| format!("Invalid dataset name: {e}"));
    }
    validate_path(&normalized, &paths.base_path, "dataset").map_err(|e| e.to_string())
}

/// Build an AI Toolkit config from typed arguments.
pub fn build_config(
    paths: &AIToolkitPaths,
    args: &CreateConfigArgs,
) -> Result<BuiltConfig, String> {
    validate_name(&args.name, "config").map_err(|e| format!("Invalid config name: {e}"))?;
    let mut warnings = Vec::new();

    let preset = match &args.preset {
        Some(id) => Some(ModelPreset::by_id(id).ok_or_else(|| {
            let ids: Vec<_> = ModelPreset::all_presets()
                .into_iter()
                .map(|p| p.id)
                .collect();
            format!("Unknown preset '{id}'. Available: {}", ids.join(", "))
        })?),
        None => None,
    };

    let model_name = args
        .model_name
        .clone()
        .or_else(|| preset.as_ref().map(|p| p.model_path.clone()))
        .unwrap_or_else(|| "runwayml/stable-diffusion-v1-5".to_string());
    if model_name.trim().is_empty() {
        return Err("model_name must not be empty".into());
    }

    let detected = match (&preset, &args.model_name) {
        (Some(p), None) => Arch {
            is_flux: p.is_flux,
            is_xl: p.is_xl,
            is_v3: p.is_v3,
        },
        _ => detect_arch(&model_name),
    };
    let arch = Arch {
        is_flux: args.is_flux.unwrap_or(detected.is_flux),
        is_xl: args.is_xl.unwrap_or(detected.is_xl),
        is_v3: args.is_v3.unwrap_or(detected.is_v3),
    };
    if [arch.is_flux, arch.is_xl, arch.is_v3]
        .iter()
        .filter(|f| **f)
        .count()
        > 1
    {
        return Err("At most one of is_flux, is_xl, is_v3 may be true".into());
    }

    // Resolution
    let resolution = args.resolution.clone().unwrap_or_else(|| {
        if arch.is_flow() {
            Resolution::Multiple(vec![512, 768, 1024])
        } else if arch.is_xl {
            Resolution::Single(1024)
        } else {
            Resolution::Single(512)
        }
    });
    let res_values: Vec<u32> = match &resolution {
        Resolution::Single(r) => vec![*r],
        Resolution::Multiple(v) => v.clone(),
    };
    if res_values.is_empty() {
        return Err("resolution array must not be empty".into());
    }
    for r in &res_values {
        if !(128..=4096).contains(r) {
            return Err(format!("resolution {r} out of range (128-4096)"));
        }
        if r % 64 != 0 {
            warnings.push(format!(
                "resolution {r} is not a multiple of 64; AI Toolkit will bucket it down"
            ));
        }
    }

    // Numeric hyper-parameters
    let steps = args.steps.unwrap_or(2000);
    if !(1..=1_000_000).contains(&steps) {
        return Err("steps must be between 1 and 1000000".into());
    }
    let batch_size = args.batch_size.unwrap_or(1);
    if !(1..=64).contains(&batch_size) {
        return Err("batch_size must be between 1 and 64".into());
    }
    let rank = args.rank.unwrap_or(16);
    if !(1..=1024).contains(&rank) {
        return Err("rank must be between 1 and 1024".into());
    }
    let alpha = args.alpha.unwrap_or(rank);
    if !(1..=1024).contains(&alpha) {
        return Err("alpha must be between 1 and 1024".into());
    }
    let lr = args.lr.unwrap_or(1e-4);
    if !lr.is_finite() || lr <= 0.0 || lr > 1.0 {
        return Err("lr must be a positive number <= 1.0".into());
    }
    if lr > 1e-2 {
        warnings.push(format!("lr {lr} is unusually high for LoRA training"));
    }
    let caption_dropout_rate = args.caption_dropout_rate.unwrap_or(0.05);
    if !(0.0..=1.0).contains(&caption_dropout_rate) {
        return Err("caption_dropout_rate must be between 0.0 and 1.0".into());
    }
    let save_every = args.save_every.unwrap_or(250).max(1);
    let sample_every = args.sample_every.unwrap_or(250).max(1);

    let optimizer = args
        .optimizer
        .clone()
        .unwrap_or_else(|| if arch.is_flow() { "adamw8bit" } else { "adamw" }.to_string());
    if !OPTIMIZERS.contains(&optimizer.as_str()) {
        return Err(format!(
            "Unsupported optimizer '{optimizer}'. Use one of: {}",
            OPTIMIZERS.join(", ")
        ));
    }
    let noise_scheduler = args
        .noise_scheduler
        .clone()
        .unwrap_or_else(|| if arch.is_flow() { "flowmatch" } else { "ddpm" }.to_string());
    if !SCHEDULERS.contains(&noise_scheduler.as_str()) {
        return Err(format!(
            "Unsupported noise_scheduler '{noise_scheduler}'. Use one of: {}",
            SCHEDULERS.join(", ")
        ));
    }
    if arch.is_flow() && noise_scheduler != "flowmatch" {
        warnings.push("Flux/SD3 models normally require noise_scheduler 'flowmatch'".into());
    }

    let quantize = args.quantize.unwrap_or(arch.is_flow());
    let dataset_folder = resolve_dataset_path(paths, &args.dataset_path)?;
    if !dataset_folder.is_dir() {
        warnings.push(format!(
            "Dataset folder does not exist yet: {}",
            dataset_folder.display()
        ));
    }

    let trigger_word = args
        .trigger_word
        .as_ref()
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty());
    let prompts = args
        .prompts
        .clone()
        .filter(|p| !p.is_empty())
        .unwrap_or_else(|| {
            let t = trigger_word
                .as_deref()
                .map(|t| format!("{t}, "))
                .unwrap_or_default();
            vec![
                format!("{t}a woman holding a coffee cup, in a beanie, sitting at a cafe"),
                format!("{t}a man showing off his cool new t-shirt at the beach"),
            ]
        });

    let sample_size = res_values.iter().copied().max().unwrap_or(1024);

    let config = TrainingConfig {
        job: "extension".to_string(),
        config: ConfigDetails {
            name: args.name.clone(),
            process: vec![ProcessConfig {
                process_type: "sd_trainer".to_string(),
                // Absolute so trained weights land where list_exported_models looks.
                training_folder: paths.outputs_path.display().to_string(),
                device: "cuda:0".to_string(),
                trigger_word,
                performance_log_every: None,
                network: NetworkConfig {
                    network_type: "lora".to_string(),
                    linear: rank,
                    linear_alpha: alpha,
                    conv: None,
                    conv_alpha: None,
                    dropout: None,
                    // Only meaningful for transformer (Flux/SD3) backbones.
                    transformer_only: arch.is_flow().then_some(true),
                },
                save: SaveConfig {
                    dtype: "float16".to_string(),
                    save_every,
                    max_step_saves_to_keep: 4,
                    push_to_hub: false,
                    hf_repo_id: None,
                    hf_private: None,
                },
                datasets: vec![DatasetConfig {
                    folder_path: dataset_folder.display().to_string(),
                    caption_ext: "txt".to_string(),
                    caption_dropout_rate,
                    shuffle_tokens: false,
                    cache_latents_to_disk: args.cache_latents.unwrap_or(true),
                    resolution,
                    default_caption: None,
                    is_reg: false,
                    network_weight: None,
                }],
                train: TrainConfig {
                    batch_size,
                    steps,
                    gradient_accumulation_steps: 1,
                    train_unet: true,
                    train_text_encoder: false,
                    gradient_checkpointing: args.gradient_checkpointing.unwrap_or(true),
                    noise_scheduler: noise_scheduler.clone(),
                    optimizer,
                    lr,
                    skip_first_sample: false,
                    disable_sampling: args.disable_sampling.unwrap_or(false),
                    linear_timesteps: false,
                    dtype: if arch.is_flow() { "bf16" } else { "fp16" }.to_string(),
                    ema_config: EmaConfig {
                        use_ema: true,
                        ema_decay: 0.99,
                    },
                    max_grad_norm: None,
                    noise_offset: None,
                },
                model: ModelConfig {
                    name_or_path: model_name,
                    is_flux: arch.is_flux,
                    is_v2: false,
                    is_v3: arch.is_v3,
                    is_xl: arch.is_xl,
                    is_v_pred: false,
                    quantize,
                    low_vram: args.low_vram.unwrap_or(false),
                },
                sample: SampleConfig {
                    sampler: noise_scheduler,
                    sample_every,
                    width: sample_size,
                    height: sample_size,
                    prompts,
                    neg: String::new(),
                    seed: 42,
                    walk_seed: true,
                    guidance_scale: if arch.is_flux { 4.0 } else { 7.5 },
                    sample_steps: 20,
                },
                logging: Some(LoggingConfig {
                    log_every: 100,
                    verbose: false,
                    use_wandb: false,
                    use_ui_logger: false,
                    project_name: None,
                    run_name: None,
                }),
            }],
        },
        meta: Some(ConfigMeta {
            // AI Toolkit substitutes "[name]" with config.name.
            name: "[name]".to_string(),
            version: "1.0".to_string(),
        }),
    };

    Ok(BuiltConfig {
        config,
        dataset_folder,
        arch,
        warnings,
    })
}

/// Outcome of [`validate_config_yaml`].
#[derive(Debug, Default, serde::Serialize)]
pub struct Validation {
    pub valid: bool,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
}

/// Facts extracted from a config that the job runner needs.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ConfigSummary {
    /// `config.name` (AI Toolkit's output sub-folder name).
    pub run_name: Option<String>,
    /// `config.process[0].training_folder`, resolved against the base path.
    pub training_folder: Option<PathBuf>,
    /// `config.process[0].train.steps`.
    pub steps: Option<u32>,
}

/// Extract [`ConfigSummary`] from parsed YAML.
pub fn summarize_config(paths: &AIToolkitPaths, cfg: &serde_yaml::Value) -> ConfigSummary {
    let process = cfg
        .get("config")
        .and_then(|c| c.get("process"))
        .and_then(|p| p.as_sequence())
        .and_then(|s| s.first());
    let run_name = cfg
        .get("config")
        .and_then(|c| c.get("name"))
        .and_then(|n| n.as_str())
        .map(String::from);
    let training_folder = process
        .and_then(|p| p.get("training_folder"))
        .and_then(|t| t.as_str())
        .map(|t| resolve_against(&paths.base_path, t));
    let steps = process
        .and_then(|p| p.get("train"))
        .and_then(|t| t.get("steps"))
        .and_then(|s| s.as_u64())
        .and_then(|s| u32::try_from(s).ok());
    ConfigSummary {
        run_name,
        training_folder,
        steps,
    }
}

fn resolve_against(base: &Path, p: &str) -> PathBuf {
    let path = Path::new(p);
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        base.join(path)
    }
}

/// Statically validate an AI Toolkit config.
///
/// Checks structure, architecture flag conflicts, hyper-parameter sanity, and
/// that every dataset folder exists and contains images. Performs blocking
/// filesystem reads; call from `spawn_blocking` in async contexts.
pub fn validate_config_yaml(paths: &AIToolkitPaths, cfg: &serde_yaml::Value) -> Validation {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();

    if cfg.get("job").is_none() {
        errors.push("Missing required key: 'job'".to_string());
    }
    let Some(config) = cfg.get("config") else {
        errors.push("Missing required key: 'config'".to_string());
        return Validation {
            valid: false,
            errors,
            warnings,
        };
    };
    match config.get("name").and_then(|n| n.as_str()) {
        None => errors.push("Missing required key: 'config.name'".to_string()),
        Some(n) => {
            if let Err(e) = validate_name(n, "config.name") {
                warnings.push(format!("config.name is not a safe folder name: {e}"));
            }
        },
    }

    let processes = match config.get("process") {
        None => {
            errors.push("Missing required key: 'config.process'".to_string());
            &[][..]
        },
        Some(p) => match p.as_sequence() {
            Some(s) if s.is_empty() => {
                errors.push("'config.process' array is empty".to_string());
                &[][..]
            },
            Some(s) => s.as_slice(),
            None => {
                errors.push("'config.process' is not an array".to_string());
                &[][..]
            },
        },
    };

    for (pi, process) in processes.iter().enumerate() {
        let at = |msg: &str| format!("process[{pi}]: {msg}");

        if process.get("training_folder").is_none() {
            warnings.push(at(
                "missing 'training_folder' (AI Toolkit default will be used)",
            ));
        }

        // Datasets
        match process.get("datasets").and_then(|d| d.as_sequence()) {
            None => errors.push(at("missing 'datasets' array")),
            Some(ds) if ds.is_empty() => errors.push(at("'datasets' array is empty")),
            Some(ds) => {
                for (i, d) in ds.iter().enumerate() {
                    let Some(folder) = d.get("folder_path").and_then(|v| v.as_str()) else {
                        errors.push(at(&format!("dataset {i} missing 'folder_path'")));
                        continue;
                    };
                    let folder_path = resolve_against(&paths.base_path, folder);
                    if !folder_path.is_dir() {
                        errors.push(at(&format!("dataset {i} folder does not exist: {folder}")));
                        continue;
                    }
                    match scan_dataset(&folder_path, 0) {
                        Ok(stats) if stats.image_count == 0 => {
                            errors.push(at(&format!("dataset {i} contains no images: {folder}")))
                        },
                        Ok(stats) if stats.missing_caption_count > 0 => {
                            warnings.push(at(&format!(
                                "dataset {i}: {} of {} images have no caption file",
                                stats.missing_caption_count, stats.image_count
                            )))
                        },
                        Ok(_) => {},
                        Err(e) => {
                            warnings.push(at(&format!("dataset {i} could not be scanned: {e}")))
                        },
                    }
                }
            },
        }

        // Model
        let mut is_flow = false;
        match process.get("model") {
            None => errors.push(at("missing 'model'")),
            Some(model) => {
                if model.get("name_or_path").and_then(|v| v.as_str()).is_none() {
                    errors.push(at("missing 'model.name_or_path'"));
                }
                let flag = |k: &str| model.get(k).and_then(|v| v.as_bool()).unwrap_or(false);
                let set = ["is_flux", "is_xl", "is_v2", "is_v3"]
                    .iter()
                    .filter(|k| flag(k))
                    .count();
                if set > 1 {
                    errors.push(at("more than one of is_flux/is_xl/is_v2/is_v3 is true"));
                }
                is_flow = flag("is_flux") || flag("is_v3");
            },
        }

        // Train
        match process.get("train") {
            None => errors.push(at("missing 'train'")),
            Some(train) => {
                match train.get("steps").and_then(|v| v.as_u64()) {
                    None => errors.push(at("missing or non-integer 'train.steps'")),
                    Some(0) => errors.push(at("'train.steps' must be > 0")),
                    Some(_) => {},
                }
                if let Some(lr) = train.get("lr").and_then(|v| v.as_f64())
                    && (lr <= 0.0 || lr > 1.0)
                {
                    errors.push(at(&format!("'train.lr' {lr} is out of range (0, 1]")));
                }
                if let Some(s) = train.get("noise_scheduler").and_then(|v| v.as_str())
                    && is_flow
                    && s != "flowmatch"
                {
                    warnings.push(at(&format!(
                        "Flux/SD3 model with noise_scheduler '{s}' (expected 'flowmatch')"
                    )));
                }
            },
        }

        // Network
        if let Some(net) = process.get("network")
            && net.get("linear").and_then(|v| v.as_u64()) == Some(0)
        {
            errors.push(at("'network.linear' (rank) must be > 0"));
        }
    }

    Validation {
        valid: errors.is_empty(),
        errors,
        warnings,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(name: &str, dataset: &str) -> CreateConfigArgs {
        CreateConfigArgs {
            name: name.into(),
            dataset_path: dataset.into(),
            ..Default::default()
        }
    }

    #[test]
    fn detect_arch_priority() {
        assert!(detect_arch("black-forest-labs/FLUX.1-dev").is_flux);
        let sd3 = detect_arch("stabilityai/stable-diffusion-3.5-large");
        assert!(sd3.is_v3 && !sd3.is_xl && !sd3.is_flux);
        let xl = detect_arch("stabilityai/stable-diffusion-xl-base-1.0");
        assert!(xl.is_xl && !xl.is_v3);
        let sd15 = detect_arch("runwayml/stable-diffusion-v1-5");
        assert_eq!(
            sd15,
            Arch {
                is_flux: false,
                is_xl: false,
                is_v3: false
            }
        );
    }

    #[test]
    fn build_defaults_sd15() {
        let paths = AIToolkitPaths::from_base("/ai");
        let built = build_config(&paths, &args("lora", "ds")).unwrap();
        let p = &built.config.config.process[0];
        assert_eq!(p.train.steps, 2000);
        assert_eq!(p.train.noise_scheduler, "ddpm");
        assert_eq!(p.train.optimizer, "adamw");
        assert!(!p.model.quantize);
        assert_eq!(p.network.transformer_only, None);
        assert_eq!(built.dataset_folder, PathBuf::from("/ai/datasets/ds"));
        assert_eq!(
            PathBuf::from(&p.training_folder),
            PathBuf::from("/ai/outputs")
        );
        assert_eq!(p.sample.width, 512);
        // folder does not exist -> warning, not error
        assert!(built.warnings.iter().any(|w| w.contains("does not exist")));
    }

    #[test]
    fn build_flux_preset() {
        let paths = AIToolkitPaths::from_base("/ai");
        let mut a = args("flux_lora", "/ai/datasets/cats");
        a.preset = Some("flux-dev".into());
        a.trigger_word = Some("ohwx".into());
        let built = build_config(&paths, &a).unwrap();
        let p = &built.config.config.process[0];
        assert!(p.model.is_flux && p.model.quantize);
        assert_eq!(p.model.name_or_path, "black-forest-labs/FLUX.1-dev");
        assert_eq!(p.train.noise_scheduler, "flowmatch");
        assert_eq!(p.train.dtype, "bf16");
        assert_eq!(p.sample.width, 1024);
        assert!(p.sample.prompts[0].starts_with("ohwx, "));
        let yaml = serde_yaml::to_string(&built.config).unwrap();
        assert!(yaml.contains("job: extension"));
        assert!(yaml.contains("type: sd_trainer"));
    }

    #[test]
    fn build_rejects_bad_input() {
        let paths = AIToolkitPaths::from_base("/ai");
        assert!(build_config(&paths, &args("../x", "ds")).is_err());
        assert!(build_config(&paths, &args("ok", "../ds")).is_err());
        assert!(build_config(&paths, &args("ok", "/ai/../etc")).is_err());
        let mut a = args("ok", "ds");
        a.optimizer = Some("sgd; rm -rf /".into());
        assert!(build_config(&paths, &a).is_err());
        let mut a = args("ok", "ds");
        a.caption_dropout_rate = Some(1.5);
        assert!(build_config(&paths, &a).is_err());
        let mut a = args("ok", "ds");
        a.resolution = Some(Resolution::Multiple(vec![]));
        assert!(build_config(&paths, &a).is_err());
        let mut a = args("ok", "ds");
        a.is_flux = Some(true);
        a.is_xl = Some(true);
        assert!(build_config(&paths, &a).is_err());
        let mut a = args("ok", "ds");
        a.preset = Some("nope".into());
        assert!(build_config(&paths, &a).unwrap_err().contains("flux-dev"));
        let mut a = args("ok", "ds");
        a.steps = Some(0);
        assert!(build_config(&paths, &a).is_err());
    }

    #[test]
    fn resolve_dataset_variants() {
        let paths = AIToolkitPaths::from_base("/ai");
        assert_eq!(
            resolve_dataset_path(&paths, "cats").unwrap(),
            PathBuf::from("/ai/datasets/cats")
        );
        assert_eq!(
            resolve_dataset_path(&paths, "datasets/cats").unwrap(),
            PathBuf::from("/ai/datasets/cats")
        );
        assert!(resolve_dataset_path(&paths, "").is_err());
        assert!(resolve_dataset_path(&paths, "a/../../b").is_err());
    }

    #[test]
    fn validate_detects_problems() {
        let tmp = tempfile::tempdir().unwrap();
        let paths = AIToolkitPaths::from_base(tmp.path());
        let ds = paths.datasets_path.join("cats");
        std::fs::create_dir_all(&ds).unwrap();

        // Valid config but empty dataset -> error
        let built = build_config(&paths, &args("lora", "cats")).unwrap();
        let yaml: serde_yaml::Value =
            serde_yaml::from_str(&serde_yaml::to_string(&built.config).unwrap()).unwrap();
        let v = validate_config_yaml(&paths, &yaml);
        assert!(!v.valid);
        assert!(v.errors.iter().any(|e| e.contains("no images")));

        // Add an image without caption -> valid with warning
        std::fs::write(ds.join("a.png"), b"x").unwrap();
        let v = validate_config_yaml(&paths, &yaml);
        assert!(v.valid, "{:?}", v.errors);
        assert!(v.warnings.iter().any(|w| w.contains("no caption")));

        let summary = summarize_config(&paths, &yaml);
        assert_eq!(summary.run_name.as_deref(), Some("lora"));
        assert_eq!(summary.steps, Some(2000));
        assert_eq!(summary.training_folder, Some(paths.outputs_path.clone()));
    }

    #[test]
    fn validate_structural_errors() {
        let paths = AIToolkitPaths::from_base("/nonexistent");
        let v = validate_config_yaml(&paths, &serde_yaml::from_str("foo: 1").unwrap());
        assert!(!v.valid);
        assert_eq!(v.errors.len(), 2);

        let y = "job: extension\nconfig:\n  name: x\n  process: []\n";
        let v = validate_config_yaml(&paths, &serde_yaml::from_str(y).unwrap());
        assert!(v.errors.iter().any(|e| e.contains("empty")));

        let y = "job: extension\nconfig:\n  name: x\n  process:\n    - model: {name_or_path: m, is_flux: true, is_xl: true}\n      datasets: []\n      train: {steps: 0}\n";
        let v = validate_config_yaml(&paths, &serde_yaml::from_str(y).unwrap());
        assert!(v.errors.iter().any(|e| e.contains("more than one")));
        assert!(v.errors.iter().any(|e| e.contains("steps")));
        assert!(v.errors.iter().any(|e| e.contains("datasets")));
    }
}
