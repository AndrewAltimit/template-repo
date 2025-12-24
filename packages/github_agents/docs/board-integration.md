# GitHub Projects v2 Board Integration

## Overview

The GitHub Projects v2 board integration enables agents to use GitHub as an external "memory system" for tracking work, dependencies, and state across sessions. This allows agents to maintain context, discover ready work, and coordinate without conflicts.

### Key Features

- **Agent Memory**: Maintain work context across sessions (survives restarts)
- **Work Discovery**: Query ready work automatically (unblocked tasks)
- **Dependency Tracking**: Blockers, parent-child relationships, priorities
- **Multi-Agent Coordination**: Multiple agents work without conflicts
- **Container-First**: Docker deployment with health checks
- **Zero Deployment**: Uses existing GitHub infrastructure

## Quick Start

### Prerequisites

- GitHub repository with Projects v2 enabled
- GitHub Personal Access Token with `project` and `repo` scopes
- Python 3.11+
- Docker (for containerized deployment)

### 1. Create GitHub Project Board

1. Go to your repository → **Projects** → **New project**
2. Choose **Board** template
3. Note the project number (visible in URL: `github.com/users/{owner}/projects/{number}`)

### 2. Configure Board Fields

Add these custom fields to your project (Settings → Custom fields):

- **Status** (Single select): `Todo`, `In Progress`, `Blocked`, `Done`, `Abandoned`
- **Priority** (Single select): `Critical`, `High`, `Medium`, `Low`
- **Type** (Single select): `Feature`, `Bug`, `Tech Debt`, `Documentation`
- **Agent** (Text): Agent name assigned to issue
- **Blocked By** (Text): Comma-separated issue numbers
- **Discovered From** (Text): Parent issue number
- **Estimated Size** (Single select): `XS`, `S`, `M`, `L`, `XL`

### 3. Configure Agent Settings

Create `ai-agents-board.yml`:

```yaml
# GitHub Project Configuration
project:
  number: 1  # Your project number
  owner: your-username  # GitHub username or org

# Repository
repository: owner/repo

# Custom Field Mappings
fields:
  status: "Status"
  priority: "Priority"
  agent: "Agent"
  type: "Type"
  blocked_by: "Blocked By"
  discovered_from: "Discovered From"
  size: "Estimated Size"

# Enabled Agents
agents:
  enabled_agents:
    - claude
    - opencode
    - gemini
    - crush
    - codex
  auto_discover: true  # Automatically file discovered issues

# Work Claim Settings
work_claims:
  timeout: 86400  # 24 hours
  renewal_interval: 3600  # 1 hour

# Work Queue Filters
work_queue:
  exclude_labels:
    - "wontfix"
    - "duplicate"
  priority_labels:
    Critical:
      - "critical"
      - "p0"
    High:
      - "high"
      - "p1"

# Integration Settings
integration:
  auto_claim_on_issue_trigger: true  # Claim when [Approved][Agent] used
  auto_update_on_pr_merge: true      # Mark Done when PR merges
  auto_discover_blockers: true        # File blockers as issues

# Logging
logging:
  level: "INFO"
  include_graphql_queries: false
```

### 4. Set Environment Variables

**Important**: GitHub Projects v2 requires a **classic token** with `project` scope. Fine-grained tokens do not work with the Projects v2 GraphQL API.

```bash
# For GitHub Projects v2 (classic token with 'project' and 'repo' scopes)
export GITHUB_PROJECTS_TOKEN=your_classic_github_token

# For repository operations (can be fine-grained or classic token)
export GITHUB_TOKEN=your_github_token

# Repository configuration
export GITHUB_REPOSITORY=owner/repo
export GITHUB_PROJECT_NUMBER=2
```

**Token Scope Requirements:**

| Token | Type | Required Scopes | Purpose |
|-------|------|-----------------|---------|
| `GITHUB_PROJECTS_TOKEN` | Classic | `project`, `repo` (or `public_repo` for public repos only) | Board operations + claim comments |
| `GITHUB_TOKEN` | Fine-grained or Classic | `contents:write`, `issues:write`, `pull_requests:write` | Repository operations |

**Why does GITHUB_PROJECTS_TOKEN need `repo` scope?**

The claim system posts comments to issues to coordinate work between agents:
- Claim comments prevent multiple agents from working on the same issue
- Renewal comments track that work is still in progress
- Release comments signal work completion

Without these comments, agents can't coordinate and you'd have race conditions. For private repositories, the classic token requires full `repo` scope to post issue comments via GraphQL.

**Why Two Tokens?**

GitHub Projects v2 uses GraphQL API which only accepts classic tokens. For better security, you can:
- Use a classic token with minimal scopes for board operations (`GITHUB_PROJECTS_TOKEN`)
- Use a fine-grained token with specific repository permissions for code operations (`GITHUB_TOKEN`)

