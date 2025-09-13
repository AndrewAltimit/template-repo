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
RUN mkdir -p /tmp/dbx-cli && \
    cd /tmp/dbx-cli && \
    wget https://github.com/databricks/cli/releases/download/v${DBX_CLI_VERSION}/databricks_cli_${DBX_CLI_VERSION}_linux_${TARGETARCH}.zip && \
    unzip *.zip && \
    mv databricks /usr/local/bin/databricks && \
    chmod +x /usr/local/bin/databricks && \
    rm -rf /tmp/dbx-cli && \
    databricks --help

# Install AWS CLI
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
        AWS_CLI_PKG="aarch64"; \
    else \
        AWS_CLI_PKG="x86_64"; \
    fi \
    && curl -L "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_CLI_PKG}.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && aws --version

# Install Terraform
ARG TERRAFORM_VERSION=1.11.2
RUN curl --remote-name --location https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && unzip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && mv terraform /usr/bin \
    && rm LICENSE.txt terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && terraform version

# Install Terragrunt
ARG TERRAGRUNT_VERSION="v0.77.0"
RUN curl -sL https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/terragrunt_linux_${TARGETARCH} -o /usr/local/bin/terragrunt \
    && chmod +x /usr/local/bin/terragrunt \
    && terragrunt --version

# Set working directory
WORKDIR /workspace

# Validation script
COPY scripts/dbr-validate /usr/local/bin/dbr-validate
RUN chmod +x /usr/local/bin/dbr-validate

# Default command
CMD ["/bin/bash"]
