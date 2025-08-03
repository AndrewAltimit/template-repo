# Containerized AI Agents

This document describes the current state of containerized AI agents in the GitHub AI Agents system.

## Overview

The containerized agents run in the `openrouter-agents` Docker container and use the OpenRouter API for LLM access.

## Current Status

### Working Agents

1. **OpenCode Agent** (`[Approved][OpenCode]`)
   - Uses `opencode` CLI tool
   - Automatically detects and uses OpenRouter API
   - Model: Can specify any OpenRouter model with `-m` flag
   - Default: Uses Gemini or configured default model

2. **Crush Agent** (`[Approved][Crush]`)
   - Uses `mods` CLI tool
   - Configured to use OpenRouter API with `-a openrouter` flag
   - Requires `OPENAI_API_KEY` environment variable (set to OpenRouter key)
   - Model: Default from mods config (qwen/qwen-2.5-coder-32b-instruct)

### Removed Agents

1. **Codex Agent** - Removed as it doesn't support OpenRouter

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
- OpenCode CLI (v0.3.112) - working
- Mods CLI (v1.8.1) - working

## Configuration Files

### OpenCode Configuration

Located at `/home/node/.config/opencode/.opencode.json` in the container:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "${OPENROUTER_API_KEY}",
      "baseURL": "https://openrouter.ai/api/v1",
      "models": {
        "qwen-coder": {
          "id": "qwen/qwen-2.5-coder-32b-instruct",
          "name": "Qwen 2.5 Coder 32B"
        },
        "claude-sonnet": {
          "id": "anthropic/claude-3.5-sonnet",
          "name": "Claude 3.5 Sonnet"
        },
        "gpt4o": {
          "id": "openai/gpt-4o",
          "name": "GPT-4 Optimized"
        }
      }
    }
  },
  "defaultModel": "openrouter/qwen-coder"
}
```

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
# OpenCode agent (working)
docker-compose run --rm openrouter-agents opencode run "Write a hello world function"

# OpenCode with specific model
docker-compose run --rm openrouter-agents opencode run -m "openrouter/anthropic/claude-3.5-sonnet" "Write a hello world function"

# Crush agent (working)
docker-compose run --rm -T -e OPENAI_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents mods -a openrouter "Write a hello world function"
```

## Implementation Notes

1. **OpenCode**: Automatically detects `OPENROUTER_API_KEY` and provides seamless integration with OpenRouter.

2. **Mods CLI**: Expects `OPENAI_API_KEY` even when using OpenRouter. The agents set this environment variable to the OpenRouter key value.

3. **Docker Preference**: All containerized agents prefer Docker execution over local installation for consistency.

4. **Error Handling**: The agents include proper error handling and logging for debugging.

## Future Work

1. Add more model options and configuration flexibility
2. Consider adding more OpenRouter-compatible agents
3. Improve documentation and examples
