#!/usr/bin/env python3
"""Complete PR monitoring workflow example.

This example demonstrates monitoring pull requests for review comments
and implementing fixes automatically based on reviewer feedback.
"""

import asyncio
import os
import sys

from github_agents.monitors.pr_monitor import PRMonitor


async def process_single_pr(pr_number: int) -> None:
    """Process a specific pull request."""
    print("=" * 60)
    print(f"Processing PR #{pr_number}")
    print("=" * 60)

    # Get configuration
    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    allowed_users = os.getenv("ALLOWED_USERS", "admin").split(",")

    if not all([github_token, repo]):
        print("ERROR: Required environment variables not set")
        print("  GITHUB_TOKEN: GitHub API token")
        print("  GITHUB_REPOSITORY: Repository (owner/repo)")
        print("  OPENROUTER_API_KEY: OpenRouter API key (optional)")
        print("  ALLOWED_USERS: Comma-separated usernames (optional)")
        return

    # Initialize monitor
    monitor = PRMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=allowed_users,
        openrouter_api_key=openrouter_key,
    )

    print(f"\nRepository: {repo}")
    print(f"Allowed users: {', '.join(allowed_users)}")
    print(f"PR number: {pr_number}\n")

    # Process PR
    try:
        print("Checking PR for review comments with triggers...")
        commit_sha = await monitor.process_pr(pr_number)

        if commit_sha:
            print("\n✓ SUCCESS: Implemented fixes")
            print(f"  Commit: {commit_sha[:7]}")
            print(f"  View: https://github.com/{repo}/pull/{pr_number}/commits/{commit_sha}")
            print("\nNext steps:")
            print("  1. Review the changes")
            print("  2. Run CI/CD checks")
            print("  3. Request re-review if needed")
            print("  4. Merge when approved")
        else:
            print("\n✓ No trigger comments found")
            print("\nTo trigger agent:")
            print(f"  1. Go to: https://github.com/{repo}/pull/{pr_number}/files")
            print("  2. Add review comment: [Approved][OpenCode]")
            print("  3. Run this script again")
            print("\nValid triggers:")
            print("  - [Approved][OpenCode] - Use OpenCode for implementation")
            print("  - [Approved][Crush] - Use Crush for quick fixes")
            print("  - [Approved][Claude] - Use Claude for complex tasks")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        print("\nCommon issues:")
        print("  - Token doesn't have repo access")
        print("  - User not in allowed list")
        print("  - PR doesn't exist or is closed")
        print("  - No write access to PR branch")


async def monitor_open_prs() -> None:
    """Monitor all open PRs for review comments."""
    print("=" * 60)
    print("Monitoring Open PRs")
    print("=" * 60)

    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    allowed_users = os.getenv("ALLOWED_USERS", "admin").split(",")

    if not all([github_token, repo]):
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY required")
        return

    monitor = PRMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=allowed_users,
        openrouter_api_key=openrouter_key,
    )

    print(f"\nRepository: {repo}")
    print("Checking all open PRs for triggered review comments...\n")

    try:
        results = await monitor.process_open_prs()

        if results:
            print(f"\n✓ Processed {len(results)} PRs with triggered reviews:")
            for pr_num, commit_sha in results.items():
                print(f"\n  PR #{pr_num}")
                print(f"  Commit: {commit_sha[:7]}")
                print(f"  View: https://github.com/{repo}/pull/{pr_num}")
        else:
            print("\n✓ No triggered review comments found")
            print("\nThis is normal! Agents only activate when:")
            print("  1. An authorized user adds a review comment")
            print("  2. Comment format: [Approved][AgentName]")
            print("  3. Valid agents: OpenCode, Claude, Gemini, Crush, Codex")
            print("\nExample workflow:")
            print("  1. Reviewer adds comment: [Approved][OpenCode] Please add error handling")
            print("  2. Agent implements the fix")
            print("  3. Changes pushed to PR branch")
            print("  4. Reviewer verifies and approves")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")


async def continuous_monitoring(interval: int = 300) -> None:
    """Run continuous PR monitoring."""
    print("=" * 60)
    print("Continuous PR Monitoring")
    print("=" * 60)

    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    allowed_users = os.getenv("ALLOWED_USERS", "admin").split(",")

    if not all([github_token, repo]):
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY required")
        return

    monitor = PRMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=allowed_users,
        openrouter_api_key=openrouter_key,
    )

    print(f"\nRepository: {repo}")
    print(f"Check interval: {interval} seconds")
    print("Press Ctrl+C to stop\n")

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"[Cycle {cycle}] Checking open PRs for review comments...")

            try:
                results = await monitor.process_open_prs()
                if results:
                    print(f"  ✓ Processed {len(results)} PRs")
                    for pr_num, commit_sha in results.items():
                        print(f"    - PR #{pr_num} → {commit_sha[:7]}")
                else:
                    print("  ✓ No new triggers")

            except Exception as e:
                print(f"  ✗ Error: {e}")

            # Wait for next cycle
            print(f"  Waiting {interval}s until next check...\n")
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nStopping continuous monitoring")
        print(f"Completed {cycle} monitoring cycles")


