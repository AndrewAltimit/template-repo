# AI Agents Image with Python and GitHub CLI
FROM python:3.13-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    jq \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Node.js from the official image (Claude Code needs Node >= 22; bookworm ships 18)
COPY --from=node:26-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:26-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code and Gemini CLI globally (will use mounted credentials from host)
# The package is @anthropic-ai/claude-code but the CLI command is just 'claude'
RUN npm install -g @anthropic-ai/claude-code@2.1.312 @google/gemini-cli@0.29.5 && \
    # Fail the build if the claude entry point did not land on PATH
    command -v claude

# Create working directory
WORKDIR /workspace

# Copy agent-specific requirements
COPY docker/requirements/requirements-agents.txt ./
RUN pip install --no-cache-dir -r requirements-agents.txt

# Python environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 agentuser

# Default command
CMD ["bash"]
