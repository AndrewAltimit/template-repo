#!/bin/bash
# pr-monitor uninstall script

set -e

INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="pr-monitor"
BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"

echo "============================================"
echo "pr-monitor Uninstall"
echo "============================================"
echo ""

if [ -f "$BINARY_PATH" ]; then
    rm -f "$BINARY_PATH"
    echo "Removed ${BINARY_NAME} from ${INSTALL_DIR}"
else
    echo "${BINARY_NAME} not found at: $BINARY_PATH"
    echo "Nothing to uninstall."
fi

echo ""
echo "Uninstall complete."
echo ""
