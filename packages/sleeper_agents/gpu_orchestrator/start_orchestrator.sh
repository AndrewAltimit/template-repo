#!/bin/bash
# Start GPU Orchestrator API
# This script should run on Linux/macOS GPU machines
# Supports both Docker and Podman container runtimes

set -e  # Exit on error
set -o pipefail  # Fail on pipeline errors

# Change to script directory - makes all relative paths work consistently
# regardless of where this script is called from
cd "$(dirname "$0")"

echo "========================================="
echo "GPU Orchestrator API Startup"
echo "========================================="
echo ""

# Check prerequisites
echo "[1/5] Checking prerequisites..."

# Detect container runtime (podman or docker)
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

# Check if container runtime is running
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

# Check NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo "WARNING: nvidia-smi not found. GPU may not be available."
fi

# Check Python
if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found. Please install Python 3.8+."
    exit 1
fi

echo "[2/5] Setting up environment..."

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "WARNING: Please edit .env and set your API_KEY!"
fi

# Create virtual environment if it doesn't exist
if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
# shellcheck source=/dev/null
source venv/bin/activate

# Install dependencies
echo "[3/5] Installing dependencies..."
python -m pip install --quiet --upgrade pip
echo "Installing sleeper_agents package..."
# With src/ layout, package root is one level up
cd ..
if ! pip install -e .; then
    echo "ERROR: Failed to install sleeper_agents package"
    echo "Please check that pyproject.toml exists and src/ layout is correct"
    exit 1
fi
cd gpu_orchestrator
echo "Successfully installed sleeper_agents package"
pip install --quiet -r requirements.txt

# Build container image
echo "[4/5] Building GPU worker container image..."
echo "This may take a few minutes on first run (cached afterwards)"
# Note: Build context is now packages/sleeper_agents/ (src/ layout)
if ! $CONTAINER_CMD build -t sleeper-agents:gpu -f ../docker/Dockerfile.gpu ..; then
    echo "ERROR: Failed to build sleeper-agents:gpu image"
    echo "Please check $CONTAINER_CMD is running and Dockerfile exists"
    exit 1
fi
echo "GPU worker image ready."

# Get IP address
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1)
else
    # Linux
    IP=$(hostname -I | awk '{print $1}')
fi

# Start API
echo "[5/5] Starting GPU Orchestrator API..."
echo ""
echo "API will be available at:"
echo "  - Local: http://localhost:8000"
echo "  - Network: http://$IP:8000"
echo "  - Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run with uvicorn
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level info
