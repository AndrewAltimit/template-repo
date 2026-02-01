//! ComfyUI workflow templates and factory

use rand::Rng;
use serde_json::{Value, json};

use crate::types::WorkflowTemplate;

/// Factory for creating ComfyUI workflows
pub struct WorkflowFactory;

impl WorkflowFactory {
    /// Create a FLUX workflow with optional LoRA support
    #[allow(clippy::too_many_arguments)]
    pub fn create_flux_workflow(
        prompt: &str,
        negative_prompt: &str,
        width: u32,
        height: u32,
        seed: i64,
        steps: u32,
        cfg_scale: f64,
        lora_name: Option<&str>,
        lora_strength: f64,
    ) -> Value {
        let seed = if seed == -1 {
            rand::thread_rng().gen_range(0..u32::MAX) as i64
        } else {
            seed
        };

        let model_source = if lora_name.is_some() {
            json!(["10", 0])
        } else {
            json!(["1", 0])
        };

        let clip_source = if lora_name.is_some() {
            json!(["10", 1])
        } else {
            json!(["1", 1])
        };

        let mut workflow = json!({
            "1": {
                "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            "2": {
                "inputs": {"text": prompt, "clip": clip_source},
                "class_type": "CLIPTextEncode"
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": clip_source},
                "class_type": "CLIPTextEncode"
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": model_source,
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "5": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode"
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
                "class_type": "SaveImage"
            }
        });

        // Add LoRA if specified
        if let Some(lora) = lora_name {
            workflow["10"] = json!({
                "inputs": {
                    "lora_name": lora,
                    "strength_model": lora_strength,
                    "strength_clip": lora_strength,
                    "model": ["1", 0],
                    "clip": ["1", 1]
                },
                "class_type": "LoraLoader"
            });
        }

        workflow
    }

    /// Create an SDXL/IllustriousXL workflow
    #[allow(clippy::too_many_arguments)]
    pub fn create_sdxl_workflow(
        prompt: &str,
        negative_prompt: &str,
        width: u32,
        height: u32,
        seed: i64,
        steps: u32,
        cfg_scale: f64,
        lora_name: Option<&str>,
        lora_strength: f64,
    ) -> Value {
        let seed = if seed == -1 {
            rand::thread_rng().gen_range(0..u32::MAX) as i64
        } else {
            seed
        };

        let model_source = if lora_name.is_some() {
            json!(["10", 0])
        } else {
            json!(["1", 0])
        };

        let clip_source = if lora_name.is_some() {
            json!(["10", 1])
        } else {
            json!(["1", 1])
        };

        let mut workflow = json!({
            "1": {
                "inputs": {"ckpt_name": "illustriousXL_smoothftSOLID.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            "2": {
                "inputs": {"text": prompt, "clip": clip_source},
                "class_type": "CLIPTextEncode"
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": clip_source},
                "class_type": "CLIPTextEncode"
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "dpmpp_2m",
                    "scheduler": "karras",
                    "denoise": 1.0,
                    "model": model_source,
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "5": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode"
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
                "class_type": "SaveImage"
            }
        });

        if let Some(lora) = lora_name {
            workflow["10"] = json!({
                "inputs": {
                    "lora_name": lora,
                    "strength_model": lora_strength,
                    "strength_clip": lora_strength,
                    "model": ["1", 0],
                    "clip": ["1", 1]
                },
                "class_type": "LoraLoader"
            });
        }

        workflow
    }

    /// Create an image-to-image workflow
    #[allow(clippy::too_many_arguments)]
    pub fn create_img2img_workflow(
        image_data: &str,
        prompt: &str,
        negative_prompt: &str,
        denoise: f64,
        width: Option<u32>,
        height: Option<u32>,
        seed: i64,
        steps: u32,
        cfg_scale: f64,
    ) -> Value {
        let seed = if seed == -1 {
            rand::thread_rng().gen_range(0..u32::MAX) as i64
        } else {
            seed
        };

        let pixels_source = if width.is_some() && height.is_some() {
            json!(["11", 0])
        } else {
            json!(["8", 0])
        };

        let mut workflow = json!({
            "1": {
                "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode"
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {"image": image_data, "upload": "image"},
                "class_type": "LoadImage"
            },
            "9": {
                "inputs": {"pixels": pixels_source, "vae": ["1", 2]},
                "class_type": "VAEEncode"
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "dpmpp_2m",
                    "scheduler": "karras",
                    "denoise": denoise,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["9", 0]
                },
                "class_type": "KSampler"
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode"
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI_img2img", "images": ["6", 0]},
                "class_type": "SaveImage"
            }
        });

        if let (Some(w), Some(h)) = (width, height) {
            workflow["11"] = json!({
                "inputs": {
                    "upscale_method": "bicubic",
                    "width": w,
                    "height": h,
                    "crop": "center",
                    "image": ["8", 0]
                },
                "class_type": "ImageScale"
            });
        }

        workflow
    }

