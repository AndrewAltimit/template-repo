# AI Code Agents Quick Reference

## Agent Overview

| Agent | Provider | Use Case |
|-------|----------|----------|
| **OpenCode** | OpenRouter | Code generation and editing |
| **Crush** | OpenRouter | Code generation and editing |
| **Codex** | OpenAI | Code generation and editing |
| **Gemini** | Google | Code review (limited tool use) |

All agents support both **review** (read-only analysis) and **edit** (code generation/modification) tasks. Choose based on your API access.

## Setup

```bash
# OpenRouter (OpenCode, Crush)
export OPENROUTER_API_KEY="your-key"

# OpenAI (Codex) - requires ChatGPT Plus
npm install -g @openai/codex && codex auth

# Google (Gemini) - free tier available
export GOOGLE_API_KEY="your-key"
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
mcp__gemini__consult_gemini(query="Analyze this code for security issues", context="...")

# Generate/edit code
mcp__crush__consult_crush(query="Write a function to validate emails")
mcp__codex__consult_codex(query="Refactor this class to use async/await", context="...")
```

## CLI Usage

```bash
# Interactive mode
opencode    # or: crush, codex

# Single query
opencode run -q "Write a binary search function"
crush run -q "Explain this regex pattern"
codex "Add error handling to this function"
```

## Docker

```bash
# Start servers
docker-compose up -d mcp-opencode mcp-crush mcp-codex

# Run via container
docker-compose run --rm openrouter-agents opencode run -q "your prompt"
```

## Health Checks

```bash
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
curl http://localhost:8021/health  # Codex
curl http://localhost:8006/health  # Gemini
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key not found | `export OPENROUTER_API_KEY="your-key"` |
| Agent not found | `pip3 install -e ./packages/github_agents --force-reinstall` |
| Server not responding | `docker-compose restart mcp-opencode mcp-crush` |
| Codex auth issues | Run `codex auth` to re-authenticate |
