#!/bin/bash
# Comprehensive Data Cleanup Script for Sleeper Agents GPU Orchestrator
# This script removes ALL data including evaluation results, models, logs, and databases
# WARNING: This is irreversible! Make backups if needed.

set -e

echo "========================================="
echo "Sleeper Agents - Complete Data Cleanup"
echo "========================================="
echo ""
echo "WARNING: This will DELETE ALL:"
echo "- Evaluation databases (evaluation_results.db, users.db, orchestrator.db)"
echo "- Model checkpoints and caches"
echo "- Validation results (outputs/, results/)"
echo "- Training checkpoints"
echo "- Logs and temporary files"
echo "- Docker volumes"
echo ""
read -rp "Are you sure you want to proceed? (yes/no): " CONFIRM
if [[ "${CONFIRM,,}" != "yes" ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Navigate to package root (one level up from gpu_orchestrator)
cd "$(dirname "$0")"
cd ..

# Detect container runtime (podman or docker)
CONTAINER_CMD=""
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
else
    echo "WARNING: Neither podman nor docker found. Skipping container operations."
fi

# ========================================
# 1. Stop all Docker containers
# ========================================
echo "[1/10] Stopping containers..."
if [[ -n "$CONTAINER_CMD" ]]; then
    $CONTAINER_CMD stop sleeper-gpu-worker 2>/dev/null || true
    $CONTAINER_CMD stop sleeper-orchestrator-api 2>/dev/null || true
    echo "Containers stopped."
else
    echo "Skipped (no container runtime)"
fi

# ========================================
# 2. Remove Docker volumes
# ========================================
echo "[2/10] Removing Docker volumes..."
echo "  This is where evaluation_results.db actually lives!"

if [[ -n "$CONTAINER_CMD" ]]; then
    # Remove specific named volumes (from docker-compose.gpu.yml)
    if $CONTAINER_CMD volume rm sleeper-results 2>/dev/null; then
        echo "  - Removed sleeper-results volume (contains /results/evaluation_results.db)"
    else
        echo "  - sleeper-results volume not found or already removed"
    fi

    if $CONTAINER_CMD volume rm sleeper-models 2>/dev/null; then
        echo "  - Removed sleeper-models volume (contains model cache)"
    else
        echo "  - sleeper-models volume not found or already removed"
    fi

    if $CONTAINER_CMD volume rm sleeper-gpu-cache 2>/dev/null; then
        echo "  - Removed sleeper-gpu-cache volume"
    else
        echo "  - sleeper-gpu-cache volume not found or already removed"
    fi

    # Remove any other sleeper-related volumes
    for vol in $($CONTAINER_CMD volume ls -q 2>/dev/null | grep sleeper || true); do
        if $CONTAINER_CMD volume rm "$vol" 2>/dev/null; then
            echo "  - Removed additional volume: $vol"
        fi
    done

    echo "Docker volumes removed."
else
    echo "Skipped (no container runtime)"
fi

# ========================================
# 3. Remove evaluation databases
# ========================================
echo "[3/10] Removing evaluation databases..."

# Main evaluation database (dashboard)
if [[ -f "dashboard/evaluation_results.db" ]]; then
    rm -f "dashboard/evaluation_results.db"
    echo "  - Deleted dashboard/evaluation_results.db"
fi

# Mock database
if [[ -f "dashboard/evaluation_results_mock.db" ]]; then
    rm -f "dashboard/evaluation_results_mock.db"
    echo "  - Deleted dashboard/evaluation_results_mock.db"
fi

# Test database
if [[ -f "dashboard/tests/test_evaluation_results.db" ]]; then
    rm -f "dashboard/tests/test_evaluation_results.db"
    echo "  - Deleted dashboard/tests/test_evaluation_results.db"
fi

# Orchestrator databases
if [[ -f "gpu_orchestrator/users.db" ]]; then
    rm -f "gpu_orchestrator/users.db"
    echo "  - Deleted gpu_orchestrator/users.db"
fi

if [[ -f "gpu_orchestrator/orchestrator.db" ]]; then
    rm -f "gpu_orchestrator/orchestrator.db"
    echo "  - Deleted gpu_orchestrator/orchestrator.db"
fi

echo "Databases removed."

# ========================================
# 4. Remove results directory
# ========================================
echo "[4/10] Removing results directory..."
if [[ -d "results" ]]; then
    rm -rf "results"
    echo "  - Deleted results/"
fi

# Also check for /results (Docker mount point) - requires root
if [[ -d "/results" ]] && [[ -w "/results" ]]; then
    rm -rf "/results"
    echo "  - Deleted /results/"
fi

# ========================================
# 5. Remove outputs directory
# ========================================
echo "[5/10] Removing outputs directory..."
if [[ -d "outputs" ]]; then
    rm -rf "outputs"
    echo "  - Deleted outputs/"
fi

# ========================================
# 6. Remove model caches
# ========================================
echo "[6/10] Removing model caches..."
if [[ -d "models" ]]; then
    rm -rf "models"
    echo "  - Deleted models/"
fi

# HuggingFace cache (in user directory)
HF_CACHE="${HOME}/.cache/huggingface"
if [[ -d "$HF_CACHE" ]]; then
    echo "  - Found HuggingFace cache: $HF_CACHE"
    read -rp "    Clear HuggingFace cache? (yes/no): " CLEAR_HF
    if [[ "${CLEAR_HF,,}" == "yes" ]]; then
        rm -rf "$HF_CACHE"
        echo "  - Deleted HuggingFace cache"
    fi
fi

# ========================================
# 7. Remove training checkpoints
# ========================================
echo "[7/10] Removing training checkpoints..."
if [[ -d "checkpoints" ]]; then
    rm -rf "checkpoints"
    echo "  - Deleted checkpoints/"
fi

# ========================================
# 8. Remove logs
# ========================================
echo "[8/10] Removing logs..."
if [[ -d "logs" ]]; then
    rm -rf "logs"
    echo "  - Deleted logs/"
fi

if [[ -d "gpu_orchestrator/logs" ]]; then
    rm -rf "gpu_orchestrator/logs"
    echo "  - Deleted gpu_orchestrator/logs/"
fi

# Remove any .log files
find . -name "*.log" -type f -delete 2>/dev/null || true

# ========================================
# 9. Remove Python cache
# ========================================
echo "[9/10] Removing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true
echo "Python cache removed."

# ========================================
# 10. Remove temporary files
# ========================================
echo "[10/10] Removing temporary files..."
if [[ -d "temp" ]]; then
    rm -rf "temp"
    echo "  - Deleted temp/"
fi

if [[ -d "tmp" ]]; then
    rm -rf "tmp"
    echo "  - Deleted tmp/"
fi

# Remove wandb artifacts (experiment tracking)
if [[ -d "wandb" ]]; then
    rm -rf "wandb"
    echo "  - Deleted wandb/"
fi

if [[ -d ".wandb" ]]; then
    rm -rf ".wandb"
    echo "  - Deleted .wandb/"
fi

# ========================================
# Summary
# ========================================
echo ""
echo "========================================="
echo "Cleanup Complete!"
echo "========================================="
echo ""
echo "All data has been removed. The following were cleaned:"
echo "  [x] Evaluation databases (evaluation_results.db, users.db, orchestrator.db)"
echo "  [x] Docker volumes (sleeper-results, sleeper-models, sleeper-logs)"
echo "  [x] Results directory (results/, outputs/)"
echo "  [x] Model caches (models/, checkpoints/)"
echo "  [x] Logs (logs/, *.log)"
echo "  [x] Python cache (__pycache__, .pytest_cache, .mypy_cache)"
echo "  [x] Temporary files (temp/, tmp/, wandb/)"
echo ""
echo "You can now run ./start_orchestrator.sh to start fresh."
echo ""
