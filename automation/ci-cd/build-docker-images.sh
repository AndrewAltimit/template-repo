#!/bin/bash
# Build Docker images in correct dependency order for CI/CD
# This ensures base images exist before building dependent images

set -e

echo "🐳 Building Docker images in dependency order..."

# Build OpenCode and Crush first (these are base images for openrouter-agents)
echo "📦 Building base images (OpenCode and Crush)..."
docker-compose -f docker-compose.build.yml build mcp-opencode mcp-crush

# Build all remaining images (including openrouter-agents)
# Docker Compose will now correctly build openrouter-agents as its dependencies are cached
echo "🏗️ Building all remaining images..."
docker-compose -f docker-compose.build.yml build

echo "✅ All images built successfully"

# List built images for verification
echo "Built images:"
docker images | grep -E "(template-repo|ghcr.io/andrewaltimit/template-repo)" | head -20
