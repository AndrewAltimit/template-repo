# Containerized AI Agents

This document describes the current state of containerized AI agents in the GitHub AI Agents system.

## Overview

The containerized agents run in the `openrouter-agents` Docker container and use the OpenRouter API for LLM access.

## Current Status

### Working Agents

1. **Crush Agent** (`[Approved][Crush]`)
   - Uses `mods` CLI tool
   - Configured to use OpenRouter API with `-a openrouter` flag
   - Requires `OPENAI_API_KEY` environment variable (set to OpenRouter key)
   - Model: Default from mods config (qwen/qwen-2.5-coder-32b-instruct)

2. **Codex Agent** (`[Approved][Codex]`)
   - Uses `mods` CLI tool
   - Configured to use OpenRouter API with `-a openrouter` flag
   - Requires `OPENAI_API_KEY` environment variable (set to OpenRouter key)
   - Model: openai/gpt-4o via OpenRouter

### Non-Working Agents

1. **OpenCode Agent** (`[Approved][OpenCode]`)
   - Status: **Disabled**
   - Issue: Requires provider configuration, fails with "no providers found" error
   - The OpenCode CLI is installed but needs additional setup to work with OpenRouter
   - TODO: Implement provider configuration for OpenCode

## Environment Variables

The following environment variables are required:

- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `GITHUB_REPOSITORY`: The GitHub repository (e.g., "owner/repo")
- `GITHUB_TOKEN`: GitHub token for API access

## Docker Container

The `openrouter-agents` container includes:

- Node.js 20
- Python 3.11
- Go 1.24.5
- GitHub CLI (gh)
- OpenCode CLI (v0.3.112) - not working yet
- Mods CLI (v1.8.1) - working
- Codex npm package (@openai/codex) - not used

## Configuration Files

### Mods Configuration

Located at `/home/node/.config/mods/mods.yml` in the container:

```yaml
default-model: qwen/qwen-2.5-coder-32b-instruct
default-api: openrouter

apis:
  openrouter:
    base-url: https://openrouter.ai/api/v1
    api-key-env: OPENROUTER_API_KEY
    # ... model configurations
```

## Usage

To test the agents manually:

```bash
# Crush agent (working)
docker-compose run --rm -T -e OPENAI_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents mods -a openrouter "Write a hello world function"

# Codex agent (working)
docker-compose run --rm -T -e OPENAI_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents mods -a openrouter -m openai/gpt-4o "Write a hello world function"

# OpenCode agent (not working)
# Requires provider configuration
```

## Implementation Notes

1. **Mods CLI**: Expects `OPENAI_API_KEY` even when using OpenRouter. The agents set this environment variable to the OpenRouter key value.

2. **Docker Preference**: All containerized agents prefer Docker execution over local installation for consistency.

3. **Error Handling**: The agents include proper error handling and logging for debugging.

## Future Work

1. Fix OpenCode provider configuration
2. Consider using the native Codex npm package instead of mods
3. Add more model options and configuration flexibility
