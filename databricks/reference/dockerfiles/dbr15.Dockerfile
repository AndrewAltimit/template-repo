# DBR 15 Reference Dockerfile
# Python 3.11 with Databricks Runtime 15.4 LTS dependencies

FROM python:3.11-bullseye

ARG TARGETARCH=amd64

USER root
WORKDIR /tmp

# Setup UV for fast package installation
ENV UV_TOOL_BIN_DIR=/bin
COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /uvx /bin/

# Copy requirements
COPY reference/requirements/dbr15-full.txt /tmp/requirements.txt

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
ARG DBX_CLI_VERSION=0.245.0
# Checksums for verification (computed from official binaries)
ARG DBX_CLI_SHA256_AMD64="43ff8feefbf7cc69b72c8118486c8b6fe5aba1a388197fd71bae3fc51b44105e"
ARG DBX_CLI_SHA256_ARM64="eff6d54a9777231a95d041e8281dad99977692b46a4d7e7499c757f6bdbdb030"
RUN mkdir -p /tmp/dbx-cli && \
    cd /tmp/dbx-cli && \
    wget https://github.com/databricks/cli/releases/download/v${DBX_CLI_VERSION}/databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip && \
    if [ "${TARGETARCH}" = "amd64" ]; then \
        echo "${DBX_CLI_SHA256_AMD64}  databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip" | sha256sum -c - || exit 1; \
    else \
        echo "${DBX_CLI_SHA256_ARM64}  databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip" | sha256sum -c - || exit 1; \
    fi && \
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
ARG TERRAFORM_VERSION=1.11.2
# Checksums for verification (computed from official binaries)
ARG TERRAFORM_SHA256_AMD64="b94f7c5080196081ea5180e8512edd3c2037f28445ce3562cfb0adfd0aab64ca"
ARG TERRAFORM_SHA256_ARM64="1f162f947e346f75ac3f6ccfdf5e6910924839f688f0773de9a79bc2e0b4ca94"
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
ARG TERRAGRUNT_VERSION="v0.77.0"
# Checksums for verification (computed from official binaries)
ARG TERRAGRUNT_SHA256_AMD64="2d865e72a9f7960823120bd5997b984b30c7f5085047387547bca5e848784d1f"
ARG TERRAGRUNT_SHA256_ARM64="0ce83a03553f9210013930eff090b0ed68b93411ce064c6813caba5c43f96679"
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
