FROM python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # LaTeX packages - using smaller base package instead of texlive-full
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-extra \
    texlive-science \
    texlive-pictures \
    # PDF utilities
    poppler-utils \
    pdf2svg \
    # Video/animation dependencies
    ffmpeg \
    # Cairo for Manim
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    python3-dev \
    libffi-dev \
    # Build tools
    build-essential \
    # Port checking utility
    lsof \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create output directories with proper permissions
RUN mkdir -p /app/output/manim /app/output/latex && \
    chmod -R 755 /app/output && \
    mkdir -p /tmp/mcp-content-output/manim /tmp/mcp-content-output/latex && \
    chmod -R 755 /tmp/mcp-content-output && \
    mkdir -p /output && \
    chmod -R 755 /output

# Copy requirements first for better layer caching
COPY docker/requirements-content.txt /app/requirements.txt

# Install Manim and MCP server dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# Copy entrypoint script
COPY docker/entrypoint-mcp-content.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set Python path
ENV PYTHONPATH=/app

# Manim configuration - use the writable temp directory
ENV MANIM_MEDIA_DIR=/tmp/mcp-content-output/manim

# Expose port
EXPOSE 8011

# Use entrypoint script to ensure proper permissions
ENTRYPOINT ["/entrypoint.sh"]

# Run the server
CMD ["python", "-m", "tools.mcp.content_creation.server", "--mode", "http"]
