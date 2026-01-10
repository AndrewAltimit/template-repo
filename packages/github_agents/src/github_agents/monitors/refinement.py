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
class RefinementResult:
    """Result of refining a single issue."""

    issue_number: int
    issue_title: str
    insights_added: int = 0
    insights_skipped: int = 0
    agents_reviewed: List[str] = field(default_factory=list)
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
    AGENT_PROMPTS = {
        "claude": """Review this GitHub issue from an ARCHITECTURAL perspective.

Issue: {title}
Description:
{body}

Existing comments:
{comments}

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

Issue: {title}
Description:
{body}

Existing comments:
{comments}

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

Issue: {title}
Description:
{body}

Existing comments:
{comments}

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

Issue: {title}
Description:
{body}

Existing comments:
{comments}

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

    # Comment marker pattern for tracking refinement
    REFINEMENT_MARKER_PATTERN = re.compile(r"<!-- backlog-refinement:(\w+):(\d{4}-\d{2}-\d{2}):(\w+) -->")

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
        similarity_threshold: float = 0.7,
        min_insight_length: int = 50,
        max_insight_length: int = 500,
        dry_run: bool = False,
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
            similarity_threshold: Threshold for insight deduplication
            min_insight_length: Minimum insight length to post
            max_insight_length: Maximum insight length to post
            dry_run: If True, don't post comments
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
        self.similarity_threshold = similarity_threshold
        self.min_insight_length = min_insight_length
        self.max_insight_length = max_insight_length
        self.dry_run = dry_run

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
            "gh",
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

            # Get insight from agent
            insight = await self._get_agent_insight(agent, agent_name, issue, existing_comments)

            if not insight:
                result.insights_skipped += 1
                continue

            # Check for similarity with existing insights
            if self._is_similar_to_existing(insight, existing_comments):
                result.insights_skipped += 1
                continue

            # Post the insight
            if await self._post_insight(insight):
                result.insights_added += 1
                comments_added += 1
            else:
                result.insights_skipped += 1

        return result

    async def _get_issue_comments(self, issue_number: int) -> List[Dict[str, Any]]:
        """Get comments on an issue.

        Args:
            issue_number: The issue number

        Returns:
            List of comment dictionaries
        """
        cmd = [
            "gh",
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

        prompt = prompt_template.format(
            title=issue.title,
            body=issue.body or "(no description)",
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

    def _is_similar_to_existing(self, insight: RefinementInsight, existing_comments: List[Dict[str, Any]]) -> bool:
        """Check if insight is too similar to existing comments.

        Args:
            insight: The insight to check
            existing_comments: Existing comments on the issue

        Returns:
            True if insight is too similar to existing
        """
        insight_words = set(insight.content.lower().split())

        for comment in existing_comments:
            body = comment.get("body", "").lower()
            comment_words = set(body.split())

            if not comment_words:
                continue

            # Calculate word overlap
            overlap = len(insight_words & comment_words)
            similarity = overlap / max(len(insight_words), len(comment_words))

            if similarity >= self.similarity_threshold:
                logger.debug("Insight too similar to existing comment (%.2f)", similarity)
                return True

        return False

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
            "gh",
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
