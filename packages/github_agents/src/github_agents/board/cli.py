"""CLI for GitHub Projects v2 board management.

Provides human-friendly interface for interacting with the board system,
similar to Beads' `bd` command.
"""

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict

from github_agents.board.config import load_config
from github_agents.board.manager import BoardManager
from github_agents.board.models import IssuePriority, IssueStatus, IssueType

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def load_board_manager() -> BoardManager:
    """Load board manager from configuration."""
    config_path = Path("ai-agents-board.yml")
    if not config_path.exists():
        logger.error("Board configuration not found at %s", config_path)
        logger.error("Please create ai-agents-board.yml with board settings")
        sys.exit(1)

    # Check for GitHub Projects token (classic token required for Projects v2)
    github_token = os.getenv("GITHUB_PROJECTS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GitHub token not found")
        logger.error("Set GITHUB_PROJECTS_TOKEN (classic token with 'project' scope)")
        logger.error("or GITHUB_TOKEN environment variable")
        sys.exit(1)

    try:
        config = load_config(str(config_path))
        manager = BoardManager(config=config, github_token=github_token)
        return manager
    except Exception as e:
        logger.error("Failed to load board manager: %s", e)
        sys.exit(1)


def format_issue(issue: Any, verbose: bool = False) -> str:
    """Format issue for display."""
    lines = [f"#{issue.number}: {issue.title}"]

    if verbose:
        lines.append(f"  Status: {issue.status.value if issue.status else 'Unknown'}")
        lines.append(f"  Priority: {issue.priority.value if issue.priority else 'Unknown'}")
        lines.append(f"  Type: {issue.type.value if issue.type else 'Unknown'}")
        if issue.agent:
            lines.append(f"  Agent: {issue.agent}")
        if issue.blocked_by:
            lines.append(f"  Blocked by: {', '.join(f'#{b}' for b in issue.blocked_by)}")

    return "\n".join(lines)


def output_result(data: Any, json_output: bool = False, verbose: bool = False) -> None:
    """Output result in requested format."""
    if json_output:
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, list):
        if not data:
            print("No results found")
        else:
            for item in data:
                if hasattr(item, "number"):  # Issue object
                    print(format_issue(item, verbose))
                else:
                    print(item)
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    else:
        print(data)


async def cmd_ready(args: argparse.Namespace) -> None:
    """Query ready work."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(
        "Querying ready work (agent=%s, priority=%s, limit=%s, include=%s, exclude=%s)",
        args.agent,
        args.priority,
        args.limit,
        args.include_labels,
        args.exclude_labels,
    )

    try:
        # Get more issues than limit to account for filtering
        fetch_limit = args.limit * 3 if (args.include_labels or args.exclude_labels) else args.limit
        issues = await manager.get_ready_work(agent_name=args.agent, limit=fetch_limit)

        # Filter by priority if specified
        if args.priority:
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            min_priority = priority_order.get(args.priority.lower(), 3)
            issues = [i for i in issues if i.priority and priority_order.get(i.priority.value.lower(), 3) <= min_priority]

        # Filter by labels if specified
        include_labels = set(args.include_labels) if args.include_labels else None
        exclude_labels = set(args.exclude_labels) if args.exclude_labels else None

        if include_labels or exclude_labels:
            filtered = []
            for issue in issues:
                issue_labels = set(issue.labels) if issue.labels else set()
                # Must have at least one include label (if specified)
                if include_labels and not issue_labels.intersection(include_labels):
                    continue
                # Must not have any exclude labels
                if exclude_labels and issue_labels.intersection(exclude_labels):
                    continue
                filtered.append(issue)
            issues = filtered

        # Apply final limit
        issues = issues[: args.limit]

        if args.json:
            output_result(
                [{"number": i.number, "title": i.title, "status": i.status.value, "labels": i.labels or []} for i in issues],
                json_output=True,
            )
        else:
            if not issues:
                print("No ready work found")
            else:
                print(f"Found {len(issues)} ready work items:\n")
                for issue in issues:
                    print(format_issue(issue, verbose=args.verbose))
                    print()

    except Exception as e:
        logger.error("Failed to query ready work: %s", e)
        sys.exit(1)


async def cmd_create(args: argparse.Namespace) -> None:
    """Create tracked issue."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Creating issue: %s", args.title)

    try:
        # Parse priority, type, size (handle case-insensitive input)
        priority = None
        if args.priority:
            priority_map = {
                "critical": IssuePriority.CRITICAL,
                "high": IssuePriority.HIGH,
                "medium": IssuePriority.MEDIUM,
                "low": IssuePriority.LOW,
            }
            priority = priority_map.get(args.priority.lower())

        issue_type = None
        if args.type:
            type_map = {
                "feature": IssueType.FEATURE,
                "bug": IssueType.BUG,
                "tech_debt": IssueType.TECH_DEBT,
                "documentation": IssueType.DOCUMENTATION,
            }
            issue_type = type_map.get(args.type.lower())

        # Create issue metadata
        metadata: Dict[str, Any] = {}
        if priority:
            metadata["priority"] = priority
        if issue_type:
            metadata["type"] = issue_type
        if args.agent:
            metadata["agent"] = args.agent
        if args.size:
            metadata["size"] = args.size.upper()

        issue = await manager.create_issue_with_metadata(title=args.title, body=args.body or "", **metadata)

        if args.json:
            output_result({"number": issue.number, "title": issue.title, "url": issue.url}, json_output=True)
        else:
            print(f"Created issue #{issue.number}: {issue.title}")
            print(f"URL: {issue.url}")

    except Exception as e:
        logger.error("Failed to create issue: %s", e)
        sys.exit(1)


