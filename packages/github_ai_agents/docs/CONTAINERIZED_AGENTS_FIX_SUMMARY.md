# Containerized Agents Fix Summary

## Problem
The GitHub issue monitoring pipeline was failing when trying to use OpenCode agent, showing the error "only available in the containerized environment" despite the pipeline supposedly being able to handle containerized agents automatically.

## Root Causes
1. The base monitor was skipping containerized agents when running on the host
2. Docker build had a UID conflict in openrouter-agents.Dockerfile
3. Git operations were using invalid `gh checkout` command
4. OpenCode CLI requires provider configuration that wasn't implemented
5. Mods CLI expects `OPENAI_API_KEY` even when using OpenRouter

## Changes Made

### 1. Fixed Docker Build Issue
- **File**: `docker/openrouter-agents.Dockerfile`
- **Change**: Used existing `node` user instead of creating `appuser` to avoid UID conflicts

### 2. Enabled Automatic Container Execution
- **File**: `packages/github_ai_agents/src/github_ai_agents/monitors/base.py`
- **Change**: Removed logic that skipped containerized agents on host
- **Result**: Containerized agents now automatically spin up Docker containers when invoked

### 3. Fixed Git Operations
- **File**: `packages/github_ai_agents/src/github_ai_agents/utils/github.py`
- **Change**: Added proper git command utilities to replace invalid `gh checkout` operations

### 4. Updated Agent Implementations
- **Crush Agent**: Now properly uses `mods` CLI with OpenRouter API
- **Codex Agent**: Updated to use `mods` instead of the npm codex package
- **OpenCode Agent**: Implemented proper command syntax but disabled due to provider configuration requirement

### 5. Environment Variable Handling
- **File**: `packages/github_ai_agents/src/github_ai_agents/agents/containerized.py`
- **Change**: Ensured critical environment variables (OPENROUTER_API_KEY, GITHUB_TOKEN, etc.) are passed through to containers

### 6. Mods Configuration
- **File**: `packages/github_ai_agents/configs/modsrc`
- **Change**: Created proper mods configuration for OpenRouter integration

## Current Status

### Working Containerized Agents
1. **Crush** - Uses mods CLI with OpenRouter
2. **Codex** - Uses mods CLI with OpenRouter (GPT-4 model)

### Non-Working Agents
1. **OpenCode** - Requires provider configuration, currently disabled

### Configuration Requirements
- Set `OPENROUTER_API_KEY` environment variable
- Mods expects `OPENAI_API_KEY` to be set (we set it to the OpenRouter key value)
- Enable agents in `.agents.yaml`

## Testing
```bash
# Test Crush agent
docker-compose run --rm -T -e OPENAI_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents mods -a openrouter "Write a hello world function"

# Test issue monitoring with containerized agents
python3 -m github_ai_agents.cli issue-monitor
```

## Future Work
1. Implement OpenCode provider configuration
2. Consider using native Codex npm package
3. Add more robust error handling and logging
4. Improve documentation for containerized agent setup
