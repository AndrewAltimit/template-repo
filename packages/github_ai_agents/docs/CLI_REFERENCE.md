# CLI Reference - GitHub AI Agents

Complete command-line interface reference for the GitHub AI Agents package.

## Table of Contents

- [Board CLI](#board-cli)
- [Issue Monitor](#issue-monitor)
- [PR Monitor](#pr-monitor)
- [General Options](#general-options)

---

## Board CLI

Command-line tool for managing GitHub Projects v2 boards.

**Command**: `board-cli`

### Global Flags

```bash
board-cli [global flags] <command> [command flags]
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--verbose` | `-v` | Enable verbose logging | `false` |
| `--json` | | Output results as JSON | `false` |

### Commands

#### `ready` - Query Ready Work

Get issues ready to work on (unblocked, unclaimed).

**Usage:**
```bash
board-cli ready [flags]
```

**Flags:**
| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--agent` | string | Filter by assigned agent | None |
| `--priority` | string | Minimum priority level (critical, high, medium, low) | None |
| `--limit` | int | Maximum number of items to return | 10 |

**Examples:**
```bash
# Get 10 ready work items
board-cli ready

# Filter by agent
board-cli ready --agent claude

# Get high priority items
board-cli ready --priority high --limit 5

# JSON output for automation
board-cli ready --json --limit 20
```

**Output:**
```
Found 3 ready work items:

#123: Implement dark mode toggle
  Status: Todo
  Priority: High
  Type: Feature
  Agent: None
  Blocked by: None

#124: Fix parser bug
  Status: Todo
  Priority: Critical
  Type: Bug
  Agent: None
  Blocked by: None

#125: Update documentation
  Status: Todo
  Priority: Medium
  Type: Documentation
  Agent: None
  Blocked by: None
```

---

#### `create` - Create Tracked Issue

Create a new issue with board metadata.

**Usage:**
```bash
board-cli create <title> [flags]
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `title` | string | Yes | Issue title |

**Flags:**
| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--body` | string | Issue body/description | None |
| `--type` | string | Issue type (feature, bug, tech_debt, documentation) | None |
| `--priority` | string | Priority level (critical, high, medium, low) | None |
| `--agent` | string | Assign to agent | None |
| `--size` | string | Estimated size (xs, s, m, l, xl) | None |

**Examples:**
```bash
# Basic issue
board-cli create "Fix authentication bug"

# With full metadata
board-cli create "Add dark mode" \
  --type feature \
  --priority high \
  --agent claude \
  --size m \
  --body "Implement dark mode toggle in user settings"

# JSON output
board-cli create "Update README" --type documentation --json
```

**Output:**
```
Created issue #126: Add dark mode
URL: https://github.com/owner/repo/issues/126
```

---

#### `block` - Add Blocker Dependency

Mark one issue as blocked by another.

**Usage:**
```bash
board-cli block <issue> --blocked-by <blocker>
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue` | int | Yes | Issue number to block |

**Flags:**
| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--blocked-by` | int | Yes | Blocker issue number |

**Examples:**
```bash
# Issue #123 is blocked by #124
board-cli block 123 --blocked-by 124

# JSON output
board-cli block 123 --blocked-by 124 --json
```

**Output:**
```
Added blocker: #123 is now blocked by #124
```

---

#### `status` - Update Issue Status

Change the status of an issue.

**Usage:**
```bash
board-cli status <issue> <status> [flags]
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue` | int | Yes | Issue number |
| `status` | string | Yes | New status |

**Status Values:**
- `todo` - Ready to work
- `in-progress` - Being worked on
- `blocked` - Waiting on dependencies
- `done` - Completed
- `abandoned` - No longer pursuing

**Flags:**
| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--agent` | string | Assign to agent | None |

**Examples:**
```bash
# Update to in-progress
board-cli status 123 in-progress

# Update and assign agent
board-cli status 123 in-progress --agent claude

# Mark as done
board-cli status 123 done

# JSON output
board-cli status 123 blocked --json
```

**Output:**
```
Updated issue #123 to status: In Progress
Assigned to agent: claude
```

---

#### `graph` - View Dependency Graph

Display dependency relationships for an issue.

**Usage:**
```bash
board-cli graph <issue> [flags]
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue` | int | Yes | Issue number |

**Flags:**
| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--depth` | int | Graph traversal depth | 3 |

**Examples:**
```bash
# Show dependencies for issue #123
board-cli graph 123

# Deep graph traversal
board-cli graph 123 --depth 5

# JSON output
board-cli graph 123 --json
```

**Output:**
```
Dependency graph for issue #123:

Blocks (issues this blocks):
  #125: Update API endpoints
  #126: Refactor auth flow

Blocked by:
  #124: Fix parser bug

Discovered from: #100: Implement user authentication

Discovered during (children):
  #127: Add input validation
  #128: Update error messages
```

---

#### `claim` - Claim Issue for Work

Claim an issue to prevent conflicts with other agents.

**Usage:**
```bash
board-cli claim <issue> --agent <agent>
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue` | int | Yes | Issue number |

**Flags:**
| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--agent` | string | Yes | Agent name |

**Examples:**
```bash
# Claim for Claude
board-cli claim 123 --agent claude

# JSON output with session ID
board-cli claim 123 --agent claude --json
```

**Output:**
```
Successfully claimed issue #123 for agent claude
Session ID: 8f7d3c2a-5b1e-4f9a-8c6d-2e3f4a5b6c7d
```

---

#### `release` - Release Claim

Release claim on an issue when done or blocked.

**Usage:**
```bash
board-cli release <issue> --agent <agent> [--reason <reason>]
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue` | int | Yes | Issue number |

**Flags:**
| Flag | Type | Required | Description | Default |
|------|------|----------|-------------|---------|
| `--agent` | string | Yes | Agent name | |
| `--reason` | string | No | Release reason | `completed` |

**Reason Values:**
- `completed` - Work finished successfully
- `blocked` - Hit a blocker, needs resolution
- `abandoned` - Decided not to pursue
- `error` - Encountered an error

**Examples:**
```bash
# Release as completed (default)
board-cli release 123 --agent claude

# Release as blocked
board-cli release 123 --agent claude --reason blocked

# Release as abandoned
board-cli release 123 --agent claude --reason abandoned

# Release with error
board-cli release 123 --agent claude --reason error

# JSON output
board-cli release 123 --agent claude --reason completed --json
```

**Output:**
```
Released claim on issue #123 (reason: completed)
```

---

#### `info` - Get Issue Details

Get detailed information about an issue including history.

**Usage:**
```bash
board-cli info <issue>
```

**Arguments:**
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue` | int | Yes | Issue number |

**Examples:**
```bash
# Get issue details
board-cli info 123

# JSON output
board-cli info 123 --json
```

**Output:**
```
#123: Implement dark mode toggle
  Status: In Progress
  Priority: High
  Type: Feature
  Agent: claude
  Blocked by: #124

Current blockers:
  #124: Fix parser bug (Done)

Claim history:
  2025-10-25T14:30:00: claude (session: abc-123)
  2025-10-25T15:45:00: claude (session: def-456)
```

---

## Issue Monitor

Monitor GitHub issues for trigger comments and create PRs.

**Command**: `issue-monitor`

### Usage

```bash
issue-monitor [flags]
```

### Flags

| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--repo` | string | Repository (overrides GITHUB_REPOSITORY) | From env |
| `--interval` | int | Polling interval in seconds | 300 |
| `--continuous` | bool | Run continuously | `false` |
| `--review-only` | bool | Review mode only, don't create PRs | `false` |
| `--target-issue` | int | Process specific issue number | None |

### Examples

```bash
# Run once
issue-monitor

# Continuous monitoring (every 5 minutes)
issue-monitor --continuous --interval 300

# Continuous with 10 minute interval
issue-monitor --continuous --interval 600

# Review-only mode (no PR creation)
issue-monitor --review-only

# Process specific issue
issue-monitor --target-issue 123

# Custom repository
issue-monitor --repo owner/repo
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub API token | Yes |
| `GITHUB_REPOSITORY` | Repository name (owner/repo) | Yes |
| `ENABLE_AI_AGENTS` | Enable agent execution | No (default: true) |

### Output

```
Processing issues for repository: owner/repo
Found 5 recent open issues
Processing issue #123: Add feature X
  [TRIGGER] Detected: [Approved][OpenCode]
  [AGENT] Generating implementation...
  [STATUS] Creating PR...
  [SUCCESS] PR created: #124
```

---

## PR Monitor

Monitor pull requests for review comments and implement fixes.

**Command**: `pr-monitor`

### Usage

```bash
pr-monitor [flags]
```

### Flags

| Flag | Type | Description | Default |
|------|------|-------------|---------|
| `--repo` | string | Repository (overrides GITHUB_REPOSITORY) | From env |
| `--continuous` | bool | Run continuously | `false` |
| `--pr-number` | int | Monitor specific PR | None |

### Examples

```bash
# Monitor all PRs once
pr-monitor

# Monitor continuously
pr-monitor --continuous

# Monitor specific PR
pr-monitor --pr-number 123

# Custom repository
pr-monitor --repo owner/repo
```

### Environment Variables

Same as Issue Monitor.

### Output

```
Monitoring PRs for repository: owner/repo
Found 3 open PRs with review comments
Processing PR #124: Add feature X
  [TRIGGER] Review comment detected: [Fix][OpenCode]
  [AGENT] Implementing fix...
  [STATUS] Pushing changes...
  [SUCCESS] Changes committed
```

---

## General Options

### Configuration Files

All commands look for configuration in:

1. `.github/ai-agents-board.yml` - Board configuration
2. `.env` - Environment variables
3. Environment variables

### Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 130 | Interrupted by user (Ctrl+C) |

### Logging

Control logging with:

```bash
# Verbose output
board-cli --verbose ready

# Quiet (errors only)
board-cli ready 2>/dev/null

# Debug logging (Python)
export PYTHONLOGLEVEL=DEBUG
board-cli ready
```

### JSON Output

All commands support `--json` flag for machine-readable output:

```bash
# Query results
board-cli ready --json | jq '.[] | {number, title, priority}'

# Command results
board-cli create "Test" --json | jq '.number'

# Pipe to other tools
board-cli ready --json | jq -r '.[] | .number' | xargs -I {} board-cli claim {} --agent claude
```

---

## Tips & Tricks

### Shell Aliases

Add to `.bashrc` or `.zshrc`:

```bash
alias br='board-cli ready'
alias bc='board-cli claim'
alias bs='board-cli status'
alias bi='board-cli info'
```

### Common Workflows

**Get work and claim:**
```bash
# Get first ready issue and claim it
ISSUE=$(board-cli ready --limit 1 --json | jq -r '.[0].number')
board-cli claim $ISSUE --agent claude
```

**Mark done:**
```bash
board-cli status 123 done
board-cli release 123 --agent claude --reason completed
```

**Check dependencies:**
```bash
board-cli graph 123 | grep "Blocked by"
```

### Automation

**Monitor and auto-claim:**
```bash
#!/bin/bash
while true; do
  board-cli ready --agent myagent --limit 1 --json | \
    jq -r '.[0].number' | \
    xargs -I {} board-cli claim {} --agent myagent
  sleep 60
done
```

**Bulk status update:**
```bash
# Mark all issues in a list as done
cat issues.txt | while read issue; do
  board-cli status $issue done
done
```

---

## See Also

- [Board Integration Guide](board-integration.md)
- [API Reference](API_REFERENCE.md)
- [Architecture Documentation](architecture.md)
- [Examples](../examples/)
