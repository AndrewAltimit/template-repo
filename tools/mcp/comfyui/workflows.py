"""ComfyUI workflow templates and factory"""

import random
from typing import Any, Dict, Optional


class WorkflowFactory:
    """Factory for creating ComfyUI workflows for different model types"""

    @staticmethod
    def create_flux_workflow(
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: int = -1,
        steps: int = 20,
        cfg_scale: float = 3.5,
        sampler_name: str = "euler",
        scheduler: str = "normal",
        model_name: str = "flux1-dev-fp8.safetensors",
        lora_name: Optional[str] = None,
        lora_strength: float = 1.0,
    ) -> Dict[str, Any]:
        """Create a FLUX workflow with optional LoRA support"""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            "1": {
                "inputs": {"ckpt_name": model_name},
                "class_type": "CheckpointLoaderSimple",
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["1", 0] if not lora_name else ["10", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "5": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage",
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode",
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
                "class_type": "SaveImage",
            },
        }

        # Add LoRA if specified
        if lora_name:
            workflow["10"] = {
                "inputs": {
                    "lora_name": lora_name,
                    "strength_model": lora_strength,
                    "strength_clip": lora_strength,
                    "model": ["1", 0],
                    "clip": ["1", 1],
                },
                "class_type": "LoraLoader",
            }
            # Update CLIP connections to use LoRA output
            workflow["2"]["inputs"]["clip"] = ["10", 1]  # type: ignore
            workflow["3"]["inputs"]["clip"] = ["10", 1]  # type: ignore

        return workflow

    @staticmethod
    def create_sdxl_workflow(
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: int = -1,
        steps: int = 30,
        cfg_scale: float = 7.0,
        sampler_name: str = "dpmpp_2m",
        scheduler: str = "karras",
        model_name: str = "illustriousXL_smoothftSOLID.safetensors",
        lora_name: Optional[str] = None,
        lora_strength: float = 1.0,
    ) -> Dict[str, Any]:
        """Create an SDXL/IllustriousXL workflow with optional LoRA support"""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            "1": {
                "inputs": {"ckpt_name": model_name},
                "class_type": "CheckpointLoaderSimple",
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["1", 0] if not lora_name else ["10", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "5": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage",
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode",
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
                "class_type": "SaveImage",
            },
        }

        # Add LoRA if specified
        if lora_name:
            workflow["10"] = {
                "inputs": {
                    "lora_name": lora_name,
                    "strength_model": lora_strength,
                    "strength_clip": lora_strength,
                    "model": ["1", 0],
                    "clip": ["1", 1],
                },
                "class_type": "LoraLoader",
            }
            # Update CLIP connections to use LoRA output
            workflow["2"]["inputs"]["clip"] = ["10", 1]  # type: ignore
            workflow["3"]["inputs"]["clip"] = ["10", 1]  # type: ignore

        return workflow

    @staticmethod
    def create_img2img_workflow(
        image_data: str,  # Base64 encoded image
        prompt: str,
        negative_prompt: str = "",
        denoise: float = 0.8,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seed: int = -1,
        steps: int = 20,
        cfg_scale: float = 7.0,
        sampler_name: str = "dpmpp_2m",
        scheduler: str = "karras",
        model_name: str = "flux1-dev-fp8.safetensors",
    ) -> Dict[str, Any]:
        """Create an image-to-image workflow"""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            "1": {
                "inputs": {"ckpt_name": model_name},
                "class_type": "CheckpointLoaderSimple",
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "8": {
                "inputs": {"image": image_data, "upload": "image"},
                "class_type": "LoadImage",
            },
            "9": {
                "inputs": {"pixels": ["8", 0], "vae": ["1", 2]},
                "class_type": "VAEEncode",
            },
            "4": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": denoise,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["9", 0],
                },
                "class_type": "KSampler",
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode",
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI_img2img", "images": ["6", 0]},
                "class_type": "SaveImage",
            },
        }

        # Add optional resize if dimensions specified
        if width and height:
            workflow["11"] = {
                "inputs": {
                    "upscale_method": "bicubic",
                    "width": width,
                    "height": height,
                    "crop": "center",
                    "image": ["8", 0],
                },
                "class_type": "ImageScale",
            }
            workflow["9"]["inputs"]["pixels"] = ["11", 0]  # type: ignore

        return workflow

    @staticmethod
    def create_upscale_workflow(
        image_data: str,
        model_name: str = "flux1-dev-fp8.safetensors",
        upscale_model: str = "4x-UltraSharp.pth",
        scale_factor: float = 2.0,
    ) -> Dict[str, Any]:
        """Create an upscaling workflow"""
        workflow = {
            "1": {
                "inputs": {"model_name": upscale_model},
                "class_type": "UpscaleModelLoader",
            },
            "2": {
                "inputs": {"image": image_data, "upload": "image"},
                "class_type": "LoadImage",
            },
            "3": {
                "inputs": {"upscale_model": ["1", 0], "image": ["2", 0]},
                "class_type": "ImageUpscaleWithModel",
            },
            "4": {
                "inputs": {"filename_prefix": "ComfyUI_upscaled", "images": ["3", 0]},
                "class_type": "SaveImage",
            },
        }
        return workflow

    @staticmethod
    def create_wan22_video_workflow(
        prompt: str,
        negative_prompt: str = "",
        start_image: Optional[str] = None,  # Base64 encoded start image for img2video
        width: int = 1280,
        height: int = 704,
        video_frames: int = 121,
        seed: int = -1,
        steps: int = 30,
        cfg_scale: float = 5.0,
        sampler_name: str = "uni_pc",
        scheduler: str = "simple",
        output_format: str = "webp",  # "webp" or "webm"
        fps: float = 24.0,
    ) -> Dict[str, Any]:
        """Create a WAN 2.2 video generation workflow (text-to-video or image-to-video)"""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        workflow: Dict[str, Any] = {
            # Model loaders
            "37": {
                "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"},
                "class_type": "UNETLoader",
            },
            "38": {
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "clip_name2": "wan",
                    "type": "default",
                },
                "class_type": "CLIPLoader",
            },
            "39": {
                "inputs": {"vae_name": "wan2.2_vae.safetensors"},
                "class_type": "VAELoader",
            },
            # Model sampling configuration
            "48": {
                "inputs": {"shift": 8.0, "model": ["37", 0]},
                "class_type": "ModelSamplingSD3",
            },
            # Text encoding
            "6": {
                "inputs": {"text": prompt, "clip": ["38", 0]},
                "class_type": "CLIPTextEncode",
            },
            "7": {
                "inputs": {"text": negative_prompt, "clip": ["38", 0]},
                "class_type": "CLIPTextEncode",
            },
            # Video latent generation
            "55": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "length": video_frames,
                    "batch_size": 1,
                    "vae": ["39", 0],
                },
                "class_type": "Wan22ImageToVideoLatent",
            },
            # KSampler
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["48", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["55", 0],
                },
                "class_type": "KSampler",
            },
            # VAE Decode
            "8": {
                "inputs": {"samples": ["3", 0], "vae": ["39", 0]},
                "class_type": "VAEDecode",
            },
        }

        # Add start image if provided (for image-to-video)
        if start_image:
            workflow["57"] = {
                "inputs": {"image": start_image, "upload": "image"},
                "class_type": "LoadImage",
            }
            # Connect start image to video latent node
            workflow["55"]["inputs"]["start_image"] = ["57", 0]  # type: ignore

        # Add output nodes based on format
        if output_format == "webm":
            workflow["47"] = {
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "codec": "vp9",
                    "fps": fps,
                    "quality": 16,
                    "images": ["8", 0],
                },
                "class_type": "SaveWEBM",
            }
        else:  # Default to WEBP
            workflow["28"] = {
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "fps": fps,
                    "lossless": False,
                    "quality": 90,
                    "method": "default",
                    "images": ["8", 0],
                },
                "class_type": "SaveAnimatedWEBP",
            }

        return workflow

    @staticmethod
    def create_controlnet_workflow(
        control_image: str,
        prompt: str,
        negative_prompt: str = "",
        control_strength: float = 1.0,
        width: int = 1024,
        height: int = 1024,
        seed: int = -1,
        steps: int = 20,
        cfg_scale: float = 7.0,
        model_name: str = "flux1-dev-fp8.safetensors",
        controlnet_name: str = "control_v11p_sd15_canny.pth",
    ) -> Dict[str, Any]:
        """Create a ControlNet workflow"""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            "1": {
                "inputs": {"ckpt_name": model_name},
                "class_type": "CheckpointLoaderSimple",
            },
            "2": {
                "inputs": {"text": prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "3": {
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
                "class_type": "CLIPTextEncode",
            },
            "12": {
                "inputs": {"control_net_name": controlnet_name},
                "class_type": "ControlNetLoader",
            },
            "13": {
                "inputs": {"image": control_image, "upload": "image"},
                "class_type": "LoadImage",
            },
            "14": {
                "inputs": {
                    "strength": control_strength,
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "control_net": ["12", 0],
                    "image": ["13", 0],
                },
                "class_type": "ControlNetApply",
            },
            "5": {
                "inputs": {"width": width, "height": height, "batch_size": 1},
                "class_type": "EmptyLatentImage",
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
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "6": {
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode",
            },
            "7": {
                "inputs": {"filename_prefix": "ComfyUI_controlnet", "images": ["6", 0]},
                "class_type": "SaveImage",
            },
        }

        return workflow


# Available workflow templates
WORKFLOW_TEMPLATES = {
    "wan22_text2video": {
        "name": "WAN 2.2 Text-to-Video",
        "description": "Generate videos from text prompts using WAN 2.2 model",
        "model_type": "video",
        "factory_method": WorkflowFactory.create_wan22_video_workflow,
    },
    "wan22_image2video": {
        "name": "WAN 2.2 Image-to-Video",
        "description": "Generate videos from a starting image using WAN 2.2 model",
        "model_type": "video",
        "factory_method": lambda **kwargs: WorkflowFactory.create_wan22_video_workflow(
            **{**kwargs, "start_image": kwargs.get("start_image", "")}
        ),
    },
    "flux_default": {
        "name": "FLUX Default",
        "description": "Default FLUX workflow for text-to-image generation",
        "model_type": "flux",
        "factory_method": WorkflowFactory.create_flux_workflow,
    },
    "sdxl_default": {
        "name": "SDXL/IllustriousXL Default",
        "description": "Default SDXL workflow for text-to-image generation",
        "model_type": "sdxl",
        "factory_method": WorkflowFactory.create_sdxl_workflow,
    },
    "img2img": {
        "name": "Image to Image",
        "description": "Transform existing images with text prompts",
        "model_type": "any",
        "factory_method": WorkflowFactory.create_img2img_workflow,
    },
    "upscale": {
        "name": "Upscale",
        "description": "Upscale images using AI models",
        "model_type": "upscale",
        "factory_method": WorkflowFactory.create_upscale_workflow,
    },
    "controlnet": {
        "name": "ControlNet",
        "description": "Guided image generation using control images",
        "model_type": "any",
        "factory_method": WorkflowFactory.create_controlnet_workflow,
    },
    "flux_with_lora": {
        "name": "FLUX with LoRA",
        "description": "FLUX workflow with LoRA model support",
        "model_type": "flux",
        "factory_method": lambda **kwargs: WorkflowFactory.create_flux_workflow(
            **{**kwargs, "lora_name": kwargs.get("lora_name", "Inkpunk_Flux.safetensors")}
        ),
    },
}
