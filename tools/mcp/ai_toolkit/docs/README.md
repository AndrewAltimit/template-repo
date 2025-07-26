# AI Toolkit MCP Server

The AI Toolkit MCP Server provides a Model Context Protocol interface for managing AI model training, particularly for LoRA (Low-Rank Adaptation) models.

## Overview

This MCP server acts as a bridge to a remote AI Toolkit instance running on `192.168.0.152:8012`. It provides tools for:

- Creating and managing training configurations
- Uploading and managing datasets
- Starting and monitoring training jobs
- Exporting and downloading trained models
- System monitoring and logs

## Architecture

The server follows a bridge pattern:
1. Local MCP server runs on port 8012
2. Forwards requests to remote AI Toolkit at `192.168.0.152:8012`
3. Handles authentication and error handling
4. Provides a consistent MCP interface

## Available Tools

### Training Configuration
- `create_training_config` - Create new training configurations
- `list_configs` - List all configurations
- `get_config` - Get specific configuration details

### Dataset Management
- `upload_dataset` - Upload images with captions for training
- `list_datasets` - List available datasets

### Training Control
- `start_training` - Start a training job
- `get_training_status` - Check training progress
- `stop_training` - Stop a running job
- `list_training_jobs` - List all jobs

### Model Management
- `export_model` - Export trained models
- `list_exported_models` - List exported models
- `download_model` - Download model files

### System Information
- `get_system_stats` - GPU and system statistics
- `get_training_logs` - Training job logs
- `get_training_info` - Training capabilities

## Configuration

Environment variables:
- `AI_TOOLKIT_HOST` - Remote host (default: 192.168.0.152)
- `AI_TOOLKIT_PORT` - Remote port (default: 8012)

## Usage Example

```python
# Create a training configuration
config = await create_training_config(
    name="my_lora_v1",
    model_name="ostris/Flux.1-alpha",
    dataset_path="/ai-toolkit/datasets/my_dataset",
    resolution=512,
    steps=1000,
    trigger_word="my_style"
)

# Start training
job = await start_training(config_name="my_lora_v1")

# Check status
status = await get_training_status(job_id=job["job_id"])
```

## Important Notes

1. **Dataset Paths**: Must use absolute paths starting with `/ai-toolkit/datasets/`
2. **Low VRAM Mode**: Enable for GPUs with <24GB memory
3. **Remote Dependency**: Requires AI Toolkit server running on remote host

## Testing

Run the test script to verify connectivity:

```bash
python tools/mcp/ai_toolkit/scripts/test_server.py
```

## Integration with ComfyUI

Trained LoRA models can be transferred to ComfyUI using the ComfyUI MCP server's `transfer_lora_from_ai_toolkit` tool.