async def cmd_block(args: argparse.Namespace) -> None:
    """Add blocker dependency."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Adding blocker: #%s blocked by #%s", args.issue, args.blocked_by)

    try:
        success = await manager.add_blocker(args.issue, args.blocked_by)

        if success:
            if args.json:
                output_result({"success": True, "issue": args.issue, "blocker": args.blocked_by}, json_output=True)
            else:
                print(f"Added blocker: #{args.issue} is now blocked by #{args.blocked_by}")
        else:
            logger.error("Failed to add blocker")
            sys.exit(1)

    except Exception as e:
        logger.error("Failed to add blocker: %s", e)
        sys.exit(1)


async def cmd_status(args: argparse.Namespace) -> None:
    """Update issue status."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Updating status: #%s -> %s", args.issue, args.status)

    try:
        # Parse status
        status_map = {
            "todo": IssueStatus.TODO,
            "in-progress": IssueStatus.IN_PROGRESS,
            "in_progress": IssueStatus.IN_PROGRESS,
            "blocked": IssueStatus.BLOCKED,
            "done": IssueStatus.DONE,
            "abandoned": IssueStatus.ABANDONED,
        }
        status = status_map.get(args.status.lower())
        if not status:
            logger.error("Invalid status: %s", args.status)
            logger.error("Valid statuses: todo, in-progress, blocked, done, abandoned")
            sys.exit(1)

        success = await manager.update_status(args.issue, status)

        if success:
            # Optionally assign agent
            if args.agent:
                await manager.assign_to_agent(args.issue, args.agent)

            if args.json:
                output_result({"success": True, "issue": args.issue, "status": status.value}, json_output=True)
            else:
                print(f"Updated issue #{args.issue} to status: {status.value}")
                if args.agent:
                    print(f"Assigned to agent: {args.agent}")
        else:
            logger.error("Failed to update status")
            sys.exit(1)

    except Exception as e:
        logger.error("Failed to update status: %s", e)
        sys.exit(1)


async def cmd_graph(args: argparse.Namespace) -> None:
    """View dependency graph."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Getting dependency graph for issue #%s", args.issue)

    try:
        graph = await manager.get_dependency_graph(args.issue, depth=args.depth)

        if args.json:
            output_result(
                {
                    "root": args.issue,
                    "blocks": [{"number": b.number, "title": b.title} for b in graph.blocks],
                    "blocked_by": [{"number": b.number, "title": b.title} for b in graph.blocked_by],
                    "parent": {"number": graph.parent.number, "title": graph.parent.title} if graph.parent else None,
                    "children": [{"number": c.number, "title": c.title} for c in graph.children],
                },
                json_output=True,
            )
        else:
            print(f"Dependency graph for issue #{args.issue}:\n")

            if graph.blocks:
                print("Blocks (issues this blocks):")
                for issue in graph.blocks:
                    print(f"  #{issue.number}: {issue.title}")
                print()

            if graph.blocked_by:
                print("Blocked by:")
                for issue in graph.blocked_by:
                    print(f"  #{issue.number}: {issue.title}")
                print()

            if graph.parent:
                print(f"Discovered from: #{graph.parent.number}: {graph.parent.title}")
                print()

            if graph.children:
                print("Discovered during (children):")
                for issue in graph.children:
                    print(f"  #{issue.number}: {issue.title}")
                print()

            if not any([graph.blocks, graph.blocked_by, graph.parent, graph.children]):
                print("No dependencies found")

    except Exception as e:
        logger.error("Failed to get dependency graph: %s", e)
        sys.exit(1)


async def cmd_claim(args: argparse.Namespace) -> None:
    """Claim an issue for work."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Claiming issue #%s for agent %s", args.issue, args.agent)

    try:
        import uuid

        # Use provided session ID or generate one
        session_id = args.session if args.session else str(uuid.uuid4())
        success = await manager.claim_work(args.issue, args.agent, session_id)

        if success:
            if args.json:
                output_result(
                    {"success": True, "issue": args.issue, "agent": args.agent, "session": session_id}, json_output=True
                )
            else:
                print(f"Successfully claimed issue #{args.issue} for agent {args.agent}")
                print(f"Session ID: {session_id}")
        else:
            if args.json:
                output_result({"success": False, "issue": args.issue, "reason": "already_claimed"}, json_output=True)
            else:
                logger.error("Failed to claim issue #%s - already claimed by another agent", args.issue)
                sys.exit(1)

    except Exception as e:
        if args.json:
            output_result({"success": False, "issue": args.issue, "error": str(e)}, json_output=True)
        logger.error("Failed to claim issue: %s", e)
        sys.exit(1)


