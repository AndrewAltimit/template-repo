# Claude Code Setup and Configuration

This guide covers the setup and usage of Claude Code as the primary AI development assistant in this repository.

## Overview

Claude Code is Anthropic's official CLI tool for AI-assisted development. It serves as the primary development partner for complex tasks including architecture design, implementation, debugging, and documentation.

## Installation

### Prerequisites

- **Node.js 22.16.0** (specifically required by Claude CLI)
- **nvm** (Node Version Manager) - recommended for managing Node.js versions

### Step 1: Install nvm and Node.js

```bash
# Install nvm (if not already installed)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Reload shell configuration
source ~/.bashrc  # or ~/.zshrc

# Install and use Node.js 22.16.0
nvm install 22.16.0
nvm use 22.16.0
```

### Step 2: Install Claude CLI

```bash
# Ensure correct Node.js version
nvm use 22.16.0

# Install Claude Code globally
npm install -g @anthropic-ai/claude-code
```

### Step 3: Authenticate

```bash
# Run the login command
claude login
```

This opens a browser for authentication. After successful login, credentials are stored in one of these locations:
- `~/.claude.json` (most common)
- `~/.config/claude/claude.json`
- `~/.claude/claude.json`

## Authentication Methods

### Subscription Authentication (Default)

Claude CLI uses subscription-based authentication tied to your Anthropic account:

```bash
claude login
```

**Important**: Subscription authentication is machine-specific. The tokens cannot be transferred to containers or other machines.

### API Key Authentication (Alternative)

For CI/CD environments or when subscription auth is unavailable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

The agents automatically prefer API key authentication when available.

## Usage

### Interactive Mode

```bash
# Start an interactive Claude Code session
./tools/cli/agents/run_claude.sh

# Or directly
claude
```

### In This Repository

Claude Code is configured via `CLAUDE.md` which provides:
- Project context and philosophy
- Available commands and tools
- Container-first guidelines
- MCP server configurations
- Security considerations

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-file Editing** | Can read and modify multiple files in a single session |
| **Command Execution** | Runs shell commands with proper sandboxing |
| **MCP Integration** | Connects to 17 MCP servers for extended capabilities |
| **Context Awareness** | Understands entire codebase through CLAUDE.md |
| **Tool Use** | Full tool use capabilities for development tasks |

## MCP Server Access

Claude Code connects to the following MCP servers (configured in `.mcp.json`):

| Server | Port | Purpose |
|--------|------|---------|
| Code Quality | 8010 | Formatting, linting, autoformat |
| Gemini | 8006 | AI consultation |
| OpenCode | 8014 | Code generation |
| Crush | 8015 | Quick code generation |
| Codex | 8021 | OpenAI code assistance |

See [MCP Documentation](../mcp/README.md) for the complete list of available servers.

## Container Considerations

Claude Code runs on the host machine rather than in containers due to authentication constraints:

1. **Session-based Auth**: Subscription tokens are machine-specific
2. **Container Isolation**: Credentials don't transfer to container environments
3. **Security Design**: Prevents credential sharing across environments

For detailed technical explanation, see [Claude Authentication](claude-auth.md).

## Best Practices

### Effective Prompting

1. **Be Specific**: Clear, detailed requests yield better results
2. **Provide Context**: Reference specific files or code sections
3. **Use CLAUDE.md**: The configuration file provides project-specific guidance
4. **Follow Conventions**: Request adherence to project patterns

### Security Considerations

1. **Review Generated Code**: Always review AI-generated code before committing
2. **No Secrets in Prompts**: Never include API keys or credentials
3. **Container-First**: Use containerized commands for CI/CD operations
4. **Validate Changes**: Run tests after significant modifications

### Integration with Other Agents

Claude Code works alongside:

| Agent | Role | When to Use |
|-------|------|-------------|
| **Gemini** | Code review | Automated PR reviews |
| **Codex** | Code generation | OpenAI-based generation |
| **OpenCode** | Code generation | OpenRouter-based generation |
| **Crush** | Quick snippets | Fast code generation |
| **GitHub Copilot** | PR suggestions | Inline code suggestions |

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `claude: command not found` | Run `nvm use 22.16.0` then reinstall |
| `Invalid API key` | Run `claude login` or set `ANTHROPIC_API_KEY` |
| Wrong Node.js version | Use `nvm use 22.16.0` before running claude |
| Auth not persisting | Check `~/.claude.json` exists and has correct permissions |

### Verify Installation

```bash
# Check Node.js version
node --version  # Should be v22.16.0

# Check Claude CLI
claude --version

# Check authentication
ls -la ~/.claude.json
```

### Re-authenticate

If authentication issues persist:

```bash
# Remove existing auth
rm ~/.claude.json

# Re-login
nvm use 22.16.0
claude login
```

## Quick Setup Script

A setup script is provided to automate host configuration:

```bash
./automation/setup/agents/setup-host-for-agents.sh
```

This script:
- Checks for required tools (Python, pip, Claude CLI, GitHub CLI)
- Verifies authentication status
- Installs Python dependencies
- Provides guidance for missing components

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | API key authentication (alternative to login) | No |
| `GITHUB_TOKEN` | GitHub API access for agent operations | Yes (for agents) |
| `GITHUB_REPOSITORY` | Repository context | Yes (for agents) |

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Project-specific Claude configuration
- [Claude Authentication](claude-auth.md) - Why agents run on host
- [Claude Expression](claude-expression.md) - Communication style guide
- [AI Agents Overview](README.md) - Complete agent ecosystem
- [AI Code Agents](../integrations/ai-services/ai-code-agents.md) - Code generation agents
