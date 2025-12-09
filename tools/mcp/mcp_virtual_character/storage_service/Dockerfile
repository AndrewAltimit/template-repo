FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    python-multipart \
    aiofiles \
    requests

# Copy server
COPY server.py /app/

# Create storage directory
RUN mkdir -p /tmp/audio_storage

# Run as non-root user
RUN useradd -m -u 1000 storage && \
    chown -R storage:storage /app /tmp/audio_storage

USER storage

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8021/health').raise_for_status()" || exit 1

EXPOSE 8021

CMD ["python", "server.py"]