If you only set `GITHUB_TOKEN`, the system will use it for both operations (backward compatible).

### 5. Start Using the Board

#### Option A: CLI Tool

```bash
# Install package
pip install -e packages/github_agents[board]

# Query ready work
board-cli ready --limit 10

# Claim an issue
board-cli claim 123 --agent claude

# Update status
board-cli status 123 in-progress

# View dependency graph
board-cli graph 123

# Release work
board-cli release 123 --agent claude --reason completed
```

#### Option B: Python API

```python
from github_agents.board.config import BoardConfig
from github_agents.board.manager import BoardManager
from github_agents.board.models import IssueStatus

# Initialize
config = BoardConfig.from_file("ai-agents-board.yml")
manager = BoardManager(config=config, github_token="your_token")
await manager.initialize()

# Get ready work
issues = await manager.get_ready_work(agent_name="claude", limit=5)

# Claim work
session_id = "unique-session-id"
await manager.claim_work(issue.number, "claude", session_id)

# Update status
await manager.update_status(issue.number, IssueStatus.IN_PROGRESS)

# Release work
await manager.release_work(issue.number, "claude", "completed")
```

#### Option C: Docker Container

```bash
# Start MCP server
docker-compose up -d mcp-github-board

# Check health
curl http://localhost:8021/health

# View logs
docker-compose logs -f mcp-github-board
```

#### Option D: MCP Tools (via Claude Code)

The board is accessible through MCP tools in Claude Code:

```
Available tools:
- query_ready_work: Get unblocked issues ready to work on
- claim_work: Claim an issue for implementation
- renew_claim: Extend claim for long tasks
- release_work: Release claim (completed/blocked/abandoned/error)
- update_status: Change issue status
- add_blocker: Add blocking dependency
- mark_discovered_from: Mark parent-child relationship
- get_issue_details: Get full issue context
- get_dependency_graph: Get dependency graph
- list_agents: Get enabled agents
- get_board_config: Get current configuration
```

## Core Concepts

### Work States

Issues flow through these states:

1. **Todo**: Ready to be claimed
2. **In Progress**: Actively being worked on
3. **Blocked**: Waiting on dependencies
4. **Done**: Completed successfully
5. **Abandoned**: No longer pursued

### Claim System

**Claiming Work**: When an agent claims an issue, it:
- Adds a comment with agent name and session ID
- Sets a 24-hour timeout (configurable)
- Prevents other agents from claiming
- Tracks when the claim was made

**Claim Renewal**: For long-running tasks:
- Agents can renew claims (extends timeout)
- Default renewal interval: 1 hour
- Prevents claim expiration during active work

**Releasing Work**: When done, agents release with a reason:
- `completed`: Work finished successfully
- `blocked`: Hit a blocker, needs another issue resolved first
- `abandoned`: Decided not to pursue
- `error`: Encountered an error during implementation

### Dependencies

**Blockers**: Issue A is blocked by Issue B
- A cannot be worked until B is resolved
- Agents query for "ready work" (no open blockers)
- Supports transitive dependencies

**Parent-Child**: Issue B was discovered while working on A
- Tracks work provenance
- Enables epic/story hierarchies
- Helps with context reconstruction

### Ready Work Algorithm

The board determines "ready work" by filtering for issues that are:
1. Status is `Todo` or `Blocked` (but blockers resolved)
2. Not claimed by another agent (or claim expired)
3. Have no open blocker dependencies
4. Match agent filter (if specified)
5. Not excluded by label filters

## Common Workflows

### Workflow 1: Agent Discovers New Work

```python
# Agent working on issue #100
current_issue = 100

# Discovers a blocker while implementing
blocker_issue = await manager.create_issue_with_metadata(
    title="Fix broken test in test_utils.py",
    body="Found while implementing #100",
    type=IssueType.BUG,
    priority=IssuePriority.HIGH
)

# Mark relationship
await manager.mark_discovered_from(blocker_issue.number, current_issue)

# Add as blocker
await manager.add_blocker(current_issue, blocker_issue.number)

# Release current work as blocked
await manager.release_work(current_issue, "claude", "blocked")
```

### Workflow 2: Multi-Session Implementation

**Session 1** (Agent starts work):
```python
# Query ready work
issues = await manager.get_ready_work(agent_name="claude", limit=1)
issue = issues[0]

# Claim work
session_id = "session-abc-123"
await manager.claim_work(issue.number, "claude", session_id)

# Start implementation...
# (Session times out after 15 minutes)
```

**Session 2** (Agent continues):
```python
# Query work (will see the claimed issue with expired claim)
issues = await manager.get_ready_work(agent_name="claude", limit=1)

# Re-claim with new session
new_session_id = "session-def-456"
await manager.claim_work(issue.number, "claude", new_session_id)

# Continue implementation...
# Mark as done
await manager.release_work(issue.number, "claude", "completed")
```

