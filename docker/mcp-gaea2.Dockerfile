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
COPY docker/requirements-gaea2.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Note: Output directory will be created at runtime with proper permissions
# Do not create it in the Dockerfile to avoid permission issues

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

# Note about limitations
RUN echo "Note: This container provides Gaea2 project creation and validation only." > /app/CONTAINER_NOTE.txt && \
    echo "For CLI automation features, run on Windows host with Gaea2 installed." >> /app/CONTAINER_NOTE.txt

# Expose port
EXPOSE 8007

# Run the server
CMD ["python", "-m", "tools.mcp.gaea2.server", "--mode", "http"]
