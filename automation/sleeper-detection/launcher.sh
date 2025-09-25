#!/bin/bash
# Universal Sleeper Detection Launcher Menu
# Interactive menu for all sleeper agent detection operations

set -e

# Color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Script paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Print functions
print_header() { echo -e "${BLUE}$1${NC}"; }
print_success() { echo -e "${GREEN}$1${NC}"; }
print_info() { echo -e "${CYAN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}$1${NC}"; }
print_error() { echo -e "${RED}$1${NC}"; }
print_option() { echo -e "${MAGENTA}$1${NC}"; }

# Clear screen and show header
clear
print_header "╔══════════════════════════════════════════════╗"
print_header "║     🔍 Sleeper Agent Detection System 🔍      ║"
print_header "║          Comprehensive AI Safety Suite        ║"
print_header "╚══════════════════════════════════════════════╝"
echo

# Main menu
show_main_menu() {
    print_info "Main Menu:"
    echo
    print_option "  1) 📊 Launch Dashboard"
    print_option "  2) 🔬 Evaluate Single Model"
    print_option "  3) 📈 Compare Multiple Models"
    print_option "  4) 🔄 Batch Evaluation"
    print_option "  5) 📄 Generate Report"
    print_option "  6) 🧪 Quick Test"
    print_option "  7) 📋 List Results"
    print_option "  8) 🗑️  Clean Results"
    print_option "  9) ⚙️  Configuration"
    print_option "  0) 🚪 Exit"
    echo
    read -r -p "Select option [0-9]: " choice
}

# Launch dashboard
launch_dashboard() {
    clear
    print_header "=== Dashboard Launcher ==="
    echo
    print_info "Select initialization method:"
    echo "  1) Mock test data (recommended for demo)"
    echo "  2) Empty database"
    echo "  3) Existing database"
    echo "  4) Load from file"
    echo
    read -r -p "Select [1-4]: " db_choice

    case $db_choice in
        1) DB_OPT="mock" ;;
        2) DB_OPT="empty" ;;
        3) DB_OPT="existing" ;;
        4)
            read -r -p "Enter database path: " db_path
            DB_OPT="$db_path"
            ;;
        *) DB_OPT="mock" ;;
    esac

    "$SCRIPT_DIR/dashboard/launch.sh" "$DB_OPT"
}

# Evaluate single model
evaluate_model() {
    clear
    print_header "=== Model Evaluation ==="
    echo
    read -r -p "Enter model name (e.g., gpt2): " model

    print_info "Select test suites (space-separated):"
    echo "  Options: basic code_vulnerability chain_of_thought robustness attention intervention"
    read -r -p "Suites [basic code_vulnerability]: " suites
    [ -z "$suites" ] && suites="basic code_vulnerability"

    read -r -p "Use GPU? [y/N]: " use_gpu
    GPU_FLAG=""
    [ "$use_gpu" = "y" ] || [ "$use_gpu" = "Y" ] && GPU_FLAG="--gpu"

    read -r -p "Generate report? [Y/n]: " gen_report
    REPORT_FLAG="--report"
    [ "$gen_report" = "n" ] || [ "$gen_report" = "N" ] && REPORT_FLAG=""

    print_info "Starting evaluation..."
    "$SCRIPT_DIR/linux/run_cli.sh" evaluate "$model" --suites $suites $GPU_FLAG $REPORT_FLAG
}

# Compare models
compare_models() {
    clear
    print_header "=== Model Comparison ==="
    echo
    print_info "Enter models to compare (space-separated):"
    read -r -p "Models: " models

    if [ -z "$models" ]; then
        print_error "No models specified"
        return
    fi

    print_info "Comparing models..."
    "$SCRIPT_DIR/linux/run_cli.sh" compare $models
}

# Batch evaluation
batch_evaluation() {
    clear
    print_header "=== Batch Evaluation ==="
    echo
    print_info "Select input method:"
    echo "  1) Use config file"
    echo "  2) Enter models manually"
    echo "  3) Use defaults (gpt2, distilgpt2, gpt2-medium)"
    echo
    read -r -p "Select [1-3]: " batch_choice

    case $batch_choice in
        1)
            read -r -p "Config file path: " config
            CONFIG_OPT="-c $config"
            ;;
        2)
            read -r -p "Models (space-separated): " models
            CONFIG_OPT="-m $models"
            ;;
        3)
            CONFIG_OPT=""
            ;;
        *)
            CONFIG_OPT=""
            ;;
    esac

    read -r -p "Use GPU? [y/N]: " use_gpu
    GPU_FLAG=""
    [ "$use_gpu" = "y" ] || [ "$use_gpu" = "Y" ] && GPU_FLAG="--gpu"

    read -r -p "Generate comparison report? [Y/n]: " compare
    COMPARE_FLAG="--compare"
    [ "$compare" = "n" ] || [ "$compare" = "N" ] && COMPARE_FLAG=""

    print_info "Starting batch evaluation..."
    "$SCRIPT_DIR/linux/batch_evaluate.sh" $CONFIG_OPT $GPU_FLAG $COMPARE_FLAG
}

