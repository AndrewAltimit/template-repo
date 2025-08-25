# Gemini CLI Corporate Proxy Container
# Builds Gemini CLI from source and includes translation services

# Stage 1: Clone Gemini CLI source
FROM alpine/git AS source
ARG GEMINI_VERSION=HEAD
WORKDIR /source
RUN git clone https://github.com/google-gemini/gemini-cli.git && \
    cd gemini-cli && \
    if [ "$GEMINI_VERSION" != "HEAD" ]; then \
        git checkout "$GEMINI_VERSION"; \
    fi

# Stage 2: Build Gemini CLI
FROM node:20 AS builder
WORKDIR /build
COPY --from=source /source/gemini-cli ./gemini-cli

# Apply patches to redirect API calls to our proxy
COPY gemini/patches/api-redirect.patch /tmp/api-redirect.patch
COPY gemini/patches/auth-bypass.patch /tmp/auth-bypass.patch

WORKDIR /build/gemini-cli

# Try to apply patches, but don't fail if they don't apply cleanly
RUN patch -p1 < /tmp/api-redirect.patch || echo "api-redirect patch failed, will use environment variables"
RUN patch -p1 < /tmp/auth-bypass.patch || echo "auth-bypass patch failed, will use dummy key"

# Install dependencies and build
RUN npm ci
RUN npm run build

# Stage 3: Runtime container
FROM node:20-slim

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Add a non-root user with configurable UID/GID
# If the UID/GID already exists (e.g., node user), we'll use that
# Store the actual username for later use
RUN if getent passwd ${USER_ID} >/dev/null 2>&1; then \
        APP_USER=$(getent passwd ${USER_ID} | cut -d: -f1); \
    else \
        APP_USER=appuser; \
        groupadd -g ${GROUP_ID} ${APP_USER} || true; \
        useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash ${APP_USER}; \
    fi && \
    echo "export APP_USER=${APP_USER:-appuser}" >> /etc/environment

# Install Python for proxy services and runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    bash curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy the built Gemini CLI
COPY --from=builder /build/gemini-cli/bundle /opt/gemini-cli/bundle
COPY --from=builder /build/gemini-cli/package.json /opt/gemini-cli/package.json
COPY --from=builder /build/gemini-cli/node_modules /opt/gemini-cli/node_modules

# Patch the bundle to use our proxy instead of Google's API
RUN sed -i 's|https://generativelanguage.googleapis.com|http://localhost:8053|g' /opt/gemini-cli/bundle/gemini.js && \
    sed -i 's|generativelanguage.googleapis.com|localhost:8053|g' /opt/gemini-cli/bundle/gemini.js && \
    echo "✅ Patched Gemini bundle to use local proxy"

# Create a wrapper script for Gemini CLI
RUN echo '#!/bin/bash' > /usr/local/bin/gemini && \
    echo 'cd /opt/gemini-cli && exec node bundle/gemini.js "$@"' >> /usr/local/bin/gemini && \
    chmod +x /usr/local/bin/gemini

# Install Python dependencies for proxy
RUN pip3 install --break-system-packages flask flask-cors requests

# Copy proxy services (paths relative to corporate-proxy directory as build context)
COPY shared/services/mock_api.py /app/mock_api.py
COPY shared/services/translation_wrapper.py /app/translation_wrapper.py
COPY gemini/gemini_proxy_wrapper.py /app/gemini_proxy_wrapper.py

# Copy Gemini config
COPY gemini/config/gemini-config.json /app/config/gemini-config.json

# Copy shared configs for translation wrapper
COPY shared/configs /app/shared/configs

# Copy startup script
COPY gemini/scripts/gemini-wrapper.sh /app/gemini-wrapper.sh
RUN chmod +x /app/gemini-wrapper.sh

# Create Gemini config directories and pre-configure auth
# Use the actual user ID to ensure ownership works
RUN USER_HOME=$(getent passwd ${USER_ID} | cut -d: -f6) && \
    mkdir -p ${USER_HOME}/.config/gemini-cli ${USER_HOME}/.cache/gemini-cli && \
    mkdir -p ${USER_HOME}/.local/share ${USER_HOME}/.local/bin && \
    mkdir -p ${USER_HOME}/.gemini && \
    echo '{"selectedAuthType":"gemini-api-key"}' > ${USER_HOME}/.gemini/settings.json && \
    chown -R ${USER_ID}:${GROUP_ID} ${USER_HOME}

# Set proper ownership for app and workspace directories
RUN chown -R ${USER_ID}:${GROUP_ID} /app && \
    mkdir -p /workspace && \
    chown -R ${USER_ID}:${GROUP_ID} /workspace && \
    chown -R ${USER_ID}:${GROUP_ID} /opt/gemini-cli

WORKDIR /workspace

# Switch to the non-root user
USER ${USER_ID}

# Set HOME for Gemini CLI to find config
# Dynamically set based on the actual user
RUN echo "export HOME=$(getent passwd ${USER_ID} | cut -d: -f6)" >> ~/.bashrc
ENV HOME=/home/node

# Environment variables for Gemini CLI to use our proxy
ENV GEMINI_API_KEY="dummy-key-for-proxy"
ENV GOOGLE_API_KEY="dummy-key-for-proxy"
ENV GEMINI_API_BASE_URL="http://localhost:8053/v1"
ENV GEMINI_PROXY_BASE_URL="http://localhost:8053/v1"
ENV GOOGLE_GENAI_API_BASE_URL="http://localhost:8053/v1"

# Disable telemetry and auto-update
ENV GEMINI_TELEMETRY_DISABLED=1
ENV GEMINI_DISABLE_UPDATE_CHECK=1
ENV DISABLE_TELEMETRY=1

# Environment for proxy services
ENV USE_MOCK_API=true
ENV COMPANY_API_BASE="http://localhost:8050"
ENV COMPANY_API_TOKEN="test-secret-token-123"
ENV GEMINI_PROXY_PORT="8053"
ENV WRAPPER_PORT="8052"
ENV MOCK_API_PORT="8050"

# TLS verification - disabled by default for safety
# Only enable this if you need it for corporate networks with self-signed certs
# Set GEMINI_ALLOW_INSECURE_TLS=true at runtime if needed
# ENV NODE_TLS_REJECT_UNAUTHORIZED=0

EXPOSE 8050 8052 8053

ENTRYPOINT ["/app/gemini-wrapper.sh"]
CMD ["interactive"]
