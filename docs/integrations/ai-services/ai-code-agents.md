# AI Code Agents Integration Guide

This document provides comprehensive documentation for the AI code assistance agents available in this project.

## Overview

The project integrates four AI code agents, each using a different backend provider:

| Agent | Provider | API | Primary Use |
|-------|----------|-----|-------------|
| **OpenCode** | OpenRouter | OpenRouter API | General code assistance |
| **Crush** | OpenRouter | OpenRouter API | General code assistance |
| **Codex** | OpenAI | ChatGPT Plus auth | General code assistance |
| **Gemini** | Google | Google AI Studio | Code review (limited tool use) |

All agents provide similar functionality through a unified MCP interface. Choose based on your API access and provider preference.

**Note on Gemini**: The Gemini CLI currently has limited tool use capabilities, making it best suited for code review tasks rather than interactive code generation.

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
          +----------------+----------------+
          |                                 |
    +-----v------+                   +------v-----+
    | OpenRouter |                   |  OpenAI    |
    | API        |                   |  (Codex)   |
    +------------+                   +------------+
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

# For Codex (requires ChatGPT Plus subscription)
npm install -g @openai/codex
codex auth  # Opens browser for OpenAI login

# For Gemini
export GOOGLE_API_KEY="your-google-ai-studio-key"
# Get free key at: https://aistudio.google.com/app/apikey
```

### Method 1: GitHub AI Agents Package (Recommended)

```bash
# Install the package with all agents
pip3 install -e ./packages/github_agents

# Verify installation
opencode --version
crush --version
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
docker compose up -d mcp-opencode mcp-crush mcp-codex

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

### Codex MCP Tools

Port: 8021

```python
# Main consultation
mcp__codex__consult_codex(
    query="Sort algorithm",            # Required
    context="Optimize for memory",     # Optional context
    mode="generate",                   # generate, complete, refactor, explain, quick
    comparison_mode=True,
    force=False
)

# Utility tools
mcp__codex__clear_codex_history()
mcp__codex__codex_status()
mcp__codex__toggle_codex_auto_consult(enable=True)
```

### Gemini MCP Tools

Port: 8006

**Note**: Gemini is primarily recommended for code review tasks due to limited tool use capabilities.

```python
# Main consultation (best for review tasks)
mcp__gemini__consult_gemini(
    query="Review this function",      # Required
    context="def factorial(n): ...",   # Optional context
    comparison_mode=True,
    force=False
)

# Utility tools
mcp__gemini__clear_gemini_history()
mcp__gemini__gemini_status()
mcp__gemini__toggle_gemini_auto_consult(enable=True)
```

## Usage Patterns

All agents support two primary use cases:

**Review (Read-Only Analysis)**
- Code review and quality analysis
- Explaining code functionality
- Security and performance audits
- Best for: Gemini (specialized), or any agent

**Edit (Code Generation/Modification)**
- Writing new code from descriptions
- Refactoring existing code
- Converting between languages
- Best for: OpenCode, Crush, or Codex

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

### Codex CLI

```bash
# Interactive mode (primary usage)
codex

# With specific prompt
codex "Write a function to validate emails"
```

## GitHub Workflow Integration

The AI agents integrate with GitHub through a keyword trigger system. For complete security documentation including allow lists, rate limiting, and commit validation, see the [Agents Security Documentation](../../agents/security.md).

### Trigger Format

Triggers use the format: `[Action][Agent]`

**Supported Actions**: `[Approved]`, `[Review]`, `[Close]`, `[Summarize]`, `[Debug]`

**Supported Agents**: `[Claude]`, `[Gemini]`, `[OpenCode]`, `[Crush]`

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

## Dual AI PR Review System

The project uses a two-stage AI review system that combines Gemini and Codex for comprehensive PR code reviews:

### Architecture

```
PR Created/Updated
        |
        v
+------------------+       +------------------+
|  Gemini Review   | ----> |  Codex Review    |
|  (Primary)       |       |  (Secondary)     |
|                  |       |  + Gemini Context|
+--------+---------+       +--------+---------+
         |                          |
         v                          v
+--------------------------------------------+
|       Consolidated Feedback System         |
|  - Deduplicates issues from both reviewers |
|  - Boosts confidence for items found by    |
|    both reviewers                          |
|  - Attributes sources: [GEMINI], [CODEX],  |
|    [BOTH]                                  |
+--------------------------------------------+
                    |
                    v
+--------------------------------------------+
|       AgentJudgement Decision System       |
|  - High confidence: Auto-fix              |
|  - Low confidence: Ask owner              |
+--------------------------------------------+
                    |
                    v
+--------------------------------------------+
|         Claude Implementation              |
|  - Receives consolidated feedback          |
|  - Implements fixes with full context      |
+--------------------------------------------+
```

### Workflow Steps

