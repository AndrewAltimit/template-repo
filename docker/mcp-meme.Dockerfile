FROM python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Image processing libraries
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    # Fonts for meme text
    fonts-liberation \
    fonts-dejavu-core \
    # Port checking utility
    lsof \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create output directory with proper permissions
RUN mkdir -p /output && \
    chmod -R 755 /output

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-meme.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only necessary MCP server code
COPY tools/mcp/core /app/tools/mcp/core
COPY tools/mcp/meme_generator /app/tools/mcp/meme_generator

# Set Python path
ENV PYTHONPATH=/app

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8016

# Run the server
CMD ["python", "-m", "tools.mcp.meme_generator.server", "--mode", "http"]
