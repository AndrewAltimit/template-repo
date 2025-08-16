# OpenRouter Agents Image with Node.js and Go
# For agents that can be fully containerized (OpenCode, Crush)

# Use a base image that already has Node.js
FROM node:20-slim

# Define version arguments for better maintainability
ARG GO_VERSION=1.24.5
ARG GO_CHECKSUM_AMD64=10ad9e86233e74c0f6590fe5426895de6bf388964210eac34a6d83f38918ecdc
ARG GO_CHECKSUM_ARM64=44e2d8b8e1b24a87dcab8c0bbf673cfcf92dc2ac0b3094df48b5c7fdb670cd5e
ARG OPENCODE_VERSION=0.3.112
ARG OPENCODE_CHECKSUM_AMD64=ce02926bbe94ca91c5a46e97565e3f8d275f1a6c2fd3352f7f99f558f6b60e09
ARG OPENCODE_CHECKSUM_ARM64=6ceae43795a62b572866e50d30d99e266889b6aeae1da058aab34041cc5d49d8
# Crush doesn't have stable releases yet, using latest

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

# Use the existing node user (UID 1000) from the base image
# This avoids UID conflicts and maintains consistency

# Install Go in a separate layer (large download)
# Checksum from https://go.dev/dl/
# Support multiple architectures using Docker's built-in TARGETARCH variable
ARG TARGETARCH=amd64
RUN wget -q https://go.dev/dl/go${GO_VERSION}.linux-${TARGETARCH}.tar.gz && \
    if [ "${TARGETARCH}" = "amd64" ]; then \
        echo "${GO_CHECKSUM_AMD64}  go${GO_VERSION}.linux-${TARGETARCH}.tar.gz" | sha256sum -c -; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
        echo "${GO_CHECKSUM_ARM64}  go${GO_VERSION}.linux-${TARGETARCH}.tar.gz" | sha256sum -c -; \
    fi && \
    tar -C /usr/local -xzf go${GO_VERSION}.linux-${TARGETARCH}.tar.gz && \
    rm go${GO_VERSION}.linux-${TARGETARCH}.tar.gz

# Set Go environment variables
ENV PATH="/usr/local/go/bin:/home/node/go/bin:${PATH}"
ENV GOPATH="/home/node/go"

# Install GitHub CLI (for agent operations) - using official method
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install OpenRouter-compatible CLI tools

# Install OpenCode from GitHub releases
# SECURITY: We verify checksums to ensure binary integrity
# Checksums calculated on 2025-08-03 for v0.3.112 release
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        ARCH="x64"; \
        CHECKSUM="${OPENCODE_CHECKSUM_AMD64}"; \
    elif [ "$ARCH" = "arm64" ]; then \
        ARCH="arm64"; \
        CHECKSUM="${OPENCODE_CHECKSUM_ARM64}"; \
    fi && \
    wget -q "https://github.com/sst/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${ARCH}.zip" -O /tmp/opencode.zip && \
    echo "${CHECKSUM}  /tmp/opencode.zip" | sha256sum -c - && \
    unzip -q /tmp/opencode.zip -d /usr/local/bin/ && \
    rm /tmp/opencode.zip && \
    chmod +x /usr/local/bin/opencode


# Install Crush from Charm Bracelet - AI-powered shell
# Crush is an AI-powered shell assistant from Charm Bracelet
ENV GOBIN=/usr/local/bin
RUN go install github.com/charmbracelet/crush@latest

# Create working directory
WORKDIR /workspace

# Change ownership of workspace to node user
RUN chown -R node:node /workspace

# Copy agent-specific requirements
COPY docker/requirements/requirements-agents.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements-agents.txt

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create necessary directories for node user
RUN mkdir -p /home/node/.config/opencode \
    /home/node/.config/crush \
    /home/node/.cache \
    /home/node/.cache/opencode \
    /home/node/.cache/crush \
    /home/node/.local \
    /home/node/.local/share \
    /home/node/.local/share/opencode \
    /home/node/.local/share/crush \
    /home/node/.local/bin

# Copy configurations for each agent
# OpenCode configuration
COPY --chown=node:node packages/github_ai_agents/configs/opencode-config.json /home/node/.config/opencode/.opencode.json

# Crush configuration - copy JSON config to multiple expected locations
COPY --chown=node:node packages/github_ai_agents/configs/crush.json /home/node/.config/crush/crush.json
COPY --chown=node:node packages/github_ai_agents/configs/crush-data.json /home/node/.local/share/crush/crush.json

# Also copy the .crush directory with database (for any cached data) - skip if not present

# Set ownership for all node user directories
# This ensures the user can write to all necessary locations
RUN chown -R node:node /home/node

# Copy security hooks and set up alias
COPY automation/security /app/security
RUN chmod +x /app/security/*.sh && \
    echo 'alias gh="/app/security/gh-wrapper.sh"' >> /etc/bash.bashrc

# Default command
CMD ["bash"]
