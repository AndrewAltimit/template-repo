FROM python:3.10-slim

# Install basic dependencies
RUN apt-get update || true && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-http-bridge.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy bridge script
COPY tools/cli/bridges/mcp-http-bridge.py .

# Set environment variables to prevent cache issues
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

# Expose port based on service
EXPOSE 8189 8190

# Run the bridge
CMD ["python", "mcp-http-bridge.py"]
