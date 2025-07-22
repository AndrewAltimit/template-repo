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
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY docker/requirements-content.txt /app/requirements.txt

# Install Manim and MCP server dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

# Manim configuration
ENV MANIM_MEDIA_DIR=/app/output/manim

# Expose port
EXPOSE 8011

# Run the server
CMD ["python", "-m", "tools.mcp.content_creation.server", "--mode", "http"]
