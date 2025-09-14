# DBR Environment Setup Helper - Technical Specification

**Version:** 1.0
**Date:** September 10, 2025
**Status:** Implementation-Ready
**Infrastructure:** GitHub Actions with Self-Hosted Linux Runners
**Purpose:** Generate Python dependency wheels and system installation scripts for Databricks Runtime environments

## Executive Summary

This specification defines a build system that produces Python wheels containing exact DBR dependency specifications and installation scripts for system-level requirements. The system uses GitHub Actions with self-hosted Linux runners for CI/CD, enabling users to recreate Databricks Runtime environments through standard pip installation combined with pre/post setup scripts. The specification includes tested reference implementations from production Dockerfiles.

## 1. Scope and Deliverables

### 1.1 Primary Deliverables

1. **Python Wheels** - Meta-packages declaring exact DBR dependencies (not bundling)
2. **Pre-installation Script** - System dependencies installer
3. **Post-installation Script** - Binary tools installer
4. **Constraints Files** - Locked dependency versions with SHA256 hashes
5. **Validation Script** - Environment verification tool

### 1.2 Infrastructure Requirements

- **CI/CD**: GitHub Actions with self-hosted Linux runners
- **Build Environment**: Linux (Ubuntu 20.04/22.04)
- **Python Versions**: 3.11 (DBR 15), 3.12 (DBR 16)
- **Container Runtime**: Docker/Podman on runners

## 2. Project Structure

```
dbr-env-setup/
├── wheels/
│   ├── dbr-env-core/
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── dbr_env_core/
│   │           └── __init__.py     # Version metadata only
│   ├── dbr-env-ml/
│   ├── dbr-env-cloud/
│   └── dbr-env-all/                # Meta-package
├── scripts/
│   ├── dbr-setup-pre               # System dependencies
│   └── dbr-setup-post              # Binary tools
│   # Note: dbr-validate is provided by the dbr-env-all Python package
├── constraints/
│   ├── dbr15-constraints.txt
│   ├── dbr16-constraints.txt
│   └── generate.py
├── checksums/
│   ├── binaries-dbr15.json
│   └── binaries-dbr16.json
├── requirements/                   # Source requirements from DBR
│   ├── dbr15/
│   │   ├── core.txt
│   │   ├── ml.txt
│   │   └── cloud.txt
│   └── dbr16/
│       ├── core.txt
│       ├── ml.txt
│       └── cloud.txt
├── reference/                      # Tested reference implementations
│   ├── dockerfiles/
│   │   ├── dbr15.Dockerfile
│   │   └── dbr16.Dockerfile
│   └── requirements/
│       ├── dbr15-full.txt
│       └── dbr16-full.txt
├── .github/
│   └── workflows/
│       ├── build-wheels.yml
│       ├── test-installation.yml
│       └── release.yml
└── build/
    └── scripts/
        ├── build-wheels.sh
        └── test-local.sh
```

## 3. Reference Implementations

### 3.1 DBR 15 Reference Dockerfile

```dockerfile
# docker/dockerfiles/dbr15.Dockerfile
FROM python:3.11-bullseye

ARG TARGETARCH=amd64

USER root
WORKDIR /tmp

# Install certificates (make configurable for generic use)
# COPY build-images/common/install_certs.sh install_certs.sh
# RUN bash /tmp/install_certs.sh

# Setup UV for fast package installation
ENV UV_TOOL_BIN_DIR=/bin
COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /uvx /bin/

# Install Python packages
COPY reference/requirements/dbr15-full.txt /tmp/requirements.txt
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
```

### 3.2 DBR 16 Reference Dockerfile

