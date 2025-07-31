# CGT Validator Docker Image - Simple Version
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libxml2 \
    libxslt1.1 \
    poppler-utils \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 cgtuser

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements-cgt.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-cgt.txt

# Copy application code
COPY --chown=cgtuser:cgtuser . .

# Set environment variables
ENV PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTEST_CACHE_DIR="/tmp/.pytest_cache"

# Create necessary directories
RUN mkdir -p /app/downloads /app/reports /app/logs /tmp/.pytest_cache && \
    chown -R cgtuser:cgtuser /app && \
    chmod -R 777 /tmp/.pytest_cache

# Switch to non-root user
USER cgtuser

# Default command
CMD ["python", "-m", "cli", "--help"]
