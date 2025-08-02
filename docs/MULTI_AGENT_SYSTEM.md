# Multi-Agent System Documentation

## Overview

The multi-agent system allows you to use multiple AI coding assistants in your development workflow. Currently supports:

- **Claude Code** (Anthropic) - Primary development assistant
- **Gemini CLI** (Google) - Code reviews and second opinions
- **OpenCode** (SST) - Open-source alternative *(coming soon)*
- **Codex CLI** (OpenAI) - Terminal-based assistant *(coming soon)*
- **Crush** (Charm) - Multi-provider terminal assistant *(coming soon)*

## Architecture

### Core Components

1. **Agent Interface** (`scripts/agents/core/agent_interface.py`)
   - Abstract base class all agents must implement
   - Defines standard methods: `generate_code()`, `review_code()`, etc.

2. **CLI Agent Wrapper** (`scripts/agents/core/cli_agent_wrapper.py`)
   - Base class for terminal-based AI agents
   - Handles subprocess execution, timeout management, output parsing

3. **Configuration Loader** (`scripts/agents/core/config_loader.py`)
   - Manages agent selection and priorities
   - Loads from `.agents.yaml` or defaults

### Agent Implementations

Each agent extends either `AIAgent` directly (for API-based agents) or `CLIAgentWrapper` (for CLI tools):

```python
from scripts.agents.core.cli_agent_wrapper import CLIAgentWrapper

class OpenCodeAgent(CLIAgentWrapper):
    def __init__(self):
        super().__init__('opencode', {
            'executable': 'opencode',
            'timeout': 300
        })

    def _build_command(self, prompt, context):
        # Build CLI command

    def _parse_output(self, output, error):
        # Parse terminal output
```

## Configuration

Create `.agents.yaml` in your project root:

```yaml
# Enable/disable agents
enabled_agents:
  - claude      # Always available
  - gemini      # Optional
  - opencode    # Optional (when implemented)
  - codex       # Optional (when implemented)
  - crush       # Optional (when implemented)

# Task-specific agent priorities
agent_priorities:
  issue_creation: [claude, opencode]
  pr_reviews: [gemini, codex]
  code_fixes: [claude, crush]

# Model overrides
model_overrides:
  opencode:
    model: deepseek/deepseek-coder-v2-instruct
    temperature: 0.3

# OpenRouter configuration
openrouter:
  api_key: ${OPENROUTER_API_KEY}
  default_model: qwen/qwen-2.5-coder-32b-instruct
```

## Usage in Workflows

### Issue Monitor
The issue monitor recognizes agent triggers in issue descriptions:

```markdown
[Claude] Please implement user authentication
[OpenCode] Add login functionality with JWT tokens
[Gemini] Review the security implications
```

### PR Review Monitor
Agents can be triggered in PR comments:

```markdown
[Gemini] Please review this code for performance
[Codex] Check for potential bugs
```

## Adding New Agents

1. **Create Implementation**:
   ```python
   # scripts/agents/implementations/new_agent.py
   from ..core.cli_agent_wrapper import CLIAgentWrapper

   class NewAgent(CLIAgentWrapper):
       # Implementation
   ```

2. **Register Agent**:
   - Add to `implementations/__init__.py`
   - Update agent registry in monitor scripts

3. **Configure**:
   - Add to `.agents.yaml`
   - Set up authentication (API keys, etc.)

4. **Test**:
   ```bash
   python scripts/agents/test_agent_system.py
   ```

## CLI Tool Integration

Since OpenCode, Codex CLI, and Crush are terminal-based tools:

1. **Installation Required**:
   ```bash
   # OpenCode
   curl -fsSL https://opencode.ai/install | bash

   # Codex CLI
   npm i -g @openai/codex

   # Crush
   go install github.com/charmbracelet/crush@latest
   ```

2. **Authentication**:
   - Each tool has its own auth mechanism
   - API keys via environment variables
   - Config files in home directory

3. **Non-Interactive Mode**:
   - Agents use flags like `--non-interactive`
   - Input via temporary files
   - Output parsing strips terminal formatting

## Security Considerations

1. **API Key Management**:
   - Store in environment variables
   - Never commit to repository
   - Use GitHub secrets for CI/CD

2. **Agent Permissions**:
   - Follow existing allow-list model
   - Per-agent permission controls
   - Audit trail for all operations

3. **Subprocess Safety**:
   - Command validation
   - Timeout enforcement
   - Resource limits

## Troubleshooting

### Agent Not Available
```bash
# Check if CLI tool is installed
which opencode

# Test agent system
python scripts/agents/test_agent_system.py
```

### Authentication Issues
- Verify API keys in environment
- Check tool-specific auth (e.g., `claude login`)
- Review config file permissions

### Output Parsing Errors
- Enable debug logging
- Check for CLI tool updates
- Verify non-interactive mode support

## Future Enhancements

1. **Agent Collaboration**: Multiple agents working together
2. **Smart Routing**: Automatic agent selection based on task
3. **Performance Metrics**: Track success rates and costs
4. **Custom Agents**: Plugin system for user-defined agents
