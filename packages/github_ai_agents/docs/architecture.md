# GitHub AI Agents Architecture

## Overview

The GitHub AI Agents package is designed with a modular, extensible architecture that supports multiple AI agents for GitHub automation.

## Core Components

### 1. Agents Module (`github_ai_agents.agents`)

The agents module contains implementations of various AI agents:

- **Base Classes**:
  - `BaseAgent`: Abstract base class defining the agent interface
  - `CLIAgent`: Base class for CLI-based agents

- **Agent Implementations**:
  - `ClaudeAgent`: Anthropic's Claude AI
  - `OpenCodeAgent`: Open-source coding AI
  - `GeminiAgent`: Google's Gemini AI
  - `CrushAgent`: Charm Bracelet Crush

Each agent implements:
- `is_available()`: Check if agent is available
- `generate_code()`: Generate code/responses
- `get_trigger_keyword()`: Get keyword for triggering
- `get_capabilities()`: List agent capabilities
- `get_priority()`: Agent selection priority

### 2. Monitors Module (`github_ai_agents.monitors`)

Monitors watch GitHub events and trigger agents:

- **IssueMonitor**:
  - Monitors GitHub issues
  - Detects trigger keywords
  - Creates PRs using appropriate agents

- **PRMonitor**:
  - Monitors pull requests
  - Handles review feedback
  - Implements fixes automatically

### 3. Security Module (`github_ai_agents.security`)

Security components ensure safe operation:

- **SecurityManager**:
  - User authorization (allowlist)
  - Rate limiting
  - Repository validation
  - Trigger validation

### 4. Utils Module (`github_ai_agents.utils`)

Utility functions for common operations:

- **GitHub utilities**:
  - `get_github_token()`: Token management
  - `run_gh_command()`: GitHub CLI wrapper

## Data Flow

```
GitHub Event (Issue/PR)
    ↓
Monitor detects trigger
    ↓
Security validation
    ↓
Agent selection
    ↓
Code generation
    ↓
GitHub action (comment/PR)
```

## Agent Selection

Agents are selected based on:

1. **Trigger keyword**: e.g., `[Approved][OpenCode]`
2. **Availability**: Is the agent installed/accessible?
3. **Priority**: Higher priority agents preferred
4. **Capabilities**: Does agent support required features?

## Extensibility

### Adding New Agents

1. Create new class inheriting from `BaseAgent` or `CLIAgent`
2. Implement required methods
3. Add to agent initialization in monitors

Example:
```python
from github_ai_agents.agents import CLIAgent

class NewAgent(CLIAgent):
    def __init__(self):
        super().__init__("newagent", "newagent-cli")

    def get_trigger_keyword(self):
        return "NewAgent"

    async def generate_code(self, prompt, context):
        # Implementation
        pass
```

### Adding New Monitors

1. Create new class in monitors module
2. Implement event detection logic
3. Use SecurityManager for validation
4. Use agents for implementation

## Configuration

Configuration is managed through:

1. **Environment variables**:
   - `GITHUB_TOKEN`: GitHub authentication
   - `GITHUB_REPOSITORY`: Target repository
   - `OPENROUTER_API_KEY`: OpenRouter agents
   - `ANTHROPIC_API_KEY`: Claude API

2. **Config files**:
   - Security configuration
   - Agent-specific settings

## Deployment

The package can be deployed in multiple ways:

1. **Direct installation**: `pip install -e .`
2. **Docker containers**: For isolated agents
3. **GitHub Actions**: For automation
4. **CLI usage**: Direct command-line use
