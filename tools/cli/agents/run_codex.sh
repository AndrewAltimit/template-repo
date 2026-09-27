#!/bin/bash
# run_codex.sh - Start Codex CLI for AI-powered code generation

# legacy: not allowed in this lab. Codex code is kept for reference only.
if [ "${ALLOW_LEGACY_AGENTS:-}" != "1" ]; then
    echo "ERROR: Codex is a legacy agent and is not allowed in this lab." >&2
    echo "Set ALLOW_LEGACY_AGENTS=1 to override." >&2
    exit 1
fi

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
    echo "   codex login"
    echo ""
    echo "Or run the container version with mounted auth:"
    echo "   ./tools/cli/containers/run_codex_container.sh"
    exit 1
fi

echo "✅ Codex CLI found and authenticated"

# Note: Security validation is handled by gh-validator binary at ~/.local/bin/gh
# via PATH shadowing. No explicit hook initialization needed.

# Parse command line arguments
MODE="interactive"
QUERY=""
CONTEXT=""
USE_EXEC=false
BYPASS_SANDBOX=false
AUTO_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--query)
            QUERY="$2"
            MODE="exec"
            USE_EXEC=true
            shift 2
            ;;
        -c|--context)
            CONTEXT="$2"
            shift 2
            ;;
        --auto)
            AUTO_MODE=true
            shift
            ;;
        --bypass-sandbox)
            BYPASS_SANDBOX=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>    Execute non-interactively with specified prompt"
            echo "  -c, --context <file>    Add context from file"
            echo "  --auto                  Auto-approve mode (uses --full-auto for safer execution)"
            echo "  --bypass-sandbox        Use --dangerously-bypass-approvals-and-sandbox (DANGEROUS!)"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Interactive Mode (default):"
            echo "  Start an interactive session with Codex"
            echo ""
            echo "Non-Interactive Execution Mode:"
            echo "  $0 -q 'Write a Python function to calculate fibonacci'"
            echo "  $0 -q 'Refactor this code' -c existing_code.py"
            echo ""
            echo "Safe Auto Mode (workspace-write sandbox):"
            echo "  $0 -q 'Build a web server' --auto"
            echo ""
            echo "Dangerous Mode (no sandbox - USE WITH CAUTION!):"
            echo "  $0 -q 'System task' --bypass-sandbox"
            echo ""
            echo "Note: Codex requires authentication via 'codex login' first."
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
if [ "$USE_EXEC" = true ] && [ -n "$QUERY" ]; then
    echo "📝 Running non-interactive execution..."

    # Build the prompt with context if provided
    FULL_PROMPT="$QUERY"
    if [ -n "$CONTEXT" ] && [ -f "$CONTEXT" ]; then
        echo "📄 Including context from: $CONTEXT"
        CONTEXT_CONTENT=$(cat "$CONTEXT")
        FULL_PROMPT="Context from $CONTEXT:
\`\`\`
$CONTEXT_CONTENT
\`\`\`

Task: $QUERY"
    fi

    # Determine execution mode
    if [ "$BYPASS_SANDBOX" = true ]; then
        # Ask for confirmation unless explicitly bypassed
        if [ "$AUTO_MODE" != true ]; then
            echo ""
            echo "⚠️  WARNING: --dangerously-bypass-approvals-and-sandbox mode"
            echo "This will execute commands WITHOUT ANY SANDBOXING or approval!"
            echo "Only use this in already-sandboxed environments."
            echo ""
            read -r -p "Are you ABSOLUTELY SURE you want to continue? (yes/no): " confirm
            if [ "$confirm" != "yes" ]; then
                echo "❌ Aborted for safety."
                exit 1
            fi
        fi

        echo "⚡ Executing with --dangerously-bypass-approvals-and-sandbox..."
        echo ""
        echo "$FULL_PROMPT" | codex exec --dangerously-bypass-approvals-and-sandbox -

    elif [ "$AUTO_MODE" = true ]; then
        echo "🔐 Executing with --full-auto (sandboxed workspace-write)..."
        echo ""
        echo "$FULL_PROMPT" | codex exec --full-auto -

    else
        # Default: interactive approval mode with workspace-write sandbox
        echo "🔒 Executing with workspace-write sandbox (approval required)..."
        echo ""
        echo "$FULL_PROMPT" | codex exec --sandbox workspace-write -
    fi

elif [ "$MODE" = "interactive" ]; then
    # Only show note if no arguments provided
    if [ $# -eq 0 ]; then
        echo "🤖 Codex Configuration"
        echo ""
        echo "ℹ️  Note: Codex is an AI-powered code generation tool by OpenAI."
        echo "It can help with code completion, generation, and refactoring."
        echo ""

        # Ask about sandbox preference for interactive mode
        echo "Choose sandbox mode for this session:"
        echo "1) Standard (with approvals and sandbox)"
        echo "2) Auto mode (--full-auto: workspace-write sandbox, no approvals)"
        echo "3) Dangerous (--dangerously-bypass-approvals-and-sandbox)"
        echo ""
        read -r -p "Enter choice (1-3) [default: 1]: " choice

        case "$choice" in
            2)
                echo "🔐 Starting with --full-auto mode..."
                codex --full-auto
                ;;
            3)
                echo ""
                echo "⚠️  WARNING: This disables ALL safety features!"
                read -r -p "Are you sure? (yes/no): " confirm
                if [ "$confirm" = "yes" ]; then
                    echo "⚡ Starting with --dangerously-bypass-approvals-and-sandbox..."
                    codex --dangerously-bypass-approvals-and-sandbox
                else
                    echo "✅ Starting standard interactive mode..."
                    codex
                fi
                ;;
            *)
                echo "✅ Starting standard interactive mode..."
                codex
                ;;
        esac
    else
        # Arguments were provided but no query - apply flags to interactive mode
        echo "🔄 Starting interactive session with provided flags..."
        echo "💡 Tips:"
        echo "   - Use 'help' to see available commands"
        echo "   - Use 'exit' or Ctrl+C to quit"
        echo ""

        # Build command with any flags that were provided
        CODEX_CMD="codex"
        if [ "$AUTO_MODE" = true ]; then
            echo "   - Running with --full-auto mode"
            CODEX_CMD="$CODEX_CMD --full-auto"
        fi
        if [ "$BYPASS_SANDBOX" = true ]; then
            echo "   - ⚠️  Running with --dangerously-bypass-approvals-and-sandbox"
            CODEX_CMD="$CODEX_CMD --dangerously-bypass-approvals-and-sandbox"
        fi
        echo ""

        # Execute with the built command
        $CODEX_CMD
    fi
else
    echo "❌ Error: Query is required for exec mode"
    echo "Use -h or --help for usage information"
    exit 1
fi
