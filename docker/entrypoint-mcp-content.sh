#!/bin/bash
# Entrypoint script for MCP Content Creation container
# Ensures proper permissions on mounted volumes

echo "🔧 Setting up MCP Content Creation container..."

# Ensure the output directory exists and has proper permissions
if [ -d "/output" ]; then
    echo "📁 Fixing /output directory permissions..."
    # If we can't change ownership, at least ensure it's writable
    if ! chmod -R 777 /output 2>/dev/null; then
        echo "⚠️  Could not set full permissions on /output"
        # Try to make it at least group writable
        chmod -R g+w /output 2>/dev/null || true
    else
        echo "✅ /output directory permissions fixed"
    fi
else
    echo "📁 Creating /output directory..."
    mkdir -p /output
    chmod 777 /output
fi

# Ensure subdirectories exist
mkdir -p /output/manim /output/latex 2>/dev/null || true
chmod -R 777 /output/manim /output/latex 2>/dev/null || true

echo "👤 Running as user: $(whoami) ($(id))"
echo "📁 Output directory permissions:"
ls -la /output 2>/dev/null || echo "Could not list /output directory"

# Execute the original command
echo "🚀 Starting MCP Content Creation server..."
exec "$@"
