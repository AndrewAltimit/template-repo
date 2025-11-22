# ComfyUI MCP Workflow Documentation

## Overview

The ComfyUI MCP server provides a flexible workflow system for generating images using various AI models. The system supports multiple model types including FLUX, SDXL/IllustriousXL, and includes support for LoRAs, ControlNet, and image manipulation workflows.

## Available Workflows

### 1. FLUX Default (`flux_default`)
**Description**: Default FLUX workflow for text-to-image generation
**Model Type**: FLUX
**Default Parameters**:
- Width/Height: 1024x1024
- Steps: 20
- CFG Scale: 3.5
- Sampler: euler
- Scheduler: normal

**Example**:
```python
workflow = WorkflowFactory.create_flux_workflow(
    prompt="A cyberpunk city at night",
    negative_prompt="",
    width=1024,
    height=1024,
    steps=20,
    cfg_scale=3.5
)
```

### 2. SDXL/IllustriousXL Default (`sdxl_default`)
**Description**: Default SDXL workflow for text-to-image generation
**Model Type**: SDXL
**Default Parameters**:
- Width/Height: 1024x1024
- Steps: 30
- CFG Scale: 7.0
- Sampler: dpmpp_2m
- Scheduler: karras

**Example**:
```python
workflow = WorkflowFactory.create_sdxl_workflow(
    prompt="A beautiful anime character",
    negative_prompt="low quality, bad anatomy",
    model_name="illustriousXL_smoothftSOLID.safetensors"
)
```

### 3. Image to Image (`img2img`)
**Description**: Transform existing images with text prompts
**Model Type**: Any
**Key Parameters**:
- `image_data`: Base64 encoded image
- `denoise`: Strength of transformation (0.0-1.0, default 0.8)

### 4. Upscale (`upscale`)
**Description**: Upscale images using AI models
**Model Type**: Upscale
**Default Upscale Model**: 4x-UltraSharp.pth

### 5. ControlNet (`controlnet`)
**Description**: Guided image generation using control images
**Model Type**: Any
**Key Parameters**:
- `control_image`: Base64 encoded control image
- `control_strength`: Influence of control (0.0-1.0)

### 6. FLUX with LoRA (`flux_with_lora`)
**Description**: FLUX workflow with LoRA model support
**Model Type**: FLUX
**Default LoRA**: Inkpunk_Flux.safetensors

### 7. WAN 2.2 Text-to-Video (`wan22_text2video`)
**Description**: Generate videos from text prompts using WAN 2.2 model
**Model Type**: Video
**Default Parameters**:
- Width/Height: 1280x704 (optimal resolution)
- Video Frames: 121 frames (~5 seconds at 24fps)
- Steps: 30
- CFG Scale: 5.0
- Sampler: uni_pc
- Scheduler: simple
- Output Format: WebP (animated) or WebM

**Example**:
```python
workflow = WorkflowFactory.create_wan22_video_workflow(
    prompt="a snowshow cat bobbing her head back and forth to the sound of music",
    negative_prompt="static, blurry, low quality",
    width=1280,
    height=704,
    video_frames=121,
    steps=30,
    cfg_scale=5.0,
    output_format="webp"
)
```

### 8. WAN 2.2 Image-to-Video (`wan22_image2video`)
**Description**: Generate videos from a starting image using WAN 2.2 model
**Model Type**: Video
**Key Parameters**:
- `start_image`: Base64 encoded starting image
- Same parameters as text-to-video

**Example**:
```python
with open("start_frame.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

workflow = WorkflowFactory.create_wan22_video_workflow(
    prompt="make the cat dance to music",
    start_image=image_data,
    width=1280,
    height=704,
    video_frames=121
)
```

## Model Support

### Currently Supported Models

#### FLUX Models
- `flux1-dev-fp8.safetensors` - FLUX Development model (FP8 optimized)

#### SDXL Models
- `illustriousXL_smoothftSOLID.safetensors` - High-quality anime/illustration model

#### LoRA Models
- `Inkpunk_Flux.safetensors` - Inkpunk art style for FLUX

#### VAE Models
- `ae.safetensors` - Standard autoencoder
- `wan2.2_vae.safetensors` - WAN VAE version 2.2 (for video)
- `wan_2.1_vae.safetensors` - WAN VAE version 2.1

#### Video Models
- `wan2.2_ti2v_5B_fp16.safetensors` - WAN 2.2 Text/Image-to-Video model (5B parameters)

#### Video CLIP Models
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors` - UMT5 XXL for video text encoding

## Usage Examples

### Basic Text-to-Image Generation

```python
# Using FLUX
result = await client.call_tool(
    "generate_image",
    prompt="A futuristic robot",
    width=1024,
    height=1024,
    steps=20,
    cfg_scale=3.5
)

# Using IllustriousXL
workflow = WorkflowFactory.create_sdxl_workflow(
    prompt="anime girl with silver hair",
    model_name="illustriousXL_smoothftSOLID.safetensors"
)
result = await client.call_tool("generate_image", workflow=workflow)
```

### Using LoRA

```python
workflow = WorkflowFactory.create_flux_workflow(
    prompt="robot in inkpunk style",
    lora_name="Inkpunk_Flux.safetensors",
    lora_strength=0.8
)
result = await client.call_tool("generate_image", workflow=workflow)
```

### Video Generation

```python
# Text-to-Video
workflow = WorkflowFactory.create_wan22_video_workflow(
    prompt="a cat playing piano, smooth motion, high quality",
    negative_prompt="static, stuttering, low fps, blurry",
    video_frames=121,
    fps=24,
    output_format="webm"
)
result = await client.call_tool("generate_image", workflow=workflow)

