# Multi-Agent System Migration Status

This document tracks the successful migration from the scripts-based agent system to the new `github_ai_agents` package.

## Migration Complete

The migration from `scripts/agents/` to the `github_ai_agents` package has been completed successfully.

### ✅ Current Implementation

- **Issue Monitor** - Using `python3 -m github_ai_agents.cli issue-monitor`
- **PR Review Monitor** - Using `python3 -m github_ai_agents.cli pr-monitor`
- **Containerized Agents** - OpenCode, Codex, and Crush run in the `openrouter-agents` container
- **Host Agents** - Claude and Gemini run on the host due to authentication requirements

### 📚 Documentation

All agent documentation is now consolidated in:
- **Package Documentation**: `packages/github_ai_agents/docs/`
- **Security Model**: `packages/github_ai_agents/docs/security.md`
- **Architecture**: `packages/github_ai_agents/docs/architecture.md`
- **Containerization Strategy**: `docs/AGENT_CONTAINERIZATION_STRATEGY.md`

## Benefits of the New System

1. **Proper Python Package**: Installable via pip with proper dependencies
2. **Containerization**: OpenRouter agents run in containers for better isolation
3. **Unified Configuration**: Single `.agents.yaml` configuration file
4. **Better Testing**: Comprehensive test suite in the package
5. **Clear Architecture**: Modular design with separated concerns

## Usage

Install the package:
```bash
pip3 install -e ./packages/github_ai_agents
```

Run agents:
```bash
# Host agents (Claude/Gemini)
python3 -m github_ai_agents.cli issue-monitor
python3 -m github_ai_agents.cli pr-monitor

# Containerized agents (OpenRouter)
docker-compose run --rm openrouter-agents python -m github_ai_agents.cli issue-monitor
```