```dockerfile
# docker/dockerfiles/dbr16.Dockerfile
FROM python:3.12-bullseye

ARG TARGETARCH=amd64

USER root
WORKDIR /tmp

# Setup UV for fast package installation
ENV UV_TOOL_BIN_DIR=/bin
COPY --from=ghcr.io/astral-sh/uv:0.7.14 /uv /uvx /bin/

# Install Python packages
COPY reference/requirements/dbr16-full.txt /tmp/requirements.txt
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
ARG TERRAFORM_VERSION=1.12.2
RUN curl --remote-name --location https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && unzip terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && mv terraform /usr/bin \
    && rm LICENSE.txt terraform_${TERRAFORM_VERSION}_linux_${TARGETARCH}.zip \
    && terraform version

# Install Terragrunt
ARG TERRAGRUNT_VERSION="v0.81.10"
RUN curl -sL https://github.com/gruntwork-io/terragrunt/releases/download/${TERRAGRUNT_VERSION}/terragrunt_linux_${TARGETARCH} -o /usr/local/bin/terragrunt \
    && chmod +x /usr/local/bin/terragrunt \
    && terragrunt --version
```

### 3.3 DBR 15 Complete Requirements

```text
# reference/requirements/dbr15-full.txt
# Packages from https://docs.databricks.com/aws/en/release-notes/runtime/15.4lts#installed-python-libraries
# Tested and verified in production
asttokens==2.0.5
astunparse==1.6.3
azure-core==1.30.2
azure-storage-blob==12.19.1
azure-storage-file-datalake==12.14.0
backcall==0.2.0
black==23.3.0
blinker==1.4
boto3==1.34.39
botocore==1.34.39
cachetools==5.3.3
certifi==2023.7.22
cffi==1.15.1
chardet==4.0.0
charset-normalizer==2.0.4
click==8.0.4
cloudpickle==2.2.1
comm==0.1.2
contourpy==1.0.5
cryptography==41.0.3
cycler==0.11.0
Cython==0.29.32
databricks-sdk==0.20.0
debugpy==1.6.7
decorator==5.1.1
delta-spark==3.2.0
distlib==0.3.8
entrypoints==0.4
executing==0.8.3
facets-overview==1.1.1
filelock==3.13.4
fonttools==4.25.0
gitdb==4.0.11
GitPython==3.1.43
google-api-core==2.18.0
google-auth==2.31.0
google-cloud-core==2.4.1
google-cloud-storage==2.17.0
google-crc32c==1.5.0
google-resumable-media==2.7.1
googleapis-common-protos==1.63.2
grpcio==1.60.0
grpcio-status==1.60.0
httplib2==0.20.2
idna==3.4
importlib-metadata==6.0.0
ipyflow-core==0.0.198
ipython==8.15.0
ipython-genutils==0.2.0
ipywidgets==7.7.2
isodate==0.6.1
jedi==0.18.1
jeepney==0.7.1
jmespath==0.10.0
joblib==1.2.0
jupyter_client==7.4.9
jupyter_core==5.3.0
keyring==23.5.0
kiwisolver==1.4.4
launchpadlib==1.10.16
lazr.restfulclient==0.14.4
lazr.uri==1.0.6
matplotlib==3.7.2
matplotlib-inline==0.1.6
mlflow-skinny==2.11.4
more-itertools==8.10.0
mypy-extensions==0.4.3
nest-asyncio==1.5.6
numpy==1.23.5
oauthlib==3.2.0
packaging==23.2
pandas==1.5.3
parso==0.8.3
pathspec==0.10.3
patsy==0.5.3
pexpect==4.8.0
pickleshare==0.7.5
Pillow==9.4.0
pip==23.2.1
platformdirs==3.10.0
plotly==5.9.0
prompt-toolkit==3.0.36
proto-plus==1.24.0
protobuf==4.24.1
psutil==5.9.0
psycopg2==2.9.3
ptyprocess==0.7.0
pure-eval==0.2.2
pyarrow==14.0.1
pyasn1==0.4.8
pyasn1-modules==0.2.8
pyccolo==0.0.52
pycparser==2.21
pydantic==1.10.6
Pygments==2.15.1
PyJWT==2.3.0
pyodbc==4.0.39
pyparsing==3.0.9
pyspark==3.5.0
python-dateutil==2.8.2
python-lsp-jsonrpc==1.1.1
pytz==2022.7
PyYAML==6.0
pyzmq==23.2.0
requests==2.31.0
rsa==4.9
s3transfer==0.10.2
scikit-learn==1.3.0
scipy==1.11.1
seaborn==0.12.2
SecretStorage==3.3.1
setuptools==68.0.0
six==1.16.0
smmap==5.0.1
sqlparse==0.5.0
ssh-import-id==5.11
stack-data==0.2.0
statsmodels==0.14.0
tenacity==8.2.2
threadpoolctl==2.2.0
tokenize-rt==4.2.1
tornado==6.3.2
traitlets==5.7.1
typing_extensions==4.10.0
tzdata==2022.1
ujson==5.4.0
urllib3==1.26.16
virtualenv==20.24.2
wadllib==1.3.6
wcwidth==0.2.5
wheel==0.38.4
zipp==3.11.0
```

