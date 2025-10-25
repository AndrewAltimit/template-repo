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
    async def release_work(self, issue_number: int, agent_name: str, reason: str) -> bool

    # Issue creation and metadata
    async def create_issue_with_metadata(self, title: str, body: str, **metadata) -> Issue
    async def update_status(self, issue_id: str, status: str) -> bool
    async def assign_to_agent(self, issue_id: str, agent_name: str) -> bool

    # Dependency management
    async def add_blocker(self, issue_id: str, blocker_id: str) -> bool
    async def mark_discovered_from(self, issue_id: str, parent_id: str) -> bool
    async def get_dependency_graph(self, issue_id: str) -> Graph

    # Background tasks
    async def cleanup_stale_claims(self) -> None
```

#### 2. MCP Server (`tools/mcp/github_board/server.py`)

**Port**: 8021 (following existing MCP server pattern)

**MCP Tools**:
- `query_ready_work`: Get unblocked, ready-to-work issues
- `claim_work`: Claim an issue for implementation (posts comment with timestamp)
- `release_work`: Release claim on an issue (completed/blocked/abandoned)
- `create_tracked_issue`: Create issue with board metadata
- `add_dependency`: Link issues with blocker/parent relationships
- `update_issue_status`: Change status (todo, in_progress, done, blocked)
- `assign_issue`: Assign to agent or unassign
- `record_discovered_work`: File issue discovered during other work
- `get_issue_context`: Get full context for an issue (dependencies, history, claims)
- `search_board_issues`: Search with filters (status, priority, agent)
- `check_stale_claims`: Manually trigger cleanup of expired claims

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

### Phase 1: Foundation (Week 1)

**Deliverables**:
1. GitHub Projects v2 GraphQL client wrapper
2. Basic CRUD operations for project items
3. Configuration file parser
4. Unit tests with mocked GraphQL responses

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/board/__init__.py`
- `packages/github_ai_agents/src/github_ai_agents/board/manager.py`
- `packages/github_ai_agents/src/github_ai_agents/board/config.py`
- `packages/github_ai_agents/src/github_ai_agents/board/models.py`
- `packages/github_ai_agents/tests/test_board_manager.py`

### Phase 2: Dependency Management (Week 1)

**Deliverables**:
1. Blocker relationship management
2. Parent-child (epic) relationships
3. "Discovered from" tracking
4. Dependency graph queries
5. Ready work detection algorithm

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/board/dependencies.py`
- `packages/github_ai_agents/src/github_ai_agents/board/queries.py`
- `packages/github_ai_agents/tests/test_dependencies.py`

### Phase 3: MCP Server (Week 2)

**Deliverables**:
1. MCP server implementation
2. All 8 core tools
3. HTTP mode support
4. Health checks and error handling
5. Integration tests

**Files**:
- `tools/mcp/github_board/__init__.py`
- `tools/mcp/github_board/server.py`
- `tools/mcp/github_board/docs/README.md`
- `tools/mcp/github_board/scripts/test_server.py`

### Phase 4: Monitor Integration (Week 2)

**Deliverables**:
1. Issue monitor auto-board addition
2. PR monitor status updates
3. Discovered work auto-filing
4. Agent assignment automation

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/monitors/issue.py` (updates)
- `packages/github_ai_agents/src/github_ai_agents/monitors/pr.py` (updates)
- `packages/github_ai_agents/tests/test_monitor_board_integration.py`

### Phase 5: CLI & Docker (Week 3)

**Deliverables**:
1. CLI tool for human interaction
2. Docker container setup
3. docker-compose integration
4. CI/CD pipeline updates
5. Documentation

**Files**:
- `packages/github_ai_agents/src/github_ai_agents/board/cli.py`
- `docker/github-board.Dockerfile`
- `docker-compose.yml` (updates)
- `.github/workflows/test-github-board.yml`
- `docs/integrations/github-board.md`

### Phase 6: Documentation & Polish (Week 3)

**Deliverables**:
1. Comprehensive README
2. API documentation
3. Usage examples for each agent
4. CLAUDE.md updates with board usage
5. Migration guide from manual issue tracking

**Files**:
- `packages/github_ai_agents/docs/board-integration.md`
- `CLAUDE.md` (updates)
- `packages/github_ai_agents/examples/board_usage.py`

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
    CLAIM_TIMEOUT = 1800  # 30 minutes in seconds
    CLAIM_COMMENT_PREFIX = "🤖 **[Agent Claim]**"

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

