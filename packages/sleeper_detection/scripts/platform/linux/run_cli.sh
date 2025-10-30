#!/bin/bash
# Linux CLI Runner for Sleeper Detection System
# Provides all CLI operations with GPU/CPU support

set -e

# Color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Default values
COMMAND=""
MODELS=()
SUITES=("basic" "code_vulnerability")
USE_GPU=false
FORMAT="html"
OUTPUT=""
GENERATE_REPORT=false
OPEN_RESULT=false
USE_DOCKER=false
VERBOSE=false

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PROJECT_ROOT="$(cd "$PACKAGE_ROOT/../.." && pwd)"

# Print colored output
print_success() { echo -e "${GREEN}$1${NC}"; }
print_info() { echo -e "${CYAN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}$1${NC}"; }
print_error() { echo -e "${RED}$1${NC}"; }
print_progress() { echo -e "${MAGENTA}$1${NC}"; }

# Show usage
usage() {
    cat << EOF
Usage: $0 COMMAND [OPTIONS]

Commands:
  evaluate MODEL    Evaluate a single model
  compare MODELS    Compare multiple models (space-separated)
  batch CONFIG      Run batch evaluation from config file
  report MODEL      Generate report for a model
  test              Run quick test
  list [TYPE]       List models or results
  clean [MODEL]     Clean evaluation results
  dashboard         Launch interactive dashboard

Options:
  -s, --suites SUITES     Test suites to run (default: basic code_vulnerability)
                          Options: basic, code_vulnerability, chain_of_thought,
                                   robustness, attention, intervention, advanced, all
  -g, --gpu               Use GPU acceleration
  -f, --format FORMAT     Report format: html, pdf, json (default: html)
  -o, --output PATH       Output directory/file
  -r, --report            Generate report after evaluation
  -O, --open              Open report/dashboard after completion
  -d, --docker            Use Docker for execution
  -v, --verbose           Verbose output
  -h, --help              Show this help message

Examples:
  # Evaluate a model with GPU
  $0 evaluate gpt2 --gpu --report

  # Compare multiple models
  $0 compare gpt2 distilgpt2 gpt2-medium

  # Run batch evaluation
  $0 batch configs/batch_eval.json --gpu

  # Generate HTML report
  $0 report gpt2 --format html --open

  # Launch dashboard
  $0 dashboard --open

EOF
}

# Parse arguments
if [ $# -eq 0 ]; then
    usage
    exit 1
fi

COMMAND=$1
shift

# Parse command-specific arguments and options
while [ $# -gt 0 ]; do
    case $1 in
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
        -f|--format)
            FORMAT="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -r|--report)
            GENERATE_REPORT=true
            shift
            ;;
        -O|--open)
            OPEN_RESULT=true
            shift
            ;;
        -d|--docker)
            USE_DOCKER=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            MODELS+=("$1")
            shift
            ;;
    esac
done

print_success "=== Sleeper Agent Detection CLI ==="
print_info "Command: $COMMAND"
if [ "$USE_GPU" = true ]; then
    print_info "Mode: GPU Acceleration"
else
    print_info "Mode: CPU"
fi
echo

