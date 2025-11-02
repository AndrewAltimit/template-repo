#!/usr/bin/env python3
"""Multi-agent coordination example.

This example demonstrates multiple AI agents working concurrently without
conflicts using the GitHub Projects v2 board for coordination.
"""

import asyncio
import os
import sys
import uuid
from typing import Dict, List

from github_agents.board.config import BoardConfig
from github_agents.board.manager import BoardManager
from github_agents.board.models import Issue, IssueStatus
from github_agents.monitors.issue_monitor import IssueMonitor


class AgentWorker:
    """Represents a single agent worker."""

    def __init__(
        self,
        name: str,
        board_manager: BoardManager,
        issue_monitor: IssueMonitor,
        color: str = "blue",
    ):
        """Initialize agent worker."""
        self.name = name
        self.board = board_manager
        self.monitor = issue_monitor
        self.color = color
        self.session_id = f"{name}-{uuid.uuid4()}"
        self.completed_issues: List[int] = []
        self.failed_issues: List[int] = []

    async def work_cycle(self) -> None:
        """Execute one work cycle."""
        print(f"[{self.name}] Starting work cycle...")

        # Get ready work for this agent
        issues = await self.board.get_ready_work(agent_name=self.name, limit=3)

        if not issues:
            print(f"[{self.name}] No ready work found")
            return

        print(f"[{self.name}] Found {len(issues)} ready issues")

        # Process each issue
        for issue in issues:
            await self.process_issue(issue)

    async def process_issue(self, issue: Issue) -> None:
        """Process a single issue."""
        print(f"[{self.name}] Processing #{issue.number}: {issue.title}")

        # Try to claim work
        claim_success = await self.board.claim_work(issue.number, self.name, self.session_id)

        if not claim_success:
            print(f"[{self.name}]   ✗ Already claimed by another agent")
            return

        print(f"[{self.name}]   ✓ Claimed issue")

        try:
            # Update status to in-progress
            await self.board.update_status(issue.number, IssueStatus.IN_PROGRESS)
            print(f"[{self.name}]   → Status: In Progress")

            # Simulate implementation work
            print(f"[{self.name}]   → Implementing solution...")
            await asyncio.sleep(2)  # Simulate work time

            # In real scenario, would call:
            # await self.monitor.process_issue(issue.number)

            # Mark as completed
            await self.board.release_work(issue.number, self.name, "completed")
            self.completed_issues.append(issue.number)
            print(f"[{self.name}]   ✓ Completed #{issue.number}")

        except Exception as e:
            print(f"[{self.name}]   ✗ Error: {e}")
            self.failed_issues.append(issue.number)
            # Release as error
            await self.board.release_work(issue.number, self.name, "error")

    def get_stats(self) -> Dict:
        """Get agent statistics."""
        return {
            "name": self.name,
            "completed": len(self.completed_issues),
            "failed": len(self.failed_issues),
            "completed_issues": self.completed_issues,
            "failed_issues": self.failed_issues,
        }


async def demonstrate_concurrent_agents() -> None:
    """Demonstrate multiple agents working concurrently."""
    print("=" * 60)
    print("Multi-Agent Concurrent Processing")
    print("=" * 60)

    # Initialize board
    config_path = os.getenv("BOARD_CONFIG_PATH", "ai-agents-board.yml")
    github_token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not all([github_token, repo]):
        print("ERROR: GITHUB_TOKEN and GITHUB_REPOSITORY required")
        return

    print("\n1. Initializing board manager...")
    config = BoardConfig.from_file(config_path)
    board = BoardManager(config=config, github_token=github_token)
    await board.initialize()
    print("   ✓ Board connected")

    print("\n2. Creating issue monitor...")
    monitor = IssueMonitor(
        repo=repo,
        github_token=github_token,
        openrouter_api_key=openrouter_key,
        board_manager=board,
    )
    print("   ✓ Monitor ready")

    # Create multiple agents
    print("\n3. Creating agents...")
    agents = [
        AgentWorker("claude", board, monitor, "blue"),
        AgentWorker("opencode", board, monitor, "green"),
        AgentWorker("gemini", board, monitor, "yellow"),
    ]
    print(f"   ✓ Created {len(agents)} agents")

    # Run agents concurrently
    print("\n4. Running agents concurrently...")
    print("-" * 60)

    tasks = [agent.work_cycle() for agent in agents]
    await asyncio.gather(*tasks)

    print("-" * 60)

    # Show results
    print("\n5. Results:")
    print("=" * 60)
    for agent in agents:
        stats = agent.get_stats()
        print(f"\n{stats['name'].upper()}")
        print(f"  Completed: {stats['completed']}")
        print(f"  Failed: {stats['failed']}")
        if stats["completed_issues"]:
            issues_str = ", ".join(f"#{n}" for n in stats["completed_issues"])
            print(f"  Issues: {issues_str}")


