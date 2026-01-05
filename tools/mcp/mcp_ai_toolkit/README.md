# AI Toolkit MCP Server

> A Model Context Protocol server for GPU-accelerated LoRA training and model management, providing remote access to AI model fine-tuning capabilities.

## Architecture

This MCP server runs on a GPU-enabled machine and provides:
- **Containerized Deployment**: Runs in Docker with NVIDIA GPU support
- **MCP Protocol**: Full MCP server implementation for AI Toolkit functionality
- **Remote Access**: Can be accessed via HTTP from any machine on the network
- **Default Location**: Typically runs on `192.168.0.152:8012`

## Configuration

The connection is configured in `.mcp.json`:

```json
"aitoolkit": {
  "type": "http",
  "url": "http://192.168.0.152:8012/messages"
}
```

## Deployment on GPU Machine

### Requirements
1. NVIDIA GPU with CUDA support
2. Docker with nvidia-docker2 runtime
3. Network access on port 8012

### Quick Start (on GPU machine)
```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Start the AI Toolkit MCP server
./automation/scripts/remote-ai-services.sh start

# Or use docker-compose directly
docker-compose --profile ai-services up -d mcp-ai-toolkit
```

### Host Mode (alternative)
```bash
# Run directly on host with GPU
./automation/scripts/start-ai-services.sh host
```

## Available Tools

When connected to the remote server, these tools are available:

### Training Management
- `create_training_config` - Create new LoRA training configurations
- `list_configs` - List all training configurations
- `get_config` - Get specific configuration details
- `update_config` - Modify existing configurations
- `delete_config` - Remove configurations

### Dataset Management
- `upload_dataset` - Upload training datasets (supports chunked uploads for large files)
- `list_datasets` - List available datasets
- `delete_dataset` - Remove datasets

### Training Operations
- `start_training` - Begin training with a configuration
- `stop_training` - Stop an active training job
- `get_training_status` - Check training progress
- `list_training_jobs` - List all training jobs

### Model Management
- `list_models` - List trained models
- `get_model_info` - Get model details
- `export_model` - Export models in various formats
- `download_model` - Download trained models
- `delete_model` - Remove models

## Usage Examples

```python
# The tools are automatically available in Claude when the remote server is running
# No local setup required - just ensure the remote server is accessible

# Example: Start training
result = mcp__aitoolkit__start_training(
    config_name="my_lora_config",
    gpu_index=0
)

# Example: Check status
status = mcp__aitoolkit__get_training_status(
    job_id=result["job_id"]
)
```

## Network Requirements

- The remote server must be accessible at `192.168.0.152:8012`
- Firewall must allow traffic on port 8012
- Both machines must be on the same network or have appropriate routing

## Troubleshooting

1. **Connection Failed**: Verify the remote server is running and accessible
2. **Tool Not Available**: Check that the remote MCP server is properly configured
3. **Network Issues**: Test connectivity with `curl http://192.168.0.152:8012/health`

## Container Management

```bash
# View logs
docker-compose logs -f mcp-ai-toolkit

# Restart service
docker-compose restart mcp-ai-toolkit

# Stop service
docker-compose --profile ai-services down

# Update and restart
./automation/scripts/remote-ai-services.sh update
```

## Architecture Notes

- The MCP server runs in a Docker container with GPU passthrough
- Uses NVIDIA CUDA 12.1 base image for optimal performance
- Volumes are used for persistent storage of datasets, models, and configs
- Can run alongside ComfyUI MCP server for integrated workflows

## License

Part of the template-repo project. See repository LICENSE file.
