#!/bin/bash
# run_crush.sh - Start Crush CLI for fast code generation

set -e

echo "⚡ Starting Crush CLI (Fast Code Generation)"

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

# Security hooks are now automatically loaded via /etc/bash.bashrc
# No need to source them manually anymore

# Check if crush CLI is available
if ! command -v crush &> /dev/null; then
    echo "⚠️  crush CLI not found. Installing..."
    echo ""

    # Install crush from Charm Bracelet
    if command -v go &> /dev/null; then
        echo "📦 Installing crush via go..."
        go install github.com/charmbracelet/crush@latest
    elif command -v brew &> /dev/null; then
        echo "📦 Installing crush via brew..."
        brew install charmbracelet/tap/crush
    else
        echo "❌ Neither go nor brew found. Please install crush manually:"
        echo "   https://github.com/charmbracelet/crush"
        exit 1
    fi
fi

# Ask about unattended mode for interactive sessions
UNATTENDED_FLAG=""
if [ $# -eq 0 ]; then
    # Only ask if no arguments provided (interactive mode)
    echo "🤖 Crush Configuration"
    echo ""
    echo "Would you like to run Crush in unattended mode?"
    echo "This will allow Crush to execute commands without asking for approval."
    echo ""
    read -p "Use unattended mode? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        UNATTENDED_FLAG="-y"
        echo "⚡ Will run Crush in UNATTENDED mode (--yolo)..."
        echo "⚠️  Crush will execute commands without asking for approval!"
        echo ""
    else
        echo "🔒 Will run Crush in NORMAL mode (with approval prompts)..."
        echo ""
    fi
fi

# Parse command line arguments
MODE="interactive"
QUERY=""
STYLE="concise"
CONVERT_TO=""
CODE_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--query)
            QUERY="$2"
            MODE="single"
            shift 2
            ;;
        -s|--style)
            STYLE="$2"
            shift 2
            ;;
        -e|--explain)
            MODE="explain"
            CODE_FILE="$2"
            shift 2
            ;;
        -c|--convert)
            MODE="convert"
            CODE_FILE="$2"
            shift 2
            ;;
        -t|--to)
            CONVERT_TO="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -q, --query <prompt>     Single query mode with specified prompt"
            echo "  -s, --style <style>      Output style: concise, detailed, explained (default: concise)"
            echo "  -e, --explain <file>     Explain code from file"
            echo "  -c, --convert <file>     Convert code from file"
            echo "  -t, --to <language>      Target language for conversion"
            echo "  -h, --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  Interactive mode (default):"
            echo "    $0"
            echo ""
            echo "  Quick generation:"
            echo "    $0 -q 'Write a Python web scraper'"
            echo ""
            echo "  Detailed generation:"
            echo "    $0 -q 'Create a REST API' -s detailed"
            echo ""
            echo "  Explain code:"
            echo "    $0 -e complex_algorithm.py"
            echo ""
            echo "  Convert code:"
            echo "    $0 -c script.py -t javascript"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Configure Crush to use OpenRouter
export OPENAI_API_KEY="$OPENROUTER_API_KEY"
export OPENAI_API_BASE="https://openrouter.ai/api/v1"

# Execute based on mode
case $MODE in
    single)
        if [ -z "$QUERY" ]; then
            echo "❌ Query required for single mode"
            exit 1
        fi

        echo "🚀 Generating code (style: $STYLE)..."
        echo ""

        # Add style prefix to query based on preference
        case $STYLE in
            detailed)
                FULL_QUERY="Generate complete, production-ready code with error handling: $QUERY"
                ;;
            explained)
                FULL_QUERY="Generate code with detailed inline comments explaining each part: $QUERY"
                ;;
            *)
                FULL_QUERY="$QUERY"
                ;;
        esac

        # Run crush with the query (UNATTENDED_FLAG will be omitted if empty)
        # shellcheck disable=SC2086
        crush run $UNATTENDED_FLAG -q "$FULL_QUERY"
        ;;

    explain)
        if [ ! -f "$CODE_FILE" ]; then
            echo "❌ File not found: $CODE_FILE"
            exit 1
        fi

        echo "📖 Explaining code from: $CODE_FILE"
        echo ""

        CODE_CONTENT=$(cat "$CODE_FILE")
        # shellcheck disable=SC2086
        crush run $UNATTENDED_FLAG -q "Explain this code in detail:\n\n$CODE_CONTENT"
        ;;

    convert)
        if [ ! -f "$CODE_FILE" ]; then
            echo "❌ File not found: $CODE_FILE"
            exit 1
        fi

        if [ -z "$CONVERT_TO" ]; then
            echo "❌ Target language required for conversion (use -t option)"
            exit 1
        fi

        echo "🔄 Converting code from: $CODE_FILE"
        echo "   Target language: $CONVERT_TO"
        echo ""

        CODE_CONTENT=$(cat "$CODE_FILE")
        # shellcheck disable=SC2086
        crush run $UNATTENDED_FLAG -q "Convert this code to $CONVERT_TO, preserving all functionality:\n\n$CODE_CONTENT"
        ;;

    interactive)
        echo "🔄 Starting interactive session..."
        echo "💡 Tips:"
        echo "   - Crush is optimized for fast, concise responses"
        echo "   - Use clear, specific prompts for best results"
        echo "   - Type 'exit' or use Ctrl+C to quit"
        echo ""

        # Start interactive Crush session (UNATTENDED_FLAG will be omitted if empty)
        # shellcheck disable=SC2086
        crush $UNATTENDED_FLAG
        ;;
esac
