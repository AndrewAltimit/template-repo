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

# Use sudo if available, otherwise try without
if command -v sudo &> /dev/null; then
    echo "Using sudo to fix permissions..."
    sudo find "$RUNNER_WORKSPACE" -type d -name "__pycache__" -exec chmod -R 755 {} + 2>/dev/null || true
    sudo find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -exec chmod 644 {} + 2>/dev/null || true
    sudo find "$RUNNER_WORKSPACE" -name ".pytest_cache" -exec chmod -R 755 {} + 2>/dev/null || true
    sudo chown -R $USER:$USER "$RUNNER_WORKSPACE" 2>/dev/null || true
else
    echo "Attempting to fix permissions without sudo..."
    find "$RUNNER_WORKSPACE" -type d -name "__pycache__" -exec chmod -R 755 {} + 2>/dev/null || true
    find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -exec chmod 644 {} + 2>/dev/null || true
    find "$RUNNER_WORKSPACE" -name ".pytest_cache" -exec chmod -R 755 {} + 2>/dev/null || true
fi

# Remove cache files if possible
echo "🗑️ Attempting to remove cache files..."
find "$RUNNER_WORKSPACE" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$RUNNER_WORKSPACE" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$RUNNER_WORKSPACE" -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

echo "✅ Permission fix complete!"
echo ""
echo "📌 Next steps:"
echo "1. Try running your GitHub Actions workflow again"
echo "2. If issues persist, you may need to manually remove the workspace:"
echo "   rm -rf $RUNNER_WORKSPACE/template-repo"
echo "3. The prevention measures in place should prevent this from happening again"