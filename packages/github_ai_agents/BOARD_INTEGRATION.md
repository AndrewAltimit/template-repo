# GitHub Project Board Integration - Product Requirements Document

## Executive Summary

This PRD defines the integration of GitHub Projects v2 board management into the `github_ai_agents` package, enabling AI agents to use GitHub as an external "memory system" for tracking work, dependencies, and state across sessions. Inspired by Steve Yegge's Beads project, this solution uses GitHub's existing infrastructure instead of a custom git-backed database, allowing agents to maintain context, discover work, and coordinate across multiple sessions and machines.

## Problem Statement

### The Agent Memory Problem

Current AI coding agents face several critical challenges:

1. **Session Amnesia**: Agents lose context between sessions (typically every 10-15 minutes), leading to:
   - Forgotten work items and priorities
   - Lost dependency tracking
   - Repeated discovery of the same issues
   - Incomplete multi-phase implementations

2. **Lost Discovered Work**: When agents encounter issues during implementation (broken tests, missing dependencies, tech debt), they either:
   - Ignore the problems due to context constraints
   - Mention them once and forget
   - Never record them for future action

3. **Poor Long-Horizon Planning**: Agents struggle with nested work that requires:
   - Multiple sessions to complete
   - Tracking blockers and dependencies
   - Coordinating between multiple agents
   - Maintaining priority across evolving requirements

4. **No Cross-Agent Coordination**: Multiple agents working on the same repository cannot:
   - See what others are working on
   - Avoid duplicate work
   - Understand blocking relationships
   - Share discovered issues

### Why Not Use Beads?

While Beads is innovative, it has limitations for our use case:

- **Local-First Design**: Beads uses a git-backed JSONL format, requiring agents to manage merge conflicts
- **CLI-Only Interface**: No API for programmatic access by multiple agent types
- **Single Repository Focus**: Doesn't leverage existing GitHub infrastructure
- **Duplication**: Creates a parallel system alongside GitHub Issues

### Why GitHub Projects v2?

GitHub Projects v2 provides:

- **Centralized State**: True multi-agent coordination without merge conflicts
- **Rich Metadata**: Custom fields, status tracking, dependencies
- **Built-in UI**: Human visibility into agent work without custom tooling
- **GraphQL API**: Programmatic access for all operations
- **Integration**: Links naturally to issues, PRs, and repositories
- **Persistence**: External to repository, survives across machines and repos

## Goals

### Primary Goals

1. **Agent Memory System**: Enable agents to maintain work context across sessions
2. **Work Discovery**: Allow agents to query for "ready" work (unblocked tasks)
3. **Dependency Tracking**: Support blockers, parent-child relationships, and priorities
4. **Multi-Agent Coordination**: Enable multiple agents to work without conflicts
5. **Zero Deployment Overhead**: Use existing GitHub infrastructure

### Secondary Goals

1. **MCP Server Integration**: Expose board operations as MCP tools for any agent
2. **Container-First**: Follow template-repo philosophy with Docker deployment
3. **Human Visibility**: Provide web UI through GitHub Projects interface
4. **Backward Compatible**: Integrate seamlessly with existing `github_ai_agents` monitors

## Non-Goals

