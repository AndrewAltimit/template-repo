# OpenRouter Agents Image with Node.js
# For agents that can be fully containerized (OpenCode, Crush)

# Build arguments for source images (must be built first)
ARG OPENCODE_IMAGE=template-repo-mcp-opencode:latest
ARG CRUSH_IMAGE=template-repo-mcp-crush:latest

# Stage 1: Build gh-validator from source
# Use bookworm-based rust image to match node:20-slim runtime glibc version
FROM rust:1.93-slim-bookworm AS gh-validator-builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY tools/rust/wrapper-common /build/wrapper-common
WORKDIR /build/gh-validator
COPY tools/rust/gh-validator/Cargo.toml tools/rust/gh-validator/Cargo.lock* ./
RUN mkdir -p src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true
COPY tools/rust/gh-validator/src ./src
RUN touch src/main.rs && cargo build --release

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

# Install gh-validator - shadows system gh via PATH priority
# /usr/local/bin comes before /usr/bin in PATH, so our validator runs first
# The validator finds the real gh at /usr/bin/gh automatically
COPY --from=gh-validator-builder /build/gh-validator/target/release/gh /usr/local/bin/gh
RUN chmod +x /usr/local/bin/gh

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

# Set ownership for all node user directories
# This ensures the user can write to all necessary locations
RUN chown -R node:node /home/node

# Security: gh-validator is installed at /usr/local/bin/gh and shadows /usr/bin/gh
# All gh commands pass through the validator which provides:
# - Secret masking (prevents accidental credential exposure)
# - Unicode emoji blocking (prevents display corruption)
# - Formatting enforcement (requires --body-file for reaction images)
# - URL validation with SSRF protection
# The real gh binary remains at /usr/bin/gh and is found automatically by the validator.

# Default command
CMD ["bash"]
