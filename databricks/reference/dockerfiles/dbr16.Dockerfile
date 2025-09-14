# DBR 16 Reference Dockerfile
# Python 3.12 with Databricks Runtime 16.4 LTS dependencies

FROM python:3.12-bullseye

ARG TARGETARCH=amd64

USER root
WORKDIR /tmp

# Copy checksum files and verification script early for use during build
RUN mkdir -p /opt/databricks/config
COPY config/checksums.txt /opt/databricks/config/checksums.txt
COPY scripts/docker-verify-checksum.sh /usr/local/bin/docker-verify-checksum.sh
RUN chmod +x /usr/local/bin/docker-verify-checksum.sh

# Setup UV for fast package installation
ENV UV_TOOL_BIN_DIR=/bin
COPY --from=ghcr.io/astral-sh/uv:0.7.14 /uv /uvx /bin/

# Copy requirements
COPY reference/requirements/dbr16-full.txt /tmp/requirements.txt

# Install Python packages
RUN uv pip install -r requirements.txt --system && uv cache clean

# Install Java & System tools
RUN apt-get update && \
    apt-get install -y -f -m \
    wget unzip zip jq \
    openjdk-17-jdk-headless && \
    /var/lib/dpkg/info/ca-certificates-java.postinst configure && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Databricks CLI
ARG DBX_CLI_VERSION=0.256.0
RUN mkdir -p /tmp/dbx-cli && \
    cd /tmp/dbx-cli && \
    wget https://github.com/databricks/cli/releases/download/v${DBX_CLI_VERSION}/databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip && \
    docker-verify-checksum.sh databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip && \
    unzip *.zip && \
    mv databricks /usr/local/bin/databricks && \
    chmod +x /usr/local/bin/databricks && \
    rm -rf /tmp/dbx-cli && \
    databricks --help

# Install AWS CLI
# Checksums for verification (computed from official binaries)
ARG AWS_CLI_SHA256_AMD64="2f6f4c699f7c93bb2f19a8502bd945d243567d1dd95fb87397e3449204fd69cf"
ARG AWS_CLI_SHA256_ARM64="90ae801d74b99e7dc4efae10c6b4236555a6b58b8c7fb2c6d7f0b4c0a2582f76"
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
        AWS_CLI_PKG="aarch64"; \
        AWS_CLI_SHA256="${AWS_CLI_SHA256_ARM64}"; \
    else \
        AWS_CLI_PKG="x86_64"; \
        AWS_CLI_SHA256="${AWS_CLI_SHA256_AMD64}"; \
    fi \
    && curl -L "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_CLI_PKG}.zip" -o "awscliv2.zip" \
    && echo "${AWS_CLI_SHA256}  awscliv2.zip" | sha256sum -c - || exit 1 \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && aws --version

# Install Terraform
ARG TERRAFORM_VERSION=1.12.2
# Checksums for verification (computed from official binaries)
ARG TERRAFORM_SHA256_AMD64="1eaed12ca41fcfe094da3d76a7e9aa0639ad3409c43be0103ee9f5a1ff4b7437"
ARG TERRAFORM_SHA256_ARM64="f8a0347dc5e68e6d60a9fa2db361762e7943ed084a773f28a981d988ceb6fdc9"
RUN curl --remote-name --location https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && if [ "${TARGETARCH}" = "amd64" ]; then \
        echo "${TERRAFORM_SHA256_AMD64}  terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" | sha256sum -c - || exit 1; \
    else \
        echo "${TERRAFORM_SHA256_ARM64}  terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip" | sha256sum -c - || exit 1; \
    fi \
    && unzip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && mv terraform /usr/bin \
    && rm LICENSE.txt terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && terraform version

# Install Terragrunt
ARG TERRAGRUNT_VERSION="v0.81.10"
# Checksums for verification (computed from official binaries)
ARG TERRAGRUNT_SHA256_AMD64="1821248830c887d40a74a8d6916024b6de660aa61d35443101857a24a2f3bdb1"
ARG TERRAGRUNT_SHA256_ARM64="a69b40723cc5210943eff6e22354105f129812f6817ea0d021af9c58ec61f38b"
RUN curl -sL https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/terragrunt_linux_${TARGETARCH} -o /usr/local/bin/terragrunt \
    && if [ "${TARGETARCH}" = "amd64" ]; then \
        echo "${TERRAGRUNT_SHA256_AMD64}  /usr/local/bin/terragrunt" | sha256sum -c - || exit 1; \
    else \
        echo "${TERRAGRUNT_SHA256_ARM64}  /usr/local/bin/terragrunt" | sha256sum -c - || exit 1; \
    fi \
    && chmod +x /usr/local/bin/terragrunt \
    && terragrunt --version

# Create non-root user
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} -o dbruser && \
    useradd --uid ${USER_ID} --gid ${GROUP_ID} --create-home --shell /bin/bash dbruser

# Set working directory
WORKDIR /workspace
RUN chown -R dbruser:dbruser /workspace

# Copy helper scripts and checksums (excluding the redundant dbr-validate)
RUN mkdir -p /opt/databricks/config
COPY scripts/dbr-setup-post /usr/local/bin/dbr-setup-post
COPY scripts/dbr-setup-pre /usr/local/bin/dbr-setup-pre
COPY scripts/verify-checksum.sh /usr/local/bin/verify-checksum.sh
COPY config/checksums.txt /opt/databricks/config/checksums.txt
RUN chmod +x /usr/local/bin/dbr-setup-post /usr/local/bin/dbr-setup-pre /usr/local/bin/verify-checksum.sh

# Note: dbr-validate command is provided by the Python dbr-env-all package

# Switch to non-root user
USER dbruser

# Default command
CMD ["/bin/bash"]
