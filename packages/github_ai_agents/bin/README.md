# GitHub AI Agents - Executables

This directory contains executable wrappers for the GitHub AI Agents tools.

## Available Commands

### `issue-monitor`

Monitor GitHub issues and automatically create PRs when triggered.

**Usage**: `./issue-monitor [options]`

**See**: `issue-monitor --help`

**Examples**:
```bash
# Run once
issue-monitor

# Continuous monitoring (every 5 minutes)
issue-monitor --continuous --interval 300

# Process specific issue
issue-monitor --target-issue 123

# Review-only mode (no PR creation)
issue-monitor --review-only
```

**Environment Variables**:
- `GITHUB_TOKEN` (required): GitHub API token
- `GITHUB_REPOSITORY` (required): Repository (owner/repo)
- `OPENROUTER_API_KEY` (optional): For AI agent execution
- `ALLOWED_USERS` (optional): Authorized users (comma-separated)

---

### `pr-monitor`

Monitor pull requests and implement review feedback automatically.

**Usage**: `./pr-monitor [options]`

**See**: `pr-monitor --help`

**Examples**:
```bash
# Monitor all open PRs
pr-monitor

# Monitor specific PR
pr-monitor --pr-number 45

# Continuous monitoring
pr-monitor --continuous
```

**Environment Variables**:
- `GITHUB_TOKEN` (required): GitHub API token
- `GITHUB_REPOSITORY` (required): Repository (owner/repo)
- `OPENROUTER_API_KEY` (optional): For AI agent execution
- `ALLOWED_USERS` (optional): Authorized users (comma-separated)

---

### `board-cli`

Manage GitHub Projects v2 boards for agent coordination and work tracking.

**Usage**: `./board-cli [command] [options]`

**See**: `board-cli --help`

**Commands**:
- `ready` - Query ready work (unblocked, unclaimed issues)
- `create` - Create issue with board metadata
- `block` - Add blocker dependency
- `status` - Update issue status
- `graph` - View dependency graph
- `claim` - Claim issue for work
- `release` - Release claim on issue
- `info` - Get issue details

**Examples**:
```bash
# Get ready work
board-cli ready --agent claude --limit 5

# Create issue
board-cli create "Fix bug" --type bug --priority high

# Claim issue
board-cli claim 123 --agent claude

# Update status
board-cli status 123 in-progress

# View dependencies
board-cli graph 123

# Release work
board-cli release 123 --agent claude --reason completed
```

**Environment Variables**:
- `GITHUB_TOKEN` (required): GitHub API token
- `GITHUB_REPOSITORY` (required): Repository (owner/repo)
- `GITHUB_PROJECT_NUMBER` (required): Project board number
- `BOARD_CONFIG_PATH` (optional): Config file path (default: `.github/ai-agents-board.yml`)

---

## Installation

These scripts are automatically added to PATH when you install the package:

```bash
# Install in editable mode
pip install -e .

# Or install with board support
pip install -e .[board]
```

After installation, run commands without the `./` prefix from anywhere:

```bash
issue-monitor
pr-monitor
board-cli ready
```

## Direct Execution

You can also run these scripts directly from the bin/ directory without installation:

```bash
# From repository root
./packages/github_ai_agents/bin/issue-monitor
./packages/github_ai_agents/bin/pr-monitor
./packages/github_ai_agents/bin/board-cli ready
```

**Note**: Direct execution requires that the package is importable (either installed or in PYTHONPATH).

## Containerized Execution

These tools can also run in containers for consistency:

```bash
# Using docker-compose
docker-compose run --rm openrouter-agents issue-monitor
docker-compose run --rm openrouter-agents pr-monitor
docker-compose run --rm mcp-github-board board-cli ready
```

See `examples/github_actions_example.yml` for GitHub Actions integration.

## Troubleshooting

### Command not found

If you get "command not found" after installation:

```bash
# Verify installation
pip list | grep github-ai-agents

# Reinstall
pip uninstall github-ai-agents
pip install -e .

# Check PATH
which issue-monitor
```

### Import errors

If you see import errors when running directly:

```bash
# Install the package first
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH=/path/to/template-repo/packages/github_ai_agents/src:$PYTHONPATH
```

### Permission denied

If you get permission denied:

```bash
# Make scripts executable
chmod +x packages/github_ai_agents/bin/*
```

## See Also

- [CLI Reference](../docs/CLI_REFERENCE.md) - Complete command documentation
- [Examples](../examples/README.md) - Usage examples
- [Board Integration](../docs/board-integration.md) - Board setup guide
- [API Reference](../docs/API_REFERENCE.md) - Python API documentation
