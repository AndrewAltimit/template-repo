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

#### create_training_config
Create new training configurations with detailed parameters.

**Parameters:**
- `name` (string, required): Configuration name
- `model_name` (string, required): Base model to train from (e.g., "ostris/Flux.1-alpha")
- `dataset_path` (string, required): Path to training dataset
- `resolution` (integer): Training resolution (default: 512)
- `steps` (integer): Number of training steps (default: 1000)
- `rank` (integer): LoRA rank (default: 16)
- `alpha` (integer): LoRA alpha (default: 16)
- `low_vram` (boolean): Enable low VRAM mode for GPUs with <24GB (default: true)
- `trigger_word` (string): Trigger word for the LoRA
- `test_prompts` (array): Test prompts for validation

#### list_configs
List all available training configurations.

#### get_config
Get details of a specific training configuration.

**Parameters:**
- `name` (string, required): Configuration name

### Dataset Management

#### upload_dataset
Upload images with captions for training. Supports chunked upload for large files (>100MB).

**Parameters:**
- `dataset_name` (string, required): Name for the dataset
- `images` (array, required): Array of image objects
  - `filename` (string): Image filename
  - `data` (string): Base64 encoded image data
  - `caption` (string): Image caption for training

**Note**: For files larger than 100MB, the upload is automatically chunked to prevent timeouts.

#### list_datasets
List all available datasets in the AI Toolkit.

### Training Control

#### start_training
Start a new training job with a configuration.

**Parameters:**
- `config_name` (string, required): Configuration name to use

**Returns:**
- `job_id`: Unique identifier for the training job
- `status`: Initial job status
- `estimated_time`: Estimated completion time

#### get_training_status
Check the progress of a training job.

**Parameters:**
- `job_id` (string, required): Training job ID

**Returns:**
- `status`: Current job status (running, completed, failed)
- `progress`: Progress percentage
- `current_step`: Current training step
- `total_steps`: Total training steps
- `loss`: Current training loss
- `estimated_time_remaining`: Time remaining estimate

#### stop_training
Stop a running training job.

**Parameters:**
- `job_id` (string, required): Training job ID to stop

#### list_training_jobs
List all training jobs with their current status.

### Model Management

#### export_model
Export a trained model to a specific format.

**Parameters:**
- `model_name` (string, required): Model name to export
- `output_path` (string, required): Output path for the exported model

#### list_exported_models
List all exported models available for download.

#### download_model
Download a trained model file.

**Parameters:**
- `model_name` (string, required): Model name to download
- `encoding` (string): Output encoding - "base64" or "raw" (default: "base64")

### System Information

#### get_system_stats
Get GPU and system statistics from the AI Toolkit server.

**Returns:**
- `gpu_memory_used`: Current GPU memory usage
- `gpu_memory_total`: Total GPU memory
- `gpu_utilization`: GPU utilization percentage
- `system_memory`: System RAM usage
- `disk_space`: Available disk space

#### get_training_logs
Get training logs for a specific job.

**Parameters:**
- `job_id` (string, required): Training job ID
- `lines` (integer): Number of log lines to retrieve (default: 100)

#### get_training_info
Get detailed information about training capabilities.

**Returns:**
- `supported_models`: List of supported base models
- `max_resolution`: Maximum supported resolution
- `gpu_info`: GPU specifications
- `training_presets`: Available training presets

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
2. **Low VRAM Mode**: Enable for GPUs with <24GB memory (automatically enabled by default)
3. **Remote Dependency**: Requires AI Toolkit server running on remote host
4. **Chunked Upload**: Files larger than 100MB are automatically chunked for reliable upload
5. **FLUX Models**: When using FLUX models, ensure proper configuration:
   - Use `cfg=1.0` for FLUX models
   - Different scheduler requirements
   - Special node configurations in ComfyUI
6. **Network Requirements**: Ensure network connectivity to `192.168.0.152:8012`

## Testing

Run the test script to verify connectivity:

```bash
# Test server connectivity and basic operations
python tools/mcp/ai_toolkit/scripts/test_server.py

# The test script will:
# 1. Check server health
# 2. List available configurations
# 3. Test dataset listing
# 4. Verify system stats retrieval
# 5. Test training info endpoint
```

## Docker Support

The AI Toolkit MCP server can run as a bridge in a container:

```yaml
# docker-compose.yml
services:
  mcp-ai-toolkit:
    build:
      context: .
      dockerfile: docker/mcp-ai-toolkit.Dockerfile
    ports:
      - "8012:8012"
    environment:
      - AI_TOOLKIT_HOST=192.168.0.152
      - AI_TOOLKIT_PORT=8012
    networks:
      - mcp-network
```

## Integration with ComfyUI

Trained LoRA models can be transferred to ComfyUI using the ComfyUI MCP server's transfer tools.

### LoRA Transfer Workflow

1. **Train LoRA in AI Toolkit**:
   ```python
   # Create config and start training
   config = await create_training_config(
       name="my_style_lora",
       model_name="ostris/Flux.1-alpha",
       dataset_path="/ai-toolkit/datasets/my_style"
   )
   job = await start_training(config_name="my_style_lora")
   ```

2. **Export the Model**:
   ```python
   await export_model(
       model_name="my_style_lora",
       output_path="/ai-toolkit/outputs/my_style_lora.safetensors"
   )
   ```

3. **Transfer to ComfyUI** (using ComfyUI MCP):
   ```python
   await transfer_lora(
       source_path="/ai-toolkit/outputs/my_style_lora.safetensors",
       lora_name="my_style_lora"
   )
   ```

4. **Use in ComfyUI Workflows**:
   The LoRA will be available in ComfyUI's LoRA loader nodes.

## Troubleshooting

### Common Issues

1. **Connection Error (503)**:
   - Verify AI Toolkit server is running on `192.168.0.152:8012`
   - Check network connectivity
   - Ensure no firewall blocking the port

2. **Upload Timeout**:
   - Large files are automatically chunked
   - If still timing out, reduce batch size
   - Check network bandwidth

3. **Low VRAM Errors**:
   - Enable `low_vram: true` in configuration
   - Reduce batch size
   - Lower resolution if necessary

4. **Dataset Path Errors**:
   - Always use absolute paths starting with `/ai-toolkit/datasets/`
   - Ensure dataset exists on remote server
   - Check file permissions

## See Also

- [AI Toolkit & ComfyUI Integration Guide](../../../../docs/integrations/creative-tools/ai-toolkit-comfyui.md)
- [LoRA Transfer Documentation](../../../../docs/integrations/creative-tools/lora-transfer.md)
- [ComfyUI MCP Server](../../comfyui/docs/README.md)
