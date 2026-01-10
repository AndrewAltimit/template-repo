"""Issue creator for automated issue generation from analysis findings.

This module handles:
- Creating GitHub issues from analysis findings
- Deduplication against existing issues
- Adding issues to the project board
- Tracking creation history for metrics
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import List, Optional, Set

from ..analyzers.base import AnalysisFinding, FindingPriority
from ..board.manager import BoardManager
from ..memory.integration import MemoryIntegration
from ..utils import run_gh_command_async

logger = logging.getLogger(__name__)


@dataclass
class CreationResult:
    """Result of issue creation attempt."""

    finding: AnalysisFinding
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    created: bool = False
    skipped_reason: Optional[str] = None
    duplicate_of: Optional[int] = None


class IssueCreator:
    """Creates GitHub issues from analysis findings with deduplication.

    This class handles the full lifecycle of issue creation:
    1. Check for duplicates using fingerprints and semantic similarity
    2. Create the GitHub issue
    3. Apply labels
    4. Add to project board
    5. Store in memory for future deduplication
    """

    # Default labels for automated issues
    DEFAULT_LABELS = ["automated", "needs-review", "agentic-analysis"]

    # Priority to label mapping
    PRIORITY_LABELS = {
        FindingPriority.P0: "priority:critical",
        FindingPriority.P1: "priority:high",
        FindingPriority.P2: "priority:medium",
        FindingPriority.P3: "priority:low",
    }

    def __init__(
        self,
        repo: str,
        board_manager: Optional[BoardManager] = None,
        memory: Optional[MemoryIntegration] = None,
        lookback_days: int = 30,
        similarity_threshold: float = 0.8,
        min_priority: FindingPriority = FindingPriority.P3,
        max_issues_per_run: int = 5,
        dry_run: bool = False,
    ):
        """Initialize the issue creator.

        Args:
            repo: Repository in owner/repo format
            board_manager: Optional board manager for project integration
            memory: Optional memory integration for deduplication
            lookback_days: Days to look back for duplicate checking
            similarity_threshold: Semantic similarity threshold for duplicates
            min_priority: Minimum priority to create issues for
            max_issues_per_run: Maximum issues to create in one run
            dry_run: If True, don't actually create issues
        """
        self.repo = repo
        self.board_manager = board_manager
        self.memory = memory
        self.lookback_days = lookback_days
        self.similarity_threshold = similarity_threshold
        self.min_priority = min_priority
        self.max_issues_per_run = max_issues_per_run
        self.dry_run = dry_run

        self._created_count = 0
        self._known_fingerprints: Set[str] = set()

    async def create_issues(
        self,
        findings: List[AnalysisFinding],
    ) -> List[CreationResult]:
        """Create GitHub issues from findings.

        Args:
            findings: List of analysis findings

        Returns:
            List of creation results
        """
        results: List[CreationResult] = []

        # Load known fingerprints from existing issues
        await self._load_existing_fingerprints()

        # Sort by priority (P0 first)
        sorted_findings = sorted(
            findings,
            key=lambda f: list(FindingPriority).index(f.priority),
        )

        for finding in sorted_findings:
            if self._created_count >= self.max_issues_per_run:
                results.append(
                    CreationResult(
                        finding=finding,
                        skipped_reason="max_issues_per_run limit reached",
                    )
                )
                continue

            result = await self._process_finding(finding)
            results.append(result)

            if result.created:
                self._created_count += 1

        return results

    async def _process_finding(self, finding: AnalysisFinding) -> CreationResult:
        """Process a single finding for issue creation.

        Args:
            finding: The finding to process

        Returns:
            Creation result
        """
        # Check priority threshold
        priority_order = list(FindingPriority)
        if priority_order.index(finding.priority) > priority_order.index(self.min_priority):
            return CreationResult(
                finding=finding,
                skipped_reason=f"below min priority ({finding.priority.value})",
            )

        # Check fingerprint for exact duplicates
        fingerprint = finding.fingerprint()
        if fingerprint in self._known_fingerprints:
            return CreationResult(
                finding=finding,
                skipped_reason="exact duplicate (fingerprint match)",
            )

        # Check for semantic duplicates using memory
        if self.memory:
            duplicate = await self._check_semantic_duplicate(finding)
            if duplicate:
                return CreationResult(
                    finding=finding,
                    skipped_reason="semantic duplicate",
                    duplicate_of=duplicate,
                )

        # Create the issue
        if self.dry_run:
            logger.info("[DRY RUN] Would create issue: %s", finding.to_issue_title())
            return CreationResult(
                finding=finding,
                skipped_reason="dry run mode",
            )

        try:
            result = await self._create_github_issue(finding)
            if result.created:
                # Store fingerprint for future dedup
                self._known_fingerprints.add(fingerprint)
                await self._store_in_memory(finding, result.issue_number)
            return result
        except Exception as e:
            logger.error("Failed to create issue: %s", e)
            return CreationResult(
                finding=finding,
                skipped_reason=f"creation failed: {e}",
            )

    async def _create_github_issue(self, finding: AnalysisFinding) -> CreationResult:
        """Create a GitHub issue for the finding.

        Args:
            finding: The finding to create an issue for

        Returns:
            Creation result with issue details
        """
        title = finding.to_issue_title()
        body = finding.to_issue_body()

        # Build labels
        labels = self.DEFAULT_LABELS.copy()
        labels.append(f"category:{finding.category.value}")
        if finding.priority in self.PRIORITY_LABELS:
            labels.append(self.PRIORITY_LABELS[finding.priority])

        # Create issue via gh CLI
        cmd = [
            "gh",
            "issue",
            "create",
            "--repo",
            self.repo,
            "--title",
            title,
            "--body",
            body,
            "--label",
            ",".join(labels),
        ]

        result = await run_gh_command_async(cmd, check=False)

        if result is None:
            logger.error("gh issue create failed")
            return CreationResult(
                finding=finding,
                skipped_reason="gh command failed",
            )

        # Parse issue URL from output
        issue_url = result.strip()
        issue_number = int(issue_url.split("/")[-1]) if issue_url else None

        logger.info("Created issue #%s: %s", issue_number, title)

        # Add to project board if configured
        if self.board_manager and issue_number:
            try:
                await self.board_manager.update_status(issue_number, "Todo")
                logger.info("Added issue #%s to board", issue_number)
            except Exception as e:
                logger.warning("Failed to add to board: %s", e)

        return CreationResult(
            finding=finding,
            issue_number=issue_number,
            issue_url=issue_url,
            created=True,
        )

    async def _load_existing_fingerprints(self) -> None:
        """Load fingerprints from existing issues for deduplication."""
        try:
            # Query recent issues with our labels
            cutoff = datetime.utcnow() - timedelta(days=self.lookback_days)
            cutoff_str = cutoff.strftime("%Y-%m-%d")

            cmd = [
                "gh",
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "all",
                "--label",
                "agentic-analysis",
                "--search",
                f"created:>={cutoff_str}",
                "--json",
                "number,body",
                "--limit",
                "200",
            ]

            result = await run_gh_command_async(cmd, check=False)

            if result:
                import json

                issues = json.loads(result)
                for issue in issues:
                    body = issue.get("body", "")
                    # Extract fingerprint from body
                    if "analysis-fingerprint:" in body:
                        start = body.index("analysis-fingerprint:") + len("analysis-fingerprint:")
                        end = body.index("-->", start)
                        fingerprint = body[start:end].strip()
                        self._known_fingerprints.add(fingerprint)

                logger.info("Loaded %d existing fingerprints", len(self._known_fingerprints))

        except Exception as e:
            logger.warning("Failed to load existing fingerprints: %s", e)

    async def _check_semantic_duplicate(self, finding: AnalysisFinding) -> Optional[int]:
        """Check for semantically similar existing issues.

        Args:
            finding: The finding to check

        Returns:
            Issue number of duplicate if found, None otherwise
        """
        if not self.memory:
            return None

        try:
            # Search memory for similar findings
            query = f"{finding.category.value} {finding.title} {finding.summary}"
            results = await self.memory.get_similar_issues(query, limit=5)

            for result in results:
                if result.get("relevance", 0) >= self.similarity_threshold:
                    # Extract issue number from content
                    content = result.get("content", "")
                    if "Issue #" in content:
                        start = content.index("Issue #") + 7
                        end = content.index(":", start)
                        return int(content[start:end])

            return None

        except Exception as e:
            logger.warning("Semantic duplicate check failed: %s", e)
            return None

    async def _store_in_memory(self, finding: AnalysisFinding, issue_number: Optional[int]) -> None:
        """Store finding in memory for future reference.

        Args:
            finding: The finding that was created
            issue_number: The issue number that was created
        """
        if not self.memory or not issue_number:
            return

        try:
            await self.memory.store_issue_context(
                issue_number=issue_number,
                title=finding.title,
                body=f"{finding.category.value}: {finding.summary}",
                labels=[finding.category.value, finding.priority.value],
                outcome="created_by_analysis",
            )
        except Exception as e:
            logger.warning("Failed to store in memory: %s", e)
