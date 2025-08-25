# Multi-stage build for Crush Company Integration
# Stage 1: Download prebuilt Crush binary
FROM alpine:latest AS downloader

# Install dependencies for downloading
RUN apk add --no-cache curl tar

# Download the nightly Crush release binary for Linux
WORKDIR /tmp
RUN curl -L https://github.com/charmbracelet/crush/releases/download/nightly/crush_0.8.0-nightly_Linux_x86_64.tar.gz -o crush.tar.gz && \
    tar -xzf crush.tar.gz && \
    chmod +x crush_0.8.0-nightly_Linux_x86_64/crush

# Stage 2: Runtime with Python translation services
FROM python:3.11-alpine

# Add a non-root user
RUN adduser -D -u 1001 appuser

# Install runtime dependencies
RUN apk add --no-cache bash curl

# Copy Crush binary from downloader (renamed to avoid conflict with wrapper)
COPY --from=downloader /tmp/crush_0.8.0-nightly_Linux_x86_64/crush /usr/local/bin/crush-binary

# Install Python dependencies for translation services
RUN pip install --no-cache-dir flask flask-cors requests

# Copy shared services
COPY shared/services/translation_wrapper.py /app/translation_wrapper.py
COPY shared/services/mock_api.py /app/mock_api.py

# Copy scripts
COPY crush/scripts/start-services.sh /app/start-services.sh
COPY crush/scripts/crush-wrapper.sh /usr/local/bin/crush
RUN chmod +x /app/start-services.sh /usr/local/bin/crush

# Create config directories with proper ownership
RUN mkdir -p /home/appuser/.config/crush && \
    mkdir -p /home/appuser/.local/share/crush && \
    mkdir -p /workspace && \
    chown -R appuser:appuser /home/appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /workspace

# Copy custom configuration (wrapper will place it correctly)
COPY crush/config/crush-config.json /app/crush-config.json

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
CMD ["bash"]
