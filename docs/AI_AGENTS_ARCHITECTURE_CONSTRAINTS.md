# AI Agents Architecture Constraints

## Overview

The AI agents system has a fundamental architectural constraint due to authentication requirements:

- **Claude** requires host-specific authentication (machine-bound credentials)
- **OpenCode/Codex/Crush** are containerized for security and portability
- The monitors can only run in one environment at a time

## Current Architecture

### Host Agents (Run on bare metal)
- **Claude** - Requires subscription authentication tied to the host machine
- **Gemini** - Requires Docker socket access for certain operations

### Container Agents (Run in `openrouter-agents` container)
- **OpenCode** - Uses OpenRouter API
- **Codex** - Uses OpenRouter API
- **Crush** - Uses OpenRouter API

## The Constraint

When GitHub Actions workflows trigger the issue or PR monitors:

1. The monitor runs on the **host** to support Claude authentication
2. Container agents (OpenCode/Codex/Crush) are **not available** in this mode
3. Only Claude and Gemini can be used for automated workflows

## Workarounds

### Option 1: Use Host Agents
Instead of `[Approved][OpenCode]`, use:
- `[Approved][Claude]` - Most capable agent
- `[Approved][Gemini]` - Good for code review

### Option 2: Manual Container Execution
Run the monitor manually in the container:

```bash
# For issues
docker-compose --profile agents run --rm openrouter-agents \
  python -m github_ai_agents.cli issue-monitor

# For PRs
docker-compose --profile agents run --rm openrouter-agents \
  python -m github_ai_agents.cli pr-monitor
```

### Option 3: Future Enhancement
A potential solution would be to create a bridge service that:
1. Runs on the host with Claude credentials
2. Proxies requests to containerized agents when needed
3. Handles the authentication handoff

## Why This Design?

1. **Security**: Container agents are isolated from the host system
2. **Authentication**: Claude's auth model requires host access
3. **Simplicity**: Running monitors in one environment avoids complex IPC

## Practical Impact

For automated GitHub workflows:
- ✅ `[Approved][Claude]` - Works
- ✅ `[Approved][Gemini]` - Works
- ❌ `[Approved][OpenCode]` - Requires manual intervention
- ❌ `[Approved][Codex]` - Requires manual intervention
- ❌ `[Approved][Crush]` - Requires manual intervention

The system will post a helpful error message explaining the constraint and suggesting alternatives when container agents are requested in automated workflows.
