# LoRA Model Transfer Documentation

This document describes the process of transferring trained LoRA models from AI Toolkit to ComfyUI.

## Overview

When training a LoRA model with AI Toolkit and using it in ComfyUI for image generation, the model file needs to be transferred between services. Both services run on the same server (192.168.0.152) but have separate model directories.

## Transfer Methods

### Method 1: API Transfer (Size Limited)

**Limitation**: HTTP APIs have request size limits that prevent uploading files larger than ~50-100MB.

For small LoRA files (<50MB):
```python
# Download from AI Toolkit
response = requests.post('http://192.168.0.152:8190/mcp/tool', json={
    "tool": "download-model",
    "arguments": {
        "model_path": "model_name/model.safetensors",
        "include_metadata": True
    }
})

# Upload to ComfyUI (will fail for large files)
upload_response = requests.post('http://192.168.0.152:8189/mcp/tool', json={
    "tool": "upload-lora",
    "arguments": {
        "filename": "model.safetensors",
        "content": base64_content  # Too large!
    }
})
```

### Method 2: Server-Side File Copy (Recommended for Local Transfer)

Since both services run on the same server, the most efficient method is direct file copying:

```bash
# On the server (192.168.0.152)
# Copy from AI Toolkit outputs to ComfyUI models
cp /ai-toolkit/outputs/[model_name]/[model_file].safetensors \
   /comfyui/models/loras/[model_file].safetensors
```

For Docker deployments:
```bash
# Copy between Docker containers
docker cp ai-toolkit-container:/ai-toolkit/outputs/model.safetensors \
          comfyui-container:/comfyui/models/loras/model.safetensors
```

### Method 3: Chunked Upload (Recommended for API Transfer)

The ComfyUI MCP server supports chunked uploads for large files:
- Split file into 256KB chunks
- Use upload-lora-chunked-start/append/finish sequence
- Successfully tested with 112MB LoRA file

Example implementation:
```python
# See transfer_lora_between_services.py for full implementation
upload_id = str(uuid.uuid4())
# Start upload with upload_id, filename, total_size
# Append chunks with upload_id, chunk (base64), chunk_index
# Finish upload with upload_id
```

## Our Specific Case

For the Pixel cat birthday LoRA:
- **Model**: pixel_cat_birthday_lora_v2.safetensors
- **Size**: 112.40 MB (too large for standard HTTP upload)
- **Source**: `/ai-toolkit/outputs/pixel_cat_birthday_lora_v2/pixel_cat_birthday_lora_v2.safetensors`
- **Destination**: `/comfyui/models/loras/pixel_cat_birthday_lora.safetensors`

## Workflow Integration

Once the LoRA is available in ComfyUI's models directory, it can be used in workflows:

```json
{
  "2": {
    "class_type": "LoraLoader",
    "inputs": {
      "lora_name": "pixel_cat_birthday_lora.safetensors",
      "strength_model": 1.0,
      "strength_clip": 1.0,
      "model": ["1", 0],  // From CheckpointLoaderSimple
      "clip": ["1", 1]    // From CheckpointLoaderSimple
    }
  }
}
```

## Important Notes

1. **LoRA Weight**: Always connect the LoRA loader between the checkpoint loader and the sampler
2. **Strength**: Use 1.0 for full effect, lower values for subtle influence
3. **Trigger Words**: Include the trigger word (e.g., "pixel_cat") in prompts
4. **Verification**: Use list-loras tool to verify the model is available after transfer
5. **FLUX Workflows**: Require different structure - see docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md

## Error Prevention

Common issues and solutions:
- **"Value not in list" error**: LoRA file not found in ComfyUI models directory
- **"Request Entity Too Large"**: File too big for HTTP upload, use chunked transfer
- **No LoRA effect**: Ensure LoRA loader is properly connected in the workflow
- **"NoneType not iterable"**: Don't pass null to negative prompt, use empty string
- **Wrong parameters**: Check actual implementation, not just documentation
- **Size mismatch**: Use "chunk" not "chunk_data", provide upload_id

## Key Discovery

The MCP tools list may not show all available tools! Always check the source:
- [ComfyUI MCP gist](https://gist.github.com/AndrewAltimit/f2a21b1a075cc8c9a151483f89e0f11e)

The chunked upload tools (upload-lora-chunked-start/append/finish) exist even if not listed!
