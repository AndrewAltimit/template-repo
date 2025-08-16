# Creative Tools Integration

Integration documentation for AI image generation, LoRA training, and creative content tools.

## 📚 Available Integrations

### [AI Toolkit & ComfyUI Integration](./ai-toolkit-comfyui.md)
Comprehensive guide for LoRA training and image generation
- AI Toolkit setup and configuration
- ComfyUI workflow integration
- Dataset preparation
- Training job management
- Image generation pipelines

### [LoRA Transfer Documentation](./lora-transfer.md)
Automated model transfer between AI Toolkit and ComfyUI
- Transfer workflow
- File management
- Model versioning
- Troubleshooting

## 🚀 Quick Start

### For LoRA Training
1. Prepare dataset in required format
2. Upload to AI Toolkit via MCP tools
3. Configure training parameters
4. Monitor training progress
5. Transfer trained model to ComfyUI

### For Image Generation
1. Select or create ComfyUI workflow
2. Load LoRA models if needed
3. Configure generation parameters
4. Execute workflow via MCP tools

## 🌐 Remote Services

These integrations connect to remote instances:

| Service | Default URL | Purpose |
|---------|-------------|---------|
| AI Toolkit | `192.168.0.152:8012` | LoRA training |
| ComfyUI | `192.168.0.152:8013` | Image generation |

## 🛠️ MCP Tools Available

### AI Toolkit Tools
- `upload_dataset` - Upload training datasets
- `create_lora_config` - Configure training
- `start_training` - Begin training job
- `monitor_training` - Check progress
- `export_lora` - Export trained model

### ComfyUI Tools
- `generate_image` - Generate images
- `list_lora_models` - List available LoRAs
- `transfer_lora` - Transfer from AI Toolkit
- `execute_workflow` - Run custom workflows

## 📁 File Paths

- **Datasets**: `/ai-toolkit/datasets/`
- **LoRA Models**: `/ai-toolkit/output/`
- **ComfyUI Models**: `/comfyui/models/loras/`

## 📖 Related Documentation

- [Integrations Overview](../README.md)
- [MCP Servers](../../mcp/servers.md)
- [AI Toolkit MCP](../../../tools/mcp/ai_toolkit/docs/README.md)
- [ComfyUI MCP](../../../tools/mcp/comfyui/docs/README.md)