async def cmd_release(args: argparse.Namespace) -> None:
    """Release claim on an issue."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Releasing claim on issue #%s", args.issue)

    try:
        await manager.release_work(args.issue, args.agent, args.reason)

        if args.json:
            output_result({"success": True, "issue": args.issue, "reason": args.reason}, json_output=True)
        else:
            print(f"Released claim on issue #{args.issue} (reason: {args.reason})")

    except Exception as e:
        if args.json:
            output_result({"success": False, "issue": args.issue, "error": str(e)}, json_output=True)
        logger.error("Failed to release claim: %s", e)
        sys.exit(1)


async def cmd_check_approval(args: argparse.Namespace) -> None:
    """Check if an issue has been approved by an authorized user."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Checking approval for issue #%s", args.issue)

    try:
        is_approved, approver = await manager.is_issue_approved(args.issue)

        if args.json:
            output_result(
                {"approved": is_approved, "issue": args.issue, "approver": approver},
                json_output=True,
            )
        else:
            if is_approved:
                print(f"Issue #{args.issue} is APPROVED by {approver}")
            else:
                print(f"Issue #{args.issue} is NOT approved")

        # Exit with code 0 if approved, 1 if not (useful for shell scripts)
        if not is_approved and not args.json:
            sys.exit(1)

    except Exception as e:
        if args.json:
            output_result({"approved": False, "issue": args.issue, "error": str(e)}, json_output=True)
        logger.error("Failed to check approval: %s", e)
        sys.exit(1)


