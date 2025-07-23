#!/bin/bash
# Wrapper script for running AI agents

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

# Set up environment
export GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || echo "")}"

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check for GitHub CLI
    if ! command -v gh &> /dev/null; then
        echo "Error: GitHub CLI (gh) is not installed"
        echo "Install from: https://cli.github.com/"
        exit 1
    fi

    # Check for Python
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is not installed"
        exit 1
    fi

    # Check for Node.js (for Claude CLI)
    if ! command -v node &> /dev/null; then
        echo "Warning: Node.js is not installed. Claude CLI features will not work."
        echo "Install Node.js 22+ for full functionality"
    fi

    # Check GitHub auth
    if ! gh auth status &> /dev/null; then
        echo "Error: Not authenticated with GitHub CLI"
        echo "Run: gh auth login"
        exit 1
    fi

    # Check repository
    if [ -z "$GITHUB_REPOSITORY" ]; then
        echo "Error: Could not determine GitHub repository"
        echo "Set GITHUB_REPOSITORY environment variable or run from a git repository"
        exit 1
    fi

    echo "✓ All prerequisites met"
    echo "  Repository: $GITHUB_REPOSITORY"
    echo ""
}

# Main script
case "${1:-help}" in
    status)
        check_prerequisites
        python3 scripts/agents/run_agents.py status
        ;;

    run-all)
        check_prerequisites
        echo "Running all AI agents..."
        python3 scripts/agents/run_agents.py run-all "${@:2}"
        ;;

    issue-monitor)
        check_prerequisites
        echo "Running issue monitor agent..."
        python3 scripts/agents/run_agents.py issue-monitor "${@:2}"
        ;;

    pr-review-monitor)
        check_prerequisites
        echo "Running PR review monitor agent..."
        python3 scripts/agents/run_agents.py pr-review-monitor "${@:2}"
        ;;

    test)
        check_prerequisites
        echo "Testing agents in dry-run mode..."
        # Add dry-run functionality here
        echo "Dry-run not yet implemented"
        ;;

    help|--help|-h|*)
        cat << EOF
AI Agent Runner

Usage: $0 [command] [options]

Commands:
  status              Show status of all agents
  run-all             Run all enabled agents
  issue-monitor       Run issue monitoring agent
  pr-review-monitor   Run PR review monitoring agent
  test                Test agents in dry-run mode
  help                Show this help message

Options:
  --continuous        Run agent continuously (for specific agents)
  --parallel          Run agents in parallel (for run-all)
  --config <path>     Use custom config file

Examples:
  $0 status
  $0 run-all --parallel
  $0 issue-monitor --continuous
  $0 pr-review-monitor

Environment Variables:
  GITHUB_REPOSITORY   Repository to monitor (auto-detected if in git repo)
  GITHUB_TOKEN        GitHub access token (auto-detected from gh cli)

Prerequisites:
  - GitHub CLI (gh) authenticated
  - Python 3.x
  - Node.js 22+ (for Claude CLI features)
EOF
        ;;
esac
