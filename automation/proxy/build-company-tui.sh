#!/bin/bash
# Build script for Company OpenCode with working TUI

set -e

echo "============================================"
echo "Building Company OpenCode with TUI Support"
echo "============================================"

# Build the Docker image
echo "Building Docker image..."
docker build -f docker/opencode-company-tui-working.Dockerfile -t opencode-company-tui:latest .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "Image tagged as: opencode-company-tui:latest"
    echo ""
    echo "To run the container:"
    echo "  ./automation/proxy/run-company-tui.sh"
    echo ""
else
    echo ""
    echo "❌ Build failed!"
    exit 1
fi
