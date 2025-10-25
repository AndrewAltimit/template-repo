#!/usr/bin/env python3
"""Complete issue monitoring workflow example.

This example demonstrates the full issue monitoring workflow including:
- Security configuration
- Agent selection
- Trigger detection
- Implementation generation
- PR creation
- Error handling
"""

import asyncio
import os
import sys

from github_ai_agents.monitors.issue_monitor import IssueMonitor


async def process_single_issue(issue_number: int) -> None:
    """Process a specific issue by number."""
    print("=" * 60)
    print(f"Processing Issue #{issue_number}")
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
    monitor = IssueMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=allowed_users,
        openrouter_api_key=openrouter_key,
    )

    print(f"\nRepository: {repo}")
    print(f"Allowed users: {', '.join(allowed_users)}")
    print(f"Issue number: {issue_number}\n")

    # Process issue
    try:
        print("Checking issue for trigger comments...")
        pr_url = await monitor.process_issue(issue_number)

        if pr_url:
            print("\n✓ SUCCESS: Created PR")
            print(f"  URL: {pr_url}")
            print("\nNext steps:")
            print("  1. Review the generated code")
            print("  2. Run tests locally if needed")
            print("  3. Merge the PR if acceptable")
        else:
            print("\n✓ No trigger comment found")
            print("\nTo trigger agent:")
            print(f"  1. Go to: https://github.com/{repo}/issues/{issue_number}")
            print("  2. Add comment: [Approved][OpenCode]")
            print("  3. Run this script again")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        print("\nCommon issues:")
        print("  - Token doesn't have repo access")
        print("  - User not in allowed list")
        print("  - Issue doesn't exist")
        print("  - Commits changed after approval")


async def monitor_recent_issues() -> None:
    """Monitor recent issues for triggers."""
    print("=" * 60)
    print("Monitoring Recent Issues")
    print("=" * 60)

    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    allowed_users = os.getenv("ALLOWED_USERS", "admin").split(",")

    if not all([github_token, repo]):
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY required")
        return

    monitor = IssueMonitor(
        repo=repo,
        github_token=github_token,
        allowed_users=allowed_users,
        openrouter_api_key=openrouter_key,
    )

    print(f"\nRepository: {repo}")
    print("Checking last 10 open issues...\n")

    try:
        results = await monitor.process_recent_issues()

        if results:
            print(f"\n✓ Processed {len(results)} triggered issues:")
            for issue_num, pr_url in results.items():
                print(f"\n  Issue #{issue_num}")
                print(f"  PR: {pr_url}")
        else:
            print("\n✓ No triggered issues found")
            print("\nThis is normal! Agents only activate when:")
            print("  1. An authorized user adds a trigger comment")
            print("  2. Comment format: [Approved][AgentName]")
            print("  3. Valid agents: OpenCode, Claude, Gemini, Crush, Codex")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")


async def continuous_monitoring(interval: int = 300) -> None:
    """Run continuous monitoring with specified interval."""
    print("=" * 60)
    print("Continuous Monitoring Mode")
    print("=" * 60)

    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    allowed_users = os.getenv("ALLOWED_USERS", "admin").split(",")

    if not all([github_token, repo]):
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY required")
        return

    monitor = IssueMonitor(
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
            print(f"[Cycle {cycle}] Checking for triggered issues...")

            try:
                results = await monitor.process_recent_issues()
                if results:
                    print(f"  ✓ Processed {len(results)} issues")
                    for issue_num, pr_url in results.items():
                        print(f"    - Issue #{issue_num} → {pr_url}")
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


async def demonstrate_agent_selection() -> None:
    """Demonstrate different agent options."""
    print("=" * 60)
    print("Agent Selection Guide")
    print("=" * 60)

    agents = {
        "OpenCode": {
            "trigger": "[Approved][OpenCode]",
            "best_for": "Complex code generation, refactoring",
            "model": "Qwen 2.5 Coder (32B)",
            "speed": "Medium",
        },
        "Crush": {
            "trigger": "[Approved][Crush]",
            "best_for": "Quick fixes, simple features",
            "model": "DeepSeek Coder (33B)",
            "speed": "Fast",
        },
        "Claude": {
            "trigger": "[Approved][Claude]",
            "best_for": "Complex logic, architecture",
            "model": "Claude Sonnet 3.5",
            "speed": "Slow (high quality)",
        },
        "Gemini": {
            "trigger": "[Approved][Gemini]",
            "best_for": "Code review, validation",
            "model": "Gemini 1.5 Pro",
            "speed": "Medium",
        },
        "Codex": {
            "trigger": "[Approved][Codex]",
            "best_for": "OpenAI Codex tasks",
            "model": "GPT-4 Codex",
            "speed": "Medium",
        },
    }

    print("\nAvailable Agents:\n")
    for name, info in agents.items():
        print(f"{name}")
        print(f"  Trigger: {info['trigger']}")
        print(f"  Best for: {info['best_for']}")
        print(f"  Model: {info['model']}")
        print(f"  Speed: {info['speed']}")
        print()

    print("Choosing an Agent:")
    print("  - Use OpenCode for most tasks (good balance)")
    print("  - Use Crush for quick fixes")
    print("  - Use Claude for complex problems")
    print("  - Use Gemini for validation")
    print("  - Use Codex for OpenAI-specific features")


def main() -> None:
    """Run issue monitor examples."""
    print("GitHub AI Agents - Issue Monitor Example\n")

    # Parse command line arguments
    if "--help" in sys.argv:
        print("Usage: python issue_monitor_example.py [OPTIONS]\n")
        print("Options:")
        print("  --issue NUMBER      Process specific issue")
        print("  --continuous        Run continuous monitoring")
        print("  --interval SECONDS  Monitoring interval (default: 300)")
        print("  --agents            Show agent selection guide")
        print("  --help              Show this help")
        print("\nEnvironment Variables:")
        print("  GITHUB_TOKEN         Required: GitHub API token")
        print("  GITHUB_REPOSITORY    Required: Repository (owner/repo)")
        print("  OPENROUTER_API_KEY   Optional: OpenRouter API key")
        print("  ALLOWED_USERS        Optional: Authorized users (comma-separated)")
        print("\nExamples:")
        print("  python issue_monitor_example.py --issue 123")
        print("  python issue_monitor_example.py --continuous --interval 600")
        print("  python issue_monitor_example.py --agents")
        return

    if "--agents" in sys.argv:
        asyncio.run(demonstrate_agent_selection())
        return

    if "--issue" in sys.argv:
        try:
            idx = sys.argv.index("--issue")
            issue_num = int(sys.argv[idx + 1])
            asyncio.run(process_single_issue(issue_num))
        except (IndexError, ValueError):
            print("ERROR: --issue requires issue number")
            print("Example: python issue_monitor_example.py --issue 123")
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

    # Default: monitor recent issues once
    asyncio.run(monitor_recent_issues())

    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("\n1. Try --issue NUMBER to process specific issue")
    print("2. Try --continuous for ongoing monitoring")
    print("3. Try --agents to see agent options")
    print("4. Try pr_monitor_example.py for PR workflow")


if __name__ == "__main__":
    main()
