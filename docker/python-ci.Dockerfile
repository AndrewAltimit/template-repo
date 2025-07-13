# Python CI/CD Image with all testing and linting tools
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /workspace

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt ./

# Install all dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Python environment configuration to prevent cache issues
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 ciuser

# Default command
CMD ["bash"]
