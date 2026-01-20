#!/bin/bash
# mcp-code-quality installation script
# Installs the Rust MCP server for code quality tools
#
# This is a server binary that can run standalone or be managed by systemd

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="mcp-code-quality"
SERVICE_NAME="mcp-code-quality"

echo "============================================"
echo "mcp-code-quality Installation"
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

# Offer to install systemd service
echo ""
echo "Would you like to install a systemd user service? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    SERVICE_DIR="${HOME}/.config/systemd/user"
    mkdir -p "$SERVICE_DIR"

    cat > "${SERVICE_DIR}/${SERVICE_NAME}.service" << EOF
[Unit]
Description=MCP Code Quality Server
After=network.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/${BINARY_NAME}
Restart=on-failure
RestartSec=5
Environment=RUST_LOG=info

[Install]
WantedBy=default.target
EOF

    echo "Systemd service installed."
    echo ""
    echo "To enable and start the service:"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable ${SERVICE_NAME}"
    echo "  systemctl --user start ${SERVICE_NAME}"
    echo ""
    echo "To check status:"
    echo "  systemctl --user status ${SERVICE_NAME}"
    echo ""
    echo "To view logs:"
    echo "  journalctl --user -u ${SERVICE_NAME} -f"
fi

echo ""
echo "============================================"
echo "Installation complete!"
echo "============================================"
echo ""
echo "To run manually: ${BINARY_NAME}"
echo "Default port: 8010"
echo ""
