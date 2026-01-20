#!/bin/bash
# pr-monitor installation script
# Installs the dedicated PR monitoring tool for watching comments and reviews

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="pr-monitor"

echo "============================================"
echo "pr-monitor Installation"
echo "============================================"
echo ""

# Check if we need to build
BINARY_PATH="${SCRIPT_DIR}/target/release/${BINARY_NAME}"
if [ ! -f "$BINARY_PATH" ]; then
    echo "Binary not found, building from source..."
    cd "$SCRIPT_DIR"
    cargo build --release
    echo "Build complete."
else
    echo "Using existing binary: $BINARY_PATH"
fi

# Verify binary exists after build attempt
if [ ! -f "$BINARY_PATH" ]; then
    echo "ERROR: Failed to build ${BINARY_NAME} binary"
    exit 1
fi

# Create install directory
echo ""
echo "Installing to: ${INSTALL_DIR}/${BINARY_NAME}"
mkdir -p "$INSTALL_DIR"

# Copy binary
cp "$BINARY_PATH" "${INSTALL_DIR}/${BINARY_NAME}"
chmod +x "${INSTALL_DIR}/${BINARY_NAME}"

echo "Binary installed successfully."

# Check PATH
echo ""
if [[ ":$PATH:" == *":${INSTALL_DIR}:"* ]]; then
    echo "PATH is configured correctly."
else
    echo "WARNING: ${INSTALL_DIR} is NOT in your PATH"
    echo ""
    echo "Add this line to your ~/.bashrc or ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# Verify installation
echo ""
echo "Verifying installation..."
if "${INSTALL_DIR}/${BINARY_NAME}" --help >/dev/null 2>&1; then
    echo "Installation successful!"
    echo ""
    "${INSTALL_DIR}/${BINARY_NAME}" --help | head -10
else
    echo "WARNING: Binary installed but --help failed"
fi

echo ""
echo "============================================"
echo "Installation complete!"
echo "============================================"
echo ""
echo "Usage: ${BINARY_NAME} <PR_NUMBER> [OPTIONS]"
echo ""
echo "Examples:"
echo "  ${BINARY_NAME} 123                      # Monitor PR #123"
echo "  ${BINARY_NAME} 123 --timeout 1800       # 30 minute timeout"
echo "  ${BINARY_NAME} 123 --since-commit abc   # Only comments after commit"
echo "  ${BINARY_NAME} 123 --json               # JSON output for automation"
echo ""
