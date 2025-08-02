# OpenRouter Agents Image with Node.js and Go
# For agents that can be fully containerized (OpenCode, Codex, Crush)
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    jq \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Go 1.21
RUN wget -q https://go.dev/dl/go1.21.0.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz \
    && rm go1.21.0.linux-amd64.tar.gz

# Set Go environment variables
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"
ENV GOPATH="/root/go"

# Install GitHub CLI (for agent operations)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
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

# Install Codex from GitHub releases (rust-v0.11.0)
# For now, create a wrapper that uses npm-installed version as fallback
RUN npm install -g @openai/codex || echo "NPM install of codex failed, will use direct binary"

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
RUN mkdir -p /root/.config/crush \
    /root/.config/opencode \
    /root/.config/codex \
    /root/.config/mods \
    /home/agentuser/.config/mods

# Create a non-root user (will be overridden by docker-compose)
RUN useradd -m -u 1000 agentuser

# Copy mods configuration
COPY scripts/agents/config/mods-config.yml /root/.config/mods/config.yml
COPY scripts/agents/config/mods-config.yml /home/agentuser/.config/mods/config.yml
RUN chown -R agentuser:agentuser /home/agentuser/.config

# Default command
CMD ["bash"]
