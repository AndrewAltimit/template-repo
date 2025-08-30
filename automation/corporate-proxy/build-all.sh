#!/bin/bash

# Build all corporate proxy containers with multi-arch support
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common functions
source "$SCRIPT_DIR/shared/scripts/common-functions.sh"

print_header "Building ALL Corporate Proxy Containers"

# Detect container runtime
detect_container_runtime

# Auto-detect architecture
detect_architecture

echo ""

# Check if specific container is requested
CONTAINER="${1:-all}"

# Function to build a container
build_container() {
    local name=$1
    local script_path=$2
    
    print_header "Building $name..."
    
    if [ -f "$script_path" ]; then
        # Export TARGETARCH for the build script to use
        export TARGETARCH
        if bash "$script_path"; then
            print_success "$name build successful"
        else
            print_error "$name build failed"
            exit 1
        fi
    else
        print_warn "Build script not found: $script_path"
    fi
    echo ""
}

# Build containers based on selection
case $CONTAINER in
    gemini)
        build_container "Gemini CLI" "$SCRIPT_DIR/gemini/scripts/build.sh"
        ;;
    opencode)
        build_container "OpenCode" "$SCRIPT_DIR/opencode/scripts/build.sh"
        ;;
    crush)
        build_container "Crush" "$SCRIPT_DIR/crush/scripts/build.sh"
        ;;
    all)
        build_container "Gemini CLI" "$SCRIPT_DIR/gemini/scripts/build.sh"
        build_container "OpenCode" "$SCRIPT_DIR/opencode/scripts/build.sh"
        build_container "Crush" "$SCRIPT_DIR/crush/scripts/build.sh"
        ;;
    *)
        echo "Usage: $0 [gemini|opencode|crush|all]"
        echo ""
        echo "Build corporate proxy containers with auto-detected architecture."
        echo "Current architecture: $TARGETARCH"
        echo "Container runtime: $CONTAINER_RUNTIME"
        echo ""
        echo "To override architecture:"
        echo "  TARGETARCH=arm64 $0 all"
        exit 1
        ;;
esac

print_header "✅ All requested builds complete!"
echo ""
echo "Built for architecture: $TARGETARCH"
echo "Using runtime: $CONTAINER_RUNTIME"
echo ""
echo "To run containers:"
echo "  Gemini:   $SCRIPT_DIR/gemini/scripts/run.sh"
echo "  OpenCode: $SCRIPT_DIR/opencode/scripts/run.sh"
echo "  Crush:    $SCRIPT_DIR/crush/scripts/run.sh"