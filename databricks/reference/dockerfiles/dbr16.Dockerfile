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

# Install AWS CLI (pinned version)
ARG AWS_CLI_VERSION=2.22.25
RUN if [ "${TARGETARCH}" = "arm64" ]; then \
        AWS_CLI_PKG="aarch64"; \
    else \
        AWS_CLI_PKG="x86_64"; \
    fi \
    && curl -L "https://awscli.amazonaws.com/awscli-exe-linux-${AWS_CLI_PKG}-${AWS_CLI_VERSION}.zip" -o "awscliv2.zip" \
    && docker-verify-checksum.sh awscliv2.zip "awscli-exe-linux-${AWS_CLI_PKG}-${AWS_CLI_VERSION}.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && aws --version

# Install Terraform
ARG TERRAFORM_VERSION=1.12.2
RUN curl --remote-name --location https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && docker-verify-checksum.sh terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && unzip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && mv terraform /usr/bin \
    && rm LICENSE.txt terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && terraform version

# Install Terragrunt
ARG TERRAGRUNT_VERSION="v0.81.10"
RUN curl -sL https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/terragrunt_linux_${TARGETARCH} -o /usr/local/bin/terragrunt \
    && docker-verify-checksum.sh /usr/local/bin/terragrunt "terragrunt_linux_${TARGETARCH}  ${TERRAGRUNT_VERSION#v}" \
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

# Copy helper scripts (excluding the redundant dbr-validate)
# Note: checksums.txt and docker-verify-checksum.sh already copied at the beginning of the Dockerfile
COPY scripts/dbr-setup-post /usr/local/bin/dbr-setup-post
COPY scripts/dbr-setup-pre /usr/local/bin/dbr-setup-pre
COPY scripts/verify-checksum.sh /usr/local/bin/verify-checksum.sh
RUN chmod +x /usr/local/bin/dbr-setup-post /usr/local/bin/dbr-setup-pre /usr/local/bin/verify-checksum.sh

# Note: dbr-validate command is provided by the Python dbr-env-all package

# Switch to non-root user
USER dbruser

# Default command
CMD ["/bin/bash"]