Claiming this issue for implementation. If this agent goes MIA, this claim expires after {self.CLAIM_TIMEOUT // 60} minutes.
"""
        await self._post_issue_comment(issue_number, comment_body)

        # Update board status
        await self.update_status(issue_number, "In Progress")
        await self.assign_to_agent(issue_number, agent_name)

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
        """Parse issue comments to find active claim."""
        comments = await self._get_issue_comments(issue_number)

        # Find most recent claim comment
        for comment in reversed(comments):
            if self.CLAIM_COMMENT_PREFIX in comment.body:
                # Parse claim metadata
                claim = self._parse_claim_comment(comment)

                # Check if released
                if not self._has_subsequent_release(comments, comment.created_at):
                    return claim

        return None
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

```python
async def cleanup_stale_claims(self):
    """
    Background task to clean up expired claims.

    Run this periodically (e.g., every 10 minutes) to:
    1. Find issues with expired claims
    2. Post expiration comment
    3. Reset status to "Todo"
    4. Unassign agent
    """
    all_issues = await self._query_issues(status=["In Progress"])

    for issue in all_issues:
        claim = await self._get_active_claim(issue.number)
        if not claim:
            continue

        claim_age = datetime.utcnow() - claim.timestamp
        if claim_age.total_seconds() >= self.CLAIM_TIMEOUT:
            logger.warning(f"Expiring stale claim on issue #{issue.number}")

            # Post expiration notice
            comment = f"""⚠️ **[Claim Expired]**

Agent `{claim.agent}` claim expired after {self.CLAIM_TIMEOUT // 60} minutes.
Releasing issue back to work queue.

Session ID: `{claim.session_id}`
"""
            await self._post_issue_comment(issue.number, comment)

            # Reset issue
            await self.update_status(issue.number, "Todo")
            await self.assign_to_agent(issue.number, None)
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
  timeout: 1800

  # Run cleanup task periodically
  cleanup_interval: 600  # 10 minutes

  # Allow stealing expired claims
  allow_steal: true

  # Require comment claim for all work
  enforce_claims: true
```

### Performance Considerations

1. **Caching**: Cache project structure and field IDs (1 hour TTL)
2. **Batch Operations**: Update multiple issues in single GraphQL call
3. **Rate Limiting**: Respect GitHub API limits (5000/hour for GraphQL)
4. **Pagination**: Handle projects with >100 issues
5. **Concurrent Agents**: Use optimistic locking with issue assignments

### Security

1. **Token Scope**: Requires `repo`, `read:org`, `write:org` permissions
2. **Agent Authorization**: Reuse existing `SecurityManager` from package
3. **Audit Trail**: GitHub Projects tracks all changes with timestamps
4. **Secrets**: Store token in environment variables, never in config

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

### Maintenance Checklist

- [ ] Update Python version requirements (3.11+)
- [ ] Audit and update dependencies
- [ ] Convert remaining sync I/O to async
- [ ] Add complete type annotations
- [ ] Write missing docstrings
- [ ] Add usage examples
- [ ] Improve test coverage to >80%
- [ ] Update all documentation
- [ ] Add CHANGELOG.md
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
| GitHub API rate limits | High | Medium | Implement caching, batch operations |
| GraphQL schema changes | Medium | Low | Version lock schema, monitor GitHub changelogs |
| Large project performance | Medium | Medium | Implement pagination, lazy loading |
| Concurrent agent conflicts | High | Medium | Optimistic locking, status check before assign |

### Organizational Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Manual board corruption | Medium | Low | Document agent-managed fields, add validation |
| GitHub service outages | High | Low | Graceful degradation, local cache fallback |
| Security token compromise | High | Low | Use fine-grained PATs, rotate regularly |

## Open Questions

1. **Board Creation**: Should package auto-create project board, or require manual setup?
   - **Recommendation**: Manual setup with helper script (safer)

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
    ├── test_server.py
    └── setup_project.py         # Helper to create GitHub Project

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

# Session 4: Stale claim scenario (agent crash)
issues = await board.query_ready_work(agent="crush")
# Returns: [Issue(#50: "Refactor database layer", status="Todo", blocks=[])]

session_id = uuid.uuid4().hex
await board.claim_work(50, agent="crush", session_id=session_id)

# Crush crashes 5 minutes in, never releases claim
# ...agent gone...

# 30 minutes later, cleanup task runs
await board.cleanup_stale_claims()
# Finds issue #50 with expired claim (>30 min old)
# Posts: "⚠️ [Claim Expired] Agent crush claim expired after 30 minutes"
# Resets status to "Todo", unassigns agent

# Now another agent can pick it up
issues = await board.query_ready_work(agent="opencode")
# Returns: [Issue(#50: "Refactor database layer", status="Todo", blocks=[])]
# Crush's stale claim has been cleared!
```

**Key Takeaways**:

1. **Claim Before Work**: Agents MUST claim before starting work
2. **Atomic Claiming**: First comment wins in race conditions
3. **Explicit Release**: Agents release claims with reason (completed/blocked/abandoned)
4. **Timeout Protection**: Crashed agents don't block work indefinitely
5. **Visible Audit**: All claim/release events visible in issue comments
6. **Context Preservation**: Claim history helps understand work evolution

## Appendix C: Comparison with Beads

| Feature | Beads | This Solution |
|---------|-------|---------------|
| **Storage** | Git-backed JSONL + SQLite | GitHub Projects v2 GraphQL |
| **Interface** | CLI (`bd`) | CLI + MCP Server + Web UI |
| **Deployment** | Local binary | Docker container + API |
| **Multi-Agent** | Via git merge | Native (centralized) |
| **Concurrency** | Merge conflict resolution | Comment-based mutex locks |
| **Work Claiming** | Implicit (via status) | Explicit (timestamped comments) |
| **Stale Lock Handling** | Manual intervention | Auto-expiration (30 min) |
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

---

**Document Version**: 1.0
**Last Updated**: 2025-10-25
**Status**: Draft for Review
**Next Steps**: Review → Implementation Phase 1 → Iteration