async def cmd_info(args: argparse.Namespace) -> None:
    """Get detailed issue information."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Getting info for issue #%s", args.issue)

    try:
        # Get specific issue directly
        issue = await manager.get_issue(args.issue)

        if not issue:
            print(f"Issue #{args.issue} not found in project board")
            return

        if args.json:
            output_result(
                {
                    "number": issue.number,
                    "title": issue.title,
                    "status": issue.status.value if issue.status else None,
                    "priority": issue.priority.value if issue.priority else None,
                    "type": issue.type.value if issue.type else None,
                    "agent": issue.agent,
                    "blocked_by": issue.blocked_by,
                    "discovered_from": issue.discovered_from,
                    "url": issue.url,
                    "labels": issue.labels,
                },
                json_output=True,
            )
        else:
            print(format_issue(issue, verbose=True))
            print()

            if issue.blocked_by:
                print(f"Blocked by: {', '.join(f'#{b}' for b in issue.blocked_by)}")
                print()

            if issue.discovered_from:
                print(f"Discovered from: #{issue.discovered_from}")
                print()

    except Exception as e:
        logger.error("Failed to get issue info: %s", e)
        sys.exit(1)


async def cmd_find_approved(args: argparse.Namespace) -> None:
    """Find issues with approval comments that are not yet on the board."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info("Finding approved issues for agent: %s", args.agent)

    try:
        import re

        import aiohttp

        # Build the approval pattern for this agent
        agent_name = args.agent or "claude"
        pattern = re.compile(r"\[Approved\]\[" + re.escape(agent_name) + r"\]", re.IGNORECASE)

        # Fetch open issues from GitHub REST API
        repo_parts = manager.config.repository.split("/")
        if len(repo_parts) != 2:
            raise ValueError(f"Invalid repository format: {manager.config.repository}")
        owner, repo_name = repo_parts

        approved_issues = []
        async with aiohttp.ClientSession() as session:
            # Get open issues
            url = f"https://api.github.com/repos/{owner}/{repo_name}/issues"
            headers = {
                "Authorization": f"token {manager.github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            params = {"state": "open", "per_page": 50}

            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"GitHub API error: {resp.status}")
                issues = await resp.json()

            # For each issue, check comments for approval
            for issue in issues:
                # Skip PRs
                if "pull_request" in issue:
                    continue

                issue_num = issue["number"]
                comments_url = issue.get("comments_url")
                if not comments_url:
                    continue

                async with session.get(comments_url, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    comments = await resp.json()

                # Check if any comment has approval
                for comment in comments:
                    body = comment.get("body", "")
                    if pattern.search(body):
                        # Check if already on board
                        on_board = await manager.get_issue(issue_num) is not None
                        approved_issues.append({"number": issue_num, "title": issue["title"], "on_board": on_board})
                        break

        if args.json:
            output_result(approved_issues, json_output=True)
        else:
            if not approved_issues:
                print(f"No approved issues found for agent: {agent_name}")
            else:
                print(f"Found {len(approved_issues)} approved issues:\n")
                for issue in approved_issues:
                    board_status = "on board" if issue["on_board"] else "NOT on board"
                    print(f"  #{issue['number']}: {issue['title']} ({board_status})")

    except Exception as e:
        if args.json:
            output_result({"error": str(e)}, json_output=True)
        logger.error("Failed to find approved issues: %s", e)
        sys.exit(1)


async def cmd_add_to_board(args: argparse.Namespace) -> None:
    """Add an issue to the project board with fields."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(
        "Adding issue #%s to board (status=%s, priority=%s, agent=%s)",
        args.issue,
        args.status,
        args.priority,
        args.agent,
    )

    try:
        # First check if already on board
        existing = await manager.get_issue(args.issue)
        if existing:
            if args.json:
                output_result(
                    {"success": True, "issue": args.issue, "already_on_board": True, "status": existing.status.value},
                    json_output=True,
                )
            else:
                print(f"Issue #{args.issue} is already on the board (status: {existing.status.value})")
            return

        # Parse status
        from github_agents.board.models import IssuePriority, IssueSize, IssueStatus, IssueType

        status_map = {
            "todo": IssueStatus.TODO,
            "in-progress": IssueStatus.IN_PROGRESS,
            "blocked": IssueStatus.BLOCKED,
            "done": IssueStatus.DONE,
            "abandoned": IssueStatus.ABANDONED,
        }
        status = status_map.get(args.status.lower(), IssueStatus.TODO) if args.status else IssueStatus.TODO

        # Parse priority
        priority = None
        if args.priority:
            priority_map = {
                "critical": IssuePriority.CRITICAL,
                "high": IssuePriority.HIGH,
                "medium": IssuePriority.MEDIUM,
                "low": IssuePriority.LOW,
            }
            priority = priority_map.get(args.priority.lower())

        # Parse type
        issue_type = None
        if args.type:
            type_map = {
                "feature": IssueType.FEATURE,
                "bug": IssueType.BUG,
                "tech_debt": IssueType.TECH_DEBT,
                "documentation": IssueType.DOCUMENTATION,
            }
            issue_type = type_map.get(args.type.lower())

        # Parse size
        size = None
        if args.size:
            size_map = {"xs": IssueSize.XS, "s": IssueSize.S, "m": IssueSize.M, "l": IssueSize.L, "xl": IssueSize.XL}
            size = size_map.get(args.size.lower())

        # Use the normalized agent name (CLI name -> board field name)
        agent_name = manager._normalize_agent_name(args.agent) if args.agent else "Claude Code"

        success = await manager.add_issue_with_fields(
            issue_number=args.issue,
            status=status,
            priority=priority,
            issue_type=issue_type,
            size=size,
            agent=agent_name,
        )

        if success:
            if args.json:
                output_result(
                    {"success": True, "issue": args.issue, "already_on_board": False, "status": status.value},
                    json_output=True,
                )
            else:
                print(f"Added issue #{args.issue} to board with status: {status.value}")
        else:
            if args.json:
                output_result({"success": False, "issue": args.issue, "error": "Failed to add"}, json_output=True)
            else:
                print(f"Failed to add issue #{args.issue} to board")
            sys.exit(1)

    except Exception as e:
        if args.json:
            output_result({"success": False, "issue": args.issue, "error": str(e)}, json_output=True)
        logger.error("Failed to add issue to board: %s", e)
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GitHub Projects v2 Board CLI - Manage AI agent work coordination",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ready command
    ready_parser = subparsers.add_parser("ready", help="Query ready work items")
    ready_parser.add_argument("--agent", type=str, help="Filter by assigned agent")
    ready_parser.add_argument(
        "--priority", type=str, choices=["critical", "high", "medium", "low"], help="Minimum priority level"
    )
    ready_parser.add_argument("--limit", type=int, default=10, help="Maximum number of items to return (default: 10)")
    ready_parser.add_argument(
        "--include-labels", type=str, nargs="+", help="Only include issues with at least one of these labels"
    )
    ready_parser.add_argument("--exclude-labels", type=str, nargs="+", help="Exclude issues with any of these labels")

    # create command
    create_parser = subparsers.add_parser("create", help="Create tracked issue with metadata")
    create_parser.add_argument("title", type=str, help="Issue title")
    create_parser.add_argument("--body", type=str, help="Issue body/description")
    create_parser.add_argument("--type", type=str, choices=["feature", "bug", "tech_debt", "documentation"], help="Issue type")
    create_parser.add_argument("--priority", type=str, choices=["critical", "high", "medium", "low"], help="Issue priority")
    create_parser.add_argument("--agent", type=str, help="Assign to agent")
    create_parser.add_argument("--size", type=str, choices=["xs", "s", "m", "l", "xl"], help="Estimated size")

    # block command
    block_parser = subparsers.add_parser("block", help="Add blocker dependency")
    block_parser.add_argument("issue", type=int, help="Issue number")
    block_parser.add_argument("--blocked-by", type=int, required=True, help="Blocker issue number")

    # status command
    status_parser = subparsers.add_parser("status", help="Update issue status")
    status_parser.add_argument("issue", type=int, help="Issue number")
    status_parser.add_argument(
        "status", type=str, choices=["todo", "in-progress", "blocked", "done", "abandoned"], help="New status"
    )
    status_parser.add_argument("--agent", type=str, help="Assign to agent")

    # graph command
    graph_parser = subparsers.add_parser("graph", help="View dependency graph")
    graph_parser.add_argument("issue", type=int, help="Issue number")
    graph_parser.add_argument("--depth", type=int, default=3, help="Graph depth (default: 3)")

    # claim command
    claim_parser = subparsers.add_parser("claim", help="Claim an issue for work")
    claim_parser.add_argument("issue", type=int, help="Issue number")
    claim_parser.add_argument("--agent", type=str, required=True, help="Agent name")
    claim_parser.add_argument("--session", type=str, help="Session ID (auto-generated if not provided)")

    # release command
    release_parser = subparsers.add_parser("release", help="Release claim on an issue")
    release_parser.add_argument("issue", type=int, help="Issue number")
    release_parser.add_argument("--agent", type=str, required=True, help="Agent name")
    release_parser.add_argument(
        "--reason",
        type=str,
        default="completed",
        choices=["completed", "pr_created", "blocked", "abandoned", "error"],
        help="Release reason (default: completed)",
    )

    # check-approval command
    approval_parser = subparsers.add_parser("check-approval", help="Check if issue is approved")
    approval_parser.add_argument("issue", type=int, help="Issue number")

    # info command
    info_parser = subparsers.add_parser("info", help="Get detailed issue information")
    info_parser.add_argument("issue", type=int, help="Issue number")

    # add-to-board command
    add_board_parser = subparsers.add_parser("add-to-board", help="Add issue to project board")
    add_board_parser.add_argument("issue", type=int, help="Issue number")
    add_board_parser.add_argument("--status", type=str, default="todo", help="Initial status (default: todo)")
    add_board_parser.add_argument("--priority", type=str, choices=["critical", "high", "medium", "low"], help="Issue priority")
    add_board_parser.add_argument(
        "--type", type=str, choices=["feature", "bug", "tech_debt", "documentation"], help="Issue type"
    )
    add_board_parser.add_argument("--size", type=str, choices=["xs", "s", "m", "l", "xl"], help="Estimated size")
    add_board_parser.add_argument("--agent", type=str, help="Assign to agent (default: Claude Code)")

    # find-approved command
    find_approved_parser = subparsers.add_parser("find-approved", help="Find approved issues not on board")
    find_approved_parser.add_argument("--agent", type=str, default="claude", help="Agent name to check approvals for")

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)

    # Handle commands
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        # Map commands to handlers
        command_map = {
            "ready": cmd_ready,
            "create": cmd_create,
            "block": cmd_block,
            "status": cmd_status,
            "graph": cmd_graph,
            "claim": cmd_claim,
            "release": cmd_release,
            "check-approval": cmd_check_approval,
            "info": cmd_info,
            "add-to-board": cmd_add_to_board,
            "find-approved": cmd_find_approved,
        }

        handler = command_map.get(args.command)
        if handler:
            asyncio.run(handler(args))
        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Error: %s", e)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
