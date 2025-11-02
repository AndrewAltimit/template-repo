"""Data models for GitHub Projects v2 board integration."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IssueStatus(str, Enum):
    """Issue status values."""

    TODO = "Todo"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    DONE = "Done"
    ABANDONED = "Abandoned"


class IssuePriority(str, Enum):
    """Issue priority levels."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class IssueType(str, Enum):
    """Issue type categorization."""

    FEATURE = "Feature"
    BUG = "Bug"
    TECH_DEBT = "Tech Debt"
    DOCUMENTATION = "Documentation"


class IssueSize(str, Enum):
    """Issue size estimation."""

    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


@dataclass
class Issue:
    """
    Represents a GitHub issue with board metadata.

    Attributes:
        number: Issue number
        title: Issue title
        body: Issue body/description
        state: Issue state (open/closed)
        status: Board status (Todo, In Progress, etc.)
        priority: Issue priority
        type: Issue type
        size: Estimated size
        agent: Assigned agent name
        blocked_by: List of issue numbers blocking this issue
        discovered_from: Parent issue number
        created_at: Creation timestamp
        updated_at: Last update timestamp
        url: Issue URL
        labels: List of label names
        project_item_id: GitHub Projects v2 item ID
    """

    number: int
    title: str
    body: str
    state: str
    status: IssueStatus = IssueStatus.TODO
    priority: IssuePriority = IssuePriority.MEDIUM
    type: IssueType | None = None
    size: IssueSize | None = None
    agent: str | None = None
    blocked_by: list[int] = field(default_factory=list)
    discovered_from: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    url: str | None = None
    labels: list[str] = field(default_factory=list)
    project_item_id: str | None = None

    def is_ready(self) -> bool:
        """
        Check if issue is ready to work on.

        Returns:
            True if issue is in Todo status and has no blockers
        """
        return self.status == IssueStatus.TODO and len(self.blocked_by) == 0

    def is_claimed(self) -> bool:
        """
        Check if issue is claimed by an agent.

        Returns:
            True if agent is assigned
        """
        return self.agent is not None

    def __str__(self) -> str:
        """String representation."""
        return f"Issue #{self.number}: {self.title} ({self.status.value})"


@dataclass
class AgentClaim:
    """
    Represents an agent's claim on an issue.

    Attributes:
        issue_number: Issue being claimed
        agent: Agent name
        session_id: Unique session identifier
        timestamp: Claim timestamp
        renewed_at: Last renewal timestamp
        released: Whether claim was released
    """

    issue_number: int
    agent: str
    session_id: str
    timestamp: datetime
    renewed_at: datetime | None = None
    released: bool = False

    def age_seconds(self) -> float:
        """
        Calculate claim age in seconds.

        Returns:
            Age in seconds from most recent timestamp
        """
        from datetime import timezone

        reference_time = self.renewed_at if self.renewed_at else self.timestamp
        now = datetime.now(timezone.utc)
        return (now - reference_time).total_seconds()

    def is_expired(self, timeout_seconds: int) -> bool:
        """
        Check if claim has expired.

        Args:
            timeout_seconds: Claim timeout in seconds

        Returns:
            True if claim is older than timeout
        """
        return self.age_seconds() > timeout_seconds

    def __str__(self) -> str:
        """String representation."""
        renewed = f" (renewed {self.renewed_at})" if self.renewed_at else ""
        return f"Claim by {self.agent} on #{self.issue_number} at {self.timestamp}{renewed}"


@dataclass
class BoardConfig:
    """
    Configuration for GitHub Projects v2 board.

    Attributes:
        project_number: GitHub Project number
        owner: Project owner (user or org)
        repository: Repository name (owner/repo)
        field_mappings: Custom field name mappings
        claim_timeout: Claim timeout in seconds
        claim_renewal_interval: How often to renew claims
        enabled_agents: List of enabled agent names
        auto_discover: Auto-file discovered issues
        exclude_labels: Labels to exclude from work queue
        priority_labels: Label-to-priority mappings
    """

    project_number: int
    owner: str
    repository: str
    field_mappings: dict[str, str] = field(default_factory=dict)
    claim_timeout: int = 86400  # 24 hours
    claim_renewal_interval: int = 3600  # 1 hour
    enabled_agents: list[str] = field(default_factory=list)
    auto_discover: bool = True
    exclude_labels: list[str] = field(default_factory=list)
    priority_labels: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set default field mappings if not provided."""
        default_mappings = {
            "status": "Status",
            "priority": "Priority",
            "agent": "Agent",
            "type": "Type",
            "blocked_by": "Blocked By",
            "discovered_from": "Discovered From",
            "size": "Estimated Size",
        }
        for key, value in default_mappings.items():
            if key not in self.field_mappings:
                self.field_mappings[key] = value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BoardConfig":
        """
        Create BoardConfig from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            BoardConfig instance
        """
        project_data = data.get("project", {})
        fields = data.get("fields", {})
        agents_data = data.get("agents", {})
        work_queue = data.get("work_queue", {})
        claims = data.get("work_claims", {})

        return cls(
            project_number=project_data.get("number"),
            owner=project_data.get("owner"),
            repository=data.get("repository", ""),
            field_mappings=fields,
            claim_timeout=claims.get("timeout", 86400),
            claim_renewal_interval=claims.get("renewal_interval", 3600),
            enabled_agents=agents_data.get("enabled_agents", []),
            auto_discover=agents_data.get("auto_discover", True),
            exclude_labels=work_queue.get("exclude_labels", []),
            priority_labels=work_queue.get("priority_labels", {}),
        )


@dataclass
class DependencyGraph:
    """
    Represents dependency relationships between issues.

    Attributes:
        issue: The main issue
        blocks: Issues this issue blocks
        blocked_by: Issues blocking this issue
        children: Child issues (discovered from this)
        parent: Parent issue (this was discovered from)
    """

    issue: Issue
    blocks: list[Issue] = field(default_factory=list)
    blocked_by: list[Issue] = field(default_factory=list)
    children: list[Issue] = field(default_factory=list)
    parent: Issue | None = None

    def is_ready(self) -> bool:
        """
        Check if all blockers are resolved.

        Returns:
            True if all blocking issues are Done or Abandoned
        """
        if not self.blocked_by:
            return True
        return all(blocker.status in (IssueStatus.DONE, IssueStatus.ABANDONED) for blocker in self.blocked_by)

    def depth(self) -> int:
        """
        Calculate depth in dependency tree.

        Returns:
            Number of levels from root
        """
        if not self.parent:
            return 0
        return 1  # Simplified - full implementation would recursively check parent


@dataclass
class GraphQLResponse:
    """
    Response from GraphQL API.

    Attributes:
        data: Response data
        errors: List of errors
        status_code: HTTP status code
    """

    data: dict[str, Any] | None
    errors: list[dict[str, Any]] = field(default_factory=list)
    status_code: int = 200

    def is_success(self) -> bool:
        """Check if response was successful."""
        return self.status_code == 200 and not self.errors

    def get_error_message(self) -> str:
        """Get formatted error message."""
        if not self.errors:
            return ""
        return "; ".join(err.get("message", "Unknown error") for err in self.errors)
