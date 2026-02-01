# AI Toolkit MCP Server (Rust)

> A Model Context Protocol server for managing LoRA training with AI Toolkit, built in Rust for remote GPU machine deployment.

## Overview

This MCP server provides tools for:
- Creating and managing training configurations
- Uploading and organizing training datasets
- Starting, monitoring, and stopping training jobs
- Exporting and downloading trained models
- System monitoring (CPU, memory, disk, GPU)

**Note**: This server is designed to run on a remote GPU machine (e.g., `192.168.0.222:8012`) and be accessed via HTTP transport.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-ai-toolkit --mode standalone --port 8012

# Run in STDIO mode (for local MCP clients)
./target/release/mcp-ai-toolkit --mode stdio

# Test health
curl http://localhost:8012/health
```

## Available Tools (21 total)

### Configuration Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `create_training_config` | Create a new LoRA training configuration | `name` (required), `dataset_path` (required), `model_name`, `resolution`, `steps`, `batch_size`, `rank`, `alpha`, `lr`, `optimizer`, `noise_scheduler`, `trigger_word`, `prompts`, `is_flux`, `is_xl`, `is_v3`, `quantize`, `gradient_checkpointing`, `cache_latents`, `caption_dropout_rate` |
| `list_configs` | List all training configurations | None |
| `get_config` | Get a specific configuration | `name` (required) |
| `delete_config` | Delete a configuration file | `name` (required) |
| `validate_config` | Validate config before training | `name` (required) |

### Dataset Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `upload_dataset` | Upload images to create a dataset | `dataset_name` (required), `images` (required) |
| `list_datasets` | List all available datasets | None |
| `get_dataset_info` | Get detailed dataset info | `name` (required) |
| `delete_dataset` | Delete a dataset | `name` (required) |

### Training Operations

| Tool | Description | Parameters |
|------|-------------|------------|
| `start_training` | Start a training job | `config_name` (required) |
| `get_training_status` | Get job status and progress | `job_id` (required) |
| `stop_training` | Stop a running training job | `job_id` (required) |
| `list_training_jobs` | List all training jobs | None |
| `get_training_logs` | Get training logs | `job_id` (required), `lines` |
| `get_training_info` | Get overall training info | None |

### Model Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `export_model` | Export a trained model | `model_name` (required), `output_path` |
| `list_exported_models` | List exported models | None |
| `download_model` | Download model as base64 | `model_name` (required), `encoding` |
| `delete_model` | Delete a model file | `name` (required) |

### Utilities

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_system_stats` | Get system statistics | None |
| `list_model_presets` | List recommended model presets | None |

## Supported Models

The server supports multiple model architectures with smart defaults:

| Model | Path | Scheduler | Quantize | Min VRAM |
|-------|------|-----------|----------|----------|
| **Flux.1-dev** | `black-forest-labs/FLUX.1-dev` | flowmatch | Yes | 24GB |
| **Flux.1-schnell** | `black-forest-labs/FLUX.1-schnell` | flowmatch | Yes | 24GB |
| **SD 3.5 Large** | `stabilityai/stable-diffusion-3.5-large` | flowmatch | Yes | 24GB |
| **SDXL** | `stabilityai/stable-diffusion-xl-base-1.0` | ddpm | No | 12GB |
| **SD 1.5** | `runwayml/stable-diffusion-v1-5` | ddpm | No | 8GB |

Use `list_model_presets` to see all presets with recommended settings.

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8012]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_TOOLKIT_PATH` | Base path for AI Toolkit installation | `/ai-toolkit` |

### Directory Structure

The server uses the following directories within `AI_TOOLKIT_PATH`:

```
/ai-toolkit/
  config/      # Training configuration YAML files
  datasets/    # Training image datasets
  outputs/     # Trained models and logs
```

## Transport Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **standalone** | Full MCP server with HTTP transport | Production, Docker |
| **stdio** | STDIO transport for direct integration | Local MCP clients |
| **server** | REST API only (no MCP protocol) | Microservices |
| **client** | MCP proxy to REST backend | Horizontal scaling |

## MCP Configuration

Add to `.mcp.json` for HTTP transport (recommended for remote GPU):

```json
{
  "mcpServers": {
    "aitoolkit": {
      "type": "http",
      "url": "http://192.168.0.222:8012/messages"
    }
  }
}
```

Or for STDIO mode (local):

```json
{
  "mcpServers": {
    "aitoolkit": {
      "command": "mcp-ai-toolkit",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_ai_toolkit

# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run tests
cargo test

# Run clippy
cargo clippy -- -D warnings

# Format code
cargo fmt
```

## Project Structure

```
tools/mcp/mcp_ai_toolkit/
  Cargo.toml          # Package configuration
  README.md           # This file
  src/
    main.rs         # CLI entry point
    server.rs       # MCP tools implementation
    config.rs       # Path validation and configuration
    types.rs        # Data structures
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Testing

```bash
# Run unit tests
cargo test

# Test HTTP endpoints (after starting server)
curl http://localhost:8012/health
curl http://localhost:8012/mcp/tools

# Create a training config
curl -X POST http://localhost:8012/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "create_training_config",
    "arguments": {
      "name": "my_lora",
      "model_name": "runwayml/stable-diffusion-v1-5",
      "dataset_path": "/ai-toolkit/datasets/my_dataset",
      "steps": 1000,
      "rank": 16
    }
  }'

# List training jobs
curl -X POST http://localhost:8012/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "list_training_jobs", "arguments": {}}'
```

## Security

### Path Validation

All user-provided paths are validated to prevent directory traversal attacks:
- Absolute paths are rejected
- Parent directory references (`..`) are blocked
- Paths must resolve within their designated base directories

### Process Isolation

Training jobs run as subprocess with their own environment, isolated from the MCP server process.

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [tokio](https://tokio.rs/) - Async runtime with process support
- [serde_yaml](https://github.com/dtolnay/serde-yaml) - YAML serialization
- [sysinfo](https://github.com/GuillaumeGomez/sysinfo) - System information
- [base64](https://github.com/marshallpierce/rust-base64) - Base64 encoding

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~20ms |
| List configs | ~5ms |
| Create config | ~10ms |
| Start training | ~100ms (excludes training time) |
| Get system stats | ~50ms |

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Configuration not found" | Config file doesn't exist | Check config name and list_configs |
| "Permission denied" | Directory not writable | Ensure AI_TOOLKIT_PATH is writable |
| Training fails to start | Python/AI Toolkit not installed | Verify AI Toolkit installation |
| "Model not found" | Model file doesn't exist | Check list_exported_models |

## License

Part of the template-repo project. See repository LICENSE file.
