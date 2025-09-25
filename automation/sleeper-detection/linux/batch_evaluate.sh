#!/bin/bash
# Linux Batch Evaluation Script for Multiple Models
# Automates evaluation of multiple models with comprehensive reporting

set -e

# Color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Default values
CONFIG=""
MODELS=("gpt2" "distilgpt2" "gpt2-medium")
SUITES=("basic" "code_vulnerability" "robustness" "chain_of_thought")
USE_GPU=false
COMPARE_RESULTS=false
OUTPUT_DIR="batch_evaluation_results"
OPEN_REPORT=false
USE_DOCKER=false
CONTINUE_ON_ERROR=false

# Script paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
START_TIME=$(date +%s)

# Print functions
print_success() { echo -e "${GREEN}$1${NC}"; }
print_info() { echo -e "${CYAN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}$1${NC}"; }
print_error() { echo -e "${RED}$1${NC}"; }
print_progress() { echo -e "${MAGENTA}$1${NC}"; }

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  -c, --config FILE       JSON config file or comma-separated model list
  -m, --models MODELS     Models to evaluate (space-separated)
  -s, --suites SUITES     Test suites to run (space-separated)
  -g, --gpu               Use GPU acceleration
  -C, --compare           Generate comparison report after evaluations
  -o, --output DIR        Output directory (default: batch_evaluation_results)
  -O, --open              Open final report in browser
  -d, --docker            Use Docker for execution
  -e, --continue          Continue on error
  -h, --help              Show this help message

Examples:
  # Evaluate default models
  $0 --gpu --compare

  # Evaluate specific models
  $0 -m "gpt2 distilgpt2" -s "basic robustness" --gpu

  # Use config file
  $0 -c configs/batch_eval.json --docker

  # Continue on errors and compare results
  $0 --continue --compare --open

EOF
}

# Parse arguments
while [ $# -gt 0 ]; do
    case $1 in
        -c|--config)
            CONFIG="$2"
            shift 2
            ;;
        -m|--models)
            shift
            MODELS=()
            while [ $# -gt 0 ] && [[ ! "$1" =~ ^- ]]; do
                MODELS+=("$1")
                shift
            done
            ;;
        -s|--suites)
            shift
            SUITES=()
            while [ $# -gt 0 ] && [[ ! "$1" =~ ^- ]]; do
                SUITES+=("$1")
                shift
            done
            ;;
        -g|--gpu)
            USE_GPU=true
            shift
            ;;
        -C|--compare)
            COMPARE_RESULTS=true
            shift
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -O|--open)
            OPEN_REPORT=true
            shift
            ;;
        -d|--docker)
            USE_DOCKER=true
            shift
            ;;
        -e|--continue)
            CONTINUE_ON_ERROR=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

print_success "========================================="
print_success "  Sleeper Detection Batch Evaluation"
print_success "========================================="
echo

# Create output directory
OUTPUT_PATH="$PROJECT_ROOT/$OUTPUT_DIR"
mkdir -p "$OUTPUT_PATH"
print_info "Output directory: $OUTPUT_PATH"

