#!/bin/bash
# Smart Dashboard Starter - Uses podman or docker, auto-detects compose tools
# Automatically loads .env and configures everything

set -e  # Exit on error

echo "========================================="
echo "Sleeper Detection Dashboard Startup"
echo "========================================="
echo ""

# Export user/group IDs for proper file ownership in containers
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# Detect container runtime (podman or docker)
echo "[1/7] Detecting container runtime..."
CONTAINER_CMD=""
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    echo "Found podman: will use podman"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    echo "Found docker: will use docker"
else
    echo "ERROR: Neither podman nor docker found. Please install one of them."
    exit 1
fi

# Check if container runtime is running (for docker)
if [ "$CONTAINER_CMD" = "docker" ]; then
    if ! docker info &> /dev/null; then
        echo "ERROR: Docker daemon not running. Please start Docker."
        exit 1
    fi
    echo "Docker daemon is running."
elif [ "$CONTAINER_CMD" = "podman" ]; then
    # Podman doesn't need a daemon check in most cases
    echo "Podman is ready."
fi
echo ""

# Detect compose tool
echo "[2/7] Detecting compose tool..."
USE_COMPOSE=0
COMPOSE_CMD=""

if [ "$CONTAINER_CMD" = "podman" ]; then
    # Check for podman-compose first
    if command -v podman-compose &> /dev/null; then
        USE_COMPOSE=1
        COMPOSE_CMD="podman-compose"
        echo "Found podman-compose: will use docker-compose.yml"
    # Check for podman compose (v2 syntax)
    elif podman compose version &> /dev/null; then
        USE_COMPOSE=2
        COMPOSE_CMD="podman compose"
        echo "Found podman compose v2: will use docker-compose.yml"
    else
        echo "podman-compose not found: will use podman run"
    fi
elif [ "$CONTAINER_CMD" = "docker" ]; then
    # Check for docker-compose
    if command -v docker-compose &> /dev/null; then
        USE_COMPOSE=1
        COMPOSE_CMD="docker-compose"
        echo "Found docker-compose: will use docker-compose.yml"
    # Check for docker compose (v2 syntax)
    elif docker compose version &> /dev/null; then
        USE_COMPOSE=2
        COMPOSE_CMD="docker compose"
        echo "Found docker compose v2: will use docker-compose.yml"
    else
        echo "docker-compose not found: will use docker run"
    fi
fi
echo ""

# Check configuration
echo "[3/7] Checking configuration..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo ""
        echo "IMPORTANT: Please edit .env and configure:"
        echo "  - GPU_API_URL=http://your-gpu-machine-ip:8000"
        echo "  - GPU_API_KEY=your-api-key"
        echo "  - DASHBOARD_ADMIN_PASSWORD=your-password"
        echo ""
        read -r -p "Press Enter to continue after editing .env..."
    else
        echo "ERROR: No .env or .env.example found"
        exit 1
    fi
fi

# Create data directories for volume mounts
mkdir -p auth
mkdir -p data

echo "Configuration file found: .env"
echo "Note: compose will load environment variables from .env"
echo ""

# Ensure required volumes exist (for docker/podman)
echo "[4/7] Checking volumes..."
if $CONTAINER_CMD volume inspect sleeper-results &> /dev/null; then
    echo "Volume sleeper-results already exists"
else
    echo "Creating sleeper-results volume..."
    if ! $CONTAINER_CMD volume create sleeper-results; then
        echo "ERROR: Failed to create sleeper-results volume"
        exit 1
    fi
    echo "Created sleeper-results volume"
fi
echo ""

# Build image
echo "[5/7] Building image..."
if [ $USE_COMPOSE -gt 0 ]; then
    echo "Building with $COMPOSE_CMD..."
    if ! $COMPOSE_CMD build; then
        echo "ERROR: Failed to build image"
        exit 1
    fi
else
    echo "Building with $CONTAINER_CMD..."
    if ! $CONTAINER_CMD build -t sleeper-dashboard:latest .; then
        echo "ERROR: Failed to build image"
        exit 1
    fi
fi
echo ""

# Stop existing container/service
echo "[6/7] Stopping existing dashboard..."
if [ $USE_COMPOSE -gt 0 ]; then
    $COMPOSE_CMD down &> /dev/null || true
else
    $CONTAINER_CMD stop sleeper-dashboard &> /dev/null || true
    $CONTAINER_CMD rm sleeper-dashboard &> /dev/null || true
fi
echo ""

# Start dashboard
echo "[7/7] Starting dashboard..."
echo ""

if [ $USE_COMPOSE -gt 0 ]; then
    echo "Using $COMPOSE_CMD..."
    if ! $COMPOSE_CMD up -d; then
        echo ""
        echo "ERROR: Failed to start dashboard"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check if port 8501 is in use: ss -tlnp | grep :8501"
        echo "  2. View logs: $CONTAINER_CMD logs sleeper-dashboard"
        echo "  3. Check .env configuration"
        echo "  4. Verify GPU Orchestrator API is accessible"
        exit 1
    fi
else
    echo "Using $CONTAINER_CMD run..."
    echo "Note: Loading environment variables from .env for $CONTAINER_CMD run..."
    if ! $CONTAINER_CMD run -d \
      --user "$USER_ID:$GROUP_ID" \
      --name sleeper-dashboard \
      -p 8501:8501 \
      --env-file .env \
      -v sleeper-results:/results:rw \
      -v ./auth:/home/dashboard/app/auth \
      -v ./data:/home/dashboard/app/data \
      sleeper-dashboard:latest; then
        echo ""
        echo "ERROR: Failed to start dashboard"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check if port 8501 is in use: ss -tlnp | grep :8501"
        echo "  2. View logs: $CONTAINER_CMD logs sleeper-dashboard"
        echo "  3. Check .env configuration"
        echo "  4. Verify GPU Orchestrator API is accessible"
        exit 1
    fi
fi

# Wait for startup with polling
echo "Waiting for container to be ready..."
for i in {1..30}; do
    if $CONTAINER_CMD ps --filter "name=sleeper-dashboard" --format "{{.Names}}" | grep -q "^sleeper-dashboard$"; then
        echo "Container is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Container failed to become ready within 60 seconds."
        echo ""
        echo "Recent container logs:"
        $CONTAINER_CMD logs --tail 30 sleeper-dashboard 2>&1 || echo "Could not retrieve logs"
        exit 1
    fi
    sleep 2
done

echo ""
echo "========================================="
echo "Dashboard Started Successfully!"
echo "========================================="
echo ""
echo "Access the dashboard at:"
echo "  - Local: http://localhost:8501"
echo ""
echo "Login:"
echo "  - Username: admin"
echo "  - Password: (from .env DASHBOARD_ADMIN_PASSWORD)"
echo ""
echo "GPU Orchestrator: (configured in .env GPU_API_URL)"
echo ""
echo "Management:"
echo "  - View logs: $CONTAINER_CMD logs -f sleeper-dashboard"
echo "  - Stop: $CONTAINER_CMD stop sleeper-dashboard"
if [ $USE_COMPOSE -gt 0 ]; then
    echo "  - Or use: $COMPOSE_CMD down"
fi
echo ""
echo "Opening browser in 3 seconds..."
sleep 3

# Try to open browser (Linux)
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8501 &> /dev/null &
elif command -v gnome-open &> /dev/null; then
    gnome-open http://localhost:8501 &> /dev/null &
fi

echo ""
echo "Dashboard is running. Press Ctrl+C to stop following logs."
echo ""

# Follow logs
$CONTAINER_CMD logs -f sleeper-dashboard
