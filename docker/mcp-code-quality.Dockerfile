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

# Install Python formatters and linters
RUN pip install --no-cache-dir \
    black \
    flake8 \
    pylint \
    isort \
    mypy \
    autopep8

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

# Install Python dependencies for MCP server
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    pydantic \
    aiohttp \
    mcp

# Create app directory
WORKDIR /app

# Create output directory
RUN mkdir -p /app/output

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8010

# Run the server
CMD ["python", "-m", "tools.mcp.code_quality.server", "--mode", "http"]
