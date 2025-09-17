# Sleeper Agent Detection - CPU-only Evaluation Dockerfile
# Lightweight version for quick testing without GPU

FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    wget \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} evaluator && \
    useradd -u ${USER_ID} -g ${GROUP_ID} -m evaluator

# Create necessary directories with correct permissions
RUN mkdir -p /models /results /db && \
    chown -R evaluator:evaluator /models /results /db

# Upgrade pip first
RUN pip install --upgrade pip

# Install Python dependencies (CPU-only versions) in stages
# Stage 1: PyTorch CPU
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Stage 2: ML dependencies
RUN pip install --no-cache-dir \
    transformers>=4.35.0 \
    einops>=0.7.0 \
    numpy>=1.24.0 \
    pandas>=2.0.0 \
    scikit-learn>=1.3.0

# Stage 2b: TransformerLens for mechanistic interpretability
RUN pip install --no-cache-dir transformer-lens>=2.0.0

# Stage 2c: API dependencies
RUN pip install --no-cache-dir \
    fastapi[all]>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    pydantic>=2.0.0

# Stage 3: Visualization and reporting
RUN pip install --no-cache-dir \
    jinja2>=3.1.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    plotly>=5.17.0

# Stage 4: Utilities and testing
RUN pip install --no-cache-dir \
    pyyaml>=6.0 \
    python-dotenv>=1.0.0 \
    pytest>=7.4.0 \
    pytest-asyncio>=0.21.0 \
    pytest-cov>=4.1.0 \
    jupyter \
    nbconvert \
    colorama>=0.4.6 \
    tabulate>=0.9.0 \
    tqdm>=4.66.0 \
    aiofiles>=23.2.1 \
    httpx>=0.25.0 \
    psutil>=5.9.0

# Copy application code
COPY --chown=evaluator:evaluator . /app

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# Model cache directories
ENV TRANSFORMERS_CACHE=/models
ENV HF_HOME=/models
ENV TORCH_HOME=/models

# Evaluation settings
ENV EVAL_RESULTS_DIR=/results
ENV EVAL_DB_PATH=/db/evaluation_results.db

# Switch to non-root user
USER evaluator

# Default command - run CLI help
CMD ["python", "-m", "packages.sleeper_detection.cli", "--help"]
