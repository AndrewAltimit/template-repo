# Board Agent Work Action

A reusable GitHub Action for executing AI agent work from a GitHub Projects v2 board.

## Overview

This action enables autonomous AI agents to:

1. Query the GitHub Projects v2 board for ready work
2. Claim issues to prevent conflicts with other agents
3. Execute agent-specific work (Claude, OpenCode, Gemini, Crush, Codex)
4. Create pull requests with the completed work
5. Release claims with appropriate status

## Quick Start

### Using the Composite Action

```yaml
jobs:
  agent-work:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
          token: ${{ secrets.AGENT_TOKEN }}

      - uses: ./.github/actions/board-agent-work
        with:
          github-token: ${{ secrets.AGENT_TOKEN }}
          github-projects-token: ${{ secrets.GITHUB_PROJECTS_TOKEN }}
          agent-name: claude
          board-config-path: ai-agents-board.yml
```

### Using the Reusable Workflow

```yaml
jobs:
  agent-work:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: claude
      board-config-path: ai-agents-board.yml
      max-issues: 1
    secrets:
      github-token: ${{ secrets.AGENT_TOKEN }}
      github-projects-token: ${{ secrets.GITHUB_PROJECTS_TOKEN }}
```

## Inputs

### Required

| Input | Description |
|-------|-------------|
| `github-token` | GitHub token for repository operations |
| `github-projects-token` | Classic token with `project` scope |

### Agent Configuration

| Input | Description | Default |
|-------|-------------|---------|
| `agent-name` | AI agent to use (claude, opencode, gemini, crush, codex) | `claude` |
| `agent-timeout` | Timeout for agent execution in minutes | `30` |

### Board Configuration

| Input | Description | Default |
|-------|-------------|---------|
| `board-config-path` | Path to board config file | `ai-agents-board.yml` |
| `max-issues` | Maximum issues to work on | `1` |

### Label Filtering

| Input | Description | Default |
|-------|-------------|---------|
| `include-labels` | Comma-separated labels to include (only process issues with these labels) | `''` |
| `exclude-labels` | Comma-separated labels to exclude (skip issues with these labels) | `''` |

### Execution Modes

| Input | Description | Default |
|-------|-------------|---------|
| `dry-run` | Query but don't execute (for testing) | `false` |
| `create-pr` | Create PR after work | `true` |

### Observability

| Input | Description | Default |
|-------|-------------|---------|
| `json-logging` | Enable structured JSON logging for log aggregators (Splunk, Datadog, etc.) | `false` |

### Janitor Settings

| Input | Description | Default |
|-------|-------------|---------|
| `stale-claim-threshold` | Hours after which to consider a claim stale and clean it up | `2` |

### Container Configuration

| Input | Description | Default |
|-------|-------------|---------|
| `use-docker` | Use Docker containers for agent execution | `true` |
| `docker-compose-file` | Docker compose file path | `docker-compose.yml` |
| `openrouter-api-key` | API key for OpenCode/Crush agents | - |

## Outputs

### Basic Outputs

| Output | Description |
|--------|-------------|
| `has-work` | Whether work was found on the board |
| `issue-number` | Issue number that was worked on |
| `issue-title` | Title of the issue |
| `work-completed` | Whether the agent completed work |
| `pr-number` | Created PR number |
| `pr-url` | Created PR URL |
| `branch-name` | Branch created for work |

### JSON Summary Output

| Output | Description |
|--------|-------------|
| `summary-json` | JSON summary with processing stats |
| `stale-claims-cleaned` | Number of stale claims cleaned by janitor |

The `summary-json` output contains:
```json
{
  "processed": 1,
  "succeeded": 1,
  "failed": 0,
  "pr_urls": ["https://github.com/owner/repo/pull/123"],
  "agent": "claude",
  "dry_run": false,
  "stale_claims_cleaned": 0,
  "duration_seconds": 180,
  "issue_number": 42,
  "issue_title": "Add feature X",
  "error": ""
}
```

## Supported Agents

| Agent | Execution | Notes |
|-------|-----------|-------|
| `claude` | Local CLI | Requires Claude Code subscription |
| `opencode` | Docker/Local | Uses OpenRouter API |
| `crush` | Docker/Local | Uses OpenRouter API |
| `gemini` | Local CLI | Requires Gemini setup |
| `codex` | Local CLI | Requires Codex auth |

## Board Configuration

Create `ai-agents-board.yml`:

```yaml
project:
  number: 1
  owner: your-username

repository: owner/repo

fields:
  status: "Status"
  priority: "Priority"
  agent: "Agent"

agents:
  enabled_agents:
    - claude
    - opencode
    - crush

work_claims:
  timeout: 86400  # 24 hours
  renewal_interval: 3600
```

## Enterprise Usage

For organizations with multiple agentic workflows:

### 1. Copy the Pattern

Copy `.github/actions/board-agent-work/` and `.github/workflows/board-agent-worker.yml` to your repository.

### 2. Customize for Your Environment

