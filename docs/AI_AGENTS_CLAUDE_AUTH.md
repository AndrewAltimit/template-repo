# Claude Authentication in AI Agents

## Current Limitation

The AI agents that use Claude Code for implementation currently face an authentication limitation when running in containerized environments (like GitHub Actions).

### The Problem

Claude CLI subscription authentication (obtained via `claude login`) is tied to the specific machine and user session where the login was performed. The authentication tokens stored in `~/.claude.json` are not portable to other environments, particularly containers.

When you try to use these credentials in a container, you'll see:
```
Invalid API key · Please run /login
```

### Why This Happens

1. **Session-based Auth**: Claude subscription authentication creates session tokens that are machine-specific
2. **Container Isolation**: Containers run in isolated environments with different system characteristics
3. **Security Design**: This is likely by design to prevent credential sharing across different environments

### Current Status

As of now, the AI agents that rely on Claude Code (issue monitor, PR review monitor) will fail in containerized GitHub Actions with authentication errors.

## Potential Solutions

### 1. Use API Keys Instead (Recommended for CI/CD)

If you have access to Anthropic API keys, you can:
- Set `ANTHROPIC_API_KEY` environment variable
- This works across all environments including containers
- More suitable for automated/CI environments

### 2. Run on Self-Hosted Runners

If you're using self-hosted GitHub Actions runners on the same machine where you use Claude:
- The agents could potentially run outside containers
- Direct access to host's `~/.claude.json`
- Requires modifying workflows to not use Docker

### 3. Wait for CI/CD Authentication Support

Claude CLI mentions a `setup-token` command that might support long-lived tokens for CI/CD, but this feature may not be fully available yet.

## Workaround for Now

Until a proper solution is available, you can:

1. **Manual Trigger**: Run the agents locally on your development machine
2. **Self-Hosted Runner**: Configure workflows to run directly on host (not in containers)
3. **API Key**: Switch to using Anthropic API keys if available

## Future Improvements

We should monitor Claude CLI updates for:
- Long-lived token support for CI/CD
- Portable authentication methods
- Official guidance for containerized environments
