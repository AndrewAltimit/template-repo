# Simple OpenCode Corporate Proxy Container
# Builds OpenCode from source and includes translation services

# Stage 1: Clone OpenCode source
FROM alpine/git AS source

# Copy and run corporate certificate installation script (as root)
COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

ARG OPENCODE_VERSION=3edab6056042
WORKDIR /source
RUN git clone https://github.com/sst/opencode.git && \
    cd opencode && \
    if [ "$OPENCODE_VERSION" != "HEAD" ]; then \
        git checkout "$OPENCODE_VERSION"; \
    fi

# Stage 2: Build TUI with Go
FROM golang:1.23 AS tui-builder

# Copy and run corporate certificate installation script (as root)
COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

WORKDIR /build
COPY --from=source /source/opencode ./opencode
WORKDIR /build/opencode/packages/tui

# Enable Go toolchain to auto-download if needed
ENV GOTOOLCHAIN=auto

# Download dependencies
RUN go mod download || true

# Build TUI for the target architecture
# Docker buildx automatically provides TARGETARCH
ARG TARGETARCH
RUN echo "Building for architecture: ${TARGETARCH}" && \
    if [ -f "./cmd/opencode/main.go" ]; then \
        CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} go build \
        -ldflags="-s -w" \
        -o tui-linux-${TARGETARCH} \
        ./cmd/opencode/main.go; \
    elif [ -f "main.go" ]; then \
        CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} go build \
        -ldflags="-s -w" \
        -o tui-linux-${TARGETARCH} \
        main.go; \
    else \
        echo "Warning: TUI source not found, creating placeholder"; \
        echo '#!/bin/sh' > tui-linux-${TARGETARCH}; \
        echo 'echo "TUI not available in this build"' >> tui-linux-${TARGETARCH}; \
        chmod +x tui-linux-${TARGETARCH}; \
    fi

# Stage 3: Build OpenCode
FROM oven/bun:1 AS builder

# Copy and run corporate certificate installation script (as root)
COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

WORKDIR /build
COPY --from=source /source/opencode ./opencode

# Apply patches to customize OpenCode for corporate proxy
# These patches configure models and API endpoints at build time
COPY automation/corporate-proxy/shared/patches/company-override.json /build/opencode/packages/opencode/src/company-models.json
COPY automation/corporate-proxy/shared/patches/models-company-simple.ts /build/opencode/packages/opencode/src/provider/models.ts
COPY automation/corporate-proxy/shared/patches/tui-company-fix.ts /build/opencode/packages/opencode/src/cli/cmd/tui.ts

WORKDIR /build/opencode
RUN bun install
WORKDIR /build/opencode/packages/opencode
RUN bun build ./src/index.ts --compile --outfile opencode

# Stage 4: Runtime container
# Use debian-based image for glibc compatibility with bun-compiled binary
FROM node:20-slim

# Copy and run corporate certificate installation script (as root)
COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

# Add a non-root user
RUN useradd -m -u 1001 appuser

# Install Python for proxy services and runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    bash curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy the compiled OpenCode binary
COPY --from=builder /build/opencode/packages/opencode/opencode /usr/local/bin/opencode.bin
RUN chmod +x /usr/local/bin/opencode.bin

# Create TUI directory structure
RUN mkdir -p /home/appuser/.cache/opencode/tui

# Copy TUI binary for the target architecture
# Docker buildx automatically provides TARGETARCH
ARG TARGETARCH
# Always copy to the path expected by the patched application ('tui-linux-x64')
# This ensures compatibility across all architectures
RUN echo "Copying TUI for architecture: ${TARGETARCH}"
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-${TARGETARCH} /home/appuser/.cache/opencode/tui/tui-linux-x64
RUN chmod +x /home/appuser/.cache/opencode/tui/tui-linux-x64

# Also copy to alternate location for compatibility
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-${TARGETARCH} /usr/local/bin/opencode-tui
RUN chmod +x /usr/local/bin/opencode-tui

# Create a wrapper script to ensure OpenCode runs correctly
RUN echo '#!/bin/bash\nexec /usr/local/bin/opencode.bin "$@"' > /usr/local/bin/opencode && \
    chmod +x /usr/local/bin/opencode

# Install Python dependencies for proxy
RUN pip3 install --break-system-packages flask flask-cors requests

# Copy shared services
COPY automation/corporate-proxy/shared/services/text_tool_parser.py /app/text_tool_parser.py
COPY automation/corporate-proxy/shared/services/translation_wrapper.py /app/translation_wrapper.py
COPY automation/corporate-proxy/shared/services/unified_tool_api.py /app/unified_tool_api.py

# Copy shared configs for translation wrapper
COPY automation/corporate-proxy/shared/configs /app/shared/configs

# Also copy tool_config.json to /configs/ where translation_wrapper expects it
COPY automation/corporate-proxy/shared/configs/tool_config.json /configs/tool_config.json
COPY automation/corporate-proxy/shared/configs/opencode_param_mappings.json /configs/opencode_param_mappings.json

# Copy startup script
COPY automation/corporate-proxy/opencode/scripts/start-services.sh /app/start-services.sh
RUN chmod +x /app/start-services.sh

# Create OpenCode config directories and Bun directories
RUN mkdir -p /home/appuser/.config/opencode /home/appuser/.cache/opencode && \
    mkdir -p /home/appuser/.local/share /home/appuser/.local/bin && \
    chown -R appuser:appuser /home/appuser/.config /home/appuser/.cache /home/appuser/.local

# Set proper ownership for app and workspace directories
# Create /workspace/opencode directory that OpenCode expects
RUN chown -R appuser:appuser /app && \
    mkdir -p /workspace/opencode && \
    chown -R appuser:appuser /workspace

WORKDIR /workspace

# Switch to the non-root user
USER appuser

# Set HOME for OpenCode to find config
ENV HOME=/home/appuser

# Environment variables for OpenCode to use our proxy
ENV OPENROUTER_API_KEY="test-secret-token-123"
ENV OPENROUTER_BASE_URL="http://localhost:8052/v1"

# Environment for proxy services
ENV COMPANY_API_BASE="http://localhost:8050"
ENV COMPANY_API_TOKEN="test-secret-token-123"
ENV WRAPPER_PORT="8052"
ENV MOCK_API_PORT="8050"
ENV AGENT_CLIENT="opencode"

EXPOSE 8050 8052

ENTRYPOINT ["/app/start-services.sh"]
CMD ["bash"]
