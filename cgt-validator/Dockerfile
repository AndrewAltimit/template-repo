# CGT Validator Docker Image - Simple Version
FROM python:3.11-slim

# Install system dependencies including tini for proper signal handling
RUN apt-get update && apt-get install -y \
    libxml2 \
    libxslt1.1 \
    poppler-utils \
    tzdata \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 cgtuser

# Set working directory
WORKDIR /app

# Copy only the files needed for dependency installation
COPY requirements-cgt.txt requirements-core.txt requirements-dev.txt setup.py README.md ./
COPY src/__init__.py src/

# Install dependencies and the package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-cgt.txt && \
    pip install --no-cache-dir -e .

# Install dev dependencies for test/dev targets
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir -r requirements-dev.txt; \
    fi

# Copy the rest of the application code
COPY --chown=cgtuser:cgtuser . .

# Set environment variables
ENV PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create necessary directories
RUN mkdir -p /app/downloads /app/reports /app/logs && \
    chown -R cgtuser:cgtuser /app

# Switch to non-root user
USER cgtuser

# Use tini as entrypoint to handle signals properly
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command
CMD ["cgt-validate", "--help"]
