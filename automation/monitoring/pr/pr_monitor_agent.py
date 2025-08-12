#!/usr/bin/env python3
"""
PR Monitoring Agent - Intelligent PR comment monitoring with structured responses.

This agent monitors a PR for new comments from administrators or AI reviewers,
analyzes them, and returns structured data for the main Claude agent to process.

Usage:
    python pr_monitor_agent.py PR_NUMBER [--timeout MINUTES] [--since-commit SHA]

Example:
    python pr_monitor_agent.py 48
    python pr_monitor_agent.py 48 --timeout 30
    python pr_monitor_agent.py 48 --since-commit abc1234
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_monitor(pr_number, timeout=600, since_commit=None):
    """Run the monitoring script and get returned comment."""
    print(f"Starting PR #{pr_number} monitoring subagent...", file=sys.stderr)
    if since_commit:
        print(f"Monitoring for comments after commit: {since_commit}", file=sys.stderr)

    script_path = Path(__file__).parent / "monitor.sh"

    try:
        # Build command with optional commit SHA
        cmd = ["/bin/bash", str(script_path), str(pr_number)]
        if since_commit:
            cmd.append(since_commit)

        # Run the monitor script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0 and result.stdout:
            # Parse the returned comment
            comment = json.loads(result.stdout)
            return comment
        else:
            print(f"Monitor exited with code {result.returncode}", file=sys.stderr)
            return None

    except subprocess.TimeoutExpired:
        print(f"Monitor timed out after {timeout} seconds", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error running monitor: {e}", file=sys.stderr)
        return None


def analyze_comment(comment):
    """Analyze if comment needs Claude's response."""
    if not comment:
        return None

    author = comment["author"]["login"]
    body = comment["body"]
    timestamp = comment["createdAt"]

    # Decision logic
    needs_response = False
    priority = "normal"
    response_type = None
    action_required = None

    # Check for admin commands
    if author == "AndrewAltimit":
        needs_response = True
        if "[ADMIN]" in body:
            priority = "high"
            response_type = "admin_command"
            action_required = "Execute admin command and respond"
        else:
            response_type = "admin_comment"
            action_required = "Review and respond to admin feedback"

    # Check for Gemini reviews
    elif "github-actions" in author and "Gemini" in body:
        needs_response = True
        priority = "normal"
        response_type = "gemini_review"
        action_required = "Address Gemini code review feedback"

    # Check for PR validation results
    elif "github-actions" in author and "PR Validation Results" in body:
        needs_response = False  # Usually informational
        response_type = "ci_results"
        action_required = "Review CI results if failures present"

    # Return structured decision
    return {
        "needs_response": needs_response,
        "priority": priority,
        "response_type": response_type,
        "action_required": action_required,
        "comment": {"author": author, "timestamp": timestamp, "body": body},
    }


def main():
    """Main agent entry point."""
    parser = argparse.ArgumentParser(description="Monitor PR for relevant comments")
    parser.add_argument("pr_number", type=int, help="PR number to monitor")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default: 600)")
    parser.add_argument("--json", action="store_true", help="Output only JSON (no stderr messages)")
    parser.add_argument("--since-commit", type=str, help="Only monitor comments after this commit SHA")

    args = parser.parse_args()

    if not args.json:
        print("=" * 60, file=sys.stderr)
        print(f"PR #{args.pr_number} MONITORING AGENT", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

    # Run monitor and get comment
    comment = run_monitor(args.pr_number, args.timeout, args.since_commit)

    if comment:
        # Analyze and decide
        decision = analyze_comment(comment)

        if decision:
            if not args.json and decision["needs_response"]:
                print(
                    f"\n✓ Action required for {decision['response_type']}",
                    file=sys.stderr,
                )
                print(f"  Priority: {decision['priority']}", file=sys.stderr)
                print(f"  Action: {decision['action_required']}", file=sys.stderr)

            # Output JSON for Claude to process
            print(json.dumps(decision, indent=2))
            return 0
        else:
            if not args.json:
                print("Comment does not require response", file=sys.stderr)
            return 1
    else:
        if not args.json:
            print("No relevant comments detected within timeout", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
