#!/usr/bin/env python3
"""
Claude Code Subagent Integration Tool

This script provides a command-line interface for using Claude Code with custom personas.
It allows direct invocation of subagents for various tasks.

Usage:
    python claude_subagent.py <persona> <command> [options]

Examples:
    python claude_subagent.py tech-lead "implement feature X"
    python claude_subagent.py qa-reviewer "review PR #123"
    python claude_subagent.py security-auditor "audit codebase"
"""

import argparse
import json
import os
import sys
from typing import Dict

from subagent_manager import SubagentManager


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Use Claude Code with custom personas for various development tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Implement a feature from an issue
  %(prog)s tech-lead implement --issue 123

  # Review a PR
  %(prog)s qa-reviewer review --pr 456

  # Perform security audit
  %(prog)s security-auditor audit --path /path/to/code

  # Custom task with any persona
  %(prog)s tech-lead custom "Refactor the authentication module"
        """,
    )

    # Positional arguments
    parser.add_argument(
        "persona",
        choices=["tech-lead", "qa-reviewer", "security-auditor"],
        help="The persona to use for the task",
    )

    parser.add_argument(
        "command",
        choices=["implement", "review", "audit", "custom"],
        help="The command to execute",
    )

    # Optional arguments
    parser.add_argument(
        "--issue", type=int, help="Issue number for 'implement' command"
    )

    parser.add_argument("--pr", type=int, help="PR number for 'review' command")

    parser.add_argument("--path", type=str, help="Path to code for 'audit' command")

    parser.add_argument(
        "--task", type=str, help="Custom task description for 'custom' command"
    )

    parser.add_argument(
        "--repo",
        type=str,
        help="GitHub repository (format: owner/repo)",
        default=os.environ.get("GITHUB_REPOSITORY"),
    )

    parser.add_argument("--branch", type=str, help="Git branch to work on")

    parser.add_argument(
        "--timeout", type=int, default=600, help="Timeout in seconds (default: 600)"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    return parser.parse_args()


def get_issue_data(repo: str, issue_number: int) -> Dict:
    """Fetch issue data from GitHub."""
    try:
        from utils import run_gh_command

        output = run_gh_command(
            [
                "issue",
                "view",
                str(issue_number),
                "--repo",
                repo,
                "--json",
                "number,title,body,labels",
            ]
        )

        if output:
            return json.loads(output)
        else:
            print(f"Error: Could not fetch issue #{issue_number}")
            return {}

    except Exception as e:
        print(f"Error fetching issue: {e}")
        return {}


def get_pr_data(repo: str, pr_number: int) -> Dict:
    """Fetch PR data from GitHub."""
    try:
        from utils import run_gh_command

        output = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo,
                "--json",
                "number,title,body,head",
            ]
        )

        if output:
            return json.loads(output)
        else:
            print(f"Error: Could not fetch PR #{pr_number}")
            return {}

    except Exception as e:
        print(f"Error fetching PR: {e}")
        return {}


def main():
    """Main entry point."""
    args = parse_arguments()

    # Validate arguments
    if args.command == "implement" and not args.issue:
        print("Error: --issue is required for 'implement' command")
        sys.exit(1)

    if args.command == "review" and not args.pr:
        print("Error: --pr is required for 'review' command")
        sys.exit(1)

    if args.command == "audit" and not args.path:
        print("Error: --path is required for 'audit' command")
        sys.exit(1)

    if args.command == "custom" and not args.task:
        print("Error: --task is required for 'custom' command")
        sys.exit(1)

    if not args.repo:
        print(
            "Error: --repo is required (or set GITHUB_REPOSITORY environment variable)"
        )
        sys.exit(1)

    # Initialize subagent manager
    manager = SubagentManager()

    # Verify persona exists
    if args.persona not in manager.list_personas():
        print(f"Error: Persona '{args.persona}' not found")
        print(f"Available personas: {', '.join(manager.list_personas())}")
        sys.exit(1)

    # Prepare context and task based on command
    context = {}
    task = ""

    if args.command == "implement":
        # Fetch issue data
        issue_data = get_issue_data(args.repo, args.issue)
        if not issue_data:
            sys.exit(1)

        task = manager.create_implementation_task(issue_data)
        context = {
            "issue_number": issue_data.get("number"),
            "issue_title": issue_data.get("title"),
            "issue_body": issue_data.get("body"),
            "branch_name": args.branch or f"fix-issue-{args.issue}",
        }

    elif args.command == "review":
        # Fetch PR data
        pr_data = get_pr_data(args.repo, args.pr)
        if not pr_data:
            sys.exit(1)

        # For demo purposes, create a simple review task
        task = f"Review PR #{args.pr} and address any issues found."
        context = {
            "pr_number": pr_data.get("number"),
            "pr_title": pr_data.get("title"),
            "branch_name": pr_data.get("head", {}).get("ref"),
        }

    elif args.command == "audit":
        task = f"Perform a security audit of the code at {args.path}"
        context = {
            "path": args.path,
            "audit_type": "security",
        }

    elif args.command == "custom":
        task = args.task
        context = {
            "custom_task": True,
            "branch_name": args.branch,
        }

    # Execute with the selected persona
    print(f"\n🤖 Using Claude Code with {args.persona} persona...")
    print(f"📋 Task: {task[:100]}..." if len(task) > 100 else f"📋 Task: {task}")

    if args.verbose:
        print("\n📝 Context:")
        for key, value in context.items():
            print(f"  - {key}: {value}")

    print(f"\n⏳ Executing (timeout: {args.timeout}s)...\n")

    success, stdout, stderr = manager.execute_with_persona(
        args.persona, task, context, timeout=args.timeout
    )

    # Display results
    if success:
        print("\n✅ Task completed successfully!")
        if args.verbose and stdout:
            print("\n📄 Output:")
            print("-" * 60)
            print(stdout)
            print("-" * 60)
    else:
        print("\n❌ Task failed!")
        if stderr:
            print(f"\n🚨 Error: {stderr}")
        if args.verbose and stdout:
            print("\n📄 Partial output:")
            print("-" * 60)
            print(stdout)
            print("-" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
