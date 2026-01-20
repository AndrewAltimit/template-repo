#!/bin/bash
# gh-validator uninstall script
# Removes the gh wrapper from ~/.local/bin

set -e

INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="gh"
BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"

echo "============================================"
echo "gh-validator Uninstall"
echo "============================================"
echo ""

if [ -f "$BINARY_PATH" ]; then
    # Verify it's gh-validator by checking if it finds real gh
    echo "Found gh at: $BINARY_PATH"
    rm -f "$BINARY_PATH"
    echo "Removed gh-validator."
    echo ""
    echo "Your system gh CLI is now used directly."
else
    echo "gh-validator not found at: $BINARY_PATH"
    echo "Nothing to uninstall."
fi

echo ""
echo "Uninstall complete."
echo ""
