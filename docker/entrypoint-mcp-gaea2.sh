#!/bin/bash
set -e  # Exit on any error
# Entrypoint script for MCP Gaea2 container
# Ensures proper permissions on mounted volumes

echo "🔧 Setting up MCP Gaea2 container..."

# Ensure the output directory exists and has proper permissions
if [ -d "/output/gaea2" ]; then
    echo "📁 Fixing /output/gaea2 directory permissions..."
    # If we can't change ownership, at least ensure it's writable
    if ! chmod -R 755 /output/gaea2 2>/dev/null; then
        echo "⚠️  Could not set full permissions on /output/gaea2"
        # Try to make it at least group writable
        chmod -R g+w /output/gaea2 2>/dev/null || true
    else
        echo "✅ /output/gaea2 directory permissions fixed"
    fi
else
    echo "📁 Creating /output/gaea2 directory..."
    mkdir -p /output/gaea2
    chmod 755 /output/gaea2
fi

echo "👤 Running as user: $(whoami) ($(id))"
echo "📁 Output directory permissions:"
ls -la /output/gaea2 2>/dev/null || echo "Could not list /output/gaea2 directory"

# Execute the original command
echo "🚀 Starting MCP Gaea2 server..."
exec "$@"
