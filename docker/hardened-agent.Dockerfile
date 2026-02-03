# syntax=docker/dockerfile:1.4
# Hardened Agent Container
#
# Provides a locked-down environment where:
# - Only git-guard and gh-validator wrappers are available as git/gh
# - Real binaries are at a restricted location (root:wrapper-guard 0750)
# - Package managers, curl, and wget are removed
# - Non-root "agent" user has no access to real binaries
#
# Usage:
#   docker compose --profile hardened build hardened-agent
#   docker compose --profile hardened run --rm hardened-agent git push --force  # blocked
#   docker compose --profile hardened run --rm hardened-agent bash

# ──────────────────────────────────────────────────────────
# Stage 1: Build the wrapper binaries
# ──────────────────────────────────────────────────────────
FROM rust:1.93-slim-bookworm AS builder

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy wrapper-common first (shared dependency)
COPY tools/rust/wrapper-common /build/wrapper-common

# Build git-guard
COPY tools/rust/git-guard /build/git-guard
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    cd /build/git-guard && cargo build --release

# Build gh-validator
COPY tools/rust/gh-validator /build/gh-validator
COPY .secrets.yaml /build/.secrets.yaml
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    cd /build/gh-validator && cargo build --release

# ──────────────────────────────────────────────────────────
# Stage 2: Runtime image with hardened binary access
# ──────────────────────────────────────────────────────────
FROM debian:bookworm-slim AS runtime

# Install real git and gh CLI
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install gh CLI from official repository
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl gpg \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Create the wrapper-guard group and restricted directory
RUN groupadd --system wrapper-guard \
    && mkdir -p /usr/lib/wrapper-guard

# Relocate real binaries to restricted location
RUN mv /usr/bin/git /usr/lib/wrapper-guard/git.real \
    && mv /usr/bin/gh /usr/lib/wrapper-guard/gh.real \
    && chown root:wrapper-guard /usr/lib/wrapper-guard /usr/lib/wrapper-guard/* \
    && chmod 0750 /usr/lib/wrapper-guard /usr/lib/wrapper-guard/*

# Install wrapper binaries as the commands users will invoke
# Wrappers are setgid wrapper-guard so they inherit group permission
# to execute the real binaries in the restricted directory.
COPY --from=builder /build/git-guard/target/release/git /usr/bin/git
COPY --from=builder /build/gh-validator/target/release/gh /usr/bin/gh
RUN chown root:wrapper-guard /usr/bin/git /usr/bin/gh \
    && chmod 2755 /usr/bin/git /usr/bin/gh

# Copy secrets config for gh-validator
COPY .secrets.yaml /etc/wrapper-guard/.secrets.yaml

# Remove bypass tools: package managers, download utilities, gpg
# This prevents the agent from installing alternative git/gh binaries
RUN apt-get purge -y curl wget gpg 2>/dev/null || true \
    && rm -f /usr/bin/curl /usr/bin/wget /usr/bin/gpg \
    && rm -rf /etc/apt /var/lib/apt /var/lib/dpkg/info \
    && rm -f /usr/bin/apt /usr/bin/apt-get /usr/bin/dpkg

# Create non-root user (NOT in wrapper-guard group)
# This user cannot execute the real binaries directly
RUN useradd -m -u 1000 agent

# Create directories the agent will need
RUN mkdir -p /home/agent/.local/share/wrapper-guard \
    && chown -R agent:agent /home/agent

USER agent
WORKDIR /workspace

# Verify the setup works
RUN /usr/bin/git --wrapper-integrity \
    && /usr/bin/gh --wrapper-integrity \
    && echo "Hardened agent container ready"
