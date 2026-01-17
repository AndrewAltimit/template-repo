# syntax=docker/dockerfile:1.4
# Rust CI/CD Image for injection_toolkit and other Rust projects
# Performance optimizations:
# - BuildKit cache mounts for apt and cargo
# - Rust 1.83 (latest stable)
# - Incremental compilation cache

FROM rust:1.83-slim

# Install system dependencies with BuildKit cache
# libx11-dev etc. are needed for the overlay crate
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    libx11-dev \
    libxext-dev \
    libxrandr-dev \
    libxi-dev \
    libxcursor-dev \
    libxinerama-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install rustfmt and clippy components
RUN rustup component add rustfmt clippy

# Install cargo tools for CI
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    cargo install cargo-deny --locked 2>/dev/null || true

# Create working directory
WORKDIR /workspace

# Create a non-root user that will be overridden by docker-compose
# CARGO_HOME is set to /tmp/cargo at runtime for universal write access
RUN useradd -m -u 1000 ciuser

# Set cargo home to a cacheable location
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup

# Configure cargo for CI (faster linking, better output)
ENV CARGO_INCREMENTAL=1 \
    CARGO_NET_RETRY=10 \
    RUST_BACKTRACE=short

# Default command
CMD ["bash"]
