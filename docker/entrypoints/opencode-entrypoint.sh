#!/bin/bash
# OpenCode Company Integration Entrypoint Script
# Manages mock services and OpenCode startup for containerized environment

# Exit on any error to prevent running in broken state
set -e

echo "[Company] Starting Company OpenCode Container"
echo "[Company] TUI binaries are installed at:"
ls -la /home/bun/.cache/opencode/tui/
echo ""

# Auto-start mock services if COMPANY_MOCK_MODE is set
if [ "$COMPANY_MOCK_MODE" = "true" ]; then
    echo "[Company] Mock mode enabled - starting services..."
    echo "Starting mock API on port ${MOCK_API_PORT:-8050}..."
    python3 /workspace/mock_company_api.py > /tmp/mock_api.log 2>&1 &
    MOCK_PID=$!
    echo "Mock API started (PID: $MOCK_PID)"

    echo "Starting translation wrapper on port ${WRAPPER_PORT:-8052}..."
    python3 /workspace/company_translation_wrapper.py > /tmp/wrapper.log 2>&1 &
    WRAPPER_PID=$!
    echo "Translation wrapper started (PID: $WRAPPER_PID)"

    # Wait for services to be ready with retry loop
    echo "Waiting for services to be ready..."

    # Check mock API with retries
    mock_ready=false
    for i in {1..10}; do
        if nc -z localhost "${MOCK_API_PORT:-8050}" 2>/dev/null; then
            echo "✅ Mock API is running on port ${MOCK_API_PORT:-8050}"
            mock_ready=true
            break
        fi
        echo "  Waiting for mock API... ($i/10)"
        sleep 1
    done

    if [ "$mock_ready" = false ]; then
        echo "⚠️  Mock API failed to start after 10 seconds - check /tmp/mock_api.log"
        echo "Last 10 lines of mock API log:"
        tail -10 /tmp/mock_api.log 2>/dev/null || echo "No log available"
    fi

    # Check wrapper with retries
    wrapper_ready=false
    for i in {1..10}; do
        if nc -z localhost "${WRAPPER_PORT:-8052}" 2>/dev/null; then
            echo "✅ Translation wrapper is running on port ${WRAPPER_PORT:-8052}"
            wrapper_ready=true
            break
        fi
        echo "  Waiting for translation wrapper... ($i/10)"
        sleep 1
    done

    if [ "$wrapper_ready" = false ]; then
        echo "⚠️  Translation wrapper failed to start after 10 seconds - check /tmp/wrapper.log"
        echo "Last 10 lines of wrapper log:"
        tail -10 /tmp/wrapper.log 2>/dev/null || echo "No log available"
    fi
    echo ""
    echo "[Company] Mock services started! Ready to use OpenCode."
else
    echo "[Company] Mock mode disabled. To enable, set COMPANY_MOCK_MODE=true"
    echo "[Company] Manual commands:"
    echo "  python3 mock_company_api.py &"
    echo "  python3 company_translation_wrapper.py &"
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "[Company] Shutting down services..."
    # Use graceful termination first (SIGTERM)
    pkill -f mock_company_api.py 2>/dev/null || true
    pkill -f company_translation_wrapper.py 2>/dev/null || true

    # Give processes time to cleanup
    sleep 1

    # Force kill if still running (only as last resort)
    if pgrep -f mock_company_api.py > /dev/null 2>&1; then
        pkill -9 -f mock_company_api.py 2>/dev/null || true
    fi
    if pgrep -f company_translation_wrapper.py > /dev/null 2>&1; then
        pkill -9 -f company_translation_wrapper.py 2>/dev/null || true
    fi

    exit 0
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

# Check if we should auto-start OpenCode
if [ "$COMPANY_AUTO_START" = "true" ]; then
    echo ""
    echo "[Company] Auto-starting OpenCode TUI..."
    echo "========================================"
    echo ""
    # Give a moment for user to see startup messages
    sleep 1
    # Start OpenCode TUI directly
    exec opencode
else
    echo ""
    echo "[Company] Available commands:"
    echo "  opencode         - Start TUI (interactive mode)"
    echo "  opencode serve   - Start headless server"
    echo "  opencode run \"prompt\" - Run a single prompt"
    echo "  opencode models  - List available models"
    echo ""
    echo "[Company] To auto-start TUI, set COMPANY_AUTO_START=true"
    echo ""
    exec bash
fi
