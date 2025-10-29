#!/usr/bin/env python3
"""GitHub Projects v2 board integration example.

This example demonstrates using GitHub Projects v2 as an external memory
system for AI agents to track work, dependencies, and state across sessions.
"""

import asyncio
import os
import sys

from github_ai_agents.board.config import BoardConfig
from github_ai_agents.board.manager import BoardManager
from github_ai_agents.board.models import Issue, IssueStatus


async def demonstrate_initialization() -> BoardManager:
    """Initialize board manager and verify connection."""
    print("=" * 60)
    print("Board Initialization")
    print("=" * 60)

    # Get configuration
    config_path = os.getenv("BOARD_CONFIG_PATH", ".github/ai-agents-board.yml")
    # Prefer GITHUB_PROJECTS_TOKEN (classic token for Projects v2)
    github_token = os.getenv("GITHUB_PROJECTS_TOKEN") or os.getenv("GITHUB_TOKEN")

    if not github_token:
        print("ERROR: GitHub token required")
        print("Set GITHUB_PROJECTS_TOKEN (classic token with 'project' scope)")
        print("or GITHUB_TOKEN environment variable")
        sys.exit(1)

    # Check if config file exists
    if not os.path.exists(config_path):
        print(f"ERROR: Board config not found at {config_path}")
        print("\nCreate .github/ai-agents-board.yml with:")
        print(
            """
project:
  number: 1  # Your project number
  owner: your-username

repository: owner/repo

fields:
  status: "Status"
  priority: "Priority"
  agent: "Agent"
  type: "Type"
  blocked_by: "Blocked By"
  discovered_from: "Discovered From"
  size: "Estimated Size"

agents:
  enabled_agents:
    - claude
    - opencode
    - gemini
  auto_discover: true

work_claims:
  timeout: 86400  # 24 hours
  renewal_interval: 3600  # 1 hour
"""
        )
        sys.exit(1)

    # Load configuration
    print(f"Loading config from: {config_path}")
    config = BoardConfig.from_file(config_path)

    print(f"\nProject: #{config.project_number} (owner: {config.project_owner})")
    print(f"Repository: {config.repository}")
    print(f"Enabled agents: {', '.join(config.enabled_agents)}")

    # Initialize manager
    print("\nInitializing board manager...")
    manager = BoardManager(config=config, github_token=github_token)
    await manager.initialize()

    print("✓ Board connection established")
    return manager


async def demonstrate_query_ready_work(manager: BoardManager) -> Issue | None:
    """Query ready work from the board."""
    print("\n" + "=" * 60)
    print("Querying Ready Work")
    print("=" * 60)

    # Query all ready work
    print("\n1. Getting all ready work (limit 10)...")
    issues = await manager.get_ready_work(limit=10)

    if not issues:
        print("  No ready work found")
        print("  (Issues must be unblocked and unclaimed)")
        return None

    print(f"  Found {len(issues)} ready issues:")
    for issue in issues:
        print(f"\n  #{issue.number}: {issue.title}")
        print(f"    Status: {issue.status.value if issue.status else 'None'}")
        print(f"    Priority: {issue.priority.value if issue.priority else 'None'}")
        print(f"    Agent: {issue.agent or 'Unassigned'}")
        if issue.blocked_by:
            print(f"    Blocked by: {', '.join(map(str, issue.blocked_by))}")

    # Query agent-specific work
    print("\n2. Getting work for specific agent (claude)...")
    claude_issues = await manager.get_ready_work(agent_name="claude", limit=5)
    print(f"  Found {len(claude_issues)} issues for claude")

    # Store for later use
    return issues[0] if issues else None


