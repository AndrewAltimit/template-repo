# ComfyUI MCP Server

> A Model Context Protocol server for AI image and video generation using ComfyUI workflows, with support for FLUX, SDXL, LoRA models, and custom workflow execution.

## Overview

This MCP server provides an interface to ComfyUI for AI image and video generation. It can run locally or connect to a remote instance. Features include:

- Advanced workflow system with FLUX, SDXL, and WAN 2.2 video support
- Text-to-video and image-to-video generation
- LoRA and checkpoint model management
- Custom ComfyUI workflow execution
- Image-to-image, upscaling, and ControlNet support
- Model transfer between AI services

## Architecture

The server provides flexible deployment options:
1. **Local Mode**: Runs alongside ComfyUI on the same machine
2. **Remote Mode**: Connects to ComfyUI instance (e.g., `192.168.0.222:8188`)
3. **Docker Mode**: Containerized deployment with GPU support

### Workflow System
The server includes a sophisticated workflow factory that creates optimized workflows for different model types. See [WORKFLOWS.md](WORKFLOWS.md) for detailed workflow documentation.

## Available Tools

### Image & Video Generation
- `generate_image` - Generate images or videos with workflows
- `execute_workflow` - Execute custom ComfyUI workflows

### Workflow Management
- `list_workflows` - List available workflows
- `get_workflow` - Get workflow configuration

### Model Management
- `list_models` - List models by type (checkpoint, lora, vae, embeddings)
- `list_loras` - List LoRA models
- `upload_lora` - Upload LoRA model (small files)
- `download_lora` - Download LoRA model

### Chunked Upload (for large files >100MB)
- `upload_lora_chunked_init` - Initialize chunked upload
- `upload_lora_chunk` - Upload file chunk
- `upload_lora_chunked_complete` - Complete upload

### Integration Tools
- `transfer_lora_from_ai_toolkit` - Transfer LoRA from AI Toolkit
- `get_object_info` - Get ComfyUI node information
- `get_system_info` - Get system information

## Configuration

Environment variables:
- `COMFYUI_HOST` - ComfyUI host (default: localhost)
- `COMFYUI_PORT` - ComfyUI API port (default: 8188)
- `COMFYUI_PATH` - ComfyUI installation path (default: /comfyui)
- `COMFYUI_GENERATION_TIMEOUT` - Generation timeout in seconds (default: 300)

## Usage Examples

### Generate Image with FLUX
```python
# FLUX performs best with lower CFG values
result = await generate_image(
    prompt="a cyberpunk city at night, neon lights",
    negative_prompt="",  # Can be empty for FLUX
    width=1024,
    height=1024,
    steps=20,
    cfg_scale=3.5  # Lower CFG for FLUX
)
```

### Generate with IllustriousXL
```python
from mcp_comfyui.workflows import WorkflowFactory

workflow = WorkflowFactory.create_sdxl_workflow(
    prompt="anime character, silver hair, detailed",
    negative_prompt="low quality, bad anatomy",
    model_name="illustriousXL_smoothftSOLID.safetensors",
    steps=30,
    cfg_scale=7.0
)
result = await generate_image(workflow=workflow)
```

### Using LoRA
```python
workflow = WorkflowFactory.create_flux_workflow(
    prompt="robot in inkpunk art style",
    lora_name="Inkpunk_Flux.safetensors",
    lora_strength=0.8
)
result = await generate_image(workflow=workflow)
```

### Generate Video with WAN 2.2
```python
# Text-to-video generation
workflow = WorkflowFactory.create_wan22_video_workflow(
    prompt="a cat playing with a ball of yarn, smooth motion",
    negative_prompt="static, blurry, choppy",
    width=1280,
    height=704,
    video_frames=121,  # 5 seconds at 24fps
    output_format="webm"
)
result = await generate_image(workflow=workflow, timeout=600)  # Longer timeout for video

# Image-to-video (animate a still image)
with open("cat.jpg", "rb") as f:
    start_image = base64.b64encode(f.read()).decode()

workflow = WorkflowFactory.create_wan22_video_workflow(
    prompt="cat slowly turns head and blinks",
    start_image=start_image,
    video_frames=60  # 2.5 seconds
)
result = await generate_image(workflow=workflow)
```

### Upload LoRA (Chunked)
```python
# For files >100MB
init_result = await upload_lora_chunked_init(
    filename="my_lora.safetensors",
    total_size=file_size_bytes
)

# Upload chunks
for i, chunk in enumerate(chunks):
    await upload_lora_chunk(
        upload_id=init_result["upload_id"],
        chunk_index=i,
        chunk=base64_chunk,
        total_chunks=len(chunks)
    )

# Complete upload
await upload_lora_chunked_complete(upload_id=init_result["upload_id"])
```

## Supported Models

### Current Models
- **FLUX**: `flux1-dev-fp8.safetensors` - Latest FLUX development model
- **SDXL**: `illustriousXL_smoothftSOLID.safetensors` - High-quality anime/illustration
- **Video**: `wan2.2_ti2v_5B_fp16.safetensors` - WAN 2.2 text/image-to-video model
- **LoRA**: `Inkpunk_Flux.safetensors` - Inkpunk art style for FLUX

### Model-Specific Settings

#### FLUX
- **CFG Scale**: 3.0-4.0 (lower is better)
- **Steps**: 20-30
- **Sampler**: euler, dpm++
- **Resolution**: 1024x1024 minimum

#### SDXL/IllustriousXL
- **CFG Scale**: 6.0-8.0
- **Steps**: 25-40
- **Sampler**: dpmpp_2m, dpmpp_sde
- **Scheduler**: karras

#### WAN 2.2 Video
- **CFG Scale**: 4.0-6.0 (5.0 optimal)
- **Steps**: 25-35 (30 optimal)
- **Sampler**: uni_pc
- **Resolution**: 1280x704 (optimal)
- **Frames**: 121 frames (~5 seconds at 24fps)

For comprehensive workflow documentation, see [WORKFLOWS.md](WORKFLOWS.md).

## Testing

Run the test script to verify connectivity:

```bash
python tools/mcp/comfyui/scripts/test_server.py
```

## Integration with AI Toolkit

Models trained in AI Toolkit can be transferred directly:

```python
await transfer_lora_from_ai_toolkit(
    model_name="my_trained_lora",
    filename="my_lora_v1.safetensors"
)
```

## Important Notes

1. **Chunked Upload**: Required for files >100MB
2. **FLUX Models**: Have specific workflow requirements
3. **Remote Dependency**: Requires ComfyUI server running on remote host

## License

Part of the template-repo project. See repository LICENSE file.
