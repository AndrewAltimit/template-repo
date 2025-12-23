# Reaction Search MCP Server
# Semantic search for anime reaction images using sentence-transformers
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
# sentence-transformers will download the model on first use
RUN pip install --no-cache-dir \
    aiohttp>=3.8.0 \
    python-dotenv>=0.19.0 \
    sentence-transformers>=2.2.0 \
    pyyaml>=6.0 \
    requests>=2.28.0 \
    numpy>=1.21.0 \
    mcp \
    uvicorn \
    fastapi \
    pydantic

# Copy MCP server code
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_reaction_search /app/tools/mcp/mcp_reaction_search

# Install MCP packages
RUN pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir /app/tools/mcp/mcp_reaction_search

# Create non-root user
RUN useradd -m -u 1000 appuser

# Create cache directory for reaction config and model
RUN mkdir -p /home/appuser/.cache/mcp_reaction_search \
    /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /home/appuser

# Switch to non-root user
USER appuser

# Set environment
ENV HOME=/home/appuser
ENV HF_HOME=/home/appuser/.cache/huggingface
ENV REACTION_CACHE_DIR=/home/appuser/.cache/mcp_reaction_search
# PYTHONPATH set to /app so volume mount takes precedence over installed package
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8024

# Working directory
WORKDIR /home/appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8024/health || exit 1

# Default command
CMD ["python", "-m", "mcp_reaction_search.server", "--mode", "http"]