# Build Python command
build_python_command() {
    local args=("-m" "sleeper_detection.cli" "$COMMAND")

    case $COMMAND in
        evaluate)
            if [ ${#MODELS[@]} -eq 0 ]; then
                print_error "Model name required for evaluate command"
                exit 1
            fi
            args+=("${MODELS[0]}")

            if [ ${#SUITES[@]} -gt 0 ] && [ "${SUITES[0]}" != "all" ]; then
                args+=("--suites" "${SUITES[@]}")
            fi

            [ "$USE_GPU" = true ] && args+=("--gpu")
            [ "$GENERATE_REPORT" = true ] && args+=("--report")
            [ -n "$OUTPUT" ] && args+=("--output" "$OUTPUT")
            ;;

        compare)
            if [ ${#MODELS[@]} -lt 2 ]; then
                print_error "At least 2 models required for compare command"
                exit 1
            fi
            args+=("${MODELS[@]}")
            [ -n "$OUTPUT" ] && args+=("--output" "$OUTPUT")
            ;;

        batch)
            if [ ${#MODELS[@]} -eq 0 ]; then
                print_error "Config file path required for batch command"
                exit 1
            fi
            args+=("${MODELS[0]}")
            [ "$USE_GPU" = true ] && args+=("--gpu")
            ;;

        report)
            if [ ${#MODELS[@]} -eq 0 ]; then
                print_error "Model name required for report command"
                exit 1
            fi
            args+=("${MODELS[0]}")
            args+=("--format" "$FORMAT")
            [ -n "$OUTPUT" ] && args+=("--output" "$OUTPUT")
            ;;

        test)
            [ "$USE_GPU" = false ] && args+=("--cpu")
            [ ${#MODELS[@]} -gt 0 ] && args+=("--model" "${MODELS[0]}")
            ;;

        list)
            if [ ${#MODELS[@]} -gt 0 ]; then
                case ${MODELS[0]} in
                    models) args+=("--models") ;;
                    results) args+=("--results") ;;
                    *) args+=("--models") ;;
                esac
            else
                args+=("--models")
            fi
            ;;

        clean)
            [ ${#MODELS[@]} -gt 0 ] && args+=("--model" "${MODELS[0]}")
            ;;

        dashboard)
            # Special case - launch dashboard
            "$SCRIPT_DIR/../dashboard/launch.sh"
            [ "$OPEN_RESULT" = true ] && sleep 3 && xdg-open "http://localhost:8501" &
            exit 0
            ;;

        *)
            print_error "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac

    echo "${args[@]}"
}

# Main execution
cd "$PROJECT_ROOT"

# Build Python command
PYTHON_ARGS=$(build_python_command)

if [ "$USE_DOCKER" = true ]; then
    print_info "Running in Docker container..."

    # Determine Docker image
    if [ "$USE_GPU" = true ]; then
        IMAGE_NAME="sleeper-eval-gpu"
        DOCKER_GPU_FLAGS="--gpus all"
    else
        IMAGE_NAME="sleeper-eval-cpu"
        DOCKER_GPU_FLAGS=""
    fi

    # Build Docker command using array
    RESULTS_PATH="$PROJECT_ROOT/evaluation_results"
    mkdir -p "$RESULTS_PATH"

    # Build Docker command array
    DOCKER_CMD=("docker" "run" "--rm")
    if [ -n "$DOCKER_GPU_FLAGS" ]; then
        # Split GPU flags into array elements safely
        read -r -a GPU_FLAGS_ARRAY <<< "$DOCKER_GPU_FLAGS"
        DOCKER_CMD+=("${GPU_FLAGS_ARRAY[@]}")
    fi
    DOCKER_CMD+=("-v" "$PROJECT_ROOT:/workspace" "-v" "$RESULTS_PATH:/results" "-w" "/workspace")
    DOCKER_CMD+=("-e" "EVAL_RESULTS_DIR=/results" "-e" "EVAL_DB_PATH=/results/evaluation_results.db")
    DOCKER_CMD+=("$IMAGE_NAME" "python")

    # Parse PYTHON_ARGS string into array elements
    read -r -a PYTHON_ARGS_ARRAY <<< "$PYTHON_ARGS"
    DOCKER_CMD+=("${PYTHON_ARGS_ARRAY[@]}")

    if [ "$VERBOSE" = true ]; then
        print_info "Docker command: ${DOCKER_CMD[*]}"
    fi

    "${DOCKER_CMD[@]}"

else
    print_info "Running locally with Python..."

    # Check Python installation
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
        exit 1
    fi

    # Set environment variables
    export EVAL_RESULTS_DIR="$PROJECT_ROOT/evaluation_results"
    export EVAL_DB_PATH="$EVAL_RESULTS_DIR/evaluation_results.db"

    # Create results directory
    mkdir -p "$EVAL_RESULTS_DIR"

    # Parse PYTHON_ARGS string into array
    read -r -a PYTHON_ARGS_ARRAY <<< "$PYTHON_ARGS"

    if [ "$VERBOSE" = true ]; then
        print_info "Python command: python ${PYTHON_ARGS_ARRAY[*]}"
    fi

    # Run Python command with array
    python "${PYTHON_ARGS_ARRAY[@]}"
fi

# Handle post-execution actions
if [ "$GENERATE_REPORT" = true ] || [ "$COMMAND" = "report" ]; then
    if [ -n "$OUTPUT" ]; then
        REPORT_PATH="$OUTPUT"
    else
        REPORT_PATH="$EVAL_RESULTS_DIR/report_${MODELS[0]}.html"
    fi

    if [ -f "$REPORT_PATH" ]; then
        print_success "Report generated: $REPORT_PATH"

        if [ "$OPEN_RESULT" = true ]; then
            xdg-open "$REPORT_PATH" 2>/dev/null || open "$REPORT_PATH" 2>/dev/null
            print_success "Opened report in browser"
        fi
    fi
fi

echo
print_success "Operation completed successfully!"
