# OpenCode with OpenRouter Setup Guide

This guide explains how to use OpenCode with OpenRouter, both locally and in containers.

## Overview

OpenCode is a powerful AI coding assistant that seamlessly integrates with OpenRouter. It automatically detects the `OPENROUTER_API_KEY` environment variable and provides access to a wide range of AI models.

## Configuration

### Environment Setup

1. **Set OpenRouter API Key**:
   ```bash
   export OPENROUTER_API_KEY="your-api-key-here"
   # Or source from .env file
   source .env
   ```

### Container Configuration

The OpenCode configuration is pre-configured in the container at `/home/node/.config/opencode/.opencode.json`:

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

## Usage

### Local Usage

```bash
# Source environment
source .env

# Run a simple prompt
opencode run "Write a Python data validation function"

# Use a specific model
opencode run -m "openrouter/qwen/qwen-2.5-coder-32b-instruct" "Your prompt"

# Start interactive mode
opencode

# List available models
opencode models
```

### Container Usage

```bash
# Source environment
source .env

# Run in container
docker-compose run --rm openrouter-agents opencode run "Write a Python data validation function"

# Use a specific model
docker-compose run --rm openrouter-agents opencode run -m "openrouter/anthropic/claude-3.5-sonnet" "Your prompt"

# List available models
docker-compose run --rm openrouter-agents opencode models

# Interactive mode in container
docker-compose run --rm -it openrouter-agents opencode
```

## Available Models

OpenCode automatically detects all available OpenRouter models. Some popular options:

### Coding-Specific Models
- `openrouter/qwen/qwen-2.5-coder-32b-instruct` - Excellent for code generation
- `openrouter/anthropic/claude-3.5-sonnet` - Strong reasoning and code quality
- `openrouter/openai/gpt-4o` - Versatile and capable

### Free Models
- `openrouter/google/gemini-2.0-flash-exp:free`
- `openrouter/meta-llama/llama-3.3-70b-instruct:free`
- `openrouter/google/gemma-2-9b-it:free`

To see all available models:
```bash
docker-compose run --rm openrouter-agents opencode models
```

## Key Features

1. **Automatic OpenRouter Detection**: No additional configuration needed beyond setting `OPENROUTER_API_KEY`
2. **Model Flexibility**: Access to 100+ models through OpenRouter
3. **Container Ready**: Works seamlessly in Docker containers
4. **Interactive & Non-Interactive**: Supports both TUI and command-line usage

## Integration with GitHub AI Agents

OpenCode is part of the containerized agents that can be used for:
- Code generation from issues
- PR implementation
- Code reviews and fixes

Example usage in agent context:
```bash
docker-compose run --rm openrouter-agents python -m github_ai_agents.cli issue-monitor
```

## Troubleshooting

### "Error: Failed to change directory"

This happens when you forget the `run` command:
```bash
# Wrong
opencode "prompt"

# Correct
opencode run "prompt"
```

### Authentication Errors

Ensure:
1. `OPENROUTER_API_KEY` is set correctly
2. The API key has credits available
3. You're using valid model names

### Container Issues

If the container can't find OpenCode:
1. Rebuild: `docker-compose build openrouter-agents`
2. Check installation: `docker-compose run --rm openrouter-agents which opencode`

## Best Practices

1. **Model Selection**: Use coding-specific models like Qwen Coder for best results
2. **Cost Management**: Be aware that some models have different pricing
3. **Interactive Mode**: Use for exploratory coding sessions
4. **Non-Interactive Mode**: Use `run` command for automation and scripts
