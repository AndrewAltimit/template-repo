# ComfyUI MCP Server (Rust)

> A Model Context Protocol server for AI image generation via ComfyUI. Provides text-to-image, image-to-image, upscaling, and ControlNet workflows with LoRA model management.

## Overview

This MCP server integrates with a remote ComfyUI instance to provide:

- Text-to-image generation with FLUX and SDXL/IllustriousXL workflows
- Image-to-image transformation with configurable denoise strength
- AI-powered image upscaling
- ControlNet-guided generation
- LoRA model upload, download, and listing
- Built-in workflow templates with customizable parameters

**Note**: ComfyUI runs on a remote GPU machine (`192.168.0.222`). Do not change the MCP transport URL to localhost in `.mcp.json`. The `COMFYUI_HOST` env var defaults to `localhost` because the MCP server runs co-located with ComfyUI on the remote machine.

## Quick Start

```bash
# Build from source
cd tools/mcp/mcp_comfyui
cargo build --release

# Run in STDIO mode (for Claude Code)
./target/release/mcp-comfyui --mode stdio

# Run in standalone HTTP mode
./target/release/mcp-comfyui --mode standalone --port 8013

# Test health
curl http://localhost:8013/health
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `generate_image` | Generate an image from a text prompt | `prompt` (required), `negative_prompt`, `width`, `height`, `seed`, `steps`, `cfg_scale`, `workflow`, `timeout` |
| `list_workflows` | List available workflow templates | None |
| `get_workflow` | Get a workflow template with sample parameters | `name` |
| `list_models` | List available models by type | `type` (checkpoint, lora, vae) |
| `upload_lora` | Upload a LoRA model (base64-encoded) | `filename` (required), `data` (required), `metadata` |
| `list_loras` | List available LoRA models | None |
| `download_lora` | Download a LoRA model as base64 | `filename` (required) |
| `get_object_info` | Get ComfyUI node and model information | None |
| `get_system_info` | Get ComfyUI system stats (GPU, Python version) | None |
| `execute_workflow` | Execute a custom workflow (non-blocking) | `workflow` (required) |

### Example: Generate Image

```json
{
  "tool": "generate_image",
  "arguments": {
    "prompt": "A beautiful landscape at sunset",
    "negative_prompt": "blurry, low quality",
    "width": 1024,
    "height": 1024,
    "steps": 20,
    "cfg_scale": 3.5
  }
}
```

## Workflow Templates

| Template | Model | Description |
|----------|-------|-------------|
| `flux_default` | FLUX | Default text-to-image (flux1-dev-fp8) |
| `sdxl_default` | SDXL | Text-to-image (IllustriousXL) |
| `flux_with_lora` | FLUX | FLUX with LoRA support |
| `img2img` | Any | Transform existing images with prompts |
| `upscale` | Upscale | AI upscaling (4x-UltraSharp) |
| `controlnet` | Any | Guided generation with control images |

Custom workflows can be passed directly via the `workflow` parameter on `generate_image` or `execute_workflow`.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFYUI_HOST` | `localhost` | ComfyUI server hostname |
| `COMFYUI_PORT` | `8188` | ComfyUI server port |
| `COMFYUI_PATH` | `/comfyui` | ComfyUI installation path (for model management) |
| `COMFYUI_GENERATION_TIMEOUT` | `300` | Image generation timeout in seconds |

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "comfyui": {
      "command": "mcp-comfyui",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Project Structure

```
tools/mcp/mcp_comfyui/
├── Cargo.toml          # Package configuration
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation (10 tools)
    ├── client.rs       # ComfyUI HTTP API client
    ├── workflows.rs    # Workflow templates and factory
    └── types.rs        # Data types (jobs, images, system stats)
```

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [reqwest](https://docs.rs/reqwest) - HTTP client for ComfyUI API
- [tokio](https://tokio.rs/) - Async runtime
- [rand](https://docs.rs/rand) - Random seed generation
- [base64](https://docs.rs/base64) - LoRA data encoding/decoding

## License

Part of the template-repo project. See repository LICENSE file.
