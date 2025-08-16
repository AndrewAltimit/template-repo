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
COPY docker/requirements/requirements-gaea2.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create output directory with proper permissions
RUN mkdir -p /output/gaea2 && chmod -R 755 /output

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# No entrypoint script needed - containers run as host user

# Set Python path
ENV PYTHONPATH=/app

# Note about limitations
RUN echo "Note: This container provides Gaea2 project creation and validation only." > /app/CONTAINER_NOTE.txt && \
    echo "For CLI automation features, run on Windows host with Gaea2 installed." >> /app/CONTAINER_NOTE.txt

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8007

# Run as host user via docker-compose - no entrypoint needed

# Run the server
CMD ["python", "-m", "tools.mcp.gaea2.server", "--mode", "http"]
