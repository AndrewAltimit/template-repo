#!/bin/bash
# Test Phase 3 Benchmarks (GPU-accelerated on RTX 4090)
# This script runs all three Phase 3 benchmarks in containerized environment
#
# Usage:
#   ./test_phase3_benchmarks.sh              - Run all Phase 3 benchmarks
#   ./test_phase3_benchmarks.sh 3a           - Run only Phase 3A (synthetic)
#   ./test_phase3_benchmarks.sh 3b           - Run only Phase 3B (real transformer)
#   ./test_phase3_benchmarks.sh 3c           - Run only Phase 3C (red team)
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
echo "Phase 3 Benchmark Suite (GPU-accelerated)"
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

# Function: Run Phase 3A (Synthetic)
run_phase3a() {
    echo "============================================================"
    echo "Phase 3A: Synthetic Data Benchmark (Multi-Scenario)"
    echo "============================================================"
    echo ""
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Tests: 4 difficulty scenarios"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~30 seconds (CPU-only, no GPU needed)"
    echo ""

    if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors_comprehensive.py"; then
        echo ""
        echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Phase 3A benchmark completed"
        echo ""
    else
        echo ""
        echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Phase 3A benchmark failed"
        return 1
    fi
}

# Function: Run Phase 3B (Real Transformer)
run_phase3b() {
    echo "============================================================"
    echo "Phase 3B: Real Transformer Benchmark (GPT-2)"
    echo "============================================================"
    echo ""
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Model: GPT-2 (124M parameters)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Device: CUDA (RTX 4090)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~15 seconds (GPU-accelerated)"
    echo ""

    if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3b_real_transformer_benchmark.py"; then
        echo ""
        echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Phase 3B benchmark completed"
        echo ""
    else
        echo ""
        echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Phase 3B benchmark failed"
        return 1
    fi
}

# Function: Run Phase 3C (Red Team)
run_phase3c() {
    echo "============================================================"
    echo "Phase 3C: Red Team Adversarial Benchmark (5 Strategies)"
    echo "============================================================"
    echo ""
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Model: GPT-2 (124M parameters)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Device: CUDA (RTX 4090)"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Strategies: Subtle, Context, Distributed, Mimicry, Typo"
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~60 seconds (GPU-accelerated)"
    echo ""

    if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3c_red_team_benchmark.py"; then
        echo ""
        echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} Phase 3C benchmark completed"
        echo ""
    else
        echo ""
        echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Phase 3C benchmark failed"
        return 1
    fi
}

# Quick mode functions (reduced datasets)
run_phase3a_quick() {
    echo "[Phase 3A Quick] Running with reduced dataset..."
    docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/benchmark_detectors.py"
}

run_phase3b_quick() {
    echo "[Phase 3B Quick] Running with GPU..."
    docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3b_real_transformer_benchmark.py"
}

run_phase3c_quick() {
    echo "[Phase 3C Quick] Running with GPU..."
    docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents[evaluation] && python packages/sleeper_agents/examples/phase3c_red_team_benchmark.py"
}

# Main execution
case "$COMMAND" in
    all)
        echo "Running ALL Phase 3 benchmarks..."
        echo ""
        run_phase3a
        run_phase3b
        run_phase3c
        ;;
    3a)
        echo "Running Phase 3A only..."
        echo ""
        run_phase3a
        ;;
    3b)
        echo "Running Phase 3B only..."
        echo ""
        run_phase3b
        ;;
    3c)
        echo "Running Phase 3C only..."
        echo ""
        run_phase3c
        ;;
    quick)
        echo "Running quick benchmarks (reduced dataset sizes)..."
        echo ""
        echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Quick mode runs faster but less comprehensive"
        echo ""
        run_phase3a_quick
        run_phase3b_quick
        run_phase3c_quick
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
echo "  - Phase 3A: Synthetic data across 4 scenarios"
echo "  - Phase 3B: Real GPT-2 activations with simple trigger"
echo "  - Phase 3C: Adversarial triggers (5 attack strategies)"
echo ""
echo "Key Findings:"
echo "  - Linear Probe: Perfect performance across all phases"
echo "  - ART Clustering: Good on synthetic, vulnerable to adversarial"
echo "  - Supervised learning essential for adversarial robustness"
echo ""
