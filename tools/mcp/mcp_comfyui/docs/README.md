# MCP ComfyUI Server

> High-performance MCP server for ComfyUI image generation, providing text-to-image, image-to-image, upscaling, and ControlNet workflows with LoRA support.

## Features

- **Text-to-Image Generation**: FLUX and SDXL/IllustriousXL workflows
- **Image-to-Image**: Transform existing images with text prompts
- **Upscaling**: AI-powered image upscaling
- **ControlNet**: Guided generation using control images
- **LoRA Support**: Upload, list, and use LoRA models
- **Workflow Management**: Pre-built templates and custom workflow execution

## Requirements

- Running ComfyUI instance (remote or local)
- Network access to ComfyUI API

## Installation

### Pre-built Binary

Download from GitHub Releases:

```bash
# Linux x64
curl -L https://github.com/AndrewAltimit/template-repo/releases/latest/download/mcp-comfyui-linux-x64 -o mcp-comfyui
chmod +x mcp-comfyui
```

### Build from Source

```bash
cd tools/mcp/mcp_comfyui
cargo build --release
# Binary will be at target/release/mcp-comfyui
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_HOST` | `192.168.0.222` | ComfyUI server hostname |
| `COMFYUI_PORT` | `8188` | ComfyUI server port |
| `COMFYUI_PATH` | `/opt/ComfyUI` | Path to ComfyUI installation (for model access) |

## Running the Server

### Standalone Mode (Recommended)

```bash
# Start server on port 8013
mcp-comfyui --mode standalone --port 8013

# Or with custom settings
mcp-comfyui --mode standalone --port 8013 --log-level debug
```

### STDIO Mode

For direct MCP client integration:

```bash
mcp-comfyui --mode stdio
```

### Server Mode (REST API only)

```bash
mcp-comfyui --mode server --port 8013
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8013/health

# List tools
curl http://localhost:8013/mcp/tools

# Execute tool
curl -X POST http://localhost:8013/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "list_workflows",
    "arguments": {}
  }'
```

## Available Tools

### 1. generate_image

Generate an image using FLUX or SDXL workflows.

**Parameters:**
- `prompt` (required): Text description of the image to generate
- `negative_prompt` (optional): What to avoid in the image
- `workflow` (optional, default: `flux`): Workflow type (`flux` or `sdxl`)
- `width` (optional, default: 1024): Image width in pixels
- `height` (optional, default: 1024): Image height in pixels
- `seed` (optional, default: -1): Seed for reproducibility (-1 for random)
- `steps` (optional): Sampling steps (default varies by workflow)
- `cfg_scale` (optional): CFG scale (default varies by workflow)
- `lora_name` (optional): LoRA model to apply
- `lora_strength` (optional, default: 1.0): LoRA strength
- `timeout` (optional, default: 300): Timeout in seconds

**Example:**
```json
{
  "prompt": "A cyberpunk cityscape at night, neon lights",
  "workflow": "flux",
  "width": 1024,
  "height": 1024,
  "steps": 20
}
```

### 2. list_workflows

List all available workflow templates.

**Parameters:** None

**Returns:** Array of workflow templates with name, description, and model type.

### 3. get_workflow

Get a sample workflow by name.

**Parameters:**
- `name` (required): Workflow name (e.g., `flux_default`, `sdxl_default`, `img2img`)

### 4. list_models

List available models of a specific type.

**Parameters:**
- `model_type` (required): Type of models (`checkpoint`, `lora`, or `vae`)

### 5. upload_lora

Upload a LoRA model to ComfyUI.

**Parameters:**
- `filename` (required): Filename for the LoRA (must end in .safetensors or .ckpt)
- `data` (required): Base64-encoded LoRA file data
- `metadata` (optional): JSON metadata to save alongside the LoRA

### 6. list_loras

List all uploaded LoRA models.

**Parameters:** None

**Returns:** Array of LoRA info with name, filename, and file size.

### 7. download_lora

Download a LoRA model as base64.

**Parameters:**
- `filename` (required): LoRA filename to download

### 8. get_object_info

Get ComfyUI node information including available nodes and their inputs.

**Parameters:** None

### 9. get_system_info

Get ComfyUI system statistics including GPU info.

**Parameters:** None

**Returns:** System info including Python version and GPU VRAM stats.

### 10. execute_workflow

Execute a custom ComfyUI workflow.

**Parameters:**
- `workflow` (required): Complete workflow JSON
- `timeout` (optional, default: 300): Timeout in seconds

**Example:**
```json
{
  "workflow": {
    "1": {
      "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
      "class_type": "CheckpointLoaderSimple"
    }
  }
}
```

## Workflow Templates

| Template | Description | Model Type |
|----------|-------------|------------|
| `flux_default` | FLUX text-to-image with FP8 checkpoint | flux |
| `sdxl_default` | SDXL/IllustriousXL text-to-image | sdxl |
| `flux_with_lora` | FLUX with LoRA support | flux |
| `img2img` | Image transformation with prompts | any |
| `upscale` | AI upscaling (4x-UltraSharp) | upscale |
| `controlnet` | ControlNet-guided generation | any |

## Default Models

The workflows use these default models (must be available in ComfyUI):

- **FLUX**: `flux1-dev-fp8.safetensors`
- **SDXL**: `illustriousXL_smoothftSOLID.safetensors`
- **Upscale**: `4x-UltraSharp.pth`
- **ControlNet**: `control_v11p_sd15_canny.pth`

## Architecture

### Components

- **MCP Server**: Built on mcp-core Rust library
- **HTTP Client**: reqwest for ComfyUI API communication
- **Async Runtime**: Tokio for high-performance async operations

### Flow

1. Client sends generation request to MCP server
2. Server constructs workflow JSON from parameters
3. Workflow queued to ComfyUI via HTTP API
4. Server polls history endpoint until completion
5. Image paths returned to client

### Error Handling

- **Timeout**: Configurable timeout for long generations
- **ComfyUI Errors**: API errors passed through with status codes
- **Validation**: Parameter validation before queuing

## Integration with .mcp.json

```json
{
  "mcpServers": {
    "comfyui": {
      "command": "mcp-comfyui",
      "args": ["--mode", "standalone", "--port", "8013"],
      "env": {
        "COMFYUI_HOST": "192.168.0.222",
        "COMFYUI_PORT": "8188"
      }
    }
  }
}
```

## Related Documentation

- [MCP Core Rust](../../mcp_core_rust/README.md)
- [AI Toolkit Server](../../mcp_ai_toolkit/README.md)

## License

Part of the template-repo project. See repository root [LICENSE](../../../../LICENSE) file.