- Custom issue tracker implementation (use GitHub Issues)
- Git-backed storage system (use GitHub's database)
- Beads CLI compatibility (design for our specific needs)
- Support for non-GitHub platforms (GitHub-only initially)

## Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agents Layer                      │
│  (Claude, OpenCode, Gemini, Crush, Issue/PR Monitors)  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Board Integration MCP Server               │
│    - Query ready work                                   │
│    - Create/update issues with metadata                │
│    - Manage dependencies (blocks, blocked-by)          │
│    - Track agent assignments                            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              GitHub Projects v2 GraphQL API             │
│    - Project boards with custom fields                 │
│    - Issue relationships                                │
│    - Status workflow automation                         │
└─────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. Board Manager Core (`src/github_ai_agents/board/manager.py`)

**Responsibilities**:
- GitHub Projects v2 GraphQL API client
- CRUD operations for project items
- Dependency management (blocks, parent-child)
- Work queue queries (ready, blocked, in-progress)

**Key Methods**:
```python
class BoardManager:
    # Work queue management
    async def get_ready_work(self, agent_name: Optional[str] = None) -> List[Issue]
    async def claim_work(self, issue_number: int, agent_name: str, session_id: str) -> bool
    async def renew_claim(self, issue_number: int, agent_name: str, session_id: str) -> bool
    async def release_work(self, issue_number: int, agent_name: str, reason: str) -> bool

    # Issue creation and metadata
    async def create_issue_with_metadata(self, title: str, body: str, **metadata) -> Issue
    async def update_status(self, issue_id: str, status: str) -> bool
    async def assign_to_agent(self, issue_id: str, agent_name: str) -> bool

    # Dependency management
    async def add_blocker(self, issue_id: str, blocker_id: str) -> bool
    async def mark_discovered_from(self, issue_id: str, parent_id: str) -> bool
    async def get_dependency_graph(self, issue_id: str) -> Graph

    # Background tasks (optional)
    async def notify_expired_claims(self) -> None  # Informational only
```

#### 2. MCP Server (`tools/mcp/github_board/server.py`)

**Port**: 8021 (following existing MCP server pattern)

**MCP Tools**:
- `query_ready_work`: Get unblocked, ready-to-work issues
- `claim_work`: Claim an issue for implementation (posts comment with timestamp)
- `renew_claim`: Renew claim for long-running tasks (extends timeout)
- `release_work`: Release claim on an issue (completed/blocked/abandoned)
- `create_tracked_issue`: Create issue with board metadata
- `add_dependency`: Link issues with blocker/parent relationships
- `update_issue_status`: Change status (todo, in_progress, done, blocked)
- `assign_issue`: Assign to agent or unassign
- `record_discovered_work`: File issue discovered during other work
- `get_issue_context`: Get full context for an issue (dependencies, history, claims)
- `search_board_issues`: Search with filters (status, priority, agent)

**Example Tool Definition**:
```python
"query_ready_work": {
    "description": "Get unblocked work items ready for implementation",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Filter by assigned agent (optional)"
            },
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Minimum priority level"
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of items to return"
            }
        }
    }
}
```

#### 3. Integration with Existing Monitors

**Issue Monitor Enhancement** (`src/github_ai_agents/monitors/issue.py`):
- Auto-add approved issues to project board
- Link to parent epics when creating PRs
- Record discovered issues during implementation

**PR Monitor Enhancement** (`src/github_ai_agents/monitors/pr.py`):
- Update board status when PR is created
- Mark issues complete when PR merges
- Discover and file new issues from review feedback

#### 4. Board Configuration (`src/github_ai_agents/board/config.py`)

**Custom Fields for GitHub Project**:
- `Agent`: Which AI agent is assigned
- `Priority`: Critical, High, Medium, Low
- `Type`: Feature, Bug, Tech Debt, Documentation
- `Blocked By`: Comma-separated issue numbers
- `Discovered From`: Parent issue that surfaced this work
- `Estimated Size`: XS, S, M, L, XL
- `Status`: Todo, In Progress, Blocked, Done, Abandoned

**Configuration File** (`.github/ai-agents-board.yml`):
```yaml
# GitHub Project Board Configuration for AI Agents
project:
  # Project number or URL
  number: 1
  # Organization or user
  owner: AndrewAltimit

# Custom field mappings
fields:
  status: "Status"
  priority: "Priority"
  agent: "Agent"
  type: "Type"
  blocked_by: "Blocked By"
  discovered_from: "Discovered From"
  size: "Estimated Size"

# Agent behavior configuration
agents:
  # Auto-file discovered issues
  auto_discover: true
  # Agents to use board for work queues
  enabled_agents:
    - claude
    - opencode
    - gemini
    - crush

# Work queue filters
work_queue:
  # Don't show issues with these labels
  exclude_labels:
    - wontfix
    - duplicate
  # Auto-prioritize based on labels
  priority_labels:
    critical: [security, outage, critical-bug]
    high: [bug, regression]
    medium: [enhancement, feature]
    low: [documentation, cleanup]
```

#### 5. CLI Tool (`src/github_ai_agents/board/cli.py`)

Similar to Beads' `bd` command, provide a CLI for human interaction:

```bash
# Query ready work
github-board ready --agent claude --limit 5

# Create tracked issue
github-board create "Fix authentication bug" \
  --type bug \
  --priority high \
  --body "Description..."

# Add dependency
github-board block 123 --blocked-by 122

# Update status
github-board status 123 in-progress --agent claude

# View dependency graph
github-board graph 123 --depth 3
```

#### 6. Docker Integration

**Dockerfile** (`docker/github-board.Dockerfile`):
```dockerfile
FROM python:3.11-slim

# Install dependencies
COPY config/python/requirements-github-board.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-github-board.txt

# Copy source
COPY packages/github_ai_agents /app/github_ai_agents
COPY tools/mcp/github_board /app/tools/mcp/github_board
COPY tools/mcp/core /app/tools/mcp/core

WORKDIR /app

# Run MCP server
CMD ["python", "-m", "tools.mcp.github_board.server", "--mode", "http"]
```

**docker-compose.yml addition**:
```yaml
  mcp-github-board:
    build:
      context: .
      dockerfile: docker/github-board.Dockerfile
    container_name: mcp-github-board
    user: "${USER_ID:-1000}:${GROUP_ID:-1000}"
    ports:
      - "8021:8021"
    volumes:
      - ./:/app:ro
    environment:
      - PYTHONUNBUFFERED=1
      - PORT=8021
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPOSITORY=${GITHUB_REPOSITORY}
    networks:
      - mcp-network
    command: ["python", "-m", "tools.mcp.github_board.server", "--mode", "http"]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8021/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
    profiles:
      - services
```

## Implementation Plan

### Phase 1: Foundation & GraphQL Client

**Deliverables**:
1. GitHub Projects v2 GraphQL client wrapper
2. Basic CRUD operations for project items
3. Error handling with exponential backoff retry
4. Rate limit monitoring and handling
5. Configuration file parser
6. Comprehensive unit tests with mocked GraphQL responses
7. Structured logging implementation
8. **[NEW from REFINE.md] Documentation structure setup**
   - Create `docs/INDEX.md` with navigation
   - Create `docs/QUICK_START.md`
   - Create `docs/INSTALLATION.md`
9. **[NEW from REFINE.md] Test infrastructure**
   - Reorganize `tests/` into `unit/`, `integration/`, `e2e/`
   - Create `tests/conftest.py` with shared fixtures
   - Create `tests/README.md`

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/board/__init__.py`
- `packages/github_ai_agents/src/github_ai_agents/board/manager.py`
- `packages/github_ai_agents/src/github_ai_agents/board/config.py`
- `packages/github_ai_agents/src/github_ai_agents/board/models.py`
- `packages/github_ai_agents/src/github_ai_agents/board/errors.py`
- `packages/github_ai_agents/tests/unit/test_board_manager.py` *(reorganized)*
- `packages/github_ai_agents/tests/unit/test_error_handling.py` *(reorganized)*
- `packages/github_ai_agents/tests/conftest.py` *(new)*
- `packages/github_ai_agents/tests/README.md` *(new)*
- `packages/github_ai_agents/docs/INDEX.md` *(new)*
- `packages/github_ai_agents/docs/QUICK_START.md` *(new)*
- `packages/github_ai_agents/docs/INSTALLATION.md` *(new)*

**Critical Focus**: Robust error handling and retry logic + Test infrastructure setup

### Phase 2: Claim System & Dependencies

**Deliverables**:
1. Comment-based claim/release mechanism
2. Claim renewal (heartbeat) for long-running tasks
3. Timestamp-based expiration checking
4. Blocker relationship management
5. Parent-child (epic) relationships
6. "Discovered from" tracking
7. Dependency graph queries
8. Ready work detection algorithm
9. Race condition testing

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/board/claims.py`
- `packages/github_ai_agents/src/github_ai_agents/board/dependencies.py`
- `packages/github_ai_agents/src/github_ai_agents/board/queries.py`
- `packages/github_ai_agents/tests/test_claims.py`
- `packages/github_ai_agents/tests/test_dependencies.py`
- `packages/github_ai_agents/tests/test_race_conditions.py`

**Critical Focus**: Claim renewal mechanism and race condition handling

### Phase 3: MCP Server

**Deliverables**:
1. MCP server implementation
2. All 11 core tools (including renew_claim)
3. HTTP mode support
4. Health checks and error handling
5. Integration tests with test repository
6. **[NEW from REFINE.md] Examples overhaul**
   - Create comprehensive `examples/README.md`
   - Create `examples/basic_usage.py`, `examples/issue_monitor_example.py`, `examples/pr_monitor_example.py`
   - Move TTS examples to `examples/tts/`
   - Create `examples/board_integration_example.py`

**Files**:
- `tools/mcp/github_board/__init__.py`
- `tools/mcp/github_board/server.py`
- `tools/mcp/github_board/docs/README.md`
- `tools/mcp/github_board/docs/CLAIM_MECHANISM.md`
- `tools/mcp/github_board/scripts/test_server.py`
- `packages/github_ai_agents/examples/README.md` *(new)*
- `packages/github_ai_agents/examples/basic_usage.py` *(new)*
- `packages/github_ai_agents/examples/issue_monitor_example.py` *(new)*
- `packages/github_ai_agents/examples/pr_monitor_example.py` *(new)*
- `packages/github_ai_agents/examples/board_integration_example.py` *(new)*
- `packages/github_ai_agents/examples/tts/*` *(reorganized)*

### Phase 4: Monitor Integration & GitHub Actions

**Deliverables**:
1. Issue monitor auto-board addition
2. PR monitor status updates
3. Discovered work auto-filing
4. Agent assignment automation
5. GitHub Actions workflows
6. Integration with existing agents (Claude, OpenCode, Gemini, Crush)

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/monitors/issue.py` (updates)
- `packages/github_ai_agents/src/github_ai_agents/monitors/pr.py` (updates)
- `.github/workflows/agent-board-integration.yml`
- `.github/ai-agents-board.yml`
- `packages/github_ai_agents/tests/test_monitor_board_integration.py`

### Phase 5: CLI, Docker & Testing

**Deliverables**:
1. CLI tool for human interaction
2. Docker container setup
3. docker-compose integration
4. End-to-end testing
5. Performance testing (500+ issues)
6. CI/CD pipeline updates

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/board/cli.py`
- `docker/github-board.Dockerfile`
- `config/python/requirements-github-board.txt`
- `docker-compose.yml` (updates)
- `.github/workflows/test-github-board.yml`
- `packages/github_ai_agents/tests/e2e/test_board_e2e.py` *(reorganized)*

### Phase 6: Documentation, Tooling & Polish

**Deliverables**:

1. **Documentation** (incorporating REFINE.md structure):
   - `docs/INDEX.md` - Central documentation hub *(completed in Phase 1)*
   - `docs/QUICK_START.md` - 5-minute guide *(completed in Phase 1)*
   - `docs/INSTALLATION.md` - Detailed setup *(completed in Phase 1)*
   - `docs/API_REFERENCE.md` - Complete API reference
   - `docs/CLI_REFERENCE.md` - Command reference
   - `docs/board-integration.md` - Board usage guide
   - `docs/board-troubleshooting.md` - Troubleshooting
   - `docs/board-performance.md` - Performance tuning
   - Update `CLAUDE.md` with board usage

2. **Examples** (incorporating REFINE.md):
   - `examples/README.md` - Comprehensive examples guide *(completed in Phase 3)*
   - `examples/basic_usage.py` *(completed in Phase 3)*
   - `examples/issue_monitor_example.py` *(completed in Phase 3)*
   - `examples/pr_monitor_example.py` *(completed in Phase 3)*
   - `examples/board_integration_example.py` *(completed in Phase 3)*
   - `examples/multi_agent_example.py`
   - `examples/custom_agent_example.py`
   - `examples/github_actions_example.yml`
   - `examples/security_example.py`
   - `examples/tts/` - TTS examples subdirectory *(reorganized in Phase 3)*

3. **Tooling & Scripts**:
   - `bin/` directory with executable wrappers (`issue-monitor`, `pr-monitor`, `board-cli`)
   - `bin/README.md`
   - `CHANGELOG.md` following Keep a Changelog format
   - `TODO.md` development roadmap

4. **pyproject.toml Updates** (incorporating REFINE.md):
   - Update `line-length`: 120 → 127 (consistency with other packages)
   - Update `requires-python`: ">=3.11"
   - Add optional dependency groups: `[board]`, `[tts]`, `[mcp]`, `[all]`
   - Add package data for configs and templates
   - Update `tool.black.target-version` to `py311`
   - Add `tool.flake8` config with `max-line-length = 127`

**Files**:
- `packages/github_ai_agents/docs/API_REFERENCE.md` *(new)*
- `packages/github_ai_agents/docs/CLI_REFERENCE.md` *(new)*
- `packages/github_ai_agents/docs/board-integration.md` *(new)*
- `packages/github_ai_agents/docs/board-troubleshooting.md` *(new)*
- `packages/github_ai_agents/docs/board-performance.md` *(new)*
- `packages/github_ai_agents/examples/multi_agent_example.py` *(new)*
- `packages/github_ai_agents/examples/custom_agent_example.py` *(new)*
- `packages/github_ai_agents/examples/github_actions_example.yml` *(new)*
- `packages/github_ai_agents/examples/security_example.py` *(new)*
- `packages/github_ai_agents/bin/README.md` *(new)*
- `packages/github_ai_agents/bin/issue-monitor` *(new)*
- `packages/github_ai_agents/bin/pr-monitor` *(new)*
- `packages/github_ai_agents/bin/board-cli` *(new)*
- `packages/github_ai_agents/CHANGELOG.md` *(new)*
- `packages/github_ai_agents/TODO.md` *(new)*
- `packages/github_ai_agents/pyproject.toml` *(updates)*
- `CLAUDE.md` *(updates)*

**Note**: This solution is designed for integration with existing GitHub Projects boards. Agents work with manually-configured boards that humans set up in advance. Documentation will provide guidance on required custom fields and board structure, but no automated project creation is included.

## Technical Specifications

### GitHub Projects v2 GraphQL Schema

**Key Queries**:

```graphql
# Get project with items
query GetProject($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      items(first: 100) {
        nodes {
          id
          content {
            ... on Issue {
              number
              title
              state
              body
            }
          }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldTextValue {
                field { ... on ProjectV2Field { name } }
                text
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2Field { name } }
                name
              }
            }
          }
        }
      }
    }
  }
}
```

**Key Mutations**:

```graphql
# Add issue to project
mutation AddProjectV2Item($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {
    projectId: $projectId
    contentId: $contentId
  }) {
    item { id }
  }
}

# Update custom field
mutation UpdateProjectV2ItemField(
  $projectId: ID!
  $itemId: ID!
  $fieldId: ID!
  $value: String!
) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $projectId
    itemId: $itemId
    fieldId: $fieldId
    value: { text: $value }
  }) {
    projectV2Item { id }
  }
}
```

### Dependency Model

**Types of Dependencies**:

1. **Blocks**: Hard blocker preventing work
   - Issue A blocks Issue B → B cannot start until A is done
   - Stored in "Blocked By" custom field
   - Used for ready-work detection

2. **Parent-Child**: Hierarchical relationship (epics)
   - Epic contains multiple child issues
   - Used for progress tracking
   - Visualized in dependency graph

3. **Discovered From**: Provenance tracking
   - Issue B was discovered while working on Issue A
   - Preserves work discovery context
   - Helps agents understand how work evolved

4. **Related**: Soft connection
   - Issues are related but not blocking
   - Reference-only, doesn't affect ready status

**Ready Work Algorithm**:

```python
def is_ready(issue: Issue) -> bool:
    """Determine if an issue is ready to work on."""
    # Must be in "Todo" status
    if issue.status != "Todo":
        return False

    # Must not be assigned (or assigned to requesting agent)
    if issue.agent and issue.agent != current_agent:
        return False

    # Must have no open blockers
    for blocker_id in issue.blocked_by:
        blocker = get_issue(blocker_id)
        if blocker.status not in ["Done", "Abandoned"]:
            return False

    return True
```

### Agent Work Claiming & Mutex Lock

**Problem**: Multiple agents querying for ready work simultaneously could grab the same issue, leading to duplicate work and wasted resources.

**Solution**: Comment-based mutex lock with timestamp expiration

**Mechanism**:

When an agent starts work on an issue, it MUST post a claim comment to the GitHub issue:

```markdown
🤖 **[Agent Claim]**

Agent: `claude`
Started: `2025-10-25T14:30:00Z`
Session ID: `abc123-def456`

Claiming this issue for implementation. If this agent goes MIA, this claim expires after 30 minutes.
```

**Implementation**:

```python
class BoardManager:
    CLAIM_TIMEOUT = 86400  # 24 hours in seconds (configurable)
    CLAIM_RENEWAL_INTERVAL = 3600  # 1 hour - how often to renew long-running claims
    CLAIM_COMMENT_PREFIX = "🤖 **[Agent Claim]**"
    CLAIM_RENEWAL_PREFIX = "🔄 **[Claim Renewal]**"

    async def claim_work(self, issue_number: int, agent_name: str, session_id: str) -> bool:
        """
        Attempt to claim an issue for work.

        Returns:
            True if claim successful, False if already claimed by another agent
        """
        # Check for existing valid claims
        existing_claim = await self._get_active_claim(issue_number)
        if existing_claim:
            # Check if claim has expired
            claim_age = datetime.utcnow() - existing_claim.timestamp
            if claim_age.total_seconds() < self.CLAIM_TIMEOUT:
                logger.info(f"Issue #{issue_number} already claimed by {existing_claim.agent}")
                return False
            else:
                logger.info(f"Stale claim expired on issue #{issue_number}, stealing")

        # Post claim comment
        comment_body = f"""🤖 **[Agent Claim]**

Agent: `{agent_name}`
Started: `{datetime.utcnow().isoformat()}Z`
Session ID: `{session_id}`

Claiming this issue for implementation. If this agent goes MIA, this claim expires after {self.CLAIM_TIMEOUT // 3600} hours.
"""
        await self._post_issue_comment(issue_number, comment_body)

        # Update board status
        await self.update_status(issue_number, "In Progress")
        await self.assign_to_agent(issue_number, agent_name)

        return True

    async def renew_claim(self, issue_number: int, agent_name: str, session_id: str) -> bool:
        """
        Renew an active claim for long-running tasks.

        This allows agents working on tasks longer than CLAIM_TIMEOUT to periodically
        update their claim timestamp, preventing it from expiring.

        Returns:
            True if renewal successful, False if no active claim or wrong agent
        """
        # Verify active claim belongs to this agent
        existing_claim = await self._get_active_claim(issue_number)
        if not existing_claim or existing_claim.agent != agent_name:
            logger.warning(f"Cannot renew claim on #{issue_number}: no active claim by {agent_name}")
            return False

        # Post renewal comment (updates timestamp)
        comment_body = f"""🔄 **[Claim Renewal]**

Agent: `{agent_name}`
Renewed: `{datetime.utcnow().isoformat()}Z`
Session ID: `{session_id}`

Claim renewed - still actively working on this issue.
"""
        await self._post_issue_comment(issue_number, comment_body)

        return True

    async def release_work(self, issue_number: int, agent_name: str, reason: str = "completed"):
        """Release claim on an issue."""
        comment_body = f"""🤖 **[Agent Release]**

Agent: `{agent_name}`
Released: `{datetime.utcnow().isoformat()}Z`
Reason: `{reason}`

Work claim released.
"""
        await self._post_issue_comment(issue_number, comment_body)

        if reason == "completed":
            await self.update_status(issue_number, "Done")
        elif reason == "blocked":
            await self.update_status(issue_number, "Blocked")
        else:
            # Abandoned or error - return to todo
            await self.update_status(issue_number, "Todo")
            await self.assign_to_agent(issue_number, None)  # Unassign

    async def _get_active_claim(self, issue_number: int) -> Optional[AgentClaim]:
        """
        Parse issue comments to find active claim.

        Looks for most recent claim/renewal comment that hasn't been released.
        Claim renewals update the effective timestamp, extending the timeout.
        """
        comments = await self._get_issue_comments(issue_number)

        latest_claim = None
        latest_timestamp = None

        # Find most recent claim or renewal
        for comment in reversed(comments):
            if self.CLAIM_COMMENT_PREFIX in comment.body:
                # Initial claim
                claim = self._parse_claim_comment(comment)
                latest_claim = claim
                latest_timestamp = comment.created_at
                break
            elif self.CLAIM_RENEWAL_PREFIX in comment.body:
                # Renewal updates timestamp
                renewal = self._parse_renewal_comment(comment)
                if latest_timestamp is None or comment.created_at > latest_timestamp:
                    latest_timestamp = comment.created_at

        # Check if claim was subsequently released
        if latest_claim and self._has_subsequent_release(comments, latest_timestamp):
            return None

        # Update claim with most recent timestamp (from renewal if exists)
        if latest_claim and latest_timestamp:
            latest_claim.timestamp = latest_timestamp

        return latest_claim
```

**Updated Ready Work Algorithm**:

```python
async def get_ready_work(self, agent_name: Optional[str] = None, limit: int = 10) -> List[Issue]:
    """
    Get issues ready for work, respecting claims.

    Returns issues that are:
    1. In "Todo" or "Blocked" status (but blockers resolved)
    2. Not claimed by another agent (or claim expired)
    3. Have no open blockers
    4. Match agent filter if specified
    """
    # Get all issues in Todo/Blocked status
    candidate_issues = await self._query_issues(status=["Todo", "Blocked"])

    ready_issues = []
    for issue in candidate_issues:
        # Check blockers
        if not await self._are_blockers_resolved(issue):
            continue

        # Check for active claim
        claim = await self._get_active_claim(issue.number)
        if claim:
            claim_age = datetime.utcnow() - claim.timestamp
            if claim_age.total_seconds() < self.CLAIM_TIMEOUT:
                # Valid claim by another agent
                if claim.agent != agent_name:
                    continue
                # Else: claimed by requesting agent, include it

        # Agent filter
        if agent_name and issue.agent and issue.agent != agent_name:
            continue

        ready_issues.append(issue)

        if len(ready_issues) >= limit:
            break

    return ready_issues
```

**Claim Expiration Handling**:

Stale claims do NOT require active cleanup. The claim system is purely timestamp-based:

1. **Claims naturally expire**: After 24 hours, `get_ready_work()` will ignore the claim
2. **Audit trail preserved**: All claim/renewal/release comments remain as permanent audit log
3. **No comment deletion**: Comments are never deleted, maintaining full history
4. **Human visibility**: Anyone can see claim history in the issue comments

```python
async def _is_claim_expired(self, claim: AgentClaim) -> bool:
    """
    Check if a claim has expired based on timestamp.

    No cleanup needed - expired claims are simply ignored by get_ready_work().
    All claim comments remain as audit trail.
    """
    claim_age = datetime.utcnow() - claim.timestamp
    return claim_age.total_seconds() >= self.CLAIM_TIMEOUT
```

**Optional Manual Expiration Notification**:

For human visibility, a scheduled task can optionally post expiration notices without modifying state:

```python
async def notify_expired_claims(self):
    """
    Optional: Post notification comments for expired claims (no state changes).

    This is purely informational - the claim is already expired based on timestamp.
    Run this as a low-priority scheduled task (e.g., once per day).
    """
    all_issues = await self._query_issues(status=["In Progress"])

    for issue in all_issues:
        claim = await self._get_active_claim(issue.number)
        if not claim:
            continue

        if self._is_claim_expired(claim):
            # Check if we already posted expiration notice
            if not await self._has_expiration_notice(issue.number, claim):
                comment = f"""⚠️ **[Claim Expired - Informational]**

Agent `{claim.agent}` claim expired after {self.CLAIM_TIMEOUT // 3600} hours.
This issue is now available for other agents to claim.

Session ID: `{claim.session_id}`

Note: This is informational only. The claim naturally expired based on timestamp.
"""
                await self._post_issue_comment(issue.number, comment)
```

**Benefits**:

1. **Visible Audit Trail**: All claim/release events are visible in issue comments
2. **Human Override**: Humans can see which agent is working on what, when
3. **Automatic Timeout**: Prevents indefinite locks from crashed agents
4. **No Database Required**: State stored in GitHub issues themselves
5. **Race Condition Prevention**: First comment wins (GitHub API is atomic)
6. **Graceful Degradation**: If claim check fails, worst case is duplicate work (not data corruption)

**Configuration**:

```yaml
# .github/ai-agents-board.yml
work_claims:
  # How long before a claim expires (seconds)
  timeout: 86400  # 24 hours

  # How often agents should renew claims for long-running tasks (seconds)
  renewal_interval: 3600  # 1 hour

  # Post informational expiration notices (optional)
  notify_expired: true
  notification_interval: 86400  # Once per day

  # Require comment claim for all work
  enforce_claims: true
```

### Error Handling & Resilience

**Retry Strategy**:

```python
class BoardManager:
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 60.0

    async def _execute_with_retry(self, operation: Callable, *args, **kwargs):
        """
        Execute GraphQL operation with exponential backoff retry.

        Handles transient failures gracefully while failing fast on permanent errors.
        """
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                return await operation(*args, **kwargs)
            except GraphQLError as e:
                # Check HTTP status code
                if hasattr(e, 'status_code'):
                    if 400 <= e.status_code < 500:
                        # Client errors (4xx) - don't retry
                        if e.status_code == 401:
                            logger.error("Authentication failed - check GITHUB_TOKEN")
                        elif e.status_code == 403:
                            logger.error("Rate limit exceeded or forbidden - check permissions")
                        elif e.status_code == 404:
                            logger.error("Resource not found - check project/issue exists")
                        raise  # Don't retry client errors

                    if e.status_code >= 500:
                        # Server errors (5xx) - retry with backoff
                        if attempt < self.MAX_RETRIES - 1:
                            logger.warning(f"Server error {e.status_code}, retrying in {backoff}s...")
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 2, self.MAX_BACKOFF)
                            continue
                        else:
                            logger.error(f"Max retries exceeded for server error: {e}")
                            raise

                # Network errors - retry with backoff
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Network error, retrying in {backoff}s: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    logger.error(f"Max retries exceeded: {e}")
                    raise
```

**Rate Limit Handling**:

```python
async def _check_rate_limit(self):
    """
    Proactively check rate limit before expensive operations.

    GitHub GraphQL has 5000 points/hour limit. Monitor remaining quota.
    """
    rate_limit = await self._query_rate_limit()

    if rate_limit.remaining < 100:  # Low threshold
        reset_time = rate_limit.reset_at
        wait_seconds = (reset_time - datetime.utcnow()).total_seconds()

        if wait_seconds > 0:
            logger.warning(f"Rate limit low ({rate_limit.remaining}), waiting {wait_seconds}s")
            await asyncio.sleep(wait_seconds)
```

**Graceful Degradation**:

When GitHub API is unavailable:
1. **Log detailed error context**: Issue URL, operation attempted, agent name
2. **Fail gracefully**: Return empty work queue rather than crashing
3. **Human notification**: Post error to dedicated monitoring issue
4. **Fallback mode**: Continue with cached data if available

### Performance Considerations

1. **Caching**: Cache project structure and field IDs (1 hour TTL)
2. **Batch Operations**: Update multiple issues in single GraphQL call
3. **Rate Limiting**: Respect GitHub API limits (5000 points/hour for GraphQL)
4. **Pagination**: Handle projects with >100 issues using cursor-based pagination
5. **Concurrent Agents**: Use optimistic locking with issue assignments
6. **Throttling Mitigation**: Minimize claim renewal frequency (default 1 hour)

### Security

1. **Token Scope**: Requires `repo`, `read:org`, `write:org` permissions
2. **Agent Authorization**: Reuse existing `SecurityManager` from package
3. **Audit Trail**: GitHub Projects tracks all changes with timestamps
4. **Secrets**: Store token in environment variables, never in config

### GitHub Actions Integration

**Authentication**: Use GitHub's built-in `GITHUB_TOKEN` secret (automatically available in workflows)

```yaml
# .github/workflows/agent-board-integration.yml
name: AI Agent Board Integration

on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:  # Manual trigger

jobs:
  process-ready-work:
    runs-on: self-hosted

    permissions:
      issues: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e packages/github_ai_agents

      - name: Query ready work and process
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          python -m github_ai_agents.board.cli ready --limit 5
```

**Token Permissions**:

The default `GITHUB_TOKEN` provides:
- Read access to repository contents
- Write access to issues and project boards
- Automatic authentication (no manual PAT needed)
- Scoped to the repository running the workflow

**Multi-Repository Support**:

For org-wide project boards, use a PAT stored as a repository secret:

```yaml
env:
  GITHUB_TOKEN: ${{ secrets.ORG_BOARD_TOKEN }}  # Fine-grained PAT
```

### Debugging & Observability

**Structured Logging**:

```python
class BoardManager:
    def __init__(self):
        self.logger = logging.getLogger('github_ai_agents.board')

    async def claim_work(self, issue_number: int, agent_name: str, session_id: str):
        self.logger.info(
            "Claiming work",
            extra={
                "issue_number": issue_number,
                "issue_url": f"https://github.com/{self.repo}/issues/{issue_number}",
                "agent": agent_name,
                "session_id": session_id,
                "action": "claim_work"
            }
        )
```

**Traceability Requirements**:

Every operation MUST log:
1. **Issue URL**: Direct link for humans to investigate
2. **Agent name**: Which agent performed the action
3. **Session ID**: Track multi-session workflows
4. **Timestamp**: ISO 8601 format with timezone
5. **Operation result**: Success/failure with error details

**Monitoring Dashboard** (future enhancement):

Track metrics like:
- Claim duration distribution
- Work queue depth over time
- Agent utilization rates
- Expired claim frequency

## Package Maintenance Tasks

### Identified Stale Components

Based on package review, the following require updates:

#### 1. Python Version Support

**Issue**: Package specifies Python 3.8+ but should target 3.11+ for consistency

**Fix**:
- Update `pyproject.toml` `requires-python` to `>=3.11`
- Remove Python 3.8, 3.9, 3.10 from classifiers
- Update GitHub Actions to test only 3.11+

#### 2. Dependency Updates

**Issue**: Some dependencies may be outdated

**Fix**:
- Audit all dependencies in `pyproject.toml`
- Update to latest stable versions
- Add `gql` for GraphQL client
- Add `sgqlc` as alternative GraphQL client

#### 3. Async Consistency

**Issue**: Mix of sync and async methods in monitors

**Fix**:
- Ensure all I/O operations are async
- Use `asyncio.run()` consistently
- Add async context managers where appropriate

#### 4. Type Annotations

**Issue**: Incomplete type hints in some modules

**Fix**:
- Add full type annotations to all public methods
- Run `mypy` in strict mode
- Add `py.typed` marker file

#### 5. Documentation Gaps

**Issue**: Missing docstrings and examples

**Fix**:
- Add comprehensive docstrings (Google style)
- Create usage examples for each monitor
- Update architecture.md with recent changes

#### 6. Test Coverage

**Issue**: Some components lack tests

**Fix**:
- Add integration tests for monitors
- Mock GitHub API responses
- Achieve >80% coverage target

### Maintenance Checklist (Integrated with REFINE.md)

**Tier 1 (During Board Integration)**:
- [ ] Create documentation index (INDEX.md) - Phase 1
- [ ] Create quick start guide (QUICK_START.md) - Phase 1
- [ ] Create installation guide (INSTALLATION.md) - Phase 1
- [ ] Reorganize tests into unit/integration/e2e - Phase 1
- [ ] Create tests/conftest.py with fixtures - Phase 1
- [ ] Create tests/README.md - Phase 1
- [ ] Overhaul examples/ directory - Phase 3
- [ ] Create comprehensive examples/README.md - Phase 3
- [ ] Move TTS examples to examples/tts/ - Phase 3
- [ ] Create CHANGELOG.md - Phase 6

**Tier 2 (During Board Integration)**:
- [ ] Create API reference (API_REFERENCE.md) - Phase 6
- [ ] Create CLI reference (CLI_REFERENCE.md) - Phase 6
- [ ] Update pyproject.toml (line length, Python 3.11+, dep groups) - Phase 6
- [ ] Create bin/ directory with executables - Phase 6
- [ ] Create bin/README.md - Phase 6
- [ ] Create TODO.md development roadmap - Phase 6

**Code Quality (Ongoing)**:
- [ ] Update Python version requirements (3.11+)
- [ ] Audit and update dependencies
- [ ] Convert remaining sync I/O to async
- [ ] Add complete type annotations
- [ ] Write missing docstrings
- [ ] Improve test coverage to >80%
- [ ] Version bump to 0.2.0

## Testing Strategy

### Unit Tests

**Test Coverage**:
- Board manager CRUD operations (mocked GraphQL)
- Dependency resolution logic
- Ready work detection algorithm
- Configuration parsing
- CLI command parsing
- Claim parsing and validation
- Stale claim detection logic

**Tools**:
- `pytest` with `pytest-asyncio`
- `unittest.mock` for GraphQL responses
- `pytest-cov` for coverage reporting

**Example Test Cases**:
```python
async def test_claim_work_success():
    """Test successful work claim."""
    board = BoardManager()
    success = await board.claim_work(45, "claude", "session123")
    assert success is True

async def test_claim_work_race_condition():
    """Test claim rejection when already claimed."""
    board = BoardManager()
    await board.claim_work(45, "claude", "session123")
    success = await board.claim_work(45, "opencode", "session456")
    assert success is False  # Already claimed

async def test_claim_expiration():
    """Test stale claim expires after timeout."""
    board = BoardManager()
    board.CLAIM_TIMEOUT = 1  # 1 second for testing
    await board.claim_work(45, "claude", "session123")
    await asyncio.sleep(2)
    success = await board.claim_work(45, "opencode", "session456")
    assert success is True  # Claim expired, stolen successfully

async def test_claim_renewal():
    """Test claim renewal extends timeout."""
    board = BoardManager()
    board.CLAIM_TIMEOUT = 2  # 2 seconds for testing

    # Initial claim
    await board.claim_work(45, "claude", "session123")
    await asyncio.sleep(1)

    # Renew claim before expiration
    success = await board.renew_claim(45, "claude", "session123")
    assert success is True

    # Wait another 1.5 seconds (total 2.5s from initial claim)
    await asyncio.sleep(1.5)

    # Without renewal, claim would be expired (>2s)
    # But renewal reset the timer, so it's still valid
    success = await board.claim_work(45, "opencode", "session456")
    assert success is False  # Still claimed by claude (renewal worked)

async def test_claim_renewal_wrong_agent():
    """Test that only the owning agent can renew a claim."""
    board = BoardManager()

    await board.claim_work(45, "claude", "session123")

    # Different agent tries to renew
    success = await board.renew_claim(45, "opencode", "session456")
    assert success is False  # Wrong agent, renewal rejected
```

### Integration Tests

**Test Coverage**:
- Full board workflow (create → claim → update → release → complete)
- Monitor integration (issue trigger → board update)
- Multi-agent coordination with claims
- Dependency graph operations
- Claim expiration and cleanup
- Race condition handling (concurrent claims)

**Requirements**:
- Test GitHub repository
- Test GitHub Project board
- Test API token with limited permissions

**Example Integration Test**:
```python
async def test_multi_agent_coordination():
    """Test multiple agents working without conflicts."""
    board = BoardManager()

    # Create test issues
    issue1 = await board.create_issue_with_metadata(
        title="Task 1", type="feature", priority="high"
    )
    issue2 = await board.create_issue_with_metadata(
        title="Task 2", type="bug", priority="medium"
    )

    # Agent 1 claims and works on issue 1
    success1 = await board.claim_work(issue1.number, "claude", "s1")
    assert success1 is True

    # Agent 2 tries to claim issue 1, should fail
    success2 = await board.claim_work(issue1.number, "opencode", "s2")
    assert success2 is False

    # Agent 2 claims issue 2 instead
    success3 = await board.claim_work(issue2.number, "opencode", "s3")
    assert success3 is True

    # Both agents work independently
    await board.release_work(issue1.number, "claude", "completed")
    await board.release_work(issue2.number, "opencode", "completed")

    # Both issues are done
    assert (await board.get_issue(issue1.number)).status == "Done"
    assert (await board.get_issue(issue2.number)).status == "Done"
```

### End-to-End Tests

**Test Coverage**:
- Claude agent queries ready work
- OpenCode creates and files issue
- Gemini discovers issue during review
- PR merge updates board status

**Tools**:
- GitHub Actions workflow
- Self-hosted runner
- Mock agents for reproducibility

## Success Metrics

### Quantitative Metrics

1. **Ready Work Query Time**: <1 second for projects with <500 issues
2. **API Rate Limit Usage**: <10% of hourly limit under normal operation
3. **Test Coverage**: >85% for board module, >80% overall package
4. **Agent Adoption**: All 4 agents (Claude, OpenCode, Gemini, Crush) using board within 1 month

### Qualitative Metrics

1. **Developer Experience**: Can manually interact with board via GitHub UI
2. **Agent Behavior**: Agents spontaneously file discovered issues
3. **Long-Horizon Tasks**: Agents complete multi-session implementations successfully
4. **Coordination**: Multiple agents work without conflicts or duplication

## Risks & Mitigations

### Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| GitHub API rate limits | High | Medium | Implement caching, batch operations, proactive rate limit checking |
| API throttling (abuse detection) | High | Medium | Minimize comment frequency, use 1-hour renewal interval (not shorter) |
| GraphQL schema changes | Medium | Low | Version lock schema, monitor GitHub changelogs, comprehensive integration tests |
| Large project performance | Medium | Medium | Implement cursor-based pagination, lazy loading, field caching |
| Concurrent agent conflicts | High | Medium | Comment-based mutex with 24-hour timeout, explicit claim/release |
| Debugging complexity | High | High | Structured logging with issue URLs, session IDs, comprehensive audit trail |
| API behavior changes | Low | Low | Extensive integration tests, monitor GitHub API announcements |

### Organizational Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Manual board corruption | Medium | Low | Document agent-managed fields, human/agent collaboration is intentional |
| GitHub service outages | High | Low | Graceful degradation, cached data fallback, retry with exponential backoff |
| Security token compromise | High | Low | Use fine-grained PATs with minimum scopes, rotate regularly |
| Stuck issues (permanent claims) | Medium | Medium | 24-hour natural expiration, optional expiration notifications |

### Implementation Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claim mechanism bugs | High | Medium | Extensive race condition testing, claim renewal testing, audit trail verification |
| Comment parsing errors | Medium | Low | Strict comment format validation, backward compatibility for format changes |
| Network partition during claim | Medium | Low | Timestamp-based expiration (no state cleanup required), duplicate work is acceptable |

## Open Questions

1. **Board Structure**: What custom fields are required on GitHub Project boards?
   - **Recommendation**: Document required fields (Status, Priority, Agent, etc.) in setup guide

2. **Multiple Projects**: Support multiple boards per repository?
   - **Recommendation**: Single board initially, multi-board in v0.3.0

3. **Issue Label Sync**: Should board status sync to issue labels?
   - **Recommendation**: Yes, bidirectional sync for human visibility

4. **Historical Data**: Track issue status history beyond GitHub's native tracking?
   - **Recommendation**: Not initially, rely on GitHub's audit log

5. **Cross-Repo Dependencies**: Support blockers across repositories?
   - **Recommendation**: Not initially, same-repo only for v0.2.0

## Future Enhancements (Out of Scope)

1. **Analytics Dashboard**: Visualize agent productivity, work patterns
2. **Slack Integration**: Post board updates to Slack channels
3. **Custom Workflows**: Define state machines for different issue types
4. **AI Insights**: Use LLM to suggest priorities, detect stale issues
5. **Multi-Platform**: Support GitLab, Bitbucket project boards

## Appendix A: File Structure

```
packages/github_ai_agents/
├── src/github_ai_agents/
│   ├── board/
│   │   ├── __init__.py
│   │   ├── manager.py          # Core BoardManager class
│   │   ├── config.py           # Configuration parsing
│   │   ├── dependencies.py     # Dependency graph logic
│   │   ├── queries.py          # GraphQL query builders
│   │   ├── models.py           # Data models
│   │   └── cli.py              # CLI tool
│   ├── monitors/
│   │   ├── issue.py            # [UPDATE] Add board integration
│   │   └── pr.py               # [UPDATE] Add board status sync
│   └── tests/
│       ├── test_board_manager.py
│       ├── test_dependencies.py
│       ├── test_board_config.py
│       └── test_monitor_board_integration.py
│
tools/mcp/github_board/
├── __init__.py
├── server.py                    # MCP server implementation
├── docs/
│   ├── README.md
│   ├── EXAMPLES.md
│   └── API.md
└── scripts/
    └── test_server.py

docker/
├── github-board.Dockerfile      # [NEW] Container for MCP server
└── requirements-github-board.txt

.github/
├── workflows/
│   └── test-github-board.yml   # [NEW] CI for board module
└── ai-agents-board.yml         # [NEW] Board configuration

docs/
└── integrations/
    └── github-board.md          # [NEW] User documentation
```

## Appendix B: Example Agent Workflow

**Scenario**: Claude is implementing a feature that requires multiple sessions, with claim-based locking

```python
# Session 1: Agent starts work
issues = await board.query_ready_work(agent="claude", limit=5)
# Returns: [Issue(#45: "Add user authentication", status="Todo", blocks=[])]

# CLAIM the work (posts comment to issue #45)
session_id = uuid.uuid4().hex
success = await board.claim_work(45, agent="claude", session_id=session_id)
# Returns: True
# Posts comment: "🤖 [Agent Claim] Agent: claude, Started: 2025-10-25T14:30:00Z"

# During implementation, agent discovers missing dependency
new_issue = await board.create_issue_with_metadata(
    title="Create database migration for user table",
    body="Required for authentication feature",
    type="tech_debt",
    priority="high",
    discovered_from=45  # Links back to parent
)
# Creates Issue #47, automatically blocks #45

await board.add_blocker(45, 47)  # Explicitly mark the blocker

# Agent realizes it's blocked, releases claim
await board.release_work(45, agent="claude", reason="blocked")
# Posts comment: "🤖 [Agent Release] Agent: claude, Reason: blocked"
# Sets status to "Blocked"

# Session ends, agent compacts
# ---

# Session 2: Different agent (OpenCode) starts
issues = await board.query_ready_work(agent="opencode")
# Returns: [Issue(#47: "Create database migration...", status="Todo", blocks=[])]
# Note: #45 is NOT returned because it's blocked by #47

# OpenCode tries to claim another issue at the same time as Gemini
session_id_oc = uuid.uuid4().hex
session_id_gm = uuid.uuid4().hex

# Race condition: both agents query simultaneously
# But only first claim_work() comment wins
success_oc = await board.claim_work(47, agent="opencode", session_id=session_id_oc)
success_gm = await board.claim_work(47, agent="gemini", session_id=session_id_gm)

# Returns: success_oc=True, success_gm=False (claim already exists)
# OpenCode gets the work, Gemini is rejected

# OpenCode completes the migration
await board.release_work(47, agent="opencode", reason="completed")
# Posts comment: "🤖 [Agent Release] Agent: opencode, Reason: completed"
# Sets status to "Done"

# Session ends
# ---

# Session 3: Claude resumes after 20 minutes
issues = await board.query_ready_work(agent="claude")
# Returns: [Issue(#45: "Add user authentication", status="Blocked", blocks=[])]
# Wait... #45 is back! Blocker #47 is resolved

# Claude sees full context
context = await board.get_issue_context(45)
# Returns:
# {
#   "issue": Issue(#45),
#   "blockers": [Issue(#47, status="Done")],  # Resolved!
#   "discovered_during": [],
#   "discovered_from": None,
#   "related": [],
#   "claim_history": [
#     Claim(agent="claude", started="...", released="...", reason="blocked")
#   ]
# }

# Claim the unblocked work
session_id = uuid.uuid4().hex
success = await board.claim_work(45, agent="claude", session_id=session_id)
# Returns: True (previous claim was released)

# Agent completes authentication feature after 10 minutes
await board.release_work(45, agent="claude", reason="completed")
# Issue #45 is now Done

# ---

# Session 4: Long-running task with claim renewal
issues = await board.query_ready_work(agent="crush")
# Returns: [Issue(#50: "Refactor database layer", status="Todo", blocks=[])]

session_id = uuid.uuid4().hex
await board.claim_work(50, agent="crush", session_id=session_id)

# Agent is working on complex refactor - will take 3 hours
# Every hour, renew the claim to prevent expiration
for hour in range(3):
    # Work for an hour
    await asyncio.sleep(3600)

    # Renew claim before it expires
    await board.renew_claim(50, agent="crush", session_id=session_id)
    # Posts: "🔄 [Claim Renewal] Agent: crush, Renewed: 2025-10-25T16:30:00Z"

# Complete the work
await board.release_work(50, agent="crush", reason="completed")

# ---

# Session 5: Stale claim scenario (agent crash - no renewal)
issues = await board.query_ready_work(agent="opencode")
# Returns: [Issue(#55: "Add new feature", status="Todo", blocks=[])]

session_id = uuid.uuid4().hex
await board.claim_work(55, agent="opencode", session_id=session_id)

# OpenCode crashes 2 hours in, never releases or renews claim
# ...agent gone...

# 24 hours later, claim naturally expires based on timestamp
# No cleanup needed - expiration is purely timestamp-based

# Now another agent can pick it up
issues = await board.query_ready_work(agent="claude")
# Returns: [Issue(#55: "Add new feature", status="Todo", blocks=[])]
# OpenCode's stale claim (>24h old) is automatically ignored!

# Claude claims the work (stealing expired claim)
await board.claim_work(55, agent="claude", session_id=uuid.uuid4().hex)
# Returns: True - expired claim can be stolen
```

**Key Takeaways**:

1. **Claim Before Work**: Agents MUST claim before starting work
2. **Atomic Claiming**: First comment wins in race conditions
3. **Explicit Release**: Agents release claims with reason (completed/blocked/abandoned)
4. **Long-Running Tasks**: Agents renew claims hourly for tasks taking >1 hour
5. **Timeout Protection**: 24-hour natural expiration prevents permanent locks
6. **No Cleanup Required**: Expired claims are simply ignored (timestamp-based)
7. **Visible Audit**: All claim/release/renewal events visible in issue comments
8. **Context Preservation**: Claim history helps understand work evolution

## Appendix C: Comparison with Beads

| Feature | Beads | This Solution |
|---------|-------|---------------|
| **Storage** | Git-backed JSONL + SQLite | GitHub Projects v2 GraphQL |
| **Interface** | CLI (`bd`) | CLI + MCP Server + Web UI |
| **Deployment** | Local binary | Docker container + API |
| **Multi-Agent** | Via git merge | Native (centralized) |
| **Concurrency** | Merge conflict resolution | Comment-based mutex locks |
| **Work Claiming** | Implicit (via status) | Explicit (timestamped comments) |
| **Claim Renewal** | Not applicable | Hourly renewals for long tasks |
| **Stale Lock Handling** | Manual intervention | Auto-expiration (24 hours, timestamp-based) |
| **Dependencies** | 4 types (blocks, parent, discovered, related) | Same 4 types + custom fields |
| **Query Language** | CLI flags | GraphQL + Python API |
| **UI** | CLI only | GitHub web UI + CLI |
| **Platform** | Any git repo | GitHub only |
| **Setup** | `bd quickstart` | Create project + config file |
| **Merge Conflicts** | AI resolves | N/A (centralized) |
| **Versioning** | Git history | GitHub audit log |
| **Custom Fields** | Fixed schema | Configurable project fields |
| **Audit Trail** | Git commits | Issue comments + GitHub audit |

**Key Advantages Over Beads**:
1. No merge conflicts - centralized state
2. Built-in web UI for human oversight
3. Cross-repository support (via GitHub org)
4. No local database to corrupt or lose
5. Claim renewal mechanism for long-running tasks
6. No cleanup required - timestamp-based expiration
7. Full audit trail in GitHub issue comments

**Key Disadvantages**:
1. GitHub-only (not portable to GitLab, etc.)
2. Requires network connection
3. Subject to GitHub API rate limits
4. Cannot work offline

## Appendix D: References

- **Beads Project**: https://github.com/steveyegge/beads
- **Steve Yegge's Article**: https://steve-yegge.medium.com/introducing-beads-a-coding-agent-memory-system-637d7d92514a
- **GitHub Projects v2 Docs**: https://docs.github.com/en/issues/planning-and-tracking-with-projects
- **GraphQL API Reference**: https://docs.github.com/en/graphql/reference/objects#projectv2
- **Template Repo MCP Docs**: `docs/mcp/README.md`
- **AI Agents Security**: `packages/github_ai_agents/docs/security.md`

## Appendix E: Integration with Package Refinement

This PRD incorporates critical improvements from `REFINE.md` (Package Refinement Plan v1.0) to ensure the `github_ai_agents` package reaches the quality standards of `sleeper_detection` and `economic_agents`.

**Integrated Refinements**:
- **Phase 1**: Documentation structure (INDEX.md, QUICK_START.md, INSTALLATION.md) + Test reorganization (unit/, integration/, e2e/) - Tier 1
- **Phase 3**: Examples overhaul with comprehensive README and usage examples - Tier 1
- **Phase 6**: Complete documentation (API/CLI reference), tooling (bin/ directory), and pyproject.toml updates - Tier 1 + Tier 2

**Remaining from REFINE.md** (to be completed post-v0.2.0):
- Tier 3 items: DEPLOYMENT.md, TROUBLESHOOTING.md, INTEGRATION_GUIDE.md
- Advanced tooling: scripts/ directory, Sphinx documentation, package-level docker-compose
- Parametrized test examples and comprehensive test fixtures

**Benefits of Integration**:
1. **Documentation Infrastructure Ready**: INDEX.md, QUICK_START.md, and INSTALLATION.md in place before board features launch
2. **Test Foundation Solid**: Reorganized test structure supports board integration testing from Phase 1
3. **Examples Showcase Features**: Comprehensive examples demonstrate both existing and new board functionality
4. **Quality Consistency**: Package reaches parity with sleeper_detection and economic_agents by v0.2.0

See `packages/github_ai_agents/REFINE.md` for the complete refinement plan and detailed specifications.

---

**Document Version**: 1.2
**Last Updated**: 2025-10-25
**Status**: Ready for Implementation
**Next Steps**: Implementation Phase 1 → Testing → Iteration

## Revision History

### Version 1.2 (2025-10-25) - Integration with REFINE.md

Integrated critical improvements from `REFINE.md` (Package Refinement Plan) to ensure quality parity with other packages:

**Phase 1 Enhancements**:
- Added documentation structure setup (INDEX.md, QUICK_START.md, INSTALLATION.md)
- Added test infrastructure reorganization (unit/, integration/, e2e/)
- Updated file paths to reflect new test structure

**Phase 3 Enhancements**:
- Added examples overhaul deliverables
- Comprehensive examples/README.md creation
- TTS examples reorganization to examples/tts/

**Phase 6 Expansion**:
- Complete documentation set (API_REFERENCE.md, CLI_REFERENCE.md)
- Tooling additions (bin/ directory with executables)
- pyproject.toml updates (line length 127, Python 3.11+, optional dep groups)
- CHANGELOG.md and TODO.md creation

**New Appendix E**:
- Documents integration strategy with REFINE.md
- Lists remaining Tier 3 items for post-v0.2.0
- Explains benefits of integrated approach

**Maintenance Checklist Update**:
- Reorganized into Tier 1, Tier 2, and Code Quality sections
- Mapped items to specific implementation phases
- Integrated with REFINE.md priorities

### Version 1.1 (2025-10-25) - Post-Gemini Review

Based on comprehensive review by Gemini AI, the following critical improvements were added:

**Claim Mechanism Enhancements**:
- Added **claim renewal mechanism** for long-running tasks (hourly heartbeat)
- Changed timeout from 30 minutes to **24 hours** (configurable)
- Clarified that **no cleanup is required** - expiration is purely timestamp-based
- All claim/renewal/release comments remain as permanent audit trail

**Error Handling & Resilience**:
- Added **exponential backoff retry strategy** with 4xx/5xx handling
- Added **proactive rate limit checking** to prevent quota exhaustion
- Added **graceful degradation** patterns for GitHub API unavailability
- Specified HTTP status code handling (401, 403, 404, 5xx)

**GitHub Actions Integration**:
- Documented use of **built-in GITHUB_TOKEN** secret (no manual PAT needed)
- Added example workflow with proper permissions
- Clarified multi-repository support with custom tokens

**Debugging & Observability**:
- Added **structured logging requirements** with issue URLs and session IDs
- Specified traceability requirements for all operations
- Added monitoring dashboard as future enhancement

**Risk Analysis**:
- Added **API throttling (abuse detection)** risk and mitigation
- Added **debugging complexity** risk with structured logging mitigation
- Added **implementation risks** section (claim bugs, parsing errors)

**Project Scope Clarification**:
- Removed project initialization script (works with existing boards only)
- Removed time estimates from implementation plan (phase-based only)
- Clarified human/agent collaboration is intentional (not spam)

### Version 1.0 (2025-10-25) - Initial Draft

Initial PRD based on Steve Yegge's Beads concept, adapted for GitHub Projects v2 integration.

---

## 📊 Implementation Progress Summary

**Last Updated**: 2025-10-25
**Current Phase**: Complete - All Phases 1-6 Finished
**Branch**: `github-agents-refine`
**Status**: ✅ Complete - 6/6 Phases Complete (100%)

---

### ✅ Phase 1: Foundation & GraphQL Client - COMPLETE

**Status**: All deliverables completed and tested (100%)

**Commits**: `9c4657f`, `565e79c`, `22417f7`, `3f338f1`, `4ab5b1f`

**Accomplishments**:
- ✅ Core module structure (board/__init__.py, errors.py, models.py, config.py)
- ✅ BoardManager with complete GraphQL client (1,076 lines)
  - Project and item management
  - Custom field operations
  - Error handling with retry logic and exponential backoff
  - Rate limit monitoring
  - Async/await throughout
- ✅ Data models (Issue, AgentClaim, BoardConfig, DependencyGraph)
- ✅ BoardConfig with YAML file support (.github/ai-agents-board.yml)
- ✅ Comprehensive error handling (BoardNotFoundError, GraphQLError)
- ✅ Structured logging implementation
- ✅ Comprehensive unit tests (44/44 board tests, 85/85 total passing)
- ✅ Test infrastructure (conftest.py, tests/README.md)
- ✅ Documentation structure (INDEX.md, QUICK_START.md, INSTALLATION.md)

**Files Created** (~1,600 lines):
```
packages/github_ai_agents/src/github_ai_agents/board/
├── __init__.py          (49 lines)
├── config.py            (185 lines)
├── errors.py            (77 lines)
├── manager.py           (1,076 lines) ← Core GraphQL client
└── models.py            (211 lines)
```

---

### ✅ Phase 2: Claim System & Dependencies - COMPLETE

**Status**: All functionality implemented and tested (100%)

**Commit**: `22d8290`

**Accomplishments**:
- ✅ Comment-based claim/release mechanism (24h timeout, configurable)
- ✅ Session ID tracking for claim ownership
- ✅ Claim renewal (heartbeat) for long-running tasks (1h interval)
- ✅ Blocker relationship management (add_blocker, resolution checking)
- ✅ Parent-child (epic) relationships (mark_discovered_from)
- ✅ Dependency graph queries (get_dependency_graph)
- ✅ Ready work detection algorithm (checks blockers, claims, expiration)
- ✅ Race condition testing (concurrent claims, expiration, renewal)
- ✅ Comprehensive unit tests (18 new tests, 62/62 board tests passing)

**Implementation Note**: Used monolithic approach (all in manager.py) rather than separate claims.py/dependencies.py modules for simplicity.

**Tests Added** (18 tests):
- test_claim_work_success, test_claim_work_race_condition
- test_claim_expiration, test_claim_renewal
- test_release_work (completed/blocked/abandoned)
- test_add_blocker_success, test_mark_discovered_from
- test_get_ready_work (filters blocked/claimed, agent filtering)
- test_race_condition_concurrent_claims (2 tests)
- test_claim_does_not_block_indefinitely (2 tests)

---

### ✅ Phase 3: MCP Server - COMPLETE

**Status**: Full MCP server operational with all core tools (100%)

**Commit**: `2d6989e`

**Accomplishments**:
- ✅ tools/mcp/github_board/ MCP server implementation
  - GitHubBoardMCPServer class extending BaseMCPServer
  - Port 8021 (HTTP mode) and STDIO mode support
  - Async initialization with BoardManager
- ✅ **11 core tools implemented**:
  1. query_ready_work - Get unblocked, ready issues
  2. claim_work - Claim issue for implementation
  3. renew_claim - Renew claim for long tasks
  4. release_work - Release claim (completed/blocked/abandoned/error)
  5. update_status - Change issue status
  6. add_blocker - Add blocking dependency
  7. mark_discovered_from - Mark parent-child relationship
  8. get_issue_details - Get full issue context
  9. get_dependency_graph - Get complete dependency graph
  10. list_agents - Get enabled agents
  11. get_board_config - Get current configuration
- ✅ Health checks with board status
- ✅ Comprehensive error handling (RuntimeError, graceful degradation, type narrowing)
- ✅ Integration with .mcp.json (STDIO mode for local use)
- ✅ Complete documentation (tools/mcp/github_board/docs/README.md, 467 lines)
- ✅ Server testing utility (scripts/test_server.py)

**Files Created** (~1,100 lines):
```
tools/mcp/github_board/
├── __init__.py          (6 lines)
├── server.py            (498 lines) ← Main MCP server
├── docs/
│   └── README.md        (467 lines)
└── scripts/
    └── test_server.py   (112 lines)
```

**Configuration Added**:
```json
// .mcp.json entry
"github-board": {
  "command": "python",
  "args": ["-m", "tools.mcp.github_board.server", "--mode", "stdio"],
  "env": {
    "GITHUB_TOKEN": "${GITHUB_TOKEN}",
    "GITHUB_REPOSITORY": "${GITHUB_REPOSITORY}",
    "GITHUB_PROJECT_NUMBER": "1"
  }
}
```

---

### ✅ Phase 4: Monitor Integration & GitHub Actions - COMPLETE

**Status**: Full monitor integration with automated board updates (100%)

**Commit**: `aefbab7`

**Accomplishments**:

**Monitor Integration**:
- ✅ Updated monitors/issue.py with board integration
  - BoardManager initialization (optional, graceful degradation)
  - Claim work when issue approved ([Approved][Agent] trigger)
  - Release work when PR created (reason: "completed")
  - Release work on error (reason: "error")
  - Release work as abandoned if no changes generated
  - Session ID tracking throughout workflow
- ✅ Updated monitors/pr.py with board integration
  - BoardManager initialization (optional)
  - Extract issue numbers from PR body (Closes/Fixes/Resolves #N)
  - Update board status to Done when PR merged
  - Support multiple linked issues per PR
  - Helper methods: _extract_issue_numbers(), _update_board_on_pr_merge()
- ✅ Graceful degradation when board config missing (no hard dependency)

**GitHub Actions**:
- ✅ Created .github/workflows/agent-board-integration.yml
  - Trigger on PR merge to update board status
  - Hourly scheduled maintenance task
  - Manual workflow dispatch support
  - Secure env variable handling for PR body (security hardening)
  - Self-hosted runner support

**Configuration**:
- ✅ Created .github/ai-agents-board.yml (166 lines)
  - Complete board configuration with all settings
  - Project, repository, and field mappings
  - Agent enablement (claude, opencode, gemini, crush, codex)
  - Work claim settings (24h timeout, 1h renewal)
  - Work queue filters (exclude labels, priority labels)
  - Integration feature toggles
  - Logging and monitoring settings

**Testing**:
- ✅ Created test_monitor_board_integration.py (21 tests)
  - TestIssueMonitorBoardIntegration (8 tests)
  - TestPRMonitorBoardIntegration (13 tests)
  - Board manager initialization tests
  - Work claiming and releasing tests
  - Issue number extraction tests
  - PR merge board update tests
  - Error handling tests

**Files Modified/Created** (~550 lines):
```
packages/github_ai_agents/src/github_ai_agents/monitors/
├── issue.py             (updated, +84 lines)
└── pr.py                (updated, +48 lines)

.github/
├── ai-agents-board.yml  (166 lines) ← Board config
└── workflows/
    └── agent-board-integration.yml (137 lines)

packages/github_ai_agents/tests/unit/
└── test_monitor_board_integration.py (239 lines, 21 tests)
```

---

### ✅ Phase 5: CLI & Docker - COMPLETE

**Status**: All deliverables completed and tested (100%)

**Commits**: `48f05c0`, `eee1a54`

**Accomplishments**:
- ✅ board/cli.py - CLI tool for human interaction (491 lines)
  - 8 commands: ready, create, block, status, graph, claim, release, info
  - Argparse-based interface with subcommands
  - JSON output support for automation
  - Verbose logging option
  - 24 comprehensive unit tests (test_board_cli.py)
- ✅ Docker container setup
  - docker/mcp-github-board.Dockerfile (48 lines)
  - docker/requirements/requirements-github-board.txt
  - Python 3.11-slim base image
  - Non-root user execution
  - Health checks
- ✅ docker-compose integration
  - mcp-github-board service on port 8021
  - Environment variable configuration
  - Health checks with 30s interval
  - Auto-restart policy
  - Volume mounts for config
- ✅ End-to-end testing
  - tests/e2e/test_board_workflow.py (237 lines, 10 tests)
  - Full workflow testing (init → claim → update → release)
  - Concurrent claim testing
  - Claim renewal testing
  - Performance testing (50 issues <5s)
  - Error handling validation
- ✅ CI/CD pipeline updates
  - .github/workflows/test-github-board.yml (235 lines)
  - 6 jobs: unit-tests, cli-tests, docker-build, mcp-server-tests, e2e-tests, test-summary
  - Conditional E2E execution (workflow_dispatch or main branch)
  - Artifact uploads for coverage reports
  - Self-hosted runner support

**Files Created/Modified** (~1,200 lines):
```
packages/github_ai_agents/src/github_ai_agents/board/
└── cli.py               (491 lines) ← Board CLI implementation

docker/
├── mcp-github-board.Dockerfile  (48 lines)
└── requirements/
    └── requirements-github-board.txt

packages/github_ai_agents/tests/
├── unit/test_board_cli.py       (464 lines, 24 tests)
└── e2e/test_board_workflow.py   (237 lines, 10 tests)

.github/workflows/
└── test-github-board.yml        (235 lines)
```

**Test Coverage**:
- CLI unit tests: 24/24 passing
- E2E workflow tests: 10/10 passing
- Docker health checks: Passing
- All pre-commit hooks: Passing

---

### ✅ Phase 6: Documentation & Polish - COMPLETE

**Status**: All deliverables completed (100%)

**Commits**: `d5115c7`, `f5b2f33`, `d92a194`, `bcff30c`

**Accomplishments**:

**Documentation (2,161 lines)**:
- ✅ Complete board integration documentation
  - docs/board-integration.md (854 lines) - Comprehensive user guide
  - Quick start, core concepts, common workflows
  - CLI reference, performance benchmarks, troubleshooting
  - Best practices, architecture diagrams
- ✅ API reference (docs/API_REFERENCE.md, 651 lines)
  - Complete BoardManager API (15+ methods)
  - BoardConfig, Issue, AgentClaim, DependencyGraph classes
  - IssueMonitor and PRMonitor documentation
  - 50+ code examples with parameters and return types
- ✅ CLI reference (docs/CLI_REFERENCE.md, 656 lines)
  - 8 board-cli commands fully documented
  - Issue monitor and PR monitor CLI docs
  - Examples, environment variables, troubleshooting
  - Tips & tricks, automation patterns

**Examples (3,325 lines)**:
- ✅ examples/README.md (comprehensive guide)
- ✅ examples/basic_usage.py (simplest patterns)
- ✅ examples/issue_monitor_example.py (complete workflow)
- ✅ examples/pr_monitor_example.py (PR review workflow)
- ✅ examples/board_integration_example.py (Projects v2 integration)
- ✅ examples/multi_agent_example.py (concurrent coordination)
- ✅ examples/custom_agent_example.py (specialized agents)
- ✅ examples/github_actions_example.yml (GitHub Actions template)
- ✅ examples/security_example.py (security features)

**Tooling (309 lines)**:
- ✅ bin/ directory with executable wrappers
  - bin/issue-monitor (wrapper for issue CLI)
  - bin/pr-monitor (wrapper for PR CLI)
  - bin/board-cli (wrapper for board CLI)
- ✅ bin/README.md (documentation for executables)

**Package Updates**:
- ✅ Updated pyproject.toml
  - Added mypy exclude for bin/ directory
- ✅ Updated .pre-commit-config.yaml
  - Added bin/ exclude pattern for mypy
- ✅ Created CHANGELOG.md (211 lines)
  - Follows Keep a Changelog format
  - Documents versions 0.2.0, 0.1.0, 0.0.1
  - Migration guide for 0.1.0 → 0.2.0
  - Release process documentation

**Files Created/Modified** (~5,995 lines):
```
packages/github_ai_agents/
├── docs/
│   ├── board-integration.md (854 lines)
│   ├── API_REFERENCE.md     (651 lines)
│   └── CLI_REFERENCE.md     (656 lines)
├── examples/
│   ├── README.md
│   ├── basic_usage.py
│   ├── issue_monitor_example.py
│   ├── pr_monitor_example.py
│   ├── board_integration_example.py
│   ├── multi_agent_example.py
│   ├── custom_agent_example.py
│   ├── github_actions_example.yml
│   └── security_example.py
├── bin/
│   ├── README.md
│   ├── issue-monitor
│   ├── pr-monitor
│   └── board-cli
└── CHANGELOG.md (211 lines)
```

**Test Coverage**:
- All examples include test mode
- All scripts are executable (chmod +x)
- All pre-commit hooks passing
- Proper import structure verified

---

## 📈 Overall Progress

### Summary Statistics

**Phases Complete**: 6/6 (100%) ✅

- ✅ Phase 1: Foundation & GraphQL Client (100%)
- ✅ Phase 2: Claim System & Dependencies (100%)
- ✅ Phase 3: MCP Server (100%)
- ✅ Phase 4: Monitor Integration & GitHub Actions (100%)
- ✅ Phase 5: CLI & Docker (100%)
- ✅ Phase 6: Documentation & Polish (100%)

**Lines of Code Written**: ~10,225 lines
- Board module: ~1,600 lines
- MCP server: ~1,100 lines
- Monitor updates: ~130 lines
- CLI implementation: ~491 lines
- Tests: ~1,200 lines
- Documentation: ~2,161 lines
- Examples: ~3,325 lines
- Configuration: ~300 lines
- Tooling (bin/): ~309 lines
- Docker files: ~48 lines
- CI/CD workflows: ~235 lines
- CHANGELOG: ~211 lines

**Tests**: 137/137 passing (100%)
- Board manager: 62 tests
- Monitor integration: 21 tests
- Board CLI: 24 tests
- E2E workflows: 10 tests
- Security: 17 tests
- Agents: 24 tests

**Commits**: 10 major commits
- Phase 1: `9c4657f`, `565e79c`, `22417f7`, `3f338f1`, `4ab5b1f`
- Phase 2: `22d8290`
- Phase 3: `2d6989e`
- Phase 4: `aefbab7`
- Phase 5: `48f05c0`, `eee1a54`
- Phase 6: `d5115c7`, `f5b2f33`, `d92a194`, `bcff30c`

**Pre-commit Hooks**: All passing ✅
- black, isort, flake8, pylint, mypy, yamllint, actionlint

**Status**: 🎉 All phases complete! Ready for v0.2.0 release.

---

## 📝 Technical Decisions & Key Learnings

### Architecture Decisions

**1. Monolithic BoardManager** (Phase 2):
- **Decision**: Keep all claim/dependency logic in manager.py
- **Rationale**: Simpler imports, reduced complexity, easier maintenance
- **Impact**: Single class handles all board operations

**2. Comment-based Claims** (Phase 2):
- **Decision**: Use GitHub issue comments for claim tracking
- **Rationale**: No database required, built-in audit trail, GitHub-native
- **Impact**: All claim state visible in issue timeline

**3. 24-Hour Timeout** (Phase 2):
- **Decision**: Claims expire after 24 hours by default
- **Rationale**: Prevents stuck issues, forces agent progress updates
- **Impact**: Agents must renew claims for long-running tasks (1h interval)

**4. Optional Monitor Integration** (Phase 4):
- **Decision**: Make board integration optional in monitors
- **Rationale**: No breaking changes, graceful degradation, flexible deployment
- **Impact**: Monitors work normally without board, seamless adoption

**5. Security Hardening** (Phase 4):
- **Decision**: Pass PR body via environment variables in GitHub Actions
- **Rationale**: Prevents code injection from untrusted PR content
- **Impact**: Secure handling of potentially malicious input

### Implementation Patterns

**Async/Await Everywhere**:
- All board operations use async/await
- Proper error handling in async contexts
- AsyncMock for testing async code

**Type Hints & Mypy**:
- `Optional[BoardManager]` for optional integration
- Type narrowing with assertions for mypy
- Comprehensive type annotations throughout

**Graceful Degradation**:
- Check if board_manager exists before operations
- Log warnings but continue operation
- No hard dependency on board configuration

**Testing Strategy**:
- Unit tests mock GraphQL responses
- Integration tests require test repository
- All tests use pytest-asyncio
- Shared fixtures in conftest.py

### Common Pitfalls to Avoid

1. **Initialization**: Always call `board_manager.initialize()` before operations
2. **Type Hints**: Use `Optional[BoardManager]` for optional integration
3. **Availability**: Handle board unavailability gracefully (log warnings)
4. **Session IDs**: Pass session_id through async call chains
5. **Type Narrowing**: Use assertions for mypy (`assert board_manager is not None`)

---

## 🎯 Next Steps

### All Implementation Phases Complete! ✅

All 6 phases of the board integration have been successfully completed:

1. ✅ **Phase 1**: Foundation & GraphQL Client - Complete
2. ✅ **Phase 2**: Claim System & Dependencies - Complete
3. ✅ **Phase 3**: MCP Server - Complete
4. ✅ **Phase 4**: Monitor Integration & GitHub Actions - Complete
5. ✅ **Phase 5**: CLI & Docker - Complete
6. ✅ **Phase 6**: Documentation & Polish - Complete

### Post-Implementation Tasks

**Ready for v0.2.0 Release**:
1. Update version number in pyproject.toml (0.1.0 → 0.2.0)
2. Final review of CHANGELOG.md
3. Tag release: `git tag v0.2.0`
4. Push to main branch

**Future Enhancements (v0.3.0+)**:
1. Advanced board features (multi-repo support, cross-repo dependencies)
2. Analytics dashboard for agent productivity
3. Performance optimizations (caching layer for GraphQL queries)
4. Enhanced test coverage (>85%)
5. Sphinx documentation generation

---

## 🔗 Related Documents

- **Development Roadmap**: `packages/github_ai_agents/TODO.md`
- **Refinement Plan**: `packages/github_ai_agents/REFINE.md`
- **Security Docs**: `packages/github_ai_agents/docs/security.md`
- **Main README**: `packages/github_ai_agents/README.md`
- **Project Instructions**: `CLAUDE.md`

---