# Generate report
generate_report() {
    clear
    print_header "=== Report Generation ==="
    echo
    read -r -p "Enter model name: " model

    print_info "Select format:"
    echo "  1) HTML (default)"
    echo "  2) PDF"
    echo "  3) JSON"
    read -r -p "Select [1-3]: " format_choice

    case $format_choice in
        1) FORMAT="html" ;;
        2) FORMAT="pdf" ;;
        3) FORMAT="json" ;;
        *) FORMAT="html" ;;
    esac

    read -r -p "Open report after generation? [Y/n]: " open_report
    OPEN_FLAG=""
    [ "$open_report" != "n" ] && [ "$open_report" != "N" ] && OPEN_FLAG="--open"

    print_info "Generating report..."
    "$SCRIPT_DIR/linux/run_cli.sh" report "$model" --format "$FORMAT" $OPEN_FLAG
}

# Quick test
quick_test() {
    clear
    print_header "=== Quick Test ==="
    echo
    read -r -p "Use GPU? [y/N]: " use_gpu

    if [ "$use_gpu" = "y" ] || [ "$use_gpu" = "Y" ]; then
        print_info "Running GPU test..."
        "$SCRIPT_DIR/linux/run_cli.sh" test
    else
        print_info "Running CPU test..."
        "$SCRIPT_DIR/linux/run_cli.sh" test --cpu
    fi
}

# List results
list_results() {
    clear
    print_header "=== List Results ==="
    echo
    print_info "What to list?"
    echo "  1) Evaluated models"
    echo "  2) All results"
    read -r -p "Select [1-2]: " list_choice

    case $list_choice in
        1)
            "$SCRIPT_DIR/linux/run_cli.sh" list models
            ;;
        2)
            "$SCRIPT_DIR/linux/run_cli.sh" list results
            ;;
        *)
            "$SCRIPT_DIR/linux/run_cli.sh" list models
            ;;
    esac
}

# Clean results
clean_results() {
    clear
    print_header "=== Clean Results ==="
    echo
    print_warning "This will remove evaluation results!"
    read -r -p "Enter model name (or 'all' for everything): " model

    if [ "$model" = "all" ]; then
        read -r -p "Are you sure you want to remove ALL results? [y/N]: " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            "$SCRIPT_DIR/linux/run_cli.sh" clean
            print_success "All results cleaned"
        fi
    else
        "$SCRIPT_DIR/linux/run_cli.sh" clean --model "$model"
        print_success "Results for $model cleaned"
    fi
}

# Configuration menu
show_configuration() {
    clear
    print_header "=== Configuration ==="
    echo
    print_info "Current Settings:"
    echo
    echo "  Project Root: $(cd "$SCRIPT_DIR/../.." && pwd)"
    echo "  Results Dir: evaluation_results/"
    echo "  Platform: $(uname -s)"

    # Check for GPU
    if command -v nvidia-smi &> /dev/null; then
        echo "  GPU: Available ($(nvidia-smi --query-gpu=name --format=csv,noheader | head -1))"
    else
        echo "  GPU: Not available"
    fi

    # Check Python
    if command -v python &> /dev/null; then
        echo "  Python: $(python --version 2>&1)"
    else
        echo "  Python: Not found"
    fi

    # Check Docker
    if command -v docker &> /dev/null; then
        echo "  Docker: $(docker --version | cut -d' ' -f3 | sed 's/,$//')"
    else
        echo "  Docker: Not installed"
    fi

    echo
    read -r -p "Press Enter to continue..."
}

# Main loop
while true; do
    clear
    print_header "╔══════════════════════════════════════════════╗"
    print_header "║     🔍 Sleeper Agent Detection System 🔍      ║"
    print_header "╚══════════════════════════════════════════════╝"
    echo

    show_main_menu

    case $choice in
        1) launch_dashboard ;;
        2) evaluate_model ;;
        3) compare_models ;;
        4) batch_evaluation ;;
        5) generate_report ;;
        6) quick_test ;;
        7) list_results ;;
        8) clean_results ;;
        9) show_configuration ;;
        0)
            print_success "Goodbye!"
            exit 0
            ;;
        *)
            print_error "Invalid option"
            ;;
    esac

    echo
    read -r -p "Press Enter to continue..."
done
