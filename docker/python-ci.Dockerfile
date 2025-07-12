# Python CI/CD Image with all testing and linting tools
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python CI/CD tools
RUN pip install --no-cache-dir \
    black \
    isort \
    flake8 \
    pylint \
    mypy \
    bandit \
    safety \
    pytest \
    pytest-asyncio \
    pytest-cov \
    yamllint

# Create working directory
WORKDIR /workspace

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["bash"]