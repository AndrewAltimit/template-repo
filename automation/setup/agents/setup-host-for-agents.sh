#!/bin/bash
# Setup script for preparing host machine to run AI agents
# This is required because AI agents now run on host (not in containers)
# due to Claude CLI subscription authentication limitations

set -e

echo "=== AI Agent Host Setup Script ==="
echo "This script prepares your host machine to run AI agents"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "[WARNING] Please don't run this script as root/sudo"
   echo "The script uses pip3 --user to install packages in your user directory"
   exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python 3
echo "[INFO] Checking Python 3..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "[OK] Found: $PYTHON_VERSION"
else
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3.8 or later"
    exit 1
fi

# Check pip3
echo ""
echo "[INFO] Checking pip3..."
if command_exists pip3; then
    PIP_VERSION=$(pip3 --version 2>&1)
    echo "[OK] Found: $PIP_VERSION"
else
    echo "[ERROR] pip3 is not installed"
    echo "Please install python3-pip"
    exit 1
fi

# Check nvm and Node.js
echo ""
echo "[INFO] Checking nvm and Node.js..."
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # Load nvm
    export NVM_DIR="$HOME/.nvm"
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"

    if command_exists nvm; then
        echo "[OK] Found nvm"

        # Check for Node.js version from .nvmrc
        if [ -f "$PROJECT_ROOT/.nvmrc" ]; then
            REQUIRED_NODE_VERSION=$(cat "$PROJECT_ROOT/.nvmrc")
            if nvm use "$REQUIRED_NODE_VERSION" >/dev/null 2>&1; then
                echo "[OK] Node.js $REQUIRED_NODE_VERSION is available"
                NODE_VERSION=$(node --version)
                echo "[OK] Using Node.js: $NODE_VERSION"
            else
                echo "[WARNING] Node.js $REQUIRED_NODE_VERSION not found"
                echo "Install it with: nvm install $REQUIRED_NODE_VERSION"
            fi
        else
            echo "[WARNING] .nvmrc file not found in project root"
        fi
    fi
else
    echo "[WARNING] nvm not found at ~/.nvm/nvm.sh"
    if [ -f "$PROJECT_ROOT/.nvmrc" ]; then
        echo "Claude CLI requires Node.js $(cat "$PROJECT_ROOT/.nvmrc") via nvm"
    else
        echo "Claude CLI requires Node.js via nvm (see .nvmrc for version)"
    fi
fi

# Check Claude CLI
echo ""
echo "[INFO] Checking Claude CLI..."
# Make sure we're using the right Node.js version
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    # shellcheck disable=SC1091
    . "$HOME/.nvm/nvm.sh"
    if [ -f "$PROJECT_ROOT/.nvmrc" ]; then
        nvm use "$(cat "$PROJECT_ROOT/.nvmrc")" >/dev/null 2>&1
    fi
fi

if command_exists claude; then
    CLAUDE_VERSION=$(claude --version 2>&1 || echo "version check failed")
    echo "[OK] Found Claude CLI: $CLAUDE_VERSION"

    # Check if Claude is authenticated
    echo "[INFO] Checking Claude authentication..."
    if [ -f "$HOME/.claude.json" ]; then
        echo "[OK] Found Claude credentials at ~/.claude.json"
    elif [ -d "$HOME/.claude" ]; then
        echo "[OK] Found Claude credentials directory at ~/.claude/"
    else
        echo "[WARNING] No Claude credentials found"
        echo "You need to run 'claude login' to authenticate"
    fi
else
    echo "[ERROR] Claude CLI is not installed"
    echo ""
    echo "To install Claude CLI:"
    echo "1. Install Node.js and npm if not already installed"
    echo "2. Run: npm install -g @anthropic-ai/claude-code"
    echo "3. Run: claude login"
    echo ""
    echo "See: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

# Check GitHub CLI
echo ""
echo "[INFO] Checking GitHub CLI..."
if command_exists gh; then
    GH_VERSION=$(gh --version 2>&1 | head -n1)
    echo "[OK] Found: $GH_VERSION"

    # Check if authenticated
    if gh auth status >/dev/null 2>&1; then
        echo "[OK] GitHub CLI is authenticated"
    else
        echo "[WARNING] GitHub CLI is not authenticated"
        echo "Run 'gh auth login' to authenticate"
    fi
else
    echo "[WARNING] GitHub CLI (gh) is not installed"
    echo "The AI agents require GitHub CLI to create PRs and manage issues"
    echo "Install from: https://cli.github.com/"
fi

# Check Git
echo ""
echo "[INFO] Checking Git..."
if command_exists git; then
    GIT_VERSION=$(git --version)
    echo "[OK] Found: $GIT_VERSION"
else
    echo "[ERROR] Git is not installed"
    exit 1
fi

# Install Python dependencies
echo ""
echo "[INFO] Installing Python dependencies..."
echo "Using pip3 install --user to avoid permission issues"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if requirements file exists
REQUIREMENTS_FILE="$PROJECT_ROOT/docker/requirements/requirements-agents.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "[INFO] Installing from: $REQUIREMENTS_FILE"
    pip3 install --user -r "$REQUIREMENTS_FILE" || {
        echo "[WARNING] Some packages failed to install"
        echo "You may need to install system dependencies"
    }
else
    echo "[ERROR] Requirements file not found: $REQUIREMENTS_FILE"
    echo "Are you running this script from the project directory?"
    exit 1
fi

# Add user's pip bin directory to PATH if not already there
USER_BIN="$HOME/.local/bin"
if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
    echo ""
    echo "[INFO] Adding $USER_BIN to PATH"
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# Summary
echo ""
echo "=== Setup Summary ==="
echo ""
echo "✓ Python 3: Installed"
if command_exists pip3; then
    echo "✓ pip3: Installed"
fi
if command_exists claude; then
    echo "✓ Claude CLI: Installed"
    if [ -f "$HOME/.claude.json" ] || [ -d "$HOME/.claude" ]; then
        echo "✓ Claude Authentication: Found"
    else
        echo "✗ Claude Authentication: Missing - run 'claude login'"
    fi
else
    echo "✗ Claude CLI: Not installed"
fi
if command_exists gh; then
    echo "✓ GitHub CLI: Installed"
    if gh auth status >/dev/null 2>&1; then
        echo "✓ GitHub Authentication: OK"
    else
        echo "✗ GitHub Authentication: Missing - run 'gh auth login'"
    fi
else
    echo "✗ GitHub CLI: Not installed"
fi
echo "✓ Python dependencies: Installed with --user"

echo ""
echo "=== Next Steps ==="
echo ""
echo "1. If nvm is not installed:"
echo "   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
echo ""
echo "2. If Node.js is not installed (check .nvmrc for required version):"
echo "   nvm install"
echo "   nvm use"
echo ""
echo "3. If Claude CLI is not installed:"
echo "   nvm use"
echo "   npm install -g @anthropic-ai/claude-code"
echo ""
echo "4. If Claude is not authenticated:"
echo "   nvm use"
echo "   claude login"
echo ""
echo "5. If GitHub CLI is not authenticated:"
echo "   gh auth login"
echo ""
echo "6. Install the AI agents package:"
echo "   pip3 install -e ./packages/github_ai_agents"
echo ""
echo "7. Test the AI agents:"
echo "   python3 -m github_ai_agents.cli --help"
echo ""
echo "Done!"
