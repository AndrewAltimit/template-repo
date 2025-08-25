# Simple OpenCode Corporate Proxy Container
# Builds OpenCode from source and includes translation services

# Stage 1: Clone OpenCode source
FROM alpine/git AS source
ARG OPENCODE_VERSION=3edab6056042
WORKDIR /source
RUN git clone https://github.com/sst/opencode.git && \
    cd opencode && \
    if [ "$OPENCODE_VERSION" != "HEAD" ]; then \
        git checkout "$OPENCODE_VERSION"; \
    fi

# Stage 2: Build OpenCode
FROM oven/bun:1 AS builder
WORKDIR /build
COPY --from=source /source/opencode ./opencode
WORKDIR /build/opencode
RUN bun install
WORKDIR /build/opencode/packages/opencode
RUN bun build ./src/index.ts --compile --outfile opencode

# Stage 3: Runtime container
# Use debian-based image for glibc compatibility with bun-compiled binary
FROM node:20-slim

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

# Create a wrapper script to ensure OpenCode runs correctly
RUN echo '#!/bin/bash\nexec /usr/local/bin/opencode.bin "$@"' > /usr/local/bin/opencode && \
    chmod +x /usr/local/bin/opencode

# Install Python dependencies for proxy
RUN pip3 install --break-system-packages flask flask-cors requests

# Copy shared services (paths relative to corporate-proxy directory as build context)
COPY shared/services/mock_api.py /app/mock_api.py
COPY shared/services/translation_wrapper.py /app/translation_wrapper.py

# Copy startup script
COPY opencode/scripts/start-services.sh /app/start-services.sh
RUN chmod +x /app/start-services.sh

# Set proper ownership for app and workspace directories
# Create /workspace/opencode directory that OpenCode expects
RUN chown -R appuser:appuser /app && \
    mkdir -p /workspace/opencode && \
    chown -R appuser:appuser /workspace

WORKDIR /workspace

# Switch to the non-root user
USER appuser

# Environment variables for OpenCode to use our proxy
ENV OPENROUTER_API_KEY="test-secret-token-123"
ENV OPENROUTER_BASE_URL="http://localhost:8052/v1"

# Environment for proxy services
ENV COMPANY_API_BASE="http://localhost:8050"
ENV COMPANY_API_TOKEN="test-secret-token-123"
ENV WRAPPER_PORT="8052"
ENV MOCK_API_PORT="8050"

EXPOSE 8050 8052

ENTRYPOINT ["/app/start-services.sh"]
CMD ["bash"]