# Image-to-Video (animate a static image)
with open("cat.jpg", "rb") as f:
    start_img = base64.b64encode(f.read()).decode()

workflow = WorkflowFactory.create_wan22_video_workflow(
    prompt="cat turns head and blinks",
    start_image=start_img,
    video_frames=60  # Shorter animation
)
result = await client.call_tool("generate_image", workflow=workflow)
```

### Image-to-Image

```python
with open("input.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

workflow = WorkflowFactory.create_img2img_workflow(
    image_data=image_data,
    prompt="transform to cyberpunk style",
    denoise=0.7  # Lower = preserve more original
)
result = await client.call_tool("generate_image", workflow=workflow)
```

## Optimal Settings by Model

### FLUX
- **CFG Scale**: 3.0-4.0 (lower is better for FLUX)
- **Steps**: 20-30
- **Sampler**: euler, dpm++
- **Resolution**: 1024x1024 or higher

### SDXL/IllustriousXL
- **CFG Scale**: 6.0-8.0
- **Steps**: 25-40
- **Sampler**: dpmpp_2m, dpmpp_sde
- **Scheduler**: karras
- **Resolution**: 1024x1024

### WAN 2.2 Video
- **CFG Scale**: 4.0-6.0 (5.0 optimal)
- **Steps**: 25-35 (30 optimal)
- **Sampler**: uni_pc, dpmpp_2m
- **Scheduler**: simple, normal
- **Resolution**: 1280x704 (optimal), 960x544 (faster)
- **Frames**: 121 (5 seconds), 61 (2.5 seconds), 241 (10 seconds)
- **FPS**: 24 (standard), 30 (smooth), 12 (stylized)

## Advanced Features

### Custom Workflows
You can provide complete custom workflows by passing a workflow dict to `generate_image`:

```python
custom_workflow = {
    "1": {"inputs": {...}, "class_type": "CheckpointLoaderSimple"},
    # ... your custom nodes
}
result = await client.call_tool("generate_image", workflow=custom_workflow)
```

### Batch Processing
The workflow factory supports creating workflows with batch sizes > 1 for generating multiple images.

### Seed Control
- Use `seed=-1` for random seeds
- Provide specific seed values for reproducible results

## Video Generation Tips

### WAN 2.2 Best Practices

1. **Resolution**: 1280x704 is optimal, but you can use:
   - 960x544 for faster generation
   - 1920x1056 for higher quality (slower)

2. **Frame Count**:
   - 61 frames (~2.5 seconds) - Quick tests
   - 121 frames (~5 seconds) - Standard
   - 241 frames (~10 seconds) - Extended (much slower)

3. **Prompting for Video**:
   - Include motion words: "walking", "turning", "dancing", "flowing"
   - Specify camera movement: "camera pans left", "zoom in", "rotating view"
   - Add temporal descriptions: "gradually", "slowly", "quickly"

4. **Negative Prompts for Video**:
   - Always include: "static", "still image", "no motion"
   - Quality terms: "stuttering", "jerky motion", "inconsistent frames"
   - Avoid artifacts: "morphing", "flickering", "unstable"

5. **Image-to-Video Tips**:
   - Start image should match the target resolution
   - Clear subjects work better than busy scenes
   - Prompt should describe the desired motion, not the image content

### Output Formats

- **WebP**: Smaller file size, good for web, wide support
- **WebM**: Better quality, VP9 codec, ideal for video players

## Troubleshooting

### Common Issues

1. **Timeout Errors**:
   - For images: Increase timeout or reduce resolution/steps
   - For videos: Use timeout=600 or more (video generation is slow)
2. **LoRA Not Working**: Ensure LoRA is compatible with the base model
3. **VAE Errors**: Some models include VAE, others need explicit VAE loading

### Performance Tips

1. Use FP8 models when available for faster generation
2. Start with lower steps and increase if needed
3. FLUX works better with lower CFG values (3-4)
4. IllustriousXL excels at anime/illustration style

## API Reference

### generate_image
Main function for image generation.

**Parameters**:
- `prompt` (str): Text description
- `negative_prompt` (str): What to avoid
- `width` (int): Image width
- `height` (int): Image height
- `steps` (int): Sampling steps
- `cfg_scale` (float): Classifier-free guidance scale
- `seed` (int): Random seed (-1 for random)
- `workflow` (dict): Custom workflow (optional)
- `timeout` (int): Generation timeout in seconds

### list_workflows
List all available workflow templates.

### get_workflow
Get a specific workflow template by name.

### list_models
List available models by type (checkpoint, lora, vae, embeddings).

## Future Enhancements

- [ ] Inpainting workflow support
- [ ] Multi-ControlNet support
- [ ] IP-Adapter integration
- [x] Video generation support (WAN 2.2)
- [ ] AnimateDiff support for SDXL video
- [ ] Regional prompting
- [ ] SDXL Refiner support
- [ ] Video interpolation workflows
- [ ] Video-to-video style transfer
