#!/bin/bash
set -e

echo "=========================================="
echo "Starting OpenCode Corporate Services"
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up services..."
    # shellcheck disable=SC2046
    kill $(jobs -p) 2>/dev/null || true
    exit
}

trap cleanup INT TERM

# Create log directory
mkdir -p /tmp/logs

# OpenCode keeps its state under $HOME. The run scripts and compose override
# the container UID (and sometimes HOME), so fall back to a writable HOME
# when the configured one is not.
if [ -z "${HOME:-}" ] || ! { mkdir -p "$HOME" && [ -w "$HOME" ]; } 2>/dev/null; then
    export HOME=/tmp/opencode-home
    mkdir -p "$HOME"
fi

MOCK_API_PORT="${MOCK_API_PORT:-8050}"
WRAPPER_PORT="${WRAPPER_PORT:-8052}"
MOCK_API_BASE="http://localhost:$MOCK_API_PORT"

# wait_for <name> <url> <log>: poll a /health endpoint for up to 30 seconds
wait_for() {
    echo "Waiting for $1 to be ready..."
    for i in {1..30}; do
        if curl -fsS "$2" > /dev/null 2>&1; then
            echo "✓ $1 is ready"
            return 0
        fi
        if [ "$i" -eq 30 ]; then
            echo "✗ $1 failed to start"
            echo "Check logs at $3"
            exit 1
        fi
        sleep 1
    done
}

# Mock Company API (unified tool API). Skipped when COMPANY_API_BASE points
# at a real Company API (run-production.sh).
if [ "${COMPANY_API_BASE:-$MOCK_API_BASE}" = "$MOCK_API_BASE" ]; then
    echo "Starting mock Company API on port $MOCK_API_PORT..."
    API_MODE=opencode API_VERSION=v3 PORT="$MOCK_API_PORT" \
        python3 /app/unified_tool_api.py > /tmp/logs/mock_api.log 2>&1 &
    wait_for "Mock API" "$MOCK_API_BASE/health" /tmp/logs/mock_api.log
else
    echo "Using Company API at $COMPANY_API_BASE (mock not started)"
fi

# Translation wrapper: the OpenAI-compatible endpoint OpenCode's "company"
# provider talks to (COMPANY_PROXY_BASE_URL)
echo "Starting translation wrapper on port $WRAPPER_PORT..."
PORT="$WRAPPER_PORT" python3 /app/translation_wrapper.py > /tmp/logs/translation_wrapper.log 2>&1 &
wait_for "Translation wrapper" "http://localhost:$WRAPPER_PORT/health" /tmp/logs/translation_wrapper.log

echo ""
echo "=========================================="
echo "All services started successfully!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  - Company API: ${COMPANY_API_BASE:-$MOCK_API_BASE}"
echo "  - Translation Wrapper: http://localhost:$WRAPPER_PORT (OpenCode provider: company)"
echo ""
echo "Service logs:"
echo "  - /tmp/logs/mock_api.log"
echo "  - /tmp/logs/translation_wrapper.log"
echo ""
echo "$(opencode --version 2>/dev/null || echo 'opencode (version unknown)') ready"
echo "=========================================="
echo ""

# Run the given command. Without one, start a shell when attached to a
# terminal; otherwise (compose `up -d`, `docker run -d`) keep serving.
if [ $# -gt 0 ]; then
    exec "$@"
elif [ -t 0 ]; then
    exec bash
else
    echo "No command and no terminal: serving until stopped"
    wait
fi
