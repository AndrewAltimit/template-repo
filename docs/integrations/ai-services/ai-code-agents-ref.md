# AI Code Agents Quick Reference

> Gemini and Codex integrations are [legacy, not allowed](../../agents/agent-matrix.md#legacy-agents-gemini-and-codex-not-allowed) and are omitted here.

## Agent Overview

| Agent | Provider | Use Case | Status |
|-------|----------|----------|--------|
| **OpenCode** | OpenRouter | Code generation and editing | Active |
| **Crush** | OpenRouter | Code generation and editing | Active |

OpenCode and Crush support both **review** (read-only analysis) and **edit** (code generation/modification) tasks.

## Setup

```bash
# OpenRouter (OpenCode, Crush)
export OPENROUTER_API_KEY="your-key"
```

## MCP Tools

All agents follow the same pattern:

```python
# Consult for code tasks
mcp__<agent>__consult_<agent>(query="...", context="...")

# Clear conversation history
mcp__<agent>__clear_<agent>_history()

# Check status
mcp__<agent>__<agent>_status()
```

### Examples

```python
# Review code (read-only)
mcp__opencode__consult_opencode(query="Review this function for bugs", context="def foo(): ...")

# Generate/edit code
mcp__crush__consult_crush(query="Write a function to validate emails")
```

## CLI Usage

```bash
# Interactive mode
opencode    # or: crush

# Single query
opencode run -q "Write a binary search function"
crush run -q "Explain this regex pattern"
```

## Docker

```bash
# Start servers
docker compose up -d mcp-opencode mcp-crush

# Run via container
docker compose run --rm openrouter-agents opencode run -q "your prompt"
```

## Health Checks

```bash
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key not found | `export OPENROUTER_API_KEY="your-key"` |
| Agent not found | Rebuild the CLI: `cargo build --release --manifest-path tools/rust/github-agents-cli/Cargo.toml` |
| Server not responding | `docker compose restart mcp-opencode mcp-crush` |
