# Codex Agent Image with Node.js
# For the OpenAI Codex CLI tool

# Use Node.js 20 slim as base (Codex requires Node.js)
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    wget \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python (if needed for any helper scripts)
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Install GitHub CLI (for potential agent operations)
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install Codex CLI globally
RUN npm install -g @openai/codex

# Create working directory
WORKDIR /workspace

# Use the existing node user (UID 1000) from the base image
# This avoids UID conflicts and maintains consistency

# Create necessary directories for node user
RUN mkdir -p /home/node/.codex \
    /home/node/.config \
    /home/node/.cache \
    /home/node/.local \
    /home/node/.local/share \
    /home/node/.local/bin

# Change ownership of workspace and home directories to node user
RUN chown -R node:node /workspace /home/node

# Copy security hooks and set up alias (if needed)
COPY automation/security /app/security
RUN chmod +x /app/security/*.sh && \
    echo 'alias gh="/app/security/gh-wrapper.sh"' >> /etc/bash.bashrc

# Set environment variables
ENV NODE_ENV=production \
    PATH="/home/node/.local/bin:${PATH}"

# Switch to node user
USER node

# Default command
CMD ["bash"]
