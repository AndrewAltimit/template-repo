#!/bin/bash
# Fix permission issues for outputs directory and subdirectories
# This script handles both local development and GitHub Actions environments
set -e

echo "🔧 Fixing outputs directory permissions..."

# Determine the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUTS_DIR="$PROJECT_ROOT/outputs"

echo "📁 Project root: $PROJECT_ROOT"
echo "📁 Outputs directory: $OUTPUTS_DIR"

# Check if outputs directory exists and what permissions it has
if [ -d "$OUTPUTS_DIR" ]; then
    echo "📋 Current outputs directory status:"
    ls -la "$OUTPUTS_DIR" || true
    echo ""
fi

# Create outputs directory if it doesn't exist
if [ ! -d "$OUTPUTS_DIR" ]; then
    echo "📁 Creating outputs directory..."
    mkdir -p "$OUTPUTS_DIR"
else
    echo "📁 Outputs directory already exists"
fi

# Function to safely create subdirectories
create_subdir() {
    local subdir_path="$1"
    local subdir_name
    subdir_name="$(basename "$subdir_path")"

    if [ ! -d "$subdir_path" ]; then
        echo "📁 Creating $subdir_name subdirectory..."
        if mkdir -p "$subdir_path" 2>/dev/null; then
            echo "✅ Created: $subdir_path"
        else
            echo "⚠️  Could not create $subdir_path (permission denied)"
            echo "    This may be due to root ownership. Try running:"
            echo "    sudo chown -R \$USER:\$USER '$OUTPUTS_DIR'"
            return 1
        fi
    else
        echo "📁 $subdir_name subdirectory already exists"
    fi
    return 0
}

# Create subdirectories that are needed
create_subdir "$OUTPUTS_DIR/mcp-content"
create_subdir "$OUTPUTS_DIR/mcp-gaea2"

# Function to fix permissions with or without sudo
fix_permissions() {
    local target_dir="$1"
    local success=false

    echo "🔨 Fixing permissions for: $target_dir"

    # Try to get current user info
    CURRENT_USER="${USER:-$(whoami)}"
    CURRENT_GROUP="${GROUP:-$(id -gn)}"

    # First try without sudo
    if chown -R "$CURRENT_USER:$CURRENT_GROUP" "$target_dir" 2>/dev/null; then
        echo "✅ Fixed ownership without sudo"
        success=true
    elif command -v sudo &> /dev/null; then
        echo "🔐 Trying with sudo..."
        if sudo chown -R "$CURRENT_USER:$CURRENT_GROUP" "$target_dir" 2>/dev/null; then
            echo "✅ Fixed ownership with sudo"
            success=true
        else
            echo "⚠️  Could not fix ownership even with sudo"
        fi
    else
        echo "⚠️  No sudo available and couldn't fix without it"
    fi

    # Fix file permissions
    if [ "$success" = true ]; then
        chmod -R 755 "$target_dir" 2>/dev/null || true
        echo "✅ Fixed file permissions"
    fi

    return $success
}

# Fix the main outputs directory
fix_permissions "$OUTPUTS_DIR"

# Fix individual subdirectories
for subdir in "$OUTPUTS_DIR"/*; do
    if [ -d "$subdir" ]; then
        fix_permissions "$subdir"
    fi
done

# Check final permissions
echo ""
echo "📋 Final permissions check:"
ls -la "$OUTPUTS_DIR" || true

echo ""
echo "✅ Outputs directory permissions fixed!"
echo ""
echo "📌 The outputs directory now has proper permissions for:"
echo "   - Local development with Docker containers"
echo "   - GitHub Actions with self-hosted runners"
echo "   - User ID: $(id -u) / Group ID: $(id -g)"
