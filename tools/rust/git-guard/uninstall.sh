#!/bin/bash
# git-guard uninstall script
# Removes the git-guard wrapper from ~/.local/bin

set -e

INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="git"
BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"

echo "============================================"
echo "git-guard Uninstall"
echo "============================================"
echo ""

if [ -f "$BINARY_PATH" ]; then
    # Verify it's actually git-guard and not some other git
    if "$BINARY_PATH" push --force 2>&1 | grep -q "GIT-GUARD"; then
        echo "Found git-guard at: $BINARY_PATH"
        rm -f "$BINARY_PATH"
        echo "Removed git-guard."
        echo ""
        echo "Your system git is now used directly."
        echo ""
        echo "Note: You may want to remove the PATH modification from"
        echo "your ~/.bashrc or ~/.zshrc if no longer needed."
    else
        echo "WARNING: ${BINARY_PATH} exists but doesn't appear to be git-guard."
        echo "Not removing to avoid breaking your system."
        exit 1
    fi
else
    echo "git-guard not found at: $BINARY_PATH"
    echo "Nothing to uninstall."
fi

echo ""
echo "Uninstall complete."
echo ""