### Workflow 3: Concurrent Agents

**Agent 1** (Claude):
```python
# Get ready work for Claude
issues = await manager.get_ready_work(agent_name="claude", limit=5)
# Works on assigned issues
```

**Agent 2** (OpenCode):
```python
# Get ready work for OpenCode
issues = await manager.get_ready_work(agent_name="opencode", limit=5)
# Gets different issues - no conflicts!
```

**Agent 3** (Generic work picker):
```python
# Get any ready work
issues = await manager.get_ready_work(limit=10)
# First agent to claim wins
```

### Workflow 4: Monitor Integration

The issue monitor automatically integrates with the board:

```python
# When [Approved][OpenCode] is detected:
# 1. Board manager claims the issue
# 2. Sets status to "In Progress"
# 3. Agent implements changes
# 4. Creates PR
# 5. Board manager releases work as "completed"
```

## CLI Reference

### Ready Work

```bash
# Get all ready work
board-cli ready

# Filter by agent
board-cli ready --agent claude

# Filter by priority
board-cli ready --priority high

# Limit results
board-cli ready --limit 5

# JSON output
board-cli ready --json
```

### Create Issues

```bash
# Basic issue
board-cli create "Fix bug in parser"

# With metadata
board-cli create "Add dark mode" \
  --type feature \
  --priority high \
  --agent claude \
  --size m \
  --body "Implement dark mode toggle in settings"
```

### Manage Dependencies

```bash
# Add blocker
board-cli block 123 --blocked-by 456

# View dependency graph
board-cli graph 123

# View with depth
board-cli graph 123 --depth 5
```

### Update Status

```bash
# Update status
board-cli status 123 in-progress

# Update status and assign agent
board-cli status 123 in-progress --agent claude
```

### Claim Management

```bash
# Claim work
board-cli claim 123 --agent claude

# Release work
board-cli release 123 --agent claude --reason completed

# Release as blocked
board-cli release 123 --agent claude --reason blocked

# Release as abandoned
board-cli release 123 --agent claude --reason abandoned
```

### Issue Details

```bash
# Get full issue info
board-cli info 123

# JSON output
board-cli info 123 --json
```

## Performance

### Benchmarks

Based on testing with real GitHub Projects API:

- **Query ready work (50 issues)**: <5 seconds
- **Claim work**: <2 seconds (includes comment creation)
- **Update status**: <1 second
- **Dependency graph (depth 3)**: <3 seconds

### Optimization Tips

1. **Limit queries**: Use `limit` parameter to reduce API calls
2. **Agent filtering**: Filter by agent to reduce result set
3. **Cache results**: BoardManager maintains internal cache
4. **Batch operations**: Group related operations in same session

### Rate Limiting

GitHub GraphQL API limits:
- **5,000 points per hour**
- Complex queries cost more points
- BoardManager implements exponential backoff
- Retry logic for transient failures

## Troubleshooting

### Common Issues

#### "Board not found" error

**Problem**: `BoardNotFoundError: Project {number} not found`

**Solution**:
1. Verify project number in URL
2. Check token has `project` scope
3. Ensure token has access to project
4. Verify `owner` in config matches project owner

#### "GraphQL error: Field not found"

**Problem**: Custom field doesn't exist on board

**Solution**:
1. Check field names match exactly (case-sensitive)
2. Add missing fields in project settings
3. Update field mappings in config

#### Claims not expiring

**Problem**: Old claims still blocking work

**Solution**:
1. Check `work_claims.timeout` in config
2. Verify system time is correct
3. Manually release stale claims:
   ```bash
   board-cli release <issue> --agent <agent> --reason abandoned
   ```

#### Rate limiting errors

**Problem**: `RateLimitError: GitHub API rate limit exceeded`

**Solution**:
1. Reduce query frequency
2. Use smaller `limit` values
3. Wait for rate limit reset (shown in error)
4. Consider using GitHub Actions token (higher limits)

### Debug Logging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or in config:

```yaml
logging:
  level: "DEBUG"
  include_graphql_queries: true
```

## Best Practices

### For Agents

1. **Always claim before working**: Prevents conflicts
2. **Renew long-running claims**: Every hour for tasks >1 hour
3. **Release promptly**: Don't leave claims hanging
4. **Use appropriate reasons**: Helps track what happened
5. **File discovered issues**: Don't lose track of problems found

### For Humans

1. **Use descriptive titles**: Agents need context
2. **Add priorities**: Helps agents choose important work
3. **Set up dependencies**: Mark blockers explicitly
4. **Review agent work**: Check board regularly
5. **Clean up stale issues**: Archive completed work

### For Repository Setup

