# Multi-Agent Implementation Guide

This document describes the complete implementation of the multi-agent system, featuring five AI agents: Claude, Gemini, OpenCode, Codex, and Crush.

## Overview

The multi-agent system allows you to use different AI coding assistants for various tasks. Each agent has its own strengths and can be selected based on the task at hand.

**Implementation Status**: ✅ Fully Implemented
- All agents have complete implementations with proper error handling
- Hybrid execution model: Host agents (Claude/Gemini) and containerized agents (OpenCode/Codex/Crush)
- Automatic detection and switching between local and Docker execution for containerized agents
- Full integration with GitHub Actions workflows

### Agent Types

1. **Host-Only Agents** (require specific authentication):
   - **Claude** (Anthropic) - Requires subscription authentication
   - **Gemini** (Google) - Requires Docker socket access

2. **Containerized Agents** (API key based):
   - **OpenCode** (SST) - Terminal-based coding agent
   - **Codex** (OpenAI) - Rust-based CLI with multimodal support
   - **Crush/mods** (Charm Bracelet) - Flexible multi-provider tool

## Quick Start

### 1. Set Up Environment

```bash
# Copy example configuration
cp .agents.yaml.example .agents.yaml

# Add OpenRouter API key to .env
echo "OPENROUTER_API_KEY=your-api-key" >> .env
```

### 2. Build Container

```bash
docker-compose build openrouter-agents
```

### 3. Verify Setup

```bash
python scripts/agents/verify_containerized_setup.py
```

### 4. Test Agents

```bash
# Test mods/Crush directly
./scripts/agents/run_containerized_agents.sh crush "Write a hello world function"

# Test all agents
./scripts/agents/run_containerized_agents.sh test

# Open shell in container
./scripts/agents/run_containerized_agents.sh shell
```

## Configuration

### .agents.yaml

```yaml
enabled_agents:
  - claude      # Host-only
  - gemini      # Host-only
  - opencode    # Containerized
  - codex       # Containerized
  - crush       # Containerized

openrouter:
  api_key: ${OPENROUTER_API_KEY}
  default_model: qwen/qwen-2.5-coder-32b-instruct

agent_priorities:
  issue_creation: [claude, opencode]
  pr_reviews: [gemini, codex]
  code_fixes: [claude, crush]
```

## Usage

### Direct Agent Usage

```bash
# Use specific agent
./scripts/agents/run_containerized_agents.sh opencode "Implement a REST API"
./scripts/agents/run_containerized_agents.sh codex "Review this code"
./scripts/agents/run_containerized_agents.sh crush "Explain Docker networking"

# Use mods directly with custom model
docker-compose run --rm openrouter-agents mods \
  "Your prompt" \
  --model "openrouter/anthropic/claude-3-5-sonnet" \
  --api https://openrouter.ai/api/v1
```

### GitHub Integration

The agents integrate with GitHub issues and PRs through trigger keywords:

- `[Approved][Claude]` - Use Claude for implementation
- `[Approved][Gemini]` - Use Gemini for implementation
- `[Approved][OpenCode]` - Use OpenCode for implementation
- `[Approved][Codex]` - Use Codex for implementation
- `[Approved][Crush]` - Use Crush for implementation

### Monitor Usage

```bash
# Run issue monitor with multi-agent support
docker-compose run --rm openrouter-agents \
  python scripts/agents/issue_monitor_multi_agent.py

# Run PR review monitor
docker-compose run --rm openrouter-agents \
  python scripts/agents/pr_review_monitor_multi_agent.py
```

## Agent Capabilities

### OpenCode
- **Strengths**: Terminal-first design, session management, LSP integration
- **Best for**: Code generation, refactoring, multi-file edits
- **Model**: Configurable via OpenRouter

### Codex
- **Strengths**: Multimodal support, sandboxed execution, approval workflows
- **Best for**: Code review, debugging, interactive development
- **Model**: GPT-4.1 or OpenRouter models

### Crush/mods
- **Strengths**: Multi-provider support, MCP integration, flexible configuration
- **Best for**: Quick tasks, explanations, code snippets
- **Model**: Any OpenRouter model

## Architecture

### Container Structure

```
openrouter-agents/
├── Python 3.11 base
├── Node.js 20 LTS (for npm packages)
├── Go 1.21 (for Go-based tools)
├── CLI Tools:
│   ├── opencode (binary from GitHub)
│   ├── codex (npm package)
│   └── mods/crush (Go binary)
└── Python agent implementations
```

### Agent Interface

All agents implement a common interface:

```python
class AgentInterface:
    async def generate_code(prompt: str, context: dict) -> str
    def is_available() -> bool
    def get_capabilities() -> List[str]
    def get_priority() -> int
    def get_trigger_keyword() -> str
```

## Troubleshooting

### Common Issues

1. **API Key Not Set**
   ```bash
   export OPENROUTER_API_KEY='your-key'
   # Or add to .env file
   ```

2. **Container Not Built**
   ```bash
   docker-compose build openrouter-agents
   ```

3. **Agent Not Available**
   - Check container logs: `docker-compose logs openrouter-agents`
   - Verify CLI installation in container
   - Check API key configuration

### Debug Mode

```bash
# Enable debug logging
export DEBUG=1

# Run with verbose output
docker-compose run --rm openrouter-agents \
  python -m scripts.agents.test_containerized_agents
```

## Cost Optimization

The system uses OpenRouter for cost-effective model access:

- **Qwen 2.5 Coder 32B**: ~$0.18/M tokens (default)
- **Mistral 7B**: ~$0.10/M tokens (fast option)
- **Claude 3.5 Sonnet**: ~$3.00/M tokens (quality option)

Configure models per agent in `.agents.yaml` to optimize cost/performance.

## Security

- API keys stored in environment variables
- Containerized execution for isolation
- Rate limiting via OpenRouter
- Audit logging for all agent actions
- Allow-list based user authorization

## Future Enhancements

1. **Additional Agents**:
   - Cursor API integration
   - Continue.dev support
   - Aider integration

2. **Features**:
   - Agent collaboration (multi-agent tasks)
   - Performance benchmarking
   - Cost tracking dashboard
   - Custom prompt templates

## References

- [OpenCode Documentation](https://opencode.ai/docs/)
- [Codex CLI Guide](https://github.com/openai/codex)
- [mods/Crush Documentation](https://github.com/charmbracelet/mods)
- [OpenRouter API](https://openrouter.ai/docs)
