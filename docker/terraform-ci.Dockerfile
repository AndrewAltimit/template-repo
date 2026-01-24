# syntax=docker/dockerfile:1.4
# Terraform/Terragrunt CI/CD Image with AWS CLI
# For deploying AWS infrastructure following container-first philosophy
#
# Includes:
# - Terraform (latest stable)
# - Terragrunt (latest stable)
# - AWS CLI v2
# - Common utilities (jq, git, curl)
#
# Supports both amd64 and arm64 architectures

FROM debian:bookworm-slim AS base

# Versions - update these as needed
ARG TERRAFORM_VERSION=1.10.5
ARG TERRAGRUNT_VERSION=0.72.6

# Architecture detection for multi-arch support
ARG TARGETARCH

# Install system dependencies with BuildKit cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    jq \
    unzip \
    gnupg \
    groff \
    less \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform (multi-arch)
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "amd64") \
    && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" -o terraform.zip \
    && unzip terraform.zip -d /usr/local/bin/ \
    && rm terraform.zip \
    && chmod +x /usr/local/bin/terraform \
    && terraform version

# Install Terragrunt (multi-arch)
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "amd64") \
    && curl -fsSL "https://github.com/gruntwork-io/terragrunt/releases/download/v${TERRAGRUNT_VERSION}/terragrunt_linux_${ARCH}" -o /usr/local/bin/terragrunt \
    && chmod +x /usr/local/bin/terragrunt \
    && terragrunt --version

# Install AWS CLI v2 (multi-arch)
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "aarch64" || echo "x86_64") \
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${ARCH}.zip" -o awscliv2.zip \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && aws --version

# Create working directory
WORKDIR /workspace

# Create non-root user for CI
RUN useradd -m -u 1000 ciuser

# Create directories for terraform plugins and cache
RUN mkdir -p /home/ciuser/.terraform.d/plugin-cache \
    && chown -R ciuser:ciuser /home/ciuser

# Environment configuration
ENV TF_PLUGIN_CACHE_DIR=/home/ciuser/.terraform.d/plugin-cache \
    TF_IN_AUTOMATION=1 \
    TF_INPUT=0 \
    TERRAGRUNT_NON_INTERACTIVE=true

# Default command
CMD ["bash"]
