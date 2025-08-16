# Integration Documentation

Documentation for external service integrations including AI services and creative tools.

## 📁 Categories

### [AI Services](./ai-services/)
Integration with AI platforms and services
- **[Gemini Setup](./ai-services/gemini-setup.md)** - Gemini CLI configuration
- **[OpenCode & Crush](./ai-services/opencode-crush.md)** - Comprehensive code generation
- **[Quick Reference](./ai-services/opencode-crush-ref.md)** - OpenCode & Crush quick guide
- **[OpenRouter Setup](./ai-services/openrouter-setup.md)** - OpenRouter API configuration

### [Creative Tools](./creative-tools/)
Integration with creative and content generation tools
- **[AI Toolkit & ComfyUI](./creative-tools/ai-toolkit-comfyui.md)** - LoRA training and image generation
- **[LoRA Transfer](./creative-tools/lora-transfer.md)** - Model transfer between services

## 🚀 Quick Start by Use Case

### For Code Generation
1. Set up OpenRouter API - [OpenRouter Setup](./ai-services/openrouter-setup.md)
2. Configure OpenCode/Crush - [Integration Guide](./ai-services/opencode-crush.md)
3. Use quick commands - [Quick Reference](./ai-services/opencode-crush-ref.md)

### For AI Image Generation
1. Configure AI Toolkit - [AI Toolkit & ComfyUI](./creative-tools/ai-toolkit-comfyui.md)
2. Set up LoRA training - [LoRA Transfer](./creative-tools/lora-transfer.md)

### For Code Reviews
1. Install Gemini CLI - [Gemini Setup](./ai-services/gemini-setup.md)
2. Configure API keys and authentication

## 🔑 API Keys Required

| Service | Environment Variable | Documentation |
|---------|---------------------|---------------|
| OpenRouter | `OPENROUTER_API_KEY` | [OpenRouter Setup](./ai-services/openrouter-setup.md) |
| Gemini | `GEMINI_API_KEY` | [Gemini Setup](./ai-services/gemini-setup.md) |

## 🌐 Remote Services

Some integrations connect to remote services:
- **AI Toolkit**: `192.168.0.152:8012`
- **ComfyUI**: `192.168.0.152:8013`
- **Gaea2**: `192.168.0.152:8007` (optional)

## 📖 Related Documentation

- [Main Documentation](../README.md)
- [MCP Servers](../mcp/servers.md)
- [AI Agents](../ai-agents/)
