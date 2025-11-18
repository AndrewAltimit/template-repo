#!/bin/bash
# Test Phase 1 ART Integration Foundation (CPU-only, containerized)
# This script runs unit tests for BaseDetector, DetectorRegistry, and ExperimentLogger
#
# Usage:
#   ./test_phase1_foundation.sh              - Run all Phase 1 tests
#   ./test_phase1_foundation.sh coverage     - Run with coverage report
#   ./test_phase1_foundation.sh verbose      - Run with verbose output
#   ./test_phase1_foundation.sh quick        - Run without pytest options

set -e

# Colors
COLOR_RESET='\033[0m'
COLOR_GREEN='\033[32m'
COLOR_RED='\033[31m'
COLOR_BLUE='\033[34m'

echo ""
echo "============================================================"
echo "Phase 1 Foundation Tests (CPU-only, containerized)"
echo "============================================================"
echo ""

# Parse command
COMMAND="${1:-default}"

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

# Determine pytest command based on input
case "$COMMAND" in
    coverage)
        echo "Running tests with coverage report..."
        PYTEST_CMD="pytest packages/sleeper_agents/tests/test_base_detector.py packages/sleeper_agents/tests/test_detector_registry.py packages/sleeper_agents/tests/test_experiment_logger.py -v --cov=sleeper_agents.detection --cov=sleeper_agents.evaluation --cov-report=term --cov-report=html"
        ;;
    verbose)
        echo "Running tests with verbose output..."
        PYTEST_CMD="pytest packages/sleeper_agents/tests/test_base_detector.py packages/sleeper_agents/tests/test_detector_registry.py packages/sleeper_agents/tests/test_experiment_logger.py -vv"
        ;;
    quick)
        echo "Running tests (quick mode)..."
        PYTEST_CMD="pytest packages/sleeper_agents/tests/test_base_detector.py packages/sleeper_agents/tests/test_detector_registry.py packages/sleeper_agents/tests/test_experiment_logger.py"
        ;;
    *)
        echo "Running tests (default mode)..."
        PYTEST_CMD="pytest packages/sleeper_agents/tests/test_base_detector.py packages/sleeper_agents/tests/test_detector_registry.py packages/sleeper_agents/tests/test_experiment_logger.py -v"
        ;;
esac

echo ""
echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Container: sleeper-agents-python-ci"
echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Tests: BaseDetector, DetectorRegistry, ExperimentLogger"
echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} Runtime: ~4 seconds (CPU-only)"
echo ""

# Run tests in container (install package first, then run tests)
if docker-compose run --rm python-ci bash -c "pip install -e packages/sleeper_agents && $PYTEST_CMD"; then
    echo ""
    echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} All tests passed"
    echo ""

    if [ "$COMMAND" = "coverage" ]; then
        echo "Coverage report saved to htmlcov/index.html"
        echo ""
    fi
else
    echo ""
    echo -e "${COLOR_RED}[FAILED]${COLOR_RESET} Some tests failed"
    exit 1
fi
