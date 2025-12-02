#!/bin/bash
# Fix permission issues on self-hosted runner
# This script fixes ownership issues caused by Docker containers running as different users

set -e

echo "🔧 Fixing permission issues in GitHub Actions runner workspace"

# Find the runner work directory
RUNNER_WORKSPACE="${GITHUB_WORKSPACE:-$HOME/Documents/repos/actions-runner-template-repo/_work}"

# Support minimal mode for pre-checkout cleanup
MINIMAL_MODE=false
if [ "$1" = "--minimal" ]; then
    MINIMAL_MODE=true
fi

if [ ! -d "$RUNNER_WORKSPACE" ]; then
    if [ "$MINIMAL_MODE" = true ]; then
        # In minimal mode, just exit silently if workspace doesn't exist
        exit 0
    fi
    echo "❌ Runner workspace not found at: $RUNNER_WORKSPACE"
    echo "Please set GITHUB_WORKSPACE environment variable or update the path"
    exit 1
fi

echo "📁 Found runner workspace: $RUNNER_WORKSPACE"

# Export user IDs for Docker to use
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

echo "👤 Running as user: $USER (UID: $USER_ID, GID: $GROUP_ID)"

# Function to safely process directories
process_directories() {
    local pattern="$1"
    local action="$2"

    # Use while loop with IFS to handle paths with spaces correctly
    find "$RUNNER_WORKSPACE" -type d -name "$pattern" 2>/dev/null | while IFS= read -r dir; do
        echo "Processing: $dir"

        # Try to fix ownership if we have sudo
        if command -v sudo &> /dev/null; then
            # Change ownership to current user (no chmod 777!)
            if sudo chown -R "$USER_ID:$GROUP_ID" "$dir" 2>/dev/null; then
                echo "✅ Fixed ownership: $dir"

                if [ "$action" = "remove" ]; then
                    if rm -rf "$dir" 2>/dev/null; then
                        echo "✅ Removed: $dir"
                    fi
                fi
            else
                # If can't fix ownership, try to remove with sudo
                if [ "$action" = "remove" ] && sudo rm -rf "$dir" 2>/dev/null; then
                    echo "✅ Removed with sudo: $dir"
                    else
                    echo "⚠️  Could not fix: $dir"
                fi
            fi
        else
            # No sudo available, try normal operations
            if [ "$action" = "remove" ] && rm -rf "$dir" 2>/dev/null; then
                echo "✅ Removed: $dir"
            else
                echo "⚠️  Could not process (no sudo): $dir"
                ((failed_count++))
            fi
        fi
    done
}

if [ "$MINIMAL_MODE" != true ]; then
    # Full cleanup mode
    echo "🔨 Fixing permissions on Python cache files..."

    # Process Python cache directories
    process_directories "__pycache__" "remove"
    process_directories ".pytest_cache" "remove"

    # Remove .pyc files
    find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -delete 2>/dev/null || true
fi

# Fix the _work directory itself and critical subdirectories (GitHub Actions runner directories)
echo ""
echo "🔧 Fixing GitHub Actions runner _work directory permissions..."

# Fix ownership of the _work directory itself and key subdirectories
if command -v sudo &> /dev/null; then
    # Fix _work directory ownership
    if [ -d "$RUNNER_WORKSPACE" ]; then
        echo "  Fixing _work directory ownership..."
        sudo chown "$USER_ID:$GROUP_ID" "$RUNNER_WORKSPACE" 2>/dev/null || echo "⚠️  Could not fix _work directory"
    fi

    # Fix _tool directory (GitHub Actions tool cache) if it exists
    if [ -d "$RUNNER_WORKSPACE/_tool" ]; then
        echo "  Fixing _tool directory ownership..."
        sudo chown -R "$USER_ID:$GROUP_ID" "$RUNNER_WORKSPACE/_tool" 2>/dev/null || echo "⚠️  Could not fix _tool directory"
    fi

    # Fix any repository checkout directories
    for dir in "$RUNNER_WORKSPACE"/*/; do
        if [ -d "$dir" ] && [ "$(stat -c '%u' "$dir" 2>/dev/null)" = "0" ]; then
            echo "  Fixing ownership: $dir"
            sudo chown -R "$USER_ID:$GROUP_ID" "$dir" 2>/dev/null || echo "⚠️  Could not fix $dir"
        fi
    done
fi

# Fix output and outputs directories (these often have Docker permission issues)
echo ""
echo "🔧 Fixing output/outputs directories..."

# Process output directories - just fix ownership, don't remove in minimal mode
if [ "$MINIMAL_MODE" = true ]; then
    process_directories "outputs" "fix"
    process_directories "output" "fix"
    # More specific patterns for MCP output directories
    for pattern in "mcp-content" "mcp-memes" "mcp-gaea2" "mcp-code-quality"; do
        process_directories "$pattern" "fix"
    done
else
    process_directories "outputs" "remove"
    process_directories "output" "remove"
    # Be more specific with MCP directories to avoid unintended matches
    for pattern in "mcp-content" "mcp-memes" "mcp-gaea2" "mcp-code-quality"; do
        process_directories "$pattern" "remove"
    done
fi

echo ""
echo "🔧 Configuring git safe directories..."
# Add workspace to git safe directories to prevent ownership issues
if command -v git &> /dev/null; then
    git config --global --add safe.directory "$RUNNER_WORKSPACE" 2>/dev/null || true
    git config --global --add safe.directory "$RUNNER_WORKSPACE/template-repo" 2>/dev/null || true
    git config --global --add safe.directory "$RUNNER_WORKSPACE/template-repo/template-repo" 2>/dev/null || true
    echo "✅ Git safe directories configured"
else
    echo "⚠️  Git not found, skipping safe directory configuration"
fi

if [ "$MINIMAL_MODE" != true ]; then
    echo ""
    echo "✅ Permission fix complete!"
    echo ""
    echo "📌 Prevention measures:"
    echo "1. Ensure USER_ID and GROUP_ID are exported before running Docker"
    echo "2. Docker containers should run with: --user \"\$(id -u):\$(id -g)\""
    echo "3. docker-compose.yml should include: user: \"\${USER_ID:-1000}:\${GROUP_ID:-1000}\""
fi
