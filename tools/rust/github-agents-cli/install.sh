#!/bin/bash
# github-agents-cli installation script
# Installs the main AI agent CLI for issue/PR monitoring and automation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="github-agents"

echo "============================================"
echo "github-agents-cli Installation"
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
rm -f "${INSTALL_DIR}/${BINARY_NAME}"
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
echo "Available commands:"
echo "  ${BINARY_NAME} issue-monitor      - Monitor issues for agent triggers"
echo "  ${BINARY_NAME} pr-monitor         - Monitor PRs for agent triggers"
echo "  ${BINARY_NAME} pr-review          - Run PR review analysis"
echo "  ${BINARY_NAME} iteration-check    - Check agent iteration limits"
echo "  ${BINARY_NAME} refinement-monitor - Run backlog refinement"
echo ""
echo "Run '${BINARY_NAME} --help' for all commands."
echo ""
