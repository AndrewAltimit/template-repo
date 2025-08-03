"""GitHub issue monitoring with multi-agent support."""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Type

from ..agents import ClaudeAgent, CodexAgent, CrushAgent, GeminiAgent, OpenCodeAgent
from ..code_parser import CodeParser
from ..config import AgentConfig
from ..security import SecurityManager
from ..utils import get_github_token, run_gh_command

logger = logging.getLogger(__name__)


class IssueMonitor:
    """Monitor GitHub issues and create PRs with AI agents."""

    def __init__(self):
        """Initialize issue monitor."""
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

    def get_open_issues(self) -> List[Dict]:
        """Get open issues from the repository."""
        output = run_gh_command(
            [
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,updatedAt,labels,comments",
            ]
        )

        if output:
            try:
                issues = json.loads(output)
                # Filter by recent activity (24 hours)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                recent_issues = []

                for issue in issues:
                    created_at = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
                    if created_at >= cutoff:
                        recent_issues.append(issue)

                return recent_issues
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse issues: {e}")

        return []

    def process_issues(self):
        """Process open issues."""
        logger.info(f"Processing issues for repository: {self.repo}")

        issues = self.get_open_issues()
        logger.info(f"Found {len(issues)} recent open issues")

        for issue in issues:
            self._process_single_issue(issue)

    def _process_single_issue(self, issue: Dict):
        """Process a single issue."""
        issue_number = issue["number"]

        # Check for trigger
        trigger_info = self.security_manager.check_trigger_comment(issue, "issue")
        if not trigger_info:
            return

        action, agent_name, trigger_user = trigger_info
        logger.info(f"Issue #{issue_number}: [{action}][{agent_name}] by {trigger_user}")

        # Security check
        is_allowed, reason = self.security_manager.perform_full_security_check(
            username=trigger_user,
            action=f"issue_{action.lower()}",
            repository=self.repo,
            entity_type="issue",
            entity_id=str(issue_number),
        )

        if not is_allowed:
            logger.warning(f"Security check failed for issue #{issue_number}: {reason}")
            self._post_security_rejection(issue_number, reason)
            return

        # Check if we already commented
        if self._has_agent_comment(issue_number):
            logger.info(f"Already processed issue #{issue_number}")
            return

        # Handle the action
        if action.lower() in ["approved", "fix", "implement"]:
            self._handle_implementation(issue, agent_name)
        elif action.lower() == "close":
            self._handle_close(issue_number, trigger_user, agent_name)
        elif action.lower() == "summarize":
            self._handle_summarize(issue)

    def _handle_implementation(self, issue: Dict, agent_name: str):
        """Handle issue implementation with specified agent."""
        issue_number = issue["number"]

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
                    f"- {', '.join([f'[Approved][{k.title()}]' for k in self.agents.keys()])}\n\n"
                    f"Or manually run the containerized agent:\n"
                    f"```bash\n"
                    f"docker-compose --profile agents run --rm openrouter-agents \\\n"
                    f"  python -m github_ai_agents.cli issue-monitor\n"
                    f"```"
                )
            else:
                error_msg = f"Agent '{agent_name}' is not available. Available agents: {list(self.agents.keys())}"

            logger.error(f"Agent '{agent_name}' not available")
            self._post_error_comment(issue_number, error_msg)
            return

        # Generate branch name
        branch_name = f"fix-issue-{issue_number}-{agent_name.lower()}-{str(uuid.uuid4())[:6]}"

        # Post starting work comment
        self._post_starting_work_comment(issue_number, branch_name, agent_name)

        # Run implementation asynchronously
        try:
            asyncio.run(self._implement_issue(issue, branch_name, agent))
        except Exception as e:
            logger.error(f"Failed to implement issue #{issue_number}: {e}")
            self._post_error_comment(issue_number, str(e))

    async def _implement_issue(self, issue: Dict, branch_name: str, agent):
        """Implement issue using specified agent."""
        issue_number = issue["number"]
        issue_title = issue["title"]
        issue_body = issue.get("body", "")

        # Create implementation prompt
        prompt = f"""
Implement the following GitHub issue:

Issue #{issue_number}: {issue_title}

Description:
{issue_body}

Requirements:
1. Create a complete, working implementation
2. Follow the project's coding standards
3. Add appropriate tests if needed
4. Update documentation if needed
"""

        # Generate implementation
        context = {
            "issue_number": issue_number,
            "issue_title": issue_title,
            "branch_name": branch_name,
        }

        try:
            response = await agent.generate_code(prompt, context)
            logger.info(f"Agent {agent.name} generated response for issue #{issue_number}")

            # Create PR with the changes
            # Note: In a real implementation, the agent would make actual file changes
            # For now, we'll just create a PR with a description
            self._create_pr(issue, branch_name, agent.name, response)

        except Exception as e:
            logger.error(f"Agent {agent.name} failed: {e}")
            raise

    def _create_pr(self, issue: Dict, branch_name: str, agent_name: str, implementation: str):
        """Create a pull request for the issue."""
        issue_number = issue["number"]
        issue_title = issue["title"]

        try:
            # 1. Create and checkout the branch
            logger.info(f"Creating branch: {branch_name}")

            # Ensure we're on the main branch first
            run_gh_command(["checkout", "main"])
            run_gh_command(["pull", "origin", "main"])

            # Create and checkout new branch
            run_gh_command(["checkout", "-b", branch_name])

            # 2. Make the actual code changes
            # Parse and apply the code changes from the AI response
            blocks, results = CodeParser.extract_and_apply(implementation)

            if results:
                logger.info(f"Applied {len(results)} file changes:")
                for filename, operation in results.items():
                    logger.info(f"  - {filename}: {operation}")
            else:
                logger.warning("No code changes were extracted from the AI response")

            # 3. Commit and push
            commit_message = (
                f"feat: implement issue #{issue_number} using {agent_name}\n\n"
                f"Automated implementation for: {issue_title}\n\n"
                f"Generated by {agent_name} AI agent.\n\n"
                f"Closes #{issue_number}\n\n"
                f"🤖 Generated with AI Agent Automation System"
            )

            # Check if there are changes to commit
            status_output = run_gh_command(["status", "--porcelain"])
            if status_output and status_output.strip():
                run_gh_command(["add", "-A"])
                run_gh_command(["commit", "-m", commit_message])

                # Push the branch
                logger.info(f"Pushing branch: {branch_name}")
                run_gh_command(["push", "-u", "origin", branch_name])

                # 4. Create the PR
                pr_title = f"fix: {issue_title} (AI Generated)"
                pr_body = (
                    f"## 🤖 AI-Generated Implementation\n\n"
                    f"This PR was automatically generated by {agent_name} in response to issue #{issue_number}.\n\n"
                    f"### Issue Summary\n"
                    f"{issue.get('body', 'No description provided')[:500]}...\n\n"
                    f"### Implementation Details\n"
                    f"Generated using {agent_name} AI agent with automated code generation.\n\n"
                    f"### Testing\n"
                    f"- [ ] Code has been tested\n"
                    f"- [ ] All tests pass\n"
                    f"- [ ] No regressions identified\n\n"
                    f"Closes #{issue_number}\n\n"
                    f"---\n"
                    f"*This PR was generated by the AI agent automation system.*"
                )

                pr_output = run_gh_command(
                    [
                        "pr",
                        "create",
                        "--title",
                        pr_title,
                        "--body",
                        pr_body,
                        "--base",
                        "main",
                        "--head",
                        branch_name,
                        "--repo",
                        self.repo,
                    ]
                )

                # Extract PR number from output
                pr_url = pr_output.strip() if pr_output else "Unknown"

                success_comment = (
                    f"{self.agent_tag} I've successfully implemented this issue using {agent_name}!\n\n"
                    f"🎉 **Pull Request Created**: {pr_url}\n\n"
                    f"Branch: `{branch_name}`\n"
                    f"Status: Ready for review\n\n"
                    f"*This comment was generated by the AI agent automation system.*"
                )
            else:
                logger.warning("No changes to commit - agent may not have generated code")
                success_comment = (
                    f"{self.agent_tag} I've analyzed this issue using {agent_name}.\n\n"
                    f"⚠️ No code changes were generated. This might indicate:\n"
                    f"- The issue needs more specific requirements\n"
                    f"- The agent needs additional context\n"
                    f"- Manual implementation may be required\n\n"
                    f"*This comment was generated by the AI agent automation system.*"
                )

        except Exception as e:
            logger.error(f"Failed to create PR for issue #{issue_number}: {e}")
            success_comment = (
                f"{self.agent_tag} I attempted to implement this issue using {agent_name} but encountered an error.\n\n"
                f"❌ Error: {str(e)}\n\n"
                f"The implementation may require manual intervention.\n\n"
                f"*This comment was generated by the AI agent automation system.*"
            )

        # Post completion comment
        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                success_comment,
            ]
        )

    def _handle_close(self, issue_number: int, trigger_user: str, agent_name: str):
        """Handle issue close request."""
        logger.info(f"Closing issue #{issue_number}")

        run_gh_command(
            [
                "issue",
                "close",
                str(issue_number),
                "--repo",
                self.repo,
            ]
        )

        comment = (
            f"{self.agent_tag} Issue closed as requested by {trigger_user} "
            f"using [{agent_name}].\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def _handle_summarize(self, issue: Dict):
        """Handle issue summarize request."""
        issue_number = issue["number"]
        title = issue.get("title", "")
        body = issue.get("body", "")[:200]
        labels = [label.get("name", "") for label in issue.get("labels", [])]

        summary = (
            f"{self.agent_tag} **Issue Summary:**\n\n"
            f"**Title:** {title}\n"
            f"**Labels:** {', '.join(labels) if labels else 'None'}\n"
            f"**Description:** {body}{'...' if len(issue.get('body', '')) > 200 else ''}\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                summary,
            ]
        )

    def _has_agent_comment(self, issue_number: int) -> bool:
        """Check if agent has already commented."""
        output = run_gh_command(
            [
                "issue",
                "view",
                str(issue_number),
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

    def _post_security_rejection(self, issue_number: int, reason: str):
        """Post security rejection comment."""
        comment = (
            f"{self.agent_tag} Security Notice\n\n"
            f"This request was blocked: {reason}\n\n"
            f"{self.security_manager.reject_message}\n\n"
            f"*This is an automated security measure.*"
        )

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def _post_error_comment(self, issue_number: int, error: str):
        """Post error comment."""
        comment = (
            f"{self.agent_tag} Error\n\n"
            f"An error occurred: {error}\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def _post_starting_work_comment(self, issue_number: int, branch_name: str, agent_name: str):
        """Post starting work comment."""
        comment = (
            f"{self.agent_tag} I'm starting work on this issue using {agent_name}!\n\n"
            f"Branch: `{branch_name}`\n\n"
            f"This typically takes a few minutes.\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )

        run_gh_command(
            [
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.repo,
                "--body",
                comment,
            ]
        )

    def run_continuous(self, interval: int = 300):
        """Run continuously checking for issues.

        Args:
            interval: Check interval in seconds
        """
        logger.info("Starting continuous issue monitoring")

        while True:
            try:
                self.process_issues()
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)

            time.sleep(interval)


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    monitor = IssueMonitor()

    if "--continuous" in os.sys.argv:
        monitor.run_continuous()
    else:
        monitor.process_issues()


if __name__ == "__main__":
    main()