async def demonstrate_claim_conflicts() -> None:
    """Demonstrate how claims prevent conflicts."""
    print("\n" + "=" * 60)
    print("Claim Conflict Prevention")
    print("=" * 60)

    config_path = os.getenv("BOARD_CONFIG_PATH", "ai-agents-board.yml")
    github_token = os.getenv("GITHUB_TOKEN")

    config = BoardConfig.from_file(config_path)
    board = BoardManager(config=config, github_token=github_token)
    await board.initialize()

    # Get one issue
    issues = await board.get_ready_work(limit=1)
    if not issues:
        print("\nNo ready issues for demo")
        return

    issue = issues[0]
    print(f"\nIssue: #{issue.number} - {issue.title}")

    # Try to claim from two agents concurrently
    print("\n1. Two agents trying to claim simultaneously...")

    async def try_claim(agent_name: str) -> bool:
        session_id = f"{agent_name}-{uuid.uuid4()}"
        success = await board.claim_work(issue.number, agent_name, session_id)
        if success:
            print(f"   [{agent_name}] ✓ Claimed successfully")
        else:
            print(f"   [{agent_name}] ✗ Claim failed (already taken)")
        return bool(success)

    # Run concurrent claims
    results = await asyncio.gather(try_claim("agent1"), try_claim("agent2"))

    # Exactly one should succeed
    success_count = sum(results)
    print(f"\n2. Result: {success_count} agent succeeded")
    print("   ✓ Conflict prevented by claim system")

    # Clean up
    await board.release_work(issue.number, "agent1", "abandoned")
    await board.release_work(issue.number, "agent2", "abandoned")


async def demonstrate_work_distribution() -> None:
    """Demonstrate how work is distributed across agents."""
    print("\n" + "=" * 60)
    print("Work Distribution")
    print("=" * 60)

    config_path = os.getenv("BOARD_CONFIG_PATH", "ai-agents-board.yml")
    github_token = os.getenv("GITHUB_TOKEN")

    config = BoardConfig.from_file(config_path)
    board = BoardManager(config=config, github_token=github_token)
    await board.initialize()

    print("\n1. Querying work for different agents:")

    agents = ["claude", "opencode", "gemini", "crush"]
    for agent in agents:
        issues = await board.get_ready_work(agent_name=agent, limit=10)
        print(f"   {agent}: {len(issues)} issues")

    print("\n2. Querying all ready work (no agent filter):")
    all_issues = await board.get_ready_work(limit=50)
    print(f"   Total: {len(all_issues)} ready issues")

    print("\n3. Work Distribution Strategy:")
    print("   - Agent-specific query returns assigned work")
    print("   - Generic query returns all unassigned work")
    print("   - Agents can claim unassigned work")
    print("   - First to claim wins")


async def demonstrate_long_running_coordination() -> None:
    """Demonstrate coordination for long-running tasks."""
    print("\n" + "=" * 60)
    print("Long-Running Task Coordination")
    print("=" * 60)

    print("\nScenario: Multiple agents working on large feature")
    print("\n1. Main issue: Implement user authentication (#100)")
    print("   Status: In Progress")
    print("   Agent: claude")

    print("\n2. Agent discovers sub-tasks:")
    print("   - #101: Create User model (claude)")
    print("   - #102: Add JWT validation (opencode)")
    print("   - #103: Update API endpoints (gemini)")

    print("\n3. Dependencies:")
    print("   #102 blocked by #101 (needs User model)")
    print("   #103 blocked by #102 (needs JWT)")

    print("\n4. Execution Order:")
    print("   Hour 1: claude works on #101")
    print("   Hour 2: opencode starts #102 (unblocked)")
    print("   Hour 3: gemini starts #103 (unblocked)")
    print("   Hour 4: claude completes #100 (all sub-tasks done)")

    print("\n5. Key Features:")
    print("   ✓ Automatic dependency resolution")
    print("   ✓ Parallel work where possible")
    print("   ✓ No manual coordination needed")
    print("   ✓ Board tracks full work graph")


