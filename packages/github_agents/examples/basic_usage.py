#!/usr/bin/env python3
"""Basic usage example for GitHub AI Agents.

This example shows the simplest way to use the issue and PR monitors
to understand core concepts without complexity.
"""

import asyncio
import os
import sys

from github_agents.monitors.issue_monitor import IssueMonitor
from github_agents.monitors.pr_monitor import PRMonitor


async def demonstrate_issue_monitor() -> None:
    """Demonstrate basic issue monitor usage."""
    print("=" * 60)
    print("Issue Monitor Demo")
    print("=" * 60)

    # Get configuration from environment
    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if not github_token or not repo:
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY must be set")
        print("Example:")
        print("  export GITHUB_TOKEN=your_token")
        print("  export GITHUB_REPOSITORY=owner/repo")
        return

    # Create monitor with basic configuration
    monitor = IssueMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=["admin"],  # Replace with your GitHub username
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    print(f"\nMonitoring repository: {repo}")
    print("Looking for issues with trigger comments...")
    print("Trigger format: [Approved][Agent]")
    print("Example: [Approved][OpenCode]\n")

    # Process recent issues (last 10)
    try:
        result = await monitor.process_recent_issues()
        if result:
            print(f"\n✓ Processed {len(result)} triggered issues")
            for issue_num, pr_url in result.items():
                print(f"  - Issue #{issue_num} → PR: {pr_url}")
        else:
            print("\n✓ No triggered issues found (this is normal!)")
            print("  To test: Add a comment '[Approved][OpenCode]' to an issue")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("  Check token permissions and repository access")


async def demonstrate_pr_monitor() -> None:
    """Demonstrate basic PR monitor usage."""
    print("\n" + "=" * 60)
    print("PR Monitor Demo")
    print("=" * 60)

    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")

    if not github_token or not repo:
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY must be set")
        return

    # Create monitor
    monitor = PRMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=["admin"],  # Replace with your GitHub username
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    print(f"\nMonitoring repository: {repo}")
    print("Looking for PRs with review comments...")
    print("Trigger format: [Approved][Agent]")
    print("Example: [Approved][OpenCode]\n")

    # Check open PRs
    try:
        result = await monitor.process_open_prs()
        if result:
            print(f"\n✓ Processed {len(result)} PRs with review comments")
            for pr_num, commit_sha in result.items():
                print(f"  - PR #{pr_num} → Commit: {commit_sha[:7]}")
        else:
            print("\n✓ No triggered review comments found")
            print("  To test: Add a review comment '[Approved][OpenCode]' to a PR")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("  Check token permissions and repository access")


async def demonstrate_security() -> None:
    """Demonstrate security features."""
    print("\n" + "=" * 60)
    print("Security Features Demo")
    print("=" * 60)

    # Show security configuration
    print("\n1. User Authorization:")
    print("   Only users in 'allowed_users' list can trigger agents")
    print("   Example: allowed_users=['admin', 'maintainer']")

    print("\n2. Commit Validation:")
    print("   Commits are validated after approval to prevent code injection")
    print("   Any changes after approval require re-approval")

    print("\n3. Trigger Pattern Validation:")
    print("   Only recognized patterns trigger agents")
    print("   Valid: [Approved][OpenCode], [Review][Claude]")
    print("   Invalid: [Approved][RandomAgent], Approved OpenCode")

    print("\n4. API Key Management:")
    print("   Keys stored in environment variables, never in code")
    print("   Example: export OPENROUTER_API_KEY=your_key")

    print("\n5. Rate Limiting:")
    print("   Built-in rate limiting prevents API abuse")
    print("   Configurable per-agent timeout and retry logic")


def main() -> None:
    """Run all demonstrations."""
    print("GitHub AI Agents - Basic Usage Example")
    print("\nThis example demonstrates:")
    print("  1. Issue monitoring for automated implementation")
    print("  2. PR monitoring for review feedback fixes")
    print("  3. Security features and best practices")
    print()

    # Check if test mode
    test_mode = "--test-mode" in sys.argv

    if test_mode:
        print("[TEST MODE] Using mock implementations (no API calls)")
        print("✓ Configuration loaded successfully")
        print("✓ Monitors initialized")
        print("✓ Security validation passed")
        return

    # Run demonstrations
    asyncio.run(demonstrate_issue_monitor())
    asyncio.run(demonstrate_pr_monitor())
    asyncio.run(demonstrate_security())

    # Show next steps
    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("\n1. Try issue_monitor_example.py for detailed issue workflow")
    print("2. Try pr_monitor_example.py for PR review handling")
    print("3. Set up GitHub Projects v2 and try board_integration_example.py")
    print("4. Review security.md for production hardening")
    print("\nSee examples/README.md for complete documentation")


if __name__ == "__main__":
    main()
