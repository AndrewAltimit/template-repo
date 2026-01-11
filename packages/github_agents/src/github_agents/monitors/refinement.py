"""Backlog refinement monitor for multi-agent issue review.

This module orchestrates multiple AI agents reviewing backlog items
and posting unique insights as comments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
import logging
import re
from string import Template
from typing import Any, Dict, List, Optional

from ..agents import BaseAgent
from ..board.manager import BoardManager
from ..board.models import Issue
from ..memory.integration import MemoryIntegration
from ..utils import run_gh_command_async

logger = logging.getLogger(__name__)


@dataclass
class RefinementInsight:
    """Represents an insight from agent review."""

    agent_name: str
    issue_number: int
    content: str
    insight_type: str  # "implementation", "quality", "blocker", "decomposition"
    confidence: float  # 0.0-1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_comment_body(self) -> str:
        """Generate GitHub comment body."""
        return f"""### Insight from {self.agent_name.title()}

{self.content}

---
*Backlog refinement by {self.agent_name} on {self.timestamp.strftime("%Y-%m-%d")}*
*This is an automated analysis - human review recommended*

<!-- backlog-refinement:{self.agent_name}:{self.timestamp.strftime("%Y-%m-%d")}:{self._fingerprint()} -->
"""

    def _fingerprint(self) -> str:
        """Generate a fingerprint for this insight."""
        content = f"{self.agent_name}|{self.issue_number}|{self.content[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class IssueAction:
    """Represents an action to take on an issue."""

    action_type: str  # "close", "update_title", "update_body", "add_label", "remove_label", "link_pr"
    issue_number: int
    details: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    triggered_by: str = ""  # username who triggered this action
    executed: bool = False


@dataclass
class RefinementResult:
    """Result of refining a single issue."""

    issue_number: int
    issue_title: str
    insights_added: int = 0
    insights_skipped: int = 0
    agents_reviewed: List[str] = field(default_factory=list)
    actions_taken: List[IssueAction] = field(default_factory=list)
    error: Optional[str] = None


class RefinementMonitor:
    """Monitors and refines backlog items with multiple agents.

    This orchestrates the multi-agent backlog refinement process:
    1. Query TODO items from the board
    2. Filter by age and labels
    3. Have each agent review and provide insights
    4. Deduplicate insights against existing comments
    5. Post unique insights as comments
    """

    # Agent-specific prompts for different perspectives
    # Uses string.Template with $variable syntax to safely handle code in issue bodies
    AGENT_PROMPTS = {
        "claude": """Review this GitHub issue from an ARCHITECTURAL perspective.

Issue: $title
Description:
$body

Existing comments:
$comments

Consider:
1. Are there design patterns that would help implementation?
2. Are there existing utilities in the codebase that could be reused?
3. Are there potential breaking changes or migration needs?
4. What's the recommended implementation order if multiple components?

IMPORTANT: Only respond if you have a UNIQUE insight not already in the issue or comments.
If you have nothing new to add, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]
""",
        "gemini": """Review this GitHub issue for QUALITY and SECURITY considerations.

Issue: $title
Description:
$body

Existing comments:
$comments

Consider:
1. Are there security implications to be aware of?
2. Are there edge cases not mentioned in the issue?
3. What test scenarios should be covered?
4. Are there related issues that should be linked?

IMPORTANT: Only respond if you have a UNIQUE insight not already captured.
If everything is already covered, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]
""",
        "codex": """Review this GitHub issue from an IMPLEMENTATION perspective.

Issue: $title
Description:
$body

Existing comments:
$comments

Consider:
1. What's the estimated complexity (XS/S/M/L/XL)?
2. Are there performance considerations?
3. What dependencies or blockers exist?
4. Can you suggest a concrete implementation approach?

IMPORTANT: Only add if you have NEW information to contribute.
If the implementation path is already clear, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]
""",
        "opencode": """Review this GitHub issue for MAINTAINABILITY concerns.

Issue: $title
Description:
$body

Existing comments:
$comments

Consider:
1. Will this create technical debt?
2. Are there documentation requirements?
3. Does this need coordination with other systems?
4. Should this be broken into smaller issues?

