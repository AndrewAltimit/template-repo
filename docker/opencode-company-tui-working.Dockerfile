# OpenCode with Company Integration and Working TUI
# This version properly builds and includes the Go TUI binary

FROM golang:1.23 AS tui-builder

# Build the TUI binary
WORKDIR /build
RUN git clone --depth 1 https://github.com/sst/opencode.git

WORKDIR /build/opencode/packages/tui

# Enable Go toolchain to auto-download Go 1.24
ENV GOTOOLCHAIN=auto

# This will automatically download and use Go 1.24 as required by go.mod
RUN go mod download

# Build TUI for Linux x64 (for our container)
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-s -w" \
    -o tui-linux-x64 \
    ./cmd/opencode/main.go

# Also build for arm64 if needed
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build \
    -ldflags="-s -w" \
    -o tui-linux-arm64 \
    ./cmd/opencode/main.go

FROM oven/bun:1 AS opencode-builder

RUN apt-get update && apt-get install -y git curl build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth 1 https://github.com/sst/opencode.git

WORKDIR /build/opencode
RUN bun install

# Copy company models override
COPY docker/patches/company-override.json packages/opencode/src/company-models.json

# Copy models patch
COPY docker/patches/models-company-simple.ts packages/opencode/src/provider/models.ts

# Copy TUI fix patch
COPY docker/patches/tui-company-fix.ts packages/opencode/src/cli/cmd/tui.ts

# Build OpenCode
WORKDIR /build/opencode/packages/opencode
RUN bun build ./src/index.ts --compile --outfile opencode

# Runtime stage
FROM oven/bun:1-slim

RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled OpenCode binary
COPY --from=opencode-builder /build/opencode/packages/opencode/opencode /usr/local/bin/opencode
RUN chmod +x /usr/local/bin/opencode

# Copy TUI binaries to the cache directory where our patched code looks for them
RUN mkdir -p /home/bun/.cache/opencode/tui
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-x64 /home/bun/.cache/opencode/tui/
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-arm64 /home/bun/.cache/opencode/tui/
RUN chmod +x /home/bun/.cache/opencode/tui/*

# Also copy to /usr/local/bin as a fallback
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-x64 /usr/local/bin/opencode-tui
RUN chmod +x /usr/local/bin/opencode-tui

# Create config and cache directories with proper permissions
RUN mkdir -p /home/bun/.config/opencode /home/bun/.cache/opencode /home/bun/.local/share/opencode && \
    chown -R bun:bun /home/bun/.cache /home/bun/.config /home/bun/.local

# Ensure TUI binaries have correct permissions and test they're executable
RUN chmod 755 /home/bun/.cache/opencode/tui/* && \
    chown bun:bun /home/bun/.cache/opencode/tui/* && \
    /home/bun/.cache/opencode/tui/tui-linux-x64 --help 2>/dev/null || true

# Configure with standard openrouter model names
RUN echo '{"provider":{"openrouter":{"options":{"apiKey":"sk-company-mock-api-key-123"}}},"model":"openrouter/anthropic/claude-3.5-sonnet"}' > /home/bun/.config/opencode/.opencode.json

# Install Python dependencies for the proxy
RUN pip install --no-cache-dir --break-system-packages flask flask-cors requests

WORKDIR /workspace
COPY automation/proxy/mock_company_api.py .
COPY automation/proxy/company_translation_wrapper.py .

# Create a startup script
RUN echo '#!/bin/bash\n\
echo "[Company] Starting Company OpenCode Container"\n\
echo "[Company] TUI binaries are installed at:"\n\
ls -la /home/bun/.cache/opencode/tui/\n\
echo ""\n\
\n\
# Auto-start mock services if COMPANY_MOCK_MODE is set\n\
if [ "$COMPANY_MOCK_MODE" = "true" ]; then\n\
    echo "[Company] Mock mode enabled - starting services..."\n\
    echo "Starting mock API on port 8050..."\n\
    python3 /workspace/mock_company_api.py > /tmp/mock_api.log 2>&1 &\n\
    MOCK_PID=$!\n\
    echo "Mock API started (PID: $MOCK_PID)"\n\
    \n\
    echo "Starting translation wrapper on port 8052..."\n\
    python3 /workspace/company_translation_wrapper.py > /tmp/wrapper.log 2>&1 &\n\
    WRAPPER_PID=$!\n\
    echo "Translation wrapper started (PID: $WRAPPER_PID)"\n\
    \n\
    # Wait for services to be ready\n\
    sleep 2\n\
    \n\
    # Check if services are running\n\
    if nc -z localhost 8050 2>/dev/null; then\n\
        echo "✅ Mock API is running on port 8050"\n\
    else\n\
        echo "⚠️  Mock API failed to start - check /tmp/mock_api.log"\n\
    fi\n\
    \n\
    if nc -z localhost 8052 2>/dev/null; then\n\
        echo "✅ Translation wrapper is running on port 8052"\n\
    else\n\
        echo "⚠️  Translation wrapper failed to start - check /tmp/wrapper.log"\n\
    fi\n\
    echo ""\n\
    echo "[Company] Mock services started! Ready to use OpenCode."\n\
else\n\
    echo "[Company] Mock mode disabled. To enable, set COMPANY_MOCK_MODE=true"\n\
    echo "[Company] Manual commands:"\n\
    echo "  python3 mock_company_api.py &"\n\
    echo "  python3 company_translation_wrapper.py &"\n\
fi\n\
\n\
# Function to cleanup background processes on exit\n\
cleanup() {\n\
    echo ""\n\
    echo "[Company] Shutting down services..."\n\
    pkill -f mock_company_api.py 2>/dev/null || true\n\
    pkill -f company_translation_wrapper.py 2>/dev/null || true\n\
    exit 0\n\
}\n\
\n\
# Set up cleanup trap\n\
trap cleanup EXIT INT TERM\n\
\n\
# Check if we should auto-start OpenCode\n\
if [ "$COMPANY_AUTO_START" = "true" ]; then\n\
    echo ""\n\
    echo "[Company] Auto-starting OpenCode TUI..."\n\
    echo "========================================"\n\
    echo ""\n\
    # Give a moment for user to see startup messages\n\
    sleep 1\n\
    # Start OpenCode TUI directly\n\
    exec opencode\n\
else\n\
    echo ""\n\
    echo "[Company] Available commands:"\n\
    echo "  opencode         - Start TUI (interactive mode)"\n\
    echo "  opencode serve   - Start headless server"\n\
    echo "  opencode run \"prompt\" - Run a single prompt"\n\
    echo "  opencode models  - List available models"\n\
    echo ""\n\
    echo "[Company] To auto-start TUI, set COMPANY_AUTO_START=true"\n\
    echo ""\n\
    exec bash\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENV OPENROUTER_API_KEY=sk-company-mock-api-key-123
ENV HOME=/home/bun

USER bun

ENTRYPOINT ["/entrypoint.sh"]