### 3.4 DBR 16 Complete Requirements

```text
# reference/requirements/dbr16-full.txt
# Packages from https://docs.databricks.com/aws/en/release-notes/runtime/16.4lts#installed-python-libraries
# Tested and verified in production
annotated-types==0.7.0
asttokens==2.0.5
astunparse==1.6.3
autocommand==2.2.2
azure-core==1.31.0
azure-storage-blob==12.23.0
azure-storage-file-datalake==12.17.0
backports.tarfile==1.2.0
black==24.4.2
blinker==1.7.0
boto3==1.34.69
botocore==1.34.69
cachetools==5.3.3
certifi==2024.6.2
cffi==1.16.0
chardet==4.0.0
charset-normalizer==2.0.4
click==8.1.7
cloudpickle==2.2.1
comm==0.2.1
contourpy==1.2.0
cryptography==42.0.5
cycler==0.11.0
Cython==3.0.11
databricks-sdk==0.30.0
debugpy==1.6.7
decorator==5.1.1
Deprecated==1.2.14
distlib==0.3.8
docstring-to-markdown==0.11
executing==0.8.3
facets-overview==1.1.1
filelock==3.15.4
fonttools==4.51.0
gitdb==4.0.11
GitPython==3.1.37
google-api-core==2.20.0
google-auth==2.35.0
google-cloud-core==2.4.1
google-cloud-storage==2.18.2
google-crc32c==1.6.0
google-resumable-media==2.7.2
googleapis-common-protos==1.65.0
grpcio==1.60.0
grpcio-status==1.60.0
httplib2==0.20.4
idna==3.7
importlib-metadata==6.0.0
importlib_resources==6.4.0
inflect==7.3.1
ipyflow-core==0.0.201
ipykernel==6.28.0
ipython==8.25.0
ipython-genutils==0.2.0
ipywidgets==7.7.2
isodate==0.6.1
jaraco.context==5.3.0
jaraco.functools==4.0.1
jaraco.text==3.12.1
jedi==0.19.1
jmespath==1.0.1
joblib==1.4.2
jupyter_client==8.6.0
jupyter_core==5.7.2
kiwisolver==1.4.4
launchpadlib==1.11.0
lazr.restfulclient==0.14.6
lazr.uri==1.0.6
matplotlib==3.8.4
matplotlib-inline==0.1.6
mccabe==0.7.0
mlflow-skinny==2.19.0
more-itertools==10.3.0
mypy==1.10.0
mypy-extensions==1.0.0
nest-asyncio==1.6.0
nodeenv==1.9.1
numpy==1.26.4
oauthlib==3.2.2
opentelemetry-api==1.27.0
opentelemetry-sdk==1.27.0
opentelemetry-semantic-conventions==0.48b0
packaging==24.1
pandas==1.5.3
parso==0.8.3
pathspec==0.10.3
patsy==0.5.6
pexpect==4.8.0
pillow==10.3.0
pip==24.2
platformdirs==3.10.0
plotly==5.22.0
pluggy==1.0.0
prompt-toolkit==3.0.43
proto-plus==1.24.0
protobuf==4.24.1
psutil==5.9.0
psycopg2==2.9.10
ptyprocess==0.7.0
pure-eval==0.2.2
pyarrow==15.0.2
pyasn1==0.4.8
pyasn1-modules==0.2.8
pyccolo==0.0.65
pycparser==2.21
pydantic==2.8.2
pydantic_core==2.20.1
pyflakes==3.2.0
Pygments==2.15.1
PyJWT==2.7.0
pyodbc==5.0.1
pyparsing==3.0.9
pyright==1.1.294
python-dateutil==2.9.0.post0
python-lsp-jsonrpc==1.1.2
python-lsp-server==1.10.0
pytoolconfig==1.2.6
pytz==2024.1
PyYAML==6.0.1
pyzmq==25.1.2
requests==2.32.2
rope==1.12.0
rsa==4.9
s3transfer==0.10.2
scikit-learn==1.4.2
scipy==1.13.1
seaborn==0.13.2
setuptools==74.0.0
six==1.16.0
smmap==5.0.0
sqlparse==0.5.1
ssh-import-id==5.11
stack-data==0.2.0
statsmodels==0.14.2
tenacity==8.2.2
threadpoolctl==2.2.0
tokenize-rt==4.2.1
tomli==2.0.1
tornado==6.4.1
traitlets==5.14.3
typeguard==4.3.0
types-protobuf==3.20.3
types-psutil==5.9.0
types-pytz==2023.3.1.1
types-PyYAML==6.0.0
types-requests==2.31.0.0
types-setuptools==68.0.0.0
types-six==1.16.0
types-urllib3==1.26.25.14
typing_extensions==4.11.0
ujson==5.10.0
urllib3==1.26.16
virtualenv==20.26.2
wadllib==1.3.6
wcwidth==0.2.5
whatthepatch==1.0.2
wheel==0.43.0
wrapt==1.14.1
zipp==3.17.0
```

