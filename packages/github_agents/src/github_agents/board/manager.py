"""GitHub Projects v2 board manager with GraphQL client."""

# pylint: disable=too-many-lines  # TODO: Extract GraphQL ops and claim management to separate modules

import asyncio
from datetime import datetime
import logging
import os
import re
from typing import Any, Callable

import aiohttp

from github_agents.board.config import load_config
from github_agents.board.errors import (
    BoardNotFoundError,
    GraphQLError,
    RateLimitError,
)
from github_agents.board.models import (
    AgentClaim,
    BoardConfig,
    GraphQLResponse,
    Issue,
    IssuePriority,
    IssueStatus,
    IssueType,
)

logger = logging.getLogger(__name__)


class BoardManager:
    """
    Manager for GitHub Projects v2 board operations.

    Provides methods for querying issues, managing claims, tracking dependencies,
    and coordinating work across AI agents.
    """

    # Constants
    GITHUB_API_URL = "https://api.github.com/graphql"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 60.0
    CLAIM_COMMENT_PREFIX = "🤖 **[Agent Claim]**"
    CLAIM_RENEWAL_PREFIX = "🔄 **[Claim Renewal]**"
    CLAIM_RELEASE_PREFIX = "🤖 **[Agent Release]**"

    def __init__(self, config: BoardConfig | None = None, github_token: str | None = None):
        """
        Initialize BoardManager.

        Args:
            config: Board configuration. If None, loads from file/env
            github_token: GitHub API token. If None, uses GITHUB_PROJECTS_TOKEN
                         or GITHUB_TOKEN env var (in that order)

        Raises:
            ValidationError: If configuration is invalid

        Note:
            GitHub Projects v2 requires a classic token with 'project' scope.
            Fine-grained tokens do not work with Projects v2 GraphQL API.
            Use GITHUB_PROJECTS_TOKEN for board operations and GITHUB_TOKEN
            for repository operations.
        """
        self.config = config or load_config()
        # Prefer GITHUB_PROJECTS_TOKEN (classic token for Projects v2)
        # Fall back to GITHUB_TOKEN for backward compatibility
        self.github_token = github_token or os.getenv("GITHUB_PROJECTS_TOKEN") or os.getenv("GITHUB_TOKEN")

        if not self.github_token:
            raise ValueError(
                "GitHub token required. Set GITHUB_PROJECTS_TOKEN environment variable "
                "(classic token with 'project' scope) or GITHUB_TOKEN"
            )

        self.session: aiohttp.ClientSession | None = None
        self.project_id: str | None = None  # Cached project ID

        logger.info("Initialized BoardManager for project #%s (owner: %s)", self.config.project_number, self.config.owner)

    async def __aenter__(self) -> "BoardManager":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def initialize(self) -> None:
        """Initialize HTTP session and load project metadata."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.github_token}",
                "Content-Type": "application/json",
            }
        )
        # Load and cache project ID
        self.project_id = await self._get_project_id()
        logger.info("Board initialized with project ID: %s", self.project_id)

    async def close(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    # ===== GraphQL Operations =====

    async def _execute_graphql(self, query: str, variables: dict[str, Any] | None = None) -> GraphQLResponse:
        """
        Execute GraphQL query with retry logic.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            GraphQLResponse object

        Raises:
            GraphQLError: If query fails after retries
            RateLimitError: If rate limit exceeded
        """
        if not self.session:
            raise RuntimeError("BoardManager not initialized. Use 'async with' or call initialize()")

        async def _execute() -> GraphQLResponse:
            payload: dict[str, Any] = {"query": query}
            if variables:
                payload["variables"] = variables

            # Type assertion: session is guaranteed to be not None here due to check above
            assert self.session is not None
            async with self.session.post(self.GITHUB_API_URL, json=payload) as response:
                data = await response.json()

                if response.status == 200:
                    return GraphQLResponse(data=data.get("data"), errors=data.get("errors", []), status_code=200)
                else:
                    return GraphQLResponse(data=None, errors=data.get("errors", []), status_code=response.status)

        result: GraphQLResponse = await self._execute_with_retry(_execute)
        return result

    def _check_rate_limit(self, response: Any) -> None:
        """Check for rate limit errors in response and raise if found."""
        if not hasattr(response, "errors"):
            return
        for error in response.errors:
            if "rate limit" in error.get("message", "").lower():
                raise RateLimitError()

    def _check_response_errors(self, response: Any) -> None:
        """Check for GraphQL errors that should be raised."""
        if not hasattr(response, "errors") or not response.errors:
            return
        # Only raise if we got errors AND no useful data
        if not response.data or not any(response.data.values()):
            error_msg = "; ".join(e.get("message", "") for e in response.errors)
            raise GraphQLError(error_msg, errors=response.errors)

    def _handle_client_error(self, error: GraphQLError) -> bool:
        """Handle client errors (4xx). Returns True if error should not be retried."""
        if not hasattr(error, "status_code") or not error.status_code:
            return False
        if not 400 <= error.status_code < 500:
            return False

        error_messages = {
            401: "Authentication failed - check GITHUB_TOKEN",
            403: "Forbidden - check permissions",
            404: "Resource not found",
        }
        if error.status_code in error_messages:
            logger.error(error_messages[error.status_code])
        return True

    async def _execute_with_retry(self, operation: Callable) -> Any:
        """
        Execute operation with exponential backoff retry.

        Args:
            operation: Async operation to execute

        Returns:
            Operation result

        Raises:
            GraphQLError: On permanent errors or max retries
            RateLimitError: On rate limit errors
        """
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await operation()
                self._check_rate_limit(response)
                self._check_response_errors(response)
                return response

            except RateLimitError:
                raise

            except GraphQLError as e:
                if self._handle_client_error(e):
                    raise

                if attempt < self.MAX_RETRIES - 1:
                    logger.warning("GraphQL error, retrying in %ss: %s", backoff, e)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    logger.error("Max retries exceeded: %s", e)
                    raise

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning("Network error, retrying in %ss: %s", backoff, e)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    logger.error("Max retries exceeded: %s", e)
                    raise GraphQLError(f"Operation failed after {self.MAX_RETRIES} retries: {e}") from e

    # ===== Project Operations =====

    async def _get_project_id(self) -> str:
        """
        Get GitHub Project ID from number.

        Returns:
            Project node ID

        Raises:
            BoardNotFoundError: If project not found
        """
        query = """
        query GetProject($owner: String!, $number: Int!) {
          user(login: $owner) {
            projectV2(number: $number) {
              id
              title
            }
          }
          organization(login: $owner) {
            projectV2(number: $number) {
              id
              title
            }
          }
        }
        """

        variables = {"owner": self.config.owner, "number": self.config.project_number}

        response = await self._execute_graphql(query, variables)

        # Try user first, then organization
        project = None
        if response.data and response.data.get("user"):
            project = response.data["user"].get("projectV2")
        if not project and response.data and response.data.get("organization"):
            project = response.data["organization"].get("projectV2")

        if not project:
            raise BoardNotFoundError(self.config.project_number, self.config.owner)

        project_id = project["id"]
        assert isinstance(project_id, str), "Project ID must be a string"
        return project_id

    # ===== Issue Operations =====

    def _parse_field_values(self, item: dict[str, Any]) -> dict[str, str]:
        """Parse field values from a project item.

        Args:
            item: Project item containing field values

        Returns:
            Dictionary mapping field names to their values
        """
        field_values: dict[str, str] = {}
        for field_value in item.get("fieldValues", {}).get("nodes", []):
            field_name = field_value.get("field", {}).get("name")
            if not field_name:
                continue
            if "name" in field_value:  # Single select
                field_values[field_name] = field_value["name"]
            elif "text" in field_value:  # Text
                field_values[field_name] = field_value["text"]
        return field_values

    def _parse_issue_metadata(
        self, field_values: dict[str, str]
    ) -> tuple[IssueStatus, IssuePriority, IssueType | None, str | None, list[int]]:
        """Parse issue metadata from field values.

        Args:
            field_values: Dictionary of field names to values

        Returns:
            Tuple of (status, priority, type, agent, blocked_by)
        """
        # Parse status
        status_str = field_values.get(self.config.field_mappings.get("status", "Status"))
        try:
            status = IssueStatus(status_str) if status_str else IssueStatus.TODO
        except ValueError:
            status = IssueStatus.TODO

        # Parse priority
        priority_str = field_values.get(self.config.field_mappings.get("priority", "Priority"))
        try:
            priority = IssuePriority(priority_str) if priority_str else IssuePriority.MEDIUM
        except ValueError:
            priority = IssuePriority.MEDIUM

        # Parse type
        type_str = field_values.get(self.config.field_mappings.get("type", "Type"))
        try:
            issue_type = IssueType(type_str) if type_str else None
        except ValueError:
            issue_type = None

        # Get assigned agent
        assigned_agent = field_values.get(self.config.field_mappings.get("agent", "Agent"))

        # Parse blocked_by field
        blocked_by_str = field_values.get(self.config.field_mappings.get("blocked_by", "Blocked By"), "")
        blocked_by: list[int] = []
        if blocked_by_str:
            try:
                blocked_by = [int(num.strip()) for num in blocked_by_str.split(",") if num.strip()]
            except ValueError:
                pass

        return status, priority, issue_type, assigned_agent, blocked_by

    def _parse_discovered_from(self, field_values: dict[str, str]) -> int | None:
        """Parse discovered_from field from field values.

        Args:
            field_values: Dictionary of field names to values

        Returns:
            Parent issue number or None
        """
        discovered_from_str = field_values.get(self.config.field_mappings.get("discovered_from", "Discovered From"), "")
        if discovered_from_str:
            try:
                return int(discovered_from_str.strip())
            except ValueError:
                pass
        return None

    def _create_issue_from_item(
        self,
        item: dict[str, Any],
        content: dict[str, Any],
        field_values: dict[str, str],
        status: IssueStatus,
        priority: IssuePriority,
        issue_type: IssueType | None,
        assigned_agent: str | None,
        blocked_by: list[int],
        discovered_from: int | None = None,
    ) -> Issue:
        """Create an Issue object from project item data.

        Args:
            item: Project item data
            content: Issue content data
            field_values: Parsed field values
            status: Issue status
            priority: Issue priority
            issue_type: Issue type
            assigned_agent: Assigned agent name
            blocked_by: List of blocking issue numbers
            discovered_from: Parent issue number if discovered from another issue

        Returns:
            Issue object
        """
        labels = [label["name"] for label in content.get("labels", {}).get("nodes", [])]

        return Issue(
            number=content["number"],
            title=content["title"],
            body=content.get("body", ""),
            state=content["state"].lower(),
            status=status,
            priority=priority,
            type=issue_type,
            agent=assigned_agent,
            blocked_by=blocked_by,
            discovered_from=discovered_from,
            created_at=datetime.fromisoformat(content["createdAt"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(content["updatedAt"].replace("Z", "+00:00")),
            url=content["url"],
            labels=labels,
            project_item_id=item["id"],
        )

    async def get_ready_work(self, agent_name: str | None = None, limit: int = 10) -> list[Issue]:
        """
        Get issues ready for work.

        Returns issues that are:
        1. In "Todo" or "Blocked" status (but blockers resolved)
        2. Not claimed by another agent (or claim expired)
        3. Have no open blockers
        4. Match agent filter if specified

        Args:
            agent_name: Filter by assigned agent (optional)
            limit: Maximum number of issues to return

        Returns:
            List of ready issues

        Raises:
            GraphQLError: If fetching issues fails
        """
        logger.info("Getting ready work (agent=%s, limit=%s)", agent_name, limit)

        # Fetch project items with issue data
        query = """
        query GetProjectItems($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                      title
                      body
                      state
                      createdAt
                      updatedAt
                      url
                      labels(first: 20) {
                        nodes {
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {"projectId": self.project_id}
        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("node"):
            raise GraphQLError("Failed to fetch project items")

        items = response.data["node"]["items"]["nodes"]
        ready_issues = []

        for item in items:
            content = item.get("content")
            if not content or content.get("state") != "OPEN":
                continue

            field_values = self._parse_field_values(item)
            status, priority, issue_type, assigned_agent, blocked_by = self._parse_issue_metadata(field_values)

            # Skip if not in Todo or Blocked status
            if status not in (IssueStatus.TODO, IssueStatus.BLOCKED):
                continue

            # Filter by agent if specified
            if agent_name and assigned_agent != agent_name:
                continue

            # Skip if has open blockers
            if blocked_by:
                continue

            # Check for active claim
            issue_number = content["number"]
            active_claim = await self._get_active_claim(issue_number)
            if active_claim and not active_claim.is_expired(self.config.claim_timeout):
                if agent_name and active_claim.agent != agent_name:
                    continue

            # Skip if has exclude labels
            labels = [label["name"] for label in content.get("labels", {}).get("nodes", [])]
            if any(label in self.config.exclude_labels for label in labels):
                continue

            issue = self._create_issue_from_item(
                item, content, field_values, status, priority, issue_type, assigned_agent, blocked_by
            )
            ready_issues.append(issue)

            if len(ready_issues) >= limit:
                break

        # Sort by priority (Critical > High > Medium > Low)
        priority_order = {
            IssuePriority.CRITICAL: 0,
            IssuePriority.HIGH: 1,
            IssuePriority.MEDIUM: 2,
            IssuePriority.LOW: 3,
        }
        ready_issues.sort(key=lambda issue: priority_order.get(issue.priority, 4))

        logger.info("Found %s ready issues", len(ready_issues))
        return ready_issues

    async def get_issue(self, issue_number: int) -> Issue | None:
        """
        Get a specific issue by number from the project board.

        Args:
            issue_number: Issue number to retrieve

        Returns:
            Issue if found on board, None otherwise

        Raises:
            GraphQLError: If fetching issue fails
        """
        logger.info("Getting issue #%s", issue_number)

        # Fetch project items with issue data
        query = """
        query GetProjectItems($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                      title
                      body
                      state
                      createdAt
                      updatedAt
                      url
                      labels(first: 10) {
                        nodes {
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "projectId": self.project_id,
        }

        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("node"):
            raise GraphQLError("Failed to fetch project items")

        items = response.data["node"]["items"]["nodes"]

        # Find the specific issue
        for item in items:
            content = item.get("content")
            if not content or content.get("number") != issue_number:
                continue

            field_values = self._parse_field_values(item)
            status, priority, issue_type, assigned_agent, blocked_by = self._parse_issue_metadata(field_values)
            discovered_from = self._parse_discovered_from(field_values)

            issue = self._create_issue_from_item(
                item, content, field_values, status, priority, issue_type, assigned_agent, blocked_by, discovered_from
            )

            logger.info("Found issue #%s: %s", issue_number, issue.title)
            return issue

        logger.warning("Issue #%s not found on board", issue_number)
        return None

    async def claim_work(self, issue_number: int, agent_name: str, session_id: str) -> bool:
        """
        Claim an issue for work.

        Posts a claim comment to the issue and updates board status.

        Args:
            issue_number: Issue to claim
            agent_name: Agent claiming the issue
            session_id: Unique session identifier

        Returns:
            True if claim successful, False if already claimed

        Raises:
            ClaimError: If claim operation fails
        """
        logger.info(
            "Claiming work",
            extra={
                "issue_number": issue_number,
                "issue_url": f"https://github.com/{self.config.repository}/issues/{issue_number}",
                "agent": agent_name,
                "session_id": session_id,
                "action": "claim_work",
            },
        )

        # Check for existing valid claim
        existing_claim = await self._get_active_claim(issue_number)
        if existing_claim:
            claim_age = existing_claim.age_seconds()
            if claim_age < self.config.claim_timeout:
                logger.info("Issue #%s already claimed by %s", issue_number, existing_claim.agent)
                return False
            else:
                logger.info("Stale claim expired on issue #%s, stealing", issue_number)

        # Post claim comment
        timeout_hours = self.config.claim_timeout // 3600
        comment_body = f"""{self.CLAIM_COMMENT_PREFIX}

Agent: `{agent_name}`
Started: `{datetime.utcnow().isoformat()}Z`
Session ID: `{session_id}`

Claiming this issue for implementation. If this agent goes MIA, this claim expires after {timeout_hours} hours.
"""

        await self._post_issue_comment(issue_number, comment_body)

        # Update board status
        await self.update_status(issue_number, IssueStatus.IN_PROGRESS)

        return True

    async def renew_claim(self, issue_number: int, agent_name: str, session_id: str) -> bool:
        """
        Renew an active claim for long-running tasks.

        Args:
            issue_number: Issue with active claim
            agent_name: Agent renewing the claim
            session_id: Session identifier

        Returns:
            True if renewal successful, False if no active claim or wrong agent
        """
        # Verify active claim belongs to this agent
        existing_claim = await self._get_active_claim(issue_number)
        if not existing_claim or existing_claim.agent != agent_name:
            logger.warning("Cannot renew claim on #%s: no active claim by %s", issue_number, agent_name)
            return False

        # Post renewal comment
        comment_body = f"""{self.CLAIM_RENEWAL_PREFIX}

Agent: `{agent_name}`
Renewed: `{datetime.utcnow().isoformat()}Z`
Session ID: `{session_id}`

Claim renewed - still actively working on this issue.
"""

        await self._post_issue_comment(issue_number, comment_body)
        logger.info("Renewed claim on #%s by %s", issue_number, agent_name)

        return True

    async def release_work(self, issue_number: int, agent_name: str, reason: str = "completed") -> None:
        """
        Release claim on an issue.

        Args:
            issue_number: Issue to release
            agent_name: Agent releasing the claim
            reason: Release reason (completed/blocked/abandoned)
        """
        comment_body = f"""{self.CLAIM_RELEASE_PREFIX}

Agent: `{agent_name}`
Released: `{datetime.utcnow().isoformat()}Z`
Reason: `{reason}`

Work claim released.
"""

        await self._post_issue_comment(issue_number, comment_body)

        # Update status based on reason
        if reason == "completed":
            await self.update_status(issue_number, IssueStatus.DONE)
        elif reason == "blocked":
            await self.update_status(issue_number, IssueStatus.BLOCKED)
        else:
            # Abandoned or error - return to todo
            await self.update_status(issue_number, IssueStatus.TODO)

        logger.info("Released claim on #%s by %s (reason: %s)", issue_number, agent_name, reason)

    async def update_status(self, issue_number: int, status: IssueStatus) -> bool:
        """
        Update issue status on board.

        Args:
            issue_number: Issue to update
            status: New status

        Returns:
            True if successful

        Raises:
            GraphQLError: If status update fails
        """
        # First, get the project item ID for this issue
        query = """
        query GetProjectItem($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                      repository {
                        owner {
                          login
                        }
                        name
                      }
                    }
                  }
                }
              }
              field(name: "Status") {
                ... on ProjectV2SingleSelectField {
                  id
                  options {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "projectId": self.project_id,
        }

        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("node"):
            raise GraphQLError(f"Failed to get project item for issue #{issue_number}")

        # Find the project item for this issue
        items = response.data["node"]["items"]["nodes"]
        project_item_id = None
        for item in items:
            content = item.get("content")
            if content and content.get("number") == issue_number:
                project_item_id = item["id"]
                break

        if not project_item_id:
            logger.warning("Issue #%s not found in project", issue_number)
            return False

        # Get the status field ID and option ID
        status_field = response.data["node"]["field"]
        if not status_field:
            raise GraphQLError("Status field not found in project")

        field_id = status_field["id"]
        status_option_id = None
        for option in status_field["options"]:
            if option["name"] == status.value:
                status_option_id = option["id"]
                break

        if not status_option_id:
            raise GraphQLError(f"Status option '{status.value}' not found")

        # Update the field value
        mutation = """
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item {
              id
            }
          }
        }
        """

        variables: dict[str, Any] = {  # type: ignore[no-redef]
            "projectId": self.project_id,
            "itemId": project_item_id,
            "fieldId": field_id,
            "value": {"singleSelectOptionId": status_option_id},
        }

        await self._execute_graphql(mutation, variables)
        logger.info("Updated issue #%s status to %s", issue_number, status.value)
        return True

    # ===== Claim Management =====

    async def _get_active_claim(self, issue_number: int) -> AgentClaim | None:
        """
        Get active claim for an issue.

        Parses issue comments to find most recent claim/renewal that hasn't been released.

        Args:
            issue_number: Issue to check

        Returns:
            AgentClaim if active claim exists, None otherwise

        Raises:
            GraphQLError: If fetching comments fails
        """
        # Fetch issue comments
        query = """
        query GetIssueComments($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              comments(last: 100) {
                nodes {
                  id
                  body
                  createdAt
                  author {
                    login
                  }
                }
              }
            }
          }
        }
        """

        owner, repo = self.config.repository.split("/")
        variables = {"owner": owner, "repo": repo, "number": issue_number}

        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("repository"):
            raise GraphQLError(f"Failed to get comments for issue #{issue_number}")

        comments = response.data["repository"]["issue"]["comments"]["nodes"]

        # Parse comments in reverse chronological order
        active_claim = None
        for comment in reversed(comments):
            body = comment.get("body", "")

            # Check for release first (invalidates claim)
            if self.CLAIM_RELEASE_PREFIX in body:
                return None

            # Check for renewal
            if self.CLAIM_RENEWAL_PREFIX in body:
                claim = self._parse_claim_comment(issue_number, body, comment["createdAt"])
                if claim:
                    active_claim = claim
                    # Update renewed_at timestamp
                    active_claim.renewed_at = datetime.fromisoformat(comment["createdAt"].replace("Z", "+00:00"))
                continue

            # Check for initial claim
            if self.CLAIM_COMMENT_PREFIX in body:
                claim = self._parse_claim_comment(issue_number, body, comment["createdAt"])
                if claim:
                    active_claim = claim
                break

        return active_claim

    def _parse_claim_comment(self, issue_number: int, body: str, created_at: str) -> AgentClaim | None:
        """
        Parse a claim comment to extract claim details.

        Args:
            issue_number: Issue number
            body: Comment body
            created_at: Comment timestamp (ISO 8601)

        Returns:
            AgentClaim if parsing successful, None otherwise
        """
        # Extract agent name
        agent_match = re.search(r"Agent:\s*`([^`]+)`", body)
        if not agent_match:
            return None

        # Extract session ID
        session_match = re.search(r"Session ID:\s*`([^`]+)`", body)
        if not session_match:
            return None

        # Extract timestamp (prefer Started, fall back to Renewed)
        timestamp_match = re.search(r"(?:Started|Renewed):\s*`([^`]+)`", body)
        if not timestamp_match:
            return None

        try:
            timestamp = datetime.fromisoformat(timestamp_match.group(1).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Failed to parse timestamp from claim comment: %s", timestamp_match.group(1))
            return None

        return AgentClaim(
            issue_number=issue_number,
            agent=agent_match.group(1),
            session_id=session_match.group(1),
            timestamp=timestamp,
        )

    async def _post_issue_comment(self, issue_number: int, body: str) -> None:
        """
        Post a comment to an issue.

        Args:
            issue_number: Issue number
            body: Comment body (markdown)

        Raises:
            GraphQLError: If comment creation fails
        """
        # First get the issue node ID
        query = """
        query GetIssueId($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              id
            }
          }
        }
        """

        owner, repo = self.config.repository.split("/")
        variables = {"owner": owner, "repo": repo, "number": issue_number}

        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("repository"):
            raise GraphQLError(f"Failed to get issue #{issue_number}")

        issue_id = response.data["repository"]["issue"]["id"]

        # Now post the comment
        mutation = """
        mutation AddComment($subjectId: ID!, $body: String!) {
          addComment(input: {subjectId: $subjectId, body: $body}) {
            commentEdge {
              node {
                id
                createdAt
              }
            }
          }
        }
        """

        variables = {"subjectId": issue_id, "body": body}
        await self._execute_graphql(mutation, variables)

        logger.debug("Posted comment to #%s: %s...", issue_number, body[:100])

    # ===== Dependency Management =====

    async def add_blocker(self, issue_number: int, blocker_number: int) -> bool:
        """
        Add blocker relationship.

        Updates the "Blocked By" field to include the blocker issue number.

        Args:
            issue_number: Issue that is blocked
            blocker_number: Issue that blocks

        Returns:
            True if successful

        Raises:
            GraphQLError: If update fails
        """
        logger.info("Adding blocker: #%s blocks #%s", blocker_number, issue_number)

        # Get current blocked_by value
        query = """
        query GetProjectItemForBlocker($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                    }
                  }
                }
              }
              field(name: "Blocked By") {
                ... on ProjectV2FieldCommon {
                  id
                }
              }
            }
          }
        }
        """

        variables = {
            "projectId": self.project_id,
        }

        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("node"):
            raise GraphQLError(f"Failed to get project item for issue #{issue_number}")

        # Find project item and current blocked_by value
        items = response.data["node"]["items"]["nodes"]
        project_item_id = None
        current_blocked_by = ""

        for item in items:
            content = item.get("content")
            if content and content.get("number") == issue_number:
                project_item_id = item["id"]
                # Find blocked_by field value
                for field_value in item.get("fieldValues", {}).get("nodes", []):
                    field_name = field_value.get("field", {}).get("name")
                    if field_name == self.config.field_mappings.get("blocked_by", "Blocked By"):
                        current_blocked_by = field_value.get("text", "")
                break

        if not project_item_id:
            logger.warning("Issue #%s not found in project", issue_number)
            return False

        # Add blocker to comma-separated list
        blocked_by_list = [num.strip() for num in current_blocked_by.split(",") if num.strip()]
        if str(blocker_number) not in blocked_by_list:
            blocked_by_list.append(str(blocker_number))
        new_blocked_by = ", ".join(blocked_by_list)

        # Get field ID
        field_id = response.data["node"]["field"]["id"]

        # Update field value
        mutation = """
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item {
              id
            }
          }
        }
        """

        variables: dict[str, Any] = {  # type: ignore[no-redef]
            "projectId": self.project_id,
            "itemId": project_item_id,
            "fieldId": field_id,
            "value": {"text": new_blocked_by},
        }

        await self._execute_graphql(mutation, variables)
        logger.info("Added blocker: #%s now blocks #%s", blocker_number, issue_number)
        return True

    async def mark_discovered_from(self, issue_number: int, parent_number: int) -> bool:
        """
        Mark issue as discovered from parent.

        Updates the "Discovered From" field with the parent issue number.

        Args:
            issue_number: Child issue
            parent_number: Parent issue

        Returns:
            True if successful

        Raises:
            GraphQLError: If update fails
        """
        logger.info("Marking #%s as discovered from #%s", issue_number, parent_number)

        # Get project item and field IDs
        query = """
        query GetProjectItemForDiscovery($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                    }
                  }
                }
              }
              field(name: "Discovered From") {
                ... on ProjectV2FieldCommon {
                  id
                }
              }
            }
          }
        }
        """

        variables = {
            "projectId": self.project_id,
        }

        response = await self._execute_graphql(query, variables)

        if not response.data or not response.data.get("node"):
            raise GraphQLError(f"Failed to get project item for issue #{issue_number}")

        # Find project item
        items = response.data["node"]["items"]["nodes"]
        project_item_id = None
        for item in items:
            content = item.get("content")
            if content and content.get("number") == issue_number:
                project_item_id = item["id"]
                break

        if not project_item_id:
            logger.warning("Issue #%s not found in project", issue_number)
            return False

        # Get field ID
        field_id = response.data["node"]["field"]["id"]

        # Update field value
        mutation = """
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item {
              id
            }
          }
        }
        """

        variables: dict[str, Any] = {  # type: ignore[no-redef]
            "projectId": self.project_id,
            "itemId": project_item_id,
            "fieldId": field_id,
            "value": {"text": str(parent_number)},
        }

        await self._execute_graphql(mutation, variables)
        logger.info("Marked #%s as discovered from #%s", issue_number, parent_number)
        return True

    async def create_issue_with_metadata(self, title: str, body: str = "", **metadata: Any) -> Issue:
        """
        Create a new issue with board metadata.

        Args:
            title: Issue title
            body: Issue body
            **metadata: Additional metadata (priority, type, agent, size, etc.)

        Returns:
            Created issue

        Raises:
            NotImplementedError: This method is not yet implemented
        """
        raise NotImplementedError("create_issue_with_metadata is not yet implemented")

    async def assign_to_agent(self, issue_number: int, agent_name: str) -> bool:
        """
        Assign an issue to an agent.

        Args:
            issue_number: Issue to assign
            agent_name: Agent to assign to

        Returns:
            True if assignment successful

        Raises:
            NotImplementedError: This method is not yet implemented
        """
        raise NotImplementedError("assign_to_agent is not yet implemented")

    async def get_dependency_graph(self, issue_number: int, depth: int = 3) -> Any:
        """
        Get full dependency graph for an issue.

        Args:
            issue_number: Issue to analyze
            depth: How many levels deep to traverse

        Returns:
            Dependency graph structure

        Raises:
            NotImplementedError: This method is not yet implemented
        """
        raise NotImplementedError("get_dependency_graph is not yet implemented")
