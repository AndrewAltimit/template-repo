FROM python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # LaTeX packages
    texlive-full \
    # PDF utilities
    poppler-utils \
    pdf2svg \
    # Video/animation dependencies
    ffmpeg \
    # Cairo for Manim
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    # Build tools
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Manim and dependencies
RUN pip install --no-cache-dir \
    manim \
    numpy \
    scipy \
    pillow \
    pycairo

# Install MCP server dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    pydantic \
    aiohttp \
    mcp

# Create app directory
WORKDIR /app

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
