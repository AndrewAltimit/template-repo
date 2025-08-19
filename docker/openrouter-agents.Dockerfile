# OpenRouter Agents Image with Node.js
# For agents that can be fully containerized (OpenCode, Crush)

# Build arguments for source images (must be built first)
ARG OPENCODE_IMAGE=template-repo-mcp-opencode:latest
ARG CRUSH_IMAGE=template-repo-mcp-crush:latest

# Build stages to copy binaries from the dedicated images
FROM ${OPENCODE_IMAGE} AS opencode-source
FROM ${CRUSH_IMAGE} AS crush-source

# Use a base image that already has Node.js
FROM node:20-slim

# No need for version arguments - binaries come from the source images

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
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Use the existing node user (UID 1000) from the base image
# This avoids UID conflicts and maintains consistency

# Install GitHub CLI (for agent operations) - using official method
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built binaries from their respective images
# This ensures single source of truth for installation logic
COPY --from=opencode-source /usr/local/bin/opencode /usr/local/bin/opencode
COPY --from=crush-source /usr/local/bin/crush /usr/local/bin/crush

# Ensure binaries have correct permissions
RUN chmod +x /usr/local/bin/opencode /usr/local/bin/crush

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