async def demonstrate_claim_workflow(manager: BoardManager, issue: Issue) -> None:
    """Demonstrate claiming and releasing work."""
    print("\n" + "=" * 60)
    print("Claim Workflow")
    print("=" * 60)

    if not issue:
        print("No issue available for claim demonstration")
        return

    agent_name = "example-agent"
    session_id = "demo-session-12345"

    print(f"\nIssue: #{issue.number} - {issue.title}")
    print(f"Agent: {agent_name}")
    print(f"Session: {session_id}")

    # Claim work
    print("\n1. Claiming work...")
    success = await manager.claim_work(issue.number, agent_name, session_id)

    if success:
        print("  ✓ Work claimed successfully")
        print("  Claim timeout: 24 hours")
        print("  Renewal interval: 1 hour")
    else:
        print("  ✗ Failed to claim (already claimed by another agent)")
        return

    # Update status to in-progress
    print("\n2. Updating status to In Progress...")
    await manager.update_status(issue.number, IssueStatus.IN_PROGRESS)
    print("  ✓ Status updated")

    # Simulate work...
    print("\n3. Simulating work (agent would implement here)...")
    await asyncio.sleep(1)

    # Release work
    print("\n4. Releasing work as completed...")
    await manager.release_work(issue.number, agent_name, "completed")
    print("  ✓ Work released")
    print("  Status automatically updated to Done")


async def demonstrate_dependencies(manager: BoardManager) -> None:
    """Demonstrate dependency management."""
    print("\n" + "=" * 60)
    print("Dependency Management")
    print("=" * 60)

    # Get ready work to use for demo
    issues = await manager.get_ready_work(limit=2)
    if len(issues) < 2:
        print("Need at least 2 issues for dependency demo")
        return

    issue1 = issues[0]
    issue2 = issues[1]

    print(f"\nIssue A: #{issue1.number} - {issue1.title}")
    print(f"Issue B: #{issue2.number} - {issue2.title}")

    # Add blocker
    print("\n1. Adding blocker: Issue A blocked by Issue B...")
    success = await manager.add_blocker(issue1.number, issue2.number)
    if success:
        print("  ✓ Blocker added")
        print(f"  Issue #{issue1.number} cannot be worked until #{issue2.number} is done")
    else:
        print("  ✗ Failed to add blocker")

    # Get dependency graph
    print("\n2. Getting dependency graph for Issue A...")
    graph = await manager.get_dependency_graph(issue1.number)
    if graph:
        print(f"  Root: #{graph.issue.number}")
        if graph.blocked_by:
            print(f"  Blocked by: {', '.join(f'#{i.number}' for i in graph.blocked_by)}")
        if graph.blocks:
            print(f"  Blocks: {', '.join(f'#{i.number}' for i in graph.blocks)}")
        if graph.parent:
            print(f"  Discovered from: #{graph.parent.number}")
        if graph.children:
            print(f"  Children: {', '.join(f'#{i.number}' for i in graph.children)}")
    else:
        print("  ✗ Failed to get dependency graph")


async def demonstrate_discovery_workflow(manager: BoardManager) -> None:
    """Demonstrate discovering new issues while working."""
    print("\n" + "=" * 60)
    print("Issue Discovery Workflow")
    print("=" * 60)

    print("\nScenario: Agent discovers a blocker while implementing")
    print("\n1. Agent working on Issue #100")
    print("2. Discovers broken test in test_utils.py")
    print("3. Files new issue for the blocker")
    print("4. Marks relationship (discovered from #100)")
    print("5. Adds as blocker to current issue")
    print("6. Releases current work as 'blocked'")

    print("\nIn practice:")
    print(
        """
    # Agent discovers issue
    blocker = await manager.create_issue_with_metadata(
        title="Fix broken test in test_utils.py",
        body="Found while implementing #100",
        type=IssueType.BUG,
        priority=IssuePriority.HIGH
    )

    # Mark relationship
    await manager.mark_discovered_from(blocker.number, 100)

    # Add as blocker
    await manager.add_blocker(100, blocker.number)

    # Release current work
    await manager.release_work(100, "agent", "blocked")
    """
    )


