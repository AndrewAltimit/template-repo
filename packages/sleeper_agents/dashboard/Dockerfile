# Dashboard Docker image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/home/dashboard/app:/home/dashboard/src \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and required directories
RUN useradd -m -u 1000 dashboard && \
    mkdir -p /home/dashboard/app /home/dashboard/app/.streamlit /home/dashboard/app/data && \
    chown -R dashboard:dashboard /home/dashboard

# Set working directory
WORKDIR /home/dashboard/app

# Copy requirements first for better caching
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire sleeper_agents package (src layout)
COPY --chown=dashboard:dashboard src/ /home/dashboard/src/

# Copy application code
COPY --chown=dashboard:dashboard dashboard/ .

# Switch to non-root user (COPY --chown already set correct ownership)
USER dashboard

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the dashboard
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
