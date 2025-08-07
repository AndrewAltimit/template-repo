#!/bin/bash
# run_opencode.sh - Start OpenCode CLI for code generation

set -e

echo "🚀 Starting OpenCode CLI"

# Auto-load .env file if it exists and OPENROUTER_API_KEY is not set
if [ -z "$OPENROUTER_API_KEY" ] && [ -f ".env" ]; then
    echo "📄 Loading environment from .env file..."
    set -a  # Enable auto-export
    source .env
    set +a  # Disable auto-export
fi

# Check for API key
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not set. Please export your API key:"
    echo "   export OPENROUTER_API_KEY='your-key-here'"
    exit 1
fi

echo "✅ Using OpenRouter API key: ****${OPENROUTER_API_KEY: -4}"

# Default model if not set
if [ -z "$OPENCODE_MODEL" ]; then
    export OPENCODE_MODEL="qwen/qwen-2.5-coder-32b-instruct"
fi
echo "🤖 Using model: $OPENCODE_MODEL"

# Check if opencode CLI is available
if ! command -v opencode &> /dev/null; then
    echo "⚠️  opencode CLI not found. Installing from GitHub AI Agents package..."
    echo ""

    # Install the package
    if [ -d "./packages/github_ai_agents" ]; then
        pip3 install -e ./packages/github_ai_agents
    else
        echo "❌ GitHub AI Agents package not found at ./packages/github_ai_agents"
        echo "   Please run this script from the repository root."
        exit 1
    fi
fi

# Parse command line arguments
MODE="interactive"
QUERY=""
CONTEXT=""
PLAN_MODE=false

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
        -p|--plan)
            PLAN_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>    Single query mode with specified prompt"
            echo "  -c, --context <file>    Add context from file"
            echo "  -p, --plan              Enable plan mode for multi-step tasks"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Interactive Mode (default):"
            echo "  Start an interactive session with OpenCode"
            echo ""
            echo "Single Query Mode:"
            echo "  $0 -q 'Write a Python function to calculate fibonacci'"
            echo ""
            echo "With Context:"
            echo "  $0 -q 'Refactor this code' -c existing_code.py"
            echo ""
            echo "Plan Mode:"
            echo "  $0 -q 'Build a REST API with authentication' -p"
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

    # Build command
    CMD="opencode run"

    if [ -n "$QUERY" ]; then
        CMD="$CMD -q \"$QUERY\""
    fi

    if [ -n "$CONTEXT" ] && [ -f "$CONTEXT" ]; then
        echo "📄 Including context from: $CONTEXT"
        CONTEXT_CONTENT=$(cat "$CONTEXT")
        CMD="$CMD -c \"$CONTEXT_CONTENT\""
    fi

    if [ "$PLAN_MODE" = true ]; then
        CMD="$CMD --plan"
    fi

    # Execute
    eval "$CMD"
else
    echo "🔄 Starting interactive session..."
    echo "💡 Tips:"
    echo "   - Use 'clear' to clear conversation history"
    echo "   - Use 'status' to see current configuration"
    echo "   - Use 'exit' or Ctrl+C to quit"
    echo ""

    # Start interactive OpenCode (just call opencode without arguments for TUI)
    opencode
fi
