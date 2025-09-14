# DBR 15 Reference Dockerfile
# Python 3.11 with Databricks Runtime 15.4 LTS dependencies
# Uses setup scripts for DRY principle and validation testing

FROM python:3.11-bullseye

ARG TARGETARCH=amd64

USER root
WORKDIR /tmp

# Copy all necessary files for setup scripts
RUN mkdir -p /opt/databricks/config /opt/databricks/scripts
COPY config/ /opt/databricks/config/
COPY scripts/ /opt/databricks/scripts/

# Make scripts executable
RUN chmod +x /opt/databricks/scripts/*.sh

# Setup UV for fast package installation
# Note: Docker doesn't support ARG in COPY --from, so UV version is fixed here
# This should match the version in config/versions.json for dbr15
ENV UV_TOOL_BIN_DIR=/bin
COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /uvx /bin/

# Install system dependencies using the setup script
# This validates the script works in container Linux environment
RUN /opt/databricks/scripts/dbr-setup-pre \
    --version dbr15 \
    --platform linux \
    --non-interactive

# Copy and install Python packages
COPY docker/requirements/dbr15-full.txt /tmp/requirements.txt
RUN uv pip install -r requirements.txt --system && uv cache clean

# Install binary tools using the setup script
# Pass build args for versions to ensure consistency
ARG DBX_CLI_VERSION=0.245.0
ARG TERRAFORM_VERSION=1.11.2
ARG TERRAGRUNT_VERSION=0.77.0
ARG AWS_CLI_VERSION=2.22.25

# Export versions as environment variables for the script
ENV DBX_CLI_VERSION=${DBX_CLI_VERSION} \
    TERRAFORM_VERSION=${TERRAFORM_VERSION} \
    TERRAGRUNT_VERSION=${TERRAGRUNT_VERSION} \
    AWS_CLI_VERSION=${AWS_CLI_VERSION} \
    TARGETARCH=${TARGETARCH}

# Run post-setup script to install binary tools
# Skip checksums in Docker build since we control the environment
RUN /opt/databricks/scripts/dbr-setup-post \
    --version dbr15 \
    --install-dir /usr/local/bin \
    --skip-checksums

# Create non-root user
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} -o dbruser && \
    useradd --uid ${USER_ID} --gid ${GROUP_ID} --create-home --shell /bin/bash dbruser

# Set working directory
WORKDIR /workspace
RUN chown -R dbruser:dbruser /workspace

# Copy setup scripts to standard location for runtime use
RUN cp /opt/databricks/scripts/dbr-setup-* /usr/local/bin/ && \
    chmod +x /usr/local/bin/dbr-setup-*

# Note: dbr-validate command is provided by the Python dbr-env-all package

# Switch to non-root user
USER dbruser

# Default command
CMD ["/bin/bash"]
