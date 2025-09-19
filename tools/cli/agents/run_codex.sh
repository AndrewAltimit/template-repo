#!/bin/bash
# run_codex.sh - Start Codex CLI for AI-powered code generation

set -e

echo "🚀 Starting Codex CLI"

# Check if codex CLI is available
if ! command -v codex &> /dev/null; then
    echo "❌ codex CLI not found. Installing..."
    echo ""
    echo "Please install Codex with:"
    echo "   npm install -g @openai/codex"
    echo ""
    echo "Or in the container version which has it pre-installed:"
    echo "   ./tools/cli/containers/run_codex_container.sh"
    exit 1
fi

# Check for auth file
AUTH_FILE="$HOME/.codex/auth.json"
if [ ! -f "$AUTH_FILE" ]; then
    echo "❌ Codex authentication not found at $AUTH_FILE"
    echo ""
    echo "Please authenticate with Codex first:"
    echo "   codex auth"
    echo ""
    echo "Or run the container version with mounted auth:"
    echo "   ./tools/cli/containers/run_codex_container.sh"
    exit 1
fi

echo "✅ Codex CLI found and authenticated"

# Set up repository root and initialize security hooks
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# Source shared security hook initialization
# shellcheck source=/dev/null
source "$REPO_ROOT/automation/security/initialize-agent-hooks.sh"

# Note about Codex permissions
if [ $# -eq 0 ]; then
    # Only show note if no arguments provided (interactive mode)
    echo "🤖 Codex Configuration"
    echo ""
    echo "ℹ️  Note: Codex is an AI-powered code generation tool by OpenAI."
    echo "It can help with code completion, generation, and refactoring."
    echo ""
    read -r -p "Press Enter to continue to interactive mode, or Ctrl+C to cancel... "
    echo ""
fi

# Parse command line arguments
MODE="interactive"
QUERY=""
CONTEXT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--query)
            QUERY="$2"
            MODE="single"
            shift 2
            ;;
        -c|--context)
            CONTEXT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>    Single query mode with specified prompt"
            echo "  -c, --context <file>    Add context from file"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Interactive Mode (default):"
            echo "  Start an interactive session with Codex"
            echo ""
            echo "Single Query Mode:"
            echo "  $0 -q 'Write a Python function to calculate fibonacci'"
            echo ""
            echo "With Context:"
            echo "  $0 -q 'Refactor this code' -c existing_code.py"
            echo ""
            echo "Note: Codex requires authentication via 'codex auth' first."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Execute based on mode
if [ "$MODE" = "single" ]; then
    echo "📝 Running single query..."
    echo ""

    # Note: Codex CLI may require interactive mode
    # This is a best-effort attempt at single query mode
    if [ -n "$CONTEXT" ] && [ -f "$CONTEXT" ]; then
        echo "📄 Including context from: $CONTEXT"
        echo "Query: $QUERY"
        echo ""
        echo "Context content:"
        cat "$CONTEXT"
        echo ""
        echo "Note: Codex CLI typically works in interactive mode."
        echo "You may need to copy the above context and query into the interactive session."
    else
        echo "Query: $QUERY"
        echo ""
        echo "Note: Codex CLI typically works in interactive mode."
        echo "Starting interactive mode - paste your query when prompted."
    fi

    # Start interactive mode since Codex doesn't have a simple command mode
    codex
else
    echo "🔄 Starting interactive session..."
    echo "💡 Tips:"
    echo "   - Use 'help' to see available commands"
    echo "   - Use 'exit' or Ctrl+C to quit"
    echo ""

    # Start interactive Codex
    codex
fi