## 4. Package Categorization

Based on the tested requirements, packages are categorized as follows:

### 4.1 Core Package Requirements

```python
# requirements/dbr15/core.txt
pandas==1.5.3
numpy==1.23.5
pyarrow==14.0.1
pyspark==3.5.0
delta-spark==3.2.0
databricks-sdk==0.20.0
requests==2.31.0
urllib3==1.26.16
certifi==2023.7.22
click==8.0.4
packaging==23.2
setuptools==68.0.0
pip==23.2.1
wheel==0.38.4
six==1.16.0
python-dateutil==2.8.2
pytz==2022.7
typing_extensions==4.10.0
```

```python
# requirements/dbr16/core.txt
pandas==1.5.3
numpy==1.26.4
pyarrow==15.0.2
pyspark==3.5.0
delta-spark==3.2.0
databricks-sdk==0.30.0
requests==2.32.2
urllib3==1.26.16
certifi==2024.6.2
click==8.1.7
packaging==24.1
setuptools==74.0.0
pip==24.2
wheel==0.43.0
six==1.16.0
python-dateutil==2.9.0.post0
pytz==2024.1
typing_extensions==4.11.0
```

### 4.2 ML Package Requirements

```python
# requirements/dbr15/ml.txt
scikit-learn==1.3.0
scipy==1.11.1
statsmodels==0.14.0
matplotlib==3.7.2
seaborn==0.12.2
plotly==5.9.0
mlflow-skinny==2.11.4
joblib==1.2.0
threadpoolctl==2.2.0
patsy==0.5.3
contourpy==1.0.5
cycler==0.11.0
fonttools==4.25.0
kiwisolver==1.4.4
Pillow==9.4.0
```

```python
# requirements/dbr16/ml.txt
scikit-learn==1.4.2
scipy==1.13.1
statsmodels==0.14.2
matplotlib==3.8.4
seaborn==0.13.2
plotly==5.22.0
mlflow-skinny==2.19.0
joblib==1.4.2
threadpoolctl==2.2.0
patsy==0.5.6
contourpy==1.2.0
cycler==0.11.0
fonttools==4.51.0
kiwisolver==1.4.4
pillow==10.3.0
```

