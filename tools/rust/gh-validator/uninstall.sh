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
    # Only remove it if it really is gh-validator (not a real gh install).
    if "$BINARY_PATH" --wrapper-integrity 2>/dev/null | grep -q "^wrapper=gh-validator$"; then
        echo "Found gh-validator at: $BINARY_PATH"
        rm -f "$BINARY_PATH"
        echo "Removed gh-validator."
        echo ""
        echo "Your system gh CLI is now used directly."
    else
        echo "WARNING: ${BINARY_PATH} exists but doesn't appear to be gh-validator."
        echo "Not removing to avoid breaking your system."
        exit 1
    fi
else
    echo "gh-validator not found at: $BINARY_PATH"
    echo "Nothing to uninstall."
fi

echo ""
echo "Uninstall complete."
echo ""
