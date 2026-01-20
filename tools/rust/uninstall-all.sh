#!/bin/bash
# Uninstall all Rust CLI tools
#
# Usage:
#   ./uninstall-all.sh              # Uninstall all tools
#   ./uninstall-all.sh tool1 tool2  # Uninstall specific tools

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# All available tools
TOOLS=(
    "board-manager"
    "code-parser"
    "gh-validator"
    "git-guard"
    "github-agents-cli"
    "markdown-link-checker"
    "mcp-code-quality"
    "pr-monitor"
)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo "============================================"
    echo "$1"
    echo "============================================"
    echo ""
}

# Show usage
usage() {
    echo "Rust CLI Tools Uninstaller"
    echo ""
    echo "Usage:"
    echo "  $0              Uninstall all tools"
    echo "  $0 tool1 tool2  Uninstall specific tools"
    echo ""
    echo "Available tools:"
    for tool in "${TOOLS[@]}"; do
        echo "  - $tool"
    done
}

# Uninstall a single tool
uninstall_tool() {
    local tool="$1"
    local tool_dir="${SCRIPT_DIR}/${tool}"
    local uninstall_script="${tool_dir}/uninstall.sh"

    if [ ! -d "$tool_dir" ]; then
        echo -e "${RED}Tool not found: $tool${NC}"
        return 1
    fi

    if [ ! -f "$uninstall_script" ]; then
        echo -e "${YELLOW}No uninstall script for: $tool${NC}"
        return 1
    fi

    print_header "Uninstalling $tool"
    bash "$uninstall_script"
}

# Main
main() {
    # Handle arguments
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        usage
        exit 0
    fi

    # Determine which tools to uninstall
    local tools_to_uninstall=()
    if [ $# -eq 0 ]; then
        tools_to_uninstall=("${TOOLS[@]}")
    else
        tools_to_uninstall=("$@")
    fi

    print_header "Rust CLI Tools Uninstallation"

    echo "Tools to uninstall:"
    for tool in "${tools_to_uninstall[@]}"; do
        echo "  - $tool"
    done
    echo ""

    local success=0
    local failed=0

    for tool in "${tools_to_uninstall[@]}"; do
        if uninstall_tool "$tool"; then
            ((success++))
        else
            ((failed++))
        fi
    done

    print_header "Uninstallation Summary"

    echo -e "${GREEN}Successful: $success${NC}"
    if [ $failed -gt 0 ]; then
        echo -e "${RED}Failed: $failed${NC}"
    fi

    echo ""
    echo "Uninstallation complete."
    echo ""

    if [ $failed -gt 0 ]; then
        exit 1
    fi
}

main "$@"