1. **One board per repository**: Simplifies configuration
2. **Consistent field names**: Follow conventions
3. **Document workflow**: Add board README
4. **Test with small tasks first**: Validate setup
5. **Monitor agent behavior**: Watch for issues

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│          Agents Layer                │
│  (Claude, OpenCode, Gemini, Crush)      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Board Integration MCP Server       │
│  - 11 core tools                        │
│  - Port 8021 (HTTP) or STDIO            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         BoardManager (Core)             │
│  - GraphQL client                       │
│  - Claim management                     │
│  - Dependency tracking                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      GitHub Projects v2 API             │
│  (GraphQL)                              │
└─────────────────────────────────────────┘
```

### Data Models

**Issue**: Represents a tracked work item
- Core fields: number, title, body, state, status
- Metadata: priority, type, size, agent
- Relationships: blocked_by, discovered_from
- Timestamps: created_at, updated_at

**AgentClaim**: Represents agent ownership
- Fields: issue_number, agent, session_id, timestamp
- Methods: is_expired(), age_seconds(), renewal

**BoardConfig**: Configuration for board integration
- Project settings: number, owner, repository
- Field mappings: Custom field name mappings
- Agent settings: enabled agents, auto-discover
- Work settings: timeout, renewal interval

**DependencyGraph**: Issue relationships
- Root issue
- Blocks: Issues this blocks
- Blocked by: Issues blocking this
- Children: Discovered sub-issues
- Parent: Where this was discovered from

## Integration with Monitors

### Issue Monitor

When an issue has `[Approved][Agent]` trigger:

1. **Before implementation**:
   - Check if board config exists
   - Claim work with session ID
   - Update status to "In Progress"

2. **During implementation**:
   - Renew claim periodically
   - Track discovered issues
   - Add blockers as needed

3. **After implementation**:
   - Create PR with changes
   - Release work as "completed"
   - Link PR in issue comment

4. **On error**:
   - Release work as "error"
   - Add error details to issue

### PR Monitor

When a PR is merged:

1. **Extract linked issues** from PR body:
   - Looks for `Closes #N`, `Fixes #N`, `Resolves #N`
   - Supports multiple issues

2. **Update board**:
   - Set status to "Done"
   - Add completion comment
   - Update timestamps

## Security

### Access Control

- **GitHub token required**: Full repo + project access
- **User authorization**: Only approved users trigger agents
- **Commit validation**: Prevents code injection
- **Rate limiting**: Prevents API abuse

### Best Practices

1. **Use fine-grained tokens**: Limit scope to specific repo/project
2. **Rotate tokens regularly**: Set expiration dates
3. **Store securely**: Use environment variables or secrets
4. **Audit logs**: GitHub tracks all GraphQL operations
5. **Review permissions**: Verify token has minimum required scopes

## Future Enhancements

Potential additions (not currently implemented):

- **Multi-repository boards**: Track work across multiple repos
- **Cross-project dependencies**: Link issues across projects
- **Analytics dashboard**: Visualize agent productivity
- **Custom workflows**: Define state transitions
- **Webhook integration**: Real-time updates
- **Board templates**: Pre-configured board setups
- **Caching layer**: Reduce API calls
- **Offline mode**: Work without network
- **Search functionality**: Full-text issue search
- **Bulk operations**: Update multiple issues at once

## Testing

The board integration has comprehensive test coverage:

### Unit Tests

```bash
# Run all board-related unit tests
pytest tests/unit/test_board_manager.py -v
pytest tests/unit/test_board_cli.py -v
pytest tests/unit/test_monitor_board_integration.py -v
```

### Robustness Tests

**Concurrency Tests** (`test_concurrency.py`):
- Simultaneous claim attempts (2 and 4 agents)
- Claim expiration under concurrent access
- Claim renewal safety
- Work selection with multiple agents

**Failure Recovery Tests** (`test_failure_recovery.py`):
- Claim expiration detection and recovery
- Network failure handling with retries
- Partial operation failures (claim posted but status update fails)
- Agent crash recovery scenarios
- Claim comment parsing robustness

```bash
# Run robustness tests
pytest tests/unit/test_concurrency.py -v
pytest tests/unit/test_failure_recovery.py -v
```

### End-to-End Tests

```bash
# Run E2E tests (requires GitHub token)
pytest tests/e2e/test_board_workflow.py -v
```

### Coverage

The board module maintains >90% test coverage on critical paths:
- Claim/release/renewal operations: 100%
- Dependency management: 100%
- Error handling: 100%
- Race condition prevention: 100%

## See Also

- [MCP Server Documentation](../../../tools/mcp/mcp_github_board/docs/README.md)
- [API Reference](API_REFERENCE.md)
- [CLI Reference](CLI_REFERENCE.md)
- [Architecture Documentation](architecture.md)