1. **Stage 2a - Gemini Review**: Gemini analyzes the PR diff and posts review comments
2. **Stage 2b - Codex Review**: Codex runs after Gemini, receiving Gemini's review as context to provide complementary feedback
3. **Consolidation**: The PR monitor detects both reviews and consolidates actionable items
4. **Decision**: AgentJudgement categorizes items by confidence level
5. **Implementation**: Claude receives the consolidated feedback and implements fixes

### Review Comment Markers

Each AI review includes a tracking marker:

```markdown
<!-- gemini-review-marker:commit:abc1234 -->
<!-- codex-review-marker:commit:abc1234 -->
<!-- ai-agent-consolidated-response:consolidated-xxx-yyy -->
```

### Consolidated Response Benefits

- **Reduced false positives**: Issues flagged by both reviewers get boosted confidence
- **Complementary perspectives**: Codex may catch issues Gemini misses and vice versa
- **Source attribution**: Each item is tagged with its source ([GEMINI], [CODEX], or [BOTH])
- **Unified implementation**: Claude receives all feedback in a single consolidated prompt

### Configuration

The dual review system is enabled by default. To customize:

```yaml
# In .github/workflows/pr-validation.yml
codex-review:
  needs: [detect-changes, gemini-review]  # Runs after Gemini
  if: needs.gemini-review.result != 'skipped'
```

Environment variables:
- `GEMINI_REVIEW_PATH`: Path to Gemini's review artifact (auto-set by workflow)
- `CODEX_REVIEW_REQUIRED`: Set to "true" for hard failure on Codex errors

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

# Codex (OpenAI)
CODEX_AUTH_PATH="~/.codex/auth.json"
CODEX_TIMEOUT=300
CODEX_MAX_CONTEXT=8000

# Gemini (Google)
GOOGLE_API_KEY="your-api-key"
GEMINI_TIMEOUT=60
GEMINI_MAX_CONTEXT=4000
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
    },
    "codex": {
      "command": "mcp-codex",
      "args": ["--mode", "stdio"]
    },
    "gemini": {
      "command": "mcp-gemini",
      "args": ["--mode", "stdio"]
    }
  }
}
```

**Note**: All agent MCP servers are now Rust binaries. Build from source with `cargo build --release` in each server directory, or download pre-built binaries from GitHub releases.

## Choosing an Agent

All agents provide equivalent functionality for most tasks. Choose based on:

1. **API Access**: Use the agent whose API you have access to
   - OpenRouter API -> OpenCode or Crush
   - ChatGPT Plus subscription -> Codex
   - Google AI Studio (free tier available) -> Gemini

2. **Task Type**:
   - **Code Review**: Gemini is well-suited for review tasks
   - **Code Generation**: OpenCode, Crush, or Codex
   - **Language Conversion**: Crush has a dedicated convert mode
   - **Code Completion**: Codex has a dedicated complete mode

3. **Interactive vs Batch**:
   - **Interactive sessions**: Any agent works well
   - **Batch processing**: OpenCode or Crush via containers

## Troubleshooting

### Common Issues

#### API Key Not Found

```bash
# Check if key is set
echo $OPENROUTER_API_KEY
echo $GOOGLE_API_KEY

# Set the key
export OPENROUTER_API_KEY="your-key-here"
```

#### Agent Not Found

```bash
# Reinstall the package
pip3 install -e ./packages/github_agents --force-reinstall

# Verify installation
which opencode
which crush
```

#### MCP Server Not Responding

```bash
# Test server health
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
curl http://localhost:8021/health  # Codex
curl http://localhost:8006/health  # Gemini
```

#### Codex Authentication

```bash
# Re-authenticate
codex auth

# Check auth file exists
ls -la ~/.codex/auth.json
```

### Debug Mode

```bash
# Enable debug logging
export OPENCODE_DEBUG=true
export CRUSH_DEBUG=true
export CODEX_DEBUG=true
export GEMINI_DEBUG=true
```

## Testing

```bash
# Test all Python MCP servers
python automation/testing/test_all_servers.py

# Test Rust MCP servers (run from each server directory)
cd tools/mcp/mcp_opencode && cargo test
cd tools/mcp/mcp_crush && cargo test
cd tools/mcp/mcp_codex && cargo test
cd tools/mcp/mcp_gemini && cargo test

# Test HTTP endpoints (after starting server in standalone mode)
curl http://localhost:8014/health  # OpenCode
curl http://localhost:8015/health  # Crush
curl http://localhost:8021/health  # Codex
curl http://localhost:8006/health  # Gemini
```

## Related Documentation

- [MCP Architecture](../../mcp/README.md) - Overall MCP server design
- [GitHub AI Agents](../../agents/README.md) - Complete agent system documentation
- [Security Model](../../agents/security.md) - Security implementation
- [Gemini Setup](./gemini-setup.md) - Detailed Gemini configuration
