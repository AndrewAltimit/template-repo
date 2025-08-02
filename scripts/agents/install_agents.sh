#!/bin/bash
# Install script for multi-agent CLI tools

set -e

echo "=== Multi-Agent CLI Tools Installation ==="
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Node.js if not present (needed for several tools)
install_nodejs() {
    if ! command_exists node; then
        echo -e "${YELLOW}Node.js not found. Installing via NodeSource...${NC}"
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt-get install -y nodejs
    else
        echo -e "${GREEN}✓ Node.js already installed${NC}"
    fi
}

# Install Go if not present (needed for Crush)
install_go() {
    if ! command_exists go; then
        echo -e "${YELLOW}Go not found. Installing Go 1.21...${NC}"
        wget -q https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
        rm go1.21.0.linux-amd64.tar.gz

        # Add to PATH
        echo "export PATH=\$PATH:/usr/local/go/bin" >> ~/.bashrc
        echo "export PATH=\$PATH:\$HOME/go/bin" >> ~/.bashrc
        export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
    else
        echo -e "${GREEN}✓ Go already installed${NC}"
    fi
}

# Claude Code
install_claude() {
    echo -e "\n${YELLOW}=== Installing Claude Code ===${NC}"
    if command_exists claude; then
        echo -e "${GREEN}✓ Claude Code already installed${NC}"
    else
        echo "Claude Code requires manual installation:"
        echo "1. Visit https://claude.ai/code"
        echo "2. Follow the installation instructions for your OS"
        echo "3. Run 'claude' to authenticate"
        echo -e "${YELLOW}Press Enter to continue...${NC}"
        read -r
    fi
}

# Gemini CLI
install_gemini() {
    echo -e "\n${YELLOW}=== Installing Gemini CLI ===${NC}"
    if command_exists gemini; then
        echo -e "${GREEN}✓ Gemini CLI already installed${NC}"
    else
        echo "Installing Gemini CLI..."
        npm install -g @google/gemini-cli
        echo -e "${GREEN}✓ Gemini CLI installed${NC}"
        echo "Run 'gemini' to authenticate"
    fi
}

# OpenCode
install_opencode() {
    echo -e "\n${YELLOW}=== Installing OpenCode ===${NC}"
    if command_exists opencode; then
        echo -e "${GREEN}✓ OpenCode already installed${NC}"
    else
        echo "Installing OpenCode..."
        curl -fsSL https://opencode.ai/install | bash
        echo -e "${GREEN}✓ OpenCode installed${NC}"
        echo "Run 'opencode auth login' to authenticate"
    fi
}

# Codex CLI
install_codex() {
    echo -e "\n${YELLOW}=== Installing Codex CLI ===${NC}"
    if command_exists codex; then
        echo -e "${GREEN}✓ Codex CLI already installed${NC}"
    else
        echo "Installing Codex CLI..."
        npm install -g @openai/codex
        echo -e "${GREEN}✓ Codex CLI installed${NC}"
        echo "Set OPENAI_API_KEY environment variable for authentication"
    fi
}

# Crush
install_crush() {
    echo -e "\n${YELLOW}=== Installing Crush ===${NC}"
    if command_exists crush; then
        echo -e "${GREEN}✓ Crush already installed${NC}"
    else
        echo "Installing Crush..."
        go install github.com/charmbracelet/crush@latest
        echo -e "${GREEN}✓ Crush installed${NC}"
        echo "Configure API keys in ~/.config/crush/crush.json"
    fi
}

# Check for required tools
check_requirements() {
    echo "Checking requirements..."

    # Check for curl
    if ! command_exists curl; then
        echo -e "${RED}Error: curl is required but not installed${NC}"
        echo "Install with: sudo apt-get install curl"
        exit 1
    fi

    # Check for git
    if ! command_exists git; then
        echo -e "${RED}Error: git is required but not installed${NC}"
        echo "Install with: sudo apt-get install git"
        exit 1
    fi
}

# Main installation flow
main() {
    check_requirements

    # Parse arguments
    if [ $# -eq 0 ]; then
        # Install all agents
        AGENTS="all"
    else
        AGENTS="$*"
    fi

    # Install prerequisites
    if [[ "$AGENTS" == "all" ]] || [[ "$AGENTS" == *"opencode"* ]] || [[ "$AGENTS" == *"codex"* ]] || [[ "$AGENTS" == *"gemini"* ]]; then
        install_nodejs
    fi

    if [[ "$AGENTS" == "all" ]] || [[ "$AGENTS" == *"crush"* ]]; then
        install_go
    fi

    # Install agents
    if [[ "$AGENTS" == "all" ]]; then
        install_claude
        install_gemini
        install_opencode
        install_codex
        install_crush
    else
        for agent in $AGENTS; do
            case "$agent" in
                claude)
                    install_claude
                    ;;
                gemini)
                    install_gemini
                    ;;
                opencode)
                    install_opencode
                    ;;
                codex)
                    install_codex
                    ;;
                crush)
                    install_crush
                    ;;
                *)
                    echo -e "${RED}Unknown agent: $agent${NC}"
                    echo "Valid agents: claude, gemini, opencode, codex, crush"
                    ;;
            esac
        done
    fi

    echo -e "\n${GREEN}=== Installation Complete ===${NC}"
    echo
    echo "Next steps:"
    echo "1. Set up API keys:"
    echo "   export OPENROUTER_API_KEY='your-key'"
    echo "   export OPENAI_API_KEY='your-key' (for Codex)"
    echo
    echo "2. Authenticate agents:"
    echo "   claude (interactive)"
    echo "   gemini (interactive)"
    echo "   opencode auth login"
    echo
    echo "3. Test the multi-agent system:"
    echo "   python scripts/agents/test_agent_system.py"
}

# Show usage
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Usage: $0 [agent1] [agent2] ..."
    echo
    echo "Install AI agent CLI tools for the multi-agent system."
    echo
    echo "Agents:"
    echo "  claude     - Claude Code (Anthropic)"
    echo "  gemini     - Gemini CLI (Google)"
    echo "  opencode   - OpenCode (SST)"
    echo "  codex      - Codex CLI (OpenAI)"
    echo "  crush      - Crush (Charm Bracelet)"
    echo
    echo "Examples:"
    echo "  $0                    # Install all agents"
    echo "  $0 claude gemini      # Install only Claude and Gemini"
    echo "  $0 opencode           # Install only OpenCode"
    exit 0
fi

main "$@"
