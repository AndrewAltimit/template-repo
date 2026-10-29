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

# Fail RUN pipelines (e.g. checksum verification) on any stage's error
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Versions - update these as needed
# (checksums from the upstream SHA256SUMS files, verified below)
ARG TERRAFORM_VERSION=1.17.1
ARG TERRAFORM_CHECKSUM_AMD64=4638628058e71a55212b1c563712eac03b902128f40740f3dc8174df12135061
ARG TERRAFORM_CHECKSUM_ARM64=988e950a1c23058093b0e66ab2d5fb53fc18345ecfbd5871acf51dbac9325edd
ARG TERRAGRUNT_VERSION=1.2.1
ARG TERRAGRUNT_CHECKSUM_AMD64=f2f6238ad2348855a4e876b90fd31f3f5d106bb234794202a00b2bcc139fa753
ARG TERRAGRUNT_CHECKSUM_ARM64=01c0768aab01e0c183209ba7edce9d2ebc8f8a7690763bb52f1b8900aec224bc

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
    && CHECKSUM=$([ "$ARCH" = "arm64" ] && echo "$TERRAFORM_CHECKSUM_ARM64" || echo "$TERRAFORM_CHECKSUM_AMD64") \
    && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" -o terraform.zip \
    && echo "${CHECKSUM}  terraform.zip" | sha256sum -c - \
    && unzip terraform.zip terraform -d /usr/local/bin/ \
    && rm terraform.zip \
    && chmod +x /usr/local/bin/terraform \
    && terraform version

# Install Terragrunt (multi-arch)
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo "arm64" || echo "amd64") \
    && CHECKSUM=$([ "$ARCH" = "arm64" ] && echo "$TERRAGRUNT_CHECKSUM_ARM64" || echo "$TERRAGRUNT_CHECKSUM_AMD64") \
    && curl -fsSL "https://github.com/gruntwork-io/terragrunt/releases/download/v${TERRAGRUNT_VERSION}/terragrunt_linux_${ARCH}" -o /usr/local/bin/terragrunt \
    && echo "${CHECKSUM}  /usr/local/bin/terragrunt" | sha256sum -c - \
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
    TG_NON_INTERACTIVE=true

# Default command
CMD ["bash"]
