FROM python:3.11-slim

# Install system dependencies and code formatters/linters
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    # For JavaScript/TypeScript
    nodejs \
    npm \
    # For Go
    golang-go \
    # For Rust
    rustc \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-code-quality.txt /app/requirements.txt

# Install Python formatters, linters, and MCP dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install JavaScript/TypeScript tools
RUN npm install -g \
    prettier \
    eslint \
    @typescript-eslint/eslint-plugin \
    @typescript-eslint/parser

# Install Go tools (skip for now due to version issues)
# RUN go install golang.org/x/lint/golint@latest && \
#     go install golang.org/x/tools/cmd/goimports@latest

# Install Rust formatter (skip - rustup not available in this image)
# RUN rustup component add rustfmt clippy

# Copy MCP server code
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_code_quality /app/tools/mcp/mcp_code_quality

# Copy markdown link checker utility (required by server)
COPY tools/cli/utilities /app/tools/cli/utilities

# Install MCP packages
RUN pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir /app/tools/mcp/mcp_code_quality

# Set Python path
ENV PYTHONPATH=/app

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# Create audit log directory with proper permissions
RUN mkdir -p /var/log/mcp-code-quality && \
    chown appuser:appuser /var/log/mcp-code-quality

# Switch to non-root user
USER appuser

# Environment variables for enterprise configuration
ENV MCP_CODE_QUALITY_TIMEOUT=600
ENV MCP_CODE_QUALITY_ALLOWED_PATHS=/workspace,/app,/home
ENV MCP_CODE_QUALITY_AUDIT_LOG=/var/log/mcp-code-quality/audit.log
ENV MCP_CODE_QUALITY_RATE_LIMIT=true

# Expose port
EXPOSE 8010

# Define volume for audit logs (allows persistence across container restarts)
VOLUME ["/var/log/mcp-code-quality"]

# Run the server
CMD ["python", "-m", "mcp_code_quality.server", "--mode", "http"]
