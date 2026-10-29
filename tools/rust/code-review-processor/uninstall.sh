#!/bin/bash
# code-review-processor uninstall script

set -e

INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="code-review-processor"
BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"

echo "============================================"
echo "code-review-processor Uninstall"
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
