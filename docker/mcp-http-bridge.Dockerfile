FROM python:3.10-slim

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    pydantic

# Copy bridge script
COPY scripts/mcp-http-bridge.py .

# Set environment variables to prevent cache issues
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

# Expose port based on service
EXPOSE 8189 8190

# Run the bridge
CMD ["python", "mcp-http-bridge.py"]
