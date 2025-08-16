# OpenCode and Crush Integration Guide

This document provides comprehensive documentation for the OpenCode and Crush AI agents, including MCP integration, CLI usage, and git monitoring workflows.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation and Setup](#installation-and-setup)
4. [MCP Server Integration](#mcp-server-integration)
5. [CLI Usage](#cli-usage)
6. [Git Monitoring Workflows](#git-monitoring-workflows)
7. [API Reference](#api-reference)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

## Overview

OpenCode and Crush are AI-powered code generation agents that integrate with our development workflow through multiple interfaces:

- **OpenCode**: Specialized for comprehensive code generation, refactoring, and review using the Qwen 2.5 Coder model. Now includes a "quick" mode (default) for general queries without specific formatting, similar to Crush.
- **Crush**: Optimized for fast, concise code generation and conversions using lightweight models

Both agents use the OpenRouter API and can be accessed through:
1. MCP servers (for Claude integration)
2. CLI tools (for direct command-line usage)
3. GitHub AI agents (for automated PR/issue handling)

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interfaces                       │
├──────────────┬────────────────┬──────────────┬──────────────┤
│   Claude     │   Direct CLI   │  GitHub PRs  │  GitHub      │
│   (MCP)      │   (Scripts)    │  (Triggers)  │  Issues      │
└──────┬───────┴────────┬───────┴──────┬───────┴──────┬───────┘
       │                │              │              │
       v                v              v              v
┌──────────────┐ ┌──────────────┐ ┌─────────────────────────┐
│  MCP Servers │ │  CLI Tools   │ │  GitHub AI Agents       │
│  (HTTP/STDIO)│ │  (Direct)    │ │  (Containerized)        │
└──────┬───────┘ └──────┬───────┘ └──────┬──────────────────┘
       │                │                 │
       └────────────────┴─────────────────┘
                        │
                        v
               ┌────────────────┐
               │  OpenRouter    │
               │  API Gateway   │
               └────────────────┘
```

### Execution Modes

1. **STDIO Mode** (Local Process): MCP servers run as local child processes via `.mcp.json`
   - Used when Claude and the server run on the same machine
   - Communication via standard input/output streams

2. **HTTP Mode** (Remote/Cross-Machine): Network servers on ports 8014/8015
   - Used for remote machines or containerized deployments
   - Communication via HTTP protocol over network

3. **Container Mode** (GitHub): Runs in `openrouter-agents` container
4. **Direct CLI Mode** (Host): Using run scripts or direct commands

## Installation and Setup

### Prerequisites

```bash
# Required environment variable
export OPENROUTER_API_KEY="your-api-key-here"

# Optional: Specify custom model for OpenCode
export OPENCODE_MODEL="qwen/qwen-2.5-coder-32b-instruct"
```

### Method 1: GitHub AI Agents Package (Recommended)

```bash
# Install the package with all agents
pip3 install -e ./packages/github_ai_agents

# Verify installation
opencode --version
crush --version
```

### Method 2: Using Helper Scripts

```bash
# Make scripts executable
chmod +x tools/utilities/run_opencode.sh
chmod +x tools/utilities/run_crush.sh

# Run OpenCode
./tools/utilities/run_opencode.sh

# Run Crush
./tools/utilities/run_crush.sh
```

### Method 3: Docker Containers

```bash
# Start MCP servers
docker-compose up -d mcp-opencode mcp-crush

# Or for GitHub agents
docker-compose up -d openrouter-agents
```

## MCP Server Integration

### OpenCode MCP Tools

The OpenCode MCP server exposes the following tools to Claude:

#### `mcp__opencode__consult_opencode`

Consult OpenCode for code generation, refactoring, or review.

```python
# Parameters
{
    "query": str,           # Required: The coding question or task
    "context": str,         # Optional: Additional context or existing code
    "mode": str,            # Optional: "generate", "refactor", "review", "explain", "quick" (default: "quick")
    "comparison_mode": bool,# Optional: Compare with previous response
    "force": bool           # Optional: Force consultation even if disabled
}

# Example usage in Claude
result = await mcp__opencode__consult_opencode(
    query="Create a REST API with authentication",
    mode="generate",
    context="Using FastAPI and JWT tokens"
)
```

#### `mcp__opencode__clear_opencode_history`

Clear the conversation history for fresh responses.

```python
# No parameters required
await mcp__opencode__clear_opencode_history()
```

#### `mcp__opencode__opencode_status`

Get integration status and statistics.

```python
# Returns
{
    "enabled": bool,
    "model": str,
    "api_key_configured": bool,
    "total_generations": int,
    "history_size": int,
    "last_generation": str
}
```

#### `mcp__opencode__toggle_opencode_auto_consult`

Control automatic consultation on uncertainty detection.

```python
# Parameters
{
    "enable": bool  # Required: Enable or disable auto-consultation
}
```

### Crush MCP Tools

The Crush MCP server exposes similar tools:

#### `mcp__crush__consult_crush`

Fast code generation with style options.

```python
# Parameters
{
    "query": str,           # Required: The coding question or task
    "context": str,         # Optional: Additional context
    "mode": str,            # Optional: "generate", "explain", "convert", "quick"
    "comparison_mode": bool,# Optional: Compare with previous response
    "force": bool           # Optional: Force consultation
}

# Example usage
result = await mcp__crush__consult_crush(
    query="Write a Python function to validate email",
    mode="quick"
)
```

#### `mcp__crush__clear_crush_history`

Clear conversation history.

```python
await mcp__crush__clear_crush_history()
```

#### `mcp__crush__crush_status`

Get integration status.

```python
# Returns similar structure to OpenCode status
```

#### `mcp__crush__toggle_crush_auto_consult`

Toggle automatic consultation.

```python
await mcp__crush__toggle_crush_auto_consult(enable=True)
```

## CLI Usage

### OpenCode CLI

#### Interactive Mode

```bash
# Start interactive session
./tools/utilities/run_opencode.sh

# Or directly
opencode interactive
```

#### Single Query Mode

```bash
# Basic generation
./tools/utilities/run_opencode.sh -q "Write a Python web scraper"

# With context file
./tools/utilities/run_opencode.sh -q "Refactor this code" -c existing.py

# With plan mode for complex tasks
./tools/utilities/run_opencode.sh -q "Build a microservices architecture" -p
```

#### Direct CLI Commands

```bash
# Generate code
opencode run -q "Create a user authentication system"

# Refactor code
opencode refactor -f legacy_code.py -i "Apply SOLID principles"

# Review code
opencode review -f new_feature.py --focus security,performance
```

### Crush CLI

#### Interactive Mode

```bash
# Start interactive session
./tools/utilities/run_crush.sh

# Or directly
crush
```

#### Quick Generation

```bash
# Concise output (default)
./tools/utilities/run_crush.sh -q "Binary search implementation"

# Detailed implementation
./tools/utilities/run_crush.sh -q "REST API endpoints" -s detailed

# With explanations
./tools/utilities/run_crush.sh -q "Sorting algorithm" -s explained
```

#### Code Operations

```bash
# Explain existing code
./tools/utilities/run_crush.sh -e complex_algorithm.py

# Convert between languages
./tools/utilities/run_crush.sh -c script.py -t javascript
./tools/utilities/run_crush.sh -c app.js -t python
```

## Git Monitoring Workflows

### Automated PR Code Generation

Both OpenCode and Crush integrate with our GitHub monitoring agents to automatically handle code generation requests in PRs and issues.

#### PR Review Workflow

1. **Trigger Detection**: The PR monitor scans for specific keywords
2. **Agent Selection**: Based on the trigger, selects appropriate agent
3. **Code Generation**: Agent generates code based on the request
4. **Comment Creation**: Posts generated code as PR comment

#### Trigger Keywords

```yaml
OpenCode Triggers:
  - "[Generate][OpenCode]" - Generate new code
  - "[Refactor][OpenCode]" - Refactor existing code
  - "[Review][OpenCode]"   - Review and analyze code
  - "[Explain][OpenCode]"  - Explain code functionality

Crush Triggers:
  - "[Quick][Crush]"       - Fast code generation
  - "[Convert][Crush]"     - Language conversion
  - "[Explain][Crush]"     - Quick explanation
  - "[Generate][Crush]"    - Standard generation
```

#### Example PR Comment Triggers

```markdown
# For comprehensive implementation
[Generate][OpenCode]
Please implement a user authentication system with:
- JWT token support
- Password hashing
- Session management
- Rate limiting

# For quick code generation
[Quick][Crush]
Write a function to validate credit card numbers

# For code conversion
[Convert][Crush]
Convert the Python script in src/utils.py to TypeScript

# For refactoring
[Refactor][OpenCode]
Refactor the database module to use async/await pattern
```

### Issue to PR Workflow

The issue monitor can automatically create PRs with OpenCode/Crush-generated code:

1. **Issue Creation**: User creates issue with detailed requirements
2. **Agent Trigger**: Include agent keyword in issue description
3. **Code Generation**: Agent generates complete implementation
4. **PR Creation**: Automatically creates PR with generated code
5. **Review Process**: Standard PR review workflow applies

#### Example Issue Template

```markdown
Title: Add data validation module

[Generate][OpenCode]

## Requirements
- Input validation for user data
- Email, phone, and address validation
- Custom validation rules support
- Error message localization

## Acceptance Criteria
- [ ] All validation functions have tests
- [ ] Documentation is included
- [ ] Follows project coding standards
```

### Scheduled Automation

Configure GitHub Actions to run agents on schedule:

```yaml
# .github/workflows/ai-agents.yml
name: AI Agent Automation

on:
  schedule:
    - cron: '0 */2 * * *'  # Every 2 hours
  workflow_dispatch:

jobs:
  monitor-issues:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v3

      - name: Run Issue Monitor with OpenCode
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          docker-compose run --rm openrouter-agents \
            python -m github_ai_agents.cli issue-monitor \
            --agent opencode

  monitor-prs:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v3

      - name: Run PR Monitor with Crush
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          docker-compose run --rm openrouter-agents \
            python -m github_ai_agents.cli pr-monitor \
            --agent crush
```

## API Reference

### OpenCode Integration Module

```python
from tools.mcp.opencode.opencode_integration import OpenCodeIntegration

# Initialize
integration = OpenCodeIntegration()

# Generate code
result = await integration.generate_code(
    prompt="Create a caching layer",
    context={"language": "python", "framework": "redis"}
)

# Refactor code
result = await integration.refactor_code(
    code=existing_code,
    instructions="Apply async/await pattern"
)

# Review code
feedback = await integration.review_code(
    code=new_feature_code,
    focus_areas=["security", "performance"]
)
```

### Crush Integration Module

```python
from tools.mcp.crush.crush_integration import CrushIntegration

# Initialize
integration = CrushIntegration()

# Quick generation
code = await integration.quick_generate(
    prompt="Binary tree traversal",
    style="concise"
)

# Convert code
converted = await integration.convert_code(
    code=python_code,
    target_language="javascript"
)

# Explain code
explanation = await integration.explain_code(
    code=complex_algorithm,
    focus="time complexity"
)
```

## Configuration

### Environment Variables

```bash
# OpenCode Configuration
export OPENROUTER_API_KEY="sk-or-..."
export OPENCODE_MODEL="qwen/qwen-2.5-coder-32b-instruct"
export OPENCODE_TIMEOUT=300
export OPENCODE_MAX_CONTEXT=8000
export OPENCODE_LOG_GENERATIONS=true
export OPENCODE_INCLUDE_HISTORY=true
export OPENCODE_MAX_HISTORY=5

# Crush Configuration
export CRUSH_TIMEOUT=300
export CRUSH_MAX_PROMPT=4000
export CRUSH_LOG_GENERATIONS=true
export CRUSH_INCLUDE_HISTORY=true
export CRUSH_MAX_HISTORY=5
```

### Configuration Files

#### opencode-config.json

```json
{
  "enabled": true,
  "model": "qwen/qwen-2.5-coder-32b-instruct",
  "timeout": 300,
  "max_context_length": 8000,
  "log_generations": true,
  "include_history": true,
  "max_history": 5,
  "auto_consult": {
    "enabled": false,
    "uncertainty_threshold": 0.7
  }
}
```

#### crush-config.json

```json
{
  "enabled": true,
  "timeout": 300,
  "max_prompt_length": 4000,
  "quiet_mode": true,
  "default_style": "concise",
  "auto_consult": {
    "enabled": false,
    "quick_mode": true
  }
}
```

### MCP Configuration (.mcp.json)

```json
{
  "mcpServers": {
    "opencode": {
      "command": "python",
      "args": ["-m", "tools.mcp.opencode.server", "--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}",
        "OPENCODE_MODEL": "qwen/qwen-2.5-coder-32b-instruct"
      }
    },
    "crush": {
      "command": "python",
      "args": ["-m", "tools.mcp.crush.server", "--mode", "stdio"],
      "env": {
        "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
      }
    }
  }
}
```

## Troubleshooting

### Common Issues

#### 1. API Key Not Found

```bash
# Check if key is set
echo $OPENROUTER_API_KEY

# Set the key
export OPENROUTER_API_KEY="your-key-here"

# Add to shell profile for persistence
echo 'export OPENROUTER_API_KEY="your-key-here"' >> ~/.bashrc
```

#### 2. Agent Not Found

```bash
# Reinstall the package
pip3 install -e ./packages/github_ai_agents --force-reinstall

# Verify installation
which opencode
which crush
```

#### 3. Container Connection Issues

```bash
# Check container status
docker-compose ps openrouter-agents

# View logs
docker-compose logs -f openrouter-agents

# Restart container
docker-compose restart openrouter-agents
```

#### 4. MCP Server Not Responding

```bash
# Test OpenCode server
curl http://localhost:8014/health

# Test Crush server
curl http://localhost:8015/health

# Check server logs
python -m tools.mcp.opencode.server --mode http --debug
python -m tools.mcp.crush.server --mode http --debug
```

#### 5. Rate Limiting

```bash
# Check current usage
python tools/mcp/opencode/scripts/test_server.py --status

# Adjust timeout
export OPENCODE_TIMEOUT=600
export CRUSH_TIMEOUT=600
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# For OpenCode
export OPENCODE_DEBUG=true
export OPENCODE_LOG_LEVEL=DEBUG

# For Crush
export CRUSH_DEBUG=true
export CRUSH_LOG_LEVEL=DEBUG

# Run with verbose output
./tools/utilities/run_opencode.sh -q "test" --debug
./tools/utilities/run_crush.sh -q "test" --debug
```

### Testing

```bash
# Test all MCP servers
python automation/testing/test_all_servers.py

# Test specific servers
python tools/mcp/opencode/scripts/test_server.py
python tools/mcp/crush/scripts/test_server.py

# Test GitHub agents
python -m pytest tests/test_opencode_agent.py -v
python -m pytest tests/test_crush_agent.py -v
```

## Best Practices

### When to Use OpenCode vs Crush

**Use OpenCode when:**
- Building complex, multi-file implementations
- Refactoring large codebases
- Needing comprehensive code review
- Requiring detailed architectural decisions
- Working with enterprise-grade requirements

**Use Crush when:**
- Need quick code snippets
- Converting code between languages
- Requiring fast iterations
- Building simple utilities
- Prototyping ideas rapidly

### Integration Patterns

1. **Hybrid Approach**: Use Crush for initial prototyping, then OpenCode for production refinement
2. **Specialized Roles**: Crush for utilities, OpenCode for core business logic
3. **Review Pipeline**: Crush for quick checks, OpenCode for thorough reviews
4. **Learning Path**: Start with Crush explanations, dive deep with OpenCode

### Security Considerations

1. **API Key Management**: Never commit API keys to the repository
2. **Code Review**: Always review generated code before merging
3. **Sandbox Testing**: Test generated code in isolated environments
4. **Access Control**: Limit agent triggers to authorized users
5. **Audit Logging**: Track all agent-generated code for compliance

## Related Documentation

- [MCP Architecture](../../mcp/README.md) - Overall MCP server design
- [GitHub AI Agents](../../ai-agents/README.md) - Complete agent system documentation
- [Security Model](../../../packages/github_ai_agents/docs/security.md) - Security implementation details
- [Container Strategy](../../ai-agents/containerization-strategy.md) - Containerization approach
