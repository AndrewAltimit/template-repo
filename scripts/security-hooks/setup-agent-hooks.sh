#!/bin/bash
# Setup script for agent-agnostic security hooks
#
# Source this file in your agent's environment or shell configuration:
#   source /path/to/setup-agent-hooks.sh
#
# This will:
# 1. Set up an alias for gh commands to use the security wrapper
# 2. Export necessary environment variables
# 3. Ensure all GitHub operations are validated

# Get the directory of this script
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set up gh alias to use the wrapper
# shellcheck disable=SC2139
alias gh="${HOOKS_DIR}/gh-wrapper.sh"

# Export the hooks directory for use by other scripts
export AGENT_HOOKS_DIR="${HOOKS_DIR}"

# Optional: Set up a function to check if hooks are active
agent_hooks_status() {
    echo "Agent security hooks status:"
    echo "  - gh wrapper: $(type -t gh)"
    echo "  - Hooks directory: ${AGENT_HOOKS_DIR}"
    if type gh | grep -q "aliased to.*gh-wrapper.sh"; then
        echo "  - Status: ✓ Active"
    else
        echo "  - Status: ✗ Inactive"
    fi
}

# Print confirmation
echo "Agent security hooks activated!"
echo "  - gh commands will now be validated for security and formatting"
echo "  - Run 'agent_hooks_status' to check hook status"
echo ""
echo "To make this permanent, add to your shell configuration:"
echo "  source ${HOOKS_DIR}/setup-agent-hooks.sh"