IMPORTANT: Only add a comment if you have something UNIQUE to contribute.
If no new insights, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]
""",
    }

    # Prompt for analyzing issue and determining management actions
    ISSUE_MANAGEMENT_PROMPT = """Analyze issue #$issue_number and determine if any management actions should be taken.

Issue: $title
Current Description:
$body

Current Labels: $labels

$maintainer_section

$community_section

Based on the issue content and feedback, determine if any actions should be taken.

Available actions:
- close: Close the issue (if resolved, duplicate, won't fix, or clearly invalid)
- update_title: Change the issue title to be more descriptive/accurate
- update_body: Update the issue description to incorporate feedback or clarify
- add_label: Add a label (e.g., "bug", "enhancement", "good first issue", "duplicate", "wontfix")
- remove_label: Remove an incorrect or outdated label
- link_pr: Reference a related PR in a comment

PRIORITY GUIDELINES:
- Maintainer feedback (marked with **[MAINTAINER]**) should be given HIGHEST priority
- Clear consensus from multiple community members can also justify actions
- Your own analysis can suggest improvements (title clarity, missing labels, etc.)

If no action is needed, respond with exactly: NO_ACTION_NEEDED

If actions are needed, respond in this format (one action per line):
ACTION: <action_type>
DETAILS: <json details, e.g., {"title": "New Title"} or {"label": "bug"} or {"reason": "duplicate of #123"}>
REASON: <brief explanation of why this action is appropriate>
TRIGGERED_BY: <username whose feedback triggered this, or "agent_analysis" if your own recommendation>
---
"""

    # Comment marker pattern for tracking refinement
    REFINEMENT_MARKER_PATTERN = re.compile(r"<!-- backlog-refinement:(\w+):(\d{4}-\d{2}-\d{2}):(\w+) -->")

    # Maximum characters for issue body to prevent context window exhaustion
    MAX_BODY_LENGTH = 5000

    def __init__(
        self,
        repo: str,
        board_manager: Optional[BoardManager] = None,
        memory: Optional[MemoryIntegration] = None,
        agents: Optional[Dict[str, BaseAgent]] = None,
        min_age_days: int = 3,
        max_age_days: int = 90,
        exclude_labels: Optional[List[str]] = None,
        max_issues_per_run: int = 10,
        max_comments_per_issue: int = 2,
        agent_cooldown_days: int = 14,
        min_insight_length: int = 50,
        max_insight_length: int = 60000,  # GitHub limit is 65536, leave room for header/footer
        dry_run: bool = False,
        enable_issue_management: bool = False,
        maintainer_allow_list: Optional[List[str]] = None,
    ):
        """Initialize the refinement monitor.

        Args:
            repo: Repository in owner/repo format
            board_manager: Board manager for querying issues
            memory: Memory integration for similarity checking
            agents: Dict of agent name to agent instance
            min_age_days: Minimum issue age to review
            max_age_days: Maximum issue age to review
            exclude_labels: Labels to exclude from review
            max_issues_per_run: Maximum issues to review per run
            max_comments_per_issue: Maximum comments to add per issue
            agent_cooldown_days: Days before same agent can comment again
            min_insight_length: Minimum insight length to post
            max_insight_length: Maximum insight length to post
            dry_run: If True, don't post comments
            enable_issue_management: If True, allow agents to manage issues
            maintainer_allow_list: List of usernames who can trigger issue management
        """
        self.repo = repo
        self.board_manager = board_manager
        self.memory = memory
        self.agents = agents or {}
        self.min_age_days = min_age_days
        self.max_age_days = max_age_days
        self.exclude_labels = exclude_labels or ["blocked", "wontfix", "in-progress"]
        self.max_issues_per_run = max_issues_per_run
        self.max_comments_per_issue = max_comments_per_issue
        self.agent_cooldown_days = agent_cooldown_days
        self.min_insight_length = min_insight_length
        self.max_insight_length = max_insight_length
        self.dry_run = dry_run
        self.enable_issue_management = enable_issue_management
        self.maintainer_allow_list = maintainer_allow_list or self._load_allow_list()

    async def run(self, agent_names: Optional[List[str]] = None) -> List[RefinementResult]:
        """Run the refinement process.

        Args:
            agent_names: Specific agents to use (defaults to all configured)

        Returns:
            List of refinement results
        """
        # Determine which agents to use
        agents_to_use = agent_names or list(self.agents.keys())
        logger.info("Starting backlog refinement with agents: %s", agents_to_use)

        # Get issues to refine
        issues = await self._get_issues_to_refine()
        logger.info("Found %d issues to refine", len(issues))

        results: List[RefinementResult] = []

        for issue in issues[: self.max_issues_per_run]:
            result = await self._refine_issue(issue, agents_to_use)
            results.append(result)

        # Log summary
        total_insights = sum(r.insights_added for r in results)
        logger.info(
            "Refinement complete: %d issues reviewed, %d insights added",
            len(results),
            total_insights,
        )

        return results

    async def _get_issues_to_refine(self) -> List[Issue]:
        """Get issues from the board that need refinement.

        Returns:
            List of issues to refine
        """
        if not self.board_manager:
            # Fall back to gh CLI query
            return await self._query_issues_via_gh()

        try:
            # Query from board
            issues = await self.board_manager.get_ready_work(limit=100)

            # Filter by age and labels
            now = datetime.utcnow()
            filtered = []

            for issue in issues:
                # Check age bounds
                if hasattr(issue, "created_at") and issue.created_at:
                    age = (now - issue.created_at).days
                    if age < self.min_age_days or age > self.max_age_days:
                        continue

                # Check excluded labels
                issue_labels = getattr(issue, "labels", []) or []
                if any(label in issue_labels for label in self.exclude_labels):
                    continue

                filtered.append(issue)

            return filtered

        except Exception as e:
            logger.error("Failed to query board: %s", e)
            return []

    async def _query_issues_via_gh(self) -> List[Issue]:
        """Query issues directly via gh CLI.

        Returns:
            List of issues as Issue objects
        """
        cutoff_min = datetime.utcnow() - timedelta(days=self.max_age_days)
        cutoff_max = datetime.utcnow() - timedelta(days=self.min_age_days)

        cmd = [
            "issue",
            "list",
            "--repo",
            self.repo,
            "--state",
            "open",
            "--search",
            f"created:{cutoff_min.strftime('%Y-%m-%d')}..{cutoff_max.strftime('%Y-%m-%d')}",
            "--json",
            "number,title,body,labels,createdAt",
            "--limit",
            "100",
        ]

        result = await run_gh_command_async(cmd, check=False)

        if result is None:
            logger.error("gh issue list failed")
            return []

        try:
            data = json.loads(result)
            issues: List[Issue] = []
            for item in data:
                # Filter excluded labels
                labels = [lbl.get("name", "") for lbl in item.get("labels", [])]
                if any(label in labels for label in self.exclude_labels):
                    continue

                # Create Issue-like object
                issue = Issue(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body", ""),
                    state="open",
                    url=f"https://github.com/{self.repo}/issues/{item['number']}",
                )
                issues.append(issue)

            return issues

        except Exception as e:
            logger.error("Failed to parse issues: %s", e)
            return []

    async def _refine_issue(self, issue: Issue, agent_names: List[str]) -> RefinementResult:
        """Refine a single issue with multiple agents.

        Args:
            issue: The issue to refine
            agent_names: Names of agents to use

        Returns:
            Refinement result
        """
        result = RefinementResult(
            issue_number=issue.number,
            issue_title=issue.title,
        )

        # Get existing comments
        existing_comments = await self._get_issue_comments(issue.number)
        existing_refinements = self._extract_existing_refinements(existing_comments)

        comments_added = 0

        for agent_name in agent_names:
            if comments_added >= self.max_comments_per_issue:
                break

            # Check cooldown
            if self._is_agent_on_cooldown(agent_name, existing_refinements):
                logger.debug("Agent %s on cooldown for issue #%s", agent_name, issue.number)
                continue

            # Get agent
            agent = self.agents.get(agent_name)
            if not agent:
                logger.warning("Agent %s not available", agent_name)
                continue

            result.agents_reviewed.append(agent_name)

            # Get insight from agent (agent receives existing comments for context)
            insight = await self._get_agent_insight(agent, agent_name, issue, existing_comments)

            if not insight:
                result.insights_skipped += 1
                continue

            # Post the insight
            if await self._post_insight(insight):
                result.insights_added += 1
                comments_added += 1
            else:
                result.insights_skipped += 1

        # Issue management: analyze maintainer feedback and take actions
        if self.enable_issue_management and result.agents_reviewed:
            # Use the first available agent for issue management analysis
            first_agent_name = result.agents_reviewed[0]
            first_agent = self.agents.get(first_agent_name)
            if first_agent:
                await self._manage_issue(first_agent, issue, existing_comments, result)

        return result

    async def _get_issue_comments(self, issue_number: int) -> List[Dict[str, Any]]:
        """Get comments on an issue.

        Args:
            issue_number: The issue number

        Returns:
            List of comment dictionaries
        """
        cmd = [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            self.repo,
            "--json",
            "comments",
        ]

        result = await run_gh_command_async(cmd, check=False)

        if result is None:
            return []

        try:
            data = json.loads(result)
            comments: List[Dict[str, Any]] = data.get("comments", [])
            return comments
        except Exception:
            return []

    def _extract_existing_refinements(self, comments: List[Dict[str, Any]]) -> Dict[str, datetime]:
        """Extract existing refinement markers from comments.

        Args:
            comments: List of comment dictionaries

        Returns:
            Dict mapping agent name to last refinement date
        """
        refinements: Dict[str, datetime] = {}

        for comment in comments:
            body = comment.get("body", "")
            matches = self.REFINEMENT_MARKER_PATTERN.findall(body)
            for agent_name, date_str, _ in matches:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                if agent_name not in refinements or date > refinements[agent_name]:
                    refinements[agent_name] = date

        return refinements

    def _is_agent_on_cooldown(self, agent_name: str, existing_refinements: Dict[str, datetime]) -> bool:
        """Check if agent is on cooldown for this issue.

        Args:
            agent_name: The agent name
            existing_refinements: Dict of agent to last refinement date

        Returns:
            True if agent should skip this issue
        """
        if agent_name not in existing_refinements:
            return False

        last_refinement = existing_refinements[agent_name]
        cooldown = timedelta(days=self.agent_cooldown_days)

        return datetime.utcnow() - last_refinement < cooldown

    async def _get_agent_insight(
        self,
        agent: BaseAgent,
        agent_name: str,
        issue: Issue,
        existing_comments: List[Dict[str, Any]],
    ) -> Optional[RefinementInsight]:
        """Get an insight from an agent for an issue.

        Args:
            agent: The agent instance
            agent_name: Name of the agent
            issue: The issue to review
            existing_comments: Existing comments on the issue

        Returns:
            RefinementInsight if agent has unique insight, None otherwise
        """
        # Build prompt
        prompt_template = self.AGENT_PROMPTS.get(agent_name)
        if not prompt_template:
            logger.warning("No prompt template for agent %s", agent_name)
            return None

        # Format comments for context
        comment_text = "\n\n".join(
            f"- {c.get('author', {}).get('login', 'unknown')}: {c.get('body', '')[:200]}..."
            for c in existing_comments[-5:]  # Last 5 comments
        )

        # Truncate body to prevent context window exhaustion
        body = issue.body or "(no description)"
        if len(body) > self.MAX_BODY_LENGTH:
            body = body[: self.MAX_BODY_LENGTH] + f"\n... (truncated at {self.MAX_BODY_LENGTH} chars)"

        # Use safe_substitute to safely handle code with special chars in issue bodies
        prompt = Template(prompt_template).safe_substitute(
            title=issue.title,
            body=body,
            comments=comment_text or "(no comments)",
        )

        try:
            # Use review_async for analysis tasks (doesn't generate code)
            response = await agent.review_async(prompt)

            if "NO_NEW_INSIGHT" in response:
                return None

            # Parse response
            return self._parse_insight_response(response, agent_name, issue.number)

        except Exception as e:
            logger.error("Agent %s failed: %s", agent_name, e)
            return None

    def _parse_insight_response(self, response: str, agent_name: str, issue_number: int) -> Optional[RefinementInsight]:
        """Parse agent response into an insight.

        Args:
            response: Raw agent response
            agent_name: Name of the agent
            issue_number: The issue number

        Returns:
            Parsed insight or None if parsing fails
        """
        try:
            # Extract structured fields
            insight_type = "implementation"
            confidence = 0.7

            if "INSIGHT_TYPE:" in response:
                type_match = re.search(r"INSIGHT_TYPE:\s*(\w+)", response)
                if type_match:
                    insight_type = type_match.group(1).lower()

            if "CONFIDENCE:" in response:
                conf_match = re.search(r"CONFIDENCE:\s*([\d.]+)", response)
                if conf_match:
                    confidence = float(conf_match.group(1))

            # Extract insight content
            content = response
            if "INSIGHT:" in response:
                content = response.split("INSIGHT:", 1)[1].strip()

            # Clean up content
            content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
            content = content.strip()

            # Validate length
            if len(content) < self.min_insight_length:
                return None
            if len(content) > self.max_insight_length:
                content = content[: self.max_insight_length] + "..."

            return RefinementInsight(
                agent_name=agent_name,
                issue_number=issue_number,
                content=content,
                insight_type=insight_type,
                confidence=confidence,
            )

        except Exception as e:
            logger.error("Failed to parse insight: %s", e)
            return None

    async def _post_insight(self, insight: RefinementInsight) -> bool:
        """Post an insight as a comment.

        Args:
            insight: The insight to post

        Returns:
            True if posted successfully
        """
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would post insight from %s to #%s: %s...",
                insight.agent_name,
                insight.issue_number,
                insight.content[:50],
            )
            return True

        comment_body = insight.to_comment_body()

        cmd = [
            "issue",
            "comment",
            str(insight.issue_number),
            "--repo",
            self.repo,
            "--body",
            comment_body,
        ]

        result = await run_gh_command_async(cmd, check=False)

        if result is None:
            logger.error("Failed to post comment to issue #%s", insight.issue_number)
            return False

        logger.info(
            "Posted insight from %s to issue #%s",
            insight.agent_name,
            insight.issue_number,
        )
        return True

    def _load_allow_list(self) -> List[str]:
        """Load maintainer allow list from .agents.yaml.

        Returns:
            List of allowed usernames
        """
        import os

        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed, using empty allow list")
            return []

        # Try common locations for .agents.yaml
        possible_paths = [
            ".agents.yaml",
            os.path.join(os.getcwd(), ".agents.yaml"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".agents.yaml"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                        allow_list = config.get("security", {}).get("allow_list", [])
                        logger.info("Loaded %d maintainers from allow list", len(allow_list))
                        return list(allow_list) if allow_list else []
                except Exception as e:
                    logger.warning("Failed to load .agents.yaml: %s", e)

        logger.warning("No .agents.yaml found, using empty allow list")
        return []

    def _get_maintainer_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter comments to only those from maintainers.

        Args:
            comments: All comments on the issue

        Returns:
            Comments from users in the allow list
        """
        maintainer_comments = []
        for comment in comments:
            author = comment.get("author", {}).get("login", "")
            if author in self.maintainer_allow_list:
                maintainer_comments.append(comment)
        return maintainer_comments

    async def _analyze_for_actions(
        self,
        agent: BaseAgent,
        issue: Issue,
        all_comments: List[Dict[str, Any]],
    ) -> List[IssueAction]:
        """Analyze issue and comments for actionable management decisions.

        Args:
            agent: The agent to use for analysis
            issue: The issue being analyzed
            all_comments: All comments on the issue

        Returns:
            List of actions to take
        """
        # Separate maintainer and community comments
        maintainer_comments = []
        community_comments = []

        for comment in all_comments:
            author = comment.get("author", {}).get("login", "")
            if author in self.maintainer_allow_list:
                maintainer_comments.append(comment)
            else:
                community_comments.append(comment)

        # Format maintainer comments (with [MAINTAINER] tag for priority)
        if maintainer_comments:
            maintainer_text = "### Maintainer Feedback (HIGH PRIORITY)\n" + "\n\n".join(
                f"**[MAINTAINER] {c.get('author', {}).get('login', 'unknown')}** ({c.get('createdAt', 'unknown date')}):\n{c.get('body', '')}"
                for c in maintainer_comments[-5:]  # Last 5 maintainer comments
            )
        else:
            maintainer_text = "### Maintainer Feedback\n(No maintainer comments yet)"

        # Format community comments
        if community_comments:
            community_text = "### Community Comments\n" + "\n\n".join(
                f"**{c.get('author', {}).get('login', 'unknown')}** ({c.get('createdAt', 'unknown date')}):\n{c.get('body', '')[:500]}..."
                if len(c.get("body", "")) > 500
                else f"**{c.get('author', {}).get('login', 'unknown')}** ({c.get('createdAt', 'unknown date')}):\n{c.get('body', '')}"
                for c in community_comments[-10:]  # Last 10 community comments
            )
        else:
            community_text = "### Community Comments\n(No community comments yet)"

        # Get issue labels
        labels = getattr(issue, "labels", []) or []
        labels_text = ", ".join(labels) if labels else "(no labels)"

        # Build prompt
        body = issue.body or "(no description)"
        if len(body) > self.MAX_BODY_LENGTH:
            body = body[: self.MAX_BODY_LENGTH] + "..."

        prompt = Template(self.ISSUE_MANAGEMENT_PROMPT).safe_substitute(
            issue_number=issue.number,
            title=issue.title,
            body=body,
            labels=labels_text,
            maintainer_section=maintainer_text,
            community_section=community_text,
        )

        try:
            response = await agent.review_async(prompt)

            if "NO_ACTION_NEEDED" in response:
                return []

            return self._parse_action_response(response, issue.number)

        except Exception as e:
            logger.error("Failed to analyze for actions: %s", e)
            return []

    def _parse_action_response(self, response: str, issue_number: int) -> List[IssueAction]:
        """Parse agent response into actions.

        Args:
            response: Raw agent response
            issue_number: The issue number

        Returns:
            List of parsed actions
        """
        actions = []

        # Split by action delimiter
        action_blocks = response.split("---")

        for block in action_blocks:
            block = block.strip()
            if not block or "ACTION:" not in block:
                continue

            try:
                action_type = ""
                details = {}
                reason = ""
                triggered_by = ""

                for line in block.split("\n"):
                    line = line.strip()
                    if line.startswith("ACTION:"):
                        action_type = line.replace("ACTION:", "").strip().lower()
                    elif line.startswith("DETAILS:"):
                        details_str = line.replace("DETAILS:", "").strip()
                        try:
                            details = json.loads(details_str)
                        except json.JSONDecodeError:
                            details = {"raw": details_str}
                    elif line.startswith("REASON:"):
                        reason = line.replace("REASON:", "").strip()
                    elif line.startswith("TRIGGERED_BY:"):
                        triggered_by = line.replace("TRIGGERED_BY:", "").strip()

                if action_type:
                    actions.append(
                        IssueAction(
                            action_type=action_type,
                            issue_number=issue_number,
                            details=details,
                            reason=reason,
                            triggered_by=triggered_by,
                        )
                    )

            except Exception as e:
                logger.warning("Failed to parse action block: %s", e)

        return actions

    async def _execute_action(self, action: IssueAction) -> bool:
        """Execute a single action on an issue.

        Args:
            action: The action to execute

        Returns:
            True if executed successfully
        """
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would execute %s on #%s: %s (triggered by %s)",
                action.action_type,
                action.issue_number,
                action.reason,
                action.triggered_by,
            )
            action.executed = True
            return True

        try:
            if action.action_type == "close":
                return await self._close_issue(action)
            elif action.action_type == "update_title":
                return await self._update_issue_title(action)
            elif action.action_type == "update_body":
                return await self._update_issue_body(action)
            elif action.action_type == "add_label":
                return await self._add_label(action)
            elif action.action_type == "remove_label":
                return await self._remove_label(action)
            elif action.action_type == "link_pr":
                return await self._link_pr(action)
            else:
                logger.warning("Unknown action type: %s", action.action_type)
                return False

        except Exception as e:
            logger.error("Failed to execute action %s: %s", action.action_type, e)
            return False

    async def _close_issue(self, action: IssueAction) -> bool:
        """Close an issue."""
        reason = action.details.get("reason", action.reason)
        comment = f"Closing this issue based on maintainer feedback.\n\n**Reason:** {reason}\n\n*Automated action triggered by @{action.triggered_by}*"

        # Post comment explaining the close
        comment_cmd = [
            "issue",
            "comment",
            str(action.issue_number),
            "--repo",
            self.repo,
            "--body",
            comment,
        ]
        await run_gh_command_async(comment_cmd, check=False)

        # Close the issue
        cmd = [
            "issue",
            "close",
            str(action.issue_number),
            "--repo",
            self.repo,
        ]
        result = await run_gh_command_async(cmd, check=False)
        action.executed = result is not None
        return action.executed

    async def _update_issue_title(self, action: IssueAction) -> bool:
        """Update issue title."""
        new_title = action.details.get("title", "")
        if not new_title:
            return False

        cmd = [
            "issue",
            "edit",
            str(action.issue_number),
            "--repo",
            self.repo,
            "--title",
            new_title,
        ]
        result = await run_gh_command_async(cmd, check=False)
        action.executed = result is not None
        return action.executed

    async def _update_issue_body(self, action: IssueAction) -> bool:
        """Update issue body."""
        new_body = action.details.get("body", "")
        if not new_body:
            return False

        cmd = [
            "issue",
            "edit",
            str(action.issue_number),
            "--repo",
            self.repo,
            "--body",
            new_body,
        ]
        result = await run_gh_command_async(cmd, check=False)
        action.executed = result is not None
        return action.executed

    async def _add_label(self, action: IssueAction) -> bool:
        """Add a label to the issue."""
        label = action.details.get("label", "")
        if not label:
            return False

        cmd = [
            "issue",
            "edit",
            str(action.issue_number),
            "--repo",
            self.repo,
            "--add-label",
            label,
        ]
        result = await run_gh_command_async(cmd, check=False)
        action.executed = result is not None
        return action.executed

    async def _remove_label(self, action: IssueAction) -> bool:
        """Remove a label from the issue."""
        label = action.details.get("label", "")
        if not label:
            return False

        cmd = [
            "issue",
            "edit",
            str(action.issue_number),
            "--repo",
            self.repo,
            "--remove-label",
            label,
        ]
        result = await run_gh_command_async(cmd, check=False)
        action.executed = result is not None
        return action.executed

    async def _link_pr(self, action: IssueAction) -> bool:
        """Link a PR to the issue via comment."""
        pr_number = action.details.get("pr_number", "")
        pr_url = action.details.get("pr_url", "")

        if pr_number:
            link = f"#{pr_number}"
        elif pr_url:
            link = pr_url
        else:
            return False

        comment = f"Related PR: {link}\n\n*Automated link based on maintainer feedback (triggered by @{action.triggered_by})*"

        cmd = [
            "issue",
            "comment",
            str(action.issue_number),
            "--repo",
            self.repo,
            "--body",
            comment,
        ]
        result = await run_gh_command_async(cmd, check=False)
        action.executed = result is not None
        return action.executed

    async def _manage_issue(
        self,
        agent: BaseAgent,
        issue: Issue,
        existing_comments: List[Dict[str, Any]],
        result: RefinementResult,
    ) -> None:
        """Manage an issue based on analysis and feedback.

        The agent analyzes the issue and all comments to determine if any
        management actions should be taken. Maintainer comments are given
        higher priority, but actions can be taken based on community feedback
        or the agent's own analysis as well.

        Args:
            agent: The agent to use for analysis
            issue: The issue to manage
            existing_comments: All comments on the issue
            result: RefinementResult to update with actions
        """
        if not self.enable_issue_management:
            return

        # Log comment breakdown for visibility
        maintainer_comments = self._get_maintainer_comments(existing_comments)
        community_count = len(existing_comments) - len(maintainer_comments)

        logger.info(
            "Analyzing issue #%s for management actions (%d maintainer, %d community comments)",
            issue.number,
            len(maintainer_comments),
            community_count,
        )

        # Analyze for actions (pass all comments - method handles separation)
        actions = await self._analyze_for_actions(agent, issue, existing_comments)

        if not actions:
            logger.debug("No actions needed for issue #%s", issue.number)
            return

        logger.info("Identified %d actions for issue #%s", len(actions), issue.number)

        # Execute actions
        for action in actions:
            success = await self._execute_action(action)
            if success:
                result.actions_taken.append(action)
                logger.info(
                    "Executed %s on #%s: %s (triggered by: %s)",
                    action.action_type,
                    action.issue_number,
                    action.reason,
                    action.triggered_by,
                )
