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

# Update pip and setuptools to secure versions
RUN pip install --no-cache-dir --upgrade pip>=23.3 setuptools>=78.1.1

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt ./

# Install all dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copy linting configuration files to both /workspace and /app
# Note: Files are copied to both locations to support different tool contexts:
# - /workspace is the primary working directory for most CI operations
# - /app is used by some tools that expect absolute paths or when running
#   with read-only mounts where the code is mounted at /app
COPY .isort.cfg .flake8 .pylintrc ./
COPY .isort.cfg .flake8 .pylintrc /app/
# Copy pyproject.toml files for proper isort configuration
# Duplicated to ensure tools can find configs regardless of working directory
COPY pyproject.toml ./
COPY pyproject.toml /app/
# Create directory structure for package configs
RUN mkdir -p packages/github_ai_agents /app/packages/github_ai_agents
COPY packages/github_ai_agents/pyproject.toml ./packages/github_ai_agents/
COPY packages/github_ai_agents/pyproject.toml /app/packages/github_ai_agents/

# Python environment configuration to prevent cache issues
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 ciuser

# Copy security hooks and set up universal gh alias
COPY scripts/security-hooks /app/security-hooks
RUN chmod +x /app/security-hooks/*.sh && \
    echo 'alias gh="/app/security-hooks/gh-wrapper.sh"' >> /etc/bash.bashrc

# Default command
CMD ["bash"]