async def demonstrate_claim_renewal(manager: BoardManager) -> None:
    """Demonstrate claim renewal for long-running tasks."""
    print("\n" + "=" * 60)
    print("Claim Renewal")
    print("=" * 60)

    print("\nFor tasks taking >1 hour:")
    print("  - Claims expire after 24 hours")
    print("  - Agents should renew every hour")
    print("  - Prevents claim expiration during active work")

    print("\nExample:")
    print(
        """
    # Long-running task
    session_id = "long-task-session"
    await manager.claim_work(123, "agent", session_id)

    # Work for 2 hours
    for hour in range(2):
        # Do work...
        await work_for_an_hour()

        # Renew claim
        await manager.renew_claim(123, "agent", session_id)
        print(f"Claim renewed at hour {hour + 1}")

    # Complete work
    await manager.release_work(123, "agent", "completed")
    """
    )


async def demonstrate_multi_session_workflow(manager: BoardManager) -> None:
    """Demonstrate agent resuming work across sessions."""
    print("\n" + "=" * 60)
    print("Multi-Session Workflow")
    print("=" * 60)

    print("\nScenario: Agent session times out mid-implementation")

    print("\n--- Session 1 (15 minutes, times out) ---")
    print("1. Query ready work")
    print("2. Claim issue #123")
    print("3. Start implementation")
    print("4. [Session timeout]")

    print("\n--- Session 2 (1 hour later) ---")
    print("1. Query ready work")
    print("   - Issue #123 appears (claim expired)")
    print("2. Re-claim issue #123 with new session ID")
    print("3. Continue implementation")
    print("4. Complete and release")

    print("\nKey Point: Board acts as memory across sessions")
    print("  - Work state preserved in GitHub")
    print("  - No local state needed")
    print("  - Agent can resume from any machine")


def main() -> None:
    """Run board integration examples."""
    print("GitHub AI Agents - Board Integration Example\n")

    if "--help" in sys.argv:
        print("Usage: python board_integration_example.py [OPTIONS]\n")
        print("Options:")
        print("  --query-only       Only demonstrate querying")
        print("  --claim-demo       Demonstrate claim workflow")
        print("  --dependencies     Show dependency management")
        print("  --all              Run all demonstrations")
        print("  --help             Show this help")
        print("\nEnvironment Variables:")
        print("  GITHUB_TOKEN         Required: GitHub API token")
        print("  GITHUB_PROJECT_NUMBER  Required: Project number")
        print("  BOARD_CONFIG_PATH    Optional: Config path (default: .github/ai-agents-board.yml)")
        print("\nExamples:")
        print("  python board_integration_example.py --query-only")
        print("  python board_integration_example.py --all")
        return

    async def run_examples():
        # Initialize
        manager = await demonstrate_initialization()

        # Query work
        issue = await demonstrate_query_ready_work(manager)

        if "--query-only" in sys.argv:
            return

        # Claim workflow
        if issue and ("--claim-demo" in sys.argv or "--all" in sys.argv):
            await demonstrate_claim_workflow(manager, issue)

        # Dependencies
        if "--dependencies" in sys.argv or "--all" in sys.argv:
            await demonstrate_dependencies(manager)

        # Discovery workflow
        if "--all" in sys.argv:
            await demonstrate_discovery_workflow(manager)
            await demonstrate_claim_renewal(manager)
            await demonstrate_multi_session_workflow(manager)

    # Run examples
    try:
        asyncio.run(run_examples())

        print("\n" + "=" * 60)
        print("Next Steps")
        print("=" * 60)
        print("\n1. Try multi_agent_example.py for concurrent agents")
        print("2. Integrate board with issue/PR monitors")
        print("3. Set up GitHub Actions for automated monitoring")
        print("4. Review docs/board-integration.md for details")

    except KeyboardInterrupt:
        print("\n\nExample interrupted")
    except Exception as e:
        print(f"\n\nError: {e}")
        print("Check environment variables and board configuration")


if __name__ == "__main__":
    main()
