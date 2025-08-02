#!/bin/bash
# Script to run containerized OpenRouter agents

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Containerized OpenRouter Agents Runner ===${NC}"
echo

# Check if OPENROUTER_API_KEY is set
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo -e "${RED}Error: OPENROUTER_API_KEY is not set${NC}"
    echo "Please add to your .env file:"
    echo "OPENROUTER_API_KEY=your-api-key"
    exit 1
fi

# Function to show usage
usage() {
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  test          - Test all containerized agents"
    echo "  opencode      - Run OpenCode agent with a prompt"
    echo "  codex         - Run Codex agent with a prompt"
    echo "  crush         - Run Crush agent with a prompt"
    echo "  mods          - Run mods directly (underlying tool)"
    echo "  issue-monitor - Run issue monitor with multi-agent support"
    echo "  pr-monitor    - Run PR review monitor with multi-agent support"
    echo "  shell         - Open interactive shell in container"
    echo
    echo "Examples:"
    echo "  $0 test"
    echo "  $0 opencode \"Write a hello world function\""
    echo "  $0 crush \"Explain Docker networking\""
    echo "  $0 issue-monitor"
    exit 1
}

# Check command
if [ $# -eq 0 ]; then
    usage
fi

COMMAND=$1
shift

# Build the container if needed
echo -e "${YELLOW}Building openrouter-agents container...${NC}"
docker-compose build openrouter-agents

case $COMMAND in
    test)
        echo -e "${GREEN}Testing containerized agents...${NC}"
        docker-compose run --rm openrouter-agents python scripts/agents/test_containerized_agents.py
        ;;

    opencode|codex|crush)
        if [ $# -eq 0 ]; then
            echo -e "${RED}Error: Please provide a prompt${NC}"
            echo "Usage: $0 $COMMAND \"your prompt here\""
            exit 1
        fi
        PROMPT="$*"
        echo -e "${GREEN}Running $COMMAND with prompt: $PROMPT${NC}"
        docker-compose run --rm openrouter-agents "$COMMAND" "$PROMPT"
        ;;

    mods)
        if [ $# -eq 0 ]; then
            echo -e "${RED}Error: Please provide a prompt${NC}"
            echo "Usage: $0 mods \"your prompt here\""
            exit 1
        fi
        PROMPT="$*"
        echo -e "${GREEN}Running mods directly: $PROMPT${NC}"
        docker-compose run --rm openrouter-agents mods "$PROMPT" --model "openrouter/qwen/qwen-2.5-coder-32b-instruct" --api https://openrouter.ai/api/v1
        ;;

    issue-monitor)
        echo -e "${GREEN}Running issue monitor with containerized agents...${NC}"
        docker-compose run --rm openrouter-agents python scripts/agents/issue_monitor_multi_agent.py "$@"
        ;;

    pr-monitor)
        echo -e "${GREEN}Running PR review monitor with containerized agents...${NC}"
        docker-compose run --rm openrouter-agents python scripts/agents/pr_review_monitor_multi_agent.py "$@"
        ;;

    shell)
        echo -e "${GREEN}Opening shell in container...${NC}"
        docker-compose run --rm openrouter-agents /bin/bash
        ;;

    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        usage
        ;;
esac
