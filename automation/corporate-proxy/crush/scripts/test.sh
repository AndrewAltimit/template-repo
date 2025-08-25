#!/bin/bash
set -e

# Get script directory and load common functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/../../shared/scripts/common-functions.sh"

print_header "Testing Crush Corporate Integration"

# Check Docker
check_docker

# Build if needed
build_if_needed "crush-corporate:latest" "$SCRIPT_DIR/../docker/Dockerfile" "$CORPORATE_PROXY_ROOT"

# Test prompt
TEST_PROMPT="Say 'Hello from Crush Corporate Integration'"

print_info "Testing with prompt: '$TEST_PROMPT'"
echo ""

# Run Crush with the test prompt using non-interactive mode
docker run --rm \
    --name crush-corporate-test \
    -e COMPANY_API_BASE="http://localhost:8050" \
    -e COMPANY_API_TOKEN="test-secret-token-123" \
    crush-corporate:latest crush run "$TEST_PROMPT"

echo ""
print_header "Test Complete"
echo "Expected output: 'Hatsune Miku' (from mock API)"
echo ""
echo "If you see 'Hatsune Miku' above, the integration is working correctly!"
