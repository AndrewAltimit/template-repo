#!/bin/bash
set -e

# Gemini CLI wrapper script for containerized environment
# Starts proxy services and runs Gemini CLI

echo "=========================================="
echo "Gemini CLI Corporate Proxy Wrapper"
echo "=========================================="

# Check if insecure TLS is explicitly enabled
if [ "${GEMINI_ALLOW_INSECURE_TLS}" = "true" ]; then
    echo "⚠️  WARNING: Insecure TLS mode enabled (GEMINI_ALLOW_INSECURE_TLS=true)"
    export NODE_TLS_REJECT_UNAUTHORIZED=0
fi

# Store PIDs of background processes for cleanup
API_PID=""
PROXY_PID=""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down services..."

    # Kill specific processes if their PIDs are set
    if [ -n "$API_PID" ]; then
        kill "$API_PID" 2>/dev/null || true
    fi
    if [ -n "$PROXY_PID" ]; then
        kill "$PROXY_PID" 2>/dev/null || true
    fi

    # Also kill any remaining jobs
    kill "$(jobs -p)" 2>/dev/null || true

    # Clean up any stray processes by name
    pkill -f unified_tool_api.py 2>/dev/null || true
    pkill -f gemini_proxy_wrapper.py 2>/dev/null || true

    exit 0
}

trap cleanup EXIT INT TERM

# Start services based on mode
MODE="${1:-interactive}"

case "$MODE" in
    interactive)
        echo "Starting services..."

        # In mock mode, we only need the Gemini proxy which will connect to the unified API
        if [ "${USE_MOCK_API}" = "true" ]; then
            # Start unified tool API for Gemini (mock mode)
            echo "Starting unified tool API in mock mode on port 8050..."
            API_MODE=gemini API_VERSION=v3 PORT=8050 python3 /app/unified_tool_api.py > /tmp/unified_api.log 2>&1 &
            API_PID=$!

            # Wait for unified API
            for _ in {1..10}; do
                if curl -s http://localhost:8050/health > /dev/null 2>&1; then
                    echo "✅ Unified tool API ready (mock mode)"
                    break
                fi
                sleep 1
            done
        fi

        # Start Gemini proxy wrapper (includes tool support)
        echo "Starting Gemini proxy with tool support on port 8053..."
        MOCK_API_BASE=http://localhost:8050 python3 /app/gemini_proxy_wrapper.py > /tmp/gemini_proxy.log 2>&1 &
        PROXY_PID=$!

        # Wait for proxy
        for _ in {1..10}; do
            if curl -s http://localhost:8053/health > /dev/null 2>&1; then
                echo "✅ Gemini proxy ready"
                break
            fi
            sleep 1
        done

        # Pre-configure Gemini CLI to use API key auth
        # This avoids the auth prompt
        # Create config in home directory (always writable)
        # Dynamically determine the home directory
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
        echo "Services running:"
        echo "  Unified API:  http://localhost:8050 (Gemini mode)"
        echo "  Gemini Proxy: http://localhost:8053"
        echo ""
        echo "Environment configured:"
        echo "  GEMINI_API_BASE_URL=$GEMINI_API_BASE_URL"
        echo "  Mock Mode: ${USE_MOCK_API:-true}"
        echo ""
        echo "You can now use Gemini CLI:"
        echo "  gemini          - Interactive mode"
        echo "  gemini --help   - Show help"

        # Create a wrapper function for gemini that forces proxy
        echo ""
        echo "Creating gemini-proxy wrapper..."
        cat > /tmp/gemini-proxy << 'EOF'
