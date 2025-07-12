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
    if sudo chown -R $USER:$USER "$RUNNER_WORKSPACE" 2>/dev/null; then
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

echo "✅ Permission fix complete!"
echo ""
echo "📌 Next steps:"
echo "1. Try running your GitHub Actions workflow again"
echo "2. If issues persist, you may need to manually remove the workspace:"
echo "   rm -rf $RUNNER_WORKSPACE/template-repo"
echo "3. The prevention measures in place should prevent this from happening again"
