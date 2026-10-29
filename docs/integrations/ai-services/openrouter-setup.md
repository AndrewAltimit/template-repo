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

The containers ship OpenCode 2.x (pinned in `docker/mcp-opencode.Dockerfile`;
`openrouter-agents` copies the binary from that image). No configuration file
is needed: OpenCode's bundled models.dev catalog already includes the
OpenRouter provider and models such as `openrouter/particle-ai/particle-1`,
and the provider picks up `OPENROUTER_API_KEY` from the environment.

To change defaults, add `~/.config/opencode/opencode.json` (or a project
`opencode.json`) using the 2.x schema, for example:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/particle-ai/particle-1",
  "providers": {
    "openrouter": {
      // Only needed to send OpenRouter traffic through a proxy or gateway
      "settings": { "baseURL": "https://openrouter.ai/api/v1" }
    }
  }
}
```

### Background Service and `--standalone`

OpenCode 2.x runs sessions in a background service that `opencode` and
`opencode run` start on demand. The service keeps the environment it started
with (API key, proxy variables) and keeps running after the command exits.
Automation in this repo therefore passes `--standalone`, which gives each run
a private server that uses the caller's environment and exits with it:

```bash
opencode run --standalone -m openrouter/particle-ai/particle-1 "Your prompt"
```

## Usage

### Local Usage

```bash
# Source environment
source .env

# Run a simple prompt
opencode run "Write a Python data validation function"

# Use a specific model
opencode run -m "openrouter/particle-ai/particle-1" "Your prompt"

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
docker compose run --rm openrouter-agents opencode run "Write a Python data validation function"

# Use a specific model
docker compose run --rm openrouter-agents opencode run -m "openrouter/anthropic/claude-3.5-sonnet" "Your prompt"

# List available models
docker compose run --rm openrouter-agents opencode models

# Interactive mode in container
docker compose run --rm -it openrouter-agents opencode
```

## Available Models

OpenCode automatically detects all available OpenRouter models. Some popular options:

### Coding-Specific Models
- `openrouter/particle-ai/particle-1` - Excellent for code generation
- `openrouter/anthropic/claude-3.5-sonnet` - Strong reasoning and code quality

### Free Models
- `openrouter/meta-llama/llama-3.3-70b-instruct:free`
- `openrouter/google/gemma-2-9b-it:free`

To see all available models:
```bash
docker compose run --rm openrouter-agents opencode models
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
docker compose run --rm openrouter-agents python -m github_agents.cli issue-monitor
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
4. A background service started earlier is not holding an old environment:
   use `--standalone`, or restart it with `opencode service stop` /
   `opencode service start`

### Container Issues

If the container can't find OpenCode:
1. Rebuild: `docker compose build openrouter-agents`
2. Check installation: `docker compose run --rm openrouter-agents which opencode`

## Best Practices

1. **Model Selection**: Use strong coding models like Particle 1 for best results
2. **Cost Management**: Be aware that some models have different pricing
3. **Interactive Mode**: Use for exploratory coding sessions
4. **Non-Interactive Mode**: Use `run` command for automation and scripts
