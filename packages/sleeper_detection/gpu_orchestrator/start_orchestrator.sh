#!/bin/bash
# Start GPU Orchestrator API
# This script should run on Linux/macOS GPU machines

set -e  # Exit on error

echo "========================================="
echo "GPU Orchestrator API Startup"
echo "========================================="
echo ""

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
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo "WARNING: nvidia-smi not found. GPU may not be available."
fi

# Check Python
if ! command -v python3 &> /dev/null; then
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
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
# shellcheck source=/dev/null
source venv/bin/activate

# Install dependencies
echo "[3/5] Installing dependencies..."
python -m pip install --quiet --upgrade pip
echo "Installing sleeper_detection package..."
if ! pip install -e ..; then
    echo "ERROR: Failed to install sleeper_detection package"
    echo "Please check that pyproject.toml exists in parent directory"
    exit 1
fi
echo "Successfully installed sleeper_detection package"
pip install --quiet -r requirements.txt

# Build Docker image
echo "[4/5] Building GPU worker Docker image..."
echo "This may take a few minutes on first run (cached afterwards)"
if ! docker build -t sleeper-detection:gpu -f ../docker/Dockerfile.gpu ..; then
    echo "ERROR: Failed to build sleeper-detection:gpu image"
    echo "Please check Docker is running and Dockerfile exists"
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
