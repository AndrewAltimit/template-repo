# OpenRouter Agents Image with Node.js and Go
# For agents that can be fully containerized (OpenCode, Codex, Crush)

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
    build-essential \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Install Go in a separate layer (large download)
# Checksum from https://go.dev/dl/
RUN wget -q https://go.dev/dl/go1.24.5.linux-amd64.tar.gz && \
    echo "10ad9e86233e74c0f6590fe5426895de6bf388964210eac34a6d83f38918ecdc  go1.24.5.linux-amd64.tar.gz" | sha256sum -c - && \
    tar -C /usr/local -xzf go1.24.5.linux-amd64.tar.gz && \
    rm go1.24.5.linux-amd64.tar.gz

# Set Go environment variables
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"
ENV GOPATH="/root/go"

# Install GitHub CLI (for agent operations) - using official method
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install OpenRouter-compatible CLI tools

# Install OpenCode from GitHub releases (v0.3.112)
# SECURITY: We verify checksums to ensure binary integrity
# Checksums calculated on 2025-08-03 for v0.3.112 release
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        ARCH="x64"; \
        CHECKSUM="ce02926bbe94ca91c5a46e97565e3f8d275f1a6c2fd3352f7f99f558f6b60e09"; \
    elif [ "$ARCH" = "arm64" ]; then \
        ARCH="arm64"; \
        CHECKSUM="6ceae43795a62b572866e50d30d99e266889b6aeae1da058aab34041cc5d49d8"; \
    fi && \
    wget -q "https://github.com/sst/opencode/releases/download/v0.3.112/opencode-linux-${ARCH}.zip" -O /tmp/opencode.zip && \
    echo "${CHECKSUM}  /tmp/opencode.zip" | sha256sum -c - && \
    unzip -q /tmp/opencode.zip -d /usr/local/bin/ && \
    rm /tmp/opencode.zip && \
    chmod +x /usr/local/bin/opencode

# Install Codex CLI - OpenAI's experimental coding agent
# Note: May show deprecation warnings for subdependencies (node-domexception, lodash.isequal, phin)
# These are dependency warnings, not warnings about codex itself - the tool is actively maintained
RUN npm install -g @openai/codex

# Install Crush/mods from Charm Bracelet - VERIFIED WORKING
# Pin to specific version for reproducible builds
RUN go install github.com/charmbracelet/mods@v1.8.1 && \
    cp /root/go/bin/mods /usr/local/bin/mods && \
    ln -s /usr/local/bin/mods /usr/local/bin/crush

# Create working directory
WORKDIR /workspace

# Copy agent-specific requirements
COPY docker/requirements-agents.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements-agents.txt

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# The node:20-slim image already has a "node" user with UID 1000
# We'll use that user and create directories in the node home directory

# Create all necessary directories for both root and node user
RUN mkdir -p /root/.config/opencode \
    /root/.config/codex \
    /root/.config/mods \
    /home/node/.config/opencode \
    /home/node/.config/codex \
    /home/node/.config/mods \
    /home/node/.cache \
    /home/node/.cache/opencode \
    /home/node/.cache/codex \
    /home/node/.cache/mods \
    /home/node/.local \
    /home/node/.local/share \
    /home/node/.local/bin

# Copy mods configuration (only for node user since container runs as node)
COPY --chown=node:node packages/github_ai_agents/configs/mods-config.yml /home/node/.config/mods/config.yml

# Set ownership for all node directories
# This ensures the user can write to all necessary locations
RUN chown -R node:node /home/node

# Default command
CMD ["bash"]
