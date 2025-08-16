# AI Toolkit MCP Server

The AI Toolkit MCP server connects directly to a remote AI Toolkit instance for LoRA training and model management.

## Architecture

This server acts as a **direct HTTP connection** to the remote AI Toolkit MCP server:
- **Remote Server**: Runs on `192.168.0.152:8012`
- **Connection**: Claude connects directly via HTTP (configured in `.mcp.json`)
- **No Local Server Required**: The remote machine handles all MCP functionality

## Configuration

The connection is configured in `.mcp.json`:

```json
"aitoolkit": {
  "type": "http",
  "url": "http://192.168.0.152:8012/messages"
}
```

## Remote Server Requirements

The remote server at `192.168.0.152` must:
1. Have the AI Toolkit MCP server running on port 8012
2. Be accessible from your local network
3. Have NVIDIA GPU support for training

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

## Note on Local Deployment

This setup does **not** run AI Toolkit locally due to GPU requirements. The server files in this repository (`server.py`, `stubs.py`) are for reference and testing only. The actual MCP server runs on the remote machine with GPU support.
