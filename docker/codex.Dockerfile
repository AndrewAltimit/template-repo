# Unified Codex Dockerfile
# Supports both codex-agent (CLI) and mcp-codex (MCP server) modes
# Build with: docker build --build-arg MODE=agent (or MODE=mcp)

ARG MODE=agent
ARG GH_VALIDATOR_IMAGE=template-repo-gh-validator:latest

# Import gh-validator binary from dedicated build image
FROM ${GH_VALIDATOR_IMAGE} AS gh-validator

# Use Python as base since both modes need it
FROM python:3.11-slim

# Install Node.js 20 and system dependencies in a single layer
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    jq \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (for agent operations)
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install gh-validator - shadows system gh with security wrapper
# Provides: secret masking, emoji blocking, URL validation, formatting enforcement
COPY --from=gh-validator /usr/local/bin/gh /usr/local/bin/gh-validator
RUN mv /usr/bin/gh /usr/bin/gh-real && \
    ln -sf /usr/local/bin/gh-validator /usr/bin/gh

# Install Codex CLI globally
RUN npm install -g @openai/codex

# Create non-root user with consistent UID
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/.codex \
             /home/user/.config \
             /home/user/.cache \
             /home/user/.local/share \
             /home/user/.local/bin && \
    chown -R user:user /home/user

# Set working directory
WORKDIR /workspace

# Copy and install Python requirements for MCP mode
COPY config/python/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy MCP modules (needed for MCP mode)
COPY tools/mcp/mcp_core /workspace/tools/mcp/mcp_core
COPY tools/mcp/mcp_codex /workspace/tools/mcp/mcp_codex

# Install MCP packages
RUN pip install --no-cache-dir /workspace/tools/mcp/mcp_core && \
    pip install --no-cache-dir /workspace/tools/mcp/mcp_codex

# Security: gh-validator is installed and shadows the system gh command.
# All gh commands pass through the validator which provides:
# - Secret masking (prevents accidental credential exposure)
# - Unicode emoji blocking (prevents display corruption)
# - Formatting enforcement (requires --body-file for reaction images)
# - URL validation with SSRF protection
# The real gh binary is preserved at /usr/bin/gh-real for direct access if needed.

# Copy entrypoint script
COPY docker/scripts/codex-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create runtime directories
RUN mkdir -p /tmp/codex-runtime && \
    chown -R user:user /tmp/codex-runtime /workspace

# Set environment variables
ENV PYTHONPATH=/workspace:$PYTHONPATH \
    NODE_ENV=production \
    HOME=/home/user \
    PATH="/home/user/.local/bin:${PATH}"

# Switch to non-root user
USER user

# Use entrypoint script to handle mode logic
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default command (can be overridden)
CMD []
