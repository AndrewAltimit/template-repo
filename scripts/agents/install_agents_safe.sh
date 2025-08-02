#!/bin/bash
# Safe installation guide for multi-agent CLI tools
# This script provides instructions rather than automatic installation

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Multi-Agent CLI Tools Installation Guide ===${NC}"
echo
echo -e "${YELLOW}This guide provides safe installation instructions for each agent.${NC}"
echo -e "${YELLOW}Follow the steps manually to maintain security.${NC}"
echo

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to show installation status
check_agent() {
    local name=$1
    local cmd=$2
    if command_exists "$cmd"; then
        echo -e "${GREEN}✓ $name is already installed${NC}"
    else
        echo -e "${RED}✗ $name is not installed${NC}"
    fi
}

# Show current status
echo -e "${BLUE}Current Installation Status:${NC}"
check_agent "Claude Code" "claude"
check_agent "Gemini CLI" "gemini"
check_agent "Node.js" "node"
check_agent "Go" "go"
check_agent "Crush/Mods" "mods"
echo

# Installation instructions
echo -e "${BLUE}=== Installation Instructions ===${NC}"
echo

echo -e "${YELLOW}1. Claude Code (Host-only - requires subscription auth)${NC}"
echo "   Visit: https://claude.ai/code"
echo "   Follow the official installation instructions for your OS"
echo "   After installation, run: claude"
echo

echo -e "${YELLOW}2. Gemini CLI (Host-only - requires Docker access)${NC}"
echo "   Prerequisites: Node.js 18+"
echo "   Install: npm install -g @google/gemini-cli"
echo "   After installation, run: gemini"
echo

echo -e "${YELLOW}3. OpenRouter Agents (Can be containerized)${NC}"
echo "   These agents can run in Docker containers or on the host."
echo "   For containerized installation, use:"
echo "   docker-compose --profile openrouter up -d"
echo
echo "   For host installation:"
echo

echo -e "${BLUE}   a) Install Node.js (if not present):${NC}"
echo "      # Using Node Version Manager (recommended):"
echo "      curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh > nvm-install.sh"
echo "      # Review the script, then run:"
echo "      bash nvm-install.sh"
echo "      nvm install 20"
echo "      nvm use 20"
echo

echo -e "${BLUE}   b) Install Go (if not present):${NC}"
echo "      # Download from https://go.dev/dl/"
echo "      wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz"
echo "      sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz"
echo "      # Add to ~/.bashrc:"
echo "      export PATH=\$PATH:/usr/local/go/bin:\$HOME/go/bin"
echo

echo -e "${BLUE}   c) Install OpenRouter CLI tools:${NC}"
echo "      # OpenCode (when available):"
echo "      # Check official docs at https://opencode.ai"
echo
echo "      # Codex CLI (when available):"
echo "      # npm install -g @openai/codex-cli"
echo
echo "      # Crush/Mods from Charm Bracelet:"
echo "      go install github.com/charmbracelet/mods@latest"
echo

echo -e "${BLUE}=== Configuration ===${NC}"
echo

echo -e "${YELLOW}1. Environment Variables:${NC}"
echo "   Add to your ~/.bashrc or ~/.zshrc:"
echo "   export OPENROUTER_API_KEY='your-key-here'"
echo "   export OPENAI_API_KEY='your-key-here'  # For Codex"
echo

echo -e "${YELLOW}2. Agent Configuration:${NC}"
echo "   The multi-agent system uses .agents.yaml for configuration"
echo "   See .agents.yaml.example for reference"
echo

echo -e "${YELLOW}3. Container Usage (Recommended):${NC}"
echo "   # Build the OpenRouter agents container:"
echo "   docker-compose build openrouter-agents"
echo
echo "   # Run agents in container:"
echo "   docker-compose run --rm openrouter-agents python scripts/agents/run_agents.py"
echo

echo -e "${BLUE}=== Testing ===${NC}"
echo "   # Test the multi-agent system:"
echo "   python scripts/agents/test_agent_system.py"
echo
echo "   # Analyze OpenRouter agents containerization feasibility:"
echo "   python scripts/agents/analyze_containerization_feasibility.py"
echo

echo -e "${GREEN}=== Done ===${NC}"
echo "Follow the instructions above to install agents safely."
echo "For production use, prefer containerized deployments when possible."
