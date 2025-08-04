# Use the openrouter-agents image as base since it has crush installed
FROM template-repo-openrouter-agents

# Switch to root to install additional packages
USER root

# Install Python MCP dependencies
RUN pip install --no-cache-dir --break-system-packages \
    aiohttp>=3.8.0 \
    click>=8.0.0 \
    python-dotenv \
    mcp \
    uvicorn \
    fastapi \
    pydantic

# Create app directory and copy MCP server code
WORKDIR /app
COPY --chown=node:node tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

# Ensure crush directories have correct permissions
RUN chown -R node:node /home/node/.config/crush /home/node/.local/share/crush || true

# Switch back to node user (from base image)
USER node

# Set HOME to ensure crush finds its config
ENV HOME=/home/node

# The crush binary is available at /usr/local/bin/crush from the base image
# Verify it exists
RUN which crush

# Default command can be overridden by docker-compose
CMD ["python", "-m", "tools.mcp.crush.server", "--mode", "http"]
