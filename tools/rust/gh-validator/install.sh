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
# Note: For forks, change this to your fork's repo or use: REPO="your-user/template-repo" ./install.sh
REPO="${GH_VALIDATOR_REPO:-AndrewAltimit/template-repo}"
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

# Build from source
build_from_source() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [ ! -f "$script_dir/Cargo.toml" ]; then
        return 1
    fi

    info "Building from source..."
    cd "$script_dir"

    if ! command -v cargo &> /dev/null; then
        warn "Cargo not found. Please install Rust first."
        return 1
    fi

    cargo build --release
    if [ -f "$script_dir/target/release/gh" ]; then
        return 0
    fi
    return 1
}

# Main installation function
main() {
    local version="${1:-}"
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local local_binary="$script_dir/target/release/gh"

    # Create install directory
    mkdir -p "$INSTALL_DIR"
    local install_path="${INSTALL_DIR}/${BINARY_NAME}"

    # Strategy 1: Use existing local binary if available
    if [ -f "$local_binary" ]; then
        info "Using existing local binary: $local_binary"
        rm -f "$install_path"
        cp "$local_binary" "$install_path"
        chmod +x "$install_path"
        info "Installed to: $install_path"
        finalize_install "$install_path"
        return 0
    fi

    # Strategy 2: Try to download from releases
    info "Detecting platform..."
    local asset_name
    asset_name=$(detect_platform)
    info "Platform: $asset_name"

    if [ -z "$version" ]; then
        info "Fetching latest version..."
        version=$(get_latest_version)
    fi

    if [ -n "$version" ]; then
        info "Version: $version"

        local download_url="https://github.com/${REPO}/releases/download/gh-validator-${version}/${asset_name}"
        local temp_file
        temp_file=$(mktemp)

        info "Downloading from: $download_url"
        if curl -sL -o "$temp_file" "$download_url" && [ -s "$temp_file" ]; then
            rm -f "$install_path"
            mv "$temp_file" "$install_path"
            chmod +x "$install_path"
            info "Installed to: $install_path"
            finalize_install "$install_path"
            return 0
        fi
        rm -f "$temp_file"
        warn "Download failed, falling back to building from source..."
    else
        warn "No release found, falling back to building from source..."
    fi

    # Strategy 3: Build from source
    if build_from_source; then
        rm -f "$install_path"
        cp "$local_binary" "$install_path"
        chmod +x "$install_path"
        info "Installed to: $install_path"
        finalize_install "$install_path"
        return 0
    fi

    error "Installation failed: no release available and could not build from source"
}

finalize_install() {
    local install_path="$1"

    # Check if hardened mode is active (wrapper-guard setup has been run)
    local guard_dir="/usr/lib/wrapper-guard"
    if [ -f "$guard_dir/gh.real" ]; then
        info "Hardened mode detected"
        echo ""
        echo "Wrapper-guard setup has been run. The wrapper should be"
        echo "installed at /usr/bin/gh, not ~/.local/bin/gh."
        echo ""
        echo "To update the hardened wrapper, re-run the setup script:"
        echo "  sudo bash automation/setup/security/setup-wrapper-guard.sh"
        echo ""
        echo "The binary has been installed to $install_path"
        echo "but will not take effect until the setup script is re-run."
        echo ""
        return 0
    fi

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
