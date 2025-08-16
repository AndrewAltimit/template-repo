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
COPY tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8010

# Run the server
CMD ["python", "-m", "tools.mcp.code_quality.server", "--mode", "http"]
