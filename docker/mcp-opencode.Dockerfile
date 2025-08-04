FROM python:3.11-slim

# Install system dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Add Docker's official GPG key and repository
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker CLI
RUN apt-get update && apt-get install -y docker-ce-cli && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create requirements file
RUN echo "aiohttp>=3.8.0\nclick>=8.0.0\npython-dotenv\nmcp\nuvicorn\nfastapi\npydantic" > /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the MCP tools
COPY tools/mcp /app/tools/mcp

# Create a non-root user and add to docker group
RUN groupadd -g 999 docker || true \
    && useradd -m -u 1000 -G docker appuser

# Set environment to indicate we're in Docker (before switching user)
ENV RUNNING_IN_DOCKER=true

# Switch to non-root user
USER appuser

# Default command
CMD ["python", "-m", "tools.mcp.opencode.server", "--mode", "http"]
