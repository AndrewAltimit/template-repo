# Multi-stage build for Crush Company Integration
# Stage 1: Download prebuilt Crush binary
FROM alpine:3.20 AS downloader

# Copy and run corporate certificate installation script (as root)
COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

# Install dependencies for downloading
RUN apk add --no-cache curl tar

# Docker buildx automatically provides TARGETARCH
ARG TARGETARCH

# Crush version can be overridden at build time
# Example: docker build --build-arg CRUSH_VERSION=0.7.4 ...
ARG CRUSH_VERSION=0.7.4

# Map Docker arch to Crush release arch names
# amd64 -> x86_64, arm64 -> arm64 (not aarch64 for this release)
RUN echo "Building for architecture: ${TARGETARCH}"

# Download the Crush release binary for the target architecture
WORKDIR /tmp
RUN if [ "${TARGETARCH}" = "amd64" ]; then \
        CRUSH_ARCH="x86_64"; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
        CRUSH_ARCH="arm64"; \
    else \
        echo "Unsupported architecture: ${TARGETARCH}"; \
        exit 1; \
    fi && \
    echo "Downloading Crush version ${CRUSH_VERSION} for ${CRUSH_ARCH}" && \
    curl -L "https://github.com/charmbracelet/crush/releases/download/v${CRUSH_VERSION}/crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}.tar.gz" -o crush.tar.gz && \
    tar -xzf crush.tar.gz && \
    mv crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}/crush crush-binary && \
    chmod +x crush-binary

# Stage 2: Runtime with Python translation services
FROM python:3.11-alpine

# Copy and run corporate certificate installation script (as root)
COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

# Add a non-root user
RUN adduser -D -u 1001 appuser

# Install runtime dependencies (including terminal support)
RUN apk add --no-cache bash curl ncurses ncurses-terminfo

# Copy Crush binary from downloader (renamed to avoid conflict with wrapper)
COPY --from=downloader /tmp/crush-binary /usr/local/bin/crush-binary

# Install Python dependencies for translation services
RUN pip install --no-cache-dir flask flask-cors requests

# Copy shared services
COPY automation/corporate-proxy/shared/services/text_tool_parser.py /app/text_tool_parser.py
COPY automation/corporate-proxy/shared/services/translation_wrapper.py /app/translation_wrapper.py
COPY automation/corporate-proxy/shared/services/unified_tool_api.py /app/unified_tool_api.py

# Copy shared configs for translation wrapper
COPY automation/corporate-proxy/shared/configs /app/shared/configs

# Also copy tool_config.json to /configs/ where translation_wrapper expects it
COPY automation/corporate-proxy/shared/configs/tool_config.json /configs/tool_config.json
COPY automation/corporate-proxy/shared/configs/opencode_param_mappings.json /configs/opencode_param_mappings.json

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
ENV COMPANY_MOCK_MODE="true"
ENV COMPANY_START_WRAPPER="true"

# Expose ports
EXPOSE 8050 8052

# Start services with entrypoint to ensure they always run
ENTRYPOINT ["/app/start-services.sh"]
# No CMD - start-services.sh handles both interactive and command modes
