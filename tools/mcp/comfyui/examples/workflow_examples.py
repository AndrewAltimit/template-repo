#!/usr/bin/env python3
"""
Examples of using ComfyUI workflows through the MCP server.

This script demonstrates how to use various workflow templates including:
- FLUX image generation
- SDXL/IllustriousXL
- Image-to-Image transformation
- Video generation with WAN 2.2
- LoRA application
"""

from tools.mcp.comfyui.workflows import WORKFLOW_TEMPLATES, WorkflowFactory


def example_flux_basic():
    """Basic FLUX text-to-image generation"""
    workflow = WorkflowFactory.create_flux_workflow(
        prompt="A cyberpunk city at night, neon lights, flying cars, detailed architecture",
        negative_prompt="",
        width=1024,
        height=1024,
        steps=20,
        cfg_scale=3.5,
    )
    print("FLUX Basic Workflow created with", len(workflow), "nodes")
    return workflow


def example_flux_with_lora():
    """FLUX with LoRA for style transfer"""
    workflow = WorkflowFactory.create_flux_workflow(
        prompt="A robot warrior in battle, dramatic lighting",
        negative_prompt="",
        lora_name="Inkpunk_Flux.safetensors",
        lora_strength=0.8,
        width=1024,
        height=1024,
        steps=25,
        cfg_scale=3.5,
    )
    print("FLUX + LoRA Workflow created with", len(workflow), "nodes")
    return workflow


def example_sdxl_anime():
    """SDXL/IllustriousXL for anime-style generation"""
    workflow = WorkflowFactory.create_sdxl_workflow(
        prompt="1girl, silver hair, blue eyes, fantasy outfit, magical aura, detailed background, masterpiece",
        negative_prompt="low quality, bad anatomy, bad hands, text, watermark",
        model_name="illustriousXL_smoothftSOLID.safetensors",
        width=1024,
        height=1024,
        steps=30,
        cfg_scale=7.0,
        sampler_name="dpmpp_2m",
        scheduler="karras",
    )
    print("SDXL Anime Workflow created with", len(workflow), "nodes")
    return workflow


def example_img2img():
    """Image-to-Image transformation"""
    # In real usage, load an actual image:
    # import base64
    # with open("input.jpg", "rb") as f:
    #     image_data = base64.b64encode(f.read()).decode()
    image_data = ""  # Placeholder

    workflow = WorkflowFactory.create_img2img_workflow(
        image_data=image_data,
        prompt="transform to cyberpunk style, neon colors, futuristic",
        negative_prompt="blurry, low quality",
        denoise=0.7,  # 0.7 = moderate transformation
        width=1024,
        height=1024,
        steps=20,
        cfg_scale=7.0,
    )
    print("Image-to-Image Workflow created with", len(workflow), "nodes")
    return workflow


def example_wan22_text_to_video():
    """Text-to-Video generation with WAN 2.2"""
    workflow = WorkflowFactory.create_wan22_video_workflow(
        prompt="a cat playing piano, smooth motion, high quality animation",
        negative_prompt="static, still image, no motion, stuttering, blurry",
        width=1280,
        height=704,  # Optimal resolution for WAN 2.2
        video_frames=121,  # 5 seconds at 24fps
        steps=30,
        cfg_scale=5.0,
        sampler_name="uni_pc",
        scheduler="simple",
        output_format="webp",  # or "webm"
        fps=24.0,
    )
    print("WAN 2.2 Text-to-Video Workflow created with", len(workflow), "nodes")
    return workflow


def example_wan22_image_to_video():
    """Image-to-Video animation with WAN 2.2"""
    # In real usage, load an actual image:
    # import base64
    # with open("start_frame.jpg", "rb") as f:
    #     start_image = base64.b64encode(f.read()).decode()
    start_image = ""  # Placeholder

    workflow = WorkflowFactory.create_wan22_video_workflow(
        prompt="make the subject slowly turn their head and smile",
        negative_prompt="morphing, distortion, flickering, unstable",
        start_image=start_image,
        width=1280,
        height=704,
        video_frames=60,  # 2.5 seconds for shorter animation
        steps=25,
        cfg_scale=5.0,
        output_format="webm",
    )
    print("WAN 2.2 Image-to-Video Workflow created with", len(workflow), "nodes")
    return workflow


def example_upscale():
    """Upscale an image using AI models"""
    # In real usage, load an actual image
    image_data = ""  # Placeholder

    workflow = WorkflowFactory.create_upscale_workflow(
        image_data=image_data,
        upscale_model="4x-UltraSharp.pth",  # or other upscale models
        scale_factor=2.0,
    )
    print("Upscale Workflow created with", len(workflow), "nodes")
    return workflow


def example_controlnet():
    """ControlNet for guided generation"""
    # In real usage, load control image (e.g., edge map, depth map)
    control_image = ""  # Placeholder

    workflow = WorkflowFactory.create_controlnet_workflow(
        control_image=control_image,
        prompt="a beautiful landscape, highly detailed",
        negative_prompt="low quality",
        control_strength=1.0,
        width=1024,
        height=1024,
        steps=20,
        cfg_scale=7.0,
        controlnet_name="control_v11p_sd15_canny.pth",
    )
    print("ControlNet Workflow created with", len(workflow), "nodes")
    return workflow


def print_workflow_summary():
    """Print summary of all available workflow templates"""
    print("\n" + "=" * 60)
    print("Available Workflow Templates:")
    print("=" * 60)

    for key, template in WORKFLOW_TEMPLATES.items():
        print(f"\n{key}:")
        print(f"  Name: {template['name']}")
        print(f"  Description: {template['description']}")
        print(f"  Model Type: {template['model_type']}")


def main():
    """Run all examples and show workflow information"""
    print("ComfyUI Workflow Examples")
    print("=" * 60)

    # Print available templates
    print_workflow_summary()

    print("\n\n" + "=" * 60)
    print("Generating Example Workflows:")
    print("=" * 60 + "\n")

    # Generate example workflows
    _ = {
        "flux_basic": example_flux_basic(),
        "flux_lora": example_flux_with_lora(),
        "sdxl_anime": example_sdxl_anime(),
        "img2img": example_img2img(),
        "text2video": example_wan22_text_to_video(),
        "img2video": example_wan22_image_to_video(),
        "upscale": example_upscale(),
        "controlnet": example_controlnet(),
    }

    print("\n" + "=" * 60)
    print("Usage with MCP Client:")
    print("=" * 60)
    print(
        """
from tools.mcp.core.client import MCPClient

# Initialize client
client = MCPClient("comfyui")

# Generate image/video
result = await client.call_tool(
    "generate_image",
    workflow=workflow,  # Use any workflow from above
    timeout=600  # Increase for video generation
)

# Check result
if "images" in result:
    for image in result["images"]:
        print(f"Generated: {image['filename']}")
"""
    )

    print("\n" + "=" * 60)
    print("Tips:")
    print("=" * 60)
    print("- For video generation, use timeout=600 or higher")
    print("- FLUX works best with CFG 3-4")
    print("- SDXL/IllustriousXL works best with CFG 6-8")
    print("- WAN 2.2 video works best at 1280x704 resolution")
    print("- Start with fewer frames/steps for testing")


if __name__ == "__main__":
    main()
