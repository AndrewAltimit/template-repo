#!/bin/bash
# Test script for auto-review functionality

echo "=== Auto Review Test Script ==="
echo "This script tests the auto-review functionality locally"
echo ""

# Set up environment variables
export GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')}"
export REVIEW_ONLY_MODE="true"
export NO_FILE_MODIFICATIONS="true"

# Parse command line arguments
AGENTS="${1:-claude,gemini}"
TARGET="${2:-both}"
REVIEW_DEPTH="${3:-standard}"
COMMENT_STYLE="${4:-consolidated}"

echo "Configuration:"
echo "  Repository: $GITHUB_REPOSITORY"
echo "  Agents: $AGENTS"
echo "  Target: $TARGET"
echo "  Review Depth: $REVIEW_DEPTH"
echo "  Comment Style: $COMMENT_STYLE"
echo ""

# Set review configuration
export REVIEW_AGENTS="$AGENTS"
export REVIEW_TARGET="$TARGET"
export REVIEW_DEPTH="$REVIEW_DEPTH"
export COMMENT_STYLE="$COMMENT_STYLE"
export ENABLED_AGENTS_OVERRIDE="$AGENTS"

# Ensure Python package is installed
echo "Installing GitHub AI Agents package..."
pip3 install --user -e ./packages/github_ai_agents

# Run the review
echo ""
echo "Starting auto-review..."
echo ""

python3 -c "
import os
import sys
import logging
from github_ai_agents.monitors import IssueMonitor, PRMonitor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    target = os.environ.get('REVIEW_TARGET', 'both')

    try:
        if target in ['issues', 'both']:
            logger.info('Processing issues...')
            issue_monitor = IssueMonitor()
            issue_monitor.process_items()

        if target in ['pull-requests', 'both']:
            logger.info('Processing pull requests...')
            pr_monitor = PRMonitor()
            pr_monitor.process_items()

        logger.info('Auto Review completed successfully')

    except Exception as e:
        logger.error(f'Auto Review failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
"

echo ""
echo "=== Auto Review Test Complete ==="
