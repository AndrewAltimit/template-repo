#!/bin/bash
# One-time fix for existing permission issues on self-hosted runner
# Run this script as the runner user to fix permission issues

echo "🔧 Fixing permission issues in GitHub Actions runner workspace"

# Find the runner work directory
RUNNER_WORKSPACE="${GITHUB_WORKSPACE:-$HOME/Documents/repos/actions-runner-template-repo/_work}"

if [ ! -d "$RUNNER_WORKSPACE" ]; then
    echo "❌ Runner workspace not found at: $RUNNER_WORKSPACE"
    echo "Please set GITHUB_WORKSPACE environment variable or update the path"
    exit 1
fi

echo "📁 Found runner workspace: $RUNNER_WORKSPACE"

# Fix permissions on all Python cache files
echo "🔨 Fixing permissions on Python cache files..."

# Track results
fixed_count=0
failed_count=0

# Use sudo if available, otherwise try without
if command -v sudo &> /dev/null; then
    echo "Using sudo to fix permissions..."

    # Fix directory permissions
    if sudo find "$RUNNER_WORKSPACE" -type d -name "__pycache__" -exec chmod -R 755 {} + 2>/dev/null; then
        ((fixed_count++))
    else
        echo "⚠️  Some __pycache__ directories couldn't be fixed"
        ((failed_count++))
    fi

    # Fix file permissions
    if sudo find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -exec chmod 644 {} + 2>/dev/null; then
        ((fixed_count++))
    else
        echo "⚠️  Some .pyc files couldn't be fixed"
        ((failed_count++))
    fi

    # Fix ownership
    if sudo chown -R "$USER:$USER" "$RUNNER_WORKSPACE" 2>/dev/null; then
        echo "✅ Ownership fixed"
    else
        echo "⚠️  Could not change ownership of all files"
        ((failed_count++))
    fi
else
    echo "Attempting to fix permissions without sudo..."
    echo "⚠️  This may not work for files owned by other users"

    find "$RUNNER_WORKSPACE" -type d -name "__pycache__" -user "$USER" -exec chmod -R 755 {} + 2>/dev/null
    find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -user "$USER" -exec chmod 644 {} + 2>/dev/null
fi

# Remove cache files if possible
echo "🗑️ Attempting to remove cache files..."
removed_count=0

for pattern in "__pycache__" ".pytest_cache"; do
    count=$(find "$RUNNER_WORKSPACE" -name "$pattern" -type d 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
        echo "Found $count $pattern directories"
        if find "$RUNNER_WORKSPACE" -name "$pattern" -type d -exec rm -rf {} + 2>/dev/null; then
            ((removed_count+=count))
        else
            echo "⚠️  Could not remove all $pattern directories"
        fi
    fi
done

# Remove .pyc files
pyc_count=$(find "$RUNNER_WORKSPACE" -name "*.pyc" -type f 2>/dev/null | wc -l)
if [ "$pyc_count" -gt 0 ]; then
    echo "Found $pyc_count .pyc files"
    if find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -delete 2>/dev/null; then
        ((removed_count+=pyc_count))
    else
        echo "⚠️  Could not remove all .pyc files"
    fi
fi

# Fix output and outputs directories (including Docker-created ones)
echo ""
echo "🔧 Fixing output/outputs directories (including Docker-created)..."

# Find both 'output' and 'outputs' directories
output_dirs=$(find "$RUNNER_WORKSPACE" -type d \( -name "output" -o -name "outputs" \) 2>/dev/null | head -50)

if [ -n "$output_dirs" ]; then
    echo "Found output/outputs directories:"
    echo "$output_dirs" | head -10
    total_count=$(echo "$output_dirs" | wc -l)
    echo "Total found: $total_count directories"

    for dir in $output_dirs; do
        echo "Processing: $dir"

        # Try to fix permissions first
        if command -v sudo &> /dev/null; then
            # First try to change permissions to allow deletion
            sudo chmod -R 777 "$dir" 2>/dev/null

            # Change ownership to current user
            if sudo chown -R "$USER:$USER" "$dir" 2>/dev/null; then
                echo "✅ Fixed ownership: $dir"
                # Then try to remove it
                if rm -rf "$dir" 2>/dev/null; then
                    echo "✅ Removed: $dir"
                    ((removed_count++))
                fi
            else
                # If can't fix ownership, try to remove with sudo
                if sudo rm -rf "$dir" 2>/dev/null; then
                    echo "✅ Removed with sudo: $dir"
                    ((removed_count++))
                else
                    echo "❌ Could not fix or remove: $dir"
                fi
            fi
        else
            # No sudo available, try normal removal
            if rm -rf "$dir" 2>/dev/null; then
                echo "✅ Removed: $dir"
                ((removed_count++))
            else
                echo "❌ Could not remove (no sudo available): $dir"
            fi
        fi
    done
else
    echo "No output/outputs directories found"
fi

# Specifically handle MCP-related directories that Docker might have created
echo ""
echo "🔧 Fixing MCP and Docker-created directories..."
mcp_patterns=("mcp-*" "manim_*" "latex_*" "*.tex" "*.pdf" "*.mp4")

for pattern in "${mcp_patterns[@]}"; do
    mcp_dirs=$(find "$RUNNER_WORKSPACE" -type d -name "$pattern" 2>/dev/null | head -20)
    if [ -n "$mcp_dirs" ]; then
        echo "Found $pattern directories:"
        for dir in $mcp_dirs; do
            if command -v sudo &> /dev/null; then
                sudo chmod -R 777 "$dir" 2>/dev/null
                sudo chown -R "$USER:$USER" "$dir" 2>/dev/null
                if rm -rf "$dir" 2>/dev/null || sudo rm -rf "$dir" 2>/dev/null; then
                    echo "✅ Removed: $dir"
                    ((removed_count++))
                else
                    echo "❌ Could not remove: $dir"
                fi
            else
                if rm -rf "$dir" 2>/dev/null; then
                    echo "✅ Removed: $dir"
                    ((removed_count++))
                fi
            fi
        done
    fi
done

echo ""
echo "🔧 Configuring git safe directories..."
# Add workspace to git safe directories to prevent ownership issues
if command -v git &> /dev/null; then
    # Add the runner workspace to safe directories
    git config --global --add safe.directory "$RUNNER_WORKSPACE" 2>/dev/null || true
    git config --global --add safe.directory "$RUNNER_WORKSPACE/template-repo" 2>/dev/null || true
    git config --global --add safe.directory "$RUNNER_WORKSPACE/template-repo/template-repo" 2>/dev/null || true
    echo "✅ Git safe directories configured"
else
    echo "⚠️  Git not found, skipping safe directory configuration"
fi

echo ""
echo "✅ Permission fix complete!"
echo ""
echo "📌 Summary:"
echo "- Removed/fixed: $removed_count items"
echo "- Failed: $failed_count items"
echo ""
echo "📌 Next steps:"
echo "1. Try running your GitHub Actions workflow again"
echo "2. If issues persist, you may need to manually remove the workspace:"
echo "   sudo rm -rf $RUNNER_WORKSPACE/template-repo"
echo "3. The prevention measures now in place should prevent this from happening again:"
echo "   - MCP containers run with proper user permissions"
echo "   - Output directories are cleaned before each run"
echo "   - Git safe directories are configured"
