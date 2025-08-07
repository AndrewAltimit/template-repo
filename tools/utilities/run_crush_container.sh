#!/bin/bash
# run_crush_container.sh - Run Crush CLI in Docker container

set -e

echo "🐳 Starting Crush CLI in Container (Fast Code Generation)"

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
            echo "  Interactive mode in container (default):"
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

# Build Docker command
DOCKER_CMD="docker-compose run --rm"
DOCKER_CMD="$DOCKER_CMD -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY"
DOCKER_CMD="$DOCKER_CMD -e OPENAI_API_KEY=$OPENROUTER_API_KEY"
DOCKER_CMD="$DOCKER_CMD -e OPENAI_API_BASE=https://openrouter.ai/api/v1"

# Mount code file if provided
if [ -n "$CODE_FILE" ] && [ -f "$CODE_FILE" ]; then
    CODE_DIR=$(dirname "$(realpath "$CODE_FILE")")
    CODE_FILENAME=$(basename "$CODE_FILE")
    DOCKER_CMD="$DOCKER_CMD -v $CODE_DIR:/workspace"
    CODE_PATH="/workspace/$CODE_FILENAME"
else
    CODE_PATH=""
fi

# Execute based on mode
case $MODE in
    single)
        if [ -z "$QUERY" ]; then
            echo "❌ Query required for single mode"
            exit 1
        fi

        echo "🚀 Generating code in container (style: $STYLE)..."
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

        # Run in container
        $DOCKER_CMD openrouter-agents crush run -q "$FULL_QUERY"
        ;;

    explain)
        if [ ! -f "$CODE_FILE" ]; then
            echo "❌ File not found: $CODE_FILE"
            exit 1
        fi

        echo "📖 Explaining code from: $CODE_FILE"
        echo ""

        # Read file content and run in container
        $DOCKER_CMD openrouter-agents sh -c "cat '$CODE_PATH' | xargs -0 -I {} crush run -q 'Explain this code in detail:\n\n{}'"
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

        # Read file content and run in container
        $DOCKER_CMD openrouter-agents sh -c "cat '$CODE_PATH' | xargs -0 -I {} crush run -q 'Convert this code to $CONVERT_TO, preserving all functionality:\n\n{}'"
        ;;

    interactive)
        echo "🔄 Starting interactive session in container..."
        echo "💡 Tips:"
        echo "   - Crush is optimized for fast, concise responses"
        echo "   - Use clear, specific prompts for best results"
        echo "   - Type 'exit' or use Ctrl+C to quit"
        echo ""

        # Start interactive session in container
        $DOCKER_CMD -it openrouter-agents crush
        ;;
esac
