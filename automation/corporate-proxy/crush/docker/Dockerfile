# Multi-stage build for Crush Company Integration
# Stage 1: Download prebuilt Crush binary
FROM alpine:latest AS downloader

# Install dependencies for downloading
RUN apk add --no-cache curl tar

# Docker buildx automatically provides TARGETARCH
ARG TARGETARCH

# Crush version can be overridden at build time
# Example: docker build --build-arg CRUSH_VERSION=0.9.0-nightly ...
ARG CRUSH_VERSION=0.8.0-nightly

# Map Docker arch to Crush release arch names
# amd64 -> x86_64, arm64 -> aarch64
RUN echo "Building for architecture: ${TARGETARCH}"

# Download the nightly Crush release binary for the target architecture
WORKDIR /tmp
RUN if [ "${TARGETARCH}" = "amd64" ]; then \
        CRUSH_ARCH="x86_64"; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
        CRUSH_ARCH="aarch64"; \
    else \
        echo "Unsupported architecture: ${TARGETARCH}"; \
        exit 1; \
    fi && \
    echo "Downloading Crush version ${CRUSH_VERSION} for ${CRUSH_ARCH}" && \
    curl -L "https://github.com/charmbracelet/crush/releases/download/nightly/crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}.tar.gz" -o crush.tar.gz && \
    tar -xzf crush.tar.gz && \
    mv crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}/crush crush-binary && \
    chmod +x crush-binary

# Stage 2: Runtime with Python translation services
FROM python:3.11-alpine

# Add a non-root user
RUN adduser -D -u 1001 appuser

# Install runtime dependencies (including terminal support)
RUN apk add --no-cache bash curl ncurses ncurses-terminfo

# Copy Crush binary from downloader (renamed to avoid conflict with wrapper)
COPY --from=downloader /tmp/crush-binary /usr/local/bin/crush-binary

# Install Python dependencies for translation services
RUN pip install --no-cache-dir flask flask-cors requests

# Copy shared services
COPY automation/corporate-proxy/shared/services/translation_wrapper.py /app/translation_wrapper.py
COPY automation/corporate-proxy/shared/services/unified_tool_api.py /app/unified_tool_api.py

# Copy scripts
COPY automation/corporate-proxy/crush/scripts/start-services.sh /app/start-services.sh
COPY automation/corporate-proxy/crush/scripts/crush-wrapper.sh /usr/local/bin/crush
RUN chmod +x /app/start-services.sh /usr/local/bin/crush

# Create config directories with proper ownership
RUN mkdir -p /home/appuser/.config/crush && \
    mkdir -p /home/appuser/.local/share/crush && \
    mkdir -p /workspace && \
    chown -R appuser:appuser /home/appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /workspace

# Copy custom configuration (wrapper will place it correctly)
COPY automation/corporate-proxy/crush/config/crush-config.json /app/crush-config.json

# Set working directory
WORKDIR /workspace

# Switch to the non-root user
USER appuser

# Environment variables
ENV COMPANY_API_BASE="http://localhost:8050"
ENV COMPANY_API_TOKEN="test-secret-token-123"
ENV WRAPPER_PORT="8052"
ENV MOCK_API_PORT="8050"

# Expose ports
EXPOSE 8050 8052

# Start services with entrypoint to ensure they always run
ENTRYPOINT ["/app/start-services.sh"]
# No CMD - start-services.sh handles both interactive and command modes