    /// Create an upscaling workflow
    pub fn create_upscale_workflow(image_data: &str, upscale_model: &str) -> Value {
        json!({
            "1": {
                "inputs": {"model_name": upscale_model},
                "class_type": "UpscaleModelLoader"
            },
            "2": {
                "inputs": {"image": image_data, "upload": "image"},
                "class_type": "LoadImage"
            },
            "3": {
                "inputs": {"upscale_model": ["1", 0], "image": ["2", 0]},
                "class_type": "ImageUpscaleWithModel"
            },
            "4": {
                "inputs": {"filename_prefix": "ComfyUI_upscaled", "images": ["3", 0]},
                "class_type": "SaveImage"
            }
        })
    }

    /// Create a ControlNet workflow
    #[allow(clippy::too_many_arguments)]
    pub fn create_controlnet_workflow(
        control_image: &str,
        prompt: &str,
        negative_prompt: &str,
        control_strength: f64,
        width: u32,
        height: u32,
        seed: i64,
        steps: u32,
        cfg_scale: f64,
        controlnet_name: &str,
    ) -> Value {
        let seed = if seed == -1 {
            rand::thread_rng().gen_range(0..u32::MAX) as i64
        } else {
            seed
        };

        json!({
            "1": {
                "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode"
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode"
            },
            "12": {
                "inputs": {"control_net_name": controlnet_name},
                "class_type": "ControlNetLoader"
            },
            "13": {
                "inputs": {"image": control_image, "upload": "image"},
                "class_type": "LoadImage"
            },
            "14": {
                "inputs": {
                    "strength": control_strength,
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "control_net": ["12", 0],
                    "image": ["13", 0]
                },
                "class_type": "ControlNetApply"
            },
            "5": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage"
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": "dpmpp_2m",
                    "scheduler": "karras",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["14", 0],
                    "negative": ["14", 1],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode"
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI_controlnet", "images": ["6", 0]},
                "class_type": "SaveImage"
            }
        })
    }
}

/// Get all available workflow templates
pub fn get_workflow_templates() -> Vec<WorkflowTemplate> {
    vec![
        WorkflowTemplate {
            name: "flux_default".to_string(),
            description: "Default FLUX workflow for text-to-image generation".to_string(),
            model_type: "flux".to_string(),
        },
        WorkflowTemplate {
            name: "sdxl_default".to_string(),
            description: "Default SDXL workflow for text-to-image generation".to_string(),
            model_type: "sdxl".to_string(),
        },
        WorkflowTemplate {
            name: "img2img".to_string(),
            description: "Transform existing images with text prompts".to_string(),
            model_type: "any".to_string(),
        },
        WorkflowTemplate {
            name: "upscale".to_string(),
            description: "Upscale images using AI models".to_string(),
            model_type: "upscale".to_string(),
        },
        WorkflowTemplate {
            name: "controlnet".to_string(),
            description: "Guided image generation using control images".to_string(),
            model_type: "any".to_string(),
        },
        WorkflowTemplate {
            name: "flux_with_lora".to_string(),
            description: "FLUX workflow with LoRA model support".to_string(),
            model_type: "flux".to_string(),
        },
    ]
}

/// Get a workflow by name with sample parameters
pub fn get_sample_workflow(name: &str) -> Option<Value> {
    match name {
        "flux_default" => Some(WorkflowFactory::create_flux_workflow(
            "A beautiful landscape",
            "",
            1024,
            1024,
            -1,
            20,
            3.5,
            None,
            1.0,
        )),
        "sdxl_default" => Some(WorkflowFactory::create_sdxl_workflow(
            "A beautiful landscape",
            "",
            1024,
            1024,
            -1,
            30,
            7.0,
            None,
            1.0,
        )),
        "img2img" => Some(WorkflowFactory::create_img2img_workflow(
            "",
            "A beautiful landscape",
            "",
            0.8,
            None,
            None,
            -1,
            20,
            7.0,
        )),
        "upscale" => Some(WorkflowFactory::create_upscale_workflow(
            "",
            "4x-UltraSharp.pth",
        )),
        "controlnet" => Some(WorkflowFactory::create_controlnet_workflow(
            "",
            "A beautiful landscape",
            "",
            1.0,
            1024,
            1024,
            -1,
            20,
            7.0,
            "control_v11p_sd15_canny.pth",
        )),
        "flux_with_lora" => Some(WorkflowFactory::create_flux_workflow(
            "A beautiful landscape",
            "",
            1024,
            1024,
            -1,
            20,
            3.5,
            Some("Inkpunk_Flux.safetensors"),
            1.0,
        )),
        _ => None,
    }
}
