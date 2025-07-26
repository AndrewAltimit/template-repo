# ComfyUI MCP Server

The ComfyUI MCP Server provides a Model Context Protocol interface for AI image generation using ComfyUI workflows.

## Overview

This MCP server acts as a bridge to a remote ComfyUI instance running on `192.168.0.152:8013`. It provides tools for:

- Generating images with various workflows
- Managing LoRA and checkpoint models
- Executing custom ComfyUI workflows
- Transferring models between services

## Architecture

The server follows a bridge pattern:
1. Local MCP server runs on port 8013
2. Forwards requests to remote ComfyUI at `192.168.0.152:8013`
3. Handles large file transfers with chunking
4. Provides a consistent MCP interface

## Available Tools

### Image Generation
- `generate_image` - Generate images with text prompts
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
- `COMFYUI_HOST` - Remote host (default: 192.168.0.152)
- `COMFYUI_PORT` - Remote port (default: 8013)

## Usage Examples

### Generate Image
```python
result = await generate_image(
    prompt="a beautiful landscape, highly detailed",
    negative_prompt="blurry, low quality",
    width=1024,
    height=1024,
    steps=20,
    cfg_scale=7.0
)
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

### FLUX Workflow Requirements

When using FLUX models:
- Use `FluxGuidance` node with guidance ~3.5
- KSampler settings: cfg=1.0, sampler="heunpp2", scheduler="simple"
- Negative prompt cannot be null (use empty string)

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
