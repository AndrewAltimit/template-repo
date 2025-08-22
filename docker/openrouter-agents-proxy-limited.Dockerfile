# OpenRouter Agents with Limited Model Display
# This version intercepts models.dev API to show only proxy models

# Build arguments for source images
ARG OPENCODE_IMAGE=template-repo-mcp-opencode:latest
ARG CRUSH_IMAGE=template-repo-mcp-crush:latest

# Build stages to copy binaries from the dedicated images
FROM ${OPENCODE_IMAGE} AS opencode-source
FROM ${CRUSH_IMAGE} AS crush-source

# Use a base image that already has Node.js
FROM node:20-slim

# Install Python 3.11 and all system dependencies in one layer
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    wget \
    jq \
    unzip \
    tar \
    netcat-openbsd \
    dnsmasq \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Install GitHub CLI (for agent operations)
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built binaries from their respective images
COPY --from=opencode-source /usr/local/bin/opencode /usr/local/bin/opencode
COPY --from=crush-source /usr/local/bin/crush /usr/local/bin/crush

# Ensure binaries have correct permissions
RUN chmod +x /usr/local/bin/opencode /usr/local/bin/crush

# Create working directory
WORKDIR /workspace

# Copy proxy scripts and configurations
COPY automation/proxy/ /workspace/automation/proxy/

# Make scripts executable
RUN chmod +x /workspace/automation/proxy/*.sh

# Copy agent-specific requirements
COPY docker/requirements/requirements-agents.txt ./
COPY docker/requirements/requirements-proxy.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements-agents.txt && \
    pip install --no-cache-dir --break-system-packages -r requirements-proxy.txt

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create necessary directories for node user
RUN mkdir -p /home/node/.config/opencode \
    /home/node/.cache/opencode \
    /home/node/.local/share/opencode

# Copy OpenCode configuration
COPY docker/patches/opencode-config.json /home/node/.config/opencode/.opencode.json

# Create startup script that intercepts models.dev
RUN cat > /usr/local/bin/start-limited-proxy.sh << 'EOF'
#!/bin/bash
set -e

# Start the models interceptor in background
echo "Starting models.dev interceptor..."
python3 /workspace/automation/proxy/models-interceptor.py > /tmp/models-interceptor.log 2>&1 &

# Wait for interceptor
sleep 2

# Add hosts entry to redirect models.dev to our interceptor
echo "127.0.0.1 models.dev" >> /etc/hosts

# Start the regular proxy wrapper
exec /workspace/automation/proxy/opencode-proxy-wrapper.sh "$@"
EOF
RUN chmod +x /usr/local/bin/start-limited-proxy.sh

# Set ownership
RUN chown -R node:node /home/node /workspace

# Set environment to enable proxy by default
ENV USE_PROXY=true \
    PROXY_MOCK_MODE=true

# Note: We need to run as root to modify /etc/hosts
# This is a limitation of the interceptor approach
USER root

# Default command - start with interceptor
CMD ["/usr/local/bin/start-limited-proxy.sh"]
