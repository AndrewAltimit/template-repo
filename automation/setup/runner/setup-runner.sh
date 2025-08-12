#!/bin/bash
#
# Setup script for GitHub Actions self-hosted runner
#

set -e

echo "🚀 GitHub Actions Self-Hosted Runner Setup (Simple)"
echo "=================================================="
echo ""
echo "Note: For a complete setup including system dependencies,"
echo "      Docker, and MCP configuration, use setup-runner-full.sh"
echo ""

# Configuration
RUNNER_VERSION="2.311.0"
RUNNER_OS=$(uname -s | tr '[:upper:]' '[:lower:]')
RUNNER_ARCH="x64"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root!"
   echo "Please run as a regular user with sudo access."
   exit 1
fi

# Function to check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."

    # Check for required commands
    local required_commands=("curl" "tar" "git" "sudo")
    for cmd in "${required_commands[@]}"; do
        if ! command -v $cmd &> /dev/null; then
            echo "❌ Missing required command: $cmd"
            echo "Please install it and try again."
            exit 1
        fi
    done

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "⚠️  Docker is not installed. Would you like to install it? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            install_docker
        else
            echo "⚠️  Continuing without Docker. Some features may not work."
        fi
    else
        echo "✅ Docker is installed"
    fi

    echo "✅ All prerequisites checked"
}

# Function to install Docker
install_docker() {
    echo "📦 Installing Docker..."

    # Install Docker
    curl -fsSL https://get.docker.com | sudo sh

    # Add current user to docker group
    sudo usermod -aG docker $USER

    echo "✅ Docker installed"
    echo "⚠️  You need to log out and back in for group changes to take effect"
}

# Function to create runner directory
create_runner_directory() {
    RUNNER_DIR="$HOME/actions-runner"

    if [ -d "$RUNNER_DIR" ]; then
        echo "⚠️  Runner directory already exists at $RUNNER_DIR"
        echo "Would you like to remove it and start fresh? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -rf "$RUNNER_DIR"
        else
            echo "Using existing directory..."
        fi
    fi

    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"
    echo "✅ Created runner directory at $RUNNER_DIR"
}

# Function to download runner
download_runner() {
    echo "📥 Downloading GitHub Actions runner v${RUNNER_VERSION}..."

    # Determine download URL based on OS and architecture
    local download_url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

    # Download and extract
    curl -O -L "$download_url"
    tar xzf "./actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
    rm "./actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

    echo "✅ Runner downloaded and extracted"
}

# Function to get runner token
get_runner_token() {
    echo ""
    echo "🔑 Runner Registration"
    echo "====================="
    echo ""
    echo "To register this runner, you need a registration token from GitHub."
    echo ""
    echo "For a repository runner:"
    echo "1. Go to: https://github.com/OWNER/REPO/settings/actions/runners/new"
    echo "2. Copy the registration token"
    echo ""
    echo "For an organization runner:"
    echo "1. Go to: https://github.com/organizations/ORG/settings/actions/runners/new"
    echo "2. Copy the registration token"
    echo ""
    echo "Enter your registration token:"
    read -s RUNNER_TOKEN
    echo ""

    if [ -z "$RUNNER_TOKEN" ]; then
        echo "❌ No token provided. Exiting."
        exit 1
    fi
}

# Function to configure runner
configure_runner() {
    echo "⚙️  Configuring runner..."

    # Get repository or organization URL
    echo "Enter the repository or organization URL:"
    echo "Example: https://github.com/owner/repo or https://github.com/org"
    read -r REPO_URL

    # Get runner name
    echo "Enter a name for this runner (default: $(hostname)):"
    read -r RUNNER_NAME
    RUNNER_NAME=${RUNNER_NAME:-$(hostname)}

    # Get runner labels
    echo "Enter additional labels for this runner (comma-separated, default: self-hosted,linux):"
    read -r RUNNER_LABELS
    RUNNER_LABELS=${RUNNER_LABELS:-"self-hosted,linux"}

    # Configure the runner
    ./config.sh \
        --url "$REPO_URL" \
        --token "$RUNNER_TOKEN" \
        --name "$RUNNER_NAME" \
        --labels "$RUNNER_LABELS" \
        --unattended \
        --replace

    echo "✅ Runner configured successfully"
}

# Function to install as service
install_service() {
    echo ""
    echo "🔧 Service Installation"
    echo "Would you like to install the runner as a systemd service? (y/n)"
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Installing runner service..."
        sudo ./svc.sh install
        sudo ./svc.sh start

        echo "✅ Runner installed as service"
        echo ""
        echo "Service commands:"
        echo "  Start:   sudo ./svc.sh start"
        echo "  Stop:    sudo ./svc.sh stop"
        echo "  Status:  sudo ./svc.sh status"
        echo "  Logs:    sudo journalctl -u actions.runner.* -f"
    else
        echo ""
        echo "To run the runner manually:"
        echo "  cd $RUNNER_DIR"
        echo "  ./run.sh"
    fi
}

# Function to setup MCP environment (simplified)
setup_mcp_environment() {
    echo ""
    echo "🤖 Setting up MCP environment..."

    # Create MCP directories
    mkdir -p "$HOME/.mcp/configs"

    # Copy configurations if available
    if [ -f "../.mcp.json" ]; then
        cp ../.mcp.json "$HOME/.mcp/configs/"
        echo "✅ Copied MCP configuration"
    elif [ -f ".mcp.json" ]; then
        cp .mcp.json "$HOME/.mcp/configs/"
        echo "✅ Copied MCP configuration"
    fi

    echo "✅ MCP environment setup complete"
}

# Main setup flow
main() {
    echo ""
    check_prerequisites
    echo ""
    create_runner_directory
    echo ""
    download_runner
    echo ""
    get_runner_token
    echo ""
    configure_runner
    echo ""
    install_service
    echo ""
    setup_mcp_environment
    echo ""

    echo "🎉 Setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. If you installed Docker, log out and back in"
    echo "2. Test the runner with a simple workflow"
    echo ""
    echo "Useful paths:"
    echo "  Runner directory: $RUNNER_DIR"
    echo "  MCP config: $HOME/.mcp/"
}

# Run main function
main
