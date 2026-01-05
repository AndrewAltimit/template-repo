# ComfyUI MCP Server

The ComfyUI MCP server provides GPU-accelerated AI image generation with workflow support.

## Architecture

This MCP server runs on a GPU-enabled machine and provides:
- **Containerized Deployment**: Runs in Docker with NVIDIA GPU support
- **MCP Protocol**: Full MCP server implementation for ComfyUI functionality
- **Remote Access**: Can be accessed via HTTP from any machine on the network
- **Default Location**: Typically runs on `192.168.0.152:8013`

## Configuration

The connection is configured in `.mcp.json`:

```json
"comfyui": {
  "type": "http",
  "url": "http://192.168.0.152:8013/messages"
}
```

## Deployment on GPU Machine

### Requirements
1. NVIDIA GPU with CUDA support
2. Docker with nvidia-docker2 runtime
3. Network access on port 8013

### Quick Start (on GPU machine)
```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Start the ComfyUI MCP server
./automation/scripts/remote-ai-services.sh start

# Or use docker-compose directly
docker-compose --profile ai-services up -d mcp-comfyui
```

### Host Mode (alternative)
```bash
# Run directly on host with GPU
./automation/scripts/start-ai-services.sh host
```

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

## Container Management

```bash
# View logs
docker-compose logs -f mcp-comfyui

# Restart service
docker-compose restart mcp-comfyui

# Stop service
docker-compose --profile ai-services down

# Update and restart
./automation/scripts/remote-ai-services.sh update
```

## Architecture Notes

- The MCP server runs in a Docker container with GPU passthrough
- Uses NVIDIA CUDA 12.1 base image for optimal performance
- Volumes are used for persistent storage of models, outputs, and inputs
- Can run alongside AI Toolkit MCP server for integrated LoRA workflows
- Includes ComfyUI backend for workflow execution

## License

Part of the template-repo project. See repository LICENSE file.
