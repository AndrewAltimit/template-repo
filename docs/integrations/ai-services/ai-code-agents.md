# AI Code Agents Integration Guide

This document covers the AI code assistance agents available in this project.

> Gemini and Codex integrations remain in the repository but are [legacy, not allowed](../../agents/agent-matrix.md#legacy-agents-gemini-and-codex-not-allowed); they are omitted from this guide. Their MCP servers are documented only in their own READMEs.

## Overview

The project integrates two active AI code agents, both backed by OpenRouter:

| Agent | Provider | API | Primary Use | Status |
|-------|----------|-----|-------------|--------|
| **OpenCode** | OpenRouter | OpenRouter API | General code assistance | Active |
| **Crush** | OpenRouter | OpenRouter API | General code assistance | Active |

OpenCode and Crush provide similar functionality through a unified MCP interface.

## Architecture

### Component Overview

```
+-------------------------------------------------------------+
|                        User Interfaces                       |
+---------------+----------------+---------------+-------------+
|   Claude      |   Direct CLI   |  GitHub PRs   |  GitHub     |
|   (MCP)       |   (Scripts)    |  (Triggers)   |  Issues     |
+-------+-------+--------+-------+-------+-------+------+------+
        |                |               |              |
        v                v               v              v
+---------------+ +---------------+ +---------------------------+
|  MCP Servers  | |  CLI Tools    | |  GitHub AI Agents         |
|  (HTTP/STDIO) | |  (Direct)     | |  (Containerized)          |
+-------+-------+ +--------+------+ +-------+-------------------+
        |                  |                |
        +------------------+----------------+
                           |
                           v
                    +------------+
                    | OpenRouter |
                    | API        |
                    +------------+
```

### Execution Modes

1. **STDIO Mode** (Local Process): MCP servers run as local child processes via `.mcp.json`
   - Used when Claude and the server run on the same machine
   - Communication via standard input/output streams

2. **HTTP Mode** (Remote/Cross-Machine): Network servers on dedicated ports
   - Used for remote machines or containerized deployments
   - Communication via HTTP protocol over network

3. **Container Mode** (GitHub): Runs in `openrouter-agents` container

4. **Direct CLI Mode** (Host): Using run scripts or direct commands

## Installation and Setup

### Prerequisites

```bash
# For OpenRouter agents (OpenCode, Crush)
export OPENROUTER_API_KEY="your-openrouter-key"
```

### Method 1: Docker Container (Recommended)

```bash
# Start the agents container
docker compose up -d openrouter-agents

# Verify agents are running
docker compose logs openrouter-agents
```

### Method 2: Using Helper Scripts

```bash
# Make scripts executable
chmod +x tools/cli/agents/run_opencode.sh
chmod +x tools/cli/agents/run_crush.sh

# Run agents
./tools/cli/agents/run_opencode.sh
./tools/cli/agents/run_crush.sh
```

### Method 3: Docker Containers

```bash
# Start MCP servers
docker compose up -d mcp-opencode mcp-crush

# Or for GitHub agents
docker compose up -d openrouter-agents
```

## MCP Server Integration

All agents follow the same MCP tool pattern with four standard tools:

### Common Tool Pattern

Each agent provides:
- `consult_<agent>` - Main consultation tool with mode parameter
- `clear_<agent>_history` - Clear conversation history
- `<agent>_status` - Get integration status and statistics
- `toggle_<agent>_auto_consult` - Control automatic consultation

### OpenCode MCP Tools

Port: 8014

```python
# Main consultation
mcp__opencode__consult_opencode(
    query="Create user auth system",  # Required
    context="Using FastAPI",           # Optional context
    mode="generate",                   # generate, refactor, review, explain, quick
    comparison_mode=True,              # Compare with Claude's response
    force=False                        # Force even if disabled
)

# Utility tools
mcp__opencode__clear_opencode_history()
mcp__opencode__opencode_status()
mcp__opencode__toggle_opencode_auto_consult(enable=True)
```

### Crush MCP Tools

Port: 8015

```python
# Main consultation
mcp__crush__consult_crush(
    query="Email validator function",  # Required
    context="TypeScript target",        # Optional context
    mode="quick",                       # generate, explain, convert, quick
    comparison_mode=True,
    force=False
)

# Utility tools
mcp__crush__clear_crush_history()
mcp__crush__crush_status()
mcp__crush__toggle_crush_auto_consult(enable=True)
```

## Usage Patterns

All agents support two primary use cases:

**Review (Read-Only Analysis)**
- Code review and quality analysis
- Explaining code functionality
- Security and performance audits
- Best for: any agent

**Edit (Code Generation/Modification)**
- Writing new code from descriptions
- Refactoring existing code
- Converting between languages
- Best for: OpenCode or Crush

## CLI Usage

### OpenCode CLI

```bash
# Interactive mode
opencode interactive

# Single query
opencode run -q "Create a REST API"

# With context file
opencode run -q "Refactor this" -c code.py

# Specific operations
opencode refactor -f legacy.py -i "Apply SOLID principles"
opencode review -f feature.py --focus security,performance
```

### Crush CLI

```bash
# Interactive mode
crush

# Single query
crush run -q "Binary search implementation"

# Explain code
crush run -e complex.py

# Convert code
crush run -c script.py -t javascript
```

## GitHub Workflow Integration

The AI agents integrate with GitHub through a keyword trigger system. For complete security documentation including allow lists, rate limiting, and commit validation, see the [Agents Security Documentation](../../agents/security.md).

### Trigger Format

Triggers use the format: `[Action][Agent]`

**Supported Actions**: `[Approved]`, `[Review]`, `[Close]`, `[Summarize]`, `[Debug]`

**Supported Agents**: `[Claude]`, `[OpenCode]`, `[Crush]`

### Example PR Comment

```markdown
[Approved][OpenCode]
Please implement a user authentication system with:
- JWT token support
- Password hashing
- Session management
```

### Security Flow

1. Authorized user comments with `[Action][Agent]`
2. System verifies user is in allow list
3. System checks rate limits and repository permissions
4. For PRs: validates trigger is on latest commit
5. Agent performs requested action
6. All actions logged with full context

## AI PR Review System

PR reviews run as parallel jobs in `.github/workflows/pr-validation.yml`.

### Architecture

```
PR Created/Updated
        |
        v
+-------------------+  +-------------------+  +-------------------+
| Claude Security   |  | Claude Quality    |  | OpenRouter        |
| Review (2a)       |  | Review (2b)       |  | Review (2c, Qwen) |
+---------+---------+  +---------+---------+  +---------+---------+
          |                      |                      |
          v                      v                      v
   claude-security-review.md  claude-quality-review.md  openrouter-review.md
          |                      |                      |
          +----------------------+----------------------+
                                 |
                                 v
+------------------------------------------------------------+
|  Agent Review Response (2e): automation-cli review respond  |
|  - Merges review artifacts and trust-bucketed PR comments   |
|  - Claude implements fixes, verified against git diff       |
|  - Runs lint-basic, then commits and pushes                 |
+------------------------------------------------------------+
```

AgentCore review (2d) is optional and only runs when the `agentcore-review` label is set.

### Review Artifacts

The response agent reads each reviewer's output from a file, overridable by env var:

- `CLAUDE_SECURITY_REVIEW_PATH` (default `claude-security-review.md`)
- `CLAUDE_QUALITY_REVIEW_PATH` (default `claude-quality-review.md`)
- `OPENROUTER_REVIEW_PATH` (default `openrouter-review.md`)

## Configuration

### Environment Variables

```bash
# OpenCode (OpenRouter)
OPENROUTER_API_KEY="sk-or-..."
OPENCODE_MODEL="qwen/qwen-2.5-coder-32b-instruct"
OPENCODE_TIMEOUT=300
OPENCODE_MAX_CONTEXT=8000

# Crush (OpenRouter)
OPENROUTER_API_KEY="sk-or-..."
CRUSH_TIMEOUT=300
CRUSH_MAX_PROMPT=4000
```

### MCP Configuration (.mcp.json)

All AI code agents have been migrated to Rust for improved performance. Configure them in `.mcp.json`:

```json
{
  "mcpServers": {
    "opencode": {
      "command": "mcp-opencode",
      "args": ["--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    },
    "crush": {
      "command": "mcp-crush",
      "args": ["--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
```

**Note**: All agent MCP servers are now Rust binaries. Build from source with `cargo build --release` in each server directory, or download pre-built binaries from GitHub releases.

## Choosing an Agent

All agents provide equivalent functionality for most tasks. Choose based on:

1. **API Access**: Use the agent whose API you have access to
   - OpenRouter API -> OpenCode or Crush

2. **Task Type**:
   - **Code Review and Generation**: OpenCode or Crush
   - **Language Conversion**: Crush has a dedicated convert mode

3. **Interactive vs Batch**:
   - **Interactive sessions**: Any agent works well
   - **Batch processing**: OpenCode or Crush via containers

## Troubleshooting

### Common Issues

#### API Key Not Found

```bash
# Check if key is set
echo $OPENROUTER_API_KEY

# Set the key
export OPENROUTER_API_KEY="your-key-here"
```

#### Agent Not Found

```bash
# Rebuild and restart the container
docker compose up -d --build openrouter-agents

# Verify agents are running
docker compose logs openrouter-agents
```

#### MCP Server Not Responding

```bash
# Test server health
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
```

### Debug Mode

```bash
# Enable debug logging
export OPENCODE_DEBUG=true
export CRUSH_DEBUG=true
```

## Testing

```bash
# Test all Python MCP servers
python automation/testing/test_all_servers.py

# Test Rust MCP servers (run from each server directory)
cd tools/mcp/mcp_opencode && cargo test
cd tools/mcp/mcp_crush && cargo test

# Test HTTP endpoints (after starting server in standalone mode)
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
```

## Related Documentation

- [MCP Architecture](../../mcp/README.md) - Overall MCP server design
- [GitHub AI Agents](../../agents/README.md) - Complete agent system documentation
- [Security Model](../../agents/security.md) - Security implementation
