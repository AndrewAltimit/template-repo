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
- `wan2.2_vae.safetensors` - WAN VAE version 2.2
- `wan_2.1_vae.safetensors` - WAN VAE version 2.1

## Usage Examples

### Basic Text-to-Image Generation

```python
# Using FLUX
result = await mcp_client.call_tool(
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
result = await mcp_client.call_tool("generate_image", workflow=workflow)
```

### Using LoRA

```python
workflow = WorkflowFactory.create_flux_workflow(
    prompt="robot in inkpunk style",
    lora_name="Inkpunk_Flux.safetensors",
    lora_strength=0.8
)
result = await mcp_client.call_tool("generate_image", workflow=workflow)
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
result = await mcp_client.call_tool("generate_image", workflow=workflow)
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

## Advanced Features

### Custom Workflows
You can provide complete custom workflows by passing a workflow dict to `generate_image`:

```python
custom_workflow = {
    "1": {"inputs": {...}, "class_type": "CheckpointLoaderSimple"},
    # ... your custom nodes
}
result = await mcp_client.call_tool("generate_image", workflow=custom_workflow)
```

### Batch Processing
The workflow factory supports creating workflows with batch sizes > 1 for generating multiple images.

### Seed Control
- Use `seed=-1` for random seeds
- Provide specific seed values for reproducible results

## Troubleshooting

### Common Issues

1. **Timeout Errors**: Increase timeout parameter or reduce image resolution/steps
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
- [ ] AnimateDiff support
- [ ] Regional prompting
- [ ] SDXL Refiner support
