# ComfyUI MCP Server

The ComfyUI MCP server connects directly to a remote ComfyUI instance for AI image generation.

## Architecture

This server acts as a **direct HTTP connection** to the remote ComfyUI MCP server:
- **Remote Server**: Runs on `192.168.0.152:8013`
- **Connection**: Claude connects directly via HTTP (configured in `.mcp.json`)
- **No Local Server Required**: The remote machine handles all MCP functionality

## Configuration

The connection is configured in `.mcp.json`:

```json
"comfyui": {
  "type": "http",
  "url": "http://192.168.0.152:8013/messages"
}
```

## Remote Server Requirements

The remote server at `192.168.0.152` must:
1. Have the ComfyUI MCP server running on port 8013
2. Be accessible from your local network
3. Have NVIDIA GPU support for image generation
4. Have ComfyUI backend running (typically on port 8188)

## Available Tools

When connected to the remote server, these tools are available:

### Image Generation
- `generate_image` - Generate images using ComfyUI workflows
- `generate_image_with_lora` - Generate using specific LoRA models
- `generate_batch` - Batch image generation

### Workflow Management
- `list_workflows` - List available workflows
- `get_workflow` - Get workflow details
- `save_workflow` - Save custom workflows
- `load_workflow` - Load saved workflows

### Model Management
- `list_models` - List available models (checkpoints, LoRAs, VAEs)
- `get_model_info` - Get model details
- `transfer_lora_from_aitoolkit` - Transfer LoRA from AI Toolkit

### Job Management
- `get_generation_status` - Check generation progress
- `cancel_generation` - Cancel active generation
- `get_output_images` - Retrieve generated images

## Usage Examples

```python
# The tools are automatically available in Claude when the remote server is running
# No local setup required - just ensure the remote server is accessible

# Example: Generate an image
result = mcp__comfyui__generate_image(
    prompt="a beautiful landscape",
    negative_prompt="blurry, low quality",
    width=512,
    height=512,
    steps=20
)

# Example: Use LoRA model
result = mcp__comfyui__generate_image_with_lora(
    prompt="character in anime style",
    lora_name="my_trained_lora",
    lora_strength=0.8
)
```

## Integration with AI Toolkit

ComfyUI can use LoRA models trained with AI Toolkit:

1. Train a LoRA using AI Toolkit MCP
2. Transfer the model using `transfer_lora_from_aitoolkit`
3. Use the LoRA in image generation

## Network Requirements

- The remote server must be accessible at `192.168.0.152:8013`
- ComfyUI backend must be running on the remote machine (port 8188)
- Firewall must allow traffic on ports 8013 and 8188
- Both machines must be on the same network or have appropriate routing

## Troubleshooting

1. **Connection Failed**: Verify the remote server is running and accessible
2. **Generation Failed**: Check ComfyUI backend is running on remote machine
3. **LoRA Not Found**: Ensure model was properly transferred from AI Toolkit
4. **Network Issues**: Test connectivity with `curl http://192.168.0.152:8013/health`

## Note on Local Deployment

This setup does **not** run ComfyUI locally due to GPU requirements. The server files in this repository (`server.py`, `stubs.py`) are for reference and testing only. The actual MCP server runs on the remote machine with GPU support.
