# AI Services Integration

Integration documentation for AI platforms and code generation services.

## Available Integrations

### [Gemini Setup](./gemini-setup.md)
Google's Gemini AI for automated code reviews
- CLI installation and configuration
- API key setup
- GitHub integration
- Docker requirements

### [AI Code Agents](./ai-code-agents.md)
Comprehensive documentation for all AI code assistants (OpenCode, Crush, Codex, Gemini)
- MCP server configuration
- CLI usage and commands
- Provider comparison
- Git workflow integration

### [AI Code Agents Quick Reference](./ai-code-agents-ref.md)
Quick command reference for all AI code agents
- Common commands
- MCP tool usage
- Setup examples

### [OpenRouter Setup](./openrouter-setup.md)
Configuration for OpenRouter API access
- API key management
- Model selection
- Rate limiting
- Cost optimization

## Quick Setup

1. **Get API Keys**
   ```bash
   export OPENROUTER_API_KEY="your-key"
   export GEMINI_API_KEY="your-key"
   ```

2. **Test Connections**
   ```bash
   # Test OpenCode
   ./tools/cli/agents/run_opencode.sh -q "Test connection"

   # Test Crush
   ./tools/cli/agents/run_crush.sh -q "Hello world"

   # Test Gemini
   gemini-cli review --test
   ```

3. **Configure MCP Servers**
   - OpenCode and Crush are configured in `.mcp.json`
   - Auto-started by Claude Code via STDIO

## Required Environment Variables

| Service | Variable | Purpose |
|---------|----------|---------|
| OpenRouter | `OPENROUTER_API_KEY` | API authentication |
| Gemini | `GEMINI_API_KEY` | API authentication |
| Gemini | `GITHUB_TOKEN` | GitHub access |

## Related Documentation

- [Integrations Overview](../README.md)
- [MCP Servers](../../mcp/servers.md)
- [AI Agents](../../agents/)
