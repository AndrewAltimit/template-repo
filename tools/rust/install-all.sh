#!/bin/bash
# Install all Rust CLI tools
#
# Usage:
#   ./install-all.sh              # Install all tools
#   ./install-all.sh --list       # List available tools
#   ./install-all.sh tool1 tool2  # Install specific tools

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
    echo "Rust CLI Tools Installer"
    echo ""
    echo "Usage:"
    echo "  $0              Install all tools"
    echo "  $0 --list       List available tools"
    echo "  $0 tool1 tool2  Install specific tools"
    echo ""
    echo "Available tools:"
    for tool in "${TOOLS[@]}"; do
        echo "  - $tool"
    done
}

# List tools
list_tools() {
    echo "Available Rust CLI tools:"
    echo ""
    for tool in "${TOOLS[@]}"; do
        local desc=""
        case "$tool" in
            "board-manager")       desc="GitHub project board operations" ;;
            "code-parser")         desc="Parse and apply code blocks from AI responses" ;;
            "gh-validator")        desc="GitHub CLI wrapper with secret masking" ;;
            "git-guard")           desc="Git wrapper requiring sudo for dangerous ops" ;;
            "github-agents-cli")   desc="AI agent CLI for issue/PR automation" ;;
            "markdown-link-checker") desc="Fast concurrent markdown link validator" ;;
            "mcp-code-quality")    desc="MCP server for code quality tools" ;;
            "pr-monitor")          desc="PR monitoring for comments and reviews" ;;
        esac
        printf "  %-25s %s\n" "$tool" "$desc"
    done
}

# Install a single tool
install_tool() {
    local tool="$1"
    local tool_dir="${SCRIPT_DIR}/${tool}"
    local install_script="${tool_dir}/install.sh"

    if [ ! -d "$tool_dir" ]; then
        echo -e "${RED}Tool not found: $tool${NC}"
        return 1
    fi

    if [ ! -f "$install_script" ]; then
        echo -e "${YELLOW}No install script for: $tool${NC}"
        return 1
    fi

    print_header "Installing $tool"
    bash "$install_script"
}

# Main
main() {
    # Handle arguments
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        usage
        exit 0
    fi

    if [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
        list_tools
        exit 0
    fi

    # Determine which tools to install
    local tools_to_install=()
    if [ $# -eq 0 ]; then
        tools_to_install=("${TOOLS[@]}")
    else
        tools_to_install=("$@")
    fi

    print_header "Rust CLI Tools Installation"

    echo "Tools to install:"
    for tool in "${tools_to_install[@]}"; do
        echo "  - $tool"
    done
    echo ""

    # Ensure ~/.local/bin exists and is in PATH
    mkdir -p "${HOME}/.local/bin"

    local success=0
    local failed=0

    for tool in "${tools_to_install[@]}"; do
        if install_tool "$tool"; then
            ((success++))
        else
            ((failed++))
        fi
    done

    print_header "Installation Summary"

    echo -e "${GREEN}Successful: $success${NC}"
    if [ $failed -gt 0 ]; then
        echo -e "${RED}Failed: $failed${NC}"
    fi

    echo ""
    echo "Make sure ~/.local/bin is in your PATH:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""

    if [ $failed -gt 0 ]; then
        exit 1
    fi
}

main "$@"
