#!/bin/sh
# Setup script for agent-agnostic security hooks
#
# Source this file in your agent's environment or shell configuration:
#   . /path/to/setup-agent-hooks.sh
#
# This will:
# 1. Set up an alias for gh commands to use the security wrapper
# 2. Export necessary environment variables
# 3. Ensure all GitHub operations are validated
#
# POSIX-compliant for maximum compatibility

# Get the directory of this script
# Note: $0 might not work correctly when sourced, so we try multiple methods
if [ -n "${BASH_SOURCE:-}" ]; then
    # Bash - use BASH_SOURCE array
    # shellcheck disable=SC3054  # We're intentionally checking for Bash features
    HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [ -n "${ZSH_VERSION:-}" ]; then
    # Zsh specific - use 0 variable which contains script path
    # shellcheck disable=SC3057  # Zsh-specific string indexing intentionally used
    if [ -n "${0:-}" ]; then
        # Try to use $0 in Zsh (it usually contains the full path when sourced)
        HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)" 2>/dev/null || HOOKS_DIR="$(pwd)/automation/security"
    else
        HOOKS_DIR="$(pwd)/automation/security"
    fi
else
    # POSIX fallback - may not work when sourced
    HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

# Set up gh alias to use the wrapper
# shellcheck disable=SC2139
alias gh="${HOOKS_DIR}/gh-wrapper.sh"

# Export the hooks directory for use by other scripts
export AGENT_HOOKS_DIR="${HOOKS_DIR}"

# Set up a function to check if hooks are active
agent_hooks_status() {
    echo "Agent security hooks status:"

    # Check if gh is aliased (POSIX-compliant check)
    if alias gh 2>/dev/null | grep -q "gh-wrapper.sh"; then
        echo "  - gh wrapper: active (aliased)"
        echo "  - Status: ✓ Active"
    else
        echo "  - gh wrapper: not active"
        echo "  - Status: ✗ Inactive"
    fi

    echo "  - Hooks directory: ${AGENT_HOOKS_DIR}"

    # Check if required files exist
    if [ -f "${AGENT_HOOKS_DIR}/gh-wrapper.sh" ]; then
        echo "  - Wrapper script: ✓ Found"
    else
        echo "  - Wrapper script: ✗ Missing"
    fi

    if [ -f "${AGENT_HOOKS_DIR}/github-secrets-masker.py" ]; then
        echo "  - Secret masker: ✓ Found"
    else
        echo "  - Secret masker: ✗ Missing"
    fi

    if [ -f "${AGENT_HOOKS_DIR}/gh-comment-validator.py" ]; then
        echo "  - Comment validator: ✓ Found"
    else
        echo "  - Comment validator: ✗ Missing"
    fi
}

# Check for Python 3 dependency
if ! command -v python3 >/dev/null 2>&1; then
    # Only warn if not in silent mode
    if [ -z "${AGENT_HOOKS_SILENT:-}" ]; then
        echo "⚠️  Warning: 'python3' command not found. The gh security wrapper will not function." >&2
        echo "    Please install Python 3 or run in a container with Python available." >&2
    fi
fi

# Print confirmation (unless AGENT_HOOKS_SILENT is set)
if [ -z "${AGENT_HOOKS_SILENT:-}" ]; then
    echo "Agent security hooks activated!"
    echo "  - gh commands will now be validated for security and formatting"
    echo "  - Run 'agent_hooks_status' to check hook status"
    echo ""
    echo "To make this permanent, add to your shell configuration:"
    echo "  . ${HOOKS_DIR}/setup-agent-hooks.sh"
fi
