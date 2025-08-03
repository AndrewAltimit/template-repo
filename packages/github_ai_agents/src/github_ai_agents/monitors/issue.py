"""GitHub issue monitoring with multi-agent support."""

import asyncio
import logging
import sys
import uuid
from typing import Dict

from ..code_parser import CodeParser
from ..utils import run_gh_command, run_gh_command_async
from .base import BaseMonitor

logger = logging.getLogger(__name__)


class IssueMonitor(BaseMonitor):
    """Monitor GitHub issues and create PRs with AI agents."""

    def __init__(self):
        """Initialize issue monitor."""
        super().__init__()

    def _get_json_fields(self, item_type: str) -> str:
        """Get JSON fields for issues."""
        return "number,title,body,author,createdAt,updatedAt,labels,comments"

    def get_open_issues(self):
        """Get open issues from the repository."""
        return self.get_recent_items("issue")

    def process_items(self):
        """Process open issues."""
        logger.info(f"Processing issues for repository: {self.repo}")

        issues = self.get_open_issues()
        logger.info(f"Found {len(issues)} recent open issues")

        # Process all issues concurrently using asyncio
        if issues:
            asyncio.run(self._process_issues_async(issues))

    async def _process_issues_async(self, issues):
        """Process multiple issues concurrently."""
        tasks = []
        for issue in issues:
            task = self._process_single_issue_async(issue)
            tasks.append(task)

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing issue: {result}")

    async def _process_single_issue_async(self, issue: Dict):
        """Process a single issue asynchronously."""
        # All the synchronous checks can remain synchronous
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
            self._post_security_rejection(issue_number, reason, "issue")
            return

        # Check if we already commented
        if self._has_agent_comment(issue_number, "issue"):
            logger.info(f"Already processed issue #{issue_number}")
            return

        # Handle the action
        if action.lower() in ["approved", "fix", "implement"]:
            await self._handle_implementation_async(issue, agent_name)
        elif action.lower() == "close":
            self._handle_close(issue_number, trigger_user, agent_name)
        elif action.lower() == "summarize":
            self._handle_summarize(issue)

    async def _handle_implementation_async(self, issue: Dict, agent_name: str):
        """Handle issue implementation with specified agent asynchronously."""
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
            self._post_error_comment(issue_number, error_msg, "issue")
            return

        # Generate branch name
        branch_name = f"fix-issue-{issue_number}-{agent_name.lower()}-{str(uuid.uuid4())[:6]}"

        # Post starting work comment
        self._post_starting_work_comment(issue_number, branch_name, agent_name)

        # Run implementation directly (no asyncio.run needed since we're already async)
        try:
            await self._implement_issue(issue, branch_name, agent)
        except Exception as e:
            logger.error(f"Failed to implement issue #{issue_number}: {e}")
            self._post_error_comment(issue_number, str(e), "issue")

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
            self._post_security_rejection(issue_number, reason, "issue")
            return

        # Check if we already commented
        if self._has_agent_comment(issue_number, "issue"):
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
            self._post_error_comment(issue_number, error_msg, "issue")
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
            self._post_error_comment(issue_number, str(e), "issue")

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
            await self._create_pr(issue, branch_name, agent.name, response)

        except Exception as e:
            logger.error(f"Agent {agent.name} failed: {e}")
            raise

    async def _create_pr(self, issue: Dict, branch_name: str, agent_name: str, implementation: str):
        """Create a pull request for the issue."""
        issue_number = issue["number"]
        issue_title = issue["title"]

        try:
            # 1. Create and checkout the branch
            logger.info(f"Creating branch: {branch_name}")

            # Ensure we're on the main branch first
            await run_gh_command_async(["checkout", "main"])
            await run_gh_command_async(["pull", "origin", "main"])

            # Create and checkout new branch
            await run_gh_command_async(["checkout", "-b", branch_name])

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
            status_output = await run_gh_command_async(["status", "--porcelain"])
            if status_output and status_output.strip():
                await run_gh_command_async(["add", "-A"])
                await run_gh_command_async(["commit", "-m", commit_message])

                # Push the branch
                logger.info(f"Pushing branch: {branch_name}")
                await run_gh_command_async(["push", "-u", "origin", branch_name])

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

                pr_output = await run_gh_command_async(
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
        await run_gh_command_async(
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

    def _post_starting_work_comment(self, issue_number: int, branch_name: str, agent_name: str):
        """Post starting work comment."""
        comment = (
            f"{self.agent_tag} I'm starting work on this issue using {agent_name}!\n\n"
            f"Branch: `{branch_name}`\n\n"
            f"This typically takes a few minutes.\n\n"
            f"*This comment was generated by the AI agent automation system.*"
        )
        self._post_comment(issue_number, comment, "issue")


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    monitor = IssueMonitor()

    if "--continuous" in sys.argv:
        monitor.run_continuous()
    else:
        monitor.process_items()


if __name__ == "__main__":
    main()
