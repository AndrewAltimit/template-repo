FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better layer caching
# Create a minimal requirements file for basic MCP servers
RUN echo "aiohttp>=3.8.0\nclick>=8.0.0\npython-dotenv\nmcp\nuvicorn\nfastapi\npydantic" > /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# The port and command will be set by docker-compose

# Default to running as appuser
USER appuser
