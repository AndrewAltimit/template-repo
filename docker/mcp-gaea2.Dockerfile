FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    gosu \
    passwd \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-gaea2.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user first
RUN useradd -m -u 1000 appuser

# Create output directory with proper ownership for non-root user
RUN mkdir -p /output/gaea2 && \
    chown -R appuser:appuser /output && \
    chmod -R 755 /output

# Copy MCP server code
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_gaea2 /app/tools/mcp/mcp_gaea2

# Install MCP packages
RUN pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir /app/tools/mcp/mcp_gaea2

# Set Python path
ENV PYTHONPATH=/app

# Note about limitations
RUN echo "Note: This container provides Gaea2 project creation and validation only." > /app/CONTAINER_NOTE.txt && \
    echo "For CLI automation features, run on Windows host with Gaea2 installed." >> /app/CONTAINER_NOTE.txt

# Copy entrypoint script
COPY docker/entrypoints/gaea2-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/gaea2-entrypoint.sh

# Expose port
EXPOSE 8007

# Entrypoint for permission handling (runs as root, then switches to appuser)
ENTRYPOINT ["/usr/local/bin/gaea2-entrypoint.sh"]

# Run the server
CMD ["python", "-m", "mcp_gaea2.server", "--mode", "http"]
