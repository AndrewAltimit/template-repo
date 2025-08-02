# OpenRouter Agents Image with Node.js and Go
# For agents that can be fully containerized (OpenCode, Codex, Crush)

# Stage 1: Node.js base
FROM node:20-slim AS node-base

# Stage 2: Go base
FROM golang:1.21-bullseye AS go-base

# Stage 3: Final image
FROM python:3.11-slim

# Copy Node.js from official image
COPY --from=node-base /usr/local/bin/node /usr/local/bin/node
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-base /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node-base /usr/local/bin/npx /usr/local/bin/npx

# Copy Go from official image
COPY --from=go-base /usr/local/go /usr/local/go

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    jq \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

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
RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/* && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then ARCH="x64"; elif [ "$ARCH" = "arm64" ]; then ARCH="arm64"; fi && \
    wget -q "https://github.com/sst/opencode/releases/download/v0.3.112/opencode-linux-${ARCH}.zip" -O /tmp/opencode.zip && \
    unzip -q /tmp/opencode.zip -d /usr/local/bin/ && \
    rm /tmp/opencode.zip && \
    chmod +x /usr/local/bin/opencode

# Install Codex CLI - OpenAI's experimental coding agent
# Note: May show deprecation warnings for subdependencies (node-domexception, lodash.isequal, phin)
# These are dependency warnings, not warnings about codex itself - the tool is actively maintained
RUN npm install -g @openai/codex

# Install Crush/mods from Charm Bracelet - VERIFIED WORKING
RUN go install github.com/charmbracelet/mods@latest && \
    cp /root/go/bin/mods /usr/local/bin/mods && \
    ln -s /usr/local/bin/mods /usr/local/bin/crush

# Create working directory
WORKDIR /workspace

# Copy agent-specific requirements
COPY docker/requirements-agents.txt ./
RUN pip install --no-cache-dir -r requirements-agents.txt

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create directories for agent configs
RUN mkdir -p /root/.config/opencode \
    /root/.config/codex \
    /root/.config/mods \
    /home/agentuser/.config/mods

# Create a non-root user (will be overridden by docker-compose)
RUN useradd -m -u 1000 agentuser

# Copy mods configuration
COPY scripts/agents/config/mods-config.yml /root/.config/mods/config.yml
COPY scripts/agents/config/mods-config.yml /home/agentuser/.config/mods/config.yml
# Set ownership for the default user. Note: when running via docker-compose,
# the user is overridden by the host's USER_ID/GROUP_ID, and volume mount
# permissions will take precedence.
RUN chown -R agentuser:agentuser /home/agentuser/.config

# Default command
CMD ["bash"]