async def demonstrate_claim_expiration() -> None:
    """Demonstrate claim expiration and recovery."""
    print("\n" + "=" * 60)
    print("Claim Expiration and Recovery")
    print("=" * 60)

    print("\nScenario: Agent session crashes mid-implementation")

    print("\n1. Initial State:")
    print("   Issue #123: Status=In Progress, Agent=claude")
    print("   Claim timestamp: 2025-10-24 10:00:00")
    print("   Claim timeout: 24 hours")

    print("\n2. Agent Crashes (10:15):")
    print("   ✗ Session ends unexpectedly")
    print("   ✗ No release_work() called")
    print("   → Issue remains In Progress")
    print("   → Claim still active")

    print("\n3. Next Day (2025-10-25 11:00):")
    print("   → Claim expired (>24 hours)")
    print("   → Issue appears in ready work query")
    print("   → New agent can claim")

    print("\n4. Recovery:")
    print("   New agent (or same agent, new session):")
    print("   - Queries ready work")
    print("   - Sees #123 with expired claim")
    print("   - Claims with new session ID")
    print("   - Continues or restarts implementation")

    print("\n5. Best Practices:")
    print("   - Use reasonable timeouts (24h default)")
    print("   - Renew claims for long tasks (>1h)")
    print("   - Always release when possible")
    print("   - Let expiration handle crashes")


def main() -> None:
    """Run multi-agent examples."""
    print("GitHub AI Agents - Multi-Agent Coordination Example\n")

    if "--help" in sys.argv:
        print("Usage: python multi_agent_example.py [OPTIONS]\n")
        print("Options:")
        print("  --concurrent       Run concurrent agent demo")
        print("  --conflicts        Show conflict prevention")
        print("  --distribution     Show work distribution")
        print("  --long-running     Show long-running coordination")
        print("  --expiration       Show claim expiration")
        print("  --all              Run all demonstrations")
        print("  --help             Show this help")
        print("\nEnvironment Variables:")
        print("  GITHUB_TOKEN         Required: GitHub API token")
        print("  GITHUB_REPOSITORY    Required: Repository (owner/repo)")
        print("  GITHUB_PROJECT_NUMBER  Required: Project number")
        print("  OPENROUTER_API_KEY   Optional: For actual implementation")
        print("  BOARD_CONFIG_PATH    Optional: Config path")
        print("\nExamples:")
        print("  python multi_agent_example.py --concurrent")
        print("  python multi_agent_example.py --all")
        return

    async def run_demos():
        if "--concurrent" in sys.argv or "--all" in sys.argv:
            await demonstrate_concurrent_agents()

        if "--conflicts" in sys.argv or "--all" in sys.argv:
            await demonstrate_claim_conflicts()

        if "--distribution" in sys.argv or "--all" in sys.argv:
            await demonstrate_work_distribution()

        if "--long-running" in sys.argv or "--all" in sys.argv:
            await demonstrate_long_running_coordination()

        if "--expiration" in sys.argv or "--all" in sys.argv:
            await demonstrate_claim_expiration()

        # Default: run concurrent demo
        if not any(
            opt in sys.argv
            for opt in ["--concurrent", "--conflicts", "--distribution", "--long-running", "--expiration", "--all"]
        ):
            await demonstrate_concurrent_agents()

    try:
        asyncio.run(run_demos())

        print("\n" + "=" * 60)
        print("Next Steps")
        print("=" * 60)
        print("\n1. Try custom_agent_example.py for specialized agents")
        print("2. Set up GitHub Actions for automated coordination")
        print("3. Review docs/board-integration.md for architecture")
        print("4. Experiment with different agent configurations")

    except KeyboardInterrupt:
        print("\n\nExample interrupted")
    except Exception as e:
        print(f"\n\nError: {e}")
        print("Check environment variables and board configuration")


if __name__ == "__main__":
    main()
