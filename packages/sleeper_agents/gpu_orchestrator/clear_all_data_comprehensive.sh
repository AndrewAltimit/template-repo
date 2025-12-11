#!/bin/bash
# COMPREHENSIVE Data Cleanup for Sleeper Agents
# Clears BOTH GPU Orchestrator AND Dashboard data
# This is the COMPLETE solution that removes EVERYTHING

set -e

echo "========================================="
echo "Sleeper Agents - COMPREHENSIVE Cleanup"
echo "GPU Orchestrator + Dashboard"
echo "========================================="
echo ""
echo "WARNING: This will DELETE ALL:"
echo ""
echo "GPU ORCHESTRATOR:"
echo "  - orchestrator.db, users.db"
echo "  - Docker volumes (sleeper-results, sleeper-models, sleeper-gpu-cache)"
echo "  - Logs and caches"
echo ""
echo "DASHBOARD:"
echo "  - sleeper-dashboard container"
echo "  - dashboard/auth/users.db (user accounts)"
echo "  - dashboard/data/* (local data including users.db)"
echo "  - evaluation_results.db (in sleeper-results volume)"
echo ""
echo "MODEL DATA:"
echo "  - Model checkpoints"
echo "  - Training results (results/, outputs/)"
echo "  - HuggingFace cache (optional)"
echo ""
read -rp "Are you ABSOLUTELY SURE? Type 'DELETE EVERYTHING' to proceed: " CONFIRM
if [[ "$CONFIRM" != "DELETE EVERYTHING" ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Starting comprehensive cleanup..."
echo ""

# Navigate to package root (one level up from gpu_orchestrator)
cd "$(dirname "$0")"
cd ..

# Detect container runtime (podman or docker)
CONTAINER_CMD=""
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    echo "Using podman as container runtime"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    echo "Using docker as container runtime"
else
    echo "WARNING: Neither podman nor docker found. Skipping container operations."
fi

# ========================================
# 1. Stop ALL containers
# ========================================
echo "[1/12] Stopping ALL containers..."

if [[ -n "$CONTAINER_CMD" ]]; then
    # Stop dashboard
    if $CONTAINER_CMD stop sleeper-dashboard 2>/dev/null; then
        echo "  - Stopped sleeper-dashboard"
        $CONTAINER_CMD rm sleeper-dashboard 2>/dev/null || true
        echo "  - Removed sleeper-dashboard container"
    fi

    # Stop GPU orchestrator
    $CONTAINER_CMD stop sleeper-gpu-worker 2>/dev/null || true
    $CONTAINER_CMD stop sleeper-orchestrator-api 2>/dev/null || true
    $CONTAINER_CMD stop sleeper-eval-gpu 2>/dev/null || true
    $CONTAINER_CMD stop sleeper-validate 2>/dev/null || true
    $CONTAINER_CMD stop sleeper-evaluate 2>/dev/null || true

    # Stop any other sleeper containers
    for container in $($CONTAINER_CMD ps -a --filter "name=sleeper" --format "{{.Names}}" 2>/dev/null); do
        echo "  - Stopping $container"
        $CONTAINER_CMD stop "$container" 2>/dev/null || true
        $CONTAINER_CMD rm "$container" 2>/dev/null || true
    done

    echo "All containers stopped."
else
    echo "Skipped (no container runtime)"
fi
echo ""

# ========================================
# 2. Remove Docker volumes
# ========================================
echo "[2/12] Removing Docker volumes..."
echo "  This is where evaluation_results.db lives!"

if [[ -n "$CONTAINER_CMD" ]]; then
    # Remove named volumes
    if $CONTAINER_CMD volume rm sleeper-results 2>/dev/null; then
        echo "  [OK] Removed sleeper-results (contains /results/evaluation_results.db)"
    else
        echo "  [!] sleeper-results not found or already removed"
    fi

    if $CONTAINER_CMD volume rm sleeper-models 2>/dev/null; then
        echo "  [OK] Removed sleeper-models"
    else
        echo "  [!] sleeper-models not found"
    fi

    if $CONTAINER_CMD volume rm sleeper-gpu-cache 2>/dev/null; then
        echo "  [OK] Removed sleeper-gpu-cache"
    else
        echo "  [!] sleeper-gpu-cache not found"
    fi

    # Remove any other sleeper volumes
    for vol in $($CONTAINER_CMD volume ls -q 2>/dev/null | grep sleeper || true); do
        if $CONTAINER_CMD volume rm "$vol" 2>/dev/null; then
            echo "  [OK] Removed additional volume: $vol"
        fi
    done

    echo "Docker volumes removed."
else
    echo "Skipped (no container runtime)"
fi
echo ""

# ========================================
# 3. Dashboard auth database (NOT the source code!)
# ========================================
echo "[3/12] Removing Dashboard auth database..."

# Only delete the users.db file, NOT the entire auth directory
# The auth directory contains source code (authentication.py, __init__.py)
if [[ -f "dashboard/auth/users.db" ]]; then
    rm -f "dashboard/auth/users.db"
    echo "  [OK] Deleted dashboard/auth/users.db"
else
    echo "  [!] dashboard/auth/users.db not found"
fi

# Also check data directory for auth database (new location)
if [[ -f "dashboard/data/users.db" ]]; then
    rm -f "dashboard/data/users.db"
    echo "  [OK] Deleted dashboard/data/users.db"
else
    echo "  [!] dashboard/data/users.db not found"
fi
echo ""

# ========================================
# 4. Dashboard data directory
# ========================================
echo "[4/12] Removing Dashboard data directory..."

if [[ -d "dashboard/data" ]]; then
    echo "  Found: dashboard/data"
    if [[ -n "$(ls -A dashboard/data 2>/dev/null)" ]]; then
        echo "  Files in data:"
        ls -la dashboard/data/
        rm -rf "dashboard/data"
        echo "  [OK] Deleted dashboard/data/"
    else
        echo "  [!] Data directory empty"
    fi
else
    echo "  [!] dashboard/data not found"
fi
echo ""

# ========================================
# 5. GPU Orchestrator databases
# ========================================
echo "[5/12] Removing GPU Orchestrator databases..."

if [[ -f "gpu_orchestrator/users.db" ]]; then
    rm -f "gpu_orchestrator/users.db"
    echo "  [OK] Deleted gpu_orchestrator/users.db"
else
    echo "  [!] gpu_orchestrator/users.db not found"
fi

if [[ -f "gpu_orchestrator/orchestrator.db" ]]; then
    rm -f "gpu_orchestrator/orchestrator.db"
    echo "  [OK] Deleted gpu_orchestrator/orchestrator.db"
else
    echo "  [!] gpu_orchestrator/orchestrator.db not found"
fi
echo ""

# ========================================
# 6. Evaluation databases (local copies)
# ========================================
echo "[6/12] Removing evaluation databases (local copies)..."

if [[ -f "dashboard/evaluation_results.db" ]]; then
    rm -f "dashboard/evaluation_results.db"
    echo "  [OK] Deleted dashboard/evaluation_results.db"
else
    echo "  [!] dashboard/evaluation_results.db not found"
fi

if [[ -f "dashboard/evaluation_results_mock.db" ]]; then
    rm -f "dashboard/evaluation_results_mock.db"
    echo "  [OK] Deleted dashboard/evaluation_results_mock.db"
else
    echo "  [!] evaluation_results_mock.db not found"
fi

if [[ -f "dashboard/tests/test_evaluation_results.db" ]]; then
    rm -f "dashboard/tests/test_evaluation_results.db"
    echo "  [OK] Deleted dashboard/tests/test_evaluation_results.db"
else
    echo "  [!] test database not found"
fi
echo ""

# ========================================
# 7. Results directories
# ========================================
echo "[7/12] Removing results directories..."

if [[ -d "results" ]]; then
    rm -rf "results"
    echo "  [OK] Deleted results/"
else
    echo "  [!] results/ not found"
fi

if [[ -d "outputs" ]]; then
    rm -rf "outputs"
    echo "  [OK] Deleted outputs/"
else
    echo "  [!] outputs/ not found"
fi

# Check for /results (Docker mount point) - requires root
if [[ -d "/results" ]] && [[ -w "/results" ]]; then
    rm -rf "/results"
    echo "  [OK] Deleted /results/ (root)"
fi
echo ""

# ========================================
# 8. Model caches
# ========================================
echo "[8/12] Removing model caches..."

if [[ -d "models" ]]; then
    rm -rf "models"
    echo "  [OK] Deleted models/"
else
    echo "  [!] models/ not found"
fi

if [[ -d "checkpoints" ]]; then
    rm -rf "checkpoints"
    echo "  [OK] Deleted checkpoints/"
else
    echo "  [!] checkpoints/ not found"
fi

# Optional: HuggingFace cache
HF_CACHE="${HOME}/.cache/huggingface"
if [[ -d "$HF_CACHE" ]]; then
    echo "  [?] Found HuggingFace cache: $HF_CACHE"
    read -rp "    Clear HuggingFace cache? (yes/no): " CLEAR_HF
    if [[ "${CLEAR_HF,,}" == "yes" ]]; then
        rm -rf "$HF_CACHE"
        echo "  [OK] Deleted HuggingFace cache"
    else
        echo "  [!] Skipped HuggingFace cache"
    fi
else
    echo "  [!] HuggingFace cache not found"
fi
echo ""

# ========================================
# 9. Logs
# ========================================
echo "[9/12] Removing logs..."

if [[ -d "logs" ]]; then
    rm -rf "logs"
    echo "  [OK] Deleted logs/"
fi

if [[ -d "gpu_orchestrator/logs" ]]; then
    rm -rf "gpu_orchestrator/logs"
    echo "  [OK] Deleted gpu_orchestrator/logs/"
fi

if [[ -d "dashboard/logs" ]]; then
    rm -rf "dashboard/logs"
    echo "  [OK] Deleted dashboard/logs/"
fi

find . -name "*.log" -type f -delete 2>/dev/null || true
echo "All logs removed."
echo ""

# ========================================
# 10. Python cache
# ========================================
echo "[10/12] Removing Python cache..."

find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true
echo "Python cache removed."
echo ""

# ========================================
# 11. Temporary files
# ========================================
echo "[11/12] Removing temporary files..."

if [[ -d "temp" ]]; then
    rm -rf "temp"
    echo "  [OK] Deleted temp/"
fi

if [[ -d "tmp" ]]; then
    rm -rf "tmp"
    echo "  [OK] Deleted tmp/"
fi

if [[ -d "wandb" ]]; then
    rm -rf "wandb"
    echo "  [OK] Deleted wandb/"
fi

if [[ -d ".wandb" ]]; then
    rm -rf ".wandb"
    echo "  [OK] Deleted .wandb/"
fi
echo ""

# ========================================
# 12. Database export backups
# ========================================
echo "[12/12] Removing database export backups..."

if [[ -d "scripts/data/db_exports" ]]; then
    rm -rf "scripts/data/db_exports"
    echo "  [OK] Deleted scripts/data/db_exports/"
else
    echo "  [!] db_exports/ not found"
fi
echo ""

# ========================================
# Summary
# ========================================
echo ""
echo "========================================="
echo "Comprehensive Cleanup Complete!"
echo "========================================="
echo ""
echo "REMOVED:"
echo ""
echo "Docker:"
echo "  [x] All sleeper containers (dashboard, GPU worker, orchestrator)"
echo "  [x] Docker volumes (sleeper-results, sleeper-models, sleeper-gpu-cache)"
echo ""
echo "Databases:"
echo "  [x] evaluation_results.db (in sleeper-results volume - GONE)"
echo "  [x] dashboard/auth/users.db (user accounts)"
echo "  [x] dashboard/data/users.db (user accounts)"
echo "  [x] gpu_orchestrator/users.db"
echo "  [x] gpu_orchestrator/orchestrator.db"
echo ""
echo "Data:"
echo "  [x] results/, outputs/ (validation results)"
echo "  [x] models/, checkpoints/ (model caches)"
echo "  [x] logs/ (all log files)"
echo "  [x] Python cache (__pycache__, .pytest_cache)"
echo "  [x] Temporary files (temp/, tmp/, wandb/)"
echo "  [x] Database backups (db_exports/)"
echo ""
echo "Next Steps:"
echo "  1. cd gpu_orchestrator"
echo "  2. ./start_orchestrator.sh    # Start GPU orchestrator fresh"
echo "  3. cd ../dashboard"
echo "  4. ./start.sh                 # Start dashboard fresh"
echo ""
echo "Everything is now COMPLETELY clean!"
echo ""