### 4.3 Cloud Package Requirements

```python
# requirements/dbr15/cloud.txt
boto3==1.34.39
botocore==1.34.39
s3transfer==0.10.2
azure-core==1.30.2
azure-storage-blob==12.19.1
azure-storage-file-datalake==12.14.0
google-cloud-storage==2.17.0
google-cloud-core==2.4.1
google-auth==2.31.0
google-api-core==2.18.0
google-crc32c==1.5.0
google-resumable-media==2.7.1
googleapis-common-protos==1.63.2
```

```python
# requirements/dbr16/cloud.txt
boto3==1.34.69
botocore==1.34.69
s3transfer==0.10.2
azure-core==1.31.0
azure-storage-blob==12.23.0
azure-storage-file-datalake==12.17.0
google-cloud-storage==2.18.2
google-cloud-core==2.4.1
google-auth==2.35.0
google-api-core==2.20.0
google-crc32c==1.6.0
google-resumable-media==2.7.2
googleapis-common-protos==1.65.0
```

## 5. Wheel Specifications

### 5.1 Core Wheel

```toml
# wheels/dbr-env-core/pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "dbr-env-core"
version = "1.0.0"
description = "Databricks Runtime core Python dependencies"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "Apache-2.0"}

[project.optional-dependencies]
dbr15 = [
    "pandas==1.5.3",
    "numpy==1.23.5",
    "pyarrow==14.0.1",
    "pyspark==3.5.0",
    "delta-spark==3.2.0",
    "databricks-sdk==0.20.0",
    # ... rest from requirements/dbr15/core.txt
]
dbr16 = [
    "pandas==1.5.3",
    "numpy==1.26.4",
    "pyarrow==15.0.2",
    "pyspark==3.5.0",
    "delta-spark==3.2.0",
    "databricks-sdk==0.30.0",
    # ... rest from requirements/dbr16/core.txt
]
```

## 6. Installation Scripts

### 6.1 Pre-Installation Script

```bash
#!/bin/bash
# scripts/dbr-setup-pre
set -euo pipefail

VERSION="1.0.0"
DBR_VERSION=""
PLATFORM=""
NON_INTERACTIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            DBR_VERSION="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Detect platform if not specified
if [ -z "$PLATFORM" ]; then
    PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
fi

echo "Installing system dependencies for $DBR_VERSION on $PLATFORM"

# Install Java 17 (required for PySpark)
install_java() {
    echo "Installing Java 17..."

    if [ "$PLATFORM" = "linux" ]; then
        if command -v apt-get &> /dev/null; then
            apt-get update
            apt-get install -y openjdk-17-jdk-headless
            # Configure certificates for Java
            /var/lib/dpkg/info/ca-certificates-java.postinst configure || true
        elif command -v yum &> /dev/null; then
            yum install -y java-17-openjdk-headless
        fi
    elif [ "$PLATFORM" = "darwin" ]; then
        if command -v brew &> /dev/null; then
            brew install openjdk@17
        fi
    fi
}

# Install system packages
install_system_packages() {
    echo "Installing system packages..."

    if [ "$PLATFORM" = "linux" ]; then
        if command -v apt-get &> /dev/null; then
            apt-get install -y wget curl unzip zip jq
        elif command -v yum &> /dev/null; then
            yum install -y wget curl unzip zip jq
        fi
    elif [ "$PLATFORM" = "darwin" ]; then
        if command -v brew &> /dev/null; then
            brew install wget curl jq
        fi
    fi
}

# Main execution
main() {
    install_java
    install_system_packages

    echo "System dependencies installation complete"
    echo "Next: pip install dbr-env-all[$DBR_VERSION]"
}

main
```

### 6.2 Post-Installation Script