async def demonstrate_review_workflow() -> None:
    """Demonstrate typical review workflow."""
    print("=" * 60)
    print("PR Review Workflow Guide")
    print("=" * 60)

    print("\nTypical Workflow:")
    print("\n1. Developer Creates PR")
    print("   - Implements feature or fix")
    print("   - Opens pull request")
    print("   - Requests review")

    print("\n2. Reviewer Provides Feedback")
    print("   - Reviews code")
    print("   - Adds review comments")
    print("   - For agent fixes: Add trigger comment")

    print("\n3. Agent Implements Fixes")
    print("   - Detects [Approved][AgentName] trigger")
    print("   - Reads all review feedback")
    print("   - Generates fixes")
    print("   - Pushes to PR branch")

    print("\n4. Reviewer Verifies")
    print("   - Checks automated fixes")
    print("   - Re-reviews if needed")
    print("   - Approves and merges")

    print("\n" + "-" * 60)
    print("Example Review Comments:")
    print("-" * 60)

    examples = [
        {
            "comment": "[Approved][OpenCode] Add error handling for null values",
            "agent": "OpenCode",
            "action": "Adds try-catch blocks and null checks",
        },
        {
            "comment": "[Approved][Crush] Fix typo in variable name",
            "agent": "Crush",
            "action": "Quick rename operation",
        },
        {
            "comment": "[Approved][Claude] Refactor this function for better readability",
            "agent": "Claude",
            "action": "Comprehensive refactoring",
        },
        {
            "comment": "This looks good, but consider adding tests",
            "agent": "None",
            "action": "No agent trigger, manual follow-up needed",
        },
    ]

    for i, ex in enumerate(examples, 1):
        print(f"\n{i}. {ex['comment']}")
        print(f"   Agent: {ex['agent']}")
        print(f"   Action: {ex['action']}")

    print("\n" + "-" * 60)
    print("Best Practices:")
    print("-" * 60)
    print("  - Be specific in feedback for better agent results")
    print("  - Use Crush for quick fixes, Claude for complex changes")
    print("  - Review automated changes before merging")
    print("  - Use triggers sparingly for critical fixes only")


async def demonstrate_multi_comment_handling() -> None:
    """Demonstrate handling multiple review comments."""
    print("=" * 60)
    print("Multiple Review Comments")
    print("=" * 60)

    print("\nThe PR monitor can handle multiple review comments in one PR:")
    print("\nScenario: PR with 3 review comments")
    print("  1. [Approved][OpenCode] Add input validation")
    print("  2. [Approved][OpenCode] Fix formatting issues")
    print("  3. Regular comment: Looks good otherwise!")

    print("\nAgent Behavior:")
    print("  - Collects ALL review comments")
    print("  - Extracts context from triggered comments")
    print("  - Includes non-triggered comments for context")
    print("  - Generates comprehensive fix")
    print("  - Creates single commit with all changes")

    print("\nBenefits:")
    print("  ✓ One commit for all fixes (clean history)")
    print("  ✓ Considers full review context")
    print("  ✓ Avoids multiple partial fixes")
    print("  ✓ Reduces CI/CD overhead")


def main() -> None:
    """Run PR monitor examples."""
    print("GitHub AI Agents - PR Monitor Example\n")

    # Parse command line arguments
    if "--help" in sys.argv:
        print("Usage: python pr_monitor_example.py [OPTIONS]\n")
        print("Options:")
        print("  --pr NUMBER       Process specific PR")
        print("  --continuous      Run continuous monitoring")
        print("  --interval SEC    Monitoring interval (default: 300)")
        print("  --workflow        Show review workflow guide")
        print("  --multi-comment   Show multi-comment handling")
        print("  --help            Show this help")
        print("\nEnvironment Variables:")
        print("  GITHUB_TOKEN         Required: GitHub API token")
        print("  GITHUB_REPOSITORY    Required: Repository (owner/repo)")
        print("  OPENROUTER_API_KEY   Optional: OpenRouter API key")
        print("  ALLOWED_USERS        Optional: Authorized users (comma-separated)")
        print("\nExamples:")
        print("  python pr_monitor_example.py --pr 45")
        print("  python pr_monitor_example.py --continuous --interval 600")
        print("  python pr_monitor_example.py --workflow")
        return

    if "--workflow" in sys.argv:
        asyncio.run(demonstrate_review_workflow())
        return

    if "--multi-comment" in sys.argv:
        asyncio.run(demonstrate_multi_comment_handling())
        return

    if "--pr" in sys.argv:
        try:
            idx = sys.argv.index("--pr")
            pr_num = int(sys.argv[idx + 1])
            asyncio.run(process_single_pr(pr_num))
        except (IndexError, ValueError):
            print("ERROR: --pr requires PR number")
            print("Example: python pr_monitor_example.py --pr 45")
        return

    if "--continuous" in sys.argv:
        interval = 300
        if "--interval" in sys.argv:
            try:
                idx = sys.argv.index("--interval")
                interval = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                print("WARNING: Invalid interval, using default 300s")

        asyncio.run(continuous_monitoring(interval))
        return

    # Default: monitor all open PRs once
    asyncio.run(monitor_open_prs())

    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("\n1. Try --pr NUMBER to process specific PR")
    print("2. Try --continuous for ongoing monitoring")
    print("3. Try --workflow to understand review process")
    print("4. Try board_integration_example.py for work coordination")


if __name__ == "__main__":
    main()
