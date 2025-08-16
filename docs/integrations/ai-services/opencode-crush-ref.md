# OpenCode & Crush Quick Reference

## Setup

```bash
# Required for both
export OPENROUTER_API_KEY="your-key-here"

# Install package
pip3 install -e ./packages/github_ai_agents
```

## OpenCode Commands

### Interactive Mode
```bash
./tools/utilities/run_opencode.sh
# or
opencode interactive
```

### Single Commands
```bash
# Generate code
./tools/utilities/run_opencode.sh -q "Create a REST API"

# With context file
./tools/utilities/run_opencode.sh -q "Refactor this" -c code.py

# With plan mode
./tools/utilities/run_opencode.sh -q "Build microservices" -p

# Direct CLI
opencode run -q "Your prompt"
opencode refactor -f file.py -i "Instructions"
opencode review -f code.py --focus security,performance
```

## Crush Commands

### Interactive Mode
```bash
./tools/utilities/run_crush.sh
# or
crush
```

### Single Commands
```bash
# Quick generation
./tools/utilities/run_crush.sh -q "Binary search"

# Detailed output
./tools/utilities/run_crush.sh -q "REST API" -s detailed

# Explain code
./tools/utilities/run_crush.sh -e complex.py

# Convert code
./tools/utilities/run_crush.sh -c script.py -t javascript

# Direct CLI
crush run -q "Your prompt"
```

## MCP Tools (in Claude)

### OpenCode MCP
```python
# Generate code
mcp__opencode__consult_opencode(
    query="Create user auth system",
    mode="generate"
)

# Clear history
mcp__opencode__clear_opencode_history()

# Check status
mcp__opencode__opencode_status()

# Toggle auto-consult
mcp__opencode__toggle_opencode_auto_consult(enable=True)
```

### Crush MCP
```python
# Quick generate
mcp__crush__consult_crush(
    query="Email validator",
    mode="quick"
)

# Clear history
mcp__crush__clear_crush_history()

# Check status
mcp__crush__crush_status()

# Toggle auto-consult
mcp__crush__toggle_crush_auto_consult(enable=True)
```

## GitHub PR/Issue Triggers

### OpenCode Triggers
```markdown
[Generate][OpenCode] - Generate new code
[Refactor][OpenCode] - Refactor existing code
[Review][OpenCode]   - Review and analyze code
[Explain][OpenCode]  - Explain code functionality
```

### Crush Triggers
```markdown
[Quick][Crush]    - Fast code generation
[Convert][Crush]  - Language conversion
[Explain][Crush]  - Quick explanation
[Generate][Crush] - Standard generation
```

## Docker Commands

```bash
# Start MCP servers
docker-compose up -d mcp-opencode mcp-crush

# Run in container
docker-compose run --rm openrouter-agents opencode run -q "prompt"
docker-compose run --rm openrouter-agents crush run -q "prompt"

# Check logs
docker-compose logs -f openrouter-agents
```

## Testing

```bash
# Test OpenCode
./tools/mcp/opencode/scripts/test_opencode_cli.sh
python tools/mcp/opencode/scripts/test_server.py

# Test Crush
./tools/mcp/crush/scripts/test_crush_cli.sh
python tools/mcp/crush/scripts/test_server.py

# Test all MCP servers
python automation/testing/test_all_servers.py
```

## When to Use Which?

| Use Case | OpenCode | Crush |
|----------|----------|-------|
| Complex implementations | ✅ Best | ⚠️ Limited |
| Quick snippets | ⚠️ Overkill | ✅ Best |
| Code refactoring | ✅ Best | ❌ No |
| Code review | ✅ Best | ❌ No |
| Language conversion | ⚠️ Works | ✅ Best |
| Fast iteration | ⚠️ Slower | ✅ Best |
| Detailed explanations | ✅ Best | ⚠️ Basic |

## Environment Variables

```bash
# OpenCode
OPENCODE_MODEL="qwen/qwen-2.5-coder-32b-instruct"
OPENCODE_TIMEOUT=300
OPENCODE_MAX_CONTEXT=8000
OPENCODE_LOG_GENERATIONS=true

# Crush
CRUSH_TIMEOUT=300
CRUSH_MAX_PROMPT=4000
CRUSH_LOG_GENERATIONS=true
```

## Common Issues

```bash
# API key not found
export OPENROUTER_API_KEY="your-key"

# Agent not found
pip3 install -e ./packages/github_ai_agents --force-reinstall

# Container issues
docker-compose restart openrouter-agents

# Server health check
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
```
