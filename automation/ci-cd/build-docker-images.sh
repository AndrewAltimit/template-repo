#!/bin/bash
# Build Docker images in correct dependency order for CI/CD
# This ensures base images exist before building dependent images

set -e

echo "🐳 Building Docker images in dependency order..."

# Build OpenCode and Crush first (these are base images for openrouter-agents)
echo "📦 Building base images (OpenCode and Crush)..."
docker-compose -f docker-compose.build.yml build mcp-opencode mcp-crush

# Build OpenRouter Agents (depends on OpenCode and Crush)
echo "🤖 Building OpenRouter Agents image..."
docker-compose -f docker-compose.build.yml build openrouter-agents

# Build all other images in parallel (they don't have local dependencies)
echo "🏗️ Building remaining images..."
docker-compose -f docker-compose.build.yml build \
  mcp-code-quality \
  mcp-content-creation \
  mcp-gaea2 \
  mcp-http-bridge \
  python-ci \
  mcp-blender \
  mcp-meme-generator \
  mcp-elevenlabs-speech

echo "✅ All images built successfully"

# List built images for verification
echo "Built images:"
docker images | grep -E "(template-repo|ghcr.io/andrewaltimit/template-repo)" | head -20
