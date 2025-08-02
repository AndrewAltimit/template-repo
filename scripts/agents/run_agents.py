#!/usr/bin/env python3
"""
Unified Agent Runner

This script manages all AI agents for GitHub automation.
"""

import argparse
import json
import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AgentRunner:
    """Manages and runs AI agents."""

    def __init__(self, config_path: str = None):
        self.agents_dir = Path(__file__).parent
        self.config_path = config_path or self.agents_dir / "config.json"
        self.config = self.load_config()

    def load_config(self) -> dict:
        """Load agent configuration."""
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            return {
                "agents": {
                    "issue_monitor": {"enabled": True},
                    "pr_review_monitor": {"enabled": True},
                }
            }

    def run_agent(self, agent_name: str, args: list = None) -> bool:
        """Run a specific agent."""
        # Use multi-agent version for issue monitor
        if agent_name == "issue_monitor":
            agent_script = self.agents_dir / "issue_monitor_multi_agent.py"
        else:
            agent_script = self.agents_dir / f"{agent_name}.py"

        if not agent_script.exists():
            logger.error(f"Agent script not found: {agent_script}")
            return False

        if not self.config.get("agents", {}).get(agent_name, {}).get("enabled", True):
            logger.info(f"Agent {agent_name} is disabled in config")
            return True

        try:
            cmd = [sys.executable, str(agent_script)]
            if args:
                cmd.extend(args)

            logger.info(f"Running agent: {agent_name}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout:
                logger.info(f"{agent_name} output:\n{result.stdout}")

            logger.info(f"Agent {agent_name} completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Agent {agent_name} failed: {e}")
            if e.stderr:
                logger.error(f"Error output:\n{e.stderr}")
            return False

    def run_all_agents(self, parallel: bool = False) -> dict:
        """Run all enabled agents."""
        agents = ["issue_monitor", "pr_review_monitor"]

        results = {}

        if parallel:
            logger.warning(
                "Running agents in parallel is not recommended as they perform "
                "git operations on the same repository, which can lead to race conditions."
            )
            with ThreadPoolExecutor(max_workers=len(agents)) as executor:
                futures = {executor.submit(self.run_agent, agent): agent for agent in agents}

                for future in as_completed(futures):
                    agent = futures[future]
                    try:
                        results[agent] = future.result()
                    except Exception as e:
                        logger.error(f"Error running agent {agent}: {e}")
                        results[agent] = False
        else:
            # Sequential execution is the default and recommended approach
            for agent in agents:
                results[agent] = self.run_agent(agent)

        return results

    def status(self) -> None:
        """Display status of all agents."""
        print("\n=== AI Agent Status ===\n")

        for agent_name, agent_config in self.config.get("agents", {}).items():
            enabled = agent_config.get("enabled", True)
            status = "✓ Enabled" if enabled else "✗ Disabled"
            print(f"{agent_name}: {status}")

            if enabled and "check_interval_minutes" in agent_config:
                print(f"  Check interval: {agent_config['check_interval_minutes']} minutes")

        print("\n=== Configuration ===")
        print(f"Config file: {self.config_path}")
        print(f"Claude CLI: {self.config.get('claude_cli', {}).get('command', 'Not configured')}")
        print(f"Git author: {self.config.get('git', {}).get('author_name', 'Not configured')}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI Agent Runner")
    parser.add_argument(
        "command",
        choices=["run", "run-all", "status", "issue-monitor", "pr-review-monitor"],
        help="Command to execute",
    )
    parser.add_argument("--config", help="Path to config file", default=None)
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run agents in parallel (NOT recommended - can cause git race conditions)",
    )
    parser.add_argument("--continuous", action="store_true", help="Run agent continuously")

    args = parser.parse_args()

    runner = AgentRunner(args.config)

    if args.command == "status":
        runner.status()
    elif args.command == "run-all":
        results = runner.run_all_agents(parallel=args.parallel)

        print("\n=== Agent Run Results ===")
        for agent, success in results.items():
            status = "✓ Success" if success else "✗ Failed"
            print(f"{agent}: {status}")

        # Exit with error if any agent failed
        if not all(results.values()):
            sys.exit(1)
    elif args.command == "run":
        print("Please specify which agent to run (e.g., issue-monitor, pr-review-monitor)")
        sys.exit(1)
    elif args.command in ["issue-monitor", "pr-review-monitor"]:
        agent_name = args.command.replace("-", "_")
        extra_args = ["--continuous"] if args.continuous else []
        success = runner.run_agent(agent_name, extra_args)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
