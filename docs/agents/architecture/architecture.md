# GitHub AI Agents Architecture

## Overview

The GitHub AI Agents system is implemented in Rust for performance and reliability. The CLI tool is located at `tools/rust/github-agents-cli/` and supports multiple AI agents for GitHub automation.

## Core Components

### 1. Agents Module

The agents module contains implementations of various AI agents:

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

### 2. Monitors

Monitors watch GitHub events and trigger agents:

- **IssueMonitor**:
  - Monitors GitHub issues
  - Detects trigger keywords
  - Creates PRs using appropriate agents

- **PRMonitor**:
  - Monitors pull requests
  - Handles review feedback
  - Implements fixes automatically

### 3. Security

Security components ensure safe operation:

- **SecurityManager**:
  - User authorization (allowlist)
  - Rate limiting
  - Repository validation
  - Trigger validation

### 4. Utils

Utility functions for common operations:

- **GitHub utilities**:
  - Token management
  - GitHub CLI wrapper

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

1. Create a new agent implementation in `tools/rust/github-agents-cli/src/agents/`
2. Implement required traits
3. Add to agent initialization in monitors

### Adding New Monitors

1. Create new monitor in `tools/rust/github-agents-cli/src/monitors/`
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
   - `.agents.yaml`: Agent configuration
   - Security configuration

## Deployment

The CLI can be deployed in multiple ways:

1. **Build from source**: `cd tools/rust/github-agents-cli && cargo build --release`
2. **GitHub Actions**: Pre-built binaries available in releases
3. **CLI usage**: `./github-agents issue-monitor` or `./github-agents pr-monitor`
