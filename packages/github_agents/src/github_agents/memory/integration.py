"""Memory integration for GitHub agents.

Provides high-level memory operations for Issue and PR monitors,
including context retrieval and pattern learning.
"""

import logging
from typing import Any, Dict, List, Optional

from .client import MemoryClient

logger = logging.getLogger(__name__)


class MemoryIntegration:
    """High-level memory integration for GitHub agents.

    Provides context-aware memory operations:
    - Store issue/PR context for future reference
    - Retrieve similar past issues/PRs
    - Learn and store patterns from implementations
    - Share knowledge across agents
    """

    # Namespace mappings for different memory types
    NAMESPACES = {
        "codebase_patterns": "codebase/patterns",
        "codebase_conventions": "codebase/conventions",
        "issue_context": "reviews/issues",
        "pr_context": "reviews/pr",
        "agent_claude": "agents/claude",
        "agent_gemini": "agents/gemini",
        "agent_opencode": "agents/opencode",
        "agent_crush": "agents/crush",
    }

    def __init__(self, agent_name: str = "github-agent"):
        """Initialize memory integration.

        Args:
            agent_name: Name of the agent using this integration
        """
        self.agent_name = agent_name
        self.client = MemoryClient()
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize and verify memory connection.

        Returns:
            True if memory is available, False otherwise
        """
        if self._initialized:
            return True

        try:
            healthy = await self.client.health_check()
            if healthy:
                logger.info("Memory integration initialized for %s", self.agent_name)
                self._initialized = True
            else:
                logger.warning("Memory service not healthy - continuing without memory")
            return healthy
        except Exception as e:
            logger.warning("Memory initialization failed: %s - continuing without memory", e)
            return False

    async def store_issue_context(
        self,
        issue_number: int,
        title: str,
        body: str,
        labels: List[str],
        outcome: Optional[str] = None,
    ) -> bool:
        """Store issue context for future reference.

        Args:
            issue_number: GitHub issue number
            title: Issue title
            body: Issue body/description
            labels: Issue labels
            outcome: Implementation outcome (if completed)

        Returns:
            True on success, False on error
        """
        if not self._initialized:
            return False

        # Create session ID from issue number
        session_id = f"issue-{issue_number}"

        # Store as event (short-term)
        content = f"Issue #{issue_number}: {title}\nLabels: {', '.join(labels)}\n{body[:500]}"
        if outcome:
            content += f"\nOutcome: {outcome}"

        result = await self.client.store_event(
            content=content,
            actor_id=self.agent_name,
            session_id=session_id,
        )

        return result is not None and result.get("success", False)

    async def store_pr_context(
        self,
        pr_number: int,
        title: str,
        body: str,
        files_changed: List[str],
        review_outcome: Optional[str] = None,
    ) -> bool:
        """Store PR context for future reference.

        Args:
            pr_number: GitHub PR number
            title: PR title
            body: PR body/description
            files_changed: List of changed files
            review_outcome: Review outcome (if completed)

        Returns:
            True on success, False on error
        """
        if not self._initialized:
            return False

        # Create session ID from PR number
        session_id = f"pr-{pr_number}"

        # Store as event (short-term)
        content = f"PR #{pr_number}: {title}\nFiles: {', '.join(files_changed[:10])}\n{body[:500]}"
        if review_outcome:
            content += f"\nReview: {review_outcome}"

        result = await self.client.store_event(
            content=content,
            actor_id=self.agent_name,
            session_id=session_id,
        )

        return result is not None and result.get("success", False)

    async def learn_pattern(
        self,
        pattern_type: str,
        pattern_description: str,
        source: str,
    ) -> bool:
        """Store a learned pattern for future reference.

        Args:
            pattern_type: Type of pattern ('codebase', 'review', 'implementation')
            pattern_description: Description of the pattern learned
            source: Source of the pattern (e.g., 'PR #42', 'Issue #15')

        Returns:
            True on success, False on error
        """
        if not self._initialized:
            return False

        namespace = self.NAMESPACES.get(f"codebase_{pattern_type}", "codebase/patterns")

        result = await self.client.store_facts(
            facts=[pattern_description],
            namespace=namespace,
            source=source,
        )

        return result is not None and result.get("success", False)

    async def get_similar_issues(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find similar past issues.

        Args:
            query: Search query (usually issue title + description)
            limit: Maximum results to return

        Returns:
            List of similar issues with relevance scores
        """
        if not self._initialized:
            return []

        result = await self.client.search_memories(
            query=query,
            namespace=self.NAMESPACES["issue_context"],
            top_k=limit,
        )

        if result and "memories" in result:
            memories: List[Dict[str, Any]] = result["memories"]
            return memories
        return []

    async def get_codebase_patterns(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant codebase patterns.

        Args:
            query: Search query related to the code task
            limit: Maximum results to return

        Returns:
            List of relevant patterns with relevance scores
        """
        if not self._initialized:
            return []

        result = await self.client.search_memories(
            query=query,
            namespace=self.NAMESPACES["codebase_patterns"],
            top_k=limit,
        )

        if result and "memories" in result:
            memories: List[Dict[str, Any]] = result["memories"]
            return memories
        return []

    async def get_conventions(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant coding conventions.

        Args:
            query: Search query related to conventions
            limit: Maximum results to return

        Returns:
            List of relevant conventions with relevance scores
        """
        if not self._initialized:
            return []

        result = await self.client.search_memories(
            query=query,
            namespace=self.NAMESPACES["codebase_conventions"],
            top_k=limit,
        )

        if result and "memories" in result:
            memories: List[Dict[str, Any]] = result["memories"]
            return memories
        return []

    async def build_context_prompt(
        self,
        task_description: str,
        include_patterns: bool = True,
        include_conventions: bool = True,
        include_similar: bool = True,
    ) -> str:
        """Build a context-enhanced prompt from memory.

        Args:
            task_description: Description of the task to perform
            include_patterns: Include relevant codebase patterns
            include_conventions: Include relevant conventions
            include_similar: Include similar past issues

        Returns:
            Context string to prepend to prompts
        """
        if not self._initialized:
            return ""

        context_parts = []

        # Get relevant patterns
        if include_patterns:
            patterns = await self.get_codebase_patterns(task_description, limit=3)
            if patterns:
                pattern_texts = [p["content"] for p in patterns if p.get("relevance", 0) > 0.3]
                if pattern_texts:
                    context_parts.append("**Relevant Patterns:**\n" + "\n".join(f"- {p}" for p in pattern_texts))

        # Get conventions
        if include_conventions:
            conventions = await self.get_conventions(task_description, limit=3)
            if conventions:
                conv_texts = [c["content"] for c in conventions if c.get("relevance", 0) > 0.3]
                if conv_texts:
                    context_parts.append("**Project Conventions:**\n" + "\n".join(f"- {c}" for c in conv_texts))

        # Get similar past issues
        if include_similar:
            similar = await self.get_similar_issues(task_description, limit=2)
            if similar:
                similar_texts = [s["content"] for s in similar if s.get("relevance", 0) > 0.4]
                if similar_texts:
                    context_parts.append("**Similar Past Issues:**\n" + "\n".join(f"- {s[:200]}..." for s in similar_texts))

        if context_parts:
            return "## Context from Memory\n\n" + "\n\n".join(context_parts) + "\n\n---\n\n"
        return ""