```bash
#!/bin/bash
# scripts/dbr-setup-post
set -euo pipefail

VERSION="1.0.0"
DBR_VERSION=""
INSTALL_DIR="/usr/local/bin"
SKIP_CHECKSUMS=false

# Version mappings from reference implementations
declare -A TOOL_VERSIONS_DBR15=(
    ["databricks-cli"]="0.245.0"
    ["terraform"]="1.11.2"
    ["terragrunt"]="0.77.0"
)

declare -A TOOL_VERSIONS_DBR16=(
    ["databricks-cli"]="0.256.0"
    ["terraform"]="1.12.2"
    ["terragrunt"]="0.81.10"
)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            DBR_VERSION="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --skip-checksums)
            SKIP_CHECKSUMS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Install Databricks CLI
install_databricks_cli() {
    local version="${TOOL_VERSIONS_DBR15[databricks-cli]}"
    if [ "$DBR_VERSION" = "dbr16" ]; then
        version="${TOOL_VERSIONS_DBR16[databricks-cli]}"
    fi

    echo "Installing Databricks CLI v${version}..."

    local platform=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    if [ "$arch" = "x86_64" ]; then
        arch="amd64"
    elif [ "$arch" = "aarch64" ]; then
        arch="arm64"
    fi

    local url="https://github.com/databricks/cli/releases/download/v${version}/databricks_cli_${version}_${platform}_${arch}.zip"

    wget -q "$url" -O /tmp/databricks_cli.zip
    unzip -q -o /tmp/databricks_cli.zip -d "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/databricks"
    rm /tmp/databricks_cli.zip

    echo "Databricks CLI installed"
}

# Install Terraform
install_terraform() {
    local version="${TOOL_VERSIONS_DBR15[terraform]}"
    if [ "$DBR_VERSION" = "dbr16" ]; then
        version="${TOOL_VERSIONS_DBR16[terraform]}"
    fi

    echo "Installing Terraform v${version}..."

    local platform=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    if [ "$arch" = "x86_64" ]; then
        arch="amd64"
    elif [ "$arch" = "aarch64" ]; then
        arch="arm64"
    fi

    local url="https://releases.hashicorp.com/terraform/${version}/terraform_${version}_${platform}_${arch}.zip"

    curl -L "$url" -o /tmp/terraform.zip
    unzip -q -o /tmp/terraform.zip terraform -d "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/terraform"
    rm /tmp/terraform.zip

    echo "Terraform installed"
}

# Install Terragrunt
install_terragrunt() {
    local version="${TOOL_VERSIONS_DBR15[terragrunt]}"
    if [ "$DBR_VERSION" = "dbr16" ]; then
        version="${TOOL_VERSIONS_DBR16[terragrunt]}"
    fi

    echo "Installing Terragrunt ${version}..."

    local platform=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    if [ "$arch" = "x86_64" ]; then
        arch="amd64"
    elif [ "$arch" = "aarch64" ]; then
        arch="arm64"
    fi

    local url="https://github.com/gruntwork-io/terragrunt/releases/download/${version}/terragrunt_${platform}_${arch}"

    curl -sL "$url" -o "$INSTALL_DIR/terragrunt"
    chmod +x "$INSTALL_DIR/terragrunt"

    echo "Terragrunt installed"
}

# Install AWS CLI
install_aws_cli() {
    echo "Installing AWS CLI..."

    local platform=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)

    if [ "$platform" = "linux" ]; then
        local aws_arch="x86_64"
        if [ "$arch" = "aarch64" ]; then
            aws_arch="aarch64"
        fi

        curl -L "https://awscli.amazonaws.com/awscli-exe-linux-${aws_arch}.zip" -o /tmp/awscliv2.zip
        unzip -q /tmp/awscliv2.zip -d /tmp
        /tmp/aws/install --install-dir /usr/local/aws-cli --bin-dir "$INSTALL_DIR"
        rm -rf /tmp/awscliv2.zip /tmp/aws
    fi

    echo "AWS CLI installed"
}

# Main execution
main() {
    mkdir -p "$INSTALL_DIR"

    install_databricks_cli
    install_terraform
    install_terragrunt
    install_aws_cli

    echo "Binary tools installation complete"
    echo "Run 'dbr-validate --version $DBR_VERSION' to verify (provided by dbr-env-all package)"
}

main
```

