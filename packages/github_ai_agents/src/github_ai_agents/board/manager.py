"""GitHub Projects v2 board manager with GraphQL client."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Callable

import aiohttp

from github_ai_agents.board.config import load_config
from github_ai_agents.board.errors import (
    BoardNotFoundError,
    GraphQLError,
    RateLimitError,
)
from github_ai_agents.board.models import (
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

        logger.info(f"Initialized BoardManager for project #{self.config.project_number} " f"(owner: {self.config.owner})")

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
        logger.info(f"Board initialized with project ID: {self.project_id}")

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

                # Check for rate limit
                if hasattr(response, "errors"):
                    for error in response.errors:
                        if "rate limit" in error.get("message", "").lower():
                            raise RateLimitError()

                # Check for errors (but only if no data was returned)
                # Note: GraphQL can return partial data with errors (e.g., querying both user and org)
                if hasattr(response, "errors") and response.errors:
                    if not response.data or not any(response.data.values()):
                        # Only raise if we got errors AND no useful data
                        error_msg = "; ".join(e.get("message", "") for e in response.errors)
                        raise GraphQLError(error_msg, errors=response.errors)
                    # else: have some data, errors are expected (e.g., one of user/org doesn't exist)

                return response

            except RateLimitError:
                raise  # Don't retry rate limit errors

            except GraphQLError as e:
                # Check HTTP status code if available
                if hasattr(e, "status_code") and e.status_code:
                    if 400 <= e.status_code < 500:
                        # Client errors - don't retry
                        if e.status_code == 401:
                            logger.error("Authentication failed - check GITHUB_TOKEN")
                        elif e.status_code == 403:
                            logger.error("Forbidden - check permissions")
                        elif e.status_code == 404:
                            logger.error("Resource not found")
                        raise

                # Retry on server errors
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"GraphQL error, retrying in {backoff}s: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    logger.error(f"Max retries exceeded: {e}")
                    raise

            except Exception as e:
                # Network errors - retry with backoff
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Network error, retrying in {backoff}s: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                else:
                    logger.error(f"Max retries exceeded: {e}")
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
        logger.info(f"Getting ready work (agent={agent_name}, limit={limit})")

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

            # Parse field values
            field_values = {}
            for field_value in item.get("fieldValues", {}).get("nodes", []):
                field_name = field_value.get("field", {}).get("name")
                if not field_name:
                    continue

                # Handle different field types
                if "name" in field_value:  # Single select
                    field_values[field_name] = field_value["name"]
                elif "text" in field_value:  # Text
                    field_values[field_name] = field_value["text"]

            # Parse status
            status_str = field_values.get(self.config.field_mappings.get("status", "Status"))
            try:
                status = IssueStatus(status_str) if status_str else IssueStatus.TODO
            except ValueError:
                status = IssueStatus.TODO

            # Skip if not in Todo or Blocked status
            if status not in (IssueStatus.TODO, IssueStatus.BLOCKED):
                continue

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

            # Filter by agent if specified
            if agent_name and assigned_agent != agent_name:
                continue

            # Parse blocked_by field (comma-separated issue numbers)
            blocked_by_str = field_values.get(self.config.field_mappings.get("blocked_by", "Blocked By"), "")
            blocked_by = []
            if blocked_by_str:
                try:
                    blocked_by = [int(num.strip()) for num in blocked_by_str.split(",") if num.strip()]
                except ValueError:
                    pass

            # Skip if has open blockers (simplified - full check would verify blocker status)
            if blocked_by:
                continue

            # Check for active claim
            issue_number = content["number"]
            active_claim = await self._get_active_claim(issue_number)
            if active_claim and not active_claim.is_expired(self.config.claim_timeout):
                # Skip if claimed by someone else
                if agent_name and active_claim.agent != agent_name:
                    continue

            # Parse labels
            labels = [label["name"] for label in content.get("labels", {}).get("nodes", [])]

            # Skip if has exclude labels
            if any(label in self.config.exclude_labels for label in labels):
                continue

            # Create Issue object
            issue = Issue(
                number=issue_number,
                title=content["title"],
                body=content.get("body", ""),
                state=content["state"].lower(),
                status=status,
                priority=priority,
                type=issue_type,
                agent=assigned_agent,
                blocked_by=blocked_by,
                created_at=datetime.fromisoformat(content["createdAt"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(content["updatedAt"].replace("Z", "+00:00")),
                url=content["url"],
                labels=labels,
                project_item_id=item["id"],
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

        logger.info(f"Found {len(ready_issues)} ready issues")
        return ready_issues

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
                logger.info(f"Issue #{issue_number} already claimed by {existing_claim.agent}")
                return False
            else:
                logger.info(f"Stale claim expired on issue #{issue_number}, stealing")

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
            logger.warning(f"Cannot renew claim on #{issue_number}: no active claim by {agent_name}")
            return False

        # Post renewal comment
        comment_body = f"""{self.CLAIM_RENEWAL_PREFIX}

Agent: `{agent_name}`
Renewed: `{datetime.utcnow().isoformat()}Z`
Session ID: `{session_id}`

Claim renewed - still actively working on this issue.
"""

        await self._post_issue_comment(issue_number, comment_body)
        logger.info(f"Renewed claim on #{issue_number} by {agent_name}")

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

        logger.info(f"Released claim on #{issue_number} by {agent_name} (reason: {reason})")

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
            logger.warning(f"Issue #{issue_number} not found in project")
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
        logger.info(f"Updated issue #{issue_number} status to {status.value}")
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
        import re

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
            logger.warning(f"Failed to parse timestamp from claim comment: {timestamp_match.group(1)}")
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

        logger.debug(f"Posted comment to #{issue_number}: {body[:100]}...")

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
        logger.info(f"Adding blocker: #{blocker_number} blocks #{issue_number}")

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
            logger.warning(f"Issue #{issue_number} not found in project")
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
        logger.info(f"Added blocker: #{blocker_number} now blocks #{issue_number}")
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
        logger.info(f"Marking #{issue_number} as discovered from #{parent_number}")

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
            logger.warning(f"Issue #{issue_number} not found in project")
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
        logger.info(f"Marked #{issue_number} as discovered from #{parent_number}")
        return True
