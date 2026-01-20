#!/bin/bash
# mcp-code-quality uninstall script

set -e

INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="mcp-code-quality"
BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"
SERVICE_NAME="mcp-code-quality"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_PATH="${SERVICE_DIR}/${SERVICE_NAME}.service"

echo "============================================"
echo "mcp-code-quality Uninstall"
echo "============================================"
echo ""

# Stop and disable service if it exists
if [ -f "$SERVICE_PATH" ]; then
    echo "Stopping and disabling systemd service..."
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SERVICE_PATH"
    systemctl --user daemon-reload
    echo "Systemd service removed."
fi

# Remove binary
if [ -f "$BINARY_PATH" ]; then
    rm -f "$BINARY_PATH"
    echo "Removed ${BINARY_NAME} from ${INSTALL_DIR}"
else
    echo "${BINARY_NAME} not found at: $BINARY_PATH"
fi

echo ""
echo "Uninstall complete."
echo ""
