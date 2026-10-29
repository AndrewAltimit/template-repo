# OpenCode Corporate Proxy Container
#
# OpenCode 2.x plus the shared translation services. OpenCode is routed to
# the Company API purely through its managed configuration
# (config/opencode.jsonc -> /etc/opencode/opencode.jsonc): a custom
# OpenAI-compatible "company" provider pointing at the local translation
# wrapper, and policies that deny every other provider. No OpenCode source
# files are patched, so the image can follow upstream releases by bumping
# OPENCODE_VERSION and its checksums.
#
# OpenCode binary source (build arg OPENCODE_BUILD):
#   release (default) - the upstream release tarball, checksum-verified.
#   source            - built from the release tag with upstream's own build
#                       script (packages/cli/script/build.ts), the same way
#                       upstream's release workflow builds it. Slow (installs
#                       the whole monorepo); use it when policy requires
#                       building from source.
# Both produce the musl build that upstream also ships in its own Docker
# image, so the runtime can stay on Alpine like the Crush proxy.

ARG OPENCODE_BUILD=release

# Pinned OpenCode release. Checksums come from the release's SHA256SUMS
# asset (opencode-linux-<arch>-musl.tar.gz).
ARG OPENCODE_VERSION=2.2.1

# ---------------------------------------------------------------------------
# Option 1: upstream release tarball
# ---------------------------------------------------------------------------
FROM alpine:3.24 AS opencode-release

COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

RUN apk add --no-cache curl

ARG OPENCODE_VERSION
ARG OPENCODE_CHECKSUM_AMD64=74ec74c74d8d8f65c354722a71396348d45e3b2323ff5051764e5a14f0d5a9e1
ARG OPENCODE_CHECKSUM_ARM64=bfe0052ed42e3d694523ed3522922bff5eff8ead8e0f9e9b9cd68f477a440bbd
# Docker buildx provides TARGETARCH
ARG TARGETARCH

RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) OC_ARCH="x64"; CHECKSUM="${OPENCODE_CHECKSUM_AMD64}" ;; \
        arm64) OC_ARCH="arm64"; CHECKSUM="${OPENCODE_CHECKSUM_ARM64}" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${OC_ARCH}-musl.tar.gz" -o /tmp/opencode.tar.gz; \
    echo "${CHECKSUM}  /tmp/opencode.tar.gz" | sha256sum -c -; \
    mkdir -p /out; \
    tar --no-same-owner -xzf /tmp/opencode.tar.gz -C /out opencode; \
    chmod 0755 /out/opencode; \
    rm /tmp/opencode.tar.gz

# ---------------------------------------------------------------------------
# Option 2: build from source with upstream's build script
# ---------------------------------------------------------------------------
# Mirrors the build-cli job of upstream's .github/workflows/release.yml:
# Bun 1.4.4 (root package.json packageManager), `bun install
# --frozen-lockfile`, a models.dev snapshot fetched once, then `bun run
# build` in packages/cli. OPENCODE_TARGET limits the build to the one musl
# target this image needs instead of all twelve release targets. Node and a
# C toolchain are needed by native install scripts (node-gyp), hence the
# full node image.
FROM node:24-bookworm AS opencode-source

COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

ARG BUN_VERSION=1.4.4
RUN npm install -g "bun@${BUN_VERSION}" && bun --version

ARG OPENCODE_VERSION
RUN git clone --depth 1 --branch "v${OPENCODE_VERSION}" https://github.com/anomalyco/opencode.git /src

WORKDIR /src
RUN bun install --frozen-lockfile
RUN bun packages/core/script/update-models-snapshot.ts .cache/models-catalog/api.json

ARG TARGETARCH
WORKDIR /src/packages/cli
RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) OC_ARCH="x64" ;; \
        arm64) OC_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    OPENCODE_VERSION="${OPENCODE_VERSION}" \
    OPENCODE_CHANNEL=latest \
    OPENCODE_TARGET="linux-${OC_ARCH}-musl" \
    OPENCODE_MODELS_SNAPSHOT=/src/.cache/models-catalog/api.json \
        bun run build; \
    mkdir -p /out; \
    cp "dist/cli-linux-${OC_ARCH}-musl/bin/opencode" /out/opencode; \
    chmod 0755 /out/opencode

# ---------------------------------------------------------------------------
# Selected OpenCode binary
# ---------------------------------------------------------------------------
FROM opencode-${OPENCODE_BUILD} AS opencode

# ---------------------------------------------------------------------------
# Runtime container
# ---------------------------------------------------------------------------
FROM python:3.13-alpine3.24

COPY automation/corporate-proxy/shared/scripts/install-corporate-certs.sh /tmp/install-certs.sh
RUN chmod +x /tmp/install-certs.sh && /tmp/install-certs.sh && rm /tmp/install-certs.sh

# libgcc/libstdc++ and ripgrep are what upstream's own musl image installs
# for the CLI; bash/curl/git serve the scripts and OpenCode's tools.
RUN apk add --no-cache bash curl git libgcc libstdc++ ripgrep

# Python dependencies for the proxy services
RUN pip install --no-cache-dir flask flask-cors requests

COPY --from=opencode /out/opencode /usr/local/bin/opencode
RUN opencode --version

# Managed OpenCode configuration (highest precedence; see the file header)
COPY automation/corporate-proxy/opencode/config/opencode.jsonc /etc/opencode/opencode.jsonc

# Shared translation services
COPY automation/corporate-proxy/shared/services/text_tool_parser.py /app/text_tool_parser.py
COPY automation/corporate-proxy/shared/services/translation_wrapper.py /app/translation_wrapper.py
COPY automation/corporate-proxy/shared/services/unified_tool_api.py /app/unified_tool_api.py
COPY automation/corporate-proxy/shared/services/api_spec_converter.py /app/api_spec_converter.py
COPY automation/corporate-proxy/shared/services/tool_prompts.py /app/tool_prompts.py

# Shared configs for the translation wrapper (it reads ../configs relative to
# the script and /configs for tool settings)
COPY automation/corporate-proxy/shared/configs /configs

COPY automation/corporate-proxy/opencode/scripts/start-services.sh /app/start-services.sh
RUN chmod +x /app/start-services.sh

# Non-root user. The run scripts and compose may override the UID, so
# start-services.sh falls back to a writable HOME when this one is not.
RUN adduser -D -u 1001 appuser && \
    mkdir -p /workspace && \
    chown -R appuser:appuser /app /workspace

WORKDIR /workspace
USER appuser
ENV HOME=/home/appuser

# OpenCode -> translation wrapper (company provider in opencode.jsonc). The
# key is a placeholder: the wrapper does not check it.
ENV COMPANY_PROXY_BASE_URL="http://localhost:8052/v1" \
    COMPANY_PROXY_API_KEY="local-translation-wrapper" \
    OPENCODE_DISABLE_AUTOUPDATE=1 \
    OPENCODE_DISABLE_MODELS_FETCH=1

# Translation wrapper -> Company API (the mock by default)
ENV COMPANY_API_BASE="http://localhost:8050" \
    COMPANY_API_TOKEN="test-secret-token-123" \
    WRAPPER_PORT="8052" \
    MOCK_API_PORT="8050" \
    AGENT_CLIENT="opencode"

EXPOSE 8050 8052

ENTRYPOINT ["/app/start-services.sh"]
