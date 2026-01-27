#!/bin/bash
# run_codex_container.sh - Run Codex CLI in Docker container

set -e

echo "🐳 Starting Codex CLI in Container"

# Check if required Docker images exist, build if not
check_and_build_images() {
    local images_missing=false

    # Check for codex-agent image
    if ! docker images | grep -q "template-repo-codex-agent"; then
        echo "📦 Codex agent image not found, building..."
        images_missing=true
    fi

    # Build missing images
    if [ "$images_missing" = true ]; then
        echo "🔨 Building required Docker images..."
        echo "This may take a few minutes on first run..."

        # Build the codex-agent image
        echo "Building Codex agent image..."
        docker compose build codex-agent

        echo "✅ Docker images built successfully!"
        echo ""
    fi
}

# Build images if needed
check_and_build_images

# Check for auth file on host
AUTH_DIR="$HOME/.codex"
AUTH_FILE="$AUTH_DIR/auth.json"

if [ ! -f "$AUTH_FILE" ]; then
    echo "⚠️  Codex authentication not found at $AUTH_FILE"
    echo ""
    echo "Please authenticate with Codex on your host machine first:"
    echo "   codex auth"
    echo ""
    echo "This will create the auth.json file that the container needs."
    exit 1
fi

echo "✅ Found Codex auth file: $AUTH_FILE"
echo "   This will be mounted into the container"

# Check for help flag specifically
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    echo "Usage: $0 [codex-options]"
    echo ""
    echo "Description:"
    echo "  Start a Codex session in a container"
    echo "  Automatically mounts your ~/.codex auth directory"
    echo "  All arguments are passed directly to the codex command"
    echo ""
    echo "Examples:"
    echo "  $0                        # Interactive mode"
    echo "  $0 --full-auto            # Auto-approve with sandbox"
    echo "  $0 exec -q 'Write code'   # Execute a query"
    echo ""
    echo "Note: Requires Codex authentication on host machine first (codex auth)"
    exit 0
fi

# Start session (interactive or with arguments)
if [ $# -eq 0 ]; then
    echo "🔄 Starting interactive session in container..."
    echo "💡 Tips:"
    echo "   - Use 'help' to see available commands"
    echo "   - Use 'exit' or Ctrl+C to quit"
    echo ""
else
    echo "🔄 Running Codex in container with arguments: $*"
    echo ""
fi

# Start session in container, forwarding all arguments
# The volume mount and HOME are configured in docker-compose.yml
docker compose run --rm -it codex-agent codex "$@"
