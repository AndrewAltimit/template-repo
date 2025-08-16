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

# Create output directory with proper permissions
# Only create the volume mount directory - other paths are not used
RUN mkdir -p /output && \
    chmod -R 755 /output

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-content.txt /app/requirements.txt

# Install Manim and MCP server dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# No entrypoint script needed - containers run as host user

# Set Python path
ENV PYTHONPATH=/app

# Manim configuration - use the volume-mounted output directory
ENV MANIM_MEDIA_DIR=/output/manim

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 appuser

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8011

# Run as host user via docker-compose - no entrypoint needed

# Run the server
CMD ["python", "-m", "tools.mcp.content_creation.server", "--mode", "http"]
