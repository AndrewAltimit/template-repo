# Dockerfile for Autonomous Economic Agents
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies including build tools for Node.js native modules
RUN apt-get update && apt-get install -y \
    git \
    curl \
    bash \
    build-essential \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for Claude (required for --dangerously-skip-permissions)
RUN useradd -m -u 1000 -s /bin/bash claude && \
    echo "claude ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Install NVM and Node.js for claude user
USER claude
WORKDIR /home/claude

ENV NVM_DIR=/home/claude/.nvm
ENV NODE_VERSION=22.16.0

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && \
    bash -c "source $NVM_DIR/nvm.sh && nvm install $NODE_VERSION && nvm use $NODE_VERSION && nvm alias default $NODE_VERSION"

# Add NVM, Node, and npm to PATH for claude user
ENV PATH="$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH"

# Install Claude CLI globally for claude user
RUN bash -c "source $NVM_DIR/nvm.sh && npm install -g @anthropic-ai/claude-code"

# Switch back to root for copying files, then switch to claude
USER root
WORKDIR /app

# Copy package files
COPY pyproject.toml README.md ./
COPY economic_agents/ ./economic_agents/
COPY tests/ ./tests/

# Install Python dependencies
# Install with all extras for full functionality
RUN pip install --no-cache-dir -e ".[all]"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Give claude user ownership of /app
RUN chown -R claude:claude /app

# Create log directories with proper permissions
# Note: Log persistence is handled by Docker volume mount in docker-compose.yml
RUN mkdir -p /app/logs/resources /app/logs/metrics /app/logs/alignment \
             /app/logs/decisions /app/logs/observability/reports && \
    chown -R claude:claude /app/logs

# Switch to claude user for runtime
USER claude

# Set up NVM environment for runtime
ENV NVM_DIR=/home/claude/.nvm
ENV PATH="$NVM_DIR/versions/node/v22.16.0/bin:$PATH"

# Default command
CMD ["/bin/bash"]
