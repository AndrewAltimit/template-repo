"""GitHub PR review monitoring with multi-agent support."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Type

from ..agents import ClaudeAgent, CodexAgent, CrushAgent, GeminiAgent, OpenCodeAgent
from ..code_parser import CodeParser
from ..config import AgentConfig
from ..security import SecurityManager
from ..utils import get_github_token, run_gh_command

logger = logging.getLogger(__name__)


class PRMonitor:
    """Monitor GitHub PRs and handle review feedback."""

    def __init__(self):
        """Initialize PR monitor."""
        self.repo = os.environ.get("GITHUB_REPOSITORY")
        if not self.repo:
            raise RuntimeError("GITHUB_REPOSITORY environment variable must be set")

        self.token = get_github_token()
        self.config = AgentConfig()
        self.security_manager = SecurityManager(agent_config=self.config)
        self.agent_tag = "[AI Agent]"

        # Initialize available agents based on configuration
        self.agents = self._initialize_agents()

    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize available AI agents based on configuration."""
        agents = {}

        # Map agent names to classes
        agent_map: Dict[str, Type[Any]] = {
            "claude": ClaudeAgent,
            "gemini": GeminiAgent,
            "opencode": OpenCodeAgent,
            "codex": CodexAgent,
            "crush": CrushAgent,
        }

        # Only initialize enabled agents
        enabled_agents = self.config.get_enabled_agents()

        for agent_name in enabled_agents:
            if agent_name in agent_map:
                agent_class = agent_map[agent_name]
                try:
                    agent = agent_class(config=self.config)
                    if agent.is_available():
                        keyword = agent.get_trigger_keyword()
                        agents[keyword.lower()] = agent
                        logger.info(f"Initialized {keyword} agent")
                except Exception as e:
                    logger.warning(f"Failed to initialize {agent_class.__name__}: {e}")

        return agents

    def get_open_prs(self) -> List[Dict]:
        """Get open PRs from the repository."""
        output = run_gh_command(
            [
                "pr",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,updatedAt,labels,reviews,comments,headRefName",
            ]
        )

        if output:
            try:
                prs = json.loads(output)
                # Filter by recent activity (24 hours)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                recent_prs = []

                for pr in prs:
                    updated_at = datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00"))
                    if updated_at >= cutoff:
                        recent_prs.append(pr)

                return recent_prs
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse PRs: {e}")

        return []

    def process_prs(self):
        """Process open PRs."""
        logger.info(f"Processing PRs for repository: {self.repo}")

        prs = self.get_open_prs()
        logger.info(f"Found {len(prs)} recent open PRs")

        for pr in prs:
            self._process_single_pr(pr)

    def _process_single_pr(self, pr: Dict):
        """Process a single PR."""
        pr_number = pr["number"]
        branch_name = pr.get("headRefName", "")

        # Get detailed review comments
        review_comments = self._get_review_comments(pr_number)
        if not review_comments:
            return

        # Check each review comment for triggers
        for comment in review_comments:
            trigger_info = self._check_review_trigger(comment)
            if not trigger_info:
                continue

            action, agent_name, trigger_user = trigger_info
            logger.info(f"PR #{pr_number}: [{action}][{agent_name}] by {trigger_user}")

            # Security check
            is_allowed, reason = self.security_manager.perform_full_security_check(
                username=trigger_user,
                action=f"pr_{action.lower()}",
                repository=self.repo,
                entity_type="pr",
                entity_id=str(pr_number),
            )

            if not is_allowed:
                logger.warning(f"Security check failed for PR #{pr_number}: {reason}")
                self._post_security_rejection(pr_number, reason)
                continue

            # Check if we already responded to this specific comment
            comment_id = comment.get("id")
            if comment_id and self._has_responded_to_comment(pr_number, comment_id):
                logger.info(f"Already responded to comment {comment_id} on PR #{pr_number}")
                continue

            # Handle the action
            if action.lower() in ["fix", "address", "implement"]:
                self._handle_review_feedback(pr, comment, agent_name, branch_name)

    def _get_review_comments(self, pr_number: int) -> List[Dict]:
        """Get review comments for a PR."""
        # Get PR reviews
        reviews_output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "reviews",
            ]
        )

        # Get issue comments (PR comments)
        comments_output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        all_comments = []

        # Process reviews
        if reviews_output:
            try:
                data = json.loads(reviews_output)
                for review in data.get("reviews", []):
                    if review.get("body"):
                        all_comments.append(
                            {
                                "id": review.get("id"),
                                "body": review["body"],
                                "author": review.get("author", {}).get("login", "unknown"),
                                "createdAt": review.get("submittedAt"),
                                "type": "review",
                            }
                        )
            except json.JSONDecodeError:
                pass

        # Process comments
        if comments_output:
            try:
                data = json.loads(comments_output)
                for comment in data.get("comments", []):
                    all_comments.append(
                        {
                            "id": comment.get("id"),
                            "body": comment.get("body", ""),
                            "author": comment.get("author", {}).get("login", "unknown"),
                            "createdAt": comment.get("createdAt"),
                            "type": "comment",
                        }
                    )
            except json.JSONDecodeError:
                pass

        return all_comments

    def _check_review_trigger(self, comment: Dict) -> Optional[Tuple[str, str, str]]:
        """Check if comment contains a trigger command.

        Returns:
            Tuple of (action, agent_name, username) if trigger found, None otherwise
        """
        body = comment.get("body", "")
        author = comment.get("author", "unknown")

        # Pattern: [Action][Agent]
        import re

        pattern = r"\[(\w+)\]\[(\w+)\]"
        matches = re.findall(pattern, body)

        if matches:
            action, agent_name = matches[0]
            return (action, agent_name, author)

        return None

    def _handle_review_feedback(self, pr: Dict, comment: Dict, agent_name: str, branch_name: str):
        """Handle PR review feedback with specified agent."""
        pr_number = pr["number"]

        # Get the agent
        agent = self.agents.get(agent_name.lower())
        if not agent:
            # Check if this is a containerized agent running on host
            containerized_agents = ["opencode", "codex", "crush"]
            if agent_name.lower() in containerized_agents:
                error_msg = (
                    f"Agent '{agent_name}' is only available in the containerized environment.\n\n"
                    f"Due to authentication constraints:\n"
                    f"- Claude requires host-specific authentication and must run on the host\n"
                    f"- {agent_name} is containerized and not installed on the host\n\n"
                    f"**Workaround**: Use one of the available host agents instead:\n"
                    f"- {', '.join([f'[Fix][{k.title()}]' for k in self.agents.keys()])}\n\n"
                    f"Or manually run the containerized agent:\n"
                    f"```bash\n"
                    f"docker-compose --profile agents run --rm openrouter-agents \\\n"
                    f"  python -m github_ai_agents.cli pr-monitor\n"
                    f"```"
                )
            else:
                error_msg = f"Agent '{agent_name}' is not available. Available agents: {list(self.agents.keys())}"

            logger.error(f"Agent '{agent_name}' not available")
            self._post_error_comment(pr_number, error_msg)
            return

        # Post starting work comment
        comment_id = comment.get("id", "unknown")
        self._post_starting_work_comment(pr_number, agent_name, comment_id)

        # Run implementation asynchronously
        try:
            asyncio.run(self._implement_review_feedback(pr, comment, agent, branch_name))
        except Exception as e:
            logger.error(f"Failed to address review feedback for PR #{pr_number}: {e}")
            self._post_error_comment(pr_number, str(e))

    async def _implement_review_feedback(self, pr: Dict, comment: Dict, agent, branch_name: str):
        """Implement review feedback using specified agent."""
        pr_number = pr["number"]
        pr_title = pr["title"]
        review_body = comment.get("body", "")

        # Get PR diff to understand current changes
        diff_output = run_gh_command(
            [
                "pr",
                "diff",
                str(pr_number),
                "--repo",
                self.repo,
            ]
        )

        # Create implementation prompt
        prompt = f"""
Address the following review feedback on PR #{pr_number}: {pr_title}

Review Comment:
{review_body}

Current PR Diff:
{diff_output[:5000] if diff_output else "No diff available"}  # Limit diff size

Requirements:
1. Address all the specific feedback points
2. Maintain existing code style and patterns
3. Ensure changes don't break existing functionality
4. Update tests if needed
"""

        # Generate implementation
        context = {
            "pr_number": pr_number,
            "pr_title": pr_title,
            "branch_name": branch_name,
            "review_comment_id": comment.get("id"),
        }

        try:
            response = await agent.generate_code(prompt, context)
            logger.info(f"Agent {agent.name} generated response for PR #{pr_number}")

            # Apply the changes
            self._apply_review_fixes(pr, agent.name, response, branch_name, context["review_comment_id"])

        except Exception as e:
            logger.error(f"Agent {agent.name} failed: {e}")
            raise

    def _apply_review_fixes(self, pr: Dict, agent_name: str, implementation: str, branch_name: str, comment_id: str):
        """Apply review fixes to the PR branch."""
        pr_number = pr["number"]

        try:
            # 1. Fetch and checkout the PR branch
            logger.info(f"Checking out PR branch: {branch_name}")
            run_gh_command(["pr", "checkout", str(pr_number), "--repo", self.repo])

            # 2. Apply the code changes
            # Parse and apply the code changes from the AI response
            blocks, results = CodeParser.extract_and_apply(implementation)

            if results:
                logger.info(f"Applied {len(results)} file changes:")
                for filename, operation in results.items():
                    logger.info(f"  - {filename}: {operation}")
            else:
                logger.warning("No code changes were extracted from the AI response")

            # 3. Commit the changes
            commit_message = (
                f"fix: address review feedback using {agent_name}\n\n"
                f"Automated fix generated by {agent_name} AI agent in response to review feedback.\n\n"
                f"🤖 Generated with AI Agent Automation System"
            )

            # Check if there are changes to commit
            status_output = run_gh_command(["status", "--porcelain"])
            if status_output and status_output.strip():
                run_gh_command(["add", "-A"])
                run_gh_command(["commit", "-m", commit_message])

                # 4. Push to the branch
                logger.info(f"Pushing changes to branch: {branch_name}")
                run_gh_command(["push"])

                success_comment = (
                    f"{self.agent_tag} I've successfully addressed the review feedback using {agent_name}!\n\n"
                    f"✅ Changes have been committed and pushed to the branch: `{branch_name}`\n\n"
                    f"Commit message: {commit_message.splitlines()[0]}\n\n"
                    f"This addresses review comment {comment_id}.\n\n"
                    f"Please review the updates.\n\n"
                    f"*This comment was generated by the AI agent automation system.*\n"
                    f"<!-- ai-agent-response-to:{comment_id} -->"
                )
            else:
                logger.info("No changes to commit")
                success_comment = (
                    f"{self.agent_tag} I've analyzed the review feedback using {agent_name}.\n\n"
                    f"ℹ️ No code changes were necessary based on the review comments.\n\n"
                    f"This addresses review comment {comment_id}.\n\n"
                    f"*This comment was generated by the AI agent automation system.*\n"
                    f"<!-- ai-agent-response-to:{comment_id} -->"
                )

        except Exception as e:
            logger.error(f"Failed to apply review fixes: {e}")
            success_comment = (
                f"{self.agent_tag} I attempted to address the review feedback using {agent_name} but encountered an error.\n\n"
                f"❌ Error: {str(e)}\n\n"
                f"This was in response to review comment {comment_id}.\n\n"
                f"Please check the logs for more details.\n\n"
                f"*This comment was generated by the AI agent automation system.*\n"
                f"<!-- ai-agent-response-to:{comment_id} -->"
            )

        # Post completion comment
        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                success_comment,
            ]
        )

    def _has_responded_to_comment(self, pr_number: int, comment_id: str) -> bool:
        """Check if we've already responded to a specific comment."""
        # Get all comments on the PR
        output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        if output:
            try:
                data = json.loads(output)
                # Look for agent comments with the hidden identifier
                target_id = f"<!-- ai-agent-response-to:{comment_id} -->"
                for comment in data.get("comments", []):
                    body = comment.get("body", "")
                    # Check for the hidden identifier
                    if target_id in body:
                        return True
                    # Fallback: check if this is an agent comment responding to the specific comment
                    if self.agent_tag in body and f"comment {comment_id}" in body:
                        return True
            except json.JSONDecodeError:
                pass

        return False

    def _has_agent_comment(self, pr_number: int) -> bool:
        """Check if agent has already commented."""
        output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                self.repo,
                "--json",
                "comments",
            ]
        )

        if output:
            try:
                data = json.loads(output)
                for comment in data.get("comments", []):
                    if self.agent_tag in comment.get("body", ""):
                        return True
            except json.JSONDecodeError:
                pass

        return False

    def _post_security_rejection(self, pr_number: int, reason: str):
        """Post security rejection comment."""
        comment = (
            f"{self.agent_tag} Security Notice\n\n"
            f"This request was blocked: {reason}\n\n"
            f"{self.security_manager.reject_message}\n\n"
            f"*This is an automated security measure.*"
        )

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def _post_error_comment(self, pr_number: int, error: str):
        """Post error comment."""
        comment = (
            f"{self.agent_tag} Error\n\n"
            f"An error occurred: {error}\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def _post_starting_work_comment(self, pr_number: int, agent_name: str, comment_id: str):
        """Post starting work comment."""
        # Include a hidden identifier for robust tracking
        hidden_id = f"<!-- ai-agent-response-to:{comment_id} -->"
        comment = (
            f"{self.agent_tag} I'm working on addressing this review feedback using {agent_name}!\n\n"
            f"Responding to review comment {comment_id}.\n\n"
            f"This typically takes a few minutes.\n\n"
            f"*This comment was generated by the AI agent automation system.*\n"
            f"{hidden_id}"
        )

        run_gh_command(
            [
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def run_continuous(self, interval: int = 300):
        """Run continuously checking for PRs.

        Args:
            interval: Check interval in seconds
        """
        logger.info("Starting continuous PR monitoring")

        while True:
            try:
                self.process_prs()
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)

            time.sleep(interval)


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    monitor = PRMonitor()

    if "--continuous" in os.sys.argv:
        monitor.run_continuous()
    else:
        monitor.process_prs()


if __name__ == "__main__":
    main()
