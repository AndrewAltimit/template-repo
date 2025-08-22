# OpenCode built from source with patched provider configuration
# This builds OpenCode from source to allow customizing the provider list

# Build stage for OpenCode
FROM oven/bun:1 AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Clone OpenCode source
WORKDIR /build
RUN git clone --depth 1 https://github.com/sst/opencode.git

# Change to OpenCode directory
WORKDIR /build/opencode

# Install dependencies using Bun
RUN bun install

# Copy patch files
COPY docker/patches/proxy-models.json packages/opencode/src/proxy-models.json
COPY docker/patches/opencode-models.patch packages/opencode/src/provider/models.ts
COPY docker/patches/models-macro.patch packages/opencode/src/provider/models-macro.ts

# Build OpenCode with Bun
RUN cd packages/opencode && bun build ./src/index.ts --compile --outfile opencode

# Final stage with our custom OpenCode
FROM node:20-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    wget \
    jq \
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

# Copy built OpenCode from builder stage
COPY --from=builder /build/opencode/packages/opencode/opencode /usr/local/bin/opencode

# Make it executable
RUN chmod +x /usr/local/bin/opencode

# Use the existing node user (UID 1000) from the base image
# Create necessary directories for node user
RUN mkdir -p /home/node/.config/opencode \
    /home/node/.cache/opencode \
    /home/node/.local/share/opencode

# Copy OpenCode configuration that uses our proxy
# This hijacks the OpenRouter provider to point to our proxy
COPY --chown=node:node docker/patches/opencode-config.json /home/node/.config/opencode/.opencode.json

# Set ownership for all node user directories
RUN chown -R node:node /home/node

# Create working directory
WORKDIR /workspace
RUN chown -R node:node /workspace

# Copy agent-specific requirements
COPY docker/requirements/requirements-agents.txt ./
RUN pip install --no-cache-dir --break-system-packages -r requirements-agents.txt

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Set fake OpenRouter API key (our proxy doesn't use it but OpenCode needs it)
ENV OPENROUTER_API_KEY=proxy-key

# Switch to node user
USER node

# Set HOME to ensure opencode finds its config
ENV HOME=/home/node

# Default command
CMD ["bash"]