```yaml
# .github/workflows/my-agent-workflow.yml
name: My Agent Pipeline

on:
  schedule:
    - cron: '0 */2 * * *'  # Every 2 hours
  workflow_dispatch:
    inputs:
      agent:
        type: choice
        options: [claude, opencode, crush]

jobs:
  run-agent:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: ${{ inputs.agent || 'claude' }}
      board-config-path: config/agents/board.yml
      max-issues: 3
      agent-timeout: 45
    secrets:
      github-token: ${{ secrets.AGENT_TOKEN }}
      github-projects-token: ${{ secrets.PROJECTS_TOKEN }}
      openrouter-api-key: ${{ secrets.OPENROUTER_KEY }}
```

### 3. Multi-Agent Orchestration

```yaml
# Run multiple agents in parallel
jobs:
  claude-work:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: claude
    secrets: inherit

  opencode-work:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: opencode
    secrets: inherit

  aggregate:
    needs: [claude-work, opencode-work]
    runs-on: ubuntu-latest
    steps:
      - name: Report
        run: |
          echo "Claude: ${{ needs.claude-work.outputs.work-completed }}"
          echo "OpenCode: ${{ needs.opencode-work.outputs.work-completed }}"
```

### 4. Label-Based Filtering

Process only security-related issues:

```yaml
jobs:
  security-work:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: claude
      include-labels: 'security,vulnerability'
      exclude-labels: 'wontfix,duplicate'
    secrets: inherit
```

### 5. JSON Logging for Log Aggregators

Enable structured logging for Splunk, Datadog, or other log aggregators:

```yaml
jobs:
  agent-work:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: claude
      json-logging: true
    secrets: inherit
```

Output format:
```json
{"event": "setup_complete", "python_version": "Python 3.11.0"}
{"event": "config_validated", "path": "ai-agents-board.yml"}
{"event": "agent_start", "agent": "claude", "issue": 42, "timeout_min": 30}
{"event": "agent_complete", "success": true, "duration_sec": 180, "error": ""}
{"event": "pr_created", "pr_number": 123, "pr_url": "https://..."}
```

### 6. Processing Summary JSON

Use the JSON summary output for downstream automation:

```yaml
jobs:
  agent-work:
    uses: ./.github/workflows/board-agent-worker.yml
    with:
      agent-name: claude
    secrets: inherit

  report:
    needs: agent-work
    runs-on: ubuntu-latest
    steps:
      - name: Process results
        run: |
          SUMMARY='${{ needs.agent-work.outputs.summary-json }}'
          echo "$SUMMARY" | jq .

          # Extract specific fields
          PROCESSED=$(echo "$SUMMARY" | jq -r '.processed')
          SUCCEEDED=$(echo "$SUMMARY" | jq -r '.succeeded')
          echo "Processed: $PROCESSED, Succeeded: $SUCCEEDED"
```

## Security

### Token Requirements

| Token | Type | Scopes | Purpose |
|-------|------|--------|---------|
| `github-token` | Fine-grained or Classic | `contents:write`, `issues:write`, `pull-requests:write` | Repository operations |
| `github-projects-token` | Classic (required) | `project`, `repo` | Board operations, claim comments |

### Claim System

The action uses a claim system to prevent race conditions:

1. Before work: Claims the issue with a comment
2. During work: Holds the claim (24h timeout by default)
3. After work: Releases with status (completed/blocked/error)

Other agents cannot work on claimed issues until the claim expires or is released.

### Janitor Pattern

The action includes a built-in janitor that cleans up stale claims before querying for work. This handles cases where:

- A runner crashes mid-execution
- A workflow is cancelled
- Network issues prevent proper claim release

Configure with `stale-claim-threshold` (default: 2 hours). The janitor only cleans claims for the current agent.

### Health Monitoring

Use the health check workflow for monitoring:

```yaml
# Reference the health check workflow
- uses: ./.github/workflows/board-health-check.yml
```

The health check:
- Validates board configuration
- Tests board connectivity
- Reports available agents
- Counts ready work items
- Generates status badges

## Troubleshooting

### "Board configuration file not found"

Ensure `board-config-path` points to a valid YAML file.

### "Failed to claim issue"

The issue may already be claimed by another agent. Wait for the claim to expire (default 24h) or have the owner release it.

### Agent not executing

Check that:
1. The agent CLI is available (for local execution)
2. Docker is available (for containerized execution)
3. Required API keys are set (OpenRouter for OpenCode/Crush)

### No work found

Verify:
1. Issues exist on the board with status "Todo"
2. Issues are assigned to the correct agent
3. Issues have no open blockers

## See Also

- [Agent Security Documentation](../../../docs/agents/security.md)
- [Board Manager README](../../../tools/rust/board-manager/README.md)
- [GitHub Agents CLI README](../../../tools/rust/github-agents-cli/README.md)
- [Health Check Workflow](../../workflows/board-health-check.yml)
- [Scheduled Agent Work Example](../../workflows/scheduled-agent-work.yml)
