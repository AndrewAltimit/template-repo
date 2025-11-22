FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-github-board.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy github_agents package
COPY packages/github_agents /app/packages/github_agents

# Copy MCP server code
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_github_board /app/tools/mcp/mcp_github_board

# Install packages
RUN pip install --no-cache-dir /app/packages/github_agents[board] && \
    pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir /app/tools/mcp/mcp_github_board

# Set Python path
ENV PYTHONPATH=/app

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8021

# Run the server
CMD ["python", "-m", "mcp_github_board.server", "--mode", "http"]
