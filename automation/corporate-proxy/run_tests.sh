#!/bin/bash
#
# Run corporate proxy tests in container
# This follows the project's container-first philosophy
#

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Source common functions
source "$SCRIPT_DIR/shared/scripts/common-functions.sh"

# Export user and group IDs for proper container permissions
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

print_header "Running Corporate Proxy Tests"
print_info "Using USER_ID=${USER_ID}, GROUP_ID=${GROUP_ID}"

# Detect container runtime
detect_container_runtime

# Change to project root
cd "$PROJECT_ROOT"

# Build the CI image if needed
print_info "Building CI image..."
compose_build python-ci

# Run all tests in container
print_info "Running tests..."
if compose_run --rm --user "${USER_ID}:${GROUP_ID}" python-ci python -m pytest \
    automation/corporate-proxy/tests/ \
    -v \
    --tb=short \
    --no-header; then
    print_success "All tests passed!"
else
    print_error "Some tests failed!"
    exit 1
fi