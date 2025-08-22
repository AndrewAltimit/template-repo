# Dockerfile for OpenCode with integrated proxy support
FROM node:22-slim

# Install Python and required packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for proxy (using break-system-packages for container)
RUN pip3 install --no-cache-dir --break-system-packages flask flask-cors requests

# Install OpenCode CLI globally
RUN npm install -g opencode-ai

# Create workspace and config directories
WORKDIR /workspace
RUN mkdir -p ~/.config/opencode

# Copy proxy scripts
COPY automation/proxy/mock_company_api.py /workspace/automation/proxy/
COPY automation/proxy/api_translation_wrapper.py /workspace/automation/proxy/
COPY automation/proxy/container_entrypoint.sh /workspace/automation/proxy/

# Make scripts executable
RUN chmod +x /workspace/automation/proxy/*.sh

# Environment variables (can be overridden at runtime)
ENV USE_PROXY=true
ENV PROXY_MOCK_MODE=true
ENV COMPANY_API_BASE=http://localhost:8050
ENV COMPANY_API_TOKEN=test-secret-token-123
ENV OPENROUTER_API_KEY=test-key

# Use our improved entrypoint that properly configures OpenCode
ENTRYPOINT ["/workspace/automation/proxy/container_entrypoint.sh"]
CMD []