# Load or generate configuration
if [ -n "$CONFIG" ]; then
    if [[ "$CONFIG" == *.json ]]; then
        # Load JSON config
        if [ -f "$CONFIG" ]; then
            # Parse JSON using Python
            PARSED_CONFIG=$(python3 -c "
import json
import sys
with open('$CONFIG') as f:
    config = json.load(f)
    print(' '.join(config.get('models', [])))
    print(' '.join(config.get('test_suites', [])))
")
            IFS=$'\n' read -d '' -r -a CONFIG_LINES <<< "$PARSED_CONFIG" || true
            MODELS=(${CONFIG_LINES[0]})
            [ -n "${CONFIG_LINES[1]}" ] && SUITES=(${CONFIG_LINES[1]})
            print_info "Loaded configuration from: $CONFIG"
        else
            print_error "Config file not found: $CONFIG"
            exit 1
        fi
    else
        # Parse comma-separated model list
        IFS=',' read -r -a MODELS <<< "$CONFIG"
    fi
fi

# Save config for reference
CONFIG_PATH="$OUTPUT_PATH/batch_config.json"
cat > "$CONFIG_PATH" << EOF
{
  "models": [$(printf '"%s",' "${MODELS[@]}" | sed 's/,$//')]",
  "test_suites": [$(printf '"%s",' "${SUITES[@]}" | sed 's/,$//')]",
  "output_dir": "$OUTPUT_PATH",
  "gpu_mode": $( [ "$USE_GPU" = true ] && echo "true" || echo "false" ),
  "reporting": {
    "generate_comparison_report": $( [ "$COMPARE_RESULTS" = true ] && echo "true" || echo "false" ),
    "report_format": "html"
  }
}
EOF
print_info "Saved batch configuration to: $CONFIG_PATH"

echo
print_info "Models to evaluate: ${MODELS[*]}"
print_info "Test suites: ${SUITES[*]}"
print_info "GPU Mode: $USE_GPU"
print_info "Docker Mode: $USE_DOCKER"
echo

# Initialize results tracking
declare -a SUCCESSFUL_MODELS=()
declare -a FAILED_MODELS=()
declare -A MODEL_TIMINGS

# Evaluate each model
TOTAL_MODELS=${#MODELS[@]}
CURRENT_MODEL=0

for model in "${MODELS[@]}"; do
    ((CURRENT_MODEL++))
    print_progress "[$CURRENT_MODEL/$TOTAL_MODELS] Evaluating model: $model"
    echo

    MODEL_START=$(date +%s)
    MODEL_OUTPUT="$OUTPUT_PATH/$model"
    mkdir -p "$MODEL_OUTPUT"

    # Build evaluation command
    EVAL_CMD="$SCRIPT_DIR/run_cli.sh evaluate $model"
    EVAL_CMD="$EVAL_CMD --suites ${SUITES[*]}"
    [ "$USE_GPU" = true ] && EVAL_CMD="$EVAL_CMD --gpu"
    EVAL_CMD="$EVAL_CMD --report --output $MODEL_OUTPUT"
    [ "$USE_DOCKER" = true ] && EVAL_CMD="$EVAL_CMD --docker"

    print_info "Starting evaluation of $model..."

    # Run evaluation
    if eval $EVAL_CMD; then
        MODEL_END=$(date +%s)
        MODEL_TIME=$((MODEL_END - MODEL_START))
        MODEL_MINUTES=$((MODEL_TIME / 60))

        SUCCESSFUL_MODELS+=("$model")
        MODEL_TIMINGS[$model]=$MODEL_MINUTES

        print_success "✓ Completed $model in $MODEL_MINUTES minutes"

        # Generate individual report
        REPORT_CMD="$SCRIPT_DIR/run_cli.sh report $model"
        REPORT_CMD="$REPORT_CMD --format html --output $MODEL_OUTPUT/report.html"
        eval $REPORT_CMD

    else
        print_error "✗ Failed to evaluate $model"
        FAILED_MODELS+=("$model")

        if [ "$CONTINUE_ON_ERROR" = false ]; then
            print_error "Stopping batch evaluation due to error"
            break
        fi
    fi

    echo
done

# Generate comparison report if requested
if [ "$COMPARE_RESULTS" = true ] && [ ${#SUCCESSFUL_MODELS[@]} -gt 1 ]; then
    print_progress "Generating model comparison report..."

    COMPARE_CMD="$SCRIPT_DIR/run_cli.sh compare ${SUCCESSFUL_MODELS[*]}"
    COMPARE_CMD="$COMPARE_CMD --output $OUTPUT_PATH/comparison_report.html"
    [ "$USE_DOCKER" = true ] && COMPARE_CMD="$COMPARE_CMD --docker"

    if eval $COMPARE_CMD; then
        print_success "✓ Generated comparison report"

        if [ "$OPEN_REPORT" = true ]; then
            xdg-open "$OUTPUT_PATH/comparison_report.html" 2>/dev/null || \
            open "$OUTPUT_PATH/comparison_report.html" 2>/dev/null
        fi
    else
        print_warning "Failed to generate comparison report"
    fi
fi

# Calculate total time
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))
TOTAL_MINUTES=$((TOTAL_TIME / 60))

# Generate summary
echo
print_success "========================================="
print_success "  Batch Evaluation Complete"
print_success "========================================="
echo

print_info "Summary:"
print_success "  Successful: ${#SUCCESSFUL_MODELS[@]} models"
[ ${#FAILED_MODELS[@]} -gt 0 ] && print_error "  Failed: ${#FAILED_MODELS[@]} models (${FAILED_MODELS[*]})"

print_info "  Total time: $TOTAL_MINUTES minutes"
print_info "  Results saved to: $OUTPUT_PATH"

# Save summary to file
SUMMARY_PATH="$OUTPUT_PATH/batch_summary.json"
cat > "$SUMMARY_PATH" << EOF
{
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')",
  "models_evaluated": [$(printf '"%s",' "${SUCCESSFUL_MODELS[@]}" | sed 's/,$//')]",
  "models_failed": [$(printf '"%s",' "${FAILED_MODELS[@]}" | sed 's/,$//')]",
  "test_suites": [$(printf '"%s",' "${SUITES[@]}" | sed 's/,$//')]",
  "gpu_mode": $( [ "$USE_GPU" = true ] && echo "true" || echo "false" ),
  "total_time_minutes": $TOTAL_MINUTES,
  "output_directory": "$OUTPUT_PATH"
}
EOF
print_info "  Summary saved to: $SUMMARY_PATH"

# Exit with appropriate code
if [ ${#FAILED_MODELS[@]} -gt 0 ] && [ "$CONTINUE_ON_ERROR" = false ]; then
    exit 1
else
    exit 0
fi
