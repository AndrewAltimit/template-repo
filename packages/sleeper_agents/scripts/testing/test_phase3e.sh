#!/bin/bash
# Phase 3E Gradient Attack Audit Test Script (Linux/Mac)

set -e  # Exit on error

# Default configuration
MODE="quick"
DEVICE="cpu"
EPSILON="0.1"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            MODE="full"
            shift
            ;;
        --gpu)
            DEVICE="cuda"
            shift
            ;;
        --epsilon)
            EPSILON="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--full] [--gpu] [--epsilon VALUE]"
            exit 1
            ;;
    esac
done

# Navigate to repo root (script is in packages/sleeper_agents/scripts/testing/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/../../../.."

echo "============================================================"
echo "Phase 3E: Gradient Attack Audit"
echo "============================================================"
echo "Configuration:"
echo "  Mode: $MODE"
echo "  Device: $DEVICE"
echo "  Epsilon: $EPSILON"
echo "============================================================"
echo ""

# Run test based on mode
if [ "$MODE" = "quick" ]; then
    echo "Running QUICK audit (50 samples, recommended)..."
    echo "Installing dependencies and running audit..."
    echo ""
    if docker-compose run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] adversarial-robustness-toolbox --quiet && python packages/sleeper_agents/examples/phase3e_gradient_attack_audit.py --quick --device $DEVICE --epsilon $EPSILON"; then
        echo ""
        echo "============================================================"
        echo "Audit completed successfully!"
        echo "Results saved to: outputs/phase3e_audit/"
        echo "============================================================"
    else
        EXIT_CODE=$?
        echo ""
        echo "============================================================"
        echo "Audit failed with error code: $EXIT_CODE"
        echo "============================================================"
        exit "$EXIT_CODE"
    fi
else
    echo "Running FULL audit (100 samples)..."
    echo "Installing dependencies and running audit..."
    echo ""
    if docker-compose run --rm python-ci bash -c "pip install -e ./packages/sleeper_agents[evaluation] adversarial-robustness-toolbox --quiet && python packages/sleeper_agents/examples/phase3e_gradient_attack_audit.py --n-samples 100 --device $DEVICE --epsilon $EPSILON"; then
        echo ""
        echo "============================================================"
        echo "Audit completed successfully!"
        echo "Results saved to: outputs/phase3e_audit/"
        echo "============================================================"
    else
        EXIT_CODE=$?
        echo ""
        echo "============================================================"
        echo "Audit failed with error code: $EXIT_CODE"
        echo "============================================================"
        exit "$EXIT_CODE"
    fi
fi
