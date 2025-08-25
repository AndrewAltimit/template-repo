# OpenCode with Company Integration and Working TUI
# This version properly builds and includes the Go TUI binary

# Pin to a specific version for reproducible builds
# Update this commit hash when you want to upgrade OpenCode
# Latest stable as of 2024-12: 3edab6056042
ARG OPENCODE_VERSION=3edab6056042

# Clone the repository once for both builders
FROM alpine/git AS source
ARG OPENCODE_VERSION
WORKDIR /source
RUN git clone https://github.com/sst/opencode.git && \
    cd opencode && \
    if [ "$OPENCODE_VERSION" != "HEAD" ]; then \
        git checkout "$OPENCODE_VERSION"; \
    fi

FROM golang:1.23 AS tui-builder

# Copy source from common stage
WORKDIR /build
COPY --from=source /source/opencode ./opencode

WORKDIR /build/opencode/packages/tui

# Enable Go toolchain to auto-download Go 1.24
ENV GOTOOLCHAIN=auto

# This will automatically download and use Go 1.24 as required by go.mod
RUN go mod download

# Build TUI for the target architecture only
# TARGETARCH is automatically set by Docker buildx
ARG TARGETARCH=amd64
RUN CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} go build \
    -ldflags="-s -w" \
    -o tui-linux-${TARGETARCH} \
    ./cmd/opencode/main.go

FROM oven/bun:1 AS opencode-builder

RUN apt-get update && apt-get install -y curl build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /build
# Copy source from common stage
COPY --from=source /source/opencode ./opencode

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

# Copy TUI binary for the target architecture
ARG TARGETARCH=amd64
RUN mkdir -p /home/bun/.cache/opencode/tui
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-${TARGETARCH} /home/bun/.cache/opencode/tui/tui-linux-x64
RUN chmod +x /home/bun/.cache/opencode/tui/*

# Also copy to /usr/local/bin as a fallback
COPY --from=tui-builder /build/opencode/packages/tui/tui-linux-${TARGETARCH} /usr/local/bin/opencode-tui
RUN chmod +x /usr/local/bin/opencode-tui

# Create config and cache directories with proper permissions
RUN mkdir -p /home/bun/.config/opencode /home/bun/.cache/opencode /home/bun/.local/share/opencode && \
    chown -R bun:bun /home/bun/.cache /home/bun/.config /home/bun/.local

# Ensure TUI binary has correct permissions and test it's executable
RUN chmod 755 /home/bun/.cache/opencode/tui/* && \
    chown bun:bun /home/bun/.cache/opencode/tui/* && \
    /home/bun/.cache/opencode/tui/tui-linux-x64 --help 2>/dev/null || true

# Note: Configuration will be generated at runtime by entrypoint script
# This ensures proper API key management and dynamic port configuration

# Install Python dependencies for the proxy
RUN pip install --no-cache-dir --break-system-packages flask flask-cors requests

WORKDIR /workspace
# Note: This Dockerfile is deprecated. Use automation/corporate-proxy/opencode/docker/Dockerfile instead
# Legacy file copies - these files have been moved:
# COPY automation/proxy/mock_company_api.py . (moved to automation/corporate-proxy/shared/services/mock_api.py)
# COPY automation/proxy/company_translation_wrapper.py . (moved to automation/corporate-proxy/shared/services/translation_wrapper.py)
# For now, copy from new location for backward compatibility
COPY automation/corporate-proxy/shared/services/mock_api.py ./mock_company_api.py
COPY automation/corporate-proxy/shared/services/translation_wrapper.py ./company_translation_wrapper.py

# Copy entrypoint script from repository
COPY docker/entrypoints/opencode-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV HOME=/home/bun

USER bun

ENTRYPOINT ["/entrypoint.sh"]
