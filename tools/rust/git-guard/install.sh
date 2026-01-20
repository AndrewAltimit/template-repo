#!/bin/bash
# git-guard installation script
# Installs the git-guard wrapper to intercept dangerous git operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"
BINARY_NAME="git"

echo "============================================"
echo "git-guard Installation"
echo "============================================"
echo ""

# Check if we need to build
BINARY_PATH="${SCRIPT_DIR}/target/release/git"
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
    echo "ERROR: Failed to build git-guard binary"
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
echo "Checking PATH configuration..."

if [[ ":$PATH:" == *":${INSTALL_DIR}:"* ]]; then
    # Check if it comes BEFORE /usr/bin
    INSTALL_DIR_POS=$(echo "$PATH" | tr ':' '\n' | grep -n "^${INSTALL_DIR}$" | cut -d: -f1 | head -1)
    USR_BIN_POS=$(echo "$PATH" | tr ':' '\n' | grep -n "^/usr/bin$" | cut -d: -f1 | head -1)

    if [ -n "$INSTALL_DIR_POS" ] && [ -n "$USR_BIN_POS" ]; then
        if [ "$INSTALL_DIR_POS" -lt "$USR_BIN_POS" ]; then
            echo "PATH is correctly configured (${INSTALL_DIR} comes before /usr/bin)"
        else
            echo ""
            echo "WARNING: ${INSTALL_DIR} is in PATH but AFTER /usr/bin"
            echo "git-guard will NOT intercept git commands!"
            echo ""
            echo "Add this to the TOP of your ~/.bashrc or ~/.zshrc:"
            echo ""
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo ""
        fi
    else
        echo "PATH configured, but could not verify order."
    fi
else
    echo ""
    echo "WARNING: ${INSTALL_DIR} is NOT in your PATH"
    echo ""
    echo "Add this line to your ~/.bashrc or ~/.zshrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then reload your shell:"
    echo ""
    echo "    source ~/.bashrc  # or source ~/.zshrc"
    echo ""
fi

# Verify installation
echo ""
echo "============================================"
echo "Verifying installation..."
echo "============================================"
echo ""

# Test that our git intercepts correctly
if [ -x "${INSTALL_DIR}/${BINARY_NAME}" ]; then
    echo "Testing git-guard..."

    # Test that it blocks force push (should fail with error message)
    if "${INSTALL_DIR}/${BINARY_NAME}" push --force 2>&1 | grep -q "GIT-GUARD"; then
        echo "Force push blocking: WORKING"
    else
        echo "Force push blocking: Could not verify (may need PATH update)"
    fi

    # Test that normal commands pass through
    if "${INSTALL_DIR}/${BINARY_NAME}" --version >/dev/null 2>&1; then
        echo "Normal git commands: WORKING"
        echo ""
        echo "Git version via git-guard:"
        "${INSTALL_DIR}/${BINARY_NAME}" --version
    else
        echo "Normal git commands: FAILED"
        echo "There may be an issue finding the real git binary."
    fi
fi

echo ""
echo "============================================"
echo "Installation complete!"
echo "============================================"
echo ""
echo "git-guard will now require sudo for:"
echo "  - Force push (--force, -f, --force-with-lease)"
echo "  - Skip hooks (--no-verify, -n on commit/merge)"
echo ""
echo "To bypass when needed, use: sudo git <command>"
echo ""
