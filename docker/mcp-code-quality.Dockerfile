# Multi-stage Rust build for mcp-code-quality
# Stage 1: Build the Rust binaries
FROM rust:1.93 AS builder

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy code quality server
COPY tools/mcp/mcp_code_quality /build/tools/mcp/mcp_code_quality

# Copy markdown link checker (required by check_markdown_links tool)
COPY tools/rust/markdown-link-checker /build/tools/rust/markdown-link-checker

# Build the mcp-code-quality binary
WORKDIR /build/tools/mcp/mcp_code_quality
RUN cargo build --release

# Build the md-link-checker binary
WORKDIR /build/tools/rust/markdown-link-checker
RUN cargo build --release

# Stage 2: Runtime image with code quality tools
FROM python:3.11-slim

# Install system dependencies and code quality tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    # For JavaScript/TypeScript
    nodejs \
    npm \
    # For Go (lightweight go-fmt only)
    # golang-go \
    && rm -rf /var/lib/apt/lists/*

# Install Python code quality tools
RUN pip install --no-cache-dir \
    black \
    ruff \
    flake8 \
    pytest \
    pytest-cov \
    bandit \
    pip-audit \
    ty

# Install JavaScript/TypeScript tools
RUN npm install -g \
    prettier \
    eslint \
    @typescript-eslint/eslint-plugin \
    @typescript-eslint/parser

# Create app user with configurable UID/GID
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} mcp || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} mcp || true

# Create directories
RUN mkdir -p /app /var/log/mcp-code-quality && \
    chown -R mcp:mcp /app /var/log/mcp-code-quality

WORKDIR /app

# Copy the binaries from builder
COPY --from=builder /build/tools/mcp/mcp_code_quality/target/release/mcp-code-quality /usr/local/bin/
COPY --from=builder /build/tools/rust/markdown-link-checker/target/release/md-link-checker /usr/local/bin/

# Set permissions
RUN chmod +x /usr/local/bin/mcp-code-quality /usr/local/bin/md-link-checker

# Switch to non-root user
USER mcp

# Environment
ENV RUST_LOG=info
ENV MCP_CODE_QUALITY_TIMEOUT=600
ENV MCP_CODE_QUALITY_ALLOWED_PATHS=/workspace,/app,/home
ENV MCP_CODE_QUALITY_AUDIT_LOG=/var/log/mcp-code-quality/audit.log
ENV MCP_CODE_QUALITY_RATE_LIMIT=true

# Expose port
EXPOSE 8010

# Define volume for audit logs
VOLUME ["/var/log/mcp-code-quality"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

# Default command
CMD ["mcp-code-quality", "--mode", "standalone", "--port", "8010"]
