#!/bin/bash
set -e

echo "=========================================="
echo "Starting Gemini Corporate Services"
echo "=========================================="
echo ""

# Check if mock mode is enabled (default to true for backward compatibility)
COMPANY_MOCK_MODE="${COMPANY_MOCK_MODE:-true}"

# Check if translation wrapper should start (default to true for backward compatibility)
COMPANY_START_WRAPPER="${COMPANY_START_WRAPPER:-true}"

# Check if Gemini should auto-start (default to true for interactive mode)
COMPANY_AUTO_START="${COMPANY_AUTO_START:-true}"

# Check if insecure TLS is explicitly enabled
if [ "${GEMINI_ALLOW_INSECURE_TLS}" = "true" ]; then
    echo "⚠️  WARNING: Insecure TLS mode enabled (GEMINI_ALLOW_INSECURE_TLS=true)"
    export NODE_TLS_REJECT_UNAUTHORIZED=0
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Cleaning up services..."

    # Multi-stage cleanup to ensure no orphaned processes:
    # 1. Kill background jobs from this shell session
    # shellcheck disable=SC2046
    kill $(jobs -p) 2>/dev/null || true

    # 2. Kill any stray processes by name
    pkill -f unified_tool_api.py 2>/dev/null || true
    pkill -f gemini_proxy_wrapper.py 2>/dev/null || true

    # 3. Clean up ports
    if command -v fuser >/dev/null 2>&1; then
        echo "Cleaning up ports..."
        fuser -k 8050/tcp 2>/dev/null || true
        fuser -k 8053/tcp 2>/dev/null || true
    fi

    exit
}

trap cleanup EXIT INT TERM

# Create log directory
mkdir -p /tmp/logs

# Determine mode from arguments
MODE="${1:-interactive}"

# Only start and wait for mock API if COMPANY_MOCK_MODE is true
if [ "$COMPANY_MOCK_MODE" = "true" ]; then
    # Start unified tool API (runs on port 8050)
    echo "Starting unified tool API on port 8050..."
    API_MODE=gemini API_VERSION=v3 PORT=8050 python3 /app/unified_tool_api.py > /tmp/logs/mock_api.log 2>&1 &

    # Wait for mock API to be ready
    echo "Waiting for mock API to be ready..."
    for i in {1..30}; do
        if curl -fsS http://localhost:8050/health > /dev/null; then
            echo "✓ Mock API is ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "✗ Mock API failed to start"
            echo "Check logs at /tmp/logs/mock_api.log"
            exit 1
        fi
        sleep 1
    done
else
    echo "Mock API disabled (COMPANY_MOCK_MODE=$COMPANY_MOCK_MODE)"
fi

# Only start and wait for Gemini proxy wrapper if COMPANY_START_WRAPPER is true
if [ "$COMPANY_START_WRAPPER" = "true" ]; then
    # Start Gemini proxy wrapper (runs on port 8053)
    echo "Starting Gemini proxy wrapper on port 8053..."
    MOCK_API_BASE=http://localhost:8050 python3 /app/gemini_proxy_wrapper.py > /tmp/logs/gemini_proxy.log 2>&1 &

    # Wait for proxy to be ready
    echo "Waiting for Gemini proxy to be ready..."
    for i in {1..30}; do
        if curl -fsS http://localhost:8053/health > /dev/null; then
            echo "✓ Gemini proxy is ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "✗ Gemini proxy failed to start"
            echo "Check logs at /tmp/logs/gemini_proxy.log"
            exit 1
        fi
        sleep 1
    done
else
    echo "Gemini proxy wrapper disabled (COMPANY_START_WRAPPER=$COMPANY_START_WRAPPER)"
fi

# Pre-configure Gemini CLI to use API key auth
# This avoids the auth prompt
# Create config in home directory (always writable)
USER_HOME="${HOME:-$(eval echo ~"$(whoami)")}"
mkdir -p "${USER_HOME}/.gemini"

# Create settings file with correct auth type value (gemini-api-key for API key)
cat > "${USER_HOME}/.gemini/settings.json" << 'EOF'
{
  "selectedAuthType": "gemini-api-key"
}
EOF

# Try to create workspace config if possible (ignore errors)
mkdir -p /workspace/.gemini 2>/dev/null || true
cp "${USER_HOME}/.gemini/settings.json" /workspace/.gemini/settings.json 2>/dev/null || true

echo ""
echo "=========================================="
echo "All services started successfully!"
echo "=========================================="
echo ""
echo "Services running:"
if [ "$COMPANY_MOCK_MODE" = "true" ]; then
    echo "  - Mock Company API: http://localhost:8050"
fi
if [ "$COMPANY_START_WRAPPER" = "true" ]; then
    echo "  - Gemini Proxy: http://localhost:8053"
fi
echo ""
echo "Service logs:"
if [ "$COMPANY_MOCK_MODE" = "true" ]; then
    echo "  - /tmp/logs/mock_api.log"
fi
if [ "$COMPANY_START_WRAPPER" = "true" ]; then
    echo "  - /tmp/logs/gemini_proxy.log"
fi
echo ""

# Create a wrapper function for gemini that forces proxy
echo "Creating gemini-proxy wrapper..."
cat > /tmp/gemini-proxy << 'EOF'
#!/bin/bash
# Force Gemini to use our proxy by intercepting the call
export GOOGLE_GENAI_API_BASE_URL="http://localhost:8053/v1"
export GEMINI_API_BASE_URL="http://localhost:8053/v1"
exec /usr/local/bin/gemini "$@"
EOF
chmod +x /tmp/gemini-proxy

