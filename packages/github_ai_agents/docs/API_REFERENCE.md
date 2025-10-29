# API Reference - GitHub AI Agents

Complete Python API reference for the GitHub AI Agents package.

## Table of Contents

- [Board Module](#board-module)
  - [BoardManager](#boardmanager)
  - [BoardConfig](#boardconfig)
  - [Models](#models)
- [Monitors](#monitors)
  - [IssueMonitor](#issuemonitor)
  - [PRMonitor](#prmonitor)
- [Agents](#agents)
- [Security](#security)

---

## Board Module

The board module provides GitHub Projects v2 integration.

### BoardManager

Main interface for board operations.

**Location**: `github_ai_agents.board.manager.BoardManager`

#### Initialization

```python
from github_ai_agents.board.manager import BoardManager
from github_ai_agents.board.config import BoardConfig

# From config file
config = BoardConfig.from_file("ai-agents-board.yml")
manager = BoardManager(config=config, github_token="your_token")
await manager.initialize()

# From dict
config = BoardConfig.from_dict({
    "project": {"number": 1, "owner": "username"},
    "repository": "owner/repo",
    "fields": {"status": "Status", "priority": "Priority"}
})
manager = BoardManager(config=config, github_token="your_token")
await manager.initialize()
```

#### Methods

##### `initialize()`

Initialize the board manager and verify connectivity.

**Signature:**
```python
async def initialize(self) -> None
```

**Example:**
```python
await manager.initialize()
```

**Raises:**
- `BoardNotFoundError`: Project not found
- `GraphQLError`: API error

---

##### `get_ready_work()`

Get issues ready for work (unblocked, unclaimed).

**Signature:**
```python
async def get_ready_work(
    self,
    agent_name: str | None = None,
    limit: int = 10
) -> list[Issue]
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `agent_name` | `str \| None` | `None` | Filter by assigned agent |
| `limit` | `int` | `10` | Maximum issues to return |

**Returns:** `list[Issue]` - Ready issues

**Example:**
```python
# Get any ready work
issues = await manager.get_ready_work(limit=5)

# Filter by agent
issues = await manager.get_ready_work(agent_name="claude", limit=10)

# Process results
for issue in issues:
    print(f"#{issue.number}: {issue.title} (Priority: {issue.priority.value})")
```

---

##### `claim_work()`

Claim an issue to prevent conflicts.

**Signature:**
```python
async def claim_work(
    self,
    issue_number: int,
    agent_name: str,
    session_id: str
) -> bool
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue to claim |
| `agent_name` | `str` | Agent claiming work |
| `session_id` | `str` | Unique session identifier |

**Returns:** `bool` - `True` if claim successful, `False` if already claimed

**Example:**
```python
import uuid

session_id = str(uuid.uuid4())
success = await manager.claim_work(123, "claude", session_id)

if success:
    print("Claimed successfully!")
else:
    print("Already claimed by another agent")
```

---

##### `renew_claim()`

Renew claim for long-running tasks.

**Signature:**
```python
async def renew_claim(
    self,
    issue_number: int,
    agent_name: str,
    session_id: str
) -> bool
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue to renew |
| `agent_name` | `str` | Agent name |
| `session_id` | `str` | Current session ID |

**Returns:** `bool` - `True` if renewal successful

**Example:**
```python
# Renew claim every hour for long tasks
import asyncio

async def long_task(issue_number, agent, session_id):
    while working:
        # Do work...
        await asyncio.sleep(3600)  # 1 hour
        await manager.renew_claim(issue_number, agent, session_id)
```

---

##### `release_work()`

Release claim when done or blocked.

**Signature:**
```python
async def release_work(
    self,
    issue_number: int,
    agent_name: str,
    reason: str
) -> None
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue to release |
| `agent_name` | `str` | Agent name |
| `reason` | `str` | Release reason (`completed`, `blocked`, `abandoned`, `error`) |

**Example:**
```python
# Release as completed
await manager.release_work(123, "claude", "completed")

# Release as blocked
await manager.release_work(123, "claude", "blocked")

# Release on error
try:
    # Do work...
    pass
except Exception:
    await manager.release_work(123, "claude", "error")
    raise
```

---

##### `update_status()`

Update issue status.

**Signature:**
```python
async def update_status(
    self,
    issue_number: int,
    status: IssueStatus
) -> bool
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue to update |
| `status` | `IssueStatus` | New status |

**Returns:** `bool` - `True` if update successful

**Example:**
```python
from github_ai_agents.board.models import IssueStatus

# Mark as in progress
await manager.update_status(123, IssueStatus.IN_PROGRESS)

# Mark as done
await manager.update_status(123, IssueStatus.DONE)

# Mark as blocked
await manager.update_status(123, IssueStatus.BLOCKED)
```

---

##### `add_blocker()`

Add blocking dependency between issues.

**Signature:**
```python
async def add_blocker(
    self,
    issue_number: int,
    blocker_number: int
) -> bool
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue that is blocked |
| `blocker_number` | `int` | Issue that is blocking |

**Returns:** `bool` - `True` if blocker added

**Example:**
```python
# Issue #123 is blocked by #124
await manager.add_blocker(123, 124)

# Check if issue is ready (no open blockers)
issues = await manager.get_ready_work(limit=100)
is_ready = any(i.number == 123 for i in issues)
```

---

##### `mark_discovered_from()`

Mark parent-child relationship.

**Signature:**
```python
async def mark_discovered_from(
    self,
    issue_number: int,
    parent_number: int
) -> bool
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Child issue |
| `parent_number` | `int` | Parent issue |

**Returns:** `bool` - `True` if relationship added

**Example:**
```python
# Issue #125 was discovered while working on #123
await manager.mark_discovered_from(125, 123)

# Query parent/child relationships
graph = await manager.get_dependency_graph(123)
children = graph.children
```

---

##### `get_dependency_graph()`

Get dependency relationships for an issue.

**Signature:**
```python
async def get_dependency_graph(
    self,
    issue_number: int,
    depth: int = 3
) -> DependencyGraph
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `issue_number` | `int` | | Root issue |
| `depth` | `int` | `3` | Traversal depth |

**Returns:** `DependencyGraph` - Complete graph

**Example:**
```python
graph = await manager.get_dependency_graph(123, depth=5)

print(f"Root: #{graph.issue.number}")
print(f"Blocks: {[i.number for i in graph.blocks]}")
print(f"Blocked by: {[i.number for i in graph.blocked_by]}")
if graph.parent:
    print(f"Parent: #{graph.parent.number}")
print(f"Children: {[i.number for i in graph.children]}")
```

---

##### `create_issue_with_metadata()`

Create issue with board metadata.

**Signature:**
```python
async def create_issue_with_metadata(
    self,
    title: str,
    body: str,
    priority: IssuePriority | None = None,
    type: IssueType | None = None,
    size: IssueSize | None = None,
    agent: str | None = None
) -> Issue
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `title` | `str` | | Issue title |
| `body` | `str` | | Issue body |
| `priority` | `IssuePriority \| None` | `None` | Priority level |
| `type` | `IssueType \| None` | `None` | Issue type |
| `size` | `IssueSize \| None` | `None` | Estimated size |
| `agent` | `str \| None` | `None` | Assigned agent |

**Returns:** `Issue` - Created issue

**Example:**
```python
from github_ai_agents.board.models import IssuePriority, IssueType, IssueSize

issue = await manager.create_issue_with_metadata(
    title="Add dark mode",
    body="Implement dark mode toggle in settings",
    priority=IssuePriority.HIGH,
    type=IssueType.FEATURE,
    size=IssueSize.M,
    agent="claude"
)

print(f"Created issue #{issue.number}: {issue.title}")
print(f"URL: {issue.url}")
```

---

##### `assign_to_agent()`

Assign issue to agent.

**Signature:**
```python
async def assign_to_agent(
    self,
    issue_number: int,
    agent_name: str
) -> bool
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue to assign |
| `agent_name` | `str` | Agent name |

**Returns:** `bool` - `True` if assignment successful

**Example:**
```python
await manager.assign_to_agent(123, "claude")
```

---

##### `get_issue_context()`

Get full issue context including history.

**Signature:**
```python
async def get_issue_context(
    self,
    issue_number: int
) -> dict[str, Any]
```

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `issue_number` | `int` | Issue to query |

**Returns:** `dict` with keys:
- `issue`: Issue object
- `blockers`: List of blocking issues
- `discovered_during`: List of child issues
- `discovered_from`: Parent issue (optional)
- `claim_history`: List of AgentClaim objects

**Example:**
```python
context = await manager.get_issue_context(123)

issue = context["issue"]
blockers = context["blockers"]
claims = context["claim_history"]

print(f"Issue: #{issue.number} - {issue.title}")
print(f"Blockers: {len(blockers)}")
print(f"Claims: {len(claims)}")

for claim in claims:
    print(f"  {claim.timestamp}: {claim.agent}")
```

---

### BoardConfig

Configuration for board integration.

**Location**: `github_ai_agents.board.config.BoardConfig`

#### Initialization

```python
from github_ai_agents.board.config import BoardConfig

# From YAML file
config = BoardConfig.from_file("ai-agents-board.yml")

# From dictionary
config = BoardConfig.from_dict({
    "project": {
        "number": 1,
        "owner": "username"
    },
    "repository": "owner/repo",
    "fields": {
        "status": "Status",
        "priority": "Priority",
        "agent": "Agent"
    },
    "agents": {
        "enabled_agents": ["claude", "opencode"]
    }
})

# Direct construction
config = BoardConfig(
    project_number=1,
    owner="username",
    repository="owner/repo",
    field_mappings={"status": "Status"},
    enabled_agents=["claude"]
)
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `project_number` | `int` | GitHub Project number |
| `owner` | `str` | Project owner (user/org) |
| `repository` | `str` | Repository (owner/repo) |
| `field_mappings` | `dict[str, str]` | Custom field name mappings |
| `claim_timeout` | `int` | Claim timeout (seconds) |
| `claim_renewal_interval` | `int` | Renewal interval (seconds) |
| `enabled_agents` | `list[str]` | Enabled agent names |
| `auto_discover` | `bool` | Auto-file discovered issues |
| `exclude_labels` | `list[str]` | Labels to exclude |
| `priority_labels` | `dict[str, list[str]]` | Priority mappings |

---

### Models

Data models for board integration.

**Location**: `github_ai_agents.board.models`

#### Issue

Represents a GitHub issue with board metadata.

**Attributes:**
```python
@dataclass
class Issue:
    number: int                          # Issue number
    title: str                           # Issue title
    body: str                            # Issue body
    state: str                           # Issue state (open/closed)
    status: IssueStatus                  # Board status
    priority: IssuePriority              # Priority level
    type: IssueType | None               # Issue type
    size: IssueSize | None               # Estimated size
    agent: str | None                    # Assigned agent
    blocked_by: list[int]                # Blocker issue numbers
    discovered_from: int | None          # Parent issue
    created_at: datetime | None          # Creation time
    updated_at: datetime | None          # Last update
    url: str | None                      # Issue URL
    labels: list[str]                    # Label names
    project_item_id: str | None          # Board item ID
```

**Methods:**
```python
issue.is_ready() -> bool  # Check if ready (no blockers)
issue.is_claimed() -> bool  # Check if claimed
```

---

#### IssueStatus

Issue status enum.

```python
class IssueStatus(str, Enum):
    TODO = "Todo"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    DONE = "Done"
    ABANDONED = "Abandoned"
```

---

#### IssuePriority

Priority level enum.

```python
class IssuePriority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
```

---

#### IssueType

Issue type enum.

```python
class IssueType(str, Enum):
    FEATURE = "Feature"
    BUG = "Bug"
    TECH_DEBT = "Tech Debt"
    DOCUMENTATION = "Documentation"
```

---

#### IssueSize

Size estimation enum.

```python
class IssueSize(str, Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
```

---

#### AgentClaim

Represents agent ownership.

**Attributes:**
```python
@dataclass
class AgentClaim:
    issue_number: int
    agent: str
    session_id: str
    timestamp: datetime
    renewed_at: datetime | None = None
    released: bool = False
```

**Methods:**
```python
claim.age_seconds() -> float  # Age in seconds
claim.is_expired(timeout: int) -> bool  # Check if expired
```

---

#### DependencyGraph

Issue relationship graph.

**Attributes:**
```python
@dataclass
class DependencyGraph:
    issue: Issue                # Root issue
    blocks: list[Issue]         # Issues this blocks
    blocked_by: list[Issue]     # Issues blocking this
    children: list[Issue]       # Discovered sub-issues
    parent: Issue | None        # Parent issue
```

**Methods:**
```python
graph.is_ready() -> bool  # Check if all blockers resolved
graph.depth() -> int  # Depth in tree
```

---

## Monitors

### IssueMonitor

Monitor GitHub issues for trigger comments.

**Location**: `github_ai_agents.monitors.issue.IssueMonitor`

#### Usage

```python
from github_ai_agents.monitors import IssueMonitor

# Initialize
monitor = IssueMonitor()

# Process issues once
monitor.process_items()

# Run continuously
monitor.run_continuous(interval=300)  # 5 minutes
```

#### Board Integration

The monitor automatically integrates with the board:

```python
# Automatic board integration:
# 1. Claims work when [Approved][Agent] detected
# 2. Updates status to "In Progress"
# 3. Releases work when PR created ("completed")
# 4. Releases work on error ("error")
```

---

### PRMonitor

Monitor pull requests for review comments.

**Location**: `github_ai_agents.monitors.pr.PRMonitor`

#### Usage

```python
from github_ai_agents.monitors import PRMonitor

# Initialize
monitor = PRMonitor()

# Process PRs once
monitor.process_items()

# Run continuously
monitor.run_continuous(interval=300)
```

#### Board Integration

Updates board when PRs merge:

```python
# Automatic board integration:
# 1. Extracts linked issues from PR body
# 2. Updates status to "Done" when PR merges
# 3. Supports multiple linked issues
```

---

## Agents

### BaseAgent

Abstract base class for agents.

**Location**: `github_ai_agents.agents.base.BaseAgent`

#### Methods

```python
class BaseAgent:
    def is_available(self) -> bool:
        """Check if agent is available."""

    async def generate_code(self, prompt: str, context: dict) -> str:
        """Generate code based on prompt."""

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword (e.g., 'Claude')."""

    def get_capabilities(self) -> list[str]:
        """List agent capabilities."""
```

---

## Security

### SecurityManager

Manages security and authorization.

**Location**: `github_ai_agents.security.manager.SecurityManager`

#### Usage

```python
from github_ai_agents.security.manager import SecurityManager

# Initialize
security = SecurityManager()

# Check trigger
trigger_info = security.check_trigger_comment(issue, "issue")
if trigger_info:
    agent = trigger_info["agent"]
    user = trigger_info["user"]
    # Process...
```

---

## Error Handling

### Exceptions

```python
from github_ai_agents.board.errors import (
    BoardNotFoundError,
    GraphQLError,
    RateLimitError
)

try:
    await manager.initialize()
except BoardNotFoundError as e:
    print(f"Project not found: {e}")
except GraphQLError as e:
    print(f"API error: {e}")
except RateLimitError as e:
    print(f"Rate limited: {e}")
```

---

## Type Hints

All public APIs include full type hints:

```python
from github_ai_agents.board.manager import BoardManager
from github_ai_agents.board.models import Issue, IssueStatus

async def process_work(manager: BoardManager) -> None:
    issues: list[Issue] = await manager.get_ready_work(limit=5)
    for issue in issues:
        success: bool = await manager.claim_work(
            issue.number,
            "claude",
            "session-123"
        )
        if success:
            await manager.update_status(issue.number, IssueStatus.IN_PROGRESS)
```

---

## Async/Await

All I/O operations are async:

```python
import asyncio

async def main():
    manager = BoardManager(config, token)
    await manager.initialize()

    issues = await manager.get_ready_work(limit=10)
    # Process issues...

# Run
asyncio.run(main())
```

---

## See Also

- [Board Integration Guide](board-integration.md)
- [CLI Reference](CLI_REFERENCE.md)
- [Architecture Documentation](architecture.md)
- [Examples](../examples/)
