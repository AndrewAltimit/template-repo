#!/bin/bash
#
# Complete setup script for GitHub Actions self-hosted runner with MCP support
#

set -e

echo "🚀 GitHub Actions Self-Hosted Runner Complete Setup"
echo "=================================================="

# Configuration
RUNNER_VERSION="2.311.0"
RUNNER_OS=$(uname -s | tr '[:upper:]' '[:lower:]')
RUNNER_ARCH="x64"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root!${NC}"
   echo "Please run as a regular user with sudo access."
   exit 1
fi

# Function to print colored output
print_status() {
    echo -e "${GREEN}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

# Function to validate environment
validate_environment() {
    echo ""
    echo "📋 Validating Runner Environment"
    echo "================================"

    # Check system info
    print_status "System Information:"
    echo "  OS: $(uname -s) $(uname -r)"
    echo "  Architecture: $(uname -m)"
    echo "  Hostname: $(hostname)"

    # Check disk space
    print_status "Disk Space:"
    df -h | grep -E '^/dev|Filesystem'

    # Check memory
    print_status "Memory:"
    free -h 2>/dev/null || echo "Memory info not available"

    # Check network connectivity
    print_status "Network Connectivity:"
    if curl -s https://api.github.com/zen > /dev/null; then
        echo "  ✅ GitHub API: Connected"
    else
        print_error "  ❌ GitHub API: Not reachable"
        exit 1
    fi
}

# Function to check and install prerequisites
check_prerequisites() {
    echo ""
    echo "📦 Checking Prerequisites"
    echo "========================"

    # Check for required commands
    local required_commands=("curl" "tar" "git" "sudo" "jq")
    local missing_commands=()

    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
        else
            print_status "✅ $cmd is installed"
        fi
    done

    # Install missing commands if on Linux
    if [ ${#missing_commands[@]} -gt 0 ] && [ "$RUNNER_OS" = "linux" ]; then
        print_warning "Installing missing commands: ${missing_commands[*]}"
        sudo apt-get update
        sudo apt-get install -y "${missing_commands[@]}"
    elif [ ${#missing_commands[@]} -gt 0 ]; then
        print_error "Missing required commands: ${missing_commands[*]}"
        echo "Please install them manually and re-run this script."
        exit 1
    fi

    # Check Python
    if command -v python3 &> /dev/null; then
        print_status "✅ Python3 is installed: $(python3 --version)"
    else
        if [ "$RUNNER_OS" = "linux" ]; then
            print_warning "Installing Python3..."
            sudo apt-get install -y python3 python3-pip python3-venv
        else
            print_error "❌ Python3 is not installed"
            exit 1
        fi
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo ""
        print_warning "⚠️  Docker is not installed."
        echo "Would you like to install Docker? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            install_docker
        else
            print_warning "Continuing without Docker. Container features will not work."
        fi
    else
        print_status "✅ Docker is installed: $(docker --version)"

        # Check Docker Compose
        if docker compose version &> /dev/null; then
            print_status "✅ Docker Compose V2 is installed"
        elif docker compose --version &> /dev/null; then
            print_status "✅ Docker Compose V1 is installed"
        else
            install_docker_compose
        fi
    fi
}

# Function to install Docker
install_docker() {
    print_status "Installing Docker..."

    if [ "$RUNNER_OS" = "linux" ]; then
        # Install Docker using official script
        curl -fsSL https://get.docker.com | sudo sh

        # Add current user to docker group
        sudo usermod -aG docker "$USER"

        print_status "✅ Docker installed"
        print_warning "⚠️  You need to log out and back in for group changes to take effect"
    else
        print_error "Please install Docker manually for your OS"
        exit 1
    fi
}

# Function to install Docker Compose
install_docker_compose() {
    print_status "Installing Docker Compose..."

    if [ "$RUNNER_OS" = "linux" ]; then
        sudo apt-get update
        sudo apt-get install -y docker-compose-plugin
        print_status "✅ Docker Compose installed"
    fi
}

# Function to install system dependencies
install_dependencies() {
    echo ""
    echo "📦 Installing System Dependencies"
    echo "================================"

    if [ "$RUNNER_OS" = "linux" ]; then
        print_status "Updating package list..."
        sudo apt-get update

        print_status "Installing essential packages..."
        sudo apt-get install -y \
            build-essential \
            git \
            curl \
            wget \
            jq \
            zip \
            unzip \
            software-properties-common \
            apt-transport-https \
            ca-certificates \
            gnupg \
            lsb-release

        print_status "✅ System dependencies installed"
    else
        print_warning "Please ensure build tools are installed for your OS"
    fi
}

# Function to create runner directory
create_runner_directory() {
    echo ""
    echo "📁 Setting Up Runner Directory"
    echo "============================="

    RUNNER_DIR="$HOME/actions-runner"

    if [ -d "$RUNNER_DIR" ]; then
        print_warning "Runner directory already exists at $RUNNER_DIR"
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

    # Create workspace directories
    mkdir -p _work _temp _logs

    print_status "✅ Created runner directory at $RUNNER_DIR"
}

# Function to download runner
download_runner() {
    echo ""
    echo "📥 Downloading GitHub Actions Runner"
    echo "==================================="

    print_status "Downloading runner v${RUNNER_VERSION}..."

    # Determine download URL based on OS and architecture
    local download_url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

    # Download and extract
    curl -O -L "$download_url"
    tar xzf "./actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
    rm "./actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"

    print_status "✅ Runner downloaded and extracted"
}

# Function to get runner token
get_runner_token() {
    echo ""
    echo "🔑 Runner Registration"
    echo "===================="
    echo ""
    echo "To register this runner, you need a registration token from GitHub."
    echo ""
    print_status "For a repository runner:"
    echo "  1. Go to: https://github.com/OWNER/REPO/settings/actions/runners/new"
    echo "  2. Copy the registration token"
    echo ""
    print_status "For an organization runner:"
    echo "  1. Go to: https://github.com/organizations/ORG/settings/actions/runners/new"
    echo "  2. Copy the registration token"
    echo ""
    echo "Enter your registration token:"
    read -rs RUNNER_TOKEN
    echo ""

    if [ -z "$RUNNER_TOKEN" ]; then
        print_error "❌ No token provided. Exiting."
        exit 1
    fi
}

# Function to configure runner
configure_runner() {
    echo ""
    echo "⚙️  Configuring Runner"
    echo "===================="

    # Get repository or organization URL
    echo "Enter the repository or organization URL:"
    echo "Example: https://github.com/owner/repo or https://github.com/org"
    read -r REPO_URL

    # Get runner name
    echo "Enter a name for this runner (default: $(hostname)):"
    read -r RUNNER_NAME
    RUNNER_NAME=${RUNNER_NAME:-$(hostname)}

    # Get runner labels
    echo "Enter additional labels for this runner (comma-separated, default: self-hosted,$RUNNER_OS):"
    read -r RUNNER_LABELS
    RUNNER_LABELS=${RUNNER_LABELS:-"self-hosted,$RUNNER_OS"}

    # Configure the runner
    ./config.sh \
        --url "$REPO_URL" \
        --token "$RUNNER_TOKEN" \
        --name "$RUNNER_NAME" \
        --labels "$RUNNER_LABELS" \
        --unattended \
        --replace

    print_status "✅ Runner configured successfully"
}

# Function to setup MCP environment
setup_mcp_environment() {
    echo ""
    echo "🤖 Setting Up MCP Environment"
    echo "============================"

    # Create MCP directories
    MCP_HOME="$HOME/.mcp"
    mkdir -p "$MCP_HOME/configs"
    mkdir -p "$MCP_HOME/logs"

    # Copy MCP configuration if available
    if [ -f "../.mcp.json" ]; then
        cp ../.mcp.json "$MCP_HOME/configs/"
        print_status "✅ Copied MCP configuration"
    elif [ -f ".mcp.json" ]; then
        cp .mcp.json "$MCP_HOME/configs/"
        print_status "✅ Copied MCP configuration"
    else
        print_warning "⚠️  No .mcp.json found. You'll need to configure MCP manually."
    fi

    # Create environment file
    if [ ! -f "$MCP_HOME/.env" ]; then
        cat > "$MCP_HOME/.env" << 'EOF'
# MCP Environment Configuration
# Update these values with your actual credentials

# GitHub Token (required for GitHub tools)
GITHUB_TOKEN=

# Gemini CLI authentication (no API key needed)

# Optional: ComfyUI Server URL
COMFYUI_SERVER_URL=http://192.168.0.222:8189

# Optional: AI Toolkit Server URL
AI_TOOLKIT_SERVER_URL=http://192.168.0.222:8190
EOF
        print_warning "⚠️  Please update $MCP_HOME/.env with your actual values"
    fi

    print_status "✅ MCP environment setup complete"
}

# Function to install git-guard
install_git_guard() {
    echo ""
    echo "🛡️  Installing git-guard"
    echo "========================"

    # Get the repo root (parent of actions-runner)
    local REPO_ROOT
    REPO_ROOT=$(cd "$HOME/actions-runner/_work" 2>/dev/null && find . -name "git-guard" -type d -path "*/tools/rust/*" 2>/dev/null | head -1 | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null)

    # If we can't find it in the workspace, check if we're in the repo
    if [ -z "$REPO_ROOT" ] || [ ! -d "$REPO_ROOT/tools/rust/git-guard" ]; then
        # Try relative to this script
        local SCRIPT_DIR
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    fi

    local GIT_GUARD_DIR="$REPO_ROOT/tools/rust/git-guard"

    if [ ! -d "$GIT_GUARD_DIR" ]; then
        print_warning "git-guard source not found at $GIT_GUARD_DIR"
        print_warning "Skipping git-guard installation. Install manually later with:"
        echo "  cd tools/rust/git-guard && ./install.sh"
        return 0
    fi

    # Check if Rust is installed
    if ! command -v cargo &> /dev/null; then
        print_warning "Rust/Cargo not installed. Installing rustup..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        # shellcheck source=/dev/null
        source "$HOME/.cargo/env"
    fi

    # Run the git-guard install script
    if [ -f "$GIT_GUARD_DIR/install.sh" ]; then
        print_status "Running git-guard installation..."
        bash "$GIT_GUARD_DIR/install.sh"
    else
        # Manual installation if script doesn't exist
        print_status "Building git-guard..."
        cd "$GIT_GUARD_DIR"
        cargo build --release

        print_status "Installing git-guard to ~/.local/bin..."
        mkdir -p "$HOME/.local/bin"
        cp target/release/git "$HOME/.local/bin/git"
        chmod +x "$HOME/.local/bin/git"
    fi

    # Ensure PATH is configured for the runner
    # Add to .bashrc if not already present
    # shellcheck disable=SC2016 # We want literal $HOME in the file
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" 2>/dev/null; then
        # shellcheck disable=SC2016 # We want literal $HOME in the file
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        print_status "Added ~/.local/bin to PATH in .bashrc"
    fi

    # Also add to runner's environment
    local RUNNER_ENV="$HOME/actions-runner/.env"
    if [ -f "$RUNNER_ENV" ]; then
        if ! grep -q 'PATH=' "$RUNNER_ENV" 2>/dev/null; then
            echo "PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" >> "$RUNNER_ENV"
            print_status "Added PATH to runner environment"
        fi
    fi

    print_status "git-guard installed successfully"
    print_status "AI agents on this runner cannot force push or skip hooks without sudo"
}

# Function to configure log rotation
configure_log_rotation() {
    echo ""
    echo "📝 Configuring Log Rotation"
    echo "=========================="

    if [ "$RUNNER_OS" = "linux" ]; then
        sudo tee /etc/logrotate.d/github-runner << EOF
$HOME/actions-runner/_logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $USER $USER
}
EOF
        print_status "✅ Log rotation configured"
    else
        print_warning "Please configure log rotation manually for your OS"
    fi
}

# Function to install as service
install_service() {
    echo ""
    echo "🔧 Service Installation"
    echo "======================"

    echo "Would you like to install the runner as a systemd service? (y/n)"
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Installing runner service..."
        sudo ./svc.sh install
        sudo ./svc.sh start

        print_status "✅ Runner installed as service"
        echo ""
        print_status "Service commands:"
        echo "  Start:   sudo ./svc.sh start"
        echo "  Stop:    sudo ./svc.sh stop"
        echo "  Status:  sudo ./svc.sh status"
        echo "  Logs:    sudo journalctl -u actions.runner.* -f"
    else
        echo ""
        print_status "To run the runner manually:"
        echo "  cd $RUNNER_DIR"
        echo "  ./run.sh"
    fi
}

# Function to test MCP server
test_mcp_server() {
    echo ""
    echo "🧪 Testing MCP Server"
    echo "===================="

    if command -v docker &> /dev/null && [ -f "../docker-compose.yml" ]; then
        print_status "Starting MCP server for testing..."
        cd ..
        docker compose up -d mcp-server
        sleep 10

        print_status "MCP server logs:"
        docker compose logs --tail=20 mcp-server

        print_status "Stopping MCP server..."
        docker compose down

        cd "$RUNNER_DIR"
        print_status "✅ MCP server test complete"
    else
        print_warning "Skipping MCP server test (Docker or docker-compose.yml not available)"
    fi
}

# Function to create summary
create_summary() {
    echo ""
    echo "============================================"
    echo "🎉 GitHub Actions Runner Setup Complete!"
    echo "============================================"
    echo ""
    print_status "Runner Details:"
    echo "  Directory: $RUNNER_DIR"
    echo "  Name: $RUNNER_NAME"
    echo "  Labels: $RUNNER_LABELS"
    echo ""
    print_status "MCP Configuration:"
    echo "  Config: $HOME/.mcp/configs/"
    echo "  Environment: $HOME/.mcp/.env"
    echo ""
    print_status "Git Safety:"
    echo "  git-guard: ~/.local/bin/git"
    echo "  Force push and --no-verify require sudo"
    echo ""
    print_status "Next Steps:"
    echo "  1. If you installed Docker, log out and back in"
    echo "  2. Update environment variables in $HOME/.mcp/.env"
    echo "  3. Test the runner with a simple workflow"
    echo ""
    print_status "Useful Commands:"
    echo "  View runner status: sudo ./svc.sh status"
    echo "  View runner logs: sudo journalctl -u actions.runner.* -f"
    echo "  Test MCP locally: cd .. && docker compose up mcp-server"
}

# Main setup flow
main() {
    # Parse command line arguments
    SKIP_DOCKER=false
    SKIP_RUNNER_DOWNLOAD=false
    export SKIP_DOCKER
    export SKIP_RUNNER_DOWNLOAD

    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-runner-download)
                SKIP_RUNNER_DOWNLOAD=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --skip-docker          Skip Docker installation"
                echo "  --skip-runner-download Skip runner download (use existing)"
                echo "  --help                 Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Run setup steps
    validate_environment
    check_prerequisites
    install_dependencies
    create_runner_directory

    if [ "$SKIP_RUNNER_DOWNLOAD" = false ]; then
        download_runner
        get_runner_token
        configure_runner
    fi

    setup_mcp_environment
    install_git_guard
    configure_log_rotation
    install_service
    test_mcp_server
    create_summary
}

# Run main function
main "$@"