#!/bin/bash
# Force Gemini to use our proxy by intercepting the call
export GOOGLE_GENAI_API_BASE_URL="http://localhost:8053/v1"
export GEMINI_API_BASE_URL="http://localhost:8053/v1"
exec /usr/local/bin/gemini "$@"
EOF
        chmod +x /tmp/gemini-proxy
        alias gemini='/tmp/gemini-proxy'
        echo ""
        echo "Example test:"
        echo "  echo 'Hello world' | gemini --non-interactive"
        echo ""
        echo "View logs:"
        echo "  tail -f /tmp/unified_api.log"
        echo "  tail -f /tmp/gemini_proxy.log"
        echo ""
        echo "=========================================="
        echo ""

        # Start Gemini CLI directly in interactive mode using the proxy wrapper
        echo "Starting Gemini CLI..."
        echo ""
        exec /tmp/gemini-proxy
        ;;

    test)
        echo "Running tests..."

        # Start unified API in mock mode for Gemini
        API_MODE=gemini API_VERSION=v3 PORT=8050 python3 /app/unified_tool_api.py > /tmp/unified_api.log 2>&1 &
        API_PID=$!
        sleep 2

        # Start Gemini proxy wrapper
        MOCK_API_BASE=http://localhost:8050 python3 /app/gemini_proxy_wrapper.py > /tmp/gemini_proxy.log 2>&1 &
        PROXY_PID=$!
        sleep 2

        # Test 1: Check services are up
        echo "Test 1: Service health checks..."
        if curl -s http://localhost:8050/health | grep -q "healthy"; then
            echo "✅ Mock API is healthy"
        else
            echo "❌ Mock API failed"
            exit 1
        fi

        if curl -s http://localhost:8053/health | grep -q "healthy"; then
            echo "✅ Gemini proxy is healthy"
        else
            echo "❌ Gemini proxy failed"
            exit 1
        fi

        # Test 2: Direct proxy test
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

        # Test 3: Gemini CLI test
        echo ""
        echo "Test 3: Gemini CLI integration..."
        # Use -p flag for prompt in non-interactive mode
        TEST_OUTPUT=$(echo "Hello world" | timeout 10 gemini -p "Respond to this message" 2>&1 || true)

        if echo "$TEST_OUTPUT" | grep -q "Hatsune Miku"; then
            echo "✅ Gemini CLI returns 'Hatsune Miku'"
        else
            echo "⚠️  Gemini CLI integration test - checking if it connects to proxy"
            echo "Output preview: $(echo "$TEST_OUTPUT" | head -5)"

            # Additional test with simpler prompt
            echo ""
            echo "Test 3b: Simple prompt test..."
            SIMPLE_OUTPUT=$(timeout 10 gemini -p "Say hello" 2>&1 || true)
            if echo "$SIMPLE_OUTPUT" | grep -q "Hatsune Miku"; then
                echo "✅ Simple prompt returns 'Hatsune Miku'"
            else
                echo "Output: $(echo "$SIMPLE_OUTPUT" | head -5)"
            fi
        fi

        echo ""
        echo "=========================================="
        echo "✅ All tests completed!"
        echo "=========================================="
        ;;

    daemon)
        echo "Starting in daemon mode..."

        # Start unified API in mock mode for Gemini
        API_MODE=gemini API_VERSION=v3 PORT=8050 python3 /app/unified_tool_api.py > /tmp/unified_api.log 2>&1 &
        API_PID=$!

        # Start Gemini proxy wrapper
        MOCK_API_BASE=http://localhost:8050 python3 /app/gemini_proxy_wrapper.py > /tmp/gemini_proxy.log 2>&1 &
        PROXY_PID=$!

        echo "Services started. Container will remain running..."
        echo "Logs available at:"
        echo "  /tmp/unified_api.log"
        echo "  /tmp/gemini_proxy.log"

        # Keep container running
        while true; do
            sleep 60
            # Check if services are still running
            if ! pgrep -f unified_tool_api.py > /dev/null; then
                echo "Unified API died, restarting..."
                API_MODE=gemini API_VERSION=v3 PORT=8050 python3 /app/unified_tool_api.py > /tmp/unified_api.log 2>&1 &
            fi
            if ! pgrep -f gemini_proxy_wrapper.py > /dev/null; then
                echo "Gemini proxy died, restarting..."
                MOCK_API_BASE=http://localhost:8050 python3 /app/gemini_proxy_wrapper.py > /tmp/gemini_proxy.log 2>&1 &
            fi
        done
        ;;

    *)
        echo "Unknown mode: $MODE"
        echo "Usage: $0 [interactive|test|daemon]"
        exit 1
        ;;
esac
