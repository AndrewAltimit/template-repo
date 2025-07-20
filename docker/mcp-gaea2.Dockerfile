FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    pydantic \
    aiohttp \
    mcp \
    numpy

# Create app directory
WORKDIR /app

# Create output directory for terrain files
RUN mkdir -p /app/output/gaea2

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