## 7. CI/CD Pipeline

### 7.1 Build Workflow

```yaml
# .github/workflows/build-wheels.yml
name: Build DBR Environment Wheels

on:
  push:
    branches: [main]
    paths:
      - 'wheels/**'
      - 'requirements/**'
      - 'reference/**'
  pull_request:
    branches: [main]

jobs:
  build-wheels:
    runs-on: [self-hosted, linux, dbr-builder]
    strategy:
      matrix:
        package: [core, ml, cloud, all]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install build tools
        run: |
          pip install --upgrade pip
          pip install build twine

      - name: Build wheel for ${{ matrix.package }}
        run: |
          cd wheels/dbr-env-${{ matrix.package }}
          python -m build --wheel

      - name: Validate wheel
        run: |
          cd wheels/dbr-env-${{ matrix.package }}
          twine check dist/*.whl

      - name: Upload wheel
        uses: actions/upload-artifact@v4
        with:
          name: wheel-${{ matrix.package }}
          path: wheels/dbr-env-${{ matrix.package }}/dist/*.whl
          retention-days: 7

  test-reference-dockerfiles:
    needs: build-wheels
    runs-on: [self-hosted, linux, dbr-builder]
    strategy:
      matrix:
        dbr-version: [15, 16]

    steps:
      - uses: actions/checkout@v4

      - name: Download wheels
        uses: actions/download-artifact@v4
        with:
          pattern: wheel-*
          path: dist/
          merge-multiple: true

      - name: Build reference Dockerfile
        run: |
          docker build -f docker/dockerfiles/dbr${{ matrix.dbr-version }}.Dockerfile \
            -t dbr-test:${{ matrix.dbr-version }} .

      - name: Test container
        run: |
          # Test Python version
          docker run --rm dbr-test:${{ matrix.dbr-version }} python --version

          # Test PySpark
          docker run --rm dbr-test:${{ matrix.dbr-version }} python -c "import pyspark; print(pyspark.__version__)"

          # Test tools
          docker run --rm dbr-test:${{ matrix.dbr-version }} databricks --version
          docker run --rm dbr-test:${{ matrix.dbr-version }} terraform version
          docker run --rm dbr-test:${{ matrix.dbr-version }} aws --version
```

## 8. Tool Version Summary

| Component | DBR 15 | DBR 16 |
|-----------|--------|--------|
| Python | 3.11 | 3.12 |
| UV | 0.6.12 | 0.7.14 |
| Databricks CLI | 0.245.0 | 0.256.0 |
| Terraform | 1.11.2 | 1.12.2 |
| Terragrunt | v0.77.0 | v0.81.10 |
| Java | 17 | 17 |
| Base Image | python:3.11-bullseye | python:3.12-bullseye |

## 9. Installation Guide

### 9.1 Quick Start

```bash
# 1. Install system dependencies (requires sudo)
sudo ./scripts/dbr-setup-pre --version dbr15

# 2. Install Python packages
pip install dbr-env-all[dbr15]

# 3. Install binary tools
./scripts/dbr-setup-post --version dbr15

# 4. Validate (command provided by dbr-env-all package)
dbr-validate --version dbr15
```

### 9.2 Docker Installation

```dockerfile
# Use reference Dockerfile as base
FROM python:3.11-bullseye

# Copy and run installation scripts
COPY scripts/ /tmp/scripts/
COPY dist/ /tmp/dist/

RUN /tmp/scripts/dbr-setup-pre --version dbr15 --non-interactive && \
    pip install /tmp/dist/dbr-env-all*.whl[dbr15] && \
    /tmp/scripts/dbr-setup-post --version dbr15

# Validate (command provided by dbr-env-all package)
RUN dbr-validate --version dbr15
```

---

*This specification includes tested reference implementations from production Dockerfiles and requirements files, providing a reliable foundation for building DBR environment setup tools.*
