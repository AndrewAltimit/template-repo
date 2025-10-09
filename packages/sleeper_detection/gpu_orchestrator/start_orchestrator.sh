#!/bin/bash
# Start GPU Orchestrator API
# This script should run on the Windows GPU machine

set -e

echo "========================================="
echo "GPU Orchestrator API Startup"
echo "========================================="

# Check prerequisites
echo "[1/5] Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker."
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon not running. Please start Docker."
    exit 1
fi

# Check NVIDIA GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "WARNING: nvidia-smi not found. GPU may not be available."
else
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.8+."
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
    python3 -m venv venv
fi

# Activate virtual environment
# shellcheck disable=SC1091
source venv/bin/activate

# Install dependencies
echo "[3/5] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Check Docker image
echo "[4/5] Checking Docker image..."
if ! docker image inspect sleeper-detection:gpu &> /dev/null; then
    echo "WARNING: sleeper-detection:gpu image not found."
    echo "Building image from ../docker/Dockerfile.gpu..."

    # Build image
    docker build -t sleeper-detection:gpu -f ../docker/Dockerfile.gpu ..
fi

# Start API
echo "[5/5] Starting GPU Orchestrator API..."
echo ""
echo "API will be available at:"
echo "  - Local: http://localhost:8000"
echo "  - Network: http://$(hostname -I | awk '{print $1}'):8000"
echo "  - Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run with uvicorn
python3 -m uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log
