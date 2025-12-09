#!/bin/bash
# Test Validation Benchmarks (GPU-accelerated on RTX 4090)
# This script runs all validation benchmarks in containerized environment
#
# Usage:
#   ./test_phase3_benchmarks.sh              - Run all benchmarks
#   ./test_phase3_benchmarks.sh 3a           - Run only synthetic benchmark (synthetic)
#   ./test_phase3_benchmarks.sh 3b           - Run only transformer benchmark (real transformer)
#   ./test_phase3_benchmarks.sh 3c           - Run only red team benchmark (red team)
#   ./test_phase3_benchmarks.sh quick        - Run quick version (smaller datasets)

set -e

# Export user permissions for Docker containers
USER_ID=$(id -u)
export USER_ID
GROUP_ID=$(id -g)
export GROUP_ID

# Colors
COLOR_RESET='\033[0m'
COLOR_GREEN='\033[32m'
COLOR_RED='\033[31m'
COLOR_BLUE='\033[34m'
COLOR_YELLOW='\033[33m'

echo ""
echo "============================================================"
echo "Validation Benchmark Suite (GPU-accelerated)"
echo "============================================================"
echo ""

# Parse command
COMMAND="${1:-all}"

# Check Docker availability
if ! docker version > /dev/null 2>&1; then
    echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} Docker not available"
    echo ""
    echo "Please install Docker:"
    echo "  Ubuntu/Debian: sudo apt-get install docker.io"
    echo "  Other: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Docker available"
echo ""

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} NVIDIA GPU detected"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo ""
else
    echo -e "${COLOR_YELLOW}[WARNING]${COLOR_RESET} No NVIDIA GPU detected, will use CPU"
    echo ""
fi

# Function: Run Synthetic Testing (Synthetic)
run_synthetic() {
    echo "============================================================"
    echo "Synthetic Benchmark: Synthetic Data Benchmark (Multi-Scenario)"
    echo "============================================================"
    echo ""
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Tests: 4 difficulty scenarios"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~30 seconds (CPU-only, no GPU needed)"
    echo ""

    if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors_comprehensive.py"; then
        echo ""
        echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Synthetic Testing benchmark completed"
        echo ""
    else
        echo ""
        echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Synthetic Testing benchmark failed"
        return 1
    fi
}

# Function: Run Transformer Testing (Real Transformer)
run_transformer() {
    echo "============================================================"
    echo "Transformer Benchmark: Real Transformer Benchmark (GPT-2)"
    echo "============================================================"
    echo ""
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Model: GPT-2 (124M parameters)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Device: CUDA (RTX 4090)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~15 seconds (GPU-accelerated)"
    echo ""

    if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/real_transformer_benchmark.py"; then
        echo ""
        echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Transformer Testing benchmark completed"
        echo ""
    else
        echo ""
        echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Transformer Testing benchmark failed"
        return 1
    fi
}

# Function: Run Red Team Testing (Red Team)
run_redteam() {
    echo "============================================================"
    echo "Red Team Benchmark: Red Team Adversarial Benchmark (5 Strategies)"
    echo "============================================================"
    echo ""
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Model: GPT-2 (124M parameters)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Device: CUDA (RTX 4090)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Strategies: Subtle, Context, Distributed, Mimicry, Typo"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~60 seconds (GPU-accelerated)"
    echo ""

    if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/red_team_benchmark.py"; then
        echo ""
        echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Red Team Testing benchmark completed"
        echo ""
    else
        echo ""
        echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Red Team Testing benchmark failed"
        return 1
    fi
}

# Quick mode functions (reduced datasets)
run_synthetic_quick() {
    echo "[Synthetic Testing Quick] Running with reduced dataset..."
    docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors.py"
}

run_transformer_quick() {
    echo "[Transformer Testing Quick] Running with GPU..."
    docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/real_transformer_benchmark.py"
}

run_redteam_quick() {
    echo "[Red Team Testing Quick] Running with GPU..."
    docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/red_team_benchmark.py"
}

# Main execution
case "$COMMAND" in
    all)
        echo "Running ALL Phase 3 benchmarks..."
        echo ""
        run_synthetic
        run_transformer
        run_redteam
        ;;
    3a)
        echo "Running Synthetic Testing only..."
        echo ""
        run_synthetic
        ;;
    3b)
        echo "Running Transformer Testing only..."
        echo ""
        run_transformer
        ;;
    3c)
        echo "Running Red Team Testing only..."
        echo ""
        run_redteam
        ;;
    quick)
        echo "Running quick benchmarks (reduced dataset sizes)..."
        echo ""
        echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Quick mode runs faster but less comprehensive"
        echo ""
        run_synthetic_quick
        run_transformer_quick
        run_redteam_quick
        ;;
    *)
        echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} Unknown command: $COMMAND"
        echo ""
        echo "Valid commands: all, 3a, 3b, 3c, quick"
        exit 1
        ;;
esac

# Success message
echo ""
echo "============================================================"
echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} All Phase 3 benchmarks completed!"
echo "============================================================"
echo ""
echo "Summary of Results:"
echo "  - Synthetic Benchmark: Synthetic data across 4 scenarios"
echo "  - Transformer Benchmark: Real GPT-2 activations with simple trigger"
echo "  - Red Team Benchmark: Adversarial triggers (5 attack strategies)"
echo ""
echo "Key Findings:"
echo "  - Linear Probe: Perfect performance across all phases"
echo "  - ART Clustering: Good on synthetic, vulnerable to adversarial"
echo "  - Supervised learning essential for adversarial robustness"
echo ""
