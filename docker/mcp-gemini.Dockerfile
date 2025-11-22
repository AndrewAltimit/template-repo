# Dockerfile for Gemini MCP Server
FROM python:3.11-slim

# Install system dependencies and Node.js for Gemini CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @google/gemini-cli@preview \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
# Handle cases where the group/user might already exist
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} geminiuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash geminiuser)

# Set working directory
WORKDIR /app

# Copy Python requirements
COPY config/python/requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_gemini /app/tools/mcp/mcp_gemini

# Install MCP packages
RUN pip3 install --no-cache-dir -e /workspace/tools/mcp/mcp_core &&\
    pip3 install --no-cache-dir -e /workspace/tools/mcp/mcp_gemini

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH

# Switch to the created user
USER geminiuser

# Default command
CMD ["python", "-m", "mcp_gemini.server", "--mode", "stdio"]
