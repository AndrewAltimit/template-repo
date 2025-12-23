#!/bin/bash
# gh-validator installer
#
# This script downloads and installs the gh-validator binary for your platform.
# It will be installed to ~/.local/bin/gh and shadow the real gh binary.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/AndrewAltimit/template-repo/main/tools/rust/gh-validator/install.sh | bash
#
# Or with a specific version:
#   curl -sSL .../install.sh | bash -s -- v1.0.0

set -e

# Configuration
REPO="AndrewAltimit/template-repo"
BINARY_NAME="gh"
INSTALL_DIR="${HOME}/.local/bin"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Detect platform
detect_platform() {
    local os
    local arch
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)

    case "$os" in
        linux)
            case "$arch" in
                x86_64) echo "gh-linux-x64" ;;
                aarch64|arm64) echo "gh-linux-arm64" ;;
                *) error "Unsupported architecture: $arch" ;;
            esac
            ;;
        darwin)
            case "$arch" in
                x86_64) echo "gh-macos-x64" ;;
                arm64) echo "gh-macos-arm64" ;;
                *) error "Unsupported architecture: $arch" ;;
            esac
            ;;
        mingw*|msys*|cygwin*)
            echo "gh-windows-x64.exe"
            ;;
        *)
            error "Unsupported OS: $os"
            ;;
    esac
}

# Get the latest release version
get_latest_version() {
    curl -sL "https://api.github.com/repos/${REPO}/releases" | \
        grep -o '"tag_name": "gh-validator-v[^"]*"' | \
        head -1 | \
        sed 's/"tag_name": "gh-validator-//' | \
        tr -d '"'
}

# Main installation function
main() {
    local version="${1:-}"

    info "Detecting platform..."
    local asset_name
    asset_name=$(detect_platform)
    info "Platform: $asset_name"

    # Get version
    if [ -z "$version" ]; then
        info "Fetching latest version..."
        version=$(get_latest_version)
        if [ -z "$version" ]; then
            error "Could not determine latest version. Specify version manually: install.sh v1.0.0"
        fi
    fi
    info "Version: $version"

    # Create install directory
    mkdir -p "$INSTALL_DIR"

    # Download binary
    local download_url="https://github.com/${REPO}/releases/download/gh-validator-${version}/${asset_name}"
    local temp_file
    temp_file=$(mktemp)

    info "Downloading from: $download_url"
    if ! curl -sL -o "$temp_file" "$download_url"; then
        rm -f "$temp_file"
        error "Failed to download binary"
    fi

    # Check if download succeeded (file should not be empty or an error page)
    if [ ! -s "$temp_file" ]; then
        rm -f "$temp_file"
        error "Downloaded file is empty"
    fi

    # Install binary
    local install_path="${INSTALL_DIR}/${BINARY_NAME}"
    mv "$temp_file" "$install_path"
    chmod +x "$install_path"

    info "Installed to: $install_path"

    # Check if install directory is in PATH
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        warn "$INSTALL_DIR is not in your PATH"
        echo ""
        echo "Add the following to your shell configuration (~/.bashrc, ~/.zshrc, etc.):"
        echo ""
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
    fi

    # Verify installation
    if [ -x "$install_path" ]; then
        info "Installation complete!"
        echo ""
        echo "The gh-validator is now installed as 'gh' and will shadow the real gh CLI."
        echo "It will automatically find and call the real gh binary after validation."
        echo ""
        echo "To verify, run: which gh"
        echo "Expected output: $install_path"
    else
        error "Installation verification failed"
    fi
}

main "$@"