# Handle different modes
case "$MODE" in
    interactive)
        if [ "$COMPANY_AUTO_START" = "true" ]; then
            echo "Starting Gemini CLI..."
            echo "=========================================="
            echo ""
            echo "You can use Gemini CLI:"
            echo "  gemini          - Interactive mode"
            echo "  gemini --help   - Show help"
            echo ""
            echo "Example test:"
            echo "  echo 'Hello world' | gemini --non-interactive"
            echo ""
            echo "=========================================="
            echo ""

            # Start Gemini CLI directly in interactive mode using the proxy wrapper
            exec /tmp/gemini-proxy
        else
            echo "Auto-start disabled (COMPANY_AUTO_START=$COMPANY_AUTO_START)"
            echo ""
            echo "To start Gemini CLI manually:"
            echo "  gemini"
            echo ""
            # Just keep the container running
            exec bash
        fi
        ;;

    run)
        # Run mode - execute command with arguments
        shift  # Remove 'run' from arguments
        if [ $# -gt 0 ]; then
            echo "Running Gemini with arguments: $*"
            echo "=========================================="
            echo ""
            exec /tmp/gemini-proxy "$@"
        else
            echo "No arguments provided for run mode"
            exit 1
        fi
        ;;

    test)
        echo "Running tests..."
        echo ""

        # Test 1: Check services are up
        echo "Test 1: Service health checks..."
        if [ "$COMPANY_MOCK_MODE" = "true" ]; then
            if curl -s http://localhost:8050/health | grep -q "healthy"; then
                echo "✅ Mock API is healthy"
            else
                echo "❌ Mock API failed"
                exit 1
            fi
        fi

        if [ "$COMPANY_START_WRAPPER" = "true" ]; then
            if curl -s http://localhost:8053/health | grep -q "healthy"; then
                echo "✅ Gemini proxy is healthy"
            else
                echo "❌ Gemini proxy failed"
                exit 1
            fi
        fi

        # Test 2: Direct proxy test
        if [ "$COMPANY_START_WRAPPER" = "true" ]; then
            echo ""
            echo "Test 2: Direct proxy API call..."
            RESPONSE=$(curl -s -X POST http://localhost:8053/v1/models/gemini-2.5-flash/generateContent \
                -H "Content-Type: application/json" \
                -d '{"contents": [{"parts": [{"text": "Hello"}]}]}')

            if echo "$RESPONSE" | grep -q "Hatsune Miku"; then
                echo "✅ Proxy returns 'Hatsune Miku'"
            else
                echo "❌ Proxy test failed"
                echo "Response: $RESPONSE"
                exit 1
            fi
        fi

        # Test 3: Gemini CLI test
        if [ "$COMPANY_AUTO_START" != "false" ]; then
            echo ""
            echo "Test 3: Gemini CLI integration..."
            TEST_OUTPUT=$(echo "Hello world" | timeout 10 /tmp/gemini-proxy -p "Respond to this message" 2>&1 || true)

            if echo "$TEST_OUTPUT" | grep -q "Hatsune Miku"; then
                echo "✅ Gemini CLI returns 'Hatsune Miku'"
            else
                echo "⚠️  Gemini CLI integration test - checking if it connects to proxy"
                echo "Output preview: $(echo "$TEST_OUTPUT" | head -5)"
            fi
        fi

        echo ""
        echo "=========================================="
        echo "✅ All tests completed!"
        echo "=========================================="
        ;;

    daemon)
        echo "Starting in daemon mode..."
        echo ""
        echo "Services running. Container will remain running..."
        echo "Logs available at:"
        if [ "$COMPANY_MOCK_MODE" = "true" ]; then
            echo "  /tmp/logs/mock_api.log"
        fi
        if [ "$COMPANY_START_WRAPPER" = "true" ]; then
            echo "  /tmp/logs/gemini_proxy.log"
        fi

        # Keep container running
        while true; do
            sleep 60
            # Check if services are still running and restart if needed
            if [ "$COMPANY_MOCK_MODE" = "true" ]; then
                if ! pgrep -f unified_tool_api.py > /dev/null; then
                    echo "Unified API died, restarting..."
                    API_MODE=gemini API_VERSION=v3 PORT=8050 python3 /app/unified_tool_api.py > /tmp/logs/mock_api.log 2>&1 &
                fi
            fi
            if [ "$COMPANY_START_WRAPPER" = "true" ]; then
                if ! pgrep -f gemini_proxy_wrapper.py > /dev/null; then
                    echo "Gemini proxy died, restarting..."
                    MOCK_API_BASE=http://localhost:8050 python3 /app/gemini_proxy_wrapper.py > /tmp/logs/gemini_proxy.log 2>&1 &
                fi
            fi
        done
        ;;

    *)
        # Check if we got arguments but no explicit mode
        if [ $# -gt 0 ]; then
            # Treat as run mode with arguments
            echo "Running Gemini with arguments: $*"
            echo "=========================================="
            echo ""
            exec /tmp/gemini-proxy "$@"
        else
            echo "Unknown mode: $MODE"
            echo "Usage: $0 [interactive|run|test|daemon] [arguments]"
            exit 1
        fi
        ;;
esac
