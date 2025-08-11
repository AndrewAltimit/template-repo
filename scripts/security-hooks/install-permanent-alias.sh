#!/bin/sh
# Install permanent gh alias for security wrapper
# This ensures the alias is active in ALL shell sessions

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER_PATH="$SCRIPT_DIR/gh-wrapper.sh"

echo "Installing permanent gh alias for security wrapper..."

# Function to add alias to a file if it doesn't exist
add_alias_to_file() {
    file="$1"
    if [ -f "$file" ]; then
        if ! grep -q "alias gh=" "$file" 2>/dev/null; then
            {
                echo ""
                echo "# Universal gh security wrapper - auto-installed"
                echo "alias gh=\"$WRAPPER_PATH\""
            } >> "$file"
            echo "  ✓ Added alias to $file"
        else
            echo "  - Alias already exists in $file"
        fi
    fi
}

# Install for current user
if [ -n "$HOME" ]; then
    # Bash
    add_alias_to_file "$HOME/.bashrc"
    add_alias_to_file "$HOME/.bash_aliases"

    # POSIX shells
    add_alias_to_file "$HOME/.profile"

    # Zsh
    add_alias_to_file "$HOME/.zshrc"
fi

# Install system-wide (requires sudo)
if [ -w "/etc/bash.bashrc" ]; then
    add_alias_to_file "/etc/bash.bashrc"
fi

if [ -w "/etc/profile" ]; then
    add_alias_to_file "/etc/profile"
fi

echo ""
echo "✅ Permanent alias installation complete!"
echo ""
echo "The gh wrapper will be active in:"
echo "  - All new bash sessions"
echo "  - All new sh/dash sessions"
echo "  - All new zsh sessions (if installed)"
echo "  - Docker containers (after rebuild)"
echo ""
echo "To activate in current session, run:"
echo "  alias gh=\"$WRAPPER_PATH\""
