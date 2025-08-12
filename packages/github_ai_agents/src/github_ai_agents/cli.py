"""CLI for GitHub AI Agents."""

import argparse
import logging
import sys

from .monitors import IssueMonitor, PRMonitor

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="GitHub AI Agents - Automated GitHub workflow management")

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Issue monitor command
    issue_parser = subparsers.add_parser("issue-monitor", help="Monitor GitHub issues")
    issue_parser.add_argument("--continuous", action="store_true", help="Run continuously")
    issue_parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)",
    )

    # PR monitor command
    pr_parser = subparsers.add_parser("pr-monitor", help="Monitor GitHub PRs")
    pr_parser.add_argument("--continuous", action="store_true", help="Run continuously")

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)

    # Handle commands
    try:
        if args.command == "issue-monitor":
            monitor = IssueMonitor()
            if args.continuous:
                monitor.run_continuous(args.interval)
            else:
                monitor.process_items()

        elif args.command == "pr-monitor":
            monitor = PRMonitor()
            monitor.process_items()

        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
