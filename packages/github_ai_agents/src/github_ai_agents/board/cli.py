"""CLI for GitHub Projects v2 board management.

Provides human-friendly interface for interacting with the board system,
similar to Beads' `bd` command.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

from github_ai_agents.board.config import load_config
from github_ai_agents.board.manager import BoardManager
from github_ai_agents.board.models import IssuePriority, IssueStatus, IssueType

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def load_board_manager() -> BoardManager:
    """Load board manager from configuration."""
    config_path = Path(".github/ai-agents-board.yml")
    if not config_path.exists():
        logger.error(f"Board configuration not found at {config_path}")
        logger.error("Please create .github/ai-agents-board.yml with board settings")
        sys.exit(1)

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set")
        sys.exit(1)

    try:
        config = load_config(str(config_path))
        manager = BoardManager(config=config, github_token=github_token)
        return manager
    except Exception as e:
        logger.error(f"Failed to load board manager: {e}")
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

    logger.info(f"Querying ready work (agent={args.agent}, priority={args.priority}, limit={args.limit})")

    try:
        issues = await manager.get_ready_work(agent_name=args.agent, limit=args.limit)

        # Filter by priority if specified
        if args.priority:
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            min_priority = priority_order.get(args.priority.lower(), 3)
            issues = [i for i in issues if i.priority and priority_order.get(i.priority.value.lower(), 3) <= min_priority]

        if args.json:
            output_result([{"number": i.number, "title": i.title, "status": i.status.value} for i in issues], json_output=True)
        else:
            if not issues:
                print("No ready work found")
            else:
                print(f"Found {len(issues)} ready work items:\n")
                for issue in issues:
                    print(format_issue(issue, verbose=args.verbose))
                    print()

    except Exception as e:
        logger.error(f"Failed to query ready work: {e}")
        sys.exit(1)


async def cmd_create(args: argparse.Namespace) -> None:
    """Create tracked issue."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Creating issue: {args.title}")

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

        issue = await manager.create_issue_with_metadata(  # type: ignore[attr-defined]
            title=args.title, body=args.body or "", **metadata
        )

        if args.json:
            output_result({"number": issue.number, "title": issue.title, "url": issue.url}, json_output=True)
        else:
            print(f"Created issue #{issue.number}: {issue.title}")
            print(f"URL: {issue.url}")

    except Exception as e:
        logger.error(f"Failed to create issue: {e}")
        sys.exit(1)


async def cmd_block(args: argparse.Namespace) -> None:
    """Add blocker dependency."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Adding blocker: #{args.issue} blocked by #{args.blocked_by}")

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
        logger.error(f"Failed to add blocker: {e}")
        sys.exit(1)


async def cmd_status(args: argparse.Namespace) -> None:
    """Update issue status."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Updating status: #{args.issue} -> {args.status}")

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
            logger.error(f"Invalid status: {args.status}")
            logger.error("Valid statuses: todo, in-progress, blocked, done, abandoned")
            sys.exit(1)

        success = await manager.update_status(args.issue, status)

        if success:
            # Optionally assign agent
            if args.agent:
                await manager.assign_to_agent(args.issue, args.agent)  # type: ignore[attr-defined]

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
        logger.error(f"Failed to update status: {e}")
        sys.exit(1)


async def cmd_graph(args: argparse.Namespace) -> None:
    """View dependency graph."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Getting dependency graph for issue #{args.issue}")

    try:
        graph = await manager.get_dependency_graph(args.issue, depth=args.depth)  # type: ignore[attr-defined]

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
        logger.error(f"Failed to get dependency graph: {e}")
        sys.exit(1)


async def cmd_claim(args: argparse.Namespace) -> None:
    """Claim an issue for work."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Claiming issue #{args.issue} for agent {args.agent}")

    try:
        import uuid

        session_id = str(uuid.uuid4())
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
                logger.error(f"Failed to claim issue #{args.issue} - already claimed by another agent")
                sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to claim issue: {e}")
        sys.exit(1)


async def cmd_release(args: argparse.Namespace) -> None:
    """Release claim on an issue."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Releasing claim on issue #{args.issue}")

    try:
        await manager.release_work(args.issue, args.agent, args.reason)

        if args.json:
            output_result({"success": True, "issue": args.issue, "reason": args.reason}, json_output=True)
        else:
            print(f"Released claim on issue #{args.issue} (reason: {args.reason})")

    except Exception as e:
        logger.error(f"Failed to release claim: {e}")
        sys.exit(1)


async def cmd_info(args: argparse.Namespace) -> None:
    """Get detailed issue information."""
    manager = load_board_manager()
    await manager.initialize()

    logger.info(f"Getting info for issue #{args.issue}")

    try:
        context = await manager.get_issue_context(args.issue)  # type: ignore[attr-defined]

        if args.json:
            output_result(
                {
                    "issue": {
                        "number": context["issue"].number,
                        "title": context["issue"].title,
                        "status": context["issue"].status.value if context["issue"].status else None,
                        "priority": context["issue"].priority.value if context["issue"].priority else None,
                        "agent": context["issue"].agent,
                    },
                    "blockers": [{"number": b.number, "title": b.title} for b in context["blockers"]],
                    "claim_history": [
                        {"agent": c.agent, "timestamp": c.timestamp.isoformat()} for c in context["claim_history"]
                    ],
                },
                json_output=True,
            )
        else:
            issue = context["issue"]
            print(format_issue(issue, verbose=True))
            print()

            if context["blockers"]:
                print("Current blockers:")
                for blocker in context["blockers"]:
                    print(f"  #{blocker.number}: {blocker.title} ({blocker.status.value if blocker.status else 'Unknown'})")
                print()

            if context["claim_history"]:
                print("Claim history:")
                for claim in context["claim_history"]:
                    print(f"  {claim.timestamp.isoformat()}: {claim.agent} (session: {claim.session_id})")

    except Exception as e:
        logger.error(f"Failed to get issue info: {e}")
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

    # release command
    release_parser = subparsers.add_parser("release", help="Release claim on an issue")
    release_parser.add_argument("issue", type=int, help="Issue number")
    release_parser.add_argument("--agent", type=str, required=True, help="Agent name")
    release_parser.add_argument(
        "--reason",
        type=str,
        default="completed",
        choices=["completed", "blocked", "abandoned", "error"],
        help="Release reason (default: completed)",
    )

    # info command
    info_parser = subparsers.add_parser("info", help="Get detailed issue information")
    info_parser.add_argument("issue", type=int, help="Issue number")

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
            "info": cmd_info,
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
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
