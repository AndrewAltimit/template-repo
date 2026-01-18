# board-manager

GitHub Projects v2 board manager for AI agent coordination via GraphQL API.

## Overview

`board-manager` provides CLI commands for managing AI agent work on GitHub issues through the Projects v2 API. It handles work claiming, status updates, dependency tracking, and comment trust bucketing.

## Installation

```bash
# Build from source
cd tools/rust/board-manager
cargo build --release

# Binary available at target/release/board-manager
```

## Commands

| Command | Description |
|---------|-------------|
| `ready` | Query ready (unblocked, unclaimed) work from the board |
| `claim` | Claim an issue for implementation |
| `renew` | Renew an active claim for long-running tasks |
| `release` | Release claim on an issue (completed, blocked, abandoned, error) |
| `status` | Update issue status (Todo, In Progress, Blocked, Done, Abandoned) |
| `block` | Add blocking dependency between issues |
| `discover-from` | Mark parent-child relationship between issues |
| `info` | Get full details for a specific issue |
| `agents` | List enabled agents from configuration |
| `config` | Show board configuration |
| `assess-fix` | Assess whether a fix should be auto-applied |
| `bucket-comments` | Bucket comments by trust level (stdin JSON input) |

## Usage Examples

```bash
# Query ready work for an agent
board-manager ready --agent claude --limit 5

# Claim an issue
board-manager claim 123 --agent claude --session "session-abc"

# Update status
board-manager status 123 --status "In Progress"

# Release with reason
board-manager release 123 --agent claude --reason completed

# Bucket comments by trust level (pipe JSON via stdin)
echo '[{"author":"admin","body":"LGTM","createdAt":"2024-01-01T00:00:00Z"}]' | board-manager bucket-comments
```

## Configuration

Requires `.agents.yaml` in the repository root with:
- `board.project_number` - GitHub Projects v2 project number
- `security.agent_admins` - Users with highest trust level
- `security.trusted_sources` - Users with medium trust level
- `enabled_agents` - List of agents allowed to claim work

## Environment Variables

- `GITHUB_TOKEN` - GitHub API token with project access
- `GITHUB_REPOSITORY` - Repository in `owner/repo` format

## See Also

- [GitHub Agents CLI](../github-agents-cli/README.md) - Full-featured agent CLI
- [Board Agent Work Action](../../../.github/actions/board-agent-work/README.md) - GitHub Action wrapper
